"""Exercise queue interruption and reuse without pretending to measure CUDA."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from topic16_upgrade.study import _execute
from topic16_upgrade.contracts import write_json, read_json
from topic16_upgrade.sessions import SessionPaused


class QueueTests(unittest.TestCase):
    def setup_mocks(self, stack, root, key='key'):
        baseline=root/'input'; baseline.mkdir(exist_ok=True)
        item={'experiment_key':key,'identity':{'method':'nerfacto'},'selection':{},'condition':'custom:tiny','recipe':'uniform','views':6}
        matrix={'jobs':[item],'storage':{'reserve_gib':30,'estimated_new_gib':1,'free_gib':100}}
        settings={'Studies':{'tiny':{'Scene':'custom:tiny','Iterations':10000,'Seed':42,'Protocol':'capture-subset-10k-v1'}}}
        stack.enter_context(patch('topic16_upgrade.study.plan',return_value=matrix))
        stack.enter_context(patch('topic16_upgrade.study.capture_split',return_value=({},{})))
        stack.enter_context(patch('topic16_upgrade.study.materialize'))
        stack.enter_context(patch('topic16_upgrade.preservation.inventory',return_value={}))
        published={'experiment_key':key,'recipe':'uniform','method':'nerfacto','run_key':'fixture',
                   'train_seconds':1.,'evaluation_cpu_seconds':1.,'metrics':{'psnr':20.,'ssim':.8,'lpips':.2}}
        publish=stack.enter_context(patch('topic16_upgrade.study.publish',return_value={'runs':[published],'controlled_comparisons':[]}))
        return baseline,item,settings,publish

    def test_paused_job_retains_exact_config_for_resume(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); baseline,item,settings,_=self.setup_mocks(stack,root)
            config=root/'artifacts/runs/custom-tiny/nerfacto/20260101T000000000Z/config.yml'
            config.parent.mkdir(parents=True);config.write_text('fixture')
            failure=SessionPaused('checkpoint committed',config)
            training=stack.enter_context(patch('topic16_upgrade.runtime.train',side_effect=failure))
            with self.assertRaises(SessionPaused):_execute(root,settings,baseline,'tiny',False,None)
            job=read_json(root/'artifacts/jobs/ledger.json')['jobs']['key']
            self.assertEqual(job['status'],'paused');self.assertEqual(job['config'],config.relative_to(root).as_posix())
            self.assertEqual(len(job['attempts']),1)

    def test_completed_job_reuses_without_training_or_materialization(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); baseline,item,settings,publish=self.setup_mocks(stack,root)
            write_json(root/'artifacts/jobs/ledger.json',{'jobs':{'key':{**item,'study':'tiny','status':'succeeded'}}})
            stack.enter_context(patch('topic16_upgrade.study.completed',return_value=True))
            training=stack.enter_context(patch('topic16_upgrade.runtime.train'))
            _execute(root,settings,baseline,'tiny',True,None)
            training.assert_not_called();publish.assert_called_once()

    def test_source_or_runtime_change_rejects_resume_before_new_work(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); baseline,item,settings,_=self.setup_mocks(stack,root,key='changed')
            write_json(root/'artifacts/jobs/ledger.json',{'jobs':{'original':{**item,'experiment_key':'original','study':'tiny','status':'paused'}}})
            training=stack.enter_context(patch('topic16_upgrade.runtime.train'))
            with self.assertRaisesRegex(ValueError,'identity changed'):_execute(root,settings,baseline,'tiny',True,None)
            training.assert_not_called()

    def test_eval_failure_retains_completed_training_to_avoid_retraining(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root=Path(directory); baseline,item,settings,_=self.setup_mocks(stack,root)
            config=root/'artifacts/runs/custom-tiny/nerfacto/20260101T000000000Z/config.yml'
            config.parent.mkdir(parents=True); config.write_text('fixture')
            stack.enter_context(patch('topic16_upgrade.runtime.train',return_value=config))
            stack.enter_context(patch('topic16_upgrade.runtime.evaluate',side_effect=ValueError('evaluation interrupted')))
            with self.assertRaisesRegex(ValueError,'evaluation interrupted'):_execute(root,settings,baseline,'tiny',False,None)
            saved=read_json(root/'artifacts/jobs/ledger.json')['jobs']['key']
            self.assertEqual(saved['status'],'failed');self.assertEqual(saved['config'],config.relative_to(root).as_posix())

    def test_materialization_error_is_not_hidden_by_uninitialized_stage_state(self):
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);baseline,item,settings,_=self.setup_mocks(stack,root)
            stack.enter_context(patch('topic16_upgrade.study.materialize',side_effect=ValueError('input checksum mismatch')))
            with self.assertRaisesRegex(ValueError,'input checksum mismatch'):_execute(root,settings,baseline,'tiny',False,None)
            saved=read_json(root/'artifacts/jobs/ledger.json')['jobs']['key']
            self.assertEqual(saved['error'],'input checksum mismatch')

    def test_publish_failure_keeps_completed_training_and_evaluation_success(self):
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            root=Path(directory);baseline,item,settings,publish=self.setup_mocks(stack,root)
            config=root/'artifacts/runs/custom-tiny/nerfacto/20260101T000000000Z/config.yml'
            config.parent.mkdir(parents=True);config.write_text('fixture')
            metrics=root/'artifacts/metrics/fixture';metrics.mkdir(parents=True);(metrics/'common-metrics.json').write_text('{}')
            stack.enter_context(patch('topic16_upgrade.runtime.train',return_value=config))
            stack.enter_context(patch('topic16_upgrade.runtime.evaluate'))
            stack.enter_context(patch('topic16_upgrade.study.evaluate_common',return_value={}))
            stack.enter_context(patch('topic16_upgrade.study.load_run',return_value={'paths':{'metrics':metrics},'manifest':{'execution_metrics':{'wall_time_seconds':1.}}}))
            publish.side_effect=PermissionError('UI output temporarily locked')
            with self.assertRaises(PermissionError):_execute(root,settings,baseline,'tiny',False,None)
            saved=read_json(root/'artifacts/jobs/ledger.json')['jobs']['key']
            self.assertEqual(saved['status'],'succeeded');self.assertEqual(saved['publication_status'],'failed')
            self.assertEqual(saved['config'],config.relative_to(root).as_posix())


if __name__=='__main__':unittest.main()
