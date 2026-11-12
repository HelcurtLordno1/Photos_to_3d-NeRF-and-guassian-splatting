"""Exact frozen cameras for official Improved-GS; upstream source stays clean."""
import math
import numpy as np
from PIL import Image
from .contracts import inside, sha256


def projection(frame, near=.01, far=100.):
    """OpenCV +Z projection; rasterizer integer centers equal gsplat centers −.5."""
    p=np.zeros((4,4),dtype=np.float32)
    p[0,0]=2*frame['fx']/frame['width'];p[1,1]=2*frame['fy']/frame['height']
    p[0,2]=2*frame['cx']/frame['width']-1;p[1,2]=2*frame['cy']/frame['height']-1
    p[2,2]=far/(far-near);p[2,3]=-far*near/(far-near);p[3,2]=1
    return p


def world_to_camera(frame):
    c2w=np.eye(4);c2w[:3,:]=frame['camera_to_world']
    c2w[:3,1:3]*=-1  # canonical OpenGL → official OpenCV
    return np.linalg.inv(c2w).astype(np.float32)


def verify_camera(frame):
    p=projection(frame).astype(np.float64)
    xyz=np.array([[.1,.2,2],[-.3,-.2,3],[0,0,1]],dtype=np.float64)
    clip=np.c_[xyz,np.ones(len(xyz))]@p.T
    ndc=clip[:,:2]/clip[:,3:4]
    pixels=(ndc+1)*np.array([frame['width'],frame['height']])/2-.5
    expected=xyz[:,:2]/xyz[:,2:3]*[frame['fx'],frame['fy']]+[frame['cx']-.5,frame['cy']-.5]
    error=float(np.max(np.abs(pixels-expected)))
    if error>1e-4:raise ValueError('Official rasterizer projection differs from frozen K')
    w2c=world_to_camera(frame)
    if not np.allclose(np.linalg.inv(w2c)[:3,3],np.asarray(frame['camera_to_world'])[:,3],atol=1e-6):
        raise ValueError('Camera center changed')
    if frame.get('camera_type',1)!=1 or any(abs(v)>1e-8 for v in frame.get('distortion_params',[])):
        raise ValueError('Official adapter requires frozen undistorted perspective images')
    return error


def make_camera(root, frame, uid):
    import torch
    from scene.cameras import Camera
    verify_camera(frame)
    path=inside(root,frame['path'])
    if sha256(path)!=frame['sha256']:raise ValueError('Frozen image changed')
    w2c=world_to_camera(frame)
    with Image.open(path) as image:
        if image.size!=(frame['width'],frame['height']):raise ValueError('Camera/image dimensions differ')
        camera=Camera((frame['width'],frame['height']),uid,w2c[:3,:3].T,w2c[:3,3],
            2*math.atan(frame['width']/(2*frame['fx'])),2*math.atan(frame['height']/(2*frame['fy'])),
            None,image.convert('RGB'),None,str(uid),uid,data_device='cuda')
    camera.projection_matrix=torch.from_numpy(projection(frame)).T.contiguous().cuda()
    camera.full_proj_transform=camera.world_view_transform@camera.projection_matrix
    return camera


class FrozenScene:
    def __init__(self,root,split,gaussians,output):
        from plyfile import PlyData
        from utils.graphics_utils import BasicPointCloud
        self.model_path=str(output);self.gaussians=gaussians
        self.train=[make_camera(root,f,i) for i,f in enumerate(split['train'])]
        self.test=[]  # held-out pixels are not loaded into the training process
        centers=np.array([np.asarray(f['camera_to_world'])[:,3] for f in split['train']])
        self.cameras_extent=float(np.linalg.norm(centers-centers.mean(axis=0),axis=1).max()*1.1)
        path=next(inside(root,f['path']) for f in split['pose_files'] if f['path'].endswith('.ply'))
        item=next(f for f in split['pose_files'] if f['path'].endswith('.ply'))
        if sha256(path)!=item['sha256']:raise ValueError('Sparse initialization changed')
        data=PlyData.read(path)['vertex']
        points=np.stack([data[k] for k in ('x','y','z')],axis=1)
        colors=np.stack([data[k] for k in ('red','green','blue')],axis=1)/255.
        gaussians.create_from_pcd(BasicPointCloud(points,colors,np.zeros_like(points)),self.train,self.cameras_extent)

    def getTrainCameras(self):return self.train
    def getTestCameras(self):return self.test
