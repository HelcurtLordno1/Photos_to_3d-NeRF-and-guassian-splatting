"""Completed single-method delivery alongside, never instead of, the baseline."""
from topic16.contracts import read_json,sha256,inside,digest_json


def read_teacher(root, asset):
    """Publish the committed Room diagnosis separately from Gaussian results."""
    import math
    upgrade = root / 'upgrade'
    state_path = upgrade / 'artifacts/jobs/teacher/teacher-room-v1/state.json'
    if not state_path.exists(): return {'status': 'unavailable'}
    references = {r['path']: r for r in read_json(state_path).get('stages', {}).get('teacher-report', [])}
    def committed(name):
        key = 'reports/teacher-room-v1/' + name
        if key not in references: raise ValueError('Teacher diagnostic file is not committed: ' + name)
        path = inside(upgrade, key); ref = references[key]
        if sha256(path) != ref['sha256']: raise ValueError('Teacher diagnostic checksum differs')
        return path, ref['sha256']
    path, checksum = committed('report.json'); document = read_json(path)
    if (document.get('schema_version') != 'teacher-room-supplement-1' or document.get('status') != 'complete'
            or set(document.get('completed_arms', [])) != {'A', 'B', 'C'}):
        raise ValueError('Teacher diagnostic matrix is incomplete')
    selected = {r['id']: r for r in document['rows'] if r['id'] in ('historical-nerfacto', 'A', 'B', 'C')}
    if len(selected) != 4: raise ValueError('Teacher diagnostic reference or arm is missing')
    rows = []
    for key in ('historical-nerfacto', 'A', 'B', 'C'):
        row = selected[key]
        expected = {'historical-nerfacto': ('SO3xR3', 'average'), 'A': ('off', 'average'),
                    'B': ('SO3xR3', 'off'), 'C': ('off', 'off')}[key]
        if (row['camera_optimizer'], row['appearance']) != expected:
            raise ValueError('Teacher diagnostic configuration label differs')
        if len(row['per_view']) != 39: raise ValueError('Teacher diagnostic lacks39 held-out results')
        values = [row['metrics'][k] for k in ('psnr', 'ssim', 'lpips')] + [row['native_metrics']['psnr']]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise ValueError('Teacher diagnostic metrics are not finite')
        rows.append({k: row[k] for k in ('id', 'camera_optimizer', 'appearance', 'metrics', 'scope')}
                    | {'native_psnr': row['native_metrics']['psnr']})
    csv_path, csv_hash = committed('results.csv')
    return {'status': 'ready', 'rows': rows, 'report_url': asset(path, checksum), 'csv_url': asset(csv_path, csv_hash),
        'scope': 'Fresh Room Nerfacto A/B/C, seed42,30k,272train/39test. Historical on/average reference retained; one seed, no full contemporaneous2x2 interaction claim.'}


