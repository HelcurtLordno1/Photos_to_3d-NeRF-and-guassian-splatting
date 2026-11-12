"""Measure saved classic checkpoint vs Spark, before any new training."""
from .contracts import read_json,write_json,sha256,relative,inside,load_run,utc_now
from .quality import references


def measure(root,settings,baseline,split):
    from .runtime import gpu_lock,run_command
    import shutil
    output=root/'reports/tea-quality-v2/q0';result=output/'parity.json'
    sources=[baseline/'UI_design/qa/tea-parity.ts',baseline/'UI_design/qa/tea-parity.html',root/'scripts/qa/measure-viewer.mjs']
    source_refs=[{'path':relative(baseline,p),'sha256':sha256(p)} for p in sources]
    if result.exists():
        saved=read_json(result)
        if saved['source_references']!=source_refs:raise ValueError('Renderer audit source changed')
        for item in saved['references']:
            if sha256(inside(root,item['path']))!=item['sha256']:raise ValueError('Renderer proof changed')
        return result
    _,owner,config=references(root,baseline)[1];run=load_run(owner,config,require_eval=True)
    export=read_json(run['paths']['exports']/'export.json');ply=run['paths']['exports']/export['files'][0]['name']
    indices=[0,10,13]
    job={'ply':str(ply),'indices':indices,'cameras':[run['split']['eval'][i] for i in indices],
         'native':[str(run['paths']['renders']/f'pred_{i:04d}.png') for i in indices],'output':str(output)}
    write_json(output/'browser-job.json',job)
    node=shutil.which('node.exe') or shutil.which('node')
    if not node:raise ValueError('Pinned UI Node runtime is missing')
    with gpu_lock(root,settings):run_command(root,[node,str(root/'scripts/qa/measure-viewer.mjs'),str(output/'browser-job.json')],output/'browser.log')
    browser=read_json(output/'browser-result.json')
    before=[r['psnr'] for r in browser['results'] if r['preset']=='spark-default']
    after=[r['psnr'] for r in browser['results'] if r['preset']=='classic-compatible']
    refs=[{'path':relative(root,p),'sha256':sha256(p)} for p in [output/'browser-result.json',*[output/f'{mode}-{i}.png' for i in indices for mode in ('spark-default','classic-compatible')]]]
    record={'status':'measured','finished_at':utc_now(),'source_references':source_refs,'references':refs,
            'mean_native_psnr_before':sum(before)/len(before),'mean_native_psnr_classic':sum(after)/len(after),
            'scope':'Renderer agreement with fixed native PNG, not reconstruction quality against GT; no claim of renderer equality',
            'decision':'Q1 is a native model resolution experiment evaluated through CUDA; viewer preset changes require separate review',
            'browser':browser}
    write_json(result,record);return result
