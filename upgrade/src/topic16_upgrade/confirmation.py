"""Declared inference audit and paired-seed confirmation, preserving trained v4."""
from pathlib import Path
import copy
import os
import shutil
import time
import zipfile
import threading
from .contracts import read_json,write_json,inside,relative,sha256,digest_json,utc_now
from .sessions import check_stop,SessionPaused
from .source_pin import freeze_current,verify_pin,source_files,identity


def validate_profile(spec):
    if spec.get('SchemaVersion')!='quality-confirmation-1':raise ValueError('Unsupported confirmation schema')
    if spec['Seeds']!=[17,2026]:raise ValueError('Only the approved two new seeds are declared')
    if spec['MaximumGpuSeconds']>10800 or spec['MaximumGpuSeconds']<=0:raise ValueError('Invalid confirmation budget')
    if spec['OrbitFrames']!=120 or spec['ReferenceStudy']!='tea-research-v4':raise ValueError('Audit reference/matrix differs')


def immutable_inspection(root,state,key,path,document):
    """Resuming must reuse committed bytes, including their original timestamp."""
    if key in state['stages']:
        refs=state['stages'][key]
        if not refs or inside(root,refs[0]['path'])!=path:raise ValueError('Inspection stage path differs')
        for ref in refs:
            if sha256(inside(root,ref['path']))!=ref['sha256']:raise ValueError('Committed inspection changed')
        return read_json(path)
    write_json(path,document)
    return document


def validate_review(root,review,inspection_path):
    if review.get('status')!='passed' or review.get('inspection_sha256')!=sha256(inspection_path):
        raise SessionPaused('Visual review proof does not match the current inspection')
    refs=[review.get('ui_check',{})]+review.get('references',[])
    if len(refs)<2:raise SessionPaused('Visual review lacks UI and inspection evidence')
    for ref in refs:
        if not ref.get('path') or sha256(inside(root,ref['path']))!=ref.get('sha256'):
            raise ValueError('Visual review evidence changed')
    ui=read_json(inside(root,refs[0]['path']))
    if (ui.get('status')!='passed' or not ui.get('idle') or ui['idle']['before']!=ui['idle']['after']
            or not ui.get('load')):raise SessionPaused('Full UI load/idle/interaction proof required')


def prepare(root,settings,study):
    from .preservation import verify_source
    spec=settings['Confirmation'];validate_profile(spec)
    if study!=spec['Study']:raise ValueError('Confirmation study differs')
    verify_source(root,Path(settings['BaselineRoot']))
    base=root/'artifacts/jobs/research'/spec['ReferenceStudy'];reference=read_json(base/'state.json')
    if reference['status']!='succeeded':raise ValueError('Reference pair has not completed')
    declaration=read_json(base/'declaration.json')
    if sha256(base/'declaration.json')!=reference['declaration_sha256']:raise ValueError('Reference declaration changed')
    for stage in reference['stages'].values():
        for ref in stage['references']:
            if sha256(inside(root,ref['path']))!=ref['sha256']:raise ValueError('Reference evidence changed')
    verify_pin(root,inside(root,declaration['source_pin']))
    directory=root/'artifacts/jobs/confirmation'/study;directory.mkdir(parents=True,exist_ok=True)
    path=directory/'declaration.json'
    def publish_pointer():
        stages=read_json(directory/'state.json').get('stages',{})
        active=stages.get('inspection-repair-r4') or stages.get('inspection-repair-r3') or stages.get('inspection-repair')
        write_json(root/'reports/confirmation-index.json',{'schema_version':'confirmation-ui-1','study':study,
            'declaration':relative(root,path),'declaration_sha256':sha256(path),'state':relative(root,directory/'state.json'),
            'inspection':active[0]['path'] if active else relative(root,root/'reports'/study/'inspection.json'),
            'report':relative(root,root/'reports'/study/'report.json')})
    if path.exists():
        saved=read_json(path)
        if saved['spec']!=spec or saved['reference_declaration_sha256']!=sha256(base/'declaration.json'):
            raise ValueError('Confirmation protocol changed')
        current=read_json(directory/'state.json')
        if sha256(path)!=current['declaration_sha256']:raise ValueError('Confirmation declaration bytes changed')
        publish_pointer();return current
    if shutil.disk_usage(root).free<spec['MinimumFreeGiB']*2**30:raise ValueError('Insufficient confirmation disk reserve')
    document={'schema_version':'confirmation-declaration-1','study':study,'spec':spec,
              'reference_declaration':relative(root,base/'declaration.json'),'reference_declaration_sha256':sha256(base/'declaration.json'),
              'created_at':utc_now(),'scope':'P0/P1/P2 approval; later interventions require measured gates and their own declarations',
              'approved_plan_sha256':sha256(root.parent/'docs/plans/tea-quality-v5.md')}
    write_json(path,document)
    state={'study':study,'status':'planned','phase':'inspection','stages':{},'gpu_stage_wall_seconds':0.,
           'declaration_sha256':sha256(path),'created_at':utc_now(),'jobs':[]}
    for seed in spec['Seeds']:
        state['jobs'].append({'seed':seed,'study':study+'-seed'+str(seed),'status':'queued'})
    write_json(directory/'state.json',state);publish_pointer();return state


