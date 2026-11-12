"""Sequential experiment queue with immutable keys, checkpoint resume and evidence."""
from pathlib import Path
import csv
import shutil
import os
from .contracts import read_json, write_json, sha256, digest_json, inside, relative, load_run, utc_now
from .capture import capture_split, audit, select, FEATURE_SCHEMA
from .data import materialize
from .sessions import SessionPaused, check_stop
from .evidence import EVALUATOR, evaluate_common, compare


def source_identity(root):
    from .source_pin import execution_sources, identity
    return identity(execution_sources(root)[1])


def definition(settings, study, root=None):
    if root is not None:
        from .settings import experiment_settings_hash
        path=inside(root/'artifacts/jobs/definitions',study+'.json')
        if path.exists():
            record=read_json(path)
            if record['schema_version']!='full-study-definition-1' or record['study']!=study:
                raise ValueError('Invalid full-study definition')
            if record['settings_hash']!=experiment_settings_hash(settings):
                raise ValueError('Full-study registry differs from its declaration')
            spec=record['spec'];base=settings['Studies']['tea-confirm-v1']
            for field in ('Iterations','Seed','Protocol','Recipes','Methods'):
                if spec[field]!=base[field]:raise ValueError('Full study changed its pinned protocol')
            if spec['Iterations']!=settings['TrainIterations']:raise ValueError('Full study must use total budget')
            return spec
    try:
        return settings['Studies'][study]
    except KeyError as error:
        raise ValueError(f'Unknown study: {study}') from error


def completed(root, item):
    if item.get('status') != 'succeeded' or not item.get('config'):
        return False
    run = load_run(root, inside(root, item['config']), require_eval=True)
    identity = item['identity']
    source_files = {k:v for k,v in run['provenance']['source_files'].items() if Path(k).suffix in ('.py','.ps1','.psd1')}
    if (digest_json(identity) != item['experiment_key'] or digest_json(source_files) != identity['source_id']
            or run['manifest']['protocol']['iterations'] != identity['budget']
            or run['manifest']['protocol']['seed'] != identity['seed']
            or run['manifest']['method'] != identity['method']
            or run['split']['capture']['selection_id'] != identity['selection_id']
            or run['split']['capture']['eval_camera_hash'] != identity['eval_camera_hash']):
        raise ValueError('Cached experiment identity contradicts its exact run evidence')
    common_path = run['paths']['metrics'] / 'common-metrics.json'
    if sha256(common_path) != item['common_metrics_sha256']:
        raise ValueError('Completed common metric record changed')
    common = read_json(common_path)
    if (common['status'] != 'succeeded' or common['identity']['evaluator_id'] != EVALUATOR
            or common['identity']['evaluation_sha256'] != sha256(run['paths']['metrics'] / 'evaluation.json')
            or common['identity']['runtime_id'] != item['identity']['runtime_id']):
        raise ValueError('Completed common evaluator does not match the exact run')
    return True


