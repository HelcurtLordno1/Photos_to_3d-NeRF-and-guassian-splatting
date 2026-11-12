"""Publish versioned inference and official-backend research, without GPU imports."""
from topic16.contracts import read_json,sha256,inside


def read_research(root,asset,limits):
    upgrade=root/'upgrade'
    pointer_path=upgrade/'reports/confirmation-index.json'
    confirmation_pointer=read_json(pointer_path) if pointer_path.exists() else None
    if confirmation_pointer:
        declared=inside(upgrade,confirmation_pointer['declaration'])
        if sha256(declared)!=confirmation_pointer['declaration_sha256']:raise ValueError('Confirmation declaration checksum differs')
        study=read_json(declared)['spec']['ReferenceStudy']
    else:
        study=next((s for s in ('tea-research-v4','tea-research-v3') if (upgrade/'artifacts/jobs/research'/s/'state.json').exists()),'tea-research-v3')
    directory=upgrade/'artifacts/jobs/research'/study
    if not (directory/'state.json').exists():return {'status':'unavailable','q15':[],'q2':None}
    state=read_json(directory/'state.json')
    if sha256(directory/'declaration.json')!=state['declaration_sha256']:
        raise ValueError('Visual research declaration changed')
    stages=state['stages'];result={'study':study,'status':state['status'],'phase':state['phase'],'q15':[],'q2':None}
    def verified(key):
        for ref in stages[key]['references']:
            if sha256(inside(upgrade,ref['path']))!=ref['sha256']:raise ValueError('Visual research evidence changed')
    def frames(directory,rows):
        output=[]
        for frame in rows:
            row={}
            for kind in ('gt','pred'):
                path=inside(upgrade,directory/frame[kind])
                if sha256(path)!=frame[kind+'_sha256']:raise ValueError('Visual research image changed')
                row[kind]=asset(path,frame[kind+'_sha256'])
            output.append(row)
        return output
    if 'q15' in stages:
        verified('q15')
        report=read_json(inside(upgrade,stages['q15']['references'][0]['path']))
        for row in report['rows']:
            path=inside(upgrade,row['path']);common=inside(upgrade,row['common'])
            if sha256(path)!=row['sha256'] or sha256(common)!=row['common_sha256']:
                raise ValueError('Multi-scale evidence changed')
            rendered=read_json(path);scored=read_json(common)
            if scored['identity']!=rendered['identity'] or scored['metrics']!=row['metrics']:
                raise ValueError('Multi-scale metrics contradict render identity')
            result['q15'].append({**row,'frames':frames(path.parent,rendered['frames'])})
    if 'report' in stages:
        verified('report')
        report=read_json(upgrade/'reports'/study/'report.json')
        declaration=read_json(directory/'declaration.json')
        split=read_json(inside(upgrade,declaration['split']))
        for row in report['rows']:
            verified('full-'+row['method'])
            path=inside(upgrade,row['result']);record=read_json(path)
            common=inside(upgrade,row['common'])
            if (sha256(path)!=row['result_sha256'] or sha256(common)!=row['common_sha256']
                    or read_json(common)['metrics']!=row['metrics']
                    or sha256(path.parent/record['checkpoint']['path'])!=record['checkpoint']['sha256']):
                raise ValueError('Official-backend result changed')
            row['frames']=frames(path.parent,record['frames'])
            ply=path.parent/'model.ply'
            from .catalog import ply_vertices
            count=ply_vertices(ply)
            if sha256(ply)!=record['ply_sha256']:raise ValueError('Official model PLY changed')
            if count<=limits['MaxVertices'] and ply.stat().st_size<=limits['DecodeLimitBytes']:
                row['model']={'id':study+'-'+row['method'],'label':'Q2 '+row['method'],'cameras':split['eval'],
                    'run':{'run_key':study+'/'+row['method'],'config':str(path.parent/'resolved-config.json'),
                           'checkpoint_sha256':record['checkpoint']['sha256'],'split_hash':declaration['split_sha256'],
                           'asset':asset(ply,record['ply_sha256']),'bytes':ply.stat().st_size,'vertices':count,
                           'kind':row['method']+' Gaussian splats','display_label':'Q2 '+row['method'],
                           'rasterize_mode':'classic','background_rgb':[0.,0.,0.],'metrics':row['metrics'],'train_seconds':row['training_seconds'],
                           'peak_vram_mb':row['peak_cuda_allocated_bytes']/2**20,'offline_fps':row['offline_fps'],
                           'provenance':{'scope':report['scope'],'comparison':report['comparison']}}}
        result['q2']=report
    if confirmation_pointer:
        current=read_json(inside(upgrade,confirmation_pointer['state']))
        result['confirmation']={k:current.get(k) for k in ('study','status','phase','jobs','gpu_stage_wall_seconds','error')}
        inspection_path=inside(upgrade,confirmation_pointer['inspection'])
        if inspection_path.exists():
            proof=next((refs[0] for key,refs in current['stages'].items() if key.startswith('inspection-')
                        and refs and inside(upgrade,refs[0]['path'])==inspection_path),None)
            if proof is None:raise ValueError('Inspection has no committed stage')
            if sha256(inspection_path)!=proof['sha256']:raise ValueError('Inspection report changed')
            inspection=read_json(inspection_path)
            cells=[]
            for method in inspection['results']:
                for cell in method['cells']:
                    path=inside(upgrade,cell['path']);common=inside(upgrade,cell['common'])
                    if sha256(path)!=cell['sha256'] or sha256(common)!=cell['common_sha256']:
                        raise ValueError('Inspection metric/render changed')
                    cells.append({**cell,'method':method['method'],'frames':frames(path.parent,read_json(path)['frames'])})
            encoding=inspection.get('viewer_encoding','packed')
            result['inspection']={'status':inspection['status'],'checks':inspection['checks'],'cells':cells,
                'viewer_encoding':encoding,'browser':[{'method':r['method'],
                    'mean_parity_db':sum(x['psnr'] for x in r['browser']['results'])/len(r['browser']['results']),
                    'minimum_parity_db':min(x['psnr'] for x in r['browser']['results']),
                    'p95_frame_interval_ms':r['browser']['benchmark']['p95_frame_interval_ms']} for r in inspection['results']]}
            if inspection['status']=='passed' and encoding in ('ext32-full','packed-ext') and result['q2']:
                for row in result['q2']['rows']:
                    if 'model' in row:row['model']['run']['splat_encoding']=encoding
        final=inside(upgrade,confirmation_pointer['report'])
        if final.exists():
            proof=current['stages']['report'][0]
            if sha256(final)!=proof['sha256']:raise ValueError('Seed report changed')
            result['confirmation_report']=read_json(final)
    return result
