import json
import sys
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from topic16_upgrade.capture import audit, select, FEATURE_SCHEMA
from topic16_upgrade.contracts import sha256, digest_json, inside, write_json
from topic16_upgrade.predictor import train, predict
from topic16_upgrade.evidence import compare, EVALUATOR, PAIR_FIELDS
from topic16_upgrade.study import plan, source_identity, completed


def frame(path, digest, position):
    return {'path': path, 'sha256': digest, 'camera_to_world': [[1.,0.,0.,position],[0.,1.,0.,0.],[0.,0.,1.,0.]],
            'width': 16, 'height': 16, 'fx': 10., 'fy': 10., 'cx': 8., 'cy': 8.}


class CaptureTests(unittest.TestCase):
    def fixture(self, directory, count=12):
        root = Path(directory); baseline = root / 'baseline'; upgrade = root / 'upgrade'
        baseline.mkdir(); upgrade.mkdir(); frames = []
        for i in range(count):
            path = baseline / f'train-{i:02d}.png'
            Image.fromarray(np.random.default_rng(i).integers(0, 255, (16, 16), dtype=np.uint8)).save(path)
            frames.append(frame(path.name, sha256(path), float(i)))
        frozen = {'schema_version': '1.0', 'scene': 'custom:tea_sets_2', 'downscale_factor': 2,
                  'train': frames, 'eval': [frame('heldout-must-never-be-opened.png', 'f'*64, 20.)]}
        split = baseline / 'split.json'; write_json(split, frozen)
        return baseline, upgrade, split

    def test_audit_never_opens_heldout_rgb_and_selection_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, upgrade, split = self.fixture(directory)
            result = audit(upgrade, baseline, 'custom:tea_sets_2', split, 32)
            self.assertEqual(len(result['frames']), 12)
            self.assertEqual(result['overlap']['status'], 'unavailable')
            for recipe in ('uniform', 'coverage-overlap'):
                a = select(result, 6, recipe); b = select(result, 6, recipe)
                self.assertEqual(a, b); self.assertEqual(len(set(a['indices'])), 6)
            self.assertEqual(select(result,12,'uniform')['selection_id'], select(result,12,'coverage-overlap')['selection_id'])
            for count in (0,13):
                with self.assertRaises(ValueError): select(result,count,'uniform')

    def test_changed_training_pixels_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, upgrade, split = self.fixture(directory)
            (baseline/'train-00.png').write_bytes(b'corrupt')
            with self.assertRaises(ValueError): audit(upgrade,baseline,'custom:tea_sets_2',split,32)

    def test_repeat_audit_preserves_published_artifact_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline,upgrade,split=self.fixture(directory)
            first=audit(upgrade,baseline,'custom:tea_sets_2',split,32)
            path=upgrade/'artifacts/features/custom-tea_sets_2/capture-features.json'
            expected=sha256(path); stamp=path.stat().st_mtime_ns
            second=audit(upgrade,baseline,'custom:tea_sets_2',split,32)
            self.assertEqual(first,second);self.assertEqual(sha256(path),expected);self.assertEqual(path.stat().st_mtime_ns,stamp)

    def test_split_leakage_is_rejected_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, upgrade, path = self.fixture(directory)
            split=json.loads(path.read_text()); split['eval']=[split['train'][0]]; write_json(path,split)
            with self.assertRaisesRegex(ValueError,'leakage'): audit(upgrade,baseline,'custom:tea_sets_2',path,32)

    def test_resolved_path_jail(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): inside(Path(directory), '../escape')

    def test_matrix_dedup_and_estimator_are_explicit_proxies(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, upgrade, split = self.fixture(directory)
            settings={'Studies': {'tiny': {'Scene':'custom:tea_sets_2','Views':[6,12],'Recipes':['uniform','coverage-overlap'],
                      'Methods':['nerfacto','splatfacto'],'Iterations':10000,'Seed':42,'Protocol':'capture-subset-10k-v1'}},
                      'AuditImageSize':32,'DownscaleFactor':2,'MinimumUpgradeFreeGiB':30}
            with patch('topic16_upgrade.runtime.runtime_snapshot',return_value='fixture-only'):
                result=plan(upgrade,settings,baseline,'tiny',split)
            self.assertEqual(len(result['jobs']),6)  # full pool deduplicates the recipes
            self.assertEqual(result['new_jobs'],6); self.assertEqual(result['cache_hits'],0)
            self.assertIsNone(result['eta']['training_seconds_proxy'])
            self.assertIn('not measured',result['eta']['source'])

    def test_resume_source_identity_changes_when_algorithm_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=root/'src/algorithm.py'; path.parent.mkdir();path.write_text('x=1')
            before=source_identity(root);path.write_text('x=2')
            self.assertNotEqual(before,source_identity(root))

    def test_changed_dry_run_does_not_overwrite_saved_resume_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline,upgrade,split=self.fixture(directory)
            source=upgrade/'src/a.py';source.parent.mkdir();source.write_text('original')
            settings={'Studies':{'tiny':{'Scene':'custom:tea_sets_2','Views':[6],'Recipes':['uniform'],
                'Methods':['nerfacto'],'Iterations':10000,'Seed':42,'Protocol':'capture-subset-10k-v1'}},
                'AuditImageSize':32,'DownscaleFactor':2,'MinimumUpgradeFreeGiB':30}
            with patch('topic16_upgrade.runtime.runtime_snapshot',return_value='fixture'):
                first=plan(upgrade,settings,baseline,'tiny',split)
                saved=(upgrade/'artifacts/jobs/tiny-plan.json').read_bytes()
                source.write_text('changed implementation')
                second=plan(upgrade,settings,baseline,'tiny',split)
            self.assertNotEqual(first['jobs'][0]['experiment_key'],second['jobs'][0]['experiment_key'])
            self.assertEqual((upgrade/'artifacts/jobs/tiny-plan.json').read_bytes(),saved)
            self.assertTrue((upgrade/'artifacts/jobs/tiny-proposed-plan.json').is_file())

    def test_incomplete_job_cannot_be_a_cache_hit(self):
        self.assertFalse(completed(Path('.'),{'status':'paused'}))
        self.assertFalse(completed(Path('.'),{'status':'failed'}))

    @unittest.skipUnless(os.name == 'nt', 'Native Windows byte-lock interoperability')
    def test_baseline_and_upgrade_contend_for_the_same_byte_lock(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
        from topic16.runtime import gpu_lock as baseline_lock
        from topic16_upgrade.runtime import gpu_lock as upgrade_lock
        with tempfile.TemporaryDirectory() as directory:
            baseline=Path(directory); upgrade=baseline/'upgrade'; upgrade.mkdir()
            settings={'SharedGpuLock':str(baseline/'artifacts/logs/gpu.lock')}
            with baseline_lock(baseline):
                with self.assertRaisesRegex(RuntimeError,'shared lock'):
                    with upgrade_lock(upgrade,settings): pass
            with upgrade_lock(upgrade,settings): pass

    @unittest.skipUnless(os.name == 'nt', 'Native ASCII junction path preservation')
    def test_native_dataparser_path_keeps_ascii_junction(self):
        from topic16_upgrade.data import scene_input
        from topic16_upgrade.contracts import native_workspace
        with tempfile.TemporaryDirectory(prefix='topic16 Unicode á ') as directory:
            root=Path(directory); alias=native_workspace(root)
            path,_,_=scene_input(alias,'custom:tiny')
            self.assertTrue(str(path).isascii())
            self.assertEqual(path.resolve(),root/'data/processed/canonical/tiny')


class PredictorTests(unittest.TestCase):
    def rows(self):
        rows=[]
        for group in range(6):
            for i in range(8):
                sharpness=(i+group)%8
                rows.append({'method':'nerfacto','budget':10000,'evaluator_id':EVALUATOR,'feature_schema':FEATURE_SCHEMA,
                             'scene_group':f'scene-{group}','run_key':f'{group}-{i}',
                             'features':{'views':60,'sharpness':sharpness,'clipped_fraction':.01,'coverage_bins':3,'radius_spread':.1},
                             'metrics':{'psnr':20+sharpness}})
        return rows

    def test_related_subsets_do_not_count_as_independent_scenes(self):
        rows=self.rows()
        for r in rows:r['scene_group']='one-video'
        model=train(rows,'nerfacto',10000,EVALUATOR)
        self.assertEqual(model['status'],'insufficient-evidence')
        self.assertIsNone(predict(model,rows[0]['features'],'nerfacto',10000,EVALUATOR)['prediction'])

    def test_all_seeds_and_subsets_of_a_scene_stay_out_of_its_training_fold(self):
        model=train(self.rows(),'nerfacto',10000,EVALUATOR)
        self.assertEqual(model['status'],'exploratory-validated')
        self.assertEqual(len(model['out_of_fold']),48)
        for row in model['out_of_fold']:
            self.assertNotIn(row['scene_group'],row['training_groups'])
            self.assertEqual(len(row['training_groups']),5)
        self.assertLess(model['validation']['predicted']['mae_db'],model['validation']['views_baseline']['mae_db'])

    def test_budget_evaluator_and_out_of_range_abstention(self):
        rows=self.rows(); model=train(rows,'nerfacto',10000,EVALUATOR); features=rows[0]['features']
        self.assertEqual(predict(model,features,'nerfacto',30000,EVALUATOR)['status'],'insufficient-evidence')
        self.assertEqual(predict(model,{**features,'views':999},'nerfacto',10000,EVALUATOR)['status'],'insufficient-evidence')
        self.assertEqual(predict(model,features,'nerfacto',10000,'other-evaluator')['status'],'insufficient-evidence')

    def test_historical_or_budget_mismatch_cannot_claim_improvement(self):
        left={k:1 for k in PAIR_FIELDS};left.update(variant='upgrade',views=60,run_key='a',metrics={'psnr':20.,'ssim':.8,'lpips':.2})
        right={**left,'run_key':'b','metrics':{'psnr':21.,'ssim':.81,'lpips':.19}}
        self.assertEqual(compare(left,right)['delta']['psnr'],1.)
        for change in ({'budget':30000},{'variant':'baseline'},{'views':30},{'evaluator_id':'other'},{'runtime_id':'other'}):
            self.assertIsNone(compare(left,{**right,**change})['delta'])


if __name__ == '__main__':
    unittest.main()
