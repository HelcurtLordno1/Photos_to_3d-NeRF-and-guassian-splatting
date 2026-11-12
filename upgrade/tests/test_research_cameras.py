import unittest
import numpy as np
from topic16_upgrade.multiscale import scaled_camera,verify_projection
from topic16_upgrade.improved_adapter import projection,world_to_camera,verify_camera


class FrozenResearchCameraTests(unittest.TestCase):
    def setUp(self):
        self.frame={'width':719,'height':1279,'fx':1070.79,'fy':1064.94,'cx':347.2,'cy':650.8,
                    'camera_to_world':[[1,0,0,.3],[0,1,0,-.4],[0,0,1,1.2]],
                    'camera_type':1,'distortion_params':[0.,0.,0.,0.,0.,0.]}

    def test_offcenter_projection_agrees_with_pinhole(self):
        self.assertLess(verify_camera(self.frame),1e-4)
        self.assertNotEqual(projection(self.frame)[0,2],0.)

    def test_opengl_world_frame_is_preserved(self):
        transform=world_to_camera(self.frame)
        point=np.array([.3,-.4,.2,1.])
        np.testing.assert_allclose((transform@point)[:3],[0,0,1],atol=1e-6)

    def test_integer_supersampling_preserves_rays_and_odd_extents(self):
        self.assertLess(verify_projection(self.frame,2),1e-12)
        scaled=scaled_camera(self.frame,2)
        self.assertEqual((scaled['width'],scaled['height']),(1438,2558))
        self.assertEqual(self.frame['width'],719)
        self.assertEqual(scaled['cx'],694.4)

    def test_distorted_camera_is_rejected(self):
        self.frame['distortion_params'][0]=.1
        with self.assertRaises(ValueError):verify_camera(self.frame)


if __name__=='__main__':unittest.main()
