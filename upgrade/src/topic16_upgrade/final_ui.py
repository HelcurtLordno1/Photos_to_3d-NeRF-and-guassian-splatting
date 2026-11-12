"""Finish delivery only after actual production UI navigation and model loading."""
from pathlib import Path
import shutil
import time
import zipfile
from .contracts import read_json,write_json,sha256,inside,relative,utc_now
from .final_campaign import prepare,publish_index
from .final_stages import Stages
from .source_pin import verify_pin
from .sessions import SessionPaused


def check(root,settings,study):
    state=prepare(root,settings,study);directory=root/'artifacts/jobs/final'/study
    doc=read_json(directory/'declaration.json');_,tree=verify_pin(root,inside(root,doc['source_pin']),study)
    stages=Stages(root,settings,directory,state,tree)
    for key in list(state['stages']):stages.done(key)
    if not stages.done('campaign-report') or len(state['scenes'])!=5:raise ValueError('All five scene reports must complete before final UI acceptance')
    if not stages.done('ui-check'):
        catalog=read_json(root.parent/'artifacts/ui/catalog.json')['catalog'];delivery=catalog.get('final_delivery',{})
        if len(delivery.get('scenes',[]))!=5 or delivery.get('errors'):raise ValueError('Final UI catalog is incomplete or invalid')
        titles={s['id']:s['title'] for s in catalog['scenes']}
        target=root/'reports'/study/'ui'/str(time.time_ns());target.mkdir(parents=True)
        server=read_json(root.parent/'artifacts/ui/server.json')
        job={'url':server['url'],'output':str(target),'scenes':[{**s,'title':titles[s['scene']]} for s in delivery['scenes']]}
        write_json(target/'job.json',job)
        sources=[root.parent/'UI_design/frontend'/name for name in ('FinalQuality.tsx','Viewer.tsx','main.tsx','types.ts','cameraProjection.ts')]
        sources += [root.parent/'UI_design/backend/final_provider.py',root.parent/'UI_design/backend/catalog.py',root.parent/'UI_design/tests/final-browser.mjs']
        sources += [p for p in (root.parent/'UI_design/dist').rglob('*') if p.is_file()]
        archive=target/'ui-source.zip'
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
            for p in sources:z.write(p,relative(root.parent,p))
        manifest={relative(root.parent,p):sha256(p) for p in sources};write_json(target/'ui-source.json',manifest)
        node=shutil.which('node.exe') or 'C:/Program Files/nodejs/node.exe'
        try:
            safety=stages.guarded('ui-check',[node,str(root.parent/'UI_design/tests/final-browser.mjs'),str(target/'job.json')],target/'console.log')
            if any(sha256(root.parent/name)!=value for name,value in manifest.items()):raise ValueError('UI source/build changed during acceptance')
            result=read_json(target/'browser-check.json')
            if result['status']!='passed' or len(result['scenes'])!=5:raise ValueError('Final UI acceptance failed')
            stages.commit('ui-check',[target/'browser-check.json',target/'job.json',archive,target/'ui-source.json',safety]+sorted(target.glob('*.png')))
        except BaseException as error:
            state.update(status='paused' if isinstance(error,SessionPaused) else 'failed',phase='ui-review',error=str(error));stages.save();raise
    completion={'schema_version':'final-completion-1','status':'succeeded','study':study,
        'computed_report':state['stages']['campaign-report'][0],'ui_acceptance':state['stages']['ui-check'][0],
        'scene_reports':[s['report'] for s in state['scenes']],'scope':'Measured experimental delivery; original baselines retained. Negative metrics/profiles remain visible; no production or SOTA certification.',
        'finished_at':utc_now()}
    output=root/'reports'/study
    if not stages.done('completion'):
        write_json(output/'completion.json',completion)
        text=['# Final quality campaign — completed','',completion['scope'],'',
            'All five scenes have preserved-baseline / selected-upgrade native comparisons, exact exports and real UI loading checks.',
            'See report.json for scene deltas/costs, capacity-selection.json for the TRAIN-only decision, and each scenes/*/report.md for losses.',
            '4K/8K are large-buffer renders from existing weights, not new source detail; unsupported profiles are explicitly recorded.',
            'GPU allocator, total device residency, historical wall time and browser timing use different scopes; do not conflate them.',
            'Original report folders stay local; source and execution plans are in Git.','',
            'UI acceptance: '+state['stages']['ui-check'][0]['path']]
        (output/'completion.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
        stages.commit('completion',[output/'completion.json',output/'completion.md'])
    state.update(status='succeeded',phase='complete',finished_at=utc_now());state.pop('error',None);stages.save();publish_index(root,directory,state)
    return state