def plan(root, settings, baseline, study, split_path=None):
    from .runtime import runtime_snapshot
    from .source_pin import activate
    activate(root,study)
    spec = definition(settings, study, root); scene = spec['Scene']
    frozen, provenance = capture_split(baseline, scene, split_path)
    features = audit(root, baseline, scene, split_path, settings['AuditImageSize'])
    source_id, runtime_id = source_identity(root), digest_json(runtime_snapshot())
    safety_id = digest_json({k: v for k, v in settings.items() if k.startswith('Gpu')})
    ledger_path = root / 'artifacts/jobs/ledger.json'
    ledger = read_json(ledger_path) if ledger_path.exists() else {'schema_version': 'upgrade-queue-1', 'jobs': {}}
    jobs, seen, estimates = [], set(), []
    report_path = baseline / 'reports/topic16-full/results.csv'
    historical = []
    if report_path.exists():
        with report_path.open(encoding='utf-8-sig', newline='') as stream:
            historical = list(csv.DictReader(stream))
    for count in spec['Views']:
        for recipe in spec['Recipes']:
            selection = select(features, count, recipe, spec['Seed'])
            for method in spec['Methods']:
                identity = {'variant': 'upgrade', 'source_id': source_id, 'runtime_id': runtime_id,
                            'scene_group': scene, 'pool_hash': features['pool_hash'], 'selection_id': selection['selection_id'],
                            'eval_camera_hash': features['eval_camera_hash'], 'method': method, 'seed': spec['Seed'],
                            'budget': spec['Iterations'], 'schedule': f'{method}-total-{spec["Iterations"]}',
                            'downscale': settings['DownscaleFactor'], 'evaluator_id': EVALUATOR,
                            'safety_id': safety_id, 'protocol_id': spec['Protocol']}
                key = digest_json(identity)
                if key in seen:
                    continue
                seen.add(key)
                previous = ledger['jobs'].get(key, {})
                hit = completed(root, previous)
                condition = 'custom:' + scene.replace('custom:', '') + '--' + selection['selection_id'][:16]
                jobs.append({'experiment_key': key, 'identity': identity, 'selection': selection,
                             'recipe': selection['recipe'], 'views': count, 'condition': condition,
                             'cache_hit': hit})
                old = [r for r in historical if r['scene'] == scene and r['method'] == method]
                if not hit and old:
                    estimates.append(float(old[0]['train_seconds']) * spec['Iterations'] / int(old[0]['iterations']))
    result = {'schema_version': 'upgrade-plan-1', 'study': study, 'created_at': utc_now(),
              'capture': provenance, 'jobs': jobs, 'new_jobs': sum(not j['cache_hit'] for j in jobs),
              'cache_hits': sum(j['cache_hit'] for j in jobs), 'deduplicated_jobs': len(jobs),
              'forecast': {'status': 'insufficient-evidence', 'reason': 'One capture does not validate cross-scene PSNR forecast'},
              'storage': {'free_gib': shutil.disk_usage(root).free / 2**30,
                          'reserve_gib': settings['MinimumUpgradeFreeGiB'],
                          'estimated_new_gib': sum(not j['cache_hit'] for j in jobs) * 2.},
              'eta': {'training_seconds_proxy': sum(estimates) if estimates else None,
                      'source': 'historical same-scene training time × iteration ratio; not measured',
                      'excludes': ['setup', 'evaluation', 'cooldown', 'pause', 'materialization'],
                      'nonlinear_warning': 'Subset size, densification and total schedules change per-step cost'}}
    actual = [v for v in ledger['jobs'].values() if v.get('status') == 'succeeded']
    if actual:
        result['eta']['actual_completed_training_seconds'] = {v['experiment_key']: v['train_seconds'] for v in actual}
    destination = root / 'artifacts/jobs' / f'{study}-plan.json'
    if destination.exists():
        previous = read_json(destination)
        old_keys = {j['experiment_key'] for j in previous['jobs']}
        if old_keys != {j['experiment_key'] for j in jobs}:
            # A failing dry-run must not destroy the only saved resume matrix.
            write_json(destination.with_name(f'{study}-proposed-plan.json'),result)
            return result
    write_json(destination, result)
    return result


