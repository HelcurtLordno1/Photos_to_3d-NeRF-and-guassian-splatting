"""Derivative ROI scores and traceable quality report, never overwrite old evidence."""
from pathlib import Path
import html
import numpy as np
from PIL import Image
from .contracts import read_json,write_json,inside,sha256,digest_json,relative,load_run
from .sessions import check_stop


def lock_rois(root,split):
    """Conservative GT-defined object boxes. Freeze before any candidate images exist."""
    path=root/'reports/tea-quality-v2/q0/rois.json'
    if not path.exists():raise ValueError('All-view GT ROI declaration must be committed before training')
    record=read_json(path)
    if record['native_eval_hash']!=digest_json(split['eval']) or len(record['boxes'])!=len(split['eval']):raise ValueError('ROI cameras differ')
    for box,frame in zip(record['boxes'],split['eval']):
        x,y,xx,yy=box
        if not 0<=x<xx<=frame['width'] or not 0<=y<yy<=frame['height']:raise ValueError('ROI outside GT')
    return path


def roi_scores(root,result,boxes):
    from .evidence import score_saved_images
    output=inside(root,result['path']).parent
    cropped=output/'roi';cropped.mkdir(exist_ok=True)
    frames=[]
    for i,box in enumerate(boxes):
        check_stop();row={}
        for kind in ('gt','pred'):
            path=cropped/f'{kind}_{i:04d}.png'
            with Image.open(output/f'{kind}_{i:04d}.png') as image:image.crop(box).save(path)
            row[kind]=path
        frames.append(row)
    return score_saved_images(frames,{**result['identity'],'roi_hash':digest_json(boxes)},cropped/'common.json')


def camera_tour(root,settings,config,split):
    """Render a capture-supported camera sweep, no invented unseen trajectory."""
    from .quality import derivative
    from .runtime import gpu_lock,run_command
    indices=np.linspace(0,len(split['train'])-1,30).round().astype(int).tolist()
    frames=[split['train'][i] for i in indices]
    rendered=derivative(root,settings,root,config,frames,'native-candidate-camera-sweep')
    directory=inside(root,rendered['path']).parent
    video=directory/'capture-sweep.mp4'
    # Odd native dimensions padded, never silently resize the benchmark frames.
    if not video.exists():
        with gpu_lock(root,{'SharedGpuLock':settings['SharedGpuLock']}):
            run_command(root,['ffmpeg','-y','-framerate','10','-i',str(directory/'pred_%04d.png'),
                '-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-threads',str(settings['CpuWorkerThreads']),
                '-pix_fmt','yuv420p',str(video)],directory/'ffmpeg.log')
    return {'path':relative(root,video),'sha256':sha256(video),'indices':indices,
            'scope':'30 actual capture train cameras; inspection sweep, not an independent held-out metric or interpolated orbit'}


def summarize(root,settings,state,split,comparisons,timed,tour):
    rois=read_json(lock_rois(root,split))
    scored=[]
    for result in comparisons:
        if result['tag'].endswith('-native'):
            roi=roi_scores(root,result,rois['boxes']);scored.append({**result,'roi_metrics':roi['metrics']})
        else:scored.append(result)
    native=next(r for r in scored if r['tag']=='native-candidate-native')
    control=next(r for r in scored if r['tag']=='half-control-native')
    delta={k:native['roi_metrics'][k]-control['roi_metrics'][k] for k in ('psnr','ssim','lpips')}
    record={'schema_version':'tea-native-quality-report-1','status':'evaluated','study':state['study'],
        'config':state['config'],'native_eval_hash':digest_json(split['eval']),'iterations':30000,'seed':42,
        'train_count':len(split['train']),'eval_count':len(split['eval']),
        'comparisons':scored,'roi_delta_vs_half_control_at_native':delta,
        'numeric_target_met':delta['psnr']>=1 and native['roi_metrics']['lpips']<=control['roi_metrics']['lpips']*.85,
        'training_wall_seconds_all_attempts':sum(a['wall_seconds'] for a in state['attempts']),
        'native_offline_throughput':timed['fps'],'camera_sweep':tour,
        'q2_status':'awaiting-visual-review','verdict':'Exploratory single-seed resolution intervention; inspect images before accepting quality or expanding research',
        'notes':['No Improved-GS run has been performed by Q1','No browser FPS or geometry ground truth claimed',
                 'Native and half scores must be compared within the same output resolution','ROI boxes contain some background; not segmentation masks']}
    output=root/'reports/tea-quality-v2';path=output/'report.json';write_json(path,record)
    lines=['# Tea Q1 — native-resolution Splatfacto','',record['verdict'],'',
           '| Checkpoint / output | PSNR | SSIM | LPIPS |','|---|---:|---:|---:|']
    lines += [f'| {r["tag"]} | {r["metrics"]["psnr"]:.4f} | {r["metrics"]["ssim"]:.5f} | {r["metrics"]["lpips"]:.5f} |' for r in scored]
    lines += ['',f'ROI delta vs half-resolution control at native output: {delta}',
              'ROI numeric target met: '+str(record['numeric_target_met']),
              f'All training attempts: {record["training_wall_seconds_all_attempts"]:.1f} s',
              'Q2: awaiting visual review. Old datasets remain paused.','',*record['notes']]
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Portable local image board; relative links preserve exact evidence files.
    rows=[]
    for i in range(15):
        paths=[f'evaluation/{tag}/pred_{i:04d}.png' for tag in ('historical-native','half-control-native','native-candidate-native')]
        rows.append('<tr><th>'+str(i)+'</th>'+''.join('<td><img loading="lazy" src="'+p+'" style="width:240px"></td>' for p in paths)+'</tr>')
    body='<meta charset="utf-8"><title>Tea Q1 image board</title><h1>Tea: same camera, native resolution</h1><p>'+html.escape(record['verdict'])+'</p><table><tr><th>View</th><th>Historical</th><th>30k half-trained control</th><th>30k native-trained candidate</th></tr>'+''.join(rows)+'</table>'
    (output/'images.html').write_text(body,encoding='utf-8')
    return path
