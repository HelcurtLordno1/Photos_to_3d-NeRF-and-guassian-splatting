"""Read-only baseline reuse and a single canonical GT for final comparisons."""
from pathlib import Path
import numpy as np
from PIL import Image
from .contracts import read_json,write_json,sha256,digest_json,inside,relative,load_run
from .evidence import score_saved_images,EVALUATOR


def reference(root,path,owner='upgrade'):
    base=root.parent if owner=='baseline' else root
    return {'owner':owner,'path':relative(base,path),'sha256':sha256(path)}


def resolve(root,ref):
    if ref['owner'] not in ('baseline','upgrade'):raise ValueError('Unknown final reference owner')
    owner=root.parent if ref['owner']=='baseline' else root
    path=inside(owner,ref['path'])
    if sha256(path)!=ref['sha256']:raise ValueError('Final image/model reference changed')
    return path


def baseline_record(root,scene,split):
    baseline=root.parent
    matches=[p for matrix in sorted((baseline/'artifacts/logs/matrices').glob('topic16-full-*.json'))
             for key,p in read_json(matrix)['pairs'].items() if key==scene]
    if len(matches)!=1:raise ValueError('Final scene must have one preserved baseline pair')
    run=load_run(baseline,inside(baseline,matches[0]['runs']['splatfacto']),require_eval=True)
    if run['manifest']['protocol']['iterations']!=30000:raise ValueError('Baseline reference is not30k')
    export=read_json(run['paths']['exports']/'export.json');item=next(f for f in export['files'] if f['name'].endswith('.ply'))
    ply=run['paths']['exports']/item['name']
    if sha256(ply)!=item['sha256']:raise ValueError('Baseline export changed')
    if scene=='custom:tea_sets_2':
        folder=root/'reports/tea-quality-v2/evaluation/historical-native';rendered=read_json(folder/'renders.json');owner='upgrade'
    else:folder=run['paths']['renders'];rendered=run['evaluation'];owner='baseline'
    if len(rendered['frames'])!=len(split['eval']):raise ValueError('Baseline evaluation view count differs')
    frames=[];pixel_diagnostics=[]
    for i,(frame,camera) in enumerate(zip(rendered['frames'],split['eval'])):
        pred=folder/frame['pred'];gt=folder/frame['gt'];canonical=inside(root,camera['path'])
        if sha256(pred)!=frame['pred_sha256'] or sha256(gt)!=frame['gt_sha256']:raise ValueError('Baseline saved pixels changed')
        with Image.open(gt) as a,Image.open(canonical) as b:
            if a.size!=b.size or a.size!=(camera['width'],camera['height']):raise ValueError('Baseline/canonical GT size mismatch')
            difference=np.abs(np.asarray(a.convert('RGB'),dtype=np.int16)-np.asarray(b.convert('RGB'),dtype=np.int16))
        maximum=int(difference.max())
        if maximum>1:raise ValueError('Baseline GT differs beyond RGB8 quantization; inspect data before training')
        pixel_diagnostics.append({'view':i,'maximum_gt_rgb8_difference':maximum,'mean_gt_rgb8_difference':float(difference.mean())})
        frames.append({'gt':reference(root,canonical),'pred':reference(root,pred,owner)})
    protocol=run['manifest']['protocol']
    return {'id':'baseline','label':'Preserved Splatfacto30k','model':reference(root,ply,'baseline'),
        'checkpoint_sha256':run['provenance']['checkpoint_sha256'],'config':reference(root,run['config'],'baseline'),
        'frames':frames,'original_metrics':{k:run['metrics']['results'][k] for k in ('psnr','ssim','lpips')},
        'training_seconds':run['manifest']['execution_metrics']['wall_time_seconds'],
        'peak_vram_mb_historical':run['manifest']['execution_metrics']['peak_vram_mb'],
        'train_count':len(run['split']['train']),'training_downscale':protocol['downscale_factor'],'iterations':30000,'seed':protocol['seed'],
        'background':[.1490,.1647,.2157],'gt_diagnostics':pixel_diagnostics,
        'comparison_scope':'Existing baseline prediction; canonical frozen RGB8 GT used in derivative common scores. Original metrics retained.'}