def publish(root, ledger):
    rows = []
    for job in ledger['jobs'].values():
        if job.get('status') != 'succeeded':
            continue
        completed(root, job)
        run = load_run(root, inside(root, job['config']), require_eval=True)
        common_path = run['paths']['metrics'] / 'common-metrics.json'
        common = read_json(common_path)
        run_settings=read_json(run['paths']['logs']/'settings.json')
        tier='smoke' if job['identity']['protocol_id']=='capture-smoke-v1' else ('full' if job['identity']['budget']==run_settings['TrainIterations'] else 'pilot')
        refs = []
        for folder, names in ((run['paths']['logs'], ('manifest.json', 'provenance.json', 'settings.json', 'split.json', 'source.zip')),
                              (run['paths']['metrics'], ('evaluation.json', 'metrics.json', 'common-metrics.json'))):
            refs.extend({'path': relative(root, folder / n), 'sha256': sha256(folder / n)} for n in names)
        refs += [{'path': relative(root, run['config']), 'sha256': sha256(run['config'])},
                 {'path': relative(root, run['checkpoint']), 'sha256': run['provenance']['checkpoint_sha256']}]
        if run['provenance'].get('controller'):
            controller = run['provenance']['controller']
            refs.append({'path':controller['archive'],'sha256':controller['archive_sha256']})
        optional_export, optional_fps, throughput_ref = None, None, None
        if (run['paths']['exports'] / 'export.json').exists():
            from .contracts import validate_export
            exported = validate_export(run['paths']['exports'], run['provenance']['checkpoint_sha256'], root,
                                       read_json(run['paths']['logs'] / 'settings.json'))
            ply = next(f for f in exported['files'] if f['name'].endswith('.ply'))
            optional_export = {**ply, 'path':relative(root,run['paths']['exports']/ply['name']),
                               'record':relative(root,run['paths']['exports']/'export.json'),
                               'record_sha256':sha256(run['paths']['exports']/'export.json')}
        # Only the frozen held-out camera protocol may populate offline FPS.
        throughput = run['paths']['videos'] / digest_json(run['split']['eval'])[:16] / 'render.json'
        if throughput.exists():
            from .contracts import validate_render
            timed = validate_render(throughput.parent, run['provenance']['checkpoint_sha256'], root,
                                    read_json(run['paths']['logs'] / 'settings.json'))
            optional_fps = timed['fps']
            throughput_ref = {'path':relative(root,throughput),'sha256':sha256(throughput)}
        rows.append({**job['identity'], 'experiment_key': job['experiment_key'], 'study': job['study'],
                     'variant': 'upgrade', 'status': 'succeeded', 'run_key': run['manifest']['run_key'],
                     'tier':tier,'full_reference':tier=='full' and job['recipe']=='full-pool',
                     'config': job['config'], 'checkpoint_sha256': run['provenance']['checkpoint_sha256'],
                     'recipe': job['recipe'], 'views': job['views'], 'selection': job['selection'], 'metrics': common['metrics'],
                     'native_metrics': run['metrics']['results'], 'train_seconds': job['train_seconds'],
                     'peak_vram_mb': run['manifest']['execution_metrics']['peak_vram_mb'],
                     'checkpoint_bytes': run['checkpoint'].stat().st_size,
                     'evaluation_cpu_seconds': common['cpu_seconds'], 'offline_fps': optional_fps, 'export': optional_export,
                     'throughput': throughput_ref,
                     'features': job['selection']['features'], 'feature_schema': FEATURE_SCHEMA,
                     'split_hash': digest_json(run['split']), 'eval_cameras': run['split']['eval'],
                     'images': [{**frame, 'gt': relative(root, run['paths']['renders'] / frame['gt']),
                                 'pred': relative(root, run['paths']['renders'] / frame['pred'])} for frame in run['evaluation']['frames']],
                     'references': refs, 'provenance': run['provenance']})
    comparisons = []
    for a in rows:
        for b in rows:
            if a['recipe'] == 'uniform' and b['recipe'] == 'coverage-overlap':
                comparison = compare(a, b)
                if comparison['status'] == 'controlled-pair':
                    comparisons.append(comparison)
    from .predictor import train
    recorded_settings = read_json(run['paths']['logs'] / 'settings.json') if rows else {}
    models = [train(rows, method, budget, EVALUATOR, recorded_settings.get('PredictorMinimumGroups',4),
                    recorded_settings.get('PredictorRidgeAlpha',10)) for method, budget in sorted({(r['method'], r['budget']) for r in rows})]
    record = {'schema_version': 'capture-ui-index-1', 'created_at': utc_now(), 'runs': rows,
              'controlled_comparisons': comparisons, 'models': models,
              'forecast': {'status': 'insufficient-evidence', 'reason': 'No validated model for a new independent capture'} if not models else {'status': 'see-model-validation'},
              'audit_assets': []}
    for f in sorted((root / 'artifacts/features').glob('*/capture-features.json')):
        record['audit_assets'].append({'scene_group': read_json(f)['scene'], 'features': read_json(f),
                                       'path': relative(root, f), 'sha256': sha256(f),
                                       'coverage': relative(root, f.with_name('coverage.svg')),
                                       'coverage_sha256': sha256(f.with_name('coverage.svg'))})
    record['revision'] = digest_json({k: v for k, v in record.items() if k not in ('created_at', 'revision')})
    write_json(root / 'reports/ui-index.json', record)
    write_json(root / 'reports/study-results.json', {'runs': rows, 'controlled_comparisons': comparisons, 'models': models})
    return record


def execute(root, settings, baseline, study, resume=False, split_path=None):
    from .runtime import train, evaluate
    from .preservation import inventory, verify_source
    from .runtime import gpu_lock
    # Serialize whole queue state as well as individual GPU stages. A separate
    # lock avoids nested acquisition of the shared baseline GPU byte.
    with gpu_lock(root, {'SharedGpuLock': str(root / 'artifacts/jobs/queue.lock')}):
        return _execute(root, settings, baseline, study, resume, split_path)


