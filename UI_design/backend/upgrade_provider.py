"""CPU-only adapter for Capture Intelligence; no training imports in HTTP."""
from pathlib import Path
import math
from topic16.contracts import read_json, sha256, inside, digest_json


def read_upgrade(root: Path):
    upgrade = inside(root, root / 'upgrade')
    path = upgrade / 'reports/ui-index.json'
    if not path.exists():
        return None
    index = read_json(path)
    if index.get('schema_version') != 'capture-ui-index-1':
        raise ValueError('Unsupported upgrade index schema')
    seen = set()
    for run in index['runs']:
        if run['experiment_key'] in seen:
            raise ValueError('Duplicate upgrade experiment identity')
        seen.add(run['experiment_key'])
        if run['status'] != 'succeeded' or run['variant'] != 'upgrade' or run['method'] not in ('nerfacto', 'splatfacto'):
            raise ValueError('Only completed identified upgrade runs may be published')
        references = {item['path']: item['sha256'] for item in run['references']}
        for name, expected in references.items():
            if sha256(inside(upgrade, name)) != expected:
                raise ValueError(f'Upgrade evidence checksum mismatch: {name}')
        logs = 'artifacts/logs/' + run['run_key']
        metrics_dir = 'artifacts/metrics/' + run['run_key']
        required = [logs + '/' + n for n in ('manifest.json', 'provenance.json', 'settings.json', 'split.json', 'source.zip')]
        required += [metrics_dir + '/' + n for n in ('evaluation.json', 'common-metrics.json', 'metrics.json')]
        required += [run['config']]
        if not all(name in references for name in required):
            raise ValueError('Upgrade index lacks verified required evidence')
        manifest = read_json(inside(upgrade, logs + '/manifest.json'))
        provenance = read_json(inside(upgrade, logs + '/provenance.json'))
        split = read_json(inside(upgrade, logs + '/split.json'))
        evaluation = read_json(inside(upgrade, metrics_dir + '/evaluation.json'))
        common = read_json(inside(upgrade, metrics_dir + '/common-metrics.json'))
        checkpoint = provenance['checkpoint_path']
        sources = {k:v for k,v in provenance['source_files'].items() if Path(k).suffix in ('.py','.ps1','.psd1')}
        import zipfile
        archive = inside(upgrade, logs + '/source.zip')
        if sha256(archive) != provenance['source_archive_sha256']:
            raise ValueError('Upgrade source snapshot checksum mismatch')
        with zipfile.ZipFile(archive) as snapshot:
            import hashlib
            if set(snapshot.namelist()) != set(provenance['source_files']):
                raise ValueError('Upgrade source snapshot file list mismatch')
            for name, expected in provenance['source_files'].items():
                if hashlib.sha256(snapshot.read(name)).hexdigest() != expected:
                    raise ValueError('Upgrade source snapshot bytes mismatch')
        if provenance.get('controller'):
            controller = provenance['controller']
            if references.get(controller['archive']) != controller['archive_sha256']:
                raise ValueError('Repaired controller lacks its source archive reference')
            controller_files = {k:v for k,v in controller['source_files'].items() if Path(k).suffix in ('.py','.ps1','.psd1')}
            if digest_json(controller_files) != controller['source_id']:
                raise ValueError('Repaired controller source identity differs')
            with zipfile.ZipFile(inside(upgrade,controller['archive'])) as snapshot:
                if set(snapshot.namelist()) != set(controller['source_files']):
                    raise ValueError('Repaired controller archive member list differs')
                for name, expected in controller['source_files'].items():
                    if hashlib.sha256(snapshot.read(name)).hexdigest() != expected:
                        raise ValueError('Repaired controller archive bytes differ')
        policy = read_json(inside(upgrade, logs + '/settings.json'))
        safety_id = digest_json({k:v for k,v in policy.items() if k.startswith('Gpu')})
        if digest_json(sources) != run['source_id'] or safety_id != run['safety_id']:
            raise ValueError('Upgrade source or safety identity differs from provenance')
        for safety_path in (provenance['gpu_safety_path'], evaluation['gpu_safety_path']):
            safety = read_json(inside(upgrade / 'artifacts/logs/safety', inside(upgrade, safety_path)))
            if safety['status'] != 'succeeded' or digest_json(safety['policy']) != safety_id:
                raise ValueError('Upgrade GPU stage lacks completed safe telemetry')
        if references.get(checkpoint) != run['checkpoint_sha256'] or provenance['checkpoint_sha256'] != run['checkpoint_sha256']:
            raise ValueError('Upgrade checkpoint reference mismatch')
        protocol = manifest['protocol']
        if (manifest['status'] != 'succeeded' or evaluation['status'] != 'succeeded'
                or protocol['iterations'] != run['budget'] or protocol['seed'] != run['seed']
                or protocol['downscale_factor'] != run['downscale'] or manifest['method'] != run['method']
                or digest_json(split) != run['split_hash'] or evaluation['split_hash'] != run['split_hash']
                or common['identity']['evaluator_id'] != run['evaluator_id']
                or common['identity']['runtime_id'] != run['runtime_id']
                or common['identity']['evaluation_sha256'] != references[metrics_dir + '/evaluation.json']
                or provenance['runtime_sha256'] != run['runtime_id'] or common['metrics'] != run['metrics']
                or split['capture']['eval_camera_hash'] != run['eval_camera_hash']
                or split['capture']['scene_group'] != run['scene_group']
                or split['capture']['selection_id'] != run['selection_id']):
            raise ValueError('Upgrade index contradicts its immutable run evidence')
        for name in ('psnr', 'ssim', 'lpips'):
            value = run['metrics'][name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Missing/nonfinite upgrade metric')
        if run['eval_cameras'] != split['eval'] or len(run['images']) != len(split['eval']):
            raise ValueError('Upgrade held-out camera list mismatch')
        export = run.get('export')
        if export:
            from topic16.contracts import validate_export
            record = inside(upgrade, export['record'])
            if sha256(record) != export['record_sha256']:
                raise ValueError('Upgrade export record changed')
            validate_export(record.parent, run['checkpoint_sha256'], upgrade, policy)
            if sha256(inside(upgrade, export['path'])) != export['sha256']:
                raise ValueError('Upgrade export asset changed')
        if run.get('offline_fps') is not None:
            from topic16.contracts import validate_render
            timed_path = inside(upgrade, run['throughput']['path'])
            if sha256(timed_path) != run['throughput']['sha256']:
                raise ValueError('Upgrade throughput record changed')
            timed = validate_render(timed_path.parent,run['checkpoint_sha256'],upgrade,policy)
            if timed['fps'] != run['offline_fps'] or timed['camera_sha256'] != digest_json(split['eval']):
                raise ValueError('Upgrade FPS uses a different camera measurement scope')
        for image, evidence in zip(run['images'], evaluation['frames']):
            for kind in ('gt', 'pred'):
                expected_path = 'artifacts/renders/' + run['run_key'] + '/' + evidence[kind]
                if image[kind] != expected_path or image[kind + '_sha256'] != evidence[kind + '_sha256']:
                    raise ValueError('Upgrade saved image reference mismatch')
                if sha256(inside(upgrade, image[kind])) != image[kind + '_sha256']:
                    raise ValueError('Upgrade saved image changed')
    for audit in index.get('audit_assets', []):
        for path_field, hash_field in (('path', 'sha256'), ('coverage', 'coverage_sha256')):
            if sha256(inside(upgrade, audit[path_field])) != audit[hash_field]:
                raise ValueError('Upgrade capture audit changed')
        if read_json(inside(upgrade, audit['path'])) != audit['features']:
            raise ValueError('Embedded audit differs from its source')
    by_key = {r['run_key']:r for r in index['runs']}
    matched_fields = ('scene_group','method','budget','seed','downscale','source_id',
                      'runtime_id','evaluator_id','eval_camera_hash','safety_id','pool_hash','views')
    for comparison in index.get('controlled_comparisons', []):
        left, right = by_key[comparison['left']], by_key[comparison['right']]
        if (comparison['status'] != 'controlled-pair' or left['recipe'] != 'uniform'
                or right['recipe'] != 'coverage-overlap'
                or any(k not in left or k not in right or left[k] != right[k] for k in matched_fields)
                or any(comparison['delta'][k] != right['metrics'][k] - left['metrics'][k] for k in ('psnr','ssim','lpips'))):
            raise ValueError('Controlled comparison contradicts its matched experiment evidence')
    return index


def merge_upgrade(root, scenes, asset, ui_settings=None):
    # One malformed source is isolated without weakening baseline validation.
    try:
        index = read_upgrade(root)
    except (ValueError, KeyError, OSError, TypeError) as error:
        return {'status': 'invalid', 'reason': str(error), 'runs': [], 'audits': [], 'models': []}
    if index is None:
        return {'status': 'unavailable', 'reason': 'No completed upgrade index', 'runs': [], 'audits': [], 'models': []}
    from PIL import Image, ImageChops
    groups, rows = {}, []
    upgrade = root / 'upgrade'
    for row in index['runs']:
        if row.get('protocol_id')=='capture-smoke-v1' or row.get('tier')=='smoke':
            continue
        group_id = digest_json({key: row[key] for key in ('scene_group', 'selection_id', 'budget', 'seed', 'downscale', 'source_id', 'runtime_id', 'evaluator_id', 'safety_id')})
        groups.setdefault(group_id, {})[row['method']] = row
        rows.append(row)
    by_scene = {s['id']: s for s in scenes}
    for group_id, methods in groups.items():
        if set(methods) != {'nerfacto', 'splatfacto'}:
            continue  # Single completed jobs appear in the benchmark, never as a paired result.
        n, splat = methods['nerfacto'], methods['splatfacto']
        if n['eval_cameras'] != splat['eval_cameras']:
            raise ValueError('Upgrade pair camera frame mismatch')
        views = []
        for i, camera in enumerate(n['eval_cameras']):
            if n['images'][i]['gt_sha256'] != splat['images'][i]['gt_sha256']:
                raise ValueError('Upgrade pair GT pixel mismatch')
            view = {'index': i, 'source': n['images'][i]['source'], 'camera': camera, 'gt_sha256': n['images'][i]['gt_sha256'],
                    'gt': asset(upgrade / n['images'][i]['gt'], n['images'][i]['gt_sha256'])}
            for method, row in methods.items():
                frame = row['images'][i]
                view[method] = asset(upgrade / frame['pred'], frame['pred_sha256'])
                error = root / 'artifacts/ui/images/upgrade' / group_id / f'{method}-{i:04d}-error.png'
                error.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(upgrade / frame['gt']) as gt, Image.open(upgrade / frame['pred']) as pred:
                    if gt.size != pred.size or gt.size != (camera['width'], camera['height']):
                        raise ValueError('Upgrade image size differs from frozen camera')
                    ImageChops.difference(gt.convert('RGB'), pred.convert('RGB')).point(lambda v: min(255, v*4)).save(error)
                view[method + '_error'] = asset(error)
            views.append(view)
        run_methods = {m: {'run_key': r['run_key'], 'config': 'upgrade/' + r['config'],
                          'checkpoint_sha256': r['checkpoint_sha256'], 'split_hash': r['split_hash'],
                          'asset': '', 'bytes': 0, 'kind': 'Saved evaluation; no pilot export',
                          'metrics': r['metrics'], 'train_seconds': r['train_seconds'],
                          'peak_vram_mb': r['peak_vram_mb'], 'offline_fps': None,
                          'checkpoint_bytes': r['checkpoint_bytes'], 'provenance': r['provenance'],
                          'budget': r['budget'], 'seed': r['seed'], 'downscale': r['downscale'],
                          'evaluator_id': r['evaluator_id'], 'variant': 'upgrade'} for m, r in methods.items()}
        runset = {'id': group_id, 'variant': 'upgrade', 'label': f'{n["recipe"]} · {n["views"]} views · {n["budget"]:,} steps · seed {n["seed"]}',
                  'study': n['study'], 'recipe': n['recipe'], 'budget': n['budget'], 'seed': n['seed'],
                  'downscale': n['downscale'], 'evaluator_id': n['evaluator_id'], 'eval_camera_hash': n['eval_camera_hash'],
                  'train_count': n['views'], 'eval_count': len(views), 'methods': run_methods, 'views': views,
                  'inference': False, 'inference_reason': 'Upgrade novel-camera worker has not been verified; saved images and metrics are available'}
        runset['tier']=n.get('tier','full' if n.get('protocol_id')=='capture-confirm-30k-v1' else 'pilot')
        runset['full_reference']=bool(n.get('full_reference',runset['tier']=='full' and n['recipe']=='full-pool'))
        for method, row in methods.items():
            if method=='splatfacto':
                import yaml
                config=yaml.load((upgrade/row['config']).read_text(encoding='utf-8'),Loader=yaml.BaseLoader)
                # Fixtures may not contain a full Nerfstudio config; never guess
                # a rendering protocol when it is absent in imported evidence.
                if isinstance(config,dict):
                    mode=config.get('pipeline',{}).get('model',{}).get('rasterize_mode')
                    if mode in ('classic','antialiased'):run_methods[method]['rasterize_mode']=mode
            exported = row.get('export')
            if exported:
                from .catalog import ply_vertices
                ply_path = upgrade / exported['path']
                count = ply_vertices(ply_path)
                # Oversized assets do not remove valid image/metric evidence.
                limits = ui_settings or {}
                if count <= limits.get('MaxVertices',0) and exported['bytes'] <= limits.get('DecodeLimitBytes',0):
                    run_methods[method].update(asset=asset(ply_path,exported['sha256']),bytes=exported['bytes'],vertices=count,
                        kind='point-cloud proxy' if method=='nerfacto' else 'Gaussian splats · browser renderer')
            run_methods[method]['offline_fps'] = row.get('offline_fps')
        scene = by_scene.get(n['scene_group'])
        if scene is None:
            scene = {'id': n['scene_group'], 'title': n['scene_group'].replace('custom:', '').replace('_', ' ').title(),
                     'subtitle': 'Capture Intelligence · controlled selection study', 'scope': 'upgrade',
                     'alignment': 'Frozen canonical camera frame; known-camera / transductive SfM',
                     'source_matrix': 'upgrade/reports/ui-index.json', 'cover': views[0]['gt'],
                     **{k: runset[k] for k in ('train_count', 'eval_count', 'methods', 'views', 'inference')},
                     'run_sets': [], 'default_run_set': group_id}
            scenes.append(scene); by_scene[scene['id']] = scene
        scene['run_sets'].append(runset)
    # Historical metric derivatives are read-only CPU reports produced by the
    # managed full campaign, never recomputed or imported from training in HTTP.
    for scene in scenes:
        base=next((s for s in scene.get('run_sets',[]) if s['variant']=='baseline'),None)
        historical=upgrade/'reports/full/historical'/scene['id'].replace(':','-')/'index.json'
        if base and historical.exists():
            record=read_json(historical)
            if record['schema_version']!='historical-common-1' or record['scene']!=scene['id']:
                raise ValueError('Historical common evaluator index differs')
            for row in record['rows']:
                method=row['method'];run=base['methods'][method]
                report=inside(upgrade,row['common_report'])
                scored=read_json(report)
                if (run['run_key']!=row['run_key'] or base['eval_camera_hash']!=row['eval_camera_hash']
                    or sha256(report)!=row['common_sha256'] or scored['metrics']!=row['metrics']
                    or sha256(inside(root,row['evaluation']))!=row['evaluation_sha256']
                    or sha256(inside(root,row['config']))!=row['config_sha256']
                    or run['checkpoint_sha256']!=row['checkpoint_sha256']
                    or scored['status']!='succeeded'
                    or scored['identity']['evaluation_sha256']!=row['evaluation_sha256']
                    or scored['identity']['config_sha256']!=row['config_sha256']
                    or scored['identity']['checkpoint_sha256']!=row['checkpoint_sha256']
                    or scored['identity']['evaluator_id']!=row['evaluator_id']):
                    raise ValueError('Historical common metrics contradict baseline evidence')
                run['common_metrics']=row['metrics'];run['common_evaluator_id']=row['evaluator_id']
    audits = []
    for audit in index.get('audit_assets', []):
        previews = []
        capture_root = inside(root, Path(audit['features']['provenance']['input_root']))
        for frame in audit['features']['frames']:
            source = inside(capture_root, frame['path'])
            thumb = root / 'artifacts/ui/images/capture' / audit['features']['pool_hash'] / f'{frame["index"]:05d}.webp'
            thumb.parent.mkdir(parents=True, exist_ok=True)
            if not thumb.exists():
                if sha256(source) != frame['sha256']:
                    raise ValueError('Capture thumbnail source changed')
                with Image.open(source) as image:
                    image.thumbnail((180,180)); image.convert('RGB').save(thumb,'WEBP',quality=75)
            previews.append({'index':frame['index'],'url':asset(thumb)})
        audits.append({**audit,'coverage_url':asset(upgrade / audit['coverage'],audit['coverage_sha256']), 'previews':previews})
    return {'status': 'ready', 'revision': index['revision'], 'runs': rows, 'audits': audits,
            'models': index['models'], 'controlled_comparisons': index['controlled_comparisons']}
