"""Tea selection first, then one selected model per remaining baseline scene."""
from pathlib import Path
import copy
import os
import shutil
import time
import zipfile
from .contracts import read_json,write_json,sha256,digest_json,inside,relative,utc_now,validate_split
from .sessions import check_stop,SessionPaused
from .source_pin import freeze_current,verify_pin,source_files,identity
from .final_stages import Stages
from .final_data import prepare_validation,materialize_scene
from .final_evidence import baseline_record,candidate_record,score_model,score_rois,reference,resolve


def validate_profile(spec):
    if (spec.get('SchemaVersion')!='single-winner-campaign-1' or spec.get('Study')!='final-quality-v1'
            or spec.get('Scenes')!=['bonsai','room','garden','poster']
            or spec.get('GaussianBudgets')!={'bonsai':1000000,'room':1000000,'garden':1200000,'poster':0}
            or spec.get('ValidationBudgets')!=[300000,450000] or spec.get('ValidationSeed')!=42
            or spec.get('ValidationViews')!=15 or spec.get('HighResolutionLongEdges')!=[3840,7680]):
        raise ValueError('Final campaign differs from the authorized fixed matrix')
    targets={'ConfirmationStudy':'tea-quality-v5','ReferenceStudy':'tea-research-v4',
        'MinimumRoiLpipsGain':.05,'MaximumValidationPsnrLoss':.2,'MaximumQualityPlyMiB':110,
        'MeanParityTargetDb':35,'MinimumViewParityDb':30,'MaximumQualityBrowserP95Ms':33.3,
        'MinimumTransferParityMeanDb':25,'MinimumTransferParityViewDb':20,
        'HighResolutionViews4k':3,'HighResolutionViews8k':1}
    if any(spec.get(k)!=v for k,v in targets.items()):raise ValueError('Final selection targets differ from the approved plan')
    if not 0<spec['MaximumCampaignSeconds']<=172800 or spec['MinimumFreeGiB']<70:raise ValueError('Final resource allowance differs')


def prepare(root,settings,study):
    from .preservation import verify_source
    from .capture import capture_split
    spec=settings['Final'];validate_profile(spec)
    if study!=spec['Study']:raise ValueError('Final study differs')
    verify_source(root,root.parent)
    directory=root/'artifacts/jobs/final'/study;directory.mkdir(parents=True,exist_ok=True);path=directory/'declaration.json'
    if path.exists():
        doc=read_json(path);state=read_json(directory/'state.json')
        if doc['spec']!=spec or sha256(path)!=state['declaration_sha256']:raise ValueError('Frozen final declaration changed')
        if sha256(inside(root,doc['source_pin']))!=doc['source_pin_sha256']:raise ValueError('Final source reference changed')
        verify_pin(root,inside(root,doc['source_pin']),study)
        for item in doc['validation'].values():
            if sha256(inside(root,item['path']))!=item['sha256']:raise ValueError('Frozen validation evidence changed')
        return state
    validation=prepare_validation(root);rois=validation.parent/'rois.json';boxes=read_json(rois)
    split=read_json(validation)
    if len(boxes['boxes'])!=15 or boxes['eval_frames_sha256']!=digest_json(split['eval']):raise ValueError('Validation ROI lock differs')
    for frame,box in zip(split['eval'],boxes['boxes']):
        x,y,xx,yy=box
        if not 0<=x<xx<=frame['width'] or not 0<=y<yy<=frame['height']:raise ValueError('Invalid validation ROI')
    if shutil.disk_usage(root).free<spec['MinimumFreeGiB']*2**30:raise ValueError('Final campaign disk reserve/remaining-model allowance not met')
    baselines=[]
    for scene in spec['Scenes']:
        frozen,provenance=capture_split(root.parent,scene)
        baselines.append({'scene':scene,'capture':provenance,'train_count':len(frozen['train']),
            'eval_count':len(frozen['eval']),'eval_camera_hash':digest_json(frozen['eval']),
            'output_sizes':sorted({(f['width'],f['height']) for f in frozen['eval']})})
    base=root/'artifacts/jobs/research'/spec['ReferenceStudy']/'declaration.json'
    pin=freeze_current(root,study)
    doc={'schema_version':'single-winner-declaration-1','study':study,'spec':spec,
        'source_pin':relative(root,pin),'source_pin_sha256':sha256(pin),'reference':reference(root,base),
        'validation':{name:reference(root,p) for name,p in [('split',validation),('rois',rois)]},
        'baselines':baselines,'approved_plan_sha256':sha256(root.parent/'docs/plans/final-quality-campaign.md'),
        'safety':{k:v for k,v in settings.items() if k.startswith('Gpu')},'created_at':utc_now(),
        'scope':'Tea controlled selection, one fixed-method upgrade per other scene, historical baselines retained; no SOTA claim'}
    write_json(path,doc)
    state={'study':study,'status':'planned','phase':'tea-confirmation','declaration_sha256':sha256(path),
        'stages':{},'stage_wall_seconds':0.,'scenes':[],'created_at':utc_now()}
    write_json(directory/'state.json',state);publish_index(root,directory,state);return state


