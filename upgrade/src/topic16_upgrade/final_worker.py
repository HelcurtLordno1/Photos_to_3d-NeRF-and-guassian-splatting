"""Separately pinned final-campaign worker, derived from the preserved v4 worker.

Numerical method calls stay unchanged; additions bound image storage, perform a
train-only continuing preflight and verify pending-gradient checkpoint recovery.
"""
from pathlib import Path
import argparse
import copy
import os
import random
import shutil
import sys
import time
import subprocess
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic16_upgrade.contracts import read_json,write_json,sha256,digest_json,utc_now,inside
from topic16_upgrade.sessions import stop_requested,SessionPaused


def atomic_torch(path,payload):
    import torch
    temporary=path.with_suffix('.pending')
    with temporary.open('wb') as stream:
        torch.save(payload,stream);stream.flush();os.fsync(stream.fileno())
    for attempt in range(8):
        try:os.replace(temporary,path);return
        except PermissionError:
            if attempt==7:raise
            time.sleep(.05*(attempt+1))


def capture(gaussians,context,loop,iteration,identity,updates):
    import torch
    excluded={'scene','pipe','train_cameras','edge_maps','edge_camera_pool','edge_map_pool','minigs_background'}
    return {'schema_version':'improved-full-state-1','identity':identity,'iteration':iteration,'updates':updates,
            'model':gaussians.capture(),'exposure':gaussians._exposure.detach().clone(),
            'exposure_optimizer':gaussians.exposure_optimizer.state_dict(),
            'grads':{n:getattr(gaussians,n).grad for n in ('_xyz','_features_dc','_features_rest','_scaling','_rotation','_opacity','_exposure')},
            'runtime':{k:v for k,v in context.runtime_state.items() if k not in excluded},
            'viewpoint_stack':[c.uid for c in loop['viewpoint_stack']],
            'edge_camera_pool':[c.uid for c in context.runtime_state.get('edge_camera_pool',[])],
            'rng':{'python':random.getstate(),'numpy':np.random.get_state(),'torch':torch.get_rng_state(),
                   'cuda':torch.cuda.get_rng_state_all()}}


def restore(payload,gaussians,context,loop,identity):
    import torch
    if payload.get('schema_version')!='improved-full-state-1' or payload['identity']!=identity:
        raise ValueError('Checkpoint identity differs; no implicit protocol/source migration')
    gaussians.restore(payload['model'],context.opt)
    with torch.no_grad():gaussians._exposure.copy_(payload['exposure'])
    gaussians.exposure_optimizer.load_state_dict(payload['exposure_optimizer'])
    for name,gradient in payload['grads'].items():
        getattr(gaussians,name).grad=None if gradient is None else gradient.clone()
    context.runtime_state.update(copy.deepcopy(payload['runtime']))
    cameras={c.uid:c for c in context.scene.getTrainCameras()}
    loop['viewpoint_stack']=[cameras[i] for i in payload['viewpoint_stack']]
    ids=payload['edge_camera_pool']
    context.runtime_state['edge_camera_pool']=[cameras[i] for i in ids]
    maps=context.runtime_state.get('edge_maps',[])
    context.runtime_state['edge_map_pool']=[maps[i] for i in ids] if maps else []
    random.setstate(payload['rng']['python']);np.random.set_state(payload['rng']['numpy'])
    torch.set_rng_state(payload['rng']['torch'].cpu())
    torch.cuda.set_rng_state_all([s.cpu() for s in payload['rng']['cuda']])


def state_equal(left,right):
    import torch
    if torch.is_tensor(left):
        return torch.is_tensor(right) and left.shape==right.shape and torch.equal(left.detach().cpu(),right.detach().cpu())
    if isinstance(left,np.ndarray):return isinstance(right,np.ndarray) and np.array_equal(left,right)
    if isinstance(left,dict):return isinstance(right,dict) and left.keys()==right.keys() and all(state_equal(v,right[k]) for k,v in left.items())
    if isinstance(left,(tuple,list)):return isinstance(right,(tuple,list)) and len(left)==len(right) and all(state_equal(a,b) for a,b in zip(left,right))
    return left==right


