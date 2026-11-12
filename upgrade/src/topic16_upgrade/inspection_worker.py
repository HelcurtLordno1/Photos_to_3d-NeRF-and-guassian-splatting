"""Checkpoint-preserving official CUDA multi-scale and continuous trajectory audit."""
from pathlib import Path
import argparse
import sys
import math
import time
import copy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic16_upgrade.contracts import read_json,write_json,inside,sha256,digest_json,utc_now
from topic16_upgrade.sessions import check_stop,SessionPaused


def trajectory(frames,count=120):
    from scipy.spatial.transform import Rotation,Slerp
    poses=np.array([f['camera_to_world'] for f in frames],dtype=float)
    keys=np.arange(len(frames));samples=np.linspace(0,len(frames)-1,count)
    rotations=Slerp(keys,Rotation.from_matrix(poses[:,:,:3]))(samples).as_matrix()
    output=[]
    for i,t in enumerate(samples):
        a=min(int(t),len(frames)-2);fraction=t-a
        frame=copy.deepcopy(frames[0]);pose=np.c_[rotations[i],poses[a,:,3]*(1-fraction)+poses[a+1,:,3]*fraction]
        frame['camera_to_world']=pose.tolist();output.append(frame)
    return output


def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);args=p.parse_args()
    job=read_json(args.job);root=Path(job['root']);output=inside(root,job['output']);output.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(root/'third_party/improved-gs'))
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from scene.gaussian_model import GaussianModel
    from scene.cameras import MiniCam
    from gaussian_renderer import render
    from types import SimpleNamespace
    from topic16_upgrade.improved_adapter import projection,world_to_camera
    from topic16_upgrade.multiscale import scaled_camera,verify_projection
    torch.set_num_threads(4)
    source=inside(root,job['result']);record=read_json(source)
    if sha256(source)!=job['result_sha256'] or record['checkpoint']['step']!=30000:raise ValueError('Audit result identity differs')
    from topic16_upgrade.runtime import runtime_snapshot
    from importlib.util import find_spec
    runtime=inside(root,job['runtime'])
    actual={'packages':runtime_snapshot(),'torch':torch.__version__,'extensions':{name:sha256(Path(find_spec(name).origin)) for name in
            ('diff_gaussian_rasterization._C','simple_knn._C','fused_ssim_cuda')}}
    if sha256(runtime)!=record['identity']['runtime_sha256'] or read_json(runtime)!=actual:
        raise ValueError('Audit runtime differs from the exact trained model')
    if sha256(source.parent/'model.ply')!=record['ply_sha256']:raise ValueError('Audit PLY changed')
    if sha256(source.parent/record['checkpoint']['path'])!=record['checkpoint']['sha256']:raise ValueError('Audit checkpoint changed')
    model=GaussianModel(3,record['identity']['resolved_options']['optimizer_type']);model.load_ply(str(source.parent/'model.ply'));model.active_sh_degree=3
    pipe=SimpleNamespace(debug=False,antialiasing=False,depth_ratio=0.)
    bg=torch.zeros(3,device='cuda');torch.cuda.reset_peak_memory_stats()
    def camera(frame):
        world=torch.from_numpy(world_to_camera(frame)).T.contiguous().cuda()
        full=world@torch.from_numpy(projection(frame)).T.contiguous().cuda()
        return MiniCam(frame['width'],frame['height'],2*math.atan(frame['height']/(2*frame['fy'])),
                       2*math.atan(frame['width']/(2*frame['fx'])),.01,100.,world,full)
    def draw(frame,factor=1,aux=False):
        verify_projection(frame,factor)
        result=render(camera(scaled_camera(frame,factor)),model,pipe,bg,track_gradients=False)
        if torch.cuda.max_memory_allocated()>12*2**30:raise SessionPaused('Inference allocator budget reached')
        rgb=result['render']
        if factor!=1:rgb=F.interpolate(rgb[None],size=(frame['height'],frame['width']),mode='area')[0]
        return result if aux else rgb.clamp(0,1)
    def save(rgb,path):
        Image.fromarray((rgb.clamp(0,1).permute(1,2,0).cpu().numpy()*255).round().astype('uint8')).save(path)
    rows=[]
    with torch.no_grad():
        for resolution,frames in [('native',job['native']),('half',job['half'])]:
            for variant,factor in [('direct',1),('area2x',2)]:
                print(job['method']+' audit '+resolution+' '+variant,flush=True)
                check_stop();folder=output/(resolution+'-'+variant);folder.mkdir(exist_ok=True)
                metadata={'source_result_sha256':job['result_sha256'],'camera_hash':digest_json(frames),'factor':factor,
                          'filter':'classic' if factor==1 else 'torch-area-float-rgb-v1','output_resolution':resolution}
                path=folder/'renders.json'
                if path.exists():
                    saved=read_json(path)
                    if saved['identity']!=metadata:raise ValueError('Existing audit cell identity differs')
                    for frame in saved['frames']:
                        for k in ('gt','pred'):
                            if sha256(folder/frame[k])!=frame[k+'_sha256']:raise ValueError('Existing audit image changed')
                else:
                    for i in range(3):draw(frames[i],factor)
                    durations=[]
                    for _ in range(3):
                        torch.cuda.synchronize();clock=time.perf_counter()
                        for frame in frames:check_stop();draw(frame,factor)
                        torch.cuda.synchronize();durations.append(time.perf_counter()-clock)
                    saved_frames=[];agreements=[]
                    for i,frame in enumerate(frames):
                        check_stop();pred=folder/f'pred_{i:04d}.png';gt=folder/f'gt_{i:04d}.png'
                        save(draw(frame,factor),pred)
                        source_gt=inside(root,frame['path'])
                        if sha256(source_gt)!=frame['sha256']:raise ValueError('Audit GT changed')
                        with Image.open(source_gt) as pixels:pixels.convert('RGB').save(gt)
                        saved_frames.append({'pred':pred.name,'gt':gt.name,'pred_sha256':sha256(pred),'gt_sha256':sha256(gt)})
                        if resolution=='native' and variant=='direct':
                            with Image.open(pred) as a,Image.open(source.parent/f'pred_{i:04d}.png') as b:
                                mse=np.mean((np.asarray(a,dtype=float)/255-np.asarray(b,dtype=float)/255)**2)
                            agreements.append(float(-10*np.log10(max(mse,1e-12))))
                    if agreements and min(agreements)<60:raise ValueError('PLY inference differs from final checkpoint renders')
                    saved={'status':'succeeded','identity':metadata,'frames':saved_frames,'fps':len(frames)*3/sum(durations),
                           'durations_seconds':durations,'checkpoint_render_agreement_db':agreements,
                           'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'finished_at':utc_now()}
                    write_json(path,saved)
                rows.append({'resolution':resolution,'variant':variant,'path':str(path.relative_to(root)),
                             'sha256':sha256(path),'fps':saved['fps']})
        for zoom in (.75,1.5):
            folder=output/f'zoom-{zoom}';folder.mkdir(exist_ok=True)
            for i,frame in enumerate(job['native']):
                check_stop();f=copy.deepcopy(frame);f['fx']*=zoom;f['fy']*=zoom
                save(draw(f),folder/f'pred_{i:04d}.png')
            write_json(folder/'scope.json',{'focal_scale':zoom,'principal_point':'unchanged','gt_metrics':None,
                                          'scope':'Novel rays without GT; visual inspection only'})
        path=output/'orbit';path.mkdir(exist_ok=True)
        cameras=trajectory(job['train'],120);write_json(path/'cameras.json',{'frames':cameras,'scope':'Interpolated adjacent train poses within capture coverage; no orbit GT'})
        for i,frame in enumerate(cameras):
            check_stop();save(draw(frame),path/f'pred_{i:04d}.png')
            if i%20==0:print(job['method']+f' orbit {i}/120',flush=True)
            if i%10==0:
                pkg=draw(frame,aux=True);depth=pkg.get('depth')
                if depth is not None:np.save(path/f'depth_{i:04d}.npy',depth.cpu().numpy())
        ancillary=[{'path':str(p.relative_to(root)),'sha256':sha256(p)} for p in sorted(output.rglob('*'))
                   if p.is_file() and (p.parent.name.startswith('zoom-') or p.parent.name=='orbit')]
        write_json(output/'result.json',{'status':'succeeded','source':job['result'],'source_sha256':job['result_sha256'],'rows':rows,
                   'ancillary':ancillary,
                   'orbit':str(path.relative_to(root)),'orbit_camera_hash':sha256(path/'cameras.json'),
                   'opacity_auxiliary':'Renderer does not expose accumulated alpha; not claimed',
                   'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'finished_at':utc_now()})
    print('Scale/zoom/orbit audit completed: '+job['method'],flush=True)


if __name__=='__main__':
    try:main()
    except SessionPaused:raise SystemExit(75)
