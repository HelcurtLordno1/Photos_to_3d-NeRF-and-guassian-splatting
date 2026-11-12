"""Lossless CPU image storage, bounded CUDA residency; unchanged official math.

This adapter is separately pinned. The v4 adapter and trainer remain untouched.
"""
from collections import OrderedDict
from pathlib import Path
import hashlib
import math
import numpy as np
from PIL import Image
from .contracts import inside,sha256,write_json,read_json,digest_json
from .improved_adapter import projection,world_to_camera,verify_camera


class ImageCache:
    def __init__(self,capacity=2,device='cuda'):
        import torch
        if capacity<1:raise ValueError('Image cache must be bounded and nonempty')
        self.capacity=capacity;self.device=torch.device(device);self.images={};self.active=OrderedDict()
        # Verified against every uint8 value in pinned PILtoTorch: the LUT
        # preserves its float32 bits, without a GPU reciprocal or re-encoding.
        self.table=torch.from_numpy((np.arange(256,dtype=np.float64)/255).astype(np.float32)).to(self.device)
        self.mask=torch.ones((1,1,1),dtype=torch.float32,device=self.device)

    def add(self,uid,pixels):
        import torch
        rgb=np.asarray(pixels)
        if rgb.dtype!=np.uint8 or rgb.ndim!=3 or rgb.shape[2]!=3:raise ValueError('Only exact uint8 RGB input is supported')
        if uid in self.images:raise ValueError('Duplicate cached camera identity')
        self.images[uid]=torch.from_numpy(rgb.copy())

    def get(self,uid):
        if uid in self.active:
            self.active.move_to_end(uid);return self.active[uid]
        if len(self.active)>=self.capacity:self.active.popitem(last=False)
        # Decode HWC then permute, matching original image values AND strides.
        result=self.table[self.images[uid].to(self.device).long()].permute(2,0,1)
        self.active[uid]=result
        return result


class CachedCamera:
    def __init__(self,camera,cache,uid):
        import torch
        original=camera.original_image
        if not bool(torch.all(camera.alpha_mask==1)):raise ValueError('Unexpected alpha mask; no implicit mask conversion')
        decoded=cache.get(uid)
        if decoded.stride()!=original.stride() or not torch.equal(decoded.cpu(),original):
            raise ValueError('Bounded cache differs from original normalized pixels/layout')
        self.__dict__.update(camera.__dict__)
        self.__dict__.pop('original_image',None);self.__dict__.pop('alpha_mask',None)
        self._cache=cache;self._cache_uid=uid

    @property
    def original_image(self):return self._cache.get(self._cache_uid)

    @property
    def alpha_mask(self):return self._cache.mask.expand(1,self.image_height,self.image_width)


def make_camera(root,frame,uid,cache=None):
    import torch
    from scene.cameras import Camera
    verify_camera(frame);path=inside(root,frame['path'])
    if sha256(path)!=frame['sha256']:raise ValueError('Frozen image changed')
    cache=cache or ImageCache();w2c=world_to_camera(frame)
    with Image.open(path) as image:
        if image.size!=(frame['width'],frame['height']):raise ValueError('Camera/image dimensions differ')
        rgb=image.convert('RGB');cache.add(uid,np.asarray(rgb))
        camera=Camera((frame['width'],frame['height']),uid,w2c[:3,:3].T,w2c[:3,3],
            2*math.atan(frame['width']/(2*frame['fx'])),2*math.atan(frame['height']/(2*frame['fy'])),
            None,rgb,None,str(uid),uid,data_device='cpu')
    camera.projection_matrix=torch.from_numpy(projection(frame)).T.contiguous().cuda()
    camera.full_proj_transform=camera.world_view_transform@camera.projection_matrix
    return CachedCamera(camera,cache,uid)


class FrozenScene:
    def __init__(self,root,split,gaussians,output):
        from plyfile import PlyData
        from utils.graphics_utils import BasicPointCloud
        self.model_path=str(output);self.gaussians=gaussians;self.cache=ImageCache(2)
        self.root=root;self.frames=split['train']
        self.train=[make_camera(root,f,i,self.cache) for i,f in enumerate(split['train'])]
        self.test=[]
        centers=np.array([np.asarray(f['camera_to_world'])[:,3] for f in split['train']])
        self.cameras_extent=float(np.linalg.norm(centers-centers.mean(axis=0),axis=1).max()*1.1)
        item=next(f for f in split['pose_files'] if f['path'].endswith('.ply'));path=inside(root,item['path'])
        if sha256(path)!=item['sha256']:raise ValueError('Sparse initialization changed')
        data=PlyData.read(path)['vertex'];points=np.stack([data[k] for k in ('x','y','z')],axis=1)
        colors=np.stack([data[k] for k in ('red','green','blue')],axis=1)/255.
        gaussians.create_from_pcd(BasicPointCloud(points,colors,np.zeros_like(points)),self.train,self.cameras_extent)
        self.proof={'schema_version':'bounded-input-1','train_camera_hash':digest_json(split['train']),
            'rgb_float_bits_and_strides':'exact at every training camera','mask':'identical all-one values; broadcast storage',
            'maximum_cached_gpu_images':2,'host_rgb_bytes':sum(x.numel() for x in self.cache.images.values()),
            'heldout_loaded_into_training':False,'adapter_sha256':sha256(Path(__file__))}

    def getTrainCameras(self):return self.train
    def getTestCameras(self):return self.test