def execute(root,settings,study,resume=False):
    from .runtime import gpu_lock,run_command
    from .safety import current_guard
    from .evidence import score_saved_images,EVALUATOR
    from .quality import references
    from .contracts import load_run
    from .inspection_worker import trajectory
    directory=root/'artifacts/jobs/confirmation'/study;state=prepare(root,settings,study)
    declaration=read_json(directory/'declaration.json');spec=declaration['spec']
    if state['status']=='succeeded':return state
    if not os.environ.get('TOPIC16_SESSION_DIRECTORY'):
        raise ValueError('Use Manage-Session -Task confirmation so the shared budget can checkpoint and stop safely')
    if state['status']!='planned' and not resume:raise ValueError('Confirmation has started; use Resume')
    base=read_json(inside(root,declaration['reference_declaration']));base_report=read_json(root/'reports'/spec['ReferenceStudy']/'report.json')
    split=read_json(inside(root,base['split']))
    half=load_run(root,references(root,root.parent)[1][2],require_eval=True)['split']['eval']
    output=root/'reports'/study;output.mkdir(parents=True,exist_ok=True)
    host=read_json(root/'artifacts/logs/host.json')
    files=source_files(root);sid=identity(files)
    archive=directory/'controllers'/sid/'source.zip';archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for name in files:z.write(root/name,name)
    controller={'source_id':sid,'archive':relative(root,archive),'sha256':sha256(archive)}
    if controller not in state.setdefault('controllers',[]):state['controllers'].append(controller)
    def save(phase):
        state.update(status='running',phase=phase,updated_at=utc_now());state.pop('error',None);write_json(directory/'state.json',state)
    def complete(key):
        if key not in state['stages']:return False
        for ref in state['stages'][key]:
            if sha256(inside(root,ref['path']))!=ref['sha256']:raise ValueError('Confirmation completed evidence changed')
        return True
    def stage(key,paths):
        state['stages'][key]=[{'path':relative(root,p),'sha256':sha256(p)} for p in paths];write_json(directory/'state.json',state)
    def guarded(command,log):
        check_stop()
        if state['gpu_stage_wall_seconds']>=spec['MaximumGpuSeconds']:raise SessionPaused('Confirmation GPU budget exhausted')
        clock=time.monotonic()
        try:
            with gpu_lock(root,settings):
                safety=current_guard().path
                run_command(root,command,log,environment_overrides={'MKL_THREADING_LAYER':'SEQUENTIAL'})
        finally:
            state['gpu_stage_wall_seconds']+=time.monotonic()-clock;write_json(directory/'state.json',state)
        return safety
    with gpu_lock(root,{'SharedGpuLock':str(root/'artifacts/jobs/confirmation.lock')}):
        try:
            pin=freeze_current(root,study+'-inspection-'+sid[:12]);_,tree=verify_pin(root,pin)
            results=[]
            for row in base_report['rows']:
                method=row['method'];key='inspect-'+method;save(key)
                if not complete(key):
                    target=output/'inspection'/sid[:12]/method;target.mkdir(parents=True,exist_ok=True)
                    job=target/'job.json'
                    write_json(job,{'root':str(root),'method':method,'result':row['result'],'result_sha256':row['result_sha256'],
                                    'runtime':relative(root,root/'artifacts/jobs/research'/spec['ReferenceStudy']/'runtime.json'),
                                    'output':relative(root,target),'native':split['eval'],'half':half,'train':split['train']})
                    command=[host['conda'],'run','--no-capture-output','-n',base['spec']['EnvironmentName'],'python',
                             str(tree/'src/topic16_upgrade/inspection_worker.py'),'--job',str(job)]
                    safety=guarded(command,target/'console.log');audit=read_json(target/'result.json')
                    for item in audit['ancillary']:
                        if sha256(inside(root,item['path']))!=item['sha256']:raise ValueError('Audit auxiliary image changed')
                    stage(key,[target/'result.json',safety])
                audit=read_json(inside(root,state['stages'][key][0]['path']));scored=[]
                for cell in audit['rows']:
                    path=inside(root,cell['path']);rendered=read_json(path)
                    if sha256(path)!=cell['sha256']:raise ValueError('Scale cell changed')
                    for f in rendered['frames']:
                        for kind in ('gt','pred'):
                            if sha256(path.parent/f[kind])!=f[kind+'_sha256']:raise ValueError('Scale pixels changed')
                    common=score_saved_images([{k:path.parent/f[k] for k in ('gt','pred')} for f in rendered['frames']],
                                             {**rendered['identity'],'evaluator_id':EVALUATOR},path.parent/'common.json',4)
                    scored.append({**cell,'metrics':common['metrics'],'common':relative(root,path.parent/'common.json'),
                                   'common_sha256':sha256(path.parent/'common.json')})
                orbit=inside(root,audit['orbit']);video=orbit/'orbit.mp4'
                if not video.exists():
                    run_command(root,['ffmpeg','-y','-framerate','24','-i',str(orbit/'pred_%04d.png'),'-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2',
                                      '-c:v','libx264','-threads','4','-pix_fmt','yuv420p',str(video)],orbit/'ffmpeg.log')
                key_browser='browser-'+method;save(key_browser)
                if not complete(key_browser):
                    target=inside(root,state['stages']['inspect-'+method][0]['path']).parent
                    result=read_json(inside(root,row['result']));parent=inside(root,row['result']).parent
                    job=target/'browser-job.json';write_json(job,{'ply':str(parent/'model.ply'),'native':[str(parent/f'pred_{i:04d}.png') for i in range(15)],
                        'cameras':split['eval'],'orbit':read_json(orbit/'cameras.json')['frames'],'output':str(target)})
                    node=shutil.which('node.exe') or 'C:/Program Files/nodejs/node.exe'
                    sources=[root/'scripts/qa/audit-viewer.mjs',root.parent/'UI_design/qa/quality-audit.ts',root.parent/'UI_design/qa/quality-audit.html',root.parent/'UI_design/qa/tea-parity.ts']
                    source_archive=target/'browser-source.zip'
                    with zipfile.ZipFile(source_archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                        for p in sources:z.write(p,relative(root.parent,p))
                    source_proof=target/'browser-source.json';write_json(source_proof,{'files':[{'path':str(p),'sha256':sha256(p)} for p in sources],
                         'archive':relative(root,source_archive),'archive_sha256':sha256(source_archive)})
                    safety=guarded([node,str(root/'scripts/qa/audit-viewer.mjs'),str(job)],target/'browser.log')
                    if any(sha256(p)!=r['sha256'] for p,r in zip(sources,read_json(source_proof)['files'])):raise ValueError('Browser audit source changed during measurement')
                    stage(key_browser,[target/'browser-result.json',safety,source_proof,source_archive])
                browser=read_json(inside(root,state['stages'][key_browser][0]['path']))
                results.append({'method':method,'cells':scored,'browser':browser,'orbit':relative(root,video),'orbit_sha256':sha256(video)})
            q1=read_json(root/'reports/tea-quality-v2/report.json');chosen=next(r for r in results if r['method']=='improvedgs')
            gate_checks={}
            for resolution in ('native','half'):
                candidate=next(c for c in chosen['cells'] if c['resolution']==resolution and c['variant']=='direct')['metrics']
                control=next(r for r in q1['comparisons'] if r['tag']=='native-candidate-'+resolution)['metrics']
                gate_checks[resolution]=(candidate['psnr']>=control['psnr']-spec['MaximumPsnrLossVsQ1']
                                           and candidate['lpips']<=control['lpips']*spec['MaximumLpipsRatioVsQ1'])
            parity=[r['psnr'] for r in chosen['browser']['results']]
            gate_checks['packed_parity']=sum(parity)/len(parity)>=spec['MeanParityTargetDb'] and min(parity)>=spec['MinimumViewParityDb']
            gate_checks['browser_p95']=chosen['browser']['benchmark']['p95_frame_interval_ms']<=spec['MaximumBrowserP95Ms']
            inspection={'status':'passed' if all(gate_checks.values()) else 'gate-not-met','checks':gate_checks,'results':results,
                        'scope':'GT metrics at locked native/half only. Zoom/orbit have no GT; no temporal quality claim.',
                        'finished_at':utc_now()}
            inspection_path=output/'inspection.json'
            inspection=immutable_inspection(root,state,'inspection-report',inspection_path,inspection)
            if not complete('inspection-report'):stage('inspection-report',[inspection_path])
            # A failed packed audit is immutable. Diagnose representation precision
            # on the same weights/cameras, with the same frozen numerical targets.
            if not inspection['checks']['packed_parity']:
                for repair_version,encoding in ((2,'ext32'),(3,'ext32-full'),(4,'packed-ext')):
                    if inspection['status']=='passed':break
                    amendment=output/('renderer-repair-r'+str(repair_version)+'.json') if repair_version>2 else output/'renderer-repair.json'
                    if not amendment.exists():
                        write_json(amendment,{'schema_version':'renderer-repair-1','original_inspection_sha256':sha256(output/'inspection.json'),
                            'hypothesis':'Packed center/shape quantization may explain browser/CUDA mismatch. Isolate extended representation.',
                            'intervention':encoding+' replaces packed in BOTH audited methods; same weights, SH3, classic filter, cameras, sorting and viewport. Full mode extends input and render accumulator; packed-ext isolates accumulator precision while retaining packed input. This completes the 2x2 source/accumulator precision diagnosis.',
                            'targets':{k:spec[k] for k in ('MeanParityTargetDb','MinimumViewParityDb','MaximumBrowserP95Ms')},
                            'decision':'Adopt as the explicit research viewer profile only if all unchanged targets pass. Preserve packed failures.',
                            'created_at':utc_now()})
                    repaired=[]
                    for row in results:
                        method=row['method'];key='browser-'+encoding+'-'+method;save(key)
                        if not complete(key):
                            original=inside(root,state['stages']['browser-'+method][0]['path']).parent
                            target=output/'inspection'/sid[:12]/method/encoding;target.mkdir(parents=True,exist_ok=True)
                            job=read_json(original/'browser-job.json');job.update(output=str(target),encoding=encoding)
                            write_json(target/'browser-job.json',job)
                            sources=[root/'scripts/qa/audit-viewer.mjs',root.parent/'UI_design/qa/quality-audit.ts',root.parent/'UI_design/qa/quality-audit.html',root.parent/'UI_design/qa/tea-parity.ts']
                            archive=target/'browser-source.zip'
                            if not archive.exists():
                                with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
                                    for p in sources:z.write(p,relative(root.parent,p))
                            proof=target/'browser-source.json';write_json(proof,{'files':[{'path':str(p),'sha256':sha256(p)} for p in sources],
                                'archive':relative(root,archive),'archive_sha256':sha256(archive)})
                            node=shutil.which('node.exe') or 'C:/Program Files/nodejs/node.exe'
                            safety=guarded([node,str(root/'scripts/qa/audit-viewer.mjs'),str(target/'browser-job.json')],target/'browser.log')
                            if any(sha256(p)!=r['sha256'] for p,r in zip(sources,read_json(proof)['files'])):raise ValueError('Repair audit source changed')
                            stage(key,[target/'browser-result.json',safety,proof,archive,amendment])
                        repaired.append({**row,'browser':read_json(inside(root,state['stages'][key][0]['path']))})
                    selected=next(r for r in repaired if r['method']=='improvedgs')['browser'];parity=[r['psnr'] for r in selected['results']]
                    gate_checks={k:inspection['checks'][k] for k in ('native','half')}
                    gate_checks.update(renderer_parity=sum(parity)/len(parity)>=spec['MeanParityTargetDb'] and min(parity)>=spec['MinimumViewParityDb'],
                        browser_p95=selected['benchmark']['p95_frame_interval_ms']<=spec['MaximumBrowserP95Ms'])
                    inspection_path=output/('inspection-r'+str(repair_version)+'.json');repair_key='inspection-repair'+('-r'+str(repair_version) if repair_version>2 else '')
                    document={'status':'passed' if all(gate_checks.values()) else 'gate-not-met','checks':gate_checks,'results':repaired,
                            'viewer_encoding':encoding,'original_packed_inspection':relative(root,output/'inspection.json'),
                            'original_packed_inspection_sha256':sha256(output/'inspection.json'),'amendment_sha256':sha256(amendment),
                            'scope':'Explicit inference representation repair, unchanged checkpoints/targets. Packed parity failure remains valid.',
                            'finished_at':utc_now()}
                    inspection=immutable_inspection(root,state,repair_key,inspection_path,document)
                    if not complete(repair_key):stage(repair_key,[inspection_path,amendment])
                prepare(root,settings,study)  # publish the measured profile pointer
            if inspection['status']!='passed':raise SessionPaused('P1 measured gate not met; inspect report before changing renderer or training')
            review_path=directory/'visual-review.json'
            if not review_path.exists():raise SessionPaused('P0/UI and P1 visual review proof required before new seed training')
            complete('visual-review')  # reject mutation of an already accepted review
            review=read_json(review_path)
            validate_review(root,review,inspection_path)
            if not complete('visual-review'):
                stage('visual-review',[review_path]+[inside(root,r['path']) for r in [review['ui_check']]+review['references']])
            for job in state['jobs']:
                check_stop();save('seed-'+str(job['seed']))
                spec_seed=copy.deepcopy(base['spec']);spec_seed.update(Study=job['study'],Seed=job['seed'],TrainingSourcePin=base['source_pin'],Split=base['split'])
                child_settings={**settings,'Research':spec_seed}
                from .research import execute as research_run
                if job['status']!='succeeded':
                    before=time.monotonic();job['status']='running';write_json(directory/'state.json',state)
                    remaining=spec['MaximumGpuSeconds']-state['gpu_stage_wall_seconds']
                    if remaining<=0:raise SessionPaused('Confirmation GPU budget exhausted before seed')
                    session=os.environ.get('TOPIC16_SESSION_DIRECTORY')
                    def stop_for_budget():
                        if session:write_json(Path(session)/'stop.json',{'requested':True,'reason':'confirmation-budget'})
                    timer=threading.Timer(remaining,stop_for_budget);timer.daemon=True;timer.start()
                    try:leaf=research_run(root,child_settings,job['study'],resume=True)
                    finally:
                        timer.cancel();state['gpu_stage_wall_seconds']+=time.monotonic()-before;write_json(directory/'state.json',state)
                    child_report=root/'reports'/job['study']/'report.json';r=read_json(child_report)
                    job.update(status='succeeded',report=relative(root,child_report),report_sha256=sha256(child_report));write_json(directory/'state.json',state)
                if sha256(inside(root,job['report']))!=job['report_sha256']:raise ValueError('Completed seed report changed')
                if state['gpu_stage_wall_seconds']>=spec['MaximumGpuSeconds']:raise SessionPaused('Confirmation budget reached after committed seed pair')
            reports=[{'seed':42,'report':base_report}]+[{'seed':j['seed'],'report':read_json(inside(root,j['report']))} for j in state['jobs']]
            import statistics
            rows=[]
            for item in reports:
                control,candidate=item['report']['rows'];rows.append({'seed':item['seed'],
                    'psnr_gain':candidate['metrics']['psnr']-control['metrics']['psnr'],
                    'ssim_gain':candidate['metrics']['ssim']-control['metrics']['ssim'],
                    'roi_lpips_delta':candidate['roi_metrics']['lpips']-control['roi_metrics']['lpips'],
                    'training_ratio':candidate['training_seconds']/control['training_seconds'],
                    'rows':item['report']['rows']})
            stats={k:{'mean':statistics.mean(r[k] for r in rows),'std':statistics.stdev(r[k] for r in rows),
                      'min':min(r[k] for r in rows),'max':max(r[k] for r in rows)} for k in ('psnr_gain','ssim_gain','roi_lpips_delta','training_ratio')}
            checks={'psnr':stats['psnr_gain']['mean']>=spec['MinimumSeedMeanPsnrGain'],'ssim':stats['ssim_gain']['mean']>=0,
                    'roi_lpips':stats['roi_lpips_delta']['mean']<=0,'favourable_seeds':sum(r['psnr_gain']>0 for r in rows)>=spec['RequiredFavourableSeeds'],
                    'training_ratio':stats['training_ratio']['mean']<=spec['MaximumMeanTrainingRatio']}
            checks['gaussian_budget']=all(r['rows'][1]['gaussians']<=base['spec']['GaussianBudget'] for r in rows)
            checks['ply_size']=all((inside(root,r['rows'][1]['result']).parent/'model.ply').stat().st_size<=80*2**20 for r in rows)
            report={'status':'evaluated','study':study,'seeds':rows,'statistics':stats,'checks':checks,
                    'signal_gate_met':all(checks.values()),'scope':'Three paired seeds on one previously inspected capture; no significance/generalization claim.',
                    'next':'One separately declared quality intervention or independent Bonsai only after visual and signal review; old campaign remains paused.',
                    'finished_at':utc_now()}
            write_json(output/'report.json',report)
            lines=['# Tea v5 paired seed confirmation','',report['scope'],'',
                '|Seed|PSNR gain dB|SSIM gain|ROI LPIPS delta|Training ratio|',
                '|---|---:|---:|---:|---:|']
            for row in rows:
                lines.append('|'+str(row['seed'])+'|'+ '|'.join(f'{row[k]:.6f}' for k in ('psnr_gain','ssim_gain','roi_lpips_delta','training_ratio'))+'|')
            lines+=['','Signal gate: '+('met' if report['signal_gate_met'] else 'not met')+'.',
                'Checks: '+str(checks)+'.','',
                'Full mean/std/min/max, per-method metrics and artifact identities: report.json.',
                'Visual defects and failed renderer profiles remain in review/assessment.md.',
                'Budget includes conservative stage/child wall time; it is not pure GPU kernel time.',
                'See ../plans and the approved public plan for conditional P3/Bonsai gates.','',report['next']]
            (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
            stage('report',[output/'report.json',output/'report.md'])
            state.update(status='succeeded',phase='complete',finished_at=utc_now());write_json(directory/'state.json',state);return state
        except BaseException as error:
            state.update(status='paused' if isinstance(error,SessionPaused) else 'failed',error=str(error),updated_at=utc_now())
            write_json(directory/'state.json',state);raise