def main():
    import torch
    p=argparse.ArgumentParser();p.add_argument('--declaration',type=Path,required=True)
    p.add_argument('--method',choices=['absgs','improvedgs'],required=True)
    p.add_argument('--qa',action='store_true');p.add_argument('--trainer-revision',default='v1');p.add_argument('--probe-until',type=int);args=p.parse_args()
    declaration=read_json(args.declaration);root=Path(declaration['root']);spec=declaration['spec']
    source=inside(root,declaration['upstream']);sys.path.insert(0,str(source))
    if subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()!=spec['ImprovedGsCommit']:
        raise ValueError('Official source commit changed')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip():
        raise ValueError('Official source modified')
    from topic16_upgrade.runtime import runtime_snapshot
    import diff_gaussian_rasterization, simple_knn._C, fused_ssim
    from importlib.util import find_spec
    runtime_record={'packages':runtime_snapshot(),'torch':torch.__version__,
        'extensions':{name:sha256(Path(find_spec(name).origin)) for name in
                      ('diff_gaussian_rasterization._C','simple_knn._C','fused_ssim_cuda')}}
    runtime_path=args.declaration.parent/'runtime.json'
    if runtime_path.exists():
        if read_json(runtime_path)!=runtime_record:raise ValueError('Research runtime or extension binary changed')
    else:write_json(runtime_path,runtime_record)
    from scene.training_runtime import parse_training_arguments,build_training_loop_state,sample_training_viewpoint
    from scene.training_context import build_training_context,attach_scene_and_gaussians_to_context
    from scene.methods.initialization_3dgs import build_gaussian_model_3dgs
    from scene.methods.optimization_methods import run_3dgs_optimization_method
    from scene.methods.densification_stage import run_3dgs_densification_method
    from scene.methods.pruning_methods import run_3dgs_pruning_method
    from scene.training_loop import update_3dgs_training_schedule,run_3dgs_parameter_update_method,should_run_parameter_update
    from topic16_upgrade.bounded_adapter import FrozenScene,make_camera,attach_bounded,check_host_memory,verify_pending_checkpoint
    from gaussian_renderer import render
    from PIL import Image
    torch.set_num_threads(4)
    if torch.__version__!=spec['TorchVersion']:raise ValueError('Isolated Torch differs')
    random.seed(spec['Seed']);np.random.seed(spec['Seed']);torch.manual_seed(spec['Seed']);torch.cuda.manual_seed_all(spec['Seed'])
    output=root/'artifacts/research'/spec['Study']/(('qa' if args.trainer_revision=='v1' else 'qa-'+args.trainer_revision) if args.qa else 'runs')/args.method
    output.mkdir(parents=True,exist_ok=True)
    split=read_json(inside(root,declaration['split']))
    if digest_json(split)!=declaration['split_sha256']:raise ValueError('Research split changed')
    argv=['--source_path',str(root),'--model_path',str(output),'--training_method',args.method,
          '--iterations',str(spec['Iterations']),'--budget',str(spec['GaussianBudget']),
          '--train_test_exp','false','--antialiasing','false','--random_background','false',
          '--depth_l1_weight_init','0','--depth_l1_weight_final','0']
    if 'SharedDensifyGradThreshold' in spec:
        argv+=['--densify_grad_threshold',str(spec['SharedDensifyGradThreshold']),
               '--optimizer_type',spec['OptimizerType'],'--position_lr_init',str(spec['PositionLearningRate'])]
    lp,op,pp,runtime=parse_training_arguments(argv)
    dataset,opt,pipe=lp.extract(runtime),op.extract(runtime),pp.extract(runtime)
    if 'SharedDensifyGradThreshold' in spec and (opt.densify_grad_threshold!=spec['SharedDensifyGradThreshold']
            or opt.optimizer_type!=spec['OptimizerType'] or opt.position_lr_init!=spec['PositionLearningRate']):
        raise ValueError('Generated training settings differ from the declared shared protocol')
    runtime.report_lpips_test=False;runtime.report_lpips_train=False
    context=build_training_context(dataset,opt,pipe,runtime)
    model=build_gaussian_model_3dgs(dataset,opt);scene=FrozenScene(root,split,model,output)
    context=attach_bounded(context,scene,model);model.training_setup(opt)
    loop=build_training_loop_state(context,False,False)
    identity={'declaration_sha256':sha256(args.declaration),'runtime_sha256':sha256(runtime_path),'method':args.method,'qa':args.qa,
              'trainer_sha256':sha256(Path(__file__)),'adapter_sha256':sha256(Path(__file__).with_name('bounded_adapter.py')),
              'resolved_options':vars(opt),'pipeline':vars(pipe),'split_sha256':declaration['split_sha256']}
    write_json(output/'resolved-config.json',identity)
    latest=output/'latest.json';first=0;updates=0;spent=0.
    if latest.exists():
        ref=read_json(latest);path=inside(output,ref['path'])
        if sha256(path)!=ref['sha256']:raise ValueError('Resume checkpoint bytes changed')
        payload=torch.load(path);restore(payload,model,context,loop,identity)
        first=payload['iteration'];updates=payload['updates'];spent=ref['training_seconds']
    clock=time.monotonic();traces=[];qa_expected=None;qa_payload=None
    setup_peak=torch.cuda.max_memory_allocated()
    if args.probe_until and (args.qa or not 600<=args.probe_until<spec['Iterations']):raise ValueError('Invalid continuing preflight boundary')
    torch.cuda.reset_peak_memory_stats()
    def commit(iteration):
        previous=read_json(latest) if latest.exists() else {}
        # Atomic alternating slots retain the current and preceding recovery
        # checkpoint without accumulating ~60 optimizer copies per 30k run.
        slot=1-int(previous.get('slot',1))
        path=output/f'checkpoint-slot-{slot}.pt'
        atomic_torch(path,capture(model,context,loop,iteration,identity,updates))
        ref={'path':path.name,'slot':slot,'sha256':sha256(path),'step':iteration,'updates':updates,
             'training_seconds':spent+time.monotonic()-clock,'finished_at':utc_now()}
        write_json(latest,ref)
        with (output/'checkpoint-history.jsonl').open('a',encoding='utf-8') as history:
            import json
            history.write(json.dumps(ref)+'\n')
        print(f'Checkpoint committed: {args.method} step {iteration} updates {updates}',flush=True)
        return ref
    maximum=610 if args.qa else spec['Iterations']
    for iteration in range(first+1,maximum+1):
        update_3dgs_training_schedule(context,model,iteration)
        camera=sample_training_viewpoint(scene,loop['viewpoint_stack'])
        result=run_3dgs_optimization_method(context,model,loop,iteration,camera)
        if not torch.isfinite(result['loss']).all():raise ValueError('Nonfinite training loss')
        with torch.no_grad():
            updating=should_run_parameter_update(opt,iteration,args.method,context.method_config['use_mu'])
            run_3dgs_parameter_update_method(context,model,iteration,result['render_state']['radii'])
            updates+=int(updating)
            run_3dgs_densification_method(context,model,iteration,result['render_state'])
            run_3dgs_pruning_method(context,model,iteration)
        traces.append({'iteration':iteration,'camera':camera.uid,'loss':float(result['loss'].item())})
        if iteration%100==0:
            write_json(output/'progress.json',{'status':'running','step':iteration,'total_steps':spec['Iterations'],
                'gaussians':len(model.get_xyz),'optimizer_updates':updates,'loss':traces[-1]['loss'],
                'training_seconds':spent+time.monotonic()-clock,'updated_at':utc_now()})
            print(f'{args.method} {iteration}/{spec["Iterations"]} loss={traces[-1]["loss"]:.6f} gaussians={len(model.get_xyz)}',flush=True)
        if iteration%100==0:
            try:check_host_memory(spec.get('MinimumHostFreeGiB',4))
            except SessionPaused:commit(iteration);raise
        if not args.qa and iteration==20001:
            ref=commit(iteration)
            verify_pending_checkpoint(model,context,loop,identity,updates,output/ref['path'],output,capture,restore)
        if args.probe_until and iteration==args.probe_until:
            ref=commit(iteration)
            write_json(output/'probe.json',{'status':'passed','step':iteration,'checkpoint':ref,'training_seconds':ref['training_seconds'],
                'gaussians':len(model.get_xyz),'setup_peak_cuda_bytes':setup_peak,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),
                'scope':'TRAIN-only first steps of the actual frozen30k run; same checkpoint continues. Later growth remains guarded.'})
            print('Continuing preflight committed; held-out evaluation has not run',flush=True);return
        if iteration%100==0 and shutil.disk_usage(root).free < 30*2**30:
            commit(iteration);raise SessionPaused('Disk reserve reached; research checkpoint retained')
        if len(model.get_xyz)>spec['AbsoluteGaussianSafetyLimit']:
            commit(iteration);raise SessionPaused('Gaussian safety limit reached; review resources before extending')
        if torch.cuda.max_memory_allocated()>spec['TrainMemoryTargetMiB']*2**20:
            commit(iteration);raise SessionPaused('Declared training allocator memory budget exceeded')
        if args.qa and iteration==600:
            commit(iteration);qa_payload=torch.load(inside(output,read_json(latest)['path']))
        if not args.qa and (iteration%spec['CheckpointInterval']==0 or iteration==maximum):commit(iteration)
        if stop_requested() or spent+time.monotonic()-clock>=spec['MaximumTrainingSecondsPerMethod']:
            commit(iteration);raise SessionPaused('Research checkpoint committed; Stop or time budget reached')
    if args.qa:
        expected=[t for t in traces if t['iteration']>600]
        expected_params={n:getattr(model,n).detach().clone() for n in ('_xyz','_scaling','_opacity','_features_dc','_features_rest','_rotation')}
        def validation_images():
            with torch.no_grad():
                return [render(scene.getTrainCameras()[i],model,pipe,loop['background'],track_gradients=False)['render'].detach().clone() for i in (0,10,13)]
        expected_images=validation_images()
        before=copy.deepcopy(qa_payload)
        restore(qa_payload,model,context,loop,identity)
        recovered=capture(model,context,loop,600,identity,qa_payload['updates'])
        exact_fields={k:state_equal(v,recovered[k]) for k,v in before.items()}
        observed=[]
        for iteration in range(601,611):
            update_3dgs_training_schedule(context,model,iteration)
            camera=sample_training_viewpoint(scene,loop['viewpoint_stack'])
            result=run_3dgs_optimization_method(context,model,loop,iteration,camera)
            with torch.no_grad():
                run_3dgs_parameter_update_method(context,model,iteration,result['render_state']['radii'])
                run_3dgs_densification_method(context,model,iteration,result['render_state'])
                run_3dgs_pruning_method(context,model,iteration)
            observed.append({'iteration':iteration,'camera':camera.uid,'loss':float(result['loss'].item())})
        parameter_errors={n:float((getattr(model,n)-v).abs().max()) for n,v in expected_params.items()}
        max_parameter_error=max(parameter_errors.values())
        loss_error=max(abs(a['loss']-b['loss']) for a,b in zip(expected,observed))
        actual_images=validation_images()
        agreement=[float(-10*torch.log10((a-b).square().mean().clamp_min(1e-12))) for a,b in zip(expected_images,actual_images)]
        first_forward_error=abs(expected[0]['loss']-observed[0]['loss'])
        passed=(all(exact_fields.values()) and all(a['camera']==b['camera'] for a,b in zip(expected,observed))
                and first_forward_error<=1e-7 and min(agreement)>=60.)
        write_json(output/'resume-check.json',{'status':'passed' if passed else 'failed','camera_sequence_match':all(a['camera']==b['camera'] for a,b in zip(expected,observed)),
            'maximum_parameter_error':max_parameter_error,'maximum_loss_error':loss_error,
            'parameter_errors':parameter_errors,'exact_restore_fields':exact_fields,'render_agreement_psnr':agreement,
            'first_forward_loss_error':first_forward_error,
            'acceptance':'Exact saved state equality; identical camera sequence; FIRST pre-update forward loss error<=1e-7; all three train-camera ten-step float render agreements>=60dB. Subsequent loss/parameter drift is reported, not claimed bitwise deterministic.',
            'scope':'Disk checkpoint at600 after RAP/densification; ten-iteration replay. Does not certify all later MU/RAP boundaries.',
            'expected':expected,'observed':observed})
        if not passed:raise ValueError('Official backend full-state resume replay failed')
        return
    ref=read_json(latest)
    if ref['step']!=spec['Iterations']:raise ValueError('Final checkpoint is incomplete')
    for name in ('_xyz','_features_dc','_features_rest','_scaling','_rotation','_opacity'):
        if not torch.isfinite(getattr(model,name)).all():raise ValueError('Nonfinite final Gaussian parameters')
    model.save_ply(str(output/'model.ply'))
    # Offline renderer throughput and saved images use the final in-memory state,
    # verified against the just committed full checkpoint before evaluation.
    frames=[];durations=[]
    with torch.no_grad():
        for i,frame in enumerate(split['eval']):
            if stop_requested():raise SessionPaused('Evaluation paused; full checkpoint retained')
            camera=make_camera(root,frame,len(split['train'])+i)
            for _ in range(3):render(camera,model,pipe,loop['background'],track_gradients=False)
            torch.cuda.synchronize();start=time.perf_counter()
            rgb=None
            for _ in range(3):rgb=render(camera,model,pipe,loop['background'],track_gradients=False)['render']
            torch.cuda.synchronize();durations.append((time.perf_counter()-start)/3)
            pred=output/f'pred_{i:04d}.png';gt=output/f'gt_{i:04d}.png'
            Image.fromarray((rgb.clamp(0,1).permute(1,2,0).cpu().numpy()*255).round().astype('uint8')).save(pred)
            with Image.open(inside(root,frame['path'])) as image:image.convert('RGB').save(gt)
            frames.append({'gt':gt.name,'pred':pred.name,'gt_sha256':sha256(gt),'pred_sha256':sha256(pred)})
    result={'status':'succeeded','method':args.method,'identity':identity,'checkpoint':ref,
            'frames':frames,'gaussians':len(model.get_xyz),'ply_sha256':sha256(output/'model.ply'),
            'setup_peak_cuda_bytes':setup_peak,'cache_proof_sha256':sha256(output/'cache-proof.json'),
            'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'offline_fps':len(durations)/sum(durations),
            'per_view_seconds':durations,'training_seconds':ref['training_seconds'],'finished_at':utc_now()}
    write_json(output/'result.json',result)
    write_json(output/'progress.json',{'status':'succeeded','step':spec['Iterations'],'total_steps':spec['Iterations'],
               'gaussians':len(model.get_xyz),'optimizer_updates':ref['updates'],
               'training_seconds':ref['training_seconds'],'updated_at':utc_now()})


if __name__=='__main__':
    try:main()
    except SessionPaused as error:
        print(str(error),flush=True);raise SystemExit(75)
