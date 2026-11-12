"""Input equivalence to the pinned upstream loader, independent of training."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
from PIL import Image
import torch
from topic16_upgrade.bounded_adapter import ImageCache


class BoundedInputContracts(unittest.TestCase):
    def test_all_uint8_values_match_upstream_normalization_and_strides(self):
        path=Path(__file__).resolve().parents[1]/'third_party/improved-gs/utils/general_utils.py'
        spec=importlib.util.spec_from_file_location('pinned_image_contract',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        values=np.arange(256,dtype=np.uint8).reshape(16,16)
        rgb=np.stack([values,np.flipud(values),np.fliplr(values)],axis=-1)
        expected=module.PILtoTorch(Image.fromarray(rgb),(16,16))[:3].clamp(0,1)
        cache=ImageCache(2,'cpu');cache.add(0,rgb);actual=cache.get(0)
        self.assertTrue(torch.equal(expected,actual));self.assertEqual(expected.stride(),actual.stride())

    def test_eviction_preserves_pixels_and_residency_bound(self):
        cache=ImageCache(2,'cpu')
        for uid in range(5):cache.add(uid,np.full((7,9,3),uid*41,dtype=np.uint8))
        for uid in [0,1,2,4,3,0,4]:
            actual=cache.get(uid);self.assertLessEqual(len(cache.active),2)
            self.assertTrue(torch.equal(actual,torch.full_like(actual,float(np.float32(uid*41/255)))))
        self.assertEqual(list(cache.active),[0,4])

    def test_lossy_or_ambiguous_inputs_are_rejected(self):
        cache=ImageCache(2,'cpu')
        for invalid in [np.zeros((2,3,4),dtype=np.uint8),np.zeros((2,3,3),dtype=float)]:
            with self.assertRaises(ValueError):cache.add(0,invalid)
        cache.add(0,np.zeros((2,3,3),dtype=np.uint8))
        with self.assertRaises(ValueError):cache.add(0,np.zeros((2,3,3),dtype=np.uint8))
