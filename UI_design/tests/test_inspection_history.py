import tempfile
import unittest
from pathlib import Path
from topic16.contracts import write_json, sha256
from UI_design.backend.inspection_history import read_inspection_history


class InspectionHistoryContracts(unittest.TestCase):
    def test_only_committed_history_is_shown_and_failures_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'reports/tea-quality-v5/inspection.json'
            report = {'status': 'gate-not-met', 'results': [{'method': 'absgs', 'browser': {
                'results': [{'psnr': 30.0}, {'psnr': 34.0}], 'benchmark': {'p95_frame_interval_ms': 40.0}}}]}
            write_json(path, report)
            self.assertEqual(read_inspection_history(root, {}, lambda *a: '/verified'), [])
            state = {'stages': {'inspection-report': [{'path': path.relative_to(root).as_posix(), 'sha256': sha256(path)}]}}
            rows = read_inspection_history(root, state, lambda *a: '/verified')
            self.assertEqual(rows[0]['status'], 'gate-not-met')
            self.assertEqual(rows[0]['mean_parity_db'], 32.)
            self.assertEqual(rows[0]['p95_frame_interval_ms'], 40.)
            write_json(path, {})
            with self.assertRaisesRegex(ValueError, 'checksum'):
                read_inspection_history(root, state, lambda *a: '/verified')
