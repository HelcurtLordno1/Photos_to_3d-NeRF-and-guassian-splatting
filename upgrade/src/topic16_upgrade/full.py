"""Dataset-first full-budget campaign; a dataset gate precedes the next GPU job."""
from pathlib import Path
import csv
import json
import shutil
import subprocess
import sys
import os
import re
from .contracts import (read_json,write_json,inside,relative,sha256,digest_json,load_run,
                        utc_now,validate_export,validate_render,validate_metrics)
from .capture import capture_split
from .settings import experiment_settings_hash
from .sessions import check_stop,SessionPaused
from .source_pin import freeze_current,verify_pin
from .study import execute,preflight,publish
from .evidence import score_saved_images,EVALUATOR


def campaign_path(root,name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',name):raise ValueError('Invalid campaign name')
    return inside(root/'artifacts/jobs/campaigns',name+'.json')


def prepare(root,settings,baseline,name):
    path=campaign_path(root,name)
    if path.exists():
        record=read_json(path)
        if record['settings_hash']!=experiment_settings_hash(settings):raise ValueError('Campaign registry changed')
        return record
    base=settings['Studies']['tea-confirm-v1']
    if base['Iterations']!=settings['TrainIterations'] or base['Iterations']!=30000:
        raise ValueError('Full campaign requires the declared 30k protocol')
    historical={}
    with (baseline/'reports/topic16-full/results.csv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):historical[row['scene']]=historical.get(row['scene'],0)+float(row['train_seconds'])
    scenes=[base['Scene']]+sorted(settings['MipNerf360Scenes'],key=lambda scene:historical.get(scene,float('inf')))
    datasets=[];total_bytes=0;source=None
    for scene in scenes:
        frozen,provenance=capture_split(baseline,scene)
        count=len(frozen['train']);views=list(dict.fromkeys([count,*base['Views']]))
        if min(views)<1 or max(views)>count:raise ValueError('Invalid full-study view count')
        study=f'full-{scene.replace(":","-")}-30k-v1'
        spec={**base,'Scene':scene,'Views':views}
        definition={'schema_version':'full-study-definition-1','study':study,'settings_hash':experiment_settings_hash(settings),
                    'spec':spec,'capture':provenance,'pool_hash':digest_json(frozen['train']),
                    'eval_camera_hash':digest_json(frozen['eval']),'source_campaign':name}
        definition_path=root/'artifacts/jobs/definitions'/f'{study}.json'
        if definition_path.exists() and read_json(definition_path)!=definition:raise ValueError('Full-study declaration already differs')
        write_json(definition_path,definition)
        source=freeze_current(root,study,source)
        jobs=len(base['Methods'])*(1+len(base['Recipes'])*(len(views)-1))
        # Materialization stores full-resolution and measured downscaled images,
        # once per condition, shared between both methods.
        frame_bytes=[]
        for frame in frozen['train']+frozen['eval']:
            image=inside(baseline,frame['path']);original=image.parent.parent/'images'/image.name
            frame_bytes.append(image.stat().st_size+original.stat().st_size)
        mean_bytes=sum(frame_bytes)/len(frame_bytes)
        conditions=1+len(base['Recipes'])*(len(views)-1)
        derivative_bytes=int(sum((v+len(frozen['eval']))*mean_bytes*(1 if v==count else len(base['Recipes'])) for v in views))
        estimate=jobs*2*2**30+derivative_bytes
        total_bytes+=estimate
        datasets.append({'scene':scene,'study':study,'status':'pending','train_pool':count,'eval_views':len(frozen['eval']),
            'views':views,'training_jobs':jobs,'conditions':conditions,'new_bytes_estimate':estimate,
            'historical_training_seconds_proxy':historical.get(scene,0)*conditions,
            'capture':provenance,'source_pin':relative(root,source)})
    free=shutil.disk_usage(root).free
    if free<total_bytes+settings['MinimumUpgradeFreeGiB']*2**30:
        raise ValueError('Full campaign would violate the disk reserve; no GPU job started')
    result={'schema_version':'dataset-first-full-1','name':name,'status':'planned','created_at':utc_now(),
        'settings_hash':experiment_settings_hash(settings),'datasets':datasets,'current_scene':None,
        'policy':'Complete training/evaluation/common metrics/reference exports/throughput/report/catalog before next dataset',
        'estimated_new_bytes':total_bytes,'free_bytes_at_plan':free,'reserve_gib':settings['MinimumUpgradeFreeGiB'],
        'eta_scope':'Historical training proxy only; evaluation/export/throughput/cooldown are additional',
        'total_training_jobs':sum(d['training_jobs'] for d in datasets)}
    write_json(path,result)
    return result


def historical_common(root,baseline,scene,settings):
    frozen,_=capture_split(baseline,scene)
    pairs=[p for matrix in sorted((baseline/'artifacts/logs/matrices').glob('topic16-full-*.json'))
           for key,p in read_json(matrix)['pairs'].items() if key==scene]
    pair=pairs[0];rows=[]
    from .runtime import runtime_snapshot
    for method in settings['Studies']['tea-confirm-v1']['Methods']:
        run=load_run(baseline,inside(baseline,pair['runs'][method]),require_eval=True)
        frames=run['evaluation']['frames']
        identity={'evaluator_id':EVALUATOR,'runtime_id':digest_json(runtime_snapshot()),
            'evaluation_sha256':sha256(run['paths']['metrics']/'evaluation.json'),
            'config_sha256':sha256(run['config']),'checkpoint_sha256':run['provenance']['checkpoint_sha256']}
        output=root/'reports/full/historical'/scene.replace(':','-')/f'{method}-common.json'
        scored=score_saved_images([{k:run['paths']['renders']/frame[k] for k in ('gt','pred')} for frame in frames],identity,output,settings['CpuWorkerThreads'])
        rows.append({'method':method,'run_key':run['manifest']['run_key'],'scene_group':scene,
            'metrics':scored['metrics'],'evaluator_id':EVALUATOR,'budget':run['manifest']['protocol']['iterations'],
            'views':len(run['split']['train']),'seed':run['manifest']['protocol']['seed'],
            'eval_camera_hash':digest_json(frozen['eval']),'common_report':relative(root,output),'common_sha256':sha256(output),
            'evaluation':relative(baseline,run['paths']['metrics']/'evaluation.json'),
            'evaluation_sha256':identity['evaluation_sha256'],'config':relative(baseline,run['config']),
            'config_sha256':identity['config_sha256'],'checkpoint_sha256':identity['checkpoint_sha256']})
    write_json(root/'reports/full/historical'/scene.replace(':','-')/'index.json',
               {'schema_version':'historical-common-1','scene':scene,'rows':rows,'scope':'Read-only re-evaluation of saved baseline predictions; no baseline retraining or writes'})
    return rows


def validate_declaration(root,settings,baseline,item):
    """Fail before compute if an artifact declaration drifted from the matrix."""
    path=root/'artifacts/jobs/definitions'/f'{item["study"]}.json'
    declaration=read_json(path)
    frozen,provenance=capture_split(baseline,item['scene'])
    base=settings['Studies']['tea-confirm-v1']
    views=list(dict.fromkeys([len(frozen['train']),*base['Views']]))
    expected={**base,'Scene':item['scene'],'Views':views}
    jobs=len(base['Methods'])*(1+len(base['Recipes'])*(len(views)-1))
    if (declaration['schema_version']!='full-study-definition-1'
        or declaration['study']!=item['study'] or declaration['spec']!=expected
        or declaration['settings_hash']!=experiment_settings_hash(settings)
        or declaration['capture']!=provenance or declaration['pool_hash']!=digest_json(frozen['train'])
        or declaration['eval_camera_hash']!=digest_json(frozen['eval'])
        or item['train_pool']!=len(frozen['train']) or item['eval_views']!=len(frozen['eval'])
        or item['views']!=views or item['training_jobs']!=jobs):
        raise ValueError('Full-study declaration or frozen dataset changed; no GPU job started')
    verify_pin(root,inside(root,item['source_pin']),item['study'])


def prepare_catalog(root,baseline,output):
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
             str(baseline/'UI_design/scripts/Prepare-UIAssets.ps1')]
    with output.open('w',encoding='utf-8') as stream:
        result=subprocess.run(command,cwd=baseline,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError(f'Catalog preparation failed; see {output}')
    catalog=read_json(baseline/'artifacts/ui/catalog.json')['catalog']
    if catalog.get('upgrade',{}).get('status')!='ready':raise ValueError('Full campaign catalog did not validate upgrade evidence')
    return catalog


def dataset_gate(root,settings,baseline,item):
    study=item['study'];scene=item['scene']
    completion_path=root/'reports'/study/'completion.json'
    completion=read_json(completion_path)
    if completion['status']!='succeeded' or completion['completed_jobs']!=item['training_jobs']:
        raise ValueError('Dataset training matrix is incomplete')
    rows=completion['runs']
    references=[r for r in rows if r['recipe']=='full-pool' and r['views']==item['train_pool']]
    if {r['method'] for r in references}!=set(settings['Studies']['tea-confirm-v1']['Methods']):
        raise ValueError('Dataset lacks the full-pool paired reference')
    from .runtime import render,export
    for row in references:
        check_stop();config=inside(root,row['config'])
        print(f'FULL REFERENCE throughput: {scene}/{row["method"]}',flush=True)
        render(root,settings,config)
        check_stop()
        print(f'FULL REFERENCE export: {scene}/{row["method"]}',flush=True)
        export(root,settings,config)
    historical=historical_common(root,baseline,scene,settings)
    for row in rows:
        run=load_run(root,inside(root,row['config']),require_eval=True)
        validate_metrics({'results':row['metrics']})
        if row['budget']!=settings['TrainIterations'] or row['eval_camera_hash']!=historical[0]['eval_camera_hash']:
            raise ValueError('Dataset result has a different full budget or held-out frame')
    for row in references:
        run=load_run(root,inside(root,row['config']),require_eval=True)
        recorded=read_json(run['paths']['logs']/'settings.json')
        validate_export(run['paths']['exports'],row['checkpoint_sha256'],root,recorded)
        validate_render(run['paths']['videos']/digest_json(run['split']['eval'])[:16],row['checkpoint_sha256'],root,recorded)
    # Refresh optional exports/FPS and derivative historical evaluations before
    # checking the shared catalog. A ready full reference must actually render.
    ledger=read_json(root/'artifacts/jobs/ledger.json');index=publish(root,ledger)
    output=root/'reports/full'/scene.replace(':','-');output.mkdir(parents=True,exist_ok=True)
    catalog=prepare_catalog(root,baseline,output/'catalog.log')
    displayed=next(s for s in catalog['scenes'] if s['id']==scene)
    selected=[s for s in displayed.get('run_sets',[]) if all(s['methods'][m]['run_key'] in {r['run_key'] for r in references} for m in ('nerfacto','splatfacto'))]
    if len(selected)!=1 or not all(selected[0]['methods'][m]['asset'] for m in ('nerfacto','splatfacto')):
        raise ValueError('Full reference is missing a verified browser-sized paired 3D export')
    compared=[]
    for row in rows:
        old=next(h for h in historical if h['method']==row['method'])
        compared.append({'method':row['method'],'recipe':row['recipe'],'views':row['views'],'budget':row['budget'],
            'metrics':row['metrics'],'historical_metrics':old['metrics'],
            'delta_vs_historical':{k:row['metrics'][k]-old['metrics'][k] for k in ('psnr','ssim','lpips')},
            'scope':'historical-budget-matched' if row['views']==old['views'] else 'declared view-count trade-off',
            'run_key':row['run_key']})
    gate={'schema_version':'full-dataset-gate-1','status':'passed','scene':scene,'study':study,
        'finished_at':utc_now(),'full_budget':settings['TrainIterations'],'training_jobs':len(rows),
        'evaluator_id':EVALUATOR,'eval_views':item['eval_views'],'reference_run_keys':[r['run_key'] for r in references],
        'run_set_id':selected[0]['id'],'catalog_revision':catalog['revision'],'comparison':compared,
        'controlled_selector_comparisons':completion['controlled_comparisons'],
        'study_completion':relative(root,completion_path),'study_completion_sha256':sha256(completion_path),
        'historical_common':historical,'cost_scope':'Training, CPU common evaluation, native evaluation/export/throughput/safety stage logs retained'}
    fields=('method','recipe','views','budget','psnr','ssim','lpips','delta_psnr','delta_ssim','delta_lpips','scope','run_key')
    with (output/'comparison.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fields,extrasaction='ignore');writer.writeheader()
        for row in compared:writer.writerow({**row,**row['metrics'],**{'delta_'+k:v for k,v in row['delta_vs_historical'].items()}})
    body=['# Full dataset evaluation — '+scene,'',f'30,000 iterations · {len(rows)} completed runs · {item["eval_views"]} frozen held-out views',
          '', '| Recipe | Method | Views | PSNR dB | SSIM | LPIPS |','|---|---|---:|---:|---:|---:|']
    body += [f'| {r["recipe"]} | {r["method"]} | {r["views"]} | {r["metrics"]["psnr"]:.4f} | {r["metrics"]["ssim"]:.4f} | {r["metrics"]["lpips"]:.4f} |' for r in rows]
    body += ['', 'Historical results use the same saved-RGB evaluator. Historical source differs; these are not controlled source-improvement claims.',
             'Selector claims use only the matched within-upgrade pairs. Negative results remain included.',
             'Full-reference paired exports and held-out throughput are verified. Gate: passed.']
    (output/'report.md').write_text('\n'.join(body)+'\n',encoding='utf-8')
    gate['report_artifacts']=[{'path':relative(root,p),'sha256':sha256(p)}
                              for p in (output/'comparison.csv',output/'report.md')]
    write_json(output/'gate.json',gate)
    return gate


def validate_gate(root,settings,baseline,item):
    path=root/'reports/full'/item['scene'].replace(':','-')/'gate.json'
    if sha256(path)!=item['gate_sha256']:raise ValueError('Prior dataset gate changed')
    gate=read_json(path)
    if gate['status']!='passed' or gate['scene']!=item['scene'] or gate['full_budget']!=settings['TrainIterations']:
        raise ValueError('Prior dataset gate differs from the declared study')
    if sha256(inside(root,gate['study_completion']))!=gate['study_completion_sha256']:
        raise ValueError('Prior dataset completion changed')
    for artifact in gate['report_artifacts']:
        if sha256(inside(root,artifact['path']))!=artifact['sha256']:raise ValueError('Prior dataset report changed')
    for row in gate['historical_common']:
        if sha256(inside(root,row['common_report']))!=row['common_sha256']:raise ValueError('Historical common evaluator report changed')
    ledger=read_json(root/'artifacts/jobs/ledger.json')
    from .study import completed
    keys=read_json(inside(root,gate['study_completion']))['experiment_keys']
    if len(keys)!=item['training_jobs'] or not all(completed(root,ledger['jobs'][key]) for key in keys):
        raise ValueError('Prior dataset no longer has all validated experiments')
    for key in gate['reference_run_keys']:
        run=load_run(root,root/'artifacts/runs'/key/'config.yml',require_eval=True)
        saved=read_json(run['paths']['logs']/'settings.json')
        validate_export(run['paths']['exports'],run['provenance']['checkpoint_sha256'],root,saved)
        validate_render(run['paths']['videos']/digest_json(run['split']['eval'])[:16],run['provenance']['checkpoint_sha256'],root,saved)
    return gate


def run(root,settings,baseline,name,resume=False):
    from .runtime import gpu_lock
    path=campaign_path(root,name)
    campaign=read_json(path)
    if campaign['settings_hash']!=experiment_settings_hash(settings):raise ValueError('Campaign settings changed')
    if campaign['status']!='planned' and not resume:raise ValueError('Campaign has attempts; use Resume')
    with gpu_lock(root,{'SharedGpuLock':str(root/'artifacts/jobs/full-campaign.lock')}):
        try:
            campaign.update(status='running',updated_at=utc_now());write_json(path,campaign)
            for item in campaign['datasets']:
                check_stop()
                validate_declaration(root,settings,baseline,item)
                if item['status']=='succeeded':validate_gate(root,settings,baseline,item);continue
                campaign['current_scene']=item['scene'];item.update(status='running',started_at=item.get('started_at',utc_now()))
                write_json(path,campaign)
                print(f'FULL DATASET START: {item["scene"]} — {item["training_jobs"]} full-budget jobs; next dataset is gated',flush=True)
                preflight(root,settings,baseline,item['study'])
                ledger=read_json(root/'artifacts/jobs/ledger.json') if (root/'artifacts/jobs/ledger.json').exists() else {'jobs':{}}
                started=any(j['study']==item['study'] for j in ledger['jobs'].values())
                execute(root,settings,baseline,item['study'],resume=started)
                check_stop();item['phase']='full-reference artifacts';write_json(path,campaign)
                gate=dataset_gate(root,settings,baseline,item)
                item.update(status='succeeded',phase='complete',finished_at=gate['finished_at'],
                            gate=relative(root,root/'reports/full'/item['scene'].replace(':','-')/'gate.json'),
                            gate_sha256=sha256(root/'reports/full'/item['scene'].replace(':','-')/'gate.json'))
                write_json(path,campaign)
                print(f'FULL DATASET PASS: {item["scene"]}; all acceptance evidence is committed',flush=True)
            campaign.update(status='succeeded',current_scene=None,finished_at=utc_now())
            write_json(path,campaign)
            return campaign
        except BaseException as error:
            campaign.update(status='paused' if isinstance(error,SessionPaused) else 'failed',error=str(error),updated_at=utc_now())
            write_json(path,campaign)
            raise
