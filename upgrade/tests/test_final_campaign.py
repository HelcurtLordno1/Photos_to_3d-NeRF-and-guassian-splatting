import copy
import random
import unittest
import numpy as np
from topic16_upgrade.final_data import validation_indices
from topic16_upgrade.final_render import long_edge_camera
from topic16_upgrade.final_campaign import select_capacity


class FinalCampaignContracts(unittest.TestCase):
    def test_validation_is_pose_only_disjoint_and_does_not_change_global_rng(self):
        class PoseOnly(dict):
            def __getitem__(self,key):
                if key!='camera_to_world':raise AssertionError('Selector inspected non-pose evidence')
                return super().__getitem__(key)
        frames=[]
        for i in range(105):
            angle=i*.09;c,s=np.cos(angle),np.sin(angle)
            frames.append(PoseOnly(camera_to_world=[[c,-s,0,c],[s,c,0,s],[0,0,1,i*.01]]))
        state=random.getstate();first=validation_indices(frames);second=validation_indices(frames)
        self.assertEqual(first,second);self.assertEqual(len(set(first)),15)
        self.assertEqual(len(set(range(105))-set(first)),90);self.assertEqual(random.getstate(),state)

    def test_large_render_keeps_rays_and_records_real_odd_pixel_dimensions(self):
        frame={'width':719,'height':1279,'fx':1000.,'fy':998.,'cx':361.2,'cy':638.7,
               'camera_to_world':[[1,0,0,0],[0,1,0,0],[0,0,1,1]]}
        original=copy.deepcopy(frame)
        for edge in (3840,7680):
            scaled=long_edge_camera(frame,edge);self.assertEqual(max(scaled['width'],scaled['height']),edge)
            for key,axis in [('fx','width'),('cx','width'),('fy','height'),('cy','height')]:
                self.assertAlmostEqual(scaled[key]/scaled[axis],frame[key]/frame[axis],places=12)
            self.assertEqual(scaled['camera_to_world'],frame['camera_to_world'])
        self.assertEqual(frame,original)

    def test_capacity_requires_joint_quality_cost_and_browser_gates(self):
        spec={'MinimumRoiLpipsGain':.05,'MaximumValidationPsnrLoss':.2,'MaximumQualityPlyMiB':110}
        old={'roi_metrics':{'lpips':.1},'metrics':{'psnr':30}}
        new={'roi_metrics':{'lpips':.094},'metrics':{'psnr':30.1}}
        browser={'parity_met':True,'timing_met':True}
        self.assertEqual(select_capacity(old,new,browser,100*2**20,spec)['chosen_budget'],450000)
        for changed in [dict(browser,timing_met=False),dict(browser,parity_met=False)]:
            self.assertEqual(select_capacity(old,new,changed,100*2**20,spec)['chosen_budget'],300000)
        new['metrics']['psnr']=29.7
        self.assertEqual(select_capacity(old,new,browser,100*2**20,spec)['chosen_budget'],300000)
