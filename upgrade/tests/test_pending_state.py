"""Real serialization/Adam/pending-gradient wrapper contract, CPU only."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import torch
from topic16_upgrade.final_worker import capture,restore,atomic_torch,state_equal


class GaussianContainer:
    names=('_xyz','_features_dc','_features_rest','_scaling','_rotation','_opacity')
    def __init__(self):
        for name in self.names:setattr(self,name,torch.nn.Parameter(torch.ones(3)))
        self.optimizer=torch.optim.Adam([getattr(self,n) for n in self.names])
        self._exposure=torch.nn.Parameter(torch.eye(3,4)[None])
        self.exposure_optimizer=torch.optim.Adam([self._exposure])
    def capture(self):return ({n:getattr(self,n).detach().clone() for n in self.names},self.optimizer.state_dict())
    def restore(self,payload,opt):
        for name,value in payload[0].items():setattr(self,name,torch.nn.Parameter(value.clone()))
        self.optimizer=torch.optim.Adam([getattr(self,n) for n in self.names]);self.optimizer.load_state_dict(payload[1])


class PendingStateContract(unittest.TestCase):
    def test_pending_gradients_sampler_and_adam_survive_atomic_disk_restore(self):
        model=GaussianContainer();cameras=[SimpleNamespace(uid=i) for i in range(4)]
        context=SimpleNamespace(opt=None,scene=SimpleNamespace(getTrainCameras=lambda:cameras),
            runtime_state={'train_cameras':cameras,'edge_maps':[torch.full((2,2),float(i)) for i in range(4)],
                'edge_camera_pool':[cameras[3],cameras[1]],'edge_map_pool':[], 'rap_reset_count':2})
        loop={'viewpoint_stack':[cameras[2],cameras[0]]};identity={'fixture':'pending-MU'}
        sum(getattr(model,n).sum() for n in model.names).backward();model.optimizer.step()
        for i,n in enumerate(model.names):getattr(model,n).grad=torch.full_like(getattr(model,n),float(i+1))
        model._exposure.grad=torch.full_like(model._exposure,2.5)
        with patch.object(torch.cuda,'get_rng_state_all',return_value=[]),patch.object(torch.cuda,'set_rng_state_all'):
            payload=capture(model,context,loop,20001,identity,20000)
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/'checkpoint.pt';atomic_torch(path,payload);saved=torch.load(path)
                for n in model.names:getattr(model,n).grad=None
                context.runtime_state['rap_reset_count']=99;loop['viewpoint_stack']=[]
                restore(saved,model,context,loop,identity)
                actual=capture(model,context,loop,20001,identity,20000)
                self.assertTrue(state_equal(saved,actual))
                self.assertTrue(all(getattr(model,n).grad is not None for n in model.names))
                self.assertEqual([c.uid for c in context.runtime_state['edge_camera_pool']],[3,1])
                self.assertEqual([float(t[0,0]) for t in context.runtime_state['edge_map_pool']],[3.,1.])
