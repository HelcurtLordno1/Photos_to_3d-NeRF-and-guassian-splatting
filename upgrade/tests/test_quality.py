"""Quality-specific boundaries: unsupported protocols, ROI lock, exact paused config."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import nullcontext
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from topic16_upgrade.contracts import write_json,read_json,sha256,digest_json
from topic16_upgrade.quality import state_path,execute
from topic16_upgrade.quality_report import lock_rois
from topic16_upgrade.sessions import SessionPaused


class QualityTests(unittest.TestCase):
    def test_native_protocol_rejects_wrong_method_resolution_or_budget_before_gpu(self):
        from topic16_upgrade.runtime import train
        for method,factor,total in (('nerfacto',1,30000),('splatfacto',2,30000),('splatfacto',1,10000)):
            with self.subTest(method=method,factor=factor,total=total),patch('topic16_upgrade.runtime.gpu_lock') as lock:
                with self.assertRaisesRegex(ValueError,'Native quality protocol'):
                    train(Path('.'),{'DownscaleFactor':factor,'RandomSeed':42},method,'custom:tea',total,42,'capture-native-30k-v2')
                lock.assert_not_called()

    def test_roi_must_cover_exact_locked_camera_list_and_stay_inside_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);split={'eval':[{'width':719,'height':1279}]}
            p=root/'reports/tea-quality-v2/q0/rois.json'
            with self.assertRaisesRegex(ValueError,'committed'):lock_rois(root,split)
            write_json(p,{'native_eval_hash':digest_json(split['eval']),'boxes':[[1,2,719,1279]]})
            self.assertEqual(lock_rois(root,split),p)
            write_json(p,{'native_eval_hash':digest_json(split['eval']),'boxes':[[1,2,720,1279]]})
            with self.assertRaisesRegex(ValueError,'outside'):lock_rois(root,split)
            write_json(p,{'native_eval_hash':'changed','boxes':[[1,2,719,1279]]})
            with self.assertRaisesRegex(ValueError,'differ'):lock_rois(root,split)

    def record(self,root):
        proof=root/'reports/q0.json';write_json(proof,{'scope':'fixture'})
        record={'status':'planned','attempts':[],'config':None,'stages':{'q0':{'path':'reports/q0.json','sha256':sha256(proof)}}}
        settings={'VisualQuality':{'Condition':'custom:tea_sets_2-native-v2','MaximumExplorationGpuSeconds':21600}}
        return record,settings

    def test_changed_q0_evidence_blocks_training(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);record,settings=self.record(root)
            write_json(root/'reports/q0.json',{'changed':True})
            with patch('topic16_upgrade.quality.prepare',return_value=record),patch('topic16_upgrade.runtime.gpu_lock',return_value=nullcontext()),patch('topic16_upgrade.data.freeze_split',return_value={}),patch('topic16_upgrade.runtime.train') as train:
                with self.assertRaisesRegex(ValueError,'Q0 proof changed'):execute(root,settings,root/'baseline','tea-quality-v2')
            train.assert_not_called()
            self.assertEqual(read_json(state_path(root,'tea-quality-v2'))['status'],'failed')

    def test_pause_keeps_latest_checkpoint_config_and_attempt_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);record,settings=self.record(root)
            config=root/'artifacts/runs/custom-tea_sets_2-native-v2/splatfacto/attempt/config.yml'
            failure=SessionPaused('checkpoint committed',config)
            with patch('topic16_upgrade.quality.prepare',return_value=record),patch('topic16_upgrade.runtime.gpu_lock',return_value=nullcontext()),patch('topic16_upgrade.data.freeze_split',return_value={}),patch('topic16_upgrade.runtime.train',side_effect=failure):
                with self.assertRaises(SessionPaused):execute(root,settings,root/'baseline','tea-quality-v2')
            saved=read_json(state_path(root,'tea-quality-v2'))
            self.assertEqual(saved['status'],'paused');self.assertEqual(saved['config'],config.relative_to(root).as_posix())
            self.assertGreaterEqual(saved['attempts'][0]['wall_seconds'],0)


if __name__=='__main__':unittest.main()
