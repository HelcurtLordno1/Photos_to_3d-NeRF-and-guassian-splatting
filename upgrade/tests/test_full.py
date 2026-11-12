"""Dataset ordering and failure boundaries, without invoking training or CUDA."""
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from topic16_upgrade.contracts import read_json,write_json
from topic16_upgrade.full import run,campaign_path
from topic16_upgrade.sessions import SessionPaused
from topic16_upgrade.source_pin import freeze_current,activate,execution_sources,PIN_ENV
from topic16_upgrade.settings import experiment_settings_hash
import os


class FullCampaignTests(unittest.TestCase):
    def fixture(self,root):
        settings={};items=[{'scene':s,'study':s,'training_jobs':6,'status':'pending'} for s in ('tea','bonsai')]
        write_json(campaign_path(root,'full'),{'settings_hash':experiment_settings_hash(settings),'status':'planned','datasets':items})
        return settings

    def test_next_dataset_never_starts_before_prior_acceptance_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);settings=self.fixture(root);events=[]
            with patch('topic16_upgrade.runtime.gpu_lock',return_value=nullcontext()),patch('topic16_upgrade.full.preflight'),patch('topic16_upgrade.full.validate_declaration'),patch('topic16_upgrade.full.sha256',return_value='fixture'),\
                 patch('topic16_upgrade.full.execute',side_effect=lambda *args,**kw:events.append(('train',args[3]))),\
                 patch('topic16_upgrade.full.dataset_gate',side_effect=lambda *args:events.append(('gate',args[3]['scene'])) or {'finished_at':'fixture'}):
                result=run(root,settings,root/'baseline','full')
            self.assertEqual(events,[('train','tea'),('gate','tea'),('train','bonsai'),('gate','bonsai')])
            self.assertEqual(result['status'],'succeeded')

    def test_failed_or_stopped_dataset_blocks_all_later_gpu_work(self):
        for error,status in ((ValueError('export evidence missing'),'failed'),(SessionPaused('requested stop'),'paused')):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);settings=self.fixture(root)
                with patch('topic16_upgrade.runtime.gpu_lock',return_value=nullcontext()),patch('topic16_upgrade.full.preflight'),patch('topic16_upgrade.full.validate_declaration'),\
                     patch('topic16_upgrade.full.execute') as execute,patch('topic16_upgrade.full.dataset_gate',side_effect=error):
                    with self.assertRaises(type(error)):run(root,settings,root/'baseline','full')
                self.assertEqual(execute.call_count,1)
                saved=read_json(campaign_path(root,'full'))
                self.assertEqual(saved['status'],status);self.assertEqual(saved['datasets'][1]['status'],'pending')

    def test_resume_revalidates_completed_dataset_before_starting_next(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);settings=self.fixture(root);path=campaign_path(root,'full');saved=read_json(path)
            saved['datasets'][0]['status']='succeeded';saved['status']='paused';write_json(path,saved)
            with patch('topic16_upgrade.runtime.gpu_lock',return_value=nullcontext()),patch('topic16_upgrade.full.validate_declaration'),\
                 patch('topic16_upgrade.full.validate_gate',side_effect=ValueError('checkpoint changed')),\
                 patch('topic16_upgrade.full.execute') as execute:
                with self.assertRaisesRegex(ValueError,'checkpoint changed'):run(root,settings,root/'baseline','full',True)
            execute.assert_not_called()

    def test_full_studies_share_one_verified_source_without_accepting_registry_drift(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ):
            root=Path(directory);(root/'src').mkdir();(root/'configs').mkdir()
            (root/'src/worker.py').write_text('original numerical code')
            registry=root/'configs/project.psd1';registry.write_text('@{TrainIterations=30000}')
            first=freeze_current(root,'tea');freeze_current(root,'bonsai',first)
            activate(root,'tea');source,files,_=execution_sources(root)
            activate(root,'bonsai');other,otherfiles,_=execution_sources(root)
            self.assertEqual(source,other);self.assertEqual(files,otherfiles)
            registry.write_text('@{TrainIterations=10}')
            with self.assertRaisesRegex(ValueError,'Registry changed'):activate(root,'tea')


if __name__=='__main__':unittest.main()
