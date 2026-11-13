import tempfile
import unittest
from pathlib import Path
from topic16.contracts import write_json, sha256
from UI_design.backend.final_provider import read_teacher


class TeacherDiagnosticPublication(unittest.TestCase):
    def fixture(self, root, incomplete=False):
        upgrade = root / 'upgrade'; output = upgrade / 'reports/teacher-room-v1'
        rows = []
        for key, camera, appearance in [('historical-nerfacto', 'SO3xR3', 'average'),
                ('A', 'off', 'average'), ('B', 'SO3xR3', 'off'), ('C', 'off', 'off')]:
            rows.append({'id': key, 'camera_optimizer': camera, 'appearance': appearance,
                'metrics': {'psnr': 25., 'ssim': .8, 'lpips': .2}, 'native_metrics': {'psnr': 25.1},
                'per_view': [{}] * 39, 'scope': 'fresh' if key != 'historical-nerfacto' else 'historical'})
        write_json(output / 'report.json', {'schema_version': 'teacher-room-supplement-1',
            'status': 'complete', 'completed_arms': ['A', 'B'] if incomplete else ['A', 'B', 'C'], 'rows': rows})
        (output / 'results.csv').write_text('recorded CSV', encoding='utf-8')
        refs = [{'path': p.relative_to(upgrade).as_posix(), 'sha256': sha256(p)}
            for p in (output / 'report.json', output / 'results.csv')]
        write_json(upgrade / 'artifacts/jobs/teacher/teacher-room-v1/state.json', {'stages': {'teacher-report': refs}})
        return output

    def test_missing_diagnostic_does_not_block_gaussian_results(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(read_teacher(Path(directory), lambda *a: '/asset')['status'], 'unavailable')

    def test_only_committed_complete_matrix_is_published_with_distinct_native_and_rgb8_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            result = read_teacher(root, lambda *a: '/verified-asset')
            self.assertEqual(result['status'], 'ready')
            self.assertEqual(len(result['rows']), 4)
            self.assertEqual(result['rows'][-1]['metrics']['psnr'], 25.)
            self.assertEqual(result['rows'][-1]['native_psnr'], 25.1)
            self.assertEqual(result['rows'][-1]['appearance'], 'off')

    def test_changed_committed_report_or_incomplete_matrix_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = self.fixture(root)
            (output / 'report.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'checksum'): read_teacher(root, lambda *a: '/asset')
            self.fixture(root, incomplete=True)
            with self.assertRaisesRegex(ValueError, 'incomplete'): read_teacher(root, lambda *a: '/asset')
