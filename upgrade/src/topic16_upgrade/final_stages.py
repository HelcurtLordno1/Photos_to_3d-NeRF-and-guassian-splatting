"""Hashed stages for the single-winner campaign; computation survives publish errors."""
from pathlib import Path
import copy
import os
import threading
import time
from .contracts import read_json,write_json,sha256,digest_json,inside,relative,utc_now
from .sessions import check_stop,SessionPaused


class Stages:
    def __init__(self,root,settings,directory,state,tree):
        self.root=root;self.settings=settings;self.directory=directory;self.state=state;self.tree=tree
        self.host=read_json(root/'artifacts/logs/host.json')

    def save(self,phase=None):
        if phase:
            if phase!=self.state.get('phase'):print('[final] '+self.state['study']+' | '+phase,flush=True)
            self.state.update(status='running',phase=phase,updated_at=utc_now());self.state.pop('error',None)
        write_json(self.directory/'state.json',self.state)

    def done(self,key):
        if key not in self.state['stages']:return False
        for ref in self.state['stages'][key]:
            if sha256(inside(self.root,ref['path']))!=ref['sha256']:raise ValueError('Final stage evidence changed: '+key)
        return True

    def commit(self,key,paths):
        if self.done(key):return
        self.state['stages'][key]=[{'path':relative(self.root,p),'sha256':sha256(p)} for p in paths];self.save()

    def guarded(self,key,command,log,cooperative=False):
        from .runtime import gpu_lock,run_command
        from .safety import current_guard
        check_stop();self.save(key);clock=time.monotonic()
        session=Path(os.environ['TOPIC16_SESSION_DIRECTORY'])
        remaining=self.settings['Final']['MaximumCampaignSeconds']-self.state.get('stage_wall_seconds',0)
        if remaining<=0:raise SessionPaused('Final campaign declared compute budget exhausted')
        limit=remaining if cooperative else min(remaining,1800)
        timer=threading.Timer(limit,lambda:write_json(session/'stop.json',{'requested':True,'reason':'final-stage-budget'}))
        timer.daemon=True;timer.start();attempt=None
        try:
            with gpu_lock(self.root,self.settings):
                guard=current_guard();safety=guard.path
                attempt={'key':key,'safety':relative(self.root,safety),'command_sha256':digest_json(command),'started_at':utc_now()}
                self.state.setdefault('attempts',[]).append(attempt);self.save()
                stop_observer=threading.Event()
                guard.record['observed_peaks']={'samples':0,'values':{},
                    'scope':'Maxima of watchdog samples observed by this monitor; not instantaneous peaks between queries.'}
                def observe():
                    previous=None;values={};count=0
                    while not stop_observer.is_set():
                        sample=guard.record.get('last_sample',guard.record.get('first_sample',{}))
                        if sample is not previous:
                            previous=sample;count+=1
                            values={k:max(values.get(k,float('-inf')),sample[k]) for k in
                                    ('temperature.gpu','clocks.gr','memory.used','power.draw') if k in sample}
                            guard.record['observed_peaks']={'samples':count,'values':values,
                                'scope':'Maxima of watchdog samples observed by this monitor; not instantaneous peaks between queries.'}
                        stop_observer.wait(.2)
                observer=threading.Thread(target=observe,daemon=True);observer.start()
                try:
                    run_command(self.root,command,log,cooperative_training=cooperative,
                                environment_overrides={'MKL_THREADING_LAYER':'SEQUENTIAL'})
                finally:stop_observer.set();observer.join(timeout=2)
            attempt.update(status='succeeded',finished_at=utc_now());return safety
        finally:
            timer.cancel();self.state['stage_wall_seconds']=self.state.get('stage_wall_seconds',0)+time.monotonic()-clock;self.save()

    def leaf(self,label,split_path,budget,base_spec,probe=False):
        from .source_pin import verify_pin
        root=self.root;spec=copy.deepcopy(base_spec)
        spec.update(Study=self.state['study']+'-'+label,Scene=read_json(split_path)['scene'],Seed=42,GaussianBudget=budget,
                    Methods=['improvedgs'],MinimumHostFreeGiB=4,MaximumTrainingSecondsPerMethod=21600 if probe else 10800)
        directory=self.directory/'leaves'/label;directory.mkdir(parents=True,exist_ok=True)
        declaration=directory/'declaration.json';parent=read_json(self.directory/'declaration.json')
        document={'schema_version':'final-leaf-1','root':str(root),'upstream':'third_party/improved-gs',
            'spec':spec,'split':relative(root,split_path),'split_sha256':digest_json(read_json(split_path)),
            'source_pin':parent['source_pin'],'source_pin_sha256':parent['source_pin_sha256'],
            'campaign_declaration_sha256':sha256(self.directory/'declaration.json')}
        if declaration.exists():
            if read_json(declaration)!=document:raise ValueError('Frozen final leaf changed')
        else:write_json(declaration,document)
        verify_pin(root,inside(root,parent['source_pin']),self.state['study'])
        worker=self.tree/'src/topic16_upgrade/final_worker.py'
        command=[self.host['conda'],'run','--no-capture-output','-n',spec['EnvironmentName'],'python',str(worker),
                 '--declaration',str(declaration),'--method','improvedgs']
        self.state['current_worker']={'study':spec['Study'],'label':label,'method':'improvedgs'};self.save()
        key=label+'-qa'
        if not self.done(key):
            attempt='final-'+str(time.time_ns())
            safety=self.guarded(key,command+['--qa','--trainer-revision',attempt],directory/(attempt+'.log'),True)
            output=root/'artifacts/research'/spec['Study']/('qa-'+attempt)/'improvedgs'
            if read_json(output/'resume-check.json')['status']!='passed':raise ValueError('Final full-state replay failed')
            self.commit(key,[output/'resume-check.json',output/'cache-proof.json',safety,declaration])
        # New scenes must use the same installed backend/binaries that earned
        # the Tea gate, not merely an environment with the same display name.
        canonical_runtime=root/'artifacts/jobs/research/tea-research-v4/runtime.json'
        if read_json(directory/'runtime.json')!=read_json(canonical_runtime):
            raise ValueError('Final leaf backend packages or extension binaries differ from validated Tea')
        output=root/'artifacts/research'/spec['Study']/'runs/improvedgs';key=label+'-probe'
        if probe and not self.done(key):
            proof=output/'probe.json'
            if not proof.exists():
                safety=self.guarded(key,command+['--probe-until','3500'],directory/('probe-'+str(time.time_ns())+'.log'),True)
            else:
                attempts=[a for a in self.state.get('attempts',[]) if a['key']==key]
                if not attempts:raise ValueError('Preflight lacks safety provenance')
                safety=inside(root,attempts[-1]['safety'])
            measured=read_json(proof)
            if measured['status']!='passed' or measured['step']!=3500:raise ValueError('Incomplete continuing preflight')
            if read_json(safety)['status']!='succeeded':raise ValueError('Preflight lacks successful telemetry')
            # Projection is conservative and diagnostic, never used to extend a
            # budget or certify later growth. The full run retains its guards.
            projection={'measured_training_seconds':measured['training_seconds'],
                'linear_30k_seconds':measured['training_seconds']*30000/3500,
                'growth_adjusted_proxy_seconds':measured['training_seconds']*30000/3500*max(1,budget/measured['gaussians'])*1.3,
                'scope':'Train-only scheduling proxy; later RAP/MU and growth are nonlinear. Hard6h model ceiling remains.'}
            write_json(directory/'projection.json',projection);self.commit(key,[proof,safety,directory/'projection.json'])
        key=label+'-full';result=output/'result.json'
        if not self.done(key):
            if result.exists():
                previous=[a for a in self.state.get('attempts',[]) if a['key']==key]
                reusable=previous and read_json(inside(root,previous[-1]['safety']))['status']=='succeeded'
            else:reusable=False
            if reusable:safety=inside(root,previous[-1]['safety'])
            else:safety=self.guarded(key,command,directory/('full-'+str(time.time_ns())+'.log'),True)
            record=read_json(result);checkpoint=output/record['checkpoint']['path']
            if (record['status']!='succeeded' or record['checkpoint']['step']!=30000
                    or record['gaussians']>budget
                    or sha256(checkpoint)!=record['checkpoint']['sha256'] or sha256(output/'model.ply')!=record['ply_sha256']
                    or record['identity']['trainer_sha256']!=sha256(worker)):
                raise ValueError('Final leaf has no exact completed30k artifact')
            if read_json(output/'pending-gradient-check.json')['status']!='passed':raise ValueError('Pending MU recovery check missing')
            images=[output/f[k] for f in record['frames'] for k in ('gt','pred')]
            self.commit(key,[result,checkpoint,output/'model.ply',output/'cache-proof.json',output/'pending-gradient-check.json',safety,declaration]+images)
        return result
