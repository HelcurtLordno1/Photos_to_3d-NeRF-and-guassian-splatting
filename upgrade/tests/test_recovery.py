"""Regression coverage for real resumed-run evidence and recovery identities."""
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from topic16_upgrade.contracts import (write_json,read_json,digest_json,sha256,relative,
    run_paths,load_run,file_required,validate_evidence_file)
from topic16_upgrade.source_pin import create_pin,activate,execution_sources,source_files,identity,PIN_ENV


def fixture(root, timestamp):
    key=f'bonsai/nerfacto/{timestamp}'
    paths=run_paths(root,key)
    for directory in paths.values():directory.mkdir(parents=True)
    config=paths['runs']/'config.yml';config.write_text('synthetic only\n')
    checkpoint=paths['runs']/'nerfstudio_models/step-000009999.ckpt'
    checkpoint.parent.mkdir();checkpoint.write_bytes(b'checkpoint fixture, never deserialized')
    camera=[[1,0,0,0],[0,1,0,0],[0,0,1,0]]
    split={'train':[{'path':'data/train.png','sha256':'a'*64,'camera_to_world':camera}],
           'eval':[{'path':'data/eval.png','sha256':'b'*64,'camera_to_world':camera}]}
    settings={'TrainIterations':10000,'RandomSeed':42,'DownscaleFactor':2,'EvalInterval':8}
    provenance={'config_sha256':sha256(config),'checkpoint_sha256':sha256(checkpoint),
        'checkpoint_path':relative(root,checkpoint),'settings_hash':digest_json(settings),'runtime_sha256':'c'*64}
    manifest={'schema_version':'1.0','run_key':key,'scene':'bonsai','method':'nerfacto','status':'succeeded',
        'protocol':{'iterations':10000,'seed':42,'downscale_factor':2,'eval_interval':8},
        'provenance':{'dataset_split_hash':digest_json(split)},
        'execution_metrics':{'wall_time_seconds':10.,'peak_vram_mb':1000.}}
    for name,value in (('manifest.json',manifest),('provenance.json',provenance),('split.json',split),('settings.json',settings)):
        write_json(paths['logs']/name,value)
    for name in ('command.txt','train.log','timing.env','gpu.csv','run.env'):(paths['logs']/name).write_text('fixture\n')
    (paths['logs']/'git-diff.txt').write_bytes(b'')
    for kind in ('gt','pred'):(paths['renders']/(kind+'.png')).write_bytes(b'pixels')
    write_json(paths['metrics']/'metrics.json',{'checkpoint':relative(root,checkpoint),'results':{'psnr':20.,'ssim':.8,'lpips':.2}})
    write_json(paths['metrics']/'evaluation.json',{'status':'succeeded','run_key':key,'split_hash':digest_json(split),
        'config_sha256':sha256(config),'checkpoint_sha256':sha256(checkpoint),
        'metrics_sha256':sha256(paths['metrics']/'metrics.json'),
        'frames':[{'source':'data/eval.png','gt':'gt.png','pred':'pred.png',
            'gt_sha256':sha256(paths['renders']/'gt.png'),'pred_sha256':sha256(paths['renders']/'pred.png')}]})
    return load_run(root,config,require_eval=True)


