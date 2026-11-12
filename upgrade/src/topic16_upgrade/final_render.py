"""Exact PLY round-trip checks and a small set of genuine large-buffer renders.

No training or artificial GT upscaling. Optional output profiles have explicit
memory checks and retain unsupported/failed evidence without replacing native.
"""
from pathlib import Path
import argparse
import copy
import gc
import math
import sys
import time
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic16_upgrade.contracts import read_json,write_json,sha256,inside,relative,digest_json
from topic16_upgrade.sessions import check_stop,SessionPaused
from topic16_upgrade.improved_adapter import projection,world_to_camera,verify_camera


def long_edge_camera(frame,long_edge):
    if long_edge not in (3840,7680):raise ValueError('Unsupported declared high-resolution output')
    result=copy.deepcopy(frame);factor=long_edge/max(frame['width'],frame['height'])
    width=max(2,round(frame['width']*factor));height=max(2,round(frame['height']*factor))
    result.update(width=width,height=height)
    for key in ('fx','cx'):result[key]=frame[key]*width/frame['width']
    for key in ('fy','cy'):result[key]=frame[key]*height/frame['height']
    verify_camera(result);return result


def main():
    import torch
    parser=argparse.ArgumentParser();parser.add_argument('--job',type=Path,required=True);args=parser.parse_args()
    job=read_json(args.job);root=Path(job['root']);sys.path.insert(0,str(root/'third_party/improved-gs'))
    from scene.gaussian_model import GaussianModel
    from scene.cameras import MiniCam
    from gaussian_renderer import render
    from types import SimpleNamespace
    torch.set_num_threads(4);output=inside(root,job['output']);output.mkdir(parents=True,exist_ok=True)
    pipe=SimpleNamespace(debug=False,antialiasing=False,depth_ratio=0.)
    def camera(f):
        verify_camera(f);world=torch.from_numpy(world_to_camera(f)).T.contiguous().cuda()
        return MiniCam(f['width'],f['height'],2*math.atan(f['height']/(2*f['fy'])),2*math.atan(f['width']/(2*f['fx'])),
            .01,100.,world,world@torch.from_numpy(projection(f)).T.contiguous().cuda())
    results=[]
    with torch.no_grad():
        for item in job['models']:
            check_stop();owner=root.parent if item['owner']=='baseline' else root
            ply=inside(owner,item['ply'])
            if sha256(ply)!=item['ply_sha256']:raise ValueError('High-resolution source PLY changed')
            model=GaussianModel(3,'default');model.load_ply(str(ply));model.active_sh_degree=3
            background=torch.tensor(item['background'],dtype=torch.float32,device='cuda')
            folder=output/item['id'];folder.mkdir(exist_ok=True);agreements=[]
            for i,f in enumerate(job['cameras']):
                check_stop();rgb=render(camera(f),model,pipe,background,track_gradients=False)['render'].clamp(0,1)
                pixels=(rgb.permute(1,2,0).cpu().numpy()*255).round().astype('uint8')
                reference=inside(owner,item['native'][i]['path'])
                if sha256(reference)!=item['native'][i]['sha256']:raise ValueError('Native reference changed')
                with Image.open(reference) as im:
                    if im.size!=(f['width'],f['height']):raise ValueError('Native camera/reference dimensions differ')
                    expected=np.asarray(im.convert('RGB'),dtype=float)
                mse=float(np.mean(((pixels.astype(float)-expected)/255)**2));agreements.append(-10*math.log10(max(mse,1e-12)))
            exact=item['owner']!='baseline'
            if exact and min(agreements)<60:raise ValueError('Candidate PLY differs from committed native checkpoint images')
            row={'id':item['id'],'ply_sha256':item['ply_sha256'],'native_agreement_db':agreements,
                 'native_scope':'Candidate exact round trip >=60dB; historical baseline cross-renderer diagnostic, not guaranteed identical.',
                 'profiles':[]}
            for edge,indices in [(3840,sorted({0,len(job['cameras'])//2,len(job['cameras'])-1})),(7680,[0])]:
                for i in indices:
                    check_stop();f=long_edge_camera(job['cameras'][i],edge)
                    path=folder/(str(edge)+'-'+str(i)+'.png');metadata=path.with_suffix('.json')
                    identity={'camera_hash':digest_json(f),'ply_sha256':item['ply_sha256'],'background':item['background'],
                        'renderer':'official-classic-sh3','long_edge':edge,'view':i,'width':f['width'],'height':f['height']}
                    if metadata.exists():
                        saved=read_json(metadata)
                        if saved['identity']!=identity:raise ValueError('High-resolution profile identity changed')
                        if saved['status']=='succeeded' and sha256(path)!=saved['sha256']:raise ValueError('High-resolution pixels changed')
                    else:
                        free,_=torch.cuda.mem_get_info();estimate=f['width']*f['height']*96+len(model.get_xyz)*2048
                        saved={'identity':identity,'status':'unsupported','scope':'No GT at this output; no PSNR/SSIM/LPIPS claim.',
                            'estimated_workspace_bytes':estimate}
                        if not exact and min(agreements)<25:saved['reason']='Baseline cross-renderer agreement too low for a trustworthy derived comparison'
                        elif estimate>min(10*2**30,max(0,free-2*2**30)):saved['reason']='Conservative workspace estimate exceeds the declared reserve'
                        else:
                            torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize();clock=time.perf_counter()
                            rgb=render(camera(f),model,pipe,background,track_gradients=False)['render'].clamp(0,1)
                            torch.cuda.synchronize();seconds=time.perf_counter()-clock
                            peak=torch.cuda.max_memory_allocated()
                            if peak>12*2**30:raise SessionPaused('High-resolution allocator exceeded12GiB; native artifacts retained')
                            Image.fromarray((rgb.permute(1,2,0).cpu().numpy()*255).round().astype('uint8')).save(path)
                            saved.update(status='succeeded',path=relative(root,path),sha256=sha256(path),render_seconds=seconds,
                                peak_cuda_allocated_bytes=peak,bytes=path.stat().st_size,
                                timing_scope='One synchronized render, excluding PLY load/PNG encoding; not steady-state FPS')
                            del rgb
                        write_json(metadata,saved)
                    row['profiles'].append(saved);print(item['id']+' '+str(edge)+' view'+str(i)+': '+saved['status'],flush=True)
            results.append(row);del model,background;gc.collect();torch.cuda.empty_cache()
    write_json(output/'profiles.json',{'status':'evaluated','models':results,'job_sha256':sha256(args.job),
        'scope':'Aspect retained to integer-pixel rounding; K scaled independently to exact output dimensions. Large renders do not imply new captured detail.'})


if __name__=='__main__':
    try:main()
    except SessionPaused as error:print(str(error),flush=True);raise SystemExit(75)
