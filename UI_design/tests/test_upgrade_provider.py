"""Synthetic CPU contracts only; these fixtures are never study evidence."""
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from topic16.contracts import write_json,sha256,digest_json
from UI_design.backend.upgrade_provider import read_upgrade,merge_upgrade
from UI_design.backend.catalog import prepare


def make_bundle(root):
    from PIL import Image
    upgrade=root/'upgrade'; rows=[]
    camera={'path':'data/eval.png','sha256':'a'*64,'width':16,'height':16,'fx':10.,'fy':10.,'cx':8.,'cy':8.,'camera_to_world':[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,1.]]}
    policy={'GpuClockMinMHz':300,'GpuClockMaxMHz':800}
    for method in ('nerfacto','splatfacto'):
        key=f'custom-tiny/{method}/20260101T000000000Z'; logs=upgrade/'artifacts/logs'/key
        metrics=upgrade/'artifacts/metrics'/key; renders=upgrade/'artifacts/renders'/key; runs=upgrade/'artifacts/runs'/key
        for p in (logs,metrics,renders,runs/'nerfstudio_models'):p.mkdir(parents=True,exist_ok=True)
        config=runs/'config.yml';config.write_text('synthetic fixture only')
        checkpoint=runs/'nerfstudio_models/step-000009999.ckpt';checkpoint.write_bytes(b'fixture only, not a checkpoint')
        with zipfile.ZipFile(logs/'source.zip','w'):pass
        safety='artifacts/logs/safety/'+method+'.json';write_json(upgrade/safety,{'status':'succeeded','policy':policy})
        provenance={'source_files':{},'source_archive_sha256':sha256(logs/'source.zip'),
                    'checkpoint_path':checkpoint.relative_to(upgrade).as_posix(),'checkpoint_sha256':sha256(checkpoint),
                    'runtime_sha256':'fixture-runtime','gpu_safety_path':safety}
        split={'train':[{**camera,'path':'data/train.png'}],'eval':[camera],
               'capture':{'eval_camera_hash':'fixture-camera-frame','scene_group':'custom:tiny','selection_id':'selection'}}
        write_json(logs/'split.json',split);write_json(logs/'settings.json',policy);write_json(logs/'provenance.json',provenance)
        write_json(logs/'manifest.json',{'status':'succeeded','method':method,'protocol':{'iterations':10000,'seed':42,'downscale_factor':2}})
        images=[]
        for kind in ('gt','pred'):Image.new('RGB',(16,16),(50,60,70)).save(renders/(kind+'.png'))
        frame={'source':'data/eval.png','gt':'gt.png','pred':'pred.png','gt_sha256':sha256(renders/'gt.png'),'pred_sha256':sha256(renders/'pred.png')}
        write_json(metrics/'evaluation.json',{'status':'succeeded','split_hash':digest_json(split),'frames':[frame],'gpu_safety_path':safety})
        scores={'psnr':20.,'ssim':.8,'lpips':.2}
        write_json(metrics/'common-metrics.json',{'identity':{'evaluator_id':'fixture-common','runtime_id':'fixture-runtime','evaluation_sha256':sha256(metrics/'evaluation.json')},'metrics':scores})
        write_json(metrics/'metrics.json',{'results':scores})
        refs=[{'path':p.relative_to(upgrade).as_posix(),'sha256':sha256(p)} for p in [*logs.iterdir(),*metrics.iterdir(),config,checkpoint] if p.is_file()]
        rows.append({'status':'succeeded','variant':'upgrade','method':method,'run_key':key,'experiment_key':'fixture-'+method,
                     'references':refs,'config':config.relative_to(upgrade).as_posix(),'checkpoint_sha256':sha256(checkpoint),
                     'source_id':digest_json({}),'runtime_id':'fixture-runtime','safety_id':digest_json(policy),
                     'budget':10000,'seed':42,'downscale':2,'split_hash':digest_json(split),'evaluator_id':'fixture-common',
                     'eval_camera_hash':'fixture-camera-frame','scene_group':'custom:tiny','selection_id':'selection','views':1,
                     'eval_cameras':[camera],'metrics':scores,'provenance':provenance,'train_seconds':10.,'peak_vram_mb':100.,
                     'checkpoint_bytes':checkpoint.stat().st_size,'study':'fixture-only','recipe':'uniform',
                     'images':[{**frame,'gt':(renders/'gt.png').relative_to(upgrade).as_posix(),'pred':(renders/'pred.png').relative_to(upgrade).as_posix()}]})
    index={'schema_version':'capture-ui-index-1','runs':rows,'revision':'fixture','audit_assets':[],'models':[],'controlled_comparisons':[]}
    write_json(upgrade/'reports/ui-index.json',index)
    return index