class ResumedEvidenceTests(unittest.TestCase):
    def graph(self,root):
        parent=fixture(root,'20260101T000000000Z');child=fixture(root,'20260101T000001000Z')
        provenance=child['provenance']
        provenance['resumed_from']={'run_key':parent['manifest']['run_key'],
            'checkpoint':relative(root,parent['checkpoint']),'checkpoint_sha256':sha256(parent['checkpoint']),
            'evidence':[{'path':relative(root,p),'sha256':sha256(p),'bytes':p.stat().st_size}
                        for p in sorted(parent['paths']['logs'].iterdir()) if p.is_file()]}
        write_json(child['paths']['logs']/'provenance.json',provenance)
        return parent,child

    def test_full_load_run_and_evaluation_accept_empty_git_diff_after_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);parent,child=self.graph(root)
            actual=load_run(root,child['config'],require_eval=True)
            self.assertEqual(actual['checkpoint'],child['checkpoint'])
            self.assertEqual((parent['paths']['logs']/'git-diff.txt').stat().st_size,0)

    def test_missing_git_diff_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);parent,child=self.graph(root)
            (parent['paths']['logs']/'git-diff.txt').unlink()
            with self.assertRaises(ValueError):load_run(root,child['config'])

    def test_changed_empty_evidence_hash_is_still_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);parent,child=self.graph(root)
            (parent['paths']['logs']/'git-diff.txt').write_text('modified')
            with self.assertRaisesRegex(ValueError,'checksum'):load_run(root,child['config'])

    def test_empty_checkpoint_or_required_log_never_qualifies_as_optional_text(self):
        for target in ('checkpoint','train.log'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);parent,child=self.graph(root)
                path=parent['checkpoint'] if target=='checkpoint' else parent['paths']['logs']/target
                path.write_bytes(b'')
                with self.assertRaises(ValueError):load_run(root,child['config'])

    def test_evidence_cannot_be_borrowed_from_another_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);parent,child=self.graph(root)
            provenance=read_json(child['paths']['logs']/'provenance.json')
            p=child['paths']['logs']/'git-diff.txt'
            provenance['resumed_from']['evidence'].append({'path':relative(root,p),'sha256':sha256(p)})
            write_json(child['paths']['logs']/'provenance.json',provenance)
            with self.assertRaisesRegex(ValueError,'another run'):load_run(root,child['config'])

    def test_atomic_json_retries_transient_windows_sharing_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json';write_json(path,{'old':True});original=Path.replace;calls=[]
            def flaky(source,target):
                calls.append(1)
                if len(calls)<3:raise PermissionError('simulated Windows sharing violation')
                return original(source,target)
            with patch.object(Path,'replace',flaky),patch('time.sleep'):
                write_json(path,{'new':True})
            self.assertEqual(read_json(path),{'new':True});self.assertEqual(len(calls),3)


class SourcePinTests(unittest.TestCase):
    def setup_pin(self,root):
        src=root/'src/adapter.py';src.parent.mkdir();src.write_text('original training adapter')
        registry=root/'configs/project.psd1';registry.parent.mkdir();registry.write_text('@{Seed=42}')
        files=source_files(root);sid=identity(files)
        config=root/'artifacts/runs/bonsai/nerfacto/20260101T000000000Z/config.yml';config.parent.mkdir(parents=True);config.write_text('fixture')
        logs=root/'artifacts/logs'/config.parent.relative_to(root/'artifacts/runs');logs.mkdir(parents=True)
        with zipfile.ZipFile(logs/'source.zip','w') as snapshot:
            for name in files:snapshot.write(root/name,name)
        write_json(logs/'provenance.json',{'source_files':files,'source_archive_sha256':sha256(logs/'source.zip')})
        write_json(root/'artifacts/jobs/tea-plan.json',{'jobs':[{'identity':{'source_id':sid}}]})
        write_json(root/'artifacts/jobs/ledger.json',{'jobs':{'key':{'study':'tea','config':relative(root,config)}}})
        src.write_text('new controller implementation')
        return create_pin(root,'tea'),src,registry

    def test_repair_reuses_original_training_bytes_without_rewriting_original_archive(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ):
            root=Path(directory);pin,src,_=self.setup_pin(root);activate(root,'tea')
            tree,files,record=execution_sources(root)
            self.assertNotEqual(source_files(root),files)
            self.assertEqual((tree/'src/adapter.py').read_text(),'original training adapter')
            self.assertEqual(identity(files),pin['source_id'])
            self.assertEqual(src.read_text(),'new controller implementation')

    def test_modified_pinned_source_or_registry_is_rejected(self):
        for target in ('source','registry'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as directory,patch.dict(os.environ):
                root=Path(directory);pin,_,registry=self.setup_pin(root)
                path=root/pin['tree']/'src/adapter.py' if target=='source' else registry
                path.write_text('tampered')
                with self.assertRaises(ValueError):activate(root,'tea')

    def test_pin_does_not_leak_to_unrelated_study(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ):
            root=Path(directory);self.setup_pin(root);activate(root,'tea');self.assertIn(PIN_ENV,os.environ)
            activate(root,'other');self.assertNotIn(PIN_ENV,os.environ)


if __name__=='__main__':unittest.main()
