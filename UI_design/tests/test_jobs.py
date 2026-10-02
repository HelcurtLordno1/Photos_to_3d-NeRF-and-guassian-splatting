import copy
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from UI_design.backend.jobs import Jobs, validate_camera

CAMERA = {
    "width": 320,
    "height": 480,
    "fx": 100,
    "fy": 100,
    "cx": 160,
    "cy": 240,
    "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]],
}


class JobsTest(unittest.TestCase):
    def test_camera_nonfinite_shear_reflection_and_budget(self):
        self.assertEqual(validate_camera(CAMERA, 200000), CAMERA)
        for key, value in [
            ("fx", float("nan")),
            ("fy", 0),
            ("width", True),
            ("height", 5000),
            ("cx", -1),
            ("camera_to_world", [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0]]),
        ]:
            c = copy.deepcopy(CAMERA)
            c[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_camera(c, 200000)
        with self.assertRaises(ValueError):
            validate_camera(CAMERA, 100)

    def test_one_lease_latest_pending_and_stale_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            # Disable execution; this is a deterministic queue contract, no mock GPU.
            jobs = Jobs.__new__(Jobs)
            jobs.root = Path(directory)
            jobs.settings = {
                "Ui": {
                    "LeaseSeconds": 45,
                    "MaxPixels": 200000,
                    "CacheBytes": 2147483648,
                }
            }
            jobs.catalog = {
                "revision": "r1",
                "scenes": [
                    {
                        "id": "tea",
                        "methods": {"nerfacto": {"config": "exact/config.yml"}},
                    }
                ],
            }
            jobs.lock = threading.RLock()
            jobs.owner = None
            jobs.expires = 0
            jobs.active = "already-running"
            jobs.pending = None
            jobs.records = {}
            token = jobs.lease()
            with self.assertRaises(RuntimeError):
                jobs.lease()
            request = {
                "scene": "tea",
                "methods": ["nerfacto"],
                "revision": "r1",
                "camera": CAMERA,
            }
            with self.assertRaises(ValueError):
                jobs.submit(request | {"revision": "stale"}, token)
            for methods in ([{}], [[]], [1], ["nerfacto", "nerfacto"]):
                with self.subTest(methods=methods), self.assertRaises(ValueError):
                    jobs.submit(request | {"methods": methods}, token)
            with self.assertRaises(PermissionError):
                jobs.submit(request, "wrong-owner")
            first = jobs.submit(request, token)
            second = jobs.submit(request, token)
            self.assertEqual(jobs.pending, second["id"])
            self.assertEqual(jobs.status(first["id"])["status"], "cancelled")
            self.assertEqual(jobs.status(second["id"])["camera"], CAMERA)

    def test_cache_only_ui_completed_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "artifacts/exports/original.ply"
            original.parent.mkdir(parents=True)
            original.write_bytes(b"original")
            jobs = Jobs.__new__(Jobs)
            jobs.root = root
            jobs.settings = {"Ui": {"CacheBytes": 12}}
            jobs.lock = threading.RLock()
            jobs.records = {}
            jobs.active = "active"
            jobs.pending = "pending"
            for name in ("old", "active", "pending", "new"):
                folder = root / "artifacts/ui/jobs" / name
                folder.mkdir(parents=True)
                (folder / "result").write_bytes(b"1234567890")
                time.sleep(0.01)
            jobs.evict()
            self.assertTrue(original.exists())
            self.assertTrue((root / "artifacts/ui/jobs/active").exists())
            self.assertTrue((root / "artifacts/ui/jobs/pending").exists())
            self.assertFalse((root / "artifacts/ui/jobs/old").exists())


if __name__ == "__main__":
    unittest.main()
