"""Negative and integration fixtures: no dataset downloads, no GPU allocation."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from topic16.contracts import (digest_json, inside, load_run, read_json, relative, run_paths,
                               sha256, validate_metrics, validate_pair, validate_split, write_json)
from topic16.analysis import analyze, collect_pairs, core_gate, paired_throughput, result_rows
from topic16.experiments import benchmark


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="topic16 test ")
        self.root = Path(self.temporary.name).resolve()
        self.settings = {"TrainIterations": 30000, "RandomSeed": 42, "DownscaleFactor": 2, "EvalInterval": 8}
        self.configs = {method: self.fixture(method) for method in ("nerfacto", "splatfacto")}
        self.pair = {"status": "succeeded", "scene": "bonsai",
                     "runs": {method: relative(self.root, path) for method, path in self.configs.items()}}

    def tearDown(self):
        self.temporary.cleanup()

    def fixture(self, method):
        key = f"bonsai/{method}/20260930T100000000Z"
        paths = run_paths(self.root, key)
        for directory in paths.values():
            directory.mkdir(parents=True)
        config = paths["runs"] / "config.yml"
        config.write_text("fixture\n")
        checkpoint = paths["runs"] / "nerfstudio_models/step-000029999.ckpt"
        checkpoint.parent.mkdir()
        checkpoint.write_bytes(b"fixture-checkpoint")
        camera = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]
        split = {"train": [{"path": "data/train.png", "sha256": "a" * 64, "camera_to_world": camera}],
                 "eval": [{"path": "data/eval.png", "sha256": "b" * 64, "camera_to_world": camera}]}
        manifest = {"schema_version": "1.0", "run_key": key, "scene": "bonsai", "method": method,
                    "status": "succeeded", "protocol": {"iterations": 30000, "seed": 42, "downscale_factor": 2, "eval_interval": 8},
                    "provenance": {"git_commit_sha": "a" * 40, "dataset_split_hash": digest_json(split)},
                    "hardware": {"gpu_name": "NVIDIA RTX A4500 Laptop GPU", "driver_version": "597.06"},
                    "execution_metrics": {"wall_time_seconds": 10.0, "peak_vram_mb": 1000}}
        provenance = {"config_sha256": sha256(config), "checkpoint_sha256": sha256(checkpoint),
                      "checkpoint_path": relative(self.root, checkpoint), "protocol_id": "primary",
                      "settings_hash": digest_json(self.settings), "runtime_sha256": "c" * 64,
                      "git_commit": "a" * 40, "git_diff_sha256": "d" * 64,
                      "gpu": {"gpu_name": "NVIDIA RTX A4500 Laptop GPU", "total_vram_mb": 16384}}
        metrics = {"checkpoint": relative(self.root, checkpoint), "results": {"psnr": 20.0, "ssim": 0.8, "lpips": 0.2}}
        write_json(paths["metrics"] / "metrics.json", metrics)
        for name in ("gt.png", "pred.png"):
            (paths["renders"] / name).write_bytes(b"pixels")
        evaluation = {"status": "succeeded", "run_key": key, "split_hash": digest_json(split),
                      "config_sha256": provenance["config_sha256"], "checkpoint_sha256": provenance["checkpoint_sha256"],
                      "metrics_sha256": sha256(paths["metrics"] / "metrics.json"), "checkpoint_bytes": checkpoint.stat().st_size,
                      "frames": [{"source": "data/eval.png", "gt": "gt.png", "pred": "pred.png",
                                  "gt_sha256": sha256(paths["renders"] / "gt.png"), "pred_sha256": sha256(paths["renders"] / "pred.png")}]}
        for name, record in (("manifest.json", manifest), ("provenance.json", provenance), ("split.json", split)):
            write_json(paths["logs"] / name, record)
        write_json(paths["metrics"] / "evaluation.json", evaluation)
        write_json(paths['logs'] / 'settings.json', self.settings)
        for name in ("command.txt", "train.log", "timing.env", "gpu.csv", "run.env"):
            (paths["logs"] / name).write_text("fixture\n")
        return config

    def change(self, path, callback):
        value = read_json(path)
        callback(value)
        write_json(path, value)

    def test_good_pair(self):
        self.assertEqual(len(validate_pair(self.root, self.pair, primary_only=True)), 2)

    def test_resume_ancestry_cycle_rejected(self):
        run = load_run(self.root, self.configs['nerfacto'])
        self.change(run['paths']['logs'] / 'provenance.json',
                    lambda record: record.update(resumed_from={'run_key': run['manifest']['run_key']}))
        with self.assertRaisesRegex(ValueError, 'ancestry contains a cycle'):
            load_run(self.root, self.configs['nerfacto'])

    def test_incomplete_training_safety_evidence_rejected(self):
        run = load_run(self.root, self.configs['nerfacto'])
        safety = self.root / 'artifacts/logs/safety/test.json'
        write_json(safety, {'status': 'monitoring', 'policy': {}})
        self.change(run['paths']['logs'] / 'provenance.json',
                    lambda record: record.update(gpu_safety_path=relative(self.root, safety)))
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs['nerfacto'])
        write_json(safety, {'status': 'succeeded', 'policy': {}})
        load_run(self.root, self.configs['nerfacto'])

    def test_unsafe_evaluation_cannot_enter_results(self):
        run = load_run(self.root, self.configs['nerfacto'])
        safety = self.root / 'artifacts/logs/safety/eval-test.json'
        write_json(safety, {'status': 'unsafe-stopped', 'failure_reason': 'overheat'})
        self.change(run['paths']['metrics'] / 'evaluation.json',
                    lambda record: record.update(gpu_safety_path=relative(self.root, safety)))
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs['nerfacto'], require_eval=True)

    def test_half_pair(self):
        self.pair["runs"].pop("splatfacto")
        with self.assertRaises(ValueError):
            validate_pair(self.root, self.pair)

    def test_reject_config_outside_runs(self):
        with self.assertRaises(ValueError):
            load_run(self.root, self.root / "config.yml")

    def test_reject_path_traversal(self):
        with self.assertRaises(ValueError):
            inside(self.root, "../escape")

    def test_invalid_run_key(self):
        with self.assertRaises(ValueError):
            run_paths(self.root, "bonsai/nerfacto/latest")

    def test_split_leakage(self):
        run = load_run(self.root, self.configs["nerfacto"])
        split = copy.deepcopy(run["split"])
        split["eval"][0]["sha256"] = split["train"][0]["sha256"]
        with self.assertRaises(ValueError):
            validate_split(split)

    def test_split_pose_nonfinite(self):
        split = load_run(self.root, self.configs["nerfacto"])["split"]
        split["eval"][0]["camera_to_world"][0][0] = float("nan")
        with self.assertRaises(ValueError):
            validate_split(split)

    def test_nonfinite_and_string_metrics(self):
        for value in (float("nan"), float("inf"), "20", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_metrics({"results": {"psnr": value, "ssim": 0.8, "lpips": 0.2}})

    def test_missing_required_metric(self):
        with self.assertRaises(KeyError):
            validate_metrics({"results": {"psnr": 20, "ssim": 0.8}})

    def test_metric_range(self):
        with self.assertRaises(ValueError):
            validate_metrics({"results": {"psnr": 20, "ssim": 1.1, "lpips": 0.2}})
        validate_metrics({'results': {'psnr': 0, 'ssim': -0.1, 'lpips': 1.2}})

    def test_failed_run(self):
        run = load_run(self.root, self.configs["nerfacto"])
        self.change(run["paths"]["logs"] / "manifest.json", lambda m: m.update(status="failed"))
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"])

    def test_modified_config(self):
        self.configs["nerfacto"].write_text("modified")
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"])

    def test_missing_checkpoint(self):
        run = load_run(self.root, self.configs["nerfacto"])
        run["checkpoint"].unlink()
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"])

    def test_modified_checkpoint(self):
        run = load_run(self.root, self.configs["nerfacto"])
        run["checkpoint"].write_bytes(b"modified")
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"])

    def test_modified_metrics(self):
        run = load_run(self.root, self.configs["nerfacto"])
        self.change(run["paths"]["metrics"] / "metrics.json", lambda m: m["results"].update(psnr=99))
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"], require_eval=True)

    def test_missing_render(self):
        run = load_run(self.root, self.configs["nerfacto"])
        (run["paths"]["renders"] / "pred.png").unlink()
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"], require_eval=True)

    def test_wrong_camera_identity(self):
        run = load_run(self.root, self.configs["nerfacto"])
        self.change(run["paths"]["metrics"] / "evaluation.json", lambda m: m["frames"][0].update(source="data/train.png"))
        with self.assertRaises(ValueError):
            load_run(self.root, self.configs["nerfacto"], require_eval=True)

    def test_mixed_protocol(self):
        run = load_run(self.root, self.configs["splatfacto"])
        self.change(run["paths"]["logs"] / "manifest.json", lambda m: m["protocol"].update(seed=43))
        with self.assertRaises(ValueError):
            validate_pair(self.root, self.pair)

    def test_mixed_runtime(self):
        run = load_run(self.root, self.configs["splatfacto"])
        self.change(run["paths"]["logs"] / "provenance.json", lambda m: m.update(runtime_sha256="f" * 64))
        with self.assertRaises(ValueError):
            validate_pair(self.root, self.pair)

    def test_diagnostic_excluded(self):
        for config in self.configs.values():
            run = load_run(self.root, config)
            self.change(run["paths"]["logs"] / "provenance.json", lambda m: m.update(protocol_id="diagnostic"))
        with self.assertRaises(ValueError):
            validate_pair(self.root, self.pair, primary_only=True)

    def test_core_not_pass_from_one_fixture_pair(self):
        runs = validate_pair(self.root, self.pair)
        gate = core_gate(self.root, self.settings, {"bonsai": runs}, [], None)
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertFalse(gate["checks"]["clean_machine_replay"])
        self.assertFalse(gate['checks']['paired_render'])
        self.assertFalse(gate['checks']['exports'])

    def test_demo_trajectory_does_not_change_primary_throughput(self):
        runs = validate_pair(self.root, self.pair)
        held_out = digest_json(runs[0]['split']['eval'])
        for run in runs:
            for camera_hash, seconds in ((held_out, 1.0), ('e' * 64, 0.5)):
                directory = run['paths']['videos'] / camera_hash[:16]
                directory.mkdir()
                frame = directory / 'frame_0000.png'
                frame.write_bytes(b'pixels')
                write_json(directory / 'render.json', {'checkpoint_sha256': run['provenance']['checkpoint_sha256'],
                    'camera_sha256': camera_hash, 'frame_count': 1, 'widths': [10], 'heights': [20],
                    'warmup_frames': 3, 'durations_seconds': [seconds], 'fps': 1 / seconds, 'includes_image_io': False})
        self.assertEqual(paired_throughput(runs), {'nerfacto': 1.0, 'splatfacto': 1.0})

    def test_review_of_another_selection_is_rejected(self):
        review = self.root / 'review.json'
        write_json(review, {'research_review': {'approved': True, 'reviewer': 'fixture', 'notes': 'fixture', 'evidence': []},
                            'settings_hash': digest_json(self.settings), 'run_keys': ['different/run']})
        with self.assertRaisesRegex(ValueError, 'current selected runs'):
            core_gate(self.root, self.settings, {'bonsai': validate_pair(self.root, self.pair)}, [], review)

    def test_repeated_analysis_keeps_gate_checksum(self):
        matrix = self.root / 'matrix.json'
        write_json(matrix, {'status': 'succeeded', 'protocol': {'id': 'primary'}, 'scenes': ['bonsai'], 'pairs': {'bonsai': self.pair}})
        output = self.root / 'reports/results'
        with patch('topic16.analysis.figures'):
            analyze(self.root, self.settings, [matrix], output)
            original = sha256(output / 'g-core.json')
            with patch('topic16.analysis.utc_now', return_value='different-check-time'):
                analyze(self.root, self.settings, [matrix], output)
        self.assertEqual(sha256(output / 'g-core.json'), original)

    def test_core_rejects_old_safety_registry(self):
        runs = validate_pair(self.root, self.pair)
        settings = dict(self.settings, GpuClockMinMHz=300)
        with self.assertRaises(ValueError):
            core_gate(self.root, settings, {'bonsai': runs}, [], None)

    def test_model_rejects_blocked_gate(self):
        from topic16.demo import verified_gate
        path = self.root / "blocked.json"
        write_json(path, {"status": "BLOCKED"})
        with self.assertRaises(ValueError):
            verified_gate(self.root, self.settings, path)

    def test_release_health_rejects_another_selected_model(self):
        from topic16.demo import validate_demo_health
        model = self.root / 'model.json'
        write_json(model, {'fixture': 'selected model'})
        with self.assertRaises(ValueError):
            validate_demo_health(self.root, {}, model, 'a' * 64)
        write_json(model.with_suffix('.health.json'), {'status': 'succeeded', 'model_sha256': sha256(model),
            'checkpoint_sha256': 'a' * 64, 'checks': {'cuda_inference': True, 'fixed_camera': True, 'png_determinism': True}})
        validate_demo_health(self.root, {}, model, 'a' * 64)
        write_json(model, {'fixture': 'a different selection'})
        with self.assertRaises(ValueError):
            validate_demo_health(self.root, {}, model, 'a' * 64)

    def test_atomic_json_preserves_prior_on_nonfinite(self):
        path = self.root / "atomic.json"
        write_json(path, {"value": 1})
        with self.assertRaises(ValueError):
            write_json(path, {"value": float("nan")})
        self.assertEqual(read_json(path), {"value": 1})
        self.assertEqual(list(self.root.glob(".atomic*")), [])

    def test_bom_input_and_unicode_output(self):
        path = self.root / "du lieu.json"
        path.write_text('\ufeff{"value": 1}', encoding="utf-8")
        self.assertEqual(read_json(path), {"value": 1})
        write_json(path, {"value": "ảnh"})
        self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_benchmark_exact_resume(self):
        path = self.root / "artifacts/logs/matrices/main.json"
        calls = []
        def fake_train(root, settings, method, scene, *args):
            calls.append(("train", method))
            return self.configs[method]
        def fake_eval(root, settings, config):
            calls.append(("eval", config.parent.parent.name))
        with patch("topic16.runtime.train", fake_train), patch("topic16.runtime.evaluate", fake_eval):
            record = benchmark(self.root, self.settings, ["bonsai"], path)
            self.assertEqual(record["status"], "succeeded")
            self.assertEqual(calls, [("train", "nerfacto"), ("eval", "nerfacto"), ("train", "splatfacto"), ("eval", "splatfacto")])
            calls.clear()
            benchmark(self.root, self.settings, ["bonsai"], path, resume=True)
            self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            benchmark(self.root, self.settings, ["bonsai"], path)
        with self.assertRaises(ValueError):
            benchmark(self.root, self.settings, ["room"], path, resume=True)

    def test_failed_eval_resumes_same_training_config(self):
        path = self.root / "artifacts/logs/matrices/retry.json"
        with patch("topic16.runtime.train", return_value=self.configs["nerfacto"]), patch("topic16.runtime.evaluate", side_effect=RuntimeError("forced")):
            with self.assertRaises(RuntimeError):
                benchmark(self.root, self.settings, ["bonsai"], path)
        record = read_json(path)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["pairs"]["bonsai"]["runs"]["nerfacto"], relative(self.root, self.configs["nerfacto"]))
        with patch("topic16.runtime.train", return_value=self.configs["splatfacto"]) as trainer, patch("topic16.runtime.evaluate"):
            benchmark(self.root, self.settings, ["bonsai"], path, resume=True)
            self.assertEqual(trainer.call_count, 1)
            self.assertEqual(trainer.call_args.args[2], "splatfacto")

    def test_aggregate_selection_is_deterministic(self):
        path = self.root / "matrix.json"
        write_json(path, {"status": "succeeded", "protocol": {"id": "primary"}, "scenes": ["bonsai"], "pairs": {"bonsai": self.pair}})
        rows = result_rows(collect_pairs(self.root, [path]))
        self.assertEqual([row["method"] for row in rows], ["nerfacto", "splatfacto"])
        self.assertTrue(all(row["offline_fps"] == "" for row in rows))
        with self.assertRaises(ValueError):
            collect_pairs(self.root, [path, path])


if __name__ == "__main__":
    unittest.main()