def read_final(root,asset,limits):
    upgrade=root/'upgrade';pointer=upgrade/'reports/final-index.json'
    if not pointer.exists():return {'status':'unavailable','scenes':[],'errors':[]}
    index=read_json(pointer);declaration=inside(upgrade,index['declaration'])
    if sha256(declaration)!=index['declaration_sha256']:raise ValueError('Final declaration checksum differs')
    state=read_json(inside(upgrade,index['state']));output=[];errors=[]
    def resolve(ref):
        if ref['owner'] not in ('baseline','upgrade'):raise ValueError('Unknown final reference owner')
        owner=root if ref['owner']=='baseline' else upgrade
        path=inside(owner,ref['path'])
        if sha256(path)!=ref['sha256']:raise ValueError('Final artifact checksum differs')
        return path
    def url(ref):return asset(resolve(ref),ref['sha256'])
    for ref in index['reports']:
        try:
            if ref not in [r['report'] for r in state['scenes'] if r['status']=='computed']:raise ValueError('Final UI pointer is not committed by the campaign')
            report=read_json(resolve(ref))
            if report['schema_version']!='final-scene-1' or report['status']!='computed':raise ValueError('Final scene incomplete')
            cameras=report['cameras'];models={}
            if read_json(resolve(report['split']))['eval']!=cameras:raise ValueError('Final camera declaration differs')
            for kind in ('baseline','upgrade'):
                row=report[kind];common=read_json(resolve(row['common']))
                if common['metrics']!=row['metrics'] or len(common['frames'])!=len(cameras):raise ValueError('Final metrics contradict saved common evidence')
                if (common['identity']['eval_camera_hash']!=digest_json(cameras)
                        or common['identity']['checkpoint_sha256']!=row['checkpoint_sha256']):raise ValueError('Final metric/checkpoint identity differs')
                if kind=='upgrade':
                    trained=read_json(resolve(row['result']))
                    if trained['checkpoint']['sha256']!=row['checkpoint_sha256'] or trained['ply_sha256']!=row['model']['sha256']:
                        raise ValueError('Final candidate model identity differs')
                ply=resolve(row['model']);resolve(row['config'])
                from .catalog import ply_vertices
                vertices=ply_vertices(ply)
                if vertices>limits['MaxVertices'] or ply.stat().st_size>limits['DecodeLimitBytes']:raise ValueError('Final model exceeds UI decode limits')
                frames=[{k:url(f[k]) for k in ('gt','pred')} for f in row['frames']]
                if len(frames)!=len(cameras):raise ValueError('Final image coverage incomplete')
                models[kind]={'label':row['label'],'frames':frames,'metrics':row['metrics'],
                    'training_seconds':row['training_seconds'],'gaussians':vertices,'bytes':ply.stat().st_size,
                    'run':{'run_key':report['campaign']+'/'+report['scene']+'/'+kind,
                        'config':str(resolve(row['config'])),'checkpoint_sha256':row['checkpoint_sha256'],
                        'split_hash':report['split']['sha256'],'asset':asset(ply,row['model']['sha256']),
                        'bytes':ply.stat().st_size,'vertices':vertices,'kind':'Gaussian splats',
                        'metrics':row['metrics'],'train_seconds':row['training_seconds'],
                        'peak_vram_mb':row.get('peak_cuda_allocated_bytes',0)/2**20,'offline_fps':row.get('offline_fps'),
                        'rasterize_mode':'classic','splat_encoding':'packed-ext' if kind=='upgrade' else 'packed',
                        'background_rgb':row['background'],'provenance':{'scope':row['comparison_scope']}}}
            profiles=read_json(resolve(report['profiles']));high=[];profile_notes=[]
            roi=None
            if report.get('roi'):
                lock=report['roi'];resolve(lock['lock'])
                roi={'original_target_met':lock['original_target_met']}
                for kind in ('baseline','upgrade'):
                    common=read_json(resolve(lock[kind]['common']))
                    if common['metrics']!=lock[kind]['metrics']:raise ValueError('Final ROI metrics contradict committed evidence')
                    for ref_roi in lock[kind]['files']:resolve(ref_roi)
                    roi[kind]=common['metrics']
            for model in profiles['models']:
                for item in model['profiles']:
                    if item['status']=='succeeded':
                        path=inside(upgrade,item['path'])
                        if sha256(path)!=item['sha256']:raise ValueError('Final large-output pixels changed')
                        high.append({'model':model['id'],'edge':item['identity']['long_edge'],'view':item['identity']['view'],
                            'width':item['identity']['width'],'height':item['identity']['height'],'url':asset(path,item['sha256']),
                            'render_seconds':item['render_seconds'],'peak_cuda_allocated_bytes':item['peak_cuda_allocated_bytes']})
                    else:profile_notes.append({'model':model['id'],'edge':item['identity']['long_edge'],'reason':item.get('reason','unsupported')})
            output.append({'scene':report['scene'],'campaign':report['campaign'],'cameras':cameras,
                'train_count':report['train_count'],'eval_count':report['eval_count'],'models':models,
                'delta':report['delta'],'per_view_delta':report['per_view_delta'],'quality_dominates':report['quality_dominates'],
                'browser':report['browser'],'preview_verdict':report['preview_verdict'],'high_resolution':high,
                'profile_notes':profile_notes,'scope':report['scope'],'report_url':url(ref)})
            output[-1]['roi']=roi
        except (ValueError,KeyError,OSError,TypeError) as error:errors.append({'report':ref.get('path'),'reason':str(error)})
    files={}
    for ref in state.get('stages',{}).get('campaign-report',[]):
        path=inside(upgrade,ref['path'])
        if sha256(path)!=ref['sha256']:raise ValueError('Final aggregate report changed')
        files[path.name]=asset(path,ref['sha256'])
    try: teacher = read_teacher(root, asset)
    except (ValueError, KeyError, OSError, TypeError) as error:
        teacher = {'status': 'invalid', 'reason': str(error)}
    return {'status':'ready' if output else 'pending','study':index['study'],'phase':state['phase'],
            'campaign_status':state['status'],'scenes':output,'errors':errors,'files':files,'teacher_room':teacher}
