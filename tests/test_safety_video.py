"""Safety thresholds, fail-closed startup, watchdog stop, and timestamp sampling."""
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from topic16.contracts import digest_json, read_json, relative, sha256, validate_capture_review, validate_export, validate_render, write_json
from topic16.safety import GpuGuard, SafetyStop, apply_clock_limit, check_sample, query_sample, wait_until_cool
from topic16.video import select_frames
from topic16.data import choose_capture_model, cpu_colmap_arguments


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.settings = {'GpuClockMinMHz': 300, 'GpuClockMaxMHz': 800, 'GpuClockToleranceMHz': 15,
                         'GpuStartTemperatureC': 65, 'GpuStopTemperatureC': 78, 'GpuStopPowerWatts': 80,
                         'GpuCooldownMaximumSeconds': 300, 'GpuCooldownPollSeconds': 5,
                         'GpuMaxMemoryPercent': 95, 'GpuSafetyPollSeconds': 0.01,
                         'GpuSafetyQueryTimeoutSeconds': 1, 'GpuEmergencyGraceSeconds': 5}
        self.sample = {'temperature.gpu': 49.0, 'clocks.gr': 300.0, 'memory.used': 1000.0,
                       'memory.total': 16384.0, 'power.draw': 18.0, 'power.limit': 85.0}

    def tearDown(self):
        self.temporary.cleanup()

    def test_safe_idle_and_safe_load(self):
        check_sample(self.sample, self.settings, starting=True)
        sample = dict(self.sample, **{'clocks.gr': 800, 'temperature.gpu': 70, 'power.draw': 60})
        check_sample(sample, self.settings)

    def test_reject_exact_stop_thresholds(self):
        cases = {'temperature.gpu': 78, 'clocks.gr': 816, 'power.draw': 80,
                 'memory.used': 16384 * 0.95, 'memory.total': 0, 'power.limit': 0}
        for key, value in cases.items():
            with self.subTest(key=key), self.assertRaises(SafetyStop):
                check_sample(dict(self.sample, **{key: value}), self.settings)

    def test_start_requires_cool_gpu(self):
        sample = dict(self.sample, **{'temperature.gpu': 65})
        check_sample(sample, self.settings)
        with self.assertRaises(SafetyStop):
            check_sample(sample, self.settings, starting=True)

    def test_warm_start_waits_without_gpu_work(self):
        warm = dict(self.sample, **{'temperature.gpu': 70})
        record = {}
        with patch('topic16.safety.query_sample', side_effect=[warm, self.sample]), patch('topic16.safety.time.sleep') as sleeper:
            self.assertEqual(wait_until_cool(self.root, self.settings, record, self.root / 'cooling.json'), self.sample)
            sleeper.assert_called_once_with(5)
        self.assertEqual(read_json(self.root / 'cooling.json')['status'], 'cooling')

    def test_cooldown_is_bounded(self):
        warm = dict(self.sample, **{'temperature.gpu': 70})
        with patch('topic16.safety.query_sample', return_value=warm), patch('topic16.safety.time.monotonic', side_effect=[0, 301]):
            with self.assertRaises(SafetyStop):
                wait_until_cool(self.root, self.settings, {}, self.root / 'cooling.json')

    def test_fail_closed_on_missing_or_nonfinite_telemetry(self):
        for value in (float('nan'), float('inf'), 'N/A', None, True, -1):
            with self.subTest(value=value), self.assertRaises(SafetyStop):
                check_sample(dict(self.sample, **{'temperature.gpu': value}), self.settings)

    def test_clock_reapply_native_arguments_and_permission_failure(self):
        completed = subprocess.CompletedProcess([], 4, 'permission denied')
        with patch('topic16.safety.subprocess.run', return_value=completed) as runner:
            with self.assertRaisesRegex(SafetyStop, 'Administrator'):
                apply_clock_limit(self.root, self.settings)
            self.assertEqual(runner.call_args.args[0], ['nvidia-smi', '-i', '0', '-lgc', '300,800'])

    def test_parse_nvidia_telemetry(self):
        with patch('topic16.safety.subprocess.check_output', return_value='49, 300, 1000, 16384, 18, 85\n'):
            self.assertEqual(query_sample(self.root, self.settings), self.sample)
        with patch('topic16.safety.subprocess.check_output', return_value='49, N/A, 1000, 16384, 18, 85\n'):
            with self.assertRaises(SafetyStop):
                query_sample(self.root, self.settings)

    def test_block_before_worker_start(self):
        guard = GpuGuard(self.root, self.settings)
        with patch('topic16.safety.apply_clock_limit', side_effect=SafetyStop('permission denied')):
            with self.assertRaises(SafetyStop):
                guard.__enter__()
        self.assertIsNone(guard.worker)
        self.assertEqual(read_json(guard.path)['status'], 'blocked')

    def test_successful_guard_records_policy(self):
        with patch('topic16.safety.apply_clock_limit', return_value='locked'), patch('topic16.safety.query_sample', return_value=self.sample):
            with GpuGuard(self.root, self.settings) as guard:
                guard.check()
        record = read_json(guard.path)
        self.assertEqual(record['status'], 'succeeded')
        self.assertEqual(record['policy'], self.settings)

    def test_cooperative_pause_records_safe_exit(self):
        from topic16.sessions import SessionPaused
        with patch('topic16.safety.apply_clock_limit', return_value='locked'), patch('topic16.safety.query_sample', return_value=self.sample):
            with self.assertRaises(SessionPaused):
                with GpuGuard(self.root, self.settings) as guard:
                    raise SessionPaused()
        record = read_json(guard.path)
        self.assertEqual(record['status'], 'succeeded')
        self.assertEqual(record['job_outcome'], 'paused')
        self.assertEqual(record['policy'], self.settings)

    def test_overheat_kills_owned_child_and_records_reason(self):
        overheated = dict(self.sample, **{'temperature.gpu': 79})
        child = MagicMock()
        child.poll.return_value = None
        with patch('topic16.safety.apply_clock_limit', return_value='locked'), \
             patch('topic16.safety.query_sample', side_effect=[self.sample, overheated]), \
             patch('topic16.safety.stop_process_tree') as killer:
            with self.assertRaises(SafetyStop):
                with GpuGuard(self.root, self.settings) as guard:
                    guard.child = child
                    deadline = time.monotonic() + 2
                    while not guard.error and time.monotonic() < deadline:
                        time.sleep(0.005)
                    self.assertIsNotNone(guard.error)
            killer.assert_called_once_with(child)
        self.assertEqual(read_json(guard.path)['status'], 'unsafe-stopped')

    def test_telemetry_loss_interrupts_inline_job(self):
        with patch('topic16.safety.apply_clock_limit', return_value='locked'), \
             patch('topic16.safety.query_sample', side_effect=[self.sample, subprocess.TimeoutExpired('nvidia-smi', 1)]), \
             patch('topic16.safety._thread.interrupt_main') as interrupt:
            with self.assertRaises(SafetyStop):
                with GpuGuard(self.root, self.settings) as guard:
                    deadline = time.monotonic() + 2
                    while not guard.error and time.monotonic() < deadline:
                        time.sleep(0.005)
            interrupt.assert_called_once()


