"""Cross-renderer camera/PLY check on an existing Q1 model, no training."""
from pathlib import Path
import argparse
import sys
import math
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic16_upgrade.contracts import read_json,write_json,inside,sha256


def main():
    p=argparse.ArgumentParser();p.add_argument('--declaration',type=Path,required=True);args=p.parse_args()
    declaration=read_json(args.declaration);root=Path(declaration['root'])
    sys.path.insert(0,str(inside(root,declaration['upstream'])))
    import torch
    from scene.gaussian_model import GaussianModel
    from gaussian_renderer import render
    from types import SimpleNamespace
    from PIL import Image
    from topic16_upgrade.improved_adapter import make_camera
    torch.set_num_threads(4)
    q1=read_json(root/'artifacts/jobs/quality/tea-quality-v2.json')
    config=inside(root,q1['config']);key=config.parent.relative_to(root/'artifacts/runs')
    exported=root/'artifacts/exports'/key
    metadata=read_json(exported/'export.json')
    item=next(f for f in metadata['files'] if f['name'].endswith('.ply'))
    ply=inside(exported,item['name'])
    if sha256(ply)!=item['sha256']:raise ValueError('Q1 PLY changed')
    model=GaussianModel(3,'default');model.load_ply(str(ply));model.active_sh_degree=3
    pipe=SimpleNamespace(debug=False,antialiasing=False,depth_ratio=0.)
    background=torch.tensor([.1490,.1647,.2157],dtype=torch.float32,device='cuda')
    split=read_json(inside(root,declaration['split']))
    output=root/'reports'/declaration['spec']['Study']/'official-parity';output.mkdir(parents=True,exist_ok=True)
    rows=[]
    with torch.no_grad():
        for i in (0,10,13):
            camera=make_camera(root,split['eval'][i],i)
            rgb=render(camera,model,pipe,background,track_gradients=False)['render'].clamp(0,1)
            pixels=(rgb.permute(1,2,0).cpu().numpy()*255).round().astype('uint8')
            Image.fromarray(pixels).save(output/f'official_{i:04d}.png')
            reference=root/f'reports/tea-quality-v2/evaluation/native-candidate-native/pred_{i:04d}.png'
            with Image.open(reference) as image:expected=np.asarray(image.convert('RGB'),dtype=np.float64)/255
            mse=float(np.mean((pixels.astype(np.float64)/255-expected)**2))
            rows.append({'view':i,'psnr_agreement':-10*math.log10(max(mse,1e-12)),
                         'reference_sha256':sha256(reference),'official_sha256':sha256(output/f'official_{i:04d}.png')})
    passed=all(r['psnr_agreement']>=32 for r in rows)
    write_json(output/'report.json',{'status':'passed' if passed else 'failed','frames':rows,
        'threshold_db':32,'q1_ply_sha256':sha256(ply),'declaration_sha256':sha256(args.declaration),
        'scope':'Existing Q1 Gaussian PLY, exact off-center cameras0/10/13, official CUDA vs saved gsplat RGB8. Renderer agreement, not GT quality.'})
    if not passed:raise ValueError('Official camera/PLY parity gate failed; inspect projection before training')
    print('Official camera/PLY parity passed',flush=True)


if __name__=='__main__':main()