def score_model(root,record,cameras,destination):
    images=[{k:resolve(root,f[k]) for k in ('gt','pred')} for f in record['frames']]
    identity={'evaluator_id':EVALUATOR,'checkpoint_sha256':record['checkpoint_sha256'],
        'eval_camera_hash':digest_json(cameras),'frames':record['frames']}
    common=score_saved_images(images,identity,destination,4)
    return {**record,'metrics':common['metrics'],'per_view':common['frames'],
            'common':reference(root,destination),'evaluator_id':EVALUATOR}


def score_rois(root,record,boxes,directory):
    directory.mkdir(parents=True,exist_ok=True);images=[];refs=[]
    for i,(frame,box) in enumerate(zip(record['frames'],boxes)):
        row={}
        for kind in ('gt','pred'):
            target=directory/f'{kind}_{i:04d}.png'
            if not target.exists():
                with Image.open(resolve(root,frame[kind])) as image:
                    x,y,xx,yy=box
                    if not 0<=x<xx<=image.width or not 0<=y<yy<=image.height:raise ValueError('ROI outside canonical pixels')
                    image.convert('RGB').crop(box).save(target)
            row[kind]=target;refs.append(reference(root,target))
        images.append(row)
    if len(images)!=len(boxes) or len(images)!=len(record['frames']):raise ValueError('ROI camera count differs')
    common=score_saved_images(images,{'evaluator_id':EVALUATOR,'checkpoint_sha256':record['checkpoint_sha256'],
        'boxes':boxes,'cropped_files':refs},directory/'common.json',4)
    return {'metrics':common['metrics'],'per_view':common['frames'],'common':reference(root,directory/'common.json'),'files':refs}


def candidate_record(root,result_path,split):
    record=read_json(result_path);folder=result_path.parent
    if record['status']!='succeeded' or record['checkpoint']['step']!=30000:raise ValueError('Incomplete final candidate')
    checkpoint=folder/record['checkpoint']['path']
    if sha256(checkpoint)!=record['checkpoint']['sha256'] or sha256(folder/'model.ply')!=record['ply_sha256']:
        raise ValueError('Candidate checkpoint/export changed')
    frames=[]
    for f,camera in zip(record['frames'],split['eval']):
        row={}
        for kind in ('gt','pred'):
            path=folder/f[kind]
            if sha256(path)!=f[kind+'_sha256']:raise ValueError('Final candidate pixels changed')
            row[kind]=reference(root,path)
        with Image.open(folder/f['gt']) as image,Image.open(inside(root,camera['path'])) as source:
            if not np.array_equal(np.asarray(image.convert('RGB')),np.asarray(source.convert('RGB'))):raise ValueError('Candidate GT differs from canonical input')
        frames.append(row)
    if len(frames)!=len(split['eval']) or len(record['frames'])!=len(frames):raise ValueError('Candidate frame count differs')
    return {'id':'upgrade','label':'Selected Improved-GS','model':reference(root,folder/'model.ply'),
        'checkpoint_sha256':record['checkpoint']['sha256'],'config':reference(root,folder/'resolved-config.json'),
        'result':reference(root,result_path),'frames':frames,'gaussians':record['gaussians'],
        'training_seconds':record['training_seconds'],'optimizer_updates':record['checkpoint']['updates'],
        'peak_cuda_allocated_bytes':record['peak_cuda_allocated_bytes'],'offline_fps':record['offline_fps'],
        'setup_peak_cuda_bytes':record.get('setup_peak_cuda_bytes'),
        'train_count':len(split['train']),'training_downscale':split['downscale_factor'],'iterations':30000,'seed':42,
        'background':[0.,0.,0.],'comparison_scope':'Package intervention; same train/test/output and common evaluator. Historical runtime/peak scopes differ.'}