class UpgradeProviderTests(unittest.TestCase):
    def test_smoke_evidence_is_retained_but_never_published_as_a_gallery_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);index=make_bundle(root)
            for row in index['runs']:row['tier']='smoke'
            write_json(root/'upgrade/reports/ui-index.json',index)
            self.assertEqual(len(read_upgrade(root)['runs']),2)
            scenes=[];status=merge_upgrade(root,scenes,lambda *args:'/fixture')
            self.assertEqual(status['runs'],[]);self.assertEqual(scenes,[])

    def test_upgrade_only_catalog_supports_metrics_without_exports_or_fps(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);make_bundle(root)
            result=prepare(root,{'Ui':{'MaxVertices':3000000,'DecodeLimitBytes':600000000}})
            self.assertEqual(len(result['catalog']['scenes']),1)
            scene=result['catalog']['scenes'][0]
            self.assertEqual(len(scene['run_sets']),1);self.assertFalse(scene['inference'])
            self.assertIsNone(scene['methods']['nerfacto']['offline_fps'])
            self.assertEqual(scene['methods']['nerfacto']['asset'],'')

    def test_multiple_run_sets_merge_into_one_gallery_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);make_bundle(root)
            scenes=[{'id':'custom:tiny','run_sets':[{'id':'baseline','variant':'baseline'}]}]
            status=merge_upgrade(root,scenes,lambda path,expected=None:'/fixture-asset')
            self.assertEqual(status['status'],'ready');self.assertEqual(len(scenes),1);self.assertEqual(len(scenes[0]['run_sets']),2)

    def test_half_pair_is_visible_as_completed_run_but_not_a_paired_gallery_scene(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);index=make_bundle(root);index['runs']=index['runs'][:1]
            write_json(root/'upgrade/reports/ui-index.json',index)
            scenes=[];status=merge_upgrade(root,scenes,lambda *args:'/fixture')
            self.assertEqual(len(status['runs']),1);self.assertEqual(scenes,[])

    def test_malformed_upgrade_does_not_remove_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);write_json(root/'upgrade/reports/ui-index.json',{'schema_version':'unsupported'})
            scenes=[{'id':'baseline'}];status=merge_upgrade(root,scenes,lambda *args:'/fixture')
            self.assertEqual(status['status'],'invalid');self.assertEqual(scenes,[{'id':'baseline'}])

    def test_tampered_metric_and_path_escape_are_rejected(self):
        for tamper in ('metric','escape','image'):
            with self.subTest(tamper=tamper),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);index=make_bundle(root)
                if tamper=='metric':index['runs'][0]['metrics']={'psnr':999.,'ssim':.8,'lpips':.2}
                elif tamper=='escape':index['runs'][0]['references'][0]['path']='../outside'
                else:(root/'upgrade'/index['runs'][0]['images'][0]['pred']).write_bytes(b'changed')
                write_json(root/'upgrade/reports/ui-index.json',index)
                with self.assertRaises((ValueError,FileNotFoundError)):read_upgrade(root)

    def test_cross_method_or_forged_delta_cannot_be_a_selector_improvement(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);index=make_bundle(root)
            index['controlled_comparisons']=[{'status':'controlled-pair','left':index['runs'][0]['run_key'],
                'right':index['runs'][1]['run_key'],'delta':{'psnr':99.,'ssim':0.,'lpips':0.}}]
            write_json(root/'upgrade/reports/ui-index.json',index)
            with self.assertRaisesRegex(ValueError,'Controlled comparison'):read_upgrade(root)


if __name__=='__main__':unittest.main()
