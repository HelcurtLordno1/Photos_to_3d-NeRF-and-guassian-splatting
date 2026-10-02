"""Runtime identity must survive setuptools imports and still reject drift."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from topic16.contracts import digest_json
from topic16.runtime import runtime_snapshot, validate_runtime_snapshot


class Distribution:
    def __init__(self, name, version, directory):
        self.metadata = {'Name': name}
        self.version = version
        self.directory = directory

    def locate_file(self, path):
        return self.directory / path


class RuntimeSnapshotTests(unittest.TestCase):
    def setUp(self):
        site = Path('/test-site').resolve()
        self.vendor = site / 'setuptools/_vendor'
        self.installed = [Distribution('setuptools', '81.0.0', site),
                          Distribution('torch', '2.1.2+cu118', site),
                          Distribution('packaging', '26.3', site)]
        self.bundled = [Distribution('packaging', '26.0', self.vendor),
                        Distribution('jaraco.text', '4.0.0', self.vendor)]
        self.imported = False
        self.lookup = patch('importlib.metadata.distribution', return_value=self.installed[0])
        self.inventory = patch('importlib.metadata.distributions', side_effect=self.distributions)
        self.lookup.start()
        self.inventory.start()
        self.addCleanup(self.lookup.stop)
        self.addCleanup(self.inventory.stop)

    def distributions(self, path=None):
        if path is not None:
            self.assertEqual(path, [str(self.vendor)])
            return self.bundled
        return self.installed + (self.bundled if self.imported else [])

    def legacy_snapshot(self):
        return '\n'.join(sorted(f"{d.metadata['Name']}=={d.version}"
                                for d in self.installed + self.bundled)) + '\n'

    def test_snapshot_unchanged_when_vendor_path_becomes_visible(self):
        before = runtime_snapshot()
        self.imported = True
        self.assertEqual(runtime_snapshot(), before)
        self.assertIn('packaging==26.3', before)
        self.assertNotIn('packaging==26.0', before)

    def test_both_saved_import_orders_load_in_either_current_import_order(self):
        hashes = (digest_json(runtime_snapshot()), digest_json(self.legacy_snapshot()))
        for self.imported in (False, True):
            for expected in hashes:
                validate_runtime_snapshot(expected)

    def test_real_installed_version_change_still_rejected(self):
        hashes = (digest_json(runtime_snapshot()), digest_json(self.legacy_snapshot()))
        self.installed[1].version = '2.2.0'
        for expected in hashes:
            with self.assertRaisesRegex(ValueError, 'Installed dependencies differ'):
                validate_runtime_snapshot(expected)

    def test_missing_installed_package_not_replaced_by_bundled_copy(self):
        expected = digest_json(self.legacy_snapshot())
        self.installed.pop()
        with self.assertRaises(ValueError):
            validate_runtime_snapshot(expected)

    def test_changed_vendor_version_rejects_legacy_snapshot(self):
        expected = digest_json(self.legacy_snapshot())
        self.bundled[0].version = '27.0'
        with self.assertRaises(ValueError):
            validate_runtime_snapshot(expected)

    def test_arbitrary_additional_metadata_not_accepted_as_legacy(self):
        expected = digest_json(self.legacy_snapshot() + 'unrecorded==1.0\n')
        with self.assertRaises(ValueError):
            validate_runtime_snapshot(expected)


if __name__ == '__main__':
    unittest.main()
