"""Versioned Tea-only Q1.5 → paired official backend queue; no old campaign resume."""
from pathlib import Path
import os
import shutil
import time
import subprocess
import zipfile
from .contracts import read_json,write_json,sha256,digest_json,inside,relative,utc_now
from .source_pin import freeze_current,verify_pin
from .sessions import check_stop,SessionPaused


def prepare(root,settings,study):
    from .preservation import verify_source
    spec=settings['Research']
    if study!=spec['Study']:raise ValueError('Only the declared Tea research study is supported')
    verify_source(root,Path(settings['BaselineRoot']))
    q1=read_json(root/'artifacts/jobs/quality/tea-quality-v2.json')
    if q1['status']!='succeeded' or sha256(inside(root,q1['report']))!=q1['report_sha256']:
        raise ValueError('Completed unchanged Q1 required')
    source=root/'third_party/improved-gs'
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if commit!=spec['ImprovedGsCommit'] or subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():
        raise ValueError('Official Improved-GS source differs from pinned clean commit')
    presets={m:read_json(source/'configs'/f'{m}.json') for m in spec['Methods']}
    if study=='tea-research-v4':
        if (spec['SharedDensifyGradThreshold']!=presets['absgs']['train_args']['densify_grad_threshold']
                or spec['OptimizerType']!='ours_adam' or spec['PositionLearningRate']!=.00004):
            raise ValueError('Shared v4 settings differ from the declared audited preset/controls')
    split=root/'data/processed/canonical/tea_sets_2-native-v2/split.json'
    directory=root/'artifacts/jobs/research'/study;directory.mkdir(parents=True,exist_ok=True)
    declaration=directory/'declaration.json'
    if declaration.exists():
        old=read_json(declaration)
        if old['spec']!=spec or old['split_sha256']!=digest_json(read_json(split)):
            raise ValueError('Research protocol changed; declare a new experiment')
        pin=inside(root,old['source_pin']);verify_pin(root,pin,study)
        if sha256(pin)!=old['source_pin_sha256']:raise ValueError('Research source pin changed')
        return read_json(directory/'state.json')
    if shutil.disk_usage(root).free<50*2**30:raise ValueError('Research requires 50 GiB free, including 30 GiB reserve')
    pin=freeze_current(root,study)
    record={'schema_version':'tea-research-declaration-1','root':str(root),'spec':spec,
            'upstream_method_presets':{m:{'path':relative(root,source/'configs'/f'{m}.json'),
                'sha256':sha256(source/'configs'/f'{m}.json'),'train_args':v['train_args']} for m,v in presets.items()},
            'upstream':relative(root,source),'split':relative(root,split),'split_sha256':digest_json(read_json(split)),
            'source_pin':relative(root,pin),'source_pin_sha256':sha256(pin),'q1_report_sha256':q1['report_sha256'],
            'safety':{k:v for k,v in settings.items() if k.startswith('Gpu')},'created_at':utc_now(),
            'protocol':'105 train /15 eval; native719x1279; SH3; seed42; 30k; identical SfM initialization; no exposure/depth/pose optimization',
            'comparison':'Official AbsGS vs Improved-GS package intervention. Same shared optimizer settings, but MU update count and method-native Gaussian growth differ. Not a same-compute or same-Gaussian-count claim.',
            'scope':'Exploratory Tea only, not exact paper reproduction; cu118 recipe, off-center camera adapter, 300k Improved-GS budget.',
            'gate':'Both 600-step resume replays must pass before either full run. No scene expansion or seed selection.'}
    write_json(declaration,record)
    state={'study':study,'status':'planned','phase':'q15','stages':{},'created_at':utc_now(),
           'declaration_sha256':sha256(declaration)}
    if spec.get('ReuseMultiscaleStudy'):
        previous=root/'artifacts/jobs/research'/spec['ReuseMultiscaleStudy']/'state.json'
        parent=read_json(previous)
        proof=parent['stages']['q15']
        for ref in proof['references']:
            if sha256(inside(root,ref['path']))!=ref['sha256']:raise ValueError('Inherited Q1.5 proof changed')
        inherited=read_json(inside(root,proof['references'][0]['path']))
        if inherited['status']!='succeeded' or len(inherited['rows'])!=12:raise ValueError('Inherited Q1.5 is incomplete')
        state['stages']['q15']=proof
        state['q15_origin']={'study':spec['ReuseMultiscaleStudy'],'scope':'Identical existing checkpoints, cameras, evaluator and inference matrix; no new rendering intervention'}
    write_json(directory/'state.json',state);return state


