import copy
from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from topic16_upgrade.teacher import validate_profile, resolve
from topic16_upgrade.teacher_worker import ARMS, differences, plain
from topic16_upgrade.teacher_report import conditional_effects, publish
from topic16_upgrade.contracts import sha256, write_json, read_json
from topic16_upgrade.teacher import reference


class TeacherContracts(unittest.TestCase):
    def test_only_requested_model_interventions_exist(self):
        self.assertEqual(ARMS, {'A': ('off', True), 'B': ('SO3xR3', False), 'C': ('off', False)})
        # B/C remove conditioning, rather than toggling its average inference mode.
        self.assertFalse(ARMS['B'][1]); self.assertFalse(ARMS['C'][1])

    def test_nested_recipe_audit_catches_unrelated_training_change(self):
        @dataclass
        class Model:
            appearance: bool = True
            learning_rate: float = .01
        original = {'model': plain(Model())}
        self.assertIsInstance(plain(Model), str)
        candidate = copy.deepcopy(original)
        candidate['model']['appearance'] = False
        self.assertEqual(set(differences(original, candidate)), {'model.appearance'})
        candidate['model']['learning_rate'] = .001
        self.assertEqual(set(differences(original, candidate)), {'model.appearance', 'model.learning_rate'})

    def test_evidence_reuse_fails_for_missing_or_changed_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / 'result.json'; path.write_text('original')
            ref = {'path': 'result.json', 'sha256': sha256(path)}
            self.assertEqual(resolve(root, ref), path)
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed'): resolve(root, ref)
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'Missing'): resolve(root, ref)

    def test_effects_use_only_current_conditional_pairs_not_historical_interaction(self):
        rows = [{'id': name, 'metrics': {'psnr': p, 'ssim': p / 100, 'lpips': 1 - p / 100}}
            for name, p in [('historical-nerfacto', 22.9), ('A', 26), ('B', 28), ('C', 30)]]
        effects = conditional_effects(rows)
        self.assertEqual([e['comparison'] for e in effects], ['C-minus-B', 'C-minus-A'])
        self.assertEqual([e['delta']['psnr'] for e in effects], [2, 4])
        self.assertEqual(conditional_effects(rows[:-1]), [])

    def test_malformed_or_smoke_matrix_is_rejected(self):
        with self.assertRaises(ValueError): validate_profile({'Iterations': 10})

    def test_resume_after_teacher_report_preserves_committed_bytes_and_skips_all_arms(self):
        from topic16_upgrade.teacher import execute
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); study = 'teacher-room-v1'
            directory = root / 'artifacts/jobs/teacher' / study; directory.mkdir(parents=True)
            report = root / 'reports' / study / 'report.json'
            write_json(report, {'status': 'complete', 'completed_arms': ['A', 'B', 'C']})
            report_hash = sha256(report)
            pin = root / 'pin.json'; write_json(pin, {'fixture': True})
            doc = {'source_pin': reference(root, pin), 'spec': {'Arms': ['A', 'B', 'C'],
                'ContinueFinalCampaign': True, 'FinalStudy': 'final-quality-v1'}}
            write_json(directory / 'declaration.json', doc)
            stages = {key: [reference(root, pin)] for key in ['preflight', 'nerfacto-historical-common',
                'splatfacto-historical-common', *[a + '-' + k for a in 'ABC' for k in ('train', 'eval', 'common')]]}
            stages['teacher-report'] = [reference(root, report)]
            state = {'study': study, 'status': 'paused', 'phase': 'upgrade-final', 'stages': stages,
                'arms': {a: {'status': 'complete', 'output': a} for a in 'ABC'}}
            write_json(directory / 'state.json', state)
            with patch('topic16_upgrade.teacher.prepare'), \
                 patch('topic16_upgrade.teacher.verify_pin', return_value=({}, root)), \
                 patch('topic16_upgrade.teacher.check_stop'), \
                 patch('topic16_upgrade.runtime.gpu_lock', return_value=nullcontext()), \
                 patch('topic16_upgrade.teacher_report.publish', side_effect=AssertionError('Committed report rewritten')) as publish_mock, \
                 patch('topic16_upgrade.runtime.run_command', side_effect=AssertionError('Completed arm rerun')), \
                 patch('topic16_upgrade.final_campaign.execute', return_value={'status': 'succeeded'}) as continuation:
                result = execute(root, {'Teacher': {}, 'DownscaleFactor': 2}, study, resume=True)
            self.assertEqual(result['status'], 'succeeded')
            self.assertEqual(sha256(report), report_hash)
            publish_mock.assert_not_called()
            self.assertTrue(continuation.call_args.kwargs['resume'])
            self.assertEqual(continuation.call_args.args[2], 'final-quality-v1')
            self.assertEqual(continuation.call_args.args[1]['DownscaleFactor'], 1)

    def test_complete_supplement_keeps_negative_result_native_metrics_and_all39_views(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp); root = baseline / 'upgrade'; root.mkdir()
            image = baseline / 'gt.png'; Image.new('RGB', (8, 6), (40, 80, 120)).save(image)
            original = {'frames': [{'gt': 'gt.png', 'pred': 'gt.png'} for _ in range(39)]}
            write_json(baseline / 'evaluation.json', original)
            metrics = {'psnr': 22.9, 'ssim': .7, 'lpips': .3}
            write_json(baseline / 'metrics.json', {'results': metrics})
            write_json(baseline / 'manifest.json', {'execution_metrics': {'wall_time_seconds': 3400., 'peak_vram_mb': 7800.}})
            item = {k: reference(baseline, baseline / (k + '.json')) for k in ('evaluation', 'metrics', 'manifest')}
            item['render_directory'] = '.'
            doc = {'study': 'teacher-room-v1', 'baseline': str(baseline), 'baselines': {
                'nerfacto': item, 'splatfacto': item}, 'split': {}, 'source_pin': {},
                'runtime_sha256': 'test', 'baseline_runtime_matches_current': False}
            def common(values):
                return {'metrics': values, 'frames': [{'index': i, **values} for i in range(39)]}
            output = root / 'reports' / doc['study']
            for method in ('nerfacto', 'splatfacto'):
                write_json(output / 'historical' / (method + '-common.json'), common(metrics))
            state = {'arms': {}}
            for arm in ('A', 'B', 'C'):
                folder = root / arm; folder.mkdir()
                native = {'psnr': 25., 'ssim': .8, 'lpips': .25}
                write_json(folder / 'training.json', {'step': 29999, 'fresh_initialization': True,
                    'training_seconds': 3300., 'camera_corrections': {'enabled': arm == 'B'}})
                ref = reference(baseline, image)
                # Image refs for current outputs must stay inside the upgrade root.
                current = folder / 'gt.png'; current.write_bytes(image.read_bytes()); ref = reference(root, current)
                write_json(folder / 'evaluation.json', {'all39_gt_pixels_equal_historical': True,
                    'native_metrics': native, 'frames': [{'gt': ref, 'pred': ref} for _ in range(39)]})
                write_json(folder / 'common.json', common(dict(native, psnr=24.99)))
                for name in ('initialization.json', 'recipe-diff.json'):
                    write_json(folder / name, {'status': 'passed'})
                write_json(folder / 'train-execution.json', {'sampled_peak_device_vram_mb': 7700.})
                state['arms'][arm] = {'status': 'complete', 'output': arm, 'attempts': []}
            paths = publish(root, doc, state, final=True)
            report = read_json(output / 'report.json')
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['diagnostic']['c_native_psnr_db'], 25.)
            self.assertFalse(report['diagnostic']['expectation_is_acceptance_gate'])
            self.assertIn('not fully resolved', (output / 'report.md').read_text())
            self.assertEqual(len(report['rows']), 5)
            self.assertEqual(len((output / 'per-view.csv').read_text().splitlines()), 196)
            self.assertEqual(len(list((output / 'errors').glob('*.png'))), 195)
            self.assertIn(output / 'gallery.html', paths)
