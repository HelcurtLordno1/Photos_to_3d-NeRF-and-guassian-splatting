"""Tea Q0/Q1 experiment. Old studies and their immutable registries stay separate."""
from pathlib import Path
import copy
import os
import shutil
import time
import numpy as np
from PIL import Image,ImageDraw
from .contracts import (read_json,write_json,sha256,digest_json,inside,relative,
                        load_run,utc_now,native_workspace,validate_split,validate_export,validate_render)
from .settings import experiment_settings_hash
from .sessions import check_stop,SessionPaused
from .source_pin import activate,freeze_current,execution_sources,identity


def state_path(root,study):
    if study!='tea-quality-v2':raise ValueError('Only the approved Tea quality study is supported')
    return root/'artifacts/jobs/quality'/f'{study}.json'


def references(root,baseline):
    gate=read_json(root/'reports/full/custom-tea_sets_2/gate.json')
    if gate['status']!='passed':raise ValueError('Full Tea reference has not passed its gate')
    upgraded=next(r for r in gate['comparison'] if r['recipe']=='full-pool' and r['method']=='splatfacto')
    historical=next(r for r in gate['historical_common'] if r['method']=='splatfacto')
    return [('historical',baseline,inside(baseline,historical['config'])),
            ('half-control',root,root/'artifacts/runs'/upgraded['run_key']/'config.yml')]


def materialize_native(root,baseline,settings):
    """Take exact factor=1 cameras from the pinned parser, never infer from floor(W/2)."""
    from .data import freeze_split,scene_input
    from nerfstudio.data.dataparsers.nerfstudio_dataparser import NerfstudioDataParserConfig
    directory=scene_input(root,settings['VisualQuality']['Condition'])[0]
    _,owner,config=references(root,baseline)[1]
    parent=load_run(owner,config,require_eval=True)
    canonical=inside(root,parent['split']['train'][0]['path']).parent.parent
    source=read_json(canonical/'transforms.json')
    parser=NerfstudioDataParserConfig(data=native_workspace(root)/canonical.relative_to(root),
        downscale_factor=1,eval_mode='filename',auto_scale_poses=False,center_method='none',orientation_method='none').setup()
    split={'schema_version':'1.0','scene':settings['VisualQuality']['Condition'],'downscale_factor':1,'train':[],'eval':[]}
    source_refs=[]
    for label in ('train','eval'):
        outputs=parser.get_dataparser_outputs(split='train' if label=='train' else 'test')
        if len(outputs.image_filenames)!=len(parent['split'][label]):raise ValueError('Native image count changed')
        for index,(image,old) in enumerate(zip(outputs.image_filenames,parent['split'][label])):
            check_stop();image=inside(root,image)
            if image.name!=Path(old['path']).name:raise ValueError('Native split order differs')
            camera=outputs.cameras
            pose=camera.camera_to_worlds[index].numpy()
            if not np.allclose(pose,old['camera_to_world'],atol=1e-6,rtol=1e-6):raise ValueError('Native pose differs')
            frame={'path':relative(root,directory/'images'/image.name),'sha256':sha256(image),
                   'camera_to_world':pose.tolist(),'camera_type':int(camera.camera_type[index].item()),
                   'distortion_params':camera.distortion_params[index].tolist() if camera.distortion_params is not None else []}
            frame.update({k:float(getattr(camera,k)[index].item()) for k in ('fx','fy','cx','cy')})
            frame.update({k:int(getattr(camera,k)[index].item()) for k in ('width','height')})
            with Image.open(image) as pixels:
                if pixels.size!=(frame['width'],frame['height']):raise ValueError('Native GT dimensions differ')
            split[label].append(frame);source_refs.append({'source':relative(root,image),'sha256':frame['sha256'],'name':image.name})
    selection={'schema_version':'native-selection-1','parent_split_sha256':digest_json(parent['split']),
               'image_sources':source_refs,'scope':'Same 105/15 frame identities and canonical poses; exact native parser intrinsics'}
    selection_id=digest_json(selection)
    split['capture']={**parent['split']['capture'],'eval_camera_hash':digest_json(split['eval']),
                      'selection_id':selection_id,'native_sources':source_refs}
    if directory.exists():
        if read_json(directory/'selection.json')!=selection:raise ValueError('Native source inputs changed')
        saved=freeze_split(root,split['scene'],settings)
        if any(saved[k]!=split[k] for k in ('train','eval','capture')):raise ValueError('Native frozen cameras changed')
        return saved
    stage=directory.with_name(directory.name+'.staging-'+str(time.time_ns()))
    inside(root,stage).mkdir(parents=True);(stage/'images').mkdir()
    for item in source_refs:shutil.copyfile(inside(root,item['source']),stage/'images'/item['name'])
    shutil.copyfile(canonical/'sparse_pc.ply',stage/'sparse_pc.ply')
    write_json(stage/'transforms.json',source);write_json(stage/'selection.json',selection)
    split['pose_files']=[{'path':relative(root,directory/name),'sha256':sha256(stage/name)} for name in ('transforms.json','sparse_pc.ply')]
    validate_split(split);write_json(stage/'split.json',split);stage.rename(directory)
    return freeze_split(root,split['scene'],settings)