def execute(root,settings,study,resume=False):
    from .runtime import gpu_lock,run_command
    from .multiscale import execute as multiscale
    from .evidence import score_saved_images,EVALUATOR
    directory=root/'artifacts/jobs/research'/study
    state=prepare(root,settings,study);declaration=directory/'declaration.json'
    document=read_json(declaration);spec=document['spec']
    if sha256(declaration)!=state['declaration_sha256']:raise ValueError('Research declaration bytes changed')
    if state['status']=='succeeded':return state
    from .runtime import gpu_identity
    hardware=gpu_identity(root)
    if state.get('hardware') and state['hardware']!=hardware:raise ValueError('Research hardware changed')
    state['hardware']=hardware
    if state['status']!='planned' and not resume:raise ValueError('Research has started; use Resume')
    record,tree=verify_pin(root,inside(root,document['source_pin']),study)
    revision='v1'
    revision_path=directory/'training-revision.json'
    if revision_path.exists():
        revision_record=read_json(revision_path)
        new_pin=inside(root,revision_record['source_pin'])
        if sha256(new_pin)!=revision_record['source_pin_sha256']:raise ValueError('Trainer revision source pin changed')
        record,tree=verify_pin(root,new_pin)
        revision=revision_record['revision']
        state['training_revision']={'path':relative(root,revision_path),'sha256':sha256(revision_path)}
    output=root/'reports'/study;output.mkdir(parents=True,exist_ok=True)
    # Controller repairs never replace the frozen trainer/declaration identity.
    from .source_pin import source_files,identity
    files=source_files(root);controller_id=identity(files)
    archive=directory/'controllers'/controller_id/'source.zip';archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as snapshot:
            for name in files:snapshot.write(inside(root,name),name)
    controller={'source_id':controller_id,'archive':relative(root,archive),'sha256':sha256(archive),'source_files':files}
    if controller not in state.setdefault('controllers',[]):state['controllers'].append(controller)
    write_json(directory/'state.json',state)
    def commit(phase):
        state.update(status='running',phase=phase,updated_at=utc_now());state.pop('error',None)
        write_json(directory/'state.json',state)
    def completed(key):
        if key not in state['stages']:return False
        for item in state['stages'][key]['references']:
            if sha256(inside(root,item['path']))!=item['sha256']:raise ValueError('Completed research evidence changed')
        return True
    def stage(key,paths):
        state['stages'][key]={'references':[{'path':relative(root,p),'sha256':sha256(p)} for p in paths]}
        write_json(directory/'state.json',state)
    with gpu_lock(root,{'SharedGpuLock':str(root/'artifacts/jobs/research.lock')}):
        try:
            check_stop()
            if not completed('q15'):
                commit('q15-multiscale')
                multiscale(root,settings,output/'q15')
                stage('q15',[output/'q15/report.json'])
            host=read_json(root/'artifacts/logs/host.json')
            ready=root/'artifacts/logs/improvedgs-setup.json'
            if not ready.exists():raise SessionPaused('Official backend setup is incomplete; frozen Q1.5 remains complete')
            setup=read_json(ready)
            if setup['status']!='ready' or setup['commit']!=spec['ImprovedGsCommit'] or setup['environment']!=spec['EnvironmentName']:
                raise ValueError('Official backend setup identity differs')
            worker=tree/'src/topic16_upgrade/improved_worker.py'
            command=[host['conda'],'run','--no-capture-output','-n',spec['EnvironmentName'],'python',str(worker),
                     '--declaration',str(declaration)]
            if revision!='v1':command+=['--trainer-revision',revision]
            if not completed('official-parity'):
                commit('official-camera-ply-parity')
                helper=root/'src/topic16_upgrade/official_parity.py'
                if sha256(helper)!=files['src/topic16_upgrade/official_parity.py']:
                    raise ValueError('Parity helper changed after controller archive')
                with gpu_lock(root,settings):
                    run_command(root,[host['conda'],'run','--no-capture-output','-n',spec['EnvironmentName'],'python',str(helper),
                                      '--declaration',str(declaration)],output/'official-parity.log',environment_overrides={'MKL_THREADING_LAYER':'SEQUENTIAL'})
                stage('official-parity',[output/'official-parity/report.json'])
            for method in spec['Methods']:
                check_stop();key='qa-'+method
                if completed(key):continue
                commit(key)
                qa_attempt=revision+'-'+str(time.time_ns())
                with gpu_lock(root,settings):
                    from .safety import current_guard
                    qa_guard=current_guard().path
                    run_command(root,command+['--method',method,'--qa','--trainer-revision',qa_attempt],output/(key+'-'+str(time.time_ns())+'.log'),cooperative_training=True,environment_overrides={'MKL_THREADING_LAYER':'SEQUENTIAL'})
                proof=root/'artifacts/research'/study/('qa-'+qa_attempt)/method/'resume-check.json'
                if read_json(proof)['status']!='passed':raise ValueError('Resume replay gate failed')
                stage(key,[proof,qa_guard])
            # All QA passes before committing GPU to either 30k research model.
            rows=[]
            for method in spec['Methods']:
                check_stop();key='full-'+method
                result_path=root/'artifacts/research'/study/'runs'/method/'result.json'
                safety_reference=result_path.parent/'safety-reference.json'
                if not completed(key):
                    commit(key)
                    spent=0.
                    for other in spec['Methods']:
                        saved=root/'artifacts/research'/study/'runs'/other/'latest.json'
                        if saved.exists():spent+=read_json(saved)['training_seconds']
                    if spent>=spec['MaximumTotalTrainingSeconds']:
                        raise SessionPaused('Total declared research training budget reached; review before extension')
                    if not result_path.exists() or not safety_reference.exists():
                        with gpu_lock(root,settings):
                            from .safety import current_guard
                            full_guard=current_guard().path
                            run_command(root,command+['--method',method],output/(key+'-'+str(time.time_ns())+'.log'),cooperative_training=True,environment_overrides={'MKL_THREADING_LAYER':'SEQUENTIAL'})
                        write_json(safety_reference,{'path':relative(root,full_guard),'sha256':sha256(full_guard)})
                    safety=read_json(safety_reference);safety_path=inside(root,safety['path'])
                    if sha256(safety_path)!=safety['sha256'] or read_json(safety_path)['status']!='succeeded':
                        raise ValueError('Official run lacks completed safe GPU telemetry')
                    result=read_json(result_path)
                    if result['status']!='succeeded' or result['checkpoint']['step']!=spec['Iterations']:
                        raise ValueError('Research model has not completed the declared schedule')
                    stage(key,[result_path,result_path.parent/result['checkpoint']['path'],result_path.parent/'model.ply',safety_reference,safety_path])
                result=read_json(result_path)
                if result['identity'].get('trainer_sha256')!=sha256(worker):
                    raise ValueError('Completed model uses a different trainer revision')
                checkpoint=inside(result_path.parent,result['checkpoint']['path'])
                if sha256(checkpoint)!=result['checkpoint']['sha256']:raise ValueError('Q2 checkpoint changed')
                for frame in result['frames']:
                    for kind in ('gt','pred'):
                        if sha256(result_path.parent/frame[kind])!=frame[kind+'_sha256']:raise ValueError('Q2 saved image changed')
                commit('common-eval-'+method)
                common=score_saved_images([{k:result_path.parent/f[k] for k in ('gt','pred')} for f in result['frames']],
                    {'evaluator_id':EVALUATOR,'result_sha256':sha256(result_path)},result_path.parent/'common.json',4)
                from .quality_report import roi_scores
                rois=read_json(root/'reports/tea-quality-v2/q0/rois.json')
                roi=roi_scores(root,{'path':relative(root,result_path.parent/'common.json'),'identity':common['identity']},rois['boxes'])
                rows.append({'method':method,'metrics':common['metrics'],'roi_metrics':roi['metrics'],'gaussians':result['gaussians'],
                             'optimizer_updates':result['checkpoint']['updates'],'training_seconds':result['training_seconds'],
                             'offline_fps':result['offline_fps'],'peak_cuda_allocated_bytes':result['peak_cuda_allocated_bytes'],
                             'result':relative(root,result_path),'result_sha256':sha256(result_path),
                             'common':relative(root,result_path.parent/'common.json'),'common_sha256':sha256(result_path.parent/'common.json')})
            control,candidate=rows
            q1=read_json(root/'reports/tea-quality-v2/report.json')
            q1_native=next(r for r in q1['comparisons'] if r['tag']=='native-candidate-native')
            half_native=next(r for r in q1['comparisons'] if r['tag']=='half-control-native')
            q1_images=read_json(inside(root,q1_native['path']).parent/'renders.json')['frames']
            for row in rows:
                images=read_json(inside(root,row['result']))['frames']
                if [f['gt_sha256'] for f in images]!=[f['gt_sha256'] for f in q1_images]:
                    raise ValueError('Q2 vs Q1 ground truth pixel mismatch')
            def dominates(left,right):
                return left['psnr']>=right['psnr'] and left['ssim']>=right['ssim'] and left['lpips']<=right['lpips']
            roi_delta={k:candidate['roi_metrics'][k]-half_native['roi_metrics'][k] for k in ('psnr','ssim','lpips')}
            numeric_target=(roi_delta['psnr']>=1 and candidate['roi_metrics']['lpips']<=half_native['roi_metrics']['lpips']*.85
                            and candidate['metrics']['psnr']>=half_native['metrics']['psnr'])
            report={'status':'succeeded','study':study,'rows':rows,'declaration_sha256':sha256(declaration),
                    'hardware':hardware,'evaluator_source_sha256':files['src/topic16_upgrade/evidence.py'],
                    'training_revision':state.get('training_revision'),
                    'delta_vs_same_backend_absgs':{k:candidate['metrics'][k]-control['metrics'][k] for k in ('psnr','ssim','lpips')},
                    'q1_native_metrics':q1_native['metrics'],
                    'delta_vs_q1_native':{k:candidate['metrics'][k]-q1_native['metrics'][k] for k in ('psnr','ssim','lpips')},
                    'roi_delta_vs_q1_native':{k:candidate['roi_metrics'][k]-q1_native['roi_metrics'][k] for k in ('psnr','ssim','lpips')},
                    'original_roi_target_vs_half_control_met':numeric_target,
                    'dominates_q1_global_metrics':dominates(candidate['metrics'],q1_native['metrics']),
                    'dominates_same_backend_absgs_global_metrics':dominates(candidate['metrics'],control['metrics']),
                    'verdict':'Numeric evidence only; visual/scale review and independent confirmation required. No automatic scene expansion.',
                    'scope':document['scope'],'comparison':document['comparison'],'finished_at':utc_now(),
                    'next_gate':'Independent visual review, scale stability and resources before extra seeds or Bonsai. Negative results remain published.'}
            write_json(output/'report.json',report)
            lines=['# Tea research v3 — measured results','',report['scope'],'',report['comparison'],'',
                   '| Method | PSNR | SSIM | LPIPS | Gaussians | Optimizer updates | Train minutes | Offline FPS |',
                   '|---|---:|---:|---:|---:|---:|---:|---:|']
            lines.extend(f"| {r['method']} | {r['metrics']['psnr']:.4f} | {r['metrics']['ssim']:.5f} | {r['metrics']['lpips']:.5f} | {r['gaussians']} | {r['optimizer_updates']} | {r['training_seconds']/60:.1f} | {r['offline_fps']:.2f} |" for r in rows)
            lines.extend(['',str(report['delta_vs_same_backend_absgs']),'',report['next_gate']])
            lines.extend(['','Compared with Q1 native: '+str(report['delta_vs_q1_native']),
                          'ROI delta vs Q1 native: '+str(report['roi_delta_vs_q1_native']),
                          'Original +1dB /−15% ROI target vs half-trained control: '+str(numeric_target),
                          '',report['verdict']])
            (output/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
            stage('report',[output/'report.json',output/'report.md'])
            state.update(status='succeeded',phase='complete',finished_at=utc_now());state.pop('error',None)
            write_json(directory/'state.json',state);return state
        except BaseException as error:
            state.update(status='paused' if isinstance(error,SessionPaused) else 'failed',error=str(error),updated_at=utc_now())
            write_json(directory/'state.json',state);raise