def preflight(root,settings,baseline,study,split_path=None):
    """Validate the real saved graph and all subsets before unattended compute."""
    from .runtime import runtime_snapshot
    from .preservation import verify_source,inventory
    from .source_pin import activate,execution_sources,source_files,identity
    activate(root,study)
    verify_source(root,root.parent) if (root/'reports/preservation/baseline-source.json').exists() else None
    inventory(root,baseline)
    matrix=plan(root,settings,baseline,study,split_path)
    ledger_path=root/'artifacts/jobs/ledger.json'
    ledger=read_json(ledger_path) if ledger_path.exists() else {'jobs':{}}
    spec=definition(settings,study,root)
    frozen,_=capture_split(baseline,spec['Scene'],split_path)
    checked=[]
    current={j['experiment_key'] for j in matrix['jobs']}
    previous=[j for j in ledger['jobs'].values() if j['study']==study]
    if {j['experiment_key'] for j in previous}-current:
        raise ValueError('Preflight refuses a changed study identity')
    for item in matrix['jobs']:
        materialize(root,baseline,frozen,item['selection'],item['condition'])
        job=ledger['jobs'].get(item['experiment_key'],{})
        status='ready-to-train'
        if job.get('config'):
            config=inside(root,job['config'])
            logs=root/'artifacts/logs'/config.parent.relative_to(root/'artifacts/runs')
            manifest=read_json(logs/'manifest.json')
            if manifest['status']=='succeeded':
                load_run(root,config,require_eval=job.get('status')=='succeeded')
                status='validated-training-reuse'
                if job.get('status')=='succeeded': completed(root,job);status='validated-completed-reuse'
            elif (logs/'resume.json').exists():
                from .sessions import resume_source
                from .data import freeze_split
                resume_source(root,config,settings,freeze_split(root,item['condition'],settings),item['identity']['method'],
                              item['condition'],spec['Iterations'],spec['Seed'],spec['Protocol'])
                status='validated-checkpoint-resume'
        checked.append({'experiment_key':item['experiment_key'],'method':item['identity']['method'],
                        'recipe':item['recipe'],'status':status})
    if shutil.disk_usage(root).free/2**30 < settings['MinimumUpgradeFreeGiB']+matrix['storage']['estimated_new_gib']:
        raise ValueError('Preflight disk reserve insufficient after materialization')
    training_root,files,pin=execution_sources(root)
    record={'status':'passed','study':study,'checked_at':utc_now(),'jobs':checked,
            'training_source_id':identity(files),'controller_source_id':identity(source_files(root)),
            'training_source_pinned':pin is not None,'runtime_id':digest_json(runtime_snapshot())}
    write_json(root/'reports/qa'/f'{study}-preflight.json',record)
    return record


