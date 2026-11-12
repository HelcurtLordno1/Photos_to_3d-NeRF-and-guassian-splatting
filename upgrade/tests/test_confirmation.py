import copy
import unittest
import tempfile
from pathlib import Path
import numpy as np
from topic16_upgrade.confirmation import validate_profile,immutable_inspection,validate_review
from topic16_upgrade.contracts import write_json,sha256
from topic16_upgrade.sessions import SessionPaused
from topic16_upgrade.inspection_worker import trajectory


class ConfirmationContracts(unittest.TestCase):
    def setUp(self):
        self.profile={'SchemaVersion':'quality-confirmation-1','Seeds':[17,2026],
                      'MaximumGpuSeconds':10800,'OrbitFrames':120,'ReferenceStudy':'tea-research-v4'}

    def test_approved_matrix_is_accepted(self):
        validate_profile(self.profile)

    def test_seed_selection_and_budget_expansion_are_rejected(self):
        for field,value in [('Seeds',[42,17]),('MaximumGpuSeconds',14400),('OrbitFrames',30),('SchemaVersion','unknown')]:
            candidate={**self.profile,field:value}
            with self.subTest(field=field),self.assertRaises(ValueError):validate_profile(candidate)

    def test_continuous_path_keeps_endpoints_and_rigid_cameras(self):
        base={'width':719,'height':1279,'fx':1000.,'fy':999.,'cx':350.,'cy':640.,
              'camera_to_world':[[1.,0.,0.,0.],[0.,1.,0.,0.],[0.,0.,1.,1.]]}
        other=copy.deepcopy(base);other['camera_to_world']=[[0.,-1.,0.,1.],[1.,0.,0.,0.],[0.,0.,1.,1.]]
        path=trajectory([base,other],120)
        self.assertEqual(len(path),120)
        np.testing.assert_allclose(path[0]['camera_to_world'],base['camera_to_world'],atol=1e-7)
        np.testing.assert_allclose(path[-1]['camera_to_world'],other['camera_to_world'],atol=1e-7)
        for frame in path:
            r=np.asarray(frame['camera_to_world'])[:,:3]
            np.testing.assert_allclose(r.T@r,np.eye(3),atol=1e-7)
            self.assertAlmostEqual(np.linalg.det(r),1.)
        self.assertEqual(base['camera_to_world'][0][3],0.)

    def test_resume_preserves_review_hash_and_rejects_changed_inspection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);path=root/'inspection.json';state={'stages':{}}
            immutable_inspection(root,state,'inspection',path,{'status':'passed','finished_at':'original'})
            original=sha256(path);state['stages']['inspection']=[{'path':'inspection.json','sha256':original}]
            saved=immutable_inspection(root,state,'inspection',path,{'status':'passed','finished_at':'resume'})
            self.assertEqual(saved['finished_at'],'original');self.assertEqual(sha256(path),original)
            write_json(path,{'status':'passed','finished_at':'modified'})
            with self.assertRaisesRegex(ValueError,'Committed inspection changed'):
                immutable_inspection(root,state,'inspection',path,{})

    def test_images_only_or_stale_ui_proof_cannot_release_training(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);inspection=root/'inspection.json';ui=root/'ui.json';notes=root/'review.md'
            write_json(inspection,{'status':'passed'});write_json(ui,{'status':'passed','idle':None});notes.write_text('review')
            review={'status':'passed','inspection_sha256':sha256(inspection),'ui_check':{'path':'ui.json','sha256':sha256(ui)},
                    'references':[{'path':'review.md','sha256':sha256(notes)}]}
            with self.assertRaisesRegex(SessionPaused,'Full UI'):validate_review(root,review,inspection)
            write_json(ui,{'status':'passed','idle':{'before':4,'after':4},'load':{'time_to_ready_ms':1000}})
            with self.assertRaisesRegex(ValueError,'evidence changed'):validate_review(root,review,inspection)
            review['ui_check']['sha256']=sha256(ui);validate_review(root,review,inspection)