class VideoTests(unittest.TestCase):
    def test_choose_qualifying_connected_model_instead_of_zero(self):
        models = [{'model': '0', 'train_count': 2, 'eval_count': 0, 'unknown_count': 0},
                  {'model': '1', 'train_count': 105, 'eval_count': 15, 'unknown_count': 0}]
        self.assertEqual(choose_capture_model(models, 105, 15, .90)['model'], '1')

    def test_never_combine_disconnected_models_or_drop_eval(self):
        models = [{'model': '0', 'train_count': 105, 'eval_count': 14, 'unknown_count': 0},
                  {'model': '1', 'train_count': 2, 'eval_count': 1, 'unknown_count': 0}]
        with self.assertRaises(ValueError):
            choose_capture_model(models, 105, 15, .90)

    def test_registration_minimum_and_unknown_names(self):
        for model in ({'model': '1', 'train_count': 90, 'eval_count': 15, 'unknown_count': 0},
                      {'model': '1', 'train_count': 105, 'eval_count': 15, 'unknown_count': 1}):
            with self.subTest(model=model), self.assertRaises(ValueError):
                choose_capture_model([model], 105, 15, .90)
    def test_cpu_colmap_explicitly_disables_gpu_and_bounds_threads(self):
        args = cpu_colmap_arguments(['--', 'feature_extractor', '--SiftExtraction.use_gpu', '0'], 4)
        self.assertEqual(args[-2:], ['--SiftExtraction.num_threads', '4'])
        args = cpu_colmap_arguments(['mapper'], 4)
        self.assertEqual(args[-2:], ['--Mapper.num_threads', '4'])
        self.assertEqual(cpu_colmap_arguments(['--', '-h'], 4), ['-h'])

    def test_cpu_colmap_rejects_gpu_and_unknown_stages(self):
        for args in (['feature_extractor', '--SiftExtraction.use_gpu', '1'], ['exhaustive_matcher'], ['patch_match_stereo']):
            with self.subTest(args=args), self.assertRaises(ValueError):
                cpu_colmap_arguments(args, 4)
    def test_constant_rate_exact_endpoints_and_unique(self):
        selected = select_frames([index / 30 for index in range(1996)], 120)
        self.assertEqual((selected[0], selected[-1], len(set(selected))), (0, 1995, 120))
        self.assertEqual(selected, sorted(selected))

    def test_variable_rate_uses_time(self):
        timestamps = [i * 0.01 for i in range(100)] + [1 + i for i in range(100)]
        selected = select_frames(timestamps, 16)
        self.assertGreater(selected[1], 100)

    def test_reject_bad_timestamps_and_counts(self):
        for times, count in ((list(range(10)), 16), (list(range(20)), 15),
                             ([0.0] * 20, 16), ([float('nan')] * 20, 16), (list(reversed(range(20))), 16)):
            with self.subTest(count=count), self.assertRaises(ValueError):
                select_frames(times, count)

    def test_reject_repeated_nearest_frame(self):
        with self.assertRaises(ValueError):
            select_frames([i / 1000 for i in range(99)] + [1000.0], 16)


class RenderContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        frames = []
        for index in range(2):
            path = self.root / f'frame_{index:04d}.png'
            path.write_bytes(b'fixture-pixels')
            frames.append({'name': path.name, 'sha256': sha256(path)})
        self.record = {'status': 'succeeded', 'checkpoint_sha256': 'a' * 64, 'frame_count': 2,
                       'fps': 2.0, 'durations_seconds': [1.0, 1.0], 'includes_image_io': False,
                       'widths': [10, 10], 'heights': [20, 20], 'frames': frames}
        write_json(self.root / 'render.json', self.record)

    def tearDown(self):
        self.temporary.cleanup()

    def test_good_render(self):
        self.assertEqual(validate_render(self.root, 'a' * 64)['fps'], 2.0)

    def test_reject_forged_fps(self):
        self.record['fps'] = 200.0
        write_json(self.root / 'render.json', self.record)
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64)

    def test_reject_missing_or_modified_frame(self):
        (self.root / 'frame_0000.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64)
        (self.root / 'frame_0000.png').unlink()
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64)

    def test_reject_other_checkpoint_or_incomplete_status(self):
        with self.assertRaises(ValueError):
            validate_render(self.root, 'b' * 64)
        self.record['status'] = 'running'
        write_json(self.root / 'render.json', self.record)
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64)

    def test_reject_io_included_or_bad_dimensions(self):
        self.record['includes_image_io'] = True
        write_json(self.root / 'render.json', self.record)
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64)
        self.record.update(includes_image_io=False, widths=[10])
        write_json(self.root / 'render.json', self.record)
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64)

    def test_gpu_render_requires_successful_current_safety_record(self):
        settings = {'GpuClockMinMHz': 300}
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64, self.root, settings)
        safety = self.root / 'artifacts/logs/safety/render.json'
        write_json(safety, {'status': 'succeeded', 'policy': settings})
        self.record['gpu_safety_path'] = relative(self.root, safety)
        write_json(self.root / 'render.json', self.record)
        validate_render(self.root, 'a' * 64, self.root, settings)
        write_json(safety, {'status': 'unsafe-stopped', 'policy': settings})
        with self.assertRaises(ValueError):
            validate_render(self.root, 'a' * 64, self.root, settings)

    def test_export_rejects_modified_ply(self):
        path = self.root / 'model.ply'
        path.write_bytes(b'ply-fixture')
        record = {'checkpoint_sha256': 'a' * 64, 'files': [{'name': path.name, 'sha256': sha256(path), 'bytes': path.stat().st_size}]}
        write_json(self.root / 'export.json', record)
        validate_export(self.root, 'a' * 64, self.root, {})
        path.write_bytes(b'modified')
        with self.assertRaises(ValueError):
            validate_export(self.root, 'a' * 64, self.root, {})

    def test_capture_review_is_bound_to_pose_images(self):
        split = {'fixture': 'frozen cameras'}
        path = self.root / 'poses.png'
        path.write_bytes(b'visual-evidence')
        review = {'approved': True, 'reviewer': 'fixture', 'notes': 'Actual review',
                  'evidence': [{'path': relative(self.root, path), 'sha256': sha256(path)}]}
        write_json(self.root / 'data/processed/custom/tea/capture.json',
                   {'status': 'ready', 'split_hash': digest_json(split), 'visual_review': review})
        validate_capture_review(self.root, 'custom:tea', split)
        path.write_bytes(b'changed-poses')
        with self.assertRaises(ValueError):
            validate_capture_review(self.root, 'custom:tea', split)


if __name__ == '__main__':
    unittest.main()