def _execute(root, settings, baseline, study, resume, split_path):
    from .runtime import train, evaluate
    from .preservation import inventory, verify_source
    verify_source(root, root.parent) if (root / 'reports/preservation/baseline-source.json').exists() else None
    inventory(root, baseline)
    matrix = plan(root, settings, baseline, study, split_path)
    needed = matrix['storage']['reserve_gib'] + matrix['storage']['estimated_new_gib']
    if matrix['storage']['free_gib'] < needed:
        raise ValueError(f'Insufficient disk reserve: need {needed:.1f} GiB before workload')
    path = root / 'artifacts/jobs/ledger.json'
    ledger = read_json(path) if path.exists() else {'schema_version': 'upgrade-queue-1', 'jobs': {}}
    # Changing source/runtime while an old study is unfinished must never silently
    # turn Resume into a different experiment with a fresh 10k schedule.
    current_keys = {j['experiment_key'] for j in matrix['jobs']}
    old_jobs = [j for j in ledger['jobs'].values() if j['study'] == study]
    if old_jobs and {j['experiment_key'] for j in old_jobs} - current_keys:
        raise ValueError('Saved study identity changed; restore recorded source/runtime/settings before Resume')
    if old_jobs and not resume:
        raise ValueError('Study already has attempts. Use -Resume')
    spec = definition(settings, study,root)
    frozen, _ = capture_split(baseline, spec['Scene'], split_path)
    for item in matrix['jobs']:
        check_stop()
        key = item['experiment_key']; job = ledger['jobs'].setdefault(key, {**item, 'study': study, 'status': 'pending', 'attempts': []})
        if completed(root, job):
            print(f'Cache hit: {key[:12]} {job["recipe"]}/{job["identity"]["method"]}', flush=True)
            continue
        trained = False
        try:
            write_json(path, ledger)
            materialize(root, baseline, frozen, item['selection'], item['condition'])
            config = inside(root, job['config']) if job.get('config') else None
            trained = False
            if config and config.exists():
                manifest = read_json(root / 'artifacts/logs' / config.parent.relative_to(root / 'artifacts/runs') / 'manifest.json')
                trained = manifest['status'] == 'succeeded'
                if trained:
                    load_run(root,config)  # Validate success before entering the GPU stage.
                if not trained and not (root / 'artifacts/logs' / config.parent.relative_to(root / 'artifacts/runs') / 'resume.json').exists():
                    config = None
            job.update(status='training' if not trained else 'evaluating', updated_at=utc_now())
            write_json(path, ledger)
            if not trained:
                session = os.environ.get('TOPIC16_SESSION_DIRECTORY')
                if session:
                    (Path(session)/'active-run.json').unlink(missing_ok=True)
                job['attempts'].append({'started_at': utc_now(), 'parent_config': relative(root, config) if config else None})
                write_json(path, ledger)
                config = train(root, settings, item['identity']['method'], item['condition'],
                               spec['Iterations'], spec['Seed'], spec['Protocol'], config)
                job['config'] = relative(root, config)
                job.update(status='evaluating'); write_json(path, ledger)
            evaluate(root, settings, config)
            common = evaluate_common(root, config)
            run = load_run(root, config, require_eval=True)
            job.update(status='succeeded', finished_at=utc_now(),
                       common_metrics_sha256=sha256(run['paths']['metrics'] / 'common-metrics.json'),
                       train_seconds=run['manifest']['execution_metrics']['wall_time_seconds'])
            job.pop('error', None); write_json(path, ledger)
            job['publication_status'] = 'pending'
            write_json(path,ledger)
            publish(root, ledger)
            job['publication_status'] = 'succeeded'
            write_json(path,ledger)
        except BaseException as error:
            if isinstance(error, SessionPaused) and error.config:
                job['config'] = relative(root, error.config)
            session = os.environ.get('TOPIC16_SESSION_DIRECTORY')
            if session and (Path(session) / 'active-run.json').exists() and not trained:
                active = read_json(Path(session) / 'active-run.json')
                if active['run_key'].split('/')[0] == item['condition'].replace(':', '-') and active['run_key'].split('/')[1] == item['identity']['method']:
                    job['config'] = active['config']
            if job.get('status') == 'succeeded':
                job.update(publication_status='failed', publication_error=str(error), updated_at=utc_now())
            else:
                job.update(status='paused' if isinstance(error, SessionPaused) else 'failed', error=str(error), updated_at=utc_now())
            write_json(path, ledger)
            raise
    verify_source(root, root.parent) if (root / 'reports/preservation/baseline-source.json').exists() else None
    inventory(root, baseline)
    index = publish(root, ledger)
    selected = [r for r in index['runs'] if r['experiment_key'] in current_keys]
    if len(selected) != len(current_keys):
        raise ValueError('Study cannot complete with missing validated jobs')
    committed=root/'reports'/study/'completion.json'
    if committed.exists():
        previous=read_json(committed)
        if previous['status']!='succeeded' or set(previous['experiment_keys'])!=current_keys:
            raise ValueError('Committed study completion differs')
        old={r['experiment_key']:r for r in previous['runs']}
        for row in selected:
            if row['experiment_key'] not in old or any(old[row['experiment_key']][k]!=row[k]
                for k in ('config','checkpoint_sha256','metrics','source_id','runtime_id','split_hash')):
                raise ValueError('Completed study evidence changed')
        return index
    rows = sorted(selected,key=lambda r:(r['recipe'],r['method']))
    report = {'schema_version':'capture-study-completion-1','study':study,'status':'succeeded',
              'finished_at':utc_now(),'expected_jobs':len(current_keys),'completed_jobs':len(rows),
              'experiment_keys':sorted(current_keys),'runs':rows,
              'controlled_comparisons':[c for c in index['controlled_comparisons']
                                       if c['left'] in {r['run_key'] for r in rows} and c['right'] in {r['run_key'] for r in rows}],
              'training_seconds_total':sum(r['train_seconds'] for r in rows),
              'evaluation_cpu_seconds_total':sum(r['evaluation_cpu_seconds'] for r in rows),
              'source_pin':os.environ.get('TOPIC16_UPGRADE_SOURCE_PIN')}
    output=root/'reports'/study
    write_json(output/'completion.json',report)
    fields=('recipe','method','views','budget','seed','psnr','ssim','lpips','train_seconds','peak_vram_mb','checkpoint_bytes','run_key')
    with (output/'results.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fields,extrasaction='ignore');writer.writeheader()
        writer.writerows({**r,**r['metrics']} for r in rows)
    write_json(root/'artifacts/jobs'/f'{study}-completion.json',{k:v for k,v in report.items() if k!='runs'})
    return index
