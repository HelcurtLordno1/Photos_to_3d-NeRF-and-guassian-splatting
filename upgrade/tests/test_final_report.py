"""Synthetic temporary data verifies reporting; never experiment evidence."""
from pathlib import Path
import tempfile
import unittest
from topic16_upgrade.final_report import scene_tables,campaign_tables


class ExportedReportContract(unittest.TestCase):
    def test_negative_views_and_actual_shapes_survive_csv_markdown_and_svg(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'upgrade';out=root/'reports/fixture';out.mkdir(parents=True)
            (root/'model.ply').write_bytes(b'unit-test-placeholder')
            old={'training_seconds':120.,'per_view':[{'psnr':30.,'ssim':.9,'lpips':.1}]}
            new={'training_seconds':90.,'optimizer_updates':21099,'gaussians':300000,
                'model':{'owner':'upgrade','path':'model.ply'},'peak_cuda_allocated_bytes':2**20,
                'per_view':[{'psnr':29.9,'ssim':.89,'lpips':.12}]}
            report={'scene':'fixture','train_count':105,'eval_count':1,'gaussian_budget':300000,
                'cameras':[{'width':719,'height':1279}],'baseline':old,'upgrade':new,
                'delta':{'psnr':-.1,'ssim':-.01,'lpips':.02},
                'browser':{'p95_frame_interval_ms':40.,'mean_parity_db':34.,'minimum_parity_db':29.}}
            (out/'report.md').write_text('Synthetic fixture\n')
            scene_tables(out,report)
            self.assertIn('-0.100000',(out/'report.md').read_text())
            paths=campaign_tables(out,{'scope':'Synthetic fixture only'},[report],{'chosen_budget':300000,'checks':{'roi':False}}, {'statistics':{}})
            self.assertTrue(all(p.is_file() and p.stat().st_size>0 for p in paths))
            self.assertIn('719x1279',(out/'report.md').read_text())
            self.assertIn('-0.1',(out/'summary.csv').read_text())