def attach_bounded(context,scene,model):
    """Store unchanged GPU-computed EAS weights on CPU, transfer when consumed.

The upstream renderer already moves pixel_weights to the model device. This
temporary, explicitly recorded bridge only changes storage, never edge math.
"""
    import torch
    import scene.training_context as module
    from scene.methods.densification_methods import compute_edge_map
    from .improved_adapter import make_camera as original_camera
    original=module.prepare_edge_maps
    hashes=[]
    def edges(cameras,opt):
        result=[]
        for c in cameras:
            edge=compute_edge_map(c.original_image).detach().cpu().contiguous()
            hashes.append(hashlib.sha256(edge.numpy().tobytes()).hexdigest());result.append(edge)
        return result
    # Train-only reference cameras validate the full CUDA input/edge path.
    for index in sorted({0,len(scene.train)//2,len(scene.train)-1}):
        bounded=scene.train[index]
        reference=original_camera(scene.root,scene.frames[index],index)
        if (not torch.equal(reference.original_image,bounded.original_image)
                or not torch.equal(reference.alpha_mask,bounded.alpha_mask)
                or not torch.equal(reference.full_proj_transform,bounded.full_proj_transform)
                or not torch.equal(compute_edge_map(reference.original_image),compute_edge_map(bounded.original_image))):
            raise ValueError('Bounded CUDA camera/edge path differs from the v4 adapter')
        del reference
    module.prepare_edge_maps=edges
    try:context=module.attach_scene_and_gaussians_to_context(context,scene,model)
    finally:module.prepare_edge_maps=original
    scene.proof.update(status='passed',edge_operator_sha256=sha256(Path(module.__file__).parent/'methods/densification_methods.py'),
        edge_storage='CPU float32; upstream transfer on use',edge_hashes=hashes)
    path=Path(scene.model_path)/'cache-proof.json'
    if path.exists():
        if read_json(path)!=scene.proof:raise ValueError('Cache contract changed across resume')
    else:write_json(path,scene.proof)
    return context


def check_host_memory(minimum_gib):
    import ctypes
    from .sessions import SessionPaused
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in
            ('total','available','total_page','available_page','total_virtual','available_virtual','extended')]
    status=Status();status.length=ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):raise ValueError('Host memory telemetry unavailable')
    if status.available<minimum_gib*2**30:raise SessionPaused('Host memory reserve reached; preserve the current checkpoint')


def verify_pending_checkpoint(model,context,loop,identity,updates,path,output,capture,restore):
    """Verify actual MU pending gradients in the continuing full training run.

    This is exact state + fixed train forward recovery, not a promise of bitwise
    future CUDA updates. The separate600-step test still checks a10-step replay.
    """
    import torch
    from gaussian_renderer import render
    def state_equal(a,b):
        if torch.is_tensor(a):return torch.is_tensor(b) and a.shape==b.shape and torch.equal(a,b)
        if isinstance(a,np.ndarray):return isinstance(b,np.ndarray) and np.array_equal(a,b)
        if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(state_equal(v,b[k]) for k,v in a.items())
        if isinstance(a,(tuple,list)):return isinstance(b,(tuple,list)) and len(a)==len(b) and all(state_equal(x,y) for x,y in zip(a,b))
        return a==b
    proof_path=output/'pending-gradient-check.json'
    payload=torch.load(path)
    if not any(g is not None for g in payload['grads'].values()):raise ValueError('Expected pending MU gradients are missing')
    before=capture(model,context,loop,20001,identity,updates)
    with torch.no_grad():
        expected=render(context.scene.getTrainCameras()[0],model,context.pipe,loop['background'],track_gradients=False)['render'].detach().cpu()
    restore(payload,model,context,loop,identity)
    recovered=capture(model,context,loop,20001,identity,updates)
    exact={k:state_equal(v,recovered[k]) for k,v in before.items()}
    with torch.no_grad():
        actual=render(context.scene.getTrainCameras()[0],model,context.pipe,loop['background'],track_gradients=False)['render'].detach().cpu()
    mse=float((expected-actual).square().mean());agreement=-10*math.log10(max(mse,1e-12))
    result={'status':'passed' if all(exact.values()) and agreement>=60 else 'failed','boundary':20001,
        'checkpoint_sha256':sha256(path),'exact_restore_fields':exact,'pending_gradients_present':True,
        'fixed_train_render_agreement_db':agreement,'scope':'Actual full-run MU checkpoint; exact pending state and train forward. Not a10-step MU trajectory claim.'}
    if proof_path.exists():
        previous=read_json(proof_path)
        if previous['status']!='passed':raise ValueError('Previous pending-gradient check failed; preserve it for review')
        from .contracts import utc_now
        attempt=output/'pending-gradient-attempts'/(utc_now().replace(':','').replace('.','')+'.json')
        write_json(attempt,result)
    else:write_json(proof_path,result)
    if result['status']!='passed':raise ValueError('Pending-gradient checkpoint recovery failed')
