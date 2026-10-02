import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from topic16.contracts import digest_json, read_json
from topic16.settings import assert_experiment_compatible, experiment_settings_hash


class SettingsCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.baseline = read_json(
            ROOT / "reports/topic16-full/review/settings.snapshot.json"
        )
        self.current = dict(self.baseline, Ui={"SchemaVersion": 1, "Port": 7016})

    def test_legacy_identity_preserved(self):
        self.assertEqual(
            experiment_settings_hash(self.current), digest_json(self.baseline)
        )
        assert_experiment_compatible(
            self.current, self.baseline, digest_json(self.baseline)
        )

    def test_ui_change_allowed(self):
        self.current["Ui"]["Port"] = 7017
        assert_experiment_compatible(self.current, self.baseline)

    def test_every_experiment_field_drift_rejected(self):
        for key in self.baseline:
            with self.subTest(key=key):
                changed = copy.deepcopy(self.current)
                value = changed[key]
                changed[key] = (
                    value + 1 if isinstance(value, (int, float)) else "changed"
                )
                with self.assertRaises(ValueError):
                    assert_experiment_compatible(changed, self.baseline)

    def test_missing_added_field_and_ui_injection_rejected(self):
        for change in ("missing", "added", "injected"):
            changed = copy.deepcopy(self.current)
            if change == "missing":
                changed.pop("RandomSeed")
            elif change == "added":
                changed["UnexpectedExperimentField"] = 1
            else:
                changed["Ui"]["TrainIterations"] = 1
            with self.assertRaises(ValueError):
                assert_experiment_compatible(changed, self.baseline)

    def test_modified_recorded_hash_rejected(self):
        with self.assertRaises(ValueError):
            assert_experiment_compatible(self.current, self.baseline, "0" * 64)


if __name__ == "__main__":
    unittest.main()
