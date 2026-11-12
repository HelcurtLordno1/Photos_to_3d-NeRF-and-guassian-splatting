"""Publish versioned inference and official-backend research, without GPU imports."""
from topic16.contracts import read_json,sha256,inside


def read_research(root,asset,limits):
    upgrade=root/'upgrade'
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
    return result