def publish_index(root,directory,state):
    reports=[s['report'] for s in state['scenes'] if s['status']=='computed']
    write_json(root/'reports/final-index.json',{'schema_version':'final-ui-1','study':state['study'],
        'declaration':relative(root,directory/'declaration.json'),'declaration_sha256':sha256(directory/'declaration.json'),
        'state':relative(root,directory/'state.json'),'reports':reports})


def browser_audit(stages,label,model,split):
    from .inspection_worker import trajectory
    root=stages.root;key=label+'-browser'
    if stages.done(key):return read_json(inside(root,stages.state['stages'][key][0]['path']))
    target=root/'reports'/stages.state['study']/'browser'/label/str(time.time_ns());target.mkdir(parents=True)
    job={'ply':str(resolve(root,model['model'])),'native':[str(resolve(root,f['pred'])) for f in model['frames']],
        'cameras':split['eval'],'orbit':trajectory(split['train'],120),'output':str(target),'encoding':'packed-ext'}
    write_json(target/'job.json',job)
    sources=[root/'scripts/qa/audit-viewer.mjs',root.parent/'UI_design/qa/quality-audit.ts',
             root.parent/'UI_design/qa/quality-audit.html',root.parent/'UI_design/qa/tea-parity.ts']
    archive=target/'source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sources:z.write(p,relative(root.parent,p))
    proof={'files':[{'path':str(p),'sha256':sha256(p)} for p in sources],'archive_sha256':sha256(archive)}
    write_json(target/'source.json',proof)
    node=shutil.which('node.exe') or 'C:/Program Files/nodejs/node.exe'
    safety=stages.guarded(key,[node,str(root/'scripts/qa/audit-viewer.mjs'),str(target/'job.json')],target/'console.log')
    if any(sha256(p)!=r['sha256'] for p,r in zip(sources,proof['files'])):raise ValueError('Browser audit source changed during measurement')
    result=read_json(target/'browser-result.json')
    if len(result['results'])!=len(split['eval']):raise ValueError('Browser camera coverage incomplete')
    stages.commit(key,[target/'browser-result.json',target/'job.json',target/'source.json',archive,safety]+sorted(target.glob('spark-*.png')))
    return result


def browser_checks(result,spec):
    parity=[r['psnr'] for r in result['results']]
    return {'mean_parity_db':sum(parity)/len(parity),'minimum_parity_db':min(parity),
        'p95_frame_interval_ms':result['benchmark']['p95_frame_interval_ms'],
        'parity_met':sum(parity)/len(parity)>=spec['MeanParityTargetDb'] and min(parity)>=spec['MinimumViewParityDb'],
        'timing_met':result['benchmark']['p95_frame_interval_ms']<=spec['MaximumQualityBrowserP95Ms'],
        'encoding':'packed-ext','scope':'Native parity against CUDA; timing at1280x720,DPR1,SH3,LODoff. Not display scanout FPS.'}


def select_capacity(control,candidate,browser,ply_bytes,spec):
    checks={'roi_lpips':candidate['roi_metrics']['lpips']<=control['roi_metrics']['lpips']*(1-spec['MinimumRoiLpipsGain']),
        'psnr':candidate['metrics']['psnr']>=control['metrics']['psnr']-spec['MaximumValidationPsnrLoss'],
        'file_size':ply_bytes<=spec['MaximumQualityPlyMiB']*2**20,
        'browser_parity':browser['parity_met'],'browser_timing':browser['timing_met']}
    return {'chosen_budget':450000 if all(checks.values()) else 300000,'checks':checks,
        'scope':'Fixed TRAIN-derived validation; no selection using held-out Tea metrics. Both candidates and all failures retained.'}