def audit(root,baseline,settings,split):
    """All train/test frames, CPU only. This is diagnosis, never model selection."""
    output=root/'reports/tea-quality-v2/q0';output.mkdir(parents=True,exist_ok=True)
    report=output/'audit.json'
    if report.exists():
        old=read_json(report)
        if old['native_split_hash']!=digest_json(split):raise ValueError('Q0 dataset changed')
        for item in old['references']:
            if sha256(inside(root,item['path']))!=item['sha256']:raise ValueError('Q0 evidence changed')
        return old
    rows=[]
    for label in ('train','eval'):
        for index,frame in enumerate(split[label]):
            check_stop()
            with Image.open(inside(root,frame['path'])) as image:
                a=np.asarray(image.convert('L').resize((180,320)),dtype=float)/255
            lap=-4*a[1:-1,1:-1]+a[:-2,1:-1]+a[2:,1:-1]+a[1:-1,:-2]+a[1:-1,2:]
            rows.append({'split':label,'index':index,'path':frame['path'],'sharpness_fixed_thumbnail':float(lap.var()),
                         'dark_fraction':float((a<.02).mean()),'bright_fraction':float((a>.98).mean())})
    sheet=Image.new('RGB',(5*180,3*350),'#eee');draw=ImageDraw.Draw(sheet)
    for index,frame in enumerate(split['eval']):
        with Image.open(inside(root,frame['path'])) as image:image=image.convert('RGB');image.thumbnail((180,320));sheet.paste(image,((index%5)*180,(index//5)*350+24))
        draw.text(((index%5)*180+6,(index//5)*350+5),f'GT #{index}',fill='black')
    sheet.save(output/'all-heldout-gt.jpg',quality=92)
    result={'status':'passed','native_split_hash':digest_json(split),'train_count':len(split['train']),'eval_count':len(split['eval']),
            'frames':rows,'scope':'CPU input integrity and fixed-size descriptive image statistics; no photometric/floater diagnosis claimed from sharpness alone',
            'references':[{'path':relative(root,output/'all-heldout-gt.jpg'),'sha256':sha256(output/'all-heldout-gt.jpg')}],
            'viewer_risk':'Classic checkpoint vs Spark default opacity-compensated blur; quantify before changing viewer',
            'finished_at':utc_now()}
    write_json(report,result);return result


def prepare(root,settings,baseline,study):
    from .preservation import verify_source
    from .runtime import runtime_snapshot,gpu_lock
    path=state_path(root,study);spec=settings['VisualQuality']
    if spec['Study']!=study or spec['DownscaleFactor']!=1 or spec['Iterations']!=30000:raise ValueError('Quality profile differs')
    verify_source(root,baseline)
    with gpu_lock(root,{'SharedGpuLock':settings['SharedGpuLock']}):
        split=materialize_native(root,baseline,settings);q0=audit(root,baseline,settings,split)
    if len(split['train'])!=105 or len(split['eval'])!=15:raise ValueError('Tea requires its original 105/15 split')
    from .quality_report import lock_rois
    roi_path=lock_rois(root,split)
    if shutil.disk_usage(root).free<settings['MinimumUpgradeFreeGiB']*2**30+10*2**30:raise ValueError('Quality study lacks disk reserve')
    if path.exists():
        record=read_json(path)
        if record['settings_hash']!=experiment_settings_hash(settings) or record['native_split_hash']!=digest_json(split) or record['roi_sha256']!=sha256(roi_path):raise ValueError('Quality declaration changed')
        activate(root,study)
        if identity(execution_sources(root)[1])!=record['source_id']:raise ValueError('Frozen quality source changed')
        return record
    pin=freeze_current(root,study);activate(root,study)
    record={'schema_version':'tea-quality-2','study':study,'status':'planned','phase':'q0-viewer-audit',
            'created_at':utc_now(),'settings_hash':experiment_settings_hash(settings),'native_split_hash':digest_json(split),
            'source_id':identity(execution_sources(root)[1]),'runtime_id':digest_json(runtime_snapshot()),
            'source_pin':relative(root,pin),'attempts':[],'config':None,'stages':{},'q2_status':'gated-after-q1','roi_sha256':sha256(roi_path),
            'scope':'Single-method native-resolution research, not Improved-GS reproduction and not an old full-campaign resume'}
    write_json(path,record);return record


def derivative(root,settings,owner,config,frames,tag):
    """Render any verified checkpoint at exact declared cameras; owner is read-only."""
    import torch
    from nerfstudio.cameras.cameras import Cameras
    from .runtime import gpu_lock,load_pipeline,close_pipeline,validate_loaded_split
    from .safety import current_guard
    from .evidence import score_saved_images,EVALUATOR
    run=load_run(owner,config,require_eval=True)
    output=root/'reports/tea-quality-v2/evaluation'/tag
    identity_record={'config_sha256':sha256(config),'checkpoint_sha256':sha256(run['checkpoint']),
                     'camera_hash':digest_json(frames),'evaluator_id':EVALUATOR,'runtime_id':run['provenance']['runtime_sha256']}
    report=output/'renders.json'
    if report.exists():
        saved=read_json(report)
        if saved['identity']!=identity_record:raise ValueError('Derivative identity changed')
        for frame in saved['frames']:
            for kind in ('gt','pred'):
                if sha256(output/frame[kind])!=frame[kind+'_sha256']:raise ValueError('Derivative image changed')
    else:
        output.mkdir(parents=True,exist_ok=True)
        with gpu_lock(root,settings):
            pipeline=None
            try:
                _,pipeline,_=load_pipeline(owner,run);validate_loaded_split(owner,run,pipeline)
                saved_frames=[]
                for index,frame in enumerate(frames):
                    check_stop()
                    camera=Cameras(camera_to_worlds=torch.tensor([frame['camera_to_world']],dtype=torch.float32),
                        **{k:frame[k] for k in ('width','height','fx','fy','cx','cy')}).to(pipeline.device)
                    with torch.no_grad():rgb=pipeline.model.get_outputs_for_camera(camera)['rgb']
                    Image.fromarray((rgb.clamp(0,1).detach().cpu().numpy()*255).round().astype('uint8')).save(output/f'pred_{index:04d}.png')
                    source=inside(root,frame['path'])
                    if sha256(source)!=frame['sha256']:raise ValueError('Derivative GT changed')
                    shutil.copyfile(source,output/f'gt_{index:04d}.png')
                    saved_frames.append({k:f'{k}_{index:04d}.png' for k in ('gt','pred')})
                    for k in ('gt','pred'):saved_frames[-1][k+'_sha256']=sha256(output/saved_frames[-1][k])
                saved={'status':'succeeded','identity':identity_record,'frames':saved_frames,
                       'gpu_safety_path':relative(root,current_guard().path),'finished_at':utc_now()}
                write_json(report,saved)
            finally:
                if pipeline is not None:close_pipeline(pipeline)
    metrics=score_saved_images([{k:output/f[k] for k in ('gt','pred')} for f in saved['frames']],identity_record,output/'common.json',settings['CpuWorkerThreads'])
    return {'tag':tag,'path':relative(root,output/'common.json'),'sha256':sha256(output/'common.json'),**metrics}


def execute(root,settings,baseline,study,resume=False):
    from .runtime import gpu_lock,train,evaluate,export,render
    from .data import freeze_split
    from .evidence import evaluate_common
    path=state_path(root,study);record=prepare(root,settings,baseline,study)
    if record['attempts'] and not resume:raise ValueError('Quality study has attempts; use Resume')
    with gpu_lock(root,{'SharedGpuLock':str(root/'artifacts/jobs/quality.lock')}):
        try:
            check_stop();record.update(status='running',updated_at=utc_now());write_json(path,record)
            split=freeze_split(root,settings['VisualQuality']['Condition'],settings)
            # Q0 browser measurements are verified before the first training iteration.
            from .quality_viewer import measure
            if not record['stages'].get('q0'):
                record['phase']='q0-renderer-measurement';write_json(path,record)
                result=measure(root,settings,baseline,split)
                record['stages']['q0']={'path':relative(root,result),'sha256':sha256(result)};write_json(path,record)
            else:
                q0=record['stages']['q0']
                if sha256(inside(root,q0['path']))!=q0['sha256']:raise ValueError('Q0 proof changed')
            check_stop();record['phase']='q1-native-training';write_json(path,record)
            config=inside(root,record['config']) if record.get('config') else None
            trained=False
            if config:
                logs=root/'artifacts/logs'/config.parent.relative_to(root/'artifacts/runs')
                trained=read_json(logs/'manifest.json')['status']=='succeeded'
                if trained:load_run(root,config)
            if not trained:
                spent=sum(a.get('wall_seconds',0) for a in record['attempts'])
                remaining=settings['VisualQuality']['MaximumExplorationGpuSeconds']-spent
                if remaining<=0:raise ValueError('Exploration training budget exhausted; review actual evidence')
                record['attempts'].append({'started_at':utc_now(),'parent_config':relative(root,config) if config else None})
                write_json(path,record)
                clock=time.monotonic();os.environ['TOPIC16_TRAIN_TIME_LIMIT']=str(remaining)
                try:
                    config=train(root,settings,'splatfacto',settings['VisualQuality']['Condition'],30000,42,'capture-native-30k-v2',config)
                finally:
                    os.environ.pop('TOPIC16_TRAIN_TIME_LIMIT',None)
                    record['attempts'][-1].update(wall_seconds=time.monotonic()-clock,finished_at=utc_now())
                    write_json(path,record)
                record['config']=relative(root,config);write_json(path,record)
            check_stop();record['phase']='q1-evaluation';write_json(path,record)
            evaluate(root,settings,config);evaluate_common(root,config)
            comparisons=[]
            # Evaluate identical checkpoint/camera/GT at native and original resolution.
            half=load_run(root,references(root,baseline)[1][2],require_eval=True)['split']['eval']
            for tag,owner,source in [*references(root,baseline),('native-candidate',root,config)]:
                for resolution,frames in [('native',split['eval']),('half',half)]:
                    comparisons.append(derivative(root,settings,owner,source,frames,tag+'-'+resolution))
            check_stop();record['phase']='q1-export-throughput';write_json(path,record)
            export(root,settings,config);timed=render(root,settings,config)
            from .quality_report import camera_tour
            tour=camera_tour(root,settings,config,split)
            from .quality_report import summarize
            report=summarize(root,settings,record,split,comparisons,timed,tour)
            record.update(status='succeeded',phase='q1-complete',finished_at=utc_now(),
                          report=relative(root,report),report_sha256=sha256(report),q2_status='awaiting-q1-visual-review')
            record.pop('error',None)
            record['updated_at']=utc_now()
            write_json(path,record);return record
        except BaseException as error:
            if isinstance(error,SessionPaused) and error.config:
                record['config']=relative(root,error.config)
            session=os.environ.get('TOPIC16_SESSION_DIRECTORY')
            if session and (Path(session)/'active-run.json').exists():
                active=read_json(Path(session)/'active-run.json')
                if active['run_key'].split('/')[0]==settings['VisualQuality']['Condition'].replace(':','-'):
                    record['config']=active['config']
            record.update(status='paused' if isinstance(error,SessionPaused) else 'failed',error=str(error),updated_at=utc_now())
            write_json(path,record);raise
