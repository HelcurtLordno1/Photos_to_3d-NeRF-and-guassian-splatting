"""Stop/resume contracts; real CUDA stop tests are separate session evidence."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import test_pipeline
from topic16.contracts import read_json, relative, sha256, write_json
from topic16.sessions import SessionPaused, StoppableLoader, average_eval_metrics, check_stop, remaining_iterations, resume_source


class SessionTests(unittest.TestCase):
    def test_evaluation_supports_read_only_loader_property(self):
        class Manager:
            @property
            def fixed_indices_eval_dataloader(self):
                return [0, 1, 2]
        class Pipeline:
            datamanager = Manager()
            def get_average_image_metrics(self, loader, prefix, **kwargs):
                return {'cameras': list(loader), 'prefix': prefix, **kwargs}
        self.assertEqual(average_eval_metrics(Pipeline(), get_std=True)['cameras'], [0, 1, 2])

    def test_remaining_budget_not_added_to_saved_steps(self):
        self.assertEqual(remaining_iterations(30000, 14999), 15000)
        self.assertEqual(remaining_iterations(30000, 29999), 0)
        for total, step in ((0, 0), (10, -1), (10, 10)):
            with self.assertRaises(ValueError):
                remaining_iterations(total, step)

    def test_stop_loader_checks_each_camera(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ, {'TOPIC16_SESSION_DIRECTORY': temporary}):
            loader = StoppableLoader([0, 1, 2])
            self.assertEqual(len(loader), 3)
            iterator = iter(loader)
            self.assertEqual(next(iterator), 0)
            Path(temporary, 'stop.json').write_text('{}')
            with self.assertRaises(SessionPaused):
                next(iterator)
            with self.assertRaises(SessionPaused):
                check_stop()

    def test_resume_rejects_tampered_checkpoint_and_protocol(self):
        fixture = test_pipeline.PipelineTests('runTest')
        fixture.setUp()
        try:
            root, settings = fixture.root, fixture.settings
            config = fixture.configs['nerfacto']
            logs = root / 'artifacts/logs/bonsai/nerfacto' / config.parent.name
            manifest = read_json(logs / 'manifest.json')
            manifest['status'] = 'failed'
            write_json(logs / 'manifest.json', manifest)
            checkpoint = config.parent / 'nerfstudio_models/step-000000099.ckpt'
            checkpoint.write_bytes(b'committed resume fixture')
            write_json(logs / 'resume.json', {'status': 'paused', 'step': 99, 'checkpoint': relative(root, checkpoint),
                'checkpoint_sha256': sha256(checkpoint), 'config_sha256': sha256(config)})
            split = read_json(logs / 'split.json')
            self.assertEqual(resume_source(root, config, settings, split, 'nerfacto', 'bonsai', 30000, 42, 'primary')['step'], 99)
            with self.assertRaises(ValueError):
                resume_source(root, config, settings, split, 'nerfacto', 'bonsai', 30000, 43, 'primary')
            checkpoint.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                resume_source(root, config, settings, split, 'nerfacto', 'bonsai', 30000, 42, 'primary')
        finally:
            fixture.tearDown()


if __name__ == '__main__':
    unittest.main()