def high_resolution(stages,scene,models,split):
    root=stages.root;key=scene.replace(':','-')+'-profiles'
    if stages.done(key):return reference(root,inside(root,stages.state['stages'][key][0]['path']))
    output=root/'reports'/stages.state['study']/'profiles'/scene.replace(':','-');output.mkdir(parents=True,exist_ok=True)
    job={'root':str(root),'output':relative(root,output),'cameras':split['eval'],'models':[]}
    for model in models:
        owner=model['model']['owner'];base=root.parent if owner=='baseline' else root
        job['models'].append({'id':model['id'],'owner':owner,'ply':model['model']['path'],
            'ply_sha256':model['model']['sha256'],'background':model['background'],
            'native':[{'path':relative(base,resolve(root,f['pred'])),'sha256':f['pred']['sha256']} for f in model['frames']]})
    path=output/'job.json'
    if path.exists() and read_json(path)!=job:raise ValueError('High-resolution render job changed')
    if not path.exists():write_json(path,job)
    base=read_json(resolve(root,read_json(stages.directory/'declaration.json')['reference']))
    command=[stages.host['conda'],'run','--no-capture-output','-n',base['spec']['EnvironmentName'],'python',
        str(stages.tree/'src/topic16_upgrade/final_render.py'),'--job',str(path)]
    safety=stages.guarded(key,command,output/('console-'+str(time.time_ns())+'.log'))
    report=output/'profiles.json';results=read_json(report)
    paths=[report,path,safety]
    for model in results['models']:
        for profile in model['profiles']:
            if profile['status']=='succeeded':
                image=inside(root,profile['path'])
                if sha256(image)!=profile['sha256']:raise ValueError('High-resolution profile image changed')
                paths.append(image)
    stages.commit(key,paths);return reference(root,report)


def publish_scene(stages,scene,result_path,split_path,budget):
    root=stages.root;key=scene.replace(':','-')+'-report';split=read_json(split_path)
    if stages.done(key):return reference(root,inside(root,stages.state['stages'][key][0]['path']))
    output=root/'reports'/stages.state['study']/'scenes'/scene.replace(':','-');output.mkdir(parents=True,exist_ok=True)
    old=score_model(root,baseline_record(root,scene,split),split['eval'],output/'baseline-common.json')
    new=score_model(root,candidate_record(root,result_path,split),split['eval'],output/'upgrade-common.json')
    browser=browser_audit(stages,scene.replace(':','-'),new,split)
    spec=read_json(stages.directory/'declaration.json')['spec'];summary=browser_checks(browser,spec)
    if summary['mean_parity_db']<spec['MinimumTransferParityMeanDb'] or summary['minimum_parity_db']<spec['MinimumTransferParityViewDb']:
        raise SessionPaused('Severe browser/CUDA mismatch; native computation retained. Inspect calibration/renderer before scene publication or further GPU work.')
    profiles=high_resolution(stages,scene,[old,new],split)
    delta={k:new['metrics'][k]-old['metrics'][k] for k in ('psnr','ssim','lpips')}
    per_view=[{'view':i,**{k:b[k]-a[k] for k in ('psnr','ssim','lpips')}} for i,(a,b) in enumerate(zip(old['per_view'],new['per_view']))]
    roi=None;roi_paths=[]
    training_safety=[]
    result_ref=relative(root,result_path)
    leaf_keys=[k for k,refs in stages.state['stages'].items() if k.endswith('-full') and any(r['path']==result_ref for r in refs)]
    safety_refs=[]
    for key_leaf in leaf_keys:
        prefix=key_leaf[:-5]
        for attempt in stages.state.get('attempts',[]):
            if attempt['key'] in (key_leaf,prefix+'-probe'):safety_refs.append(reference(root,inside(root,attempt['safety'])))
    if not leaf_keys and scene=='custom:tea_sets_2':
        historical=read_json(root/'artifacts/jobs/research/tea-research-v4/state.json')
        safety_refs += [dict(r,owner='upgrade') for r in historical['stages']['full-improvedgs']['references'] if r['path'].startswith('artifacts/logs/safety/')]
    for ref_safety in safety_refs:
        measured=read_json(resolve(root,ref_safety));training_safety.append({'reference':ref_safety,
            'status':measured['status'],'first_sample':measured.get('first_sample'),'last_sample':measured.get('last_sample'),
            'observed_peaks':measured.get('observed_peaks')})
    if scene=='custom:tea_sets_2':
        roi_path=root/'reports/tea-quality-v2/q0/rois.json';locked=read_json(roi_path)
        if locked['native_eval_hash']!=digest_json(split['eval']):raise ValueError('Original Tea ROI cameras differ')
        roi={kind:score_rois(root,model,locked['boxes'],output/'roi'/kind) for kind,model in [('baseline',old),('upgrade',new)]}
        roi['lock']=reference(root,roi_path)
        for kind in ('baseline','upgrade'):
            roi_paths += [resolve(root,roi[kind]['common'])]+[resolve(root,r) for r in roi[kind]['files']]
        original=next(r for r in read_json(root/'reports/tea-quality-v2/report.json')['comparisons'] if r['tag']=='half-control-native')
        roi['original_target_met']=(roi['upgrade']['metrics']['psnr']>=original['roi_metrics']['psnr']+1
            and roi['upgrade']['metrics']['lpips']<=original['roi_metrics']['lpips']*.85
            and new['metrics']['psnr']>=original['metrics']['psnr'])
    report={'schema_version':'final-scene-1','status':'computed','scene':scene,'campaign':stages.state['study'],
        'split':reference(root,split_path),'cameras':split['eval'],'train_count':len(split['train']),'eval_count':len(split['eval']),
        'gaussian_budget':budget,'baseline':old,'upgrade':new,'delta':delta,'per_view_delta':per_view,
        'browser':summary,'browser_result':reference(root,inside(root,stages.state['stages'][scene.replace(':','-')+'-browser'][0]['path'])),
        'profiles':profiles,'quality_dominates':delta['psnr']>=0 and delta['ssim']>=0 and delta['lpips']<=0,
        'roi':roi,
        'training_safety':training_safety,
        'preview_verdict':'measured-parity' if summary['parity_met'] else 'approximate-preview-parity-miss',
        'scope':'One selected upgrade vs preserved baseline; same canonical GT/output. Report negative views, historical runtime differences and Tea training-resolution intervention. MU changes optimizer update count; no same-compute/update claim.',
        'roi_scope':'Tea selection uses locked validation ROI; no post-hoc ROI metric is fabricated for other scenes.',
        'finished_at':utc_now()}
    write_json(output/'report.json',report)
    lines=['# '+scene+' — preserved baseline vs selected upgrade','',report['scope'],'',
        '|Model|PSNR|SSIM|LPIPS|Train seconds|','|---|---:|---:|---:|---:|']
    for model in (old,new):lines.append('|'+model['label']+'|'+ '|'.join(f'{model["metrics"][k]:.6f}' for k in ('psnr','ssim','lpips'))+'|'+f'{model["training_seconds"]:.2f}'+'|')
    lines+=['','Delta upgrade-baseline: '+str(delta), 'Browser: '+str(summary),
        'All three mean quality metrics favourable: '+str(report['quality_dominates']),
        'Per-view losses are retained in report.json. Historical peak device residency and current CUDA allocator are different scopes.',
        'Large output profiles have no GT metrics and do not imply new captured detail.',report['roi_scope']]
    (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    from .final_report import scene_tables
    tabular=scene_tables(output,report)
    stages.commit(key,[output/'report.json',output/'report.md',output/'baseline-common.json',output/'upgrade-common.json']+roi_paths+tabular)
    return reference(root,output/'report.json')


def execute(root,settings,study,resume=False):
    from .runtime import gpu_lock
    state=prepare(root,settings,study);directory=root/'artifacts/jobs/final'/study;doc=read_json(directory/'declaration.json')
    if state['status']=='succeeded':return state
    if not os.environ.get('TOPIC16_SESSION_DIRECTORY'):raise ValueError('Use a native managed final session')
    if state['status']!='planned' and not resume:raise ValueError('Final campaign already started; use Resume')
    _,tree=verify_pin(root,inside(root,doc['source_pin']),study);stages=Stages(root,settings,directory,state,tree)
    files=source_files(root);controller_id=identity(files);archive=directory/'controllers'/controller_id/'source.zip'
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for name in files:z.write(root/name,name)
    controller={'source_id':controller_id,'archive':relative(root,archive),'sha256':sha256(archive)}
    if controller not in state.setdefault('controllers',[]):state['controllers'].append(controller)
    for key in list(state['stages']):stages.done(key)
    base=read_json(resolve(root,doc['reference']));spec=doc['spec'];output=root/'reports'/study;output.mkdir(parents=True,exist_ok=True)
    with gpu_lock(root,{'SharedGpuLock':str(root/'artifacts/jobs/final.lock')}):
        try:
            if not stages.done('component-preflight'):
                target=output/'component-preflight'/str(time.time_ns());target.mkdir(parents=True)
                snapshot=target/'catalog.json';shutil.copyfile(root.parent/'artifacts/ui/catalog.json',snapshot)
                job=target/'job.json';write_json(job,{'catalog':str(snapshot),'baseline':str(root.parent),'output':str(target)})
                sources=[root/'scripts/qa/check-final-component.mjs',root.parent/'UI_design/qa/final-component.html',
                    root.parent/'UI_design/qa/final-component.ts',root.parent/'UI_design/frontend/FinalQuality.tsx',
                    root.parent/'UI_design/frontend/Viewer.tsx',root.parent/'UI_design/frontend/types.ts']
                archive=target/'source.zip'
                with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
                    for p in sources:z.write(p,relative(root.parent,p))
                node=shutil.which('node.exe') or 'C:/Program Files/nodejs/node.exe'
                safety=stages.guarded('component-preflight',[node,str(root/'scripts/qa/check-final-component.mjs'),str(job)],target/'console.log')
                if read_json(target/'component-check.json')['status']!='passed':raise ValueError('Existing-artifact component integration failed')
                stages.commit('component-preflight',[target/'component-check.json',target/'component.png',snapshot,job,archive,safety])
            # Exercise the actual large-buffer renderer with already completed
            # Tea weights before entrusting it to overnight scene publication.
            # This is integration QA, never a new training/quality result.
            if not stages.done('qa-existing-tea-profiles'):
                existing_split=read_json(inside(root,base['split']))
                existing=next(r for r in read_json(root/'reports'/spec['ReferenceStudy']/'report.json')['rows'] if r['method']=='improvedgs')
                models=[baseline_record(root,'custom:tea_sets_2',existing_split),
                    candidate_record(root,inside(root,existing['result']),existing_split)]
                profiles=high_resolution(stages,'qa-existing-tea',models,existing_split)
                stages.commit('qa-existing-tea-profiles',[resolve(root,profiles)])
            stages.save('tea-confirmation')
            from .confirmation import execute as confirm
            clock=time.monotonic()
            try:confirmed=confirm(root,settings,spec['ConfirmationStudy'],resume=True)
            finally:state['stage_wall_seconds']+=time.monotonic()-clock;stages.save()
            proof=root/'reports'/spec['ConfirmationStudy']/'report.json';confirmation=read_json(proof)
            if not confirmation['signal_gate_met']:raise SessionPaused('Tea replication signal gate failed; no scene expansion or hidden tuning')
            stages.commit('tea-confirmation',[proof])
            validation=resolve(root,doc['validation']['split']);split=read_json(validation);boxes=read_json(resolve(root,doc['validation']['rois']))['boxes']
            choice_path=output/'capacity-selection.json'
            if not stages.done('capacity-selection'):
                candidates=[]
                for budget in spec['ValidationBudgets']:
                    check_stop();label='tea-val-'+str(budget)
                    result=stages.leaf(label,validation,budget,base['spec']);model=candidate_record(root,result,split)
                    scored=score_model(root,model,split['eval'],result.parent/'common.json')
                    from .quality_report import roi_scores
                    common=read_json(result.parent/'common.json')
                    roi=roi_scores(root,{'path':relative(root,result.parent/'common.json'),'identity':common['identity']},boxes)
                    candidates.append({**scored,'roi_metrics':roi['metrics'],'result':reference(root,result)})
                browser=browser_audit(stages,'tea-val-450000',candidates[1],split)
                summary=browser_checks(browser,spec)
                selection=select_capacity(candidates[0],candidates[1],summary,resolve(root,candidates[1]['model']).stat().st_size,spec)
                selection.update(candidates=candidates,browser=summary,validation=doc['validation'],finished_at=utc_now())
                roi_files=[p for m in candidates for p in resolve(root,m['result']).parent.joinpath('roi').glob('*.png')]
                roi_common=[resolve(root,m['result']).parent/'roi/common.json' for m in candidates]
                write_json(choice_path,selection);stages.commit('capacity-selection',[choice_path]+[resolve(root,m['common']) for m in candidates]+roi_common+roi_files)
            selection=read_json(choice_path);budget=selection['chosen_budget']
            native=inside(root,base['split'])
            if budget==450000:tea=stages.leaf('tea-selected-full',native,budget,base['spec'])
            else:tea=inside(root,next(r for r in read_json(root/'reports'/spec['ReferenceStudy']/'report.json')['rows'] if r['method']=='improvedgs')['result'])
            queue=[('custom:tea_sets_2',tea,native,budget)]+[(s,None,None,spec['GaussianBudgets'][s] or budget) for s in spec['Scenes']]
            for scene,result,split_path,count in queue:
                check_stop();stages.save('scene-'+scene.replace(':','-'))
                saved=next((s for s in state['scenes'] if s['scene']==scene),None)
                if saved and saved['status']=='computed':
                    resolve(root,saved['report'])
                    from .full import prepare_catalog
                    catalog=prepare_catalog(root,root.parent,output/('catalog-'+scene.replace(':','-')+'.log'))
                    if scene not in [s['scene'] for s in catalog.get('final_delivery',{}).get('scenes',[])]:
                        raise RuntimeError('Completed scene requires valid UI publication before further GPU work')
                    continue
                if split_path is None:
                    split_path=materialize_scene(root,root.parent,scene,study)
                    # Validate historical camera/pixel compatibility BEFORE GPU.
                    baseline_record(root,scene,read_json(split_path))
                    result=stages.leaf(scene,split_path,count,base['spec'],probe=True)
                report=publish_scene(stages,scene,result,split_path,count)
                item={'scene':scene,'status':'computed','report':report}
                if saved:state['scenes'].remove(saved)
                state['scenes'].append(item);stages.save();publish_index(root,directory,state)
                from .full import prepare_catalog
                catalog=prepare_catalog(root,root.parent,output/('catalog-'+scene.replace(':','-')+'.log'))
                if scene not in [s['scene'] for s in catalog.get('final_delivery',{}).get('scenes',[])]:
                    raise RuntimeError('Scene computed; UI publication did not validate. Resume must retry publication, not training.')
            reports=[read_json(resolve(root,s['report'])) for s in state['scenes']]
            document={'schema_version':'final-campaign-report-1','status':'computed-awaiting-ui','study':study,
                'capacity_selection':reference(root,choice_path),'tea_confirmation':reference(root,proof),
                'scenes':[s['report'] for s in state['scenes']],
                'summary':[{'scene':r['scene'],'delta':r['delta'],'quality_dominates':r['quality_dominates'],
                    'browser':r['browser'],'gaussian_budget':r['gaussian_budget']} for r in reports],
                'stage_wall_seconds':state['stage_wall_seconds'],'attempts':state.get('attempts',[]),
                'original_baseline_results':reference(root,root.parent/'reports/topic16-full/results.csv','baseline'),
                'scope':'No best-seed selection, no new baseline training, no SOTA claim. Reports retain negative quality/browser/profile results.',
                'finished_compute_at':utc_now()}
            if not stages.done('campaign-report'):
                from .final_report import campaign_tables
                tabular=campaign_tables(output,document,reports,selection,confirmation)
                write_json(output/'report.json',document);stages.commit('campaign-report',[output/'report.json']+tabular)
            state.update(status='computed',phase='awaiting-ui',finished_compute_at=utc_now());stages.save();publish_index(root,directory,state);return state
        except BaseException as error:
            state.update(status='paused' if isinstance(error,SessionPaused) else 'failed',error=str(error),updated_at=utc_now());stages.save();raise
