"""Native entry point; import origin is verified before executing any job."""
from pathlib import Path
import sys
import argparse
import json
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import topic16_upgrade
from topic16_upgrade.contracts import read_json, write_json, inside


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--settings', type=Path, required=True)
    subs = parser.add_subparsers(dest='command', required=True)
    for command in ('inventory', 'verify', 'audit', 'plan', 'run', 'publish', 'runtime-check', 'safety-check', 'session-watch', 'prepare', 'repair-study', 'preflight','full-plan','full-run','historical-common','quality-plan','quality-run','quality-audit','quality-measure','research-plan','research-run','confirmation-plan','confirmation-run','final-plan','final-run','final-ui-check'):
        p = subs.add_parser(command)
        p.add_argument('--baseline-root', type=Path)
        p.add_argument('--study', default='tea60-v1')
        p.add_argument('--scene', default='tea_sets_2')
        p.add_argument('--split-path', type=Path)
        p.add_argument('--resume', action='store_true')
        p.add_argument('--full-hash', action='store_true')
        p.add_argument('--directory', type=Path)
    for operation in ('render','export'):
        p = subs.add_parser(operation)
        p.add_argument('--config',type=Path,required=True)
        p.add_argument('--camera-path',type=Path)
        p.set_defaults(baseline_root=None)
    args = parser.parse_args()
    root = args.root.resolve(); settings = read_json(args.settings)
    if not Path(topic16_upgrade.__file__).resolve().is_relative_to(root / 'src'):
        raise ValueError('Upgrade module origin is outside the isolated source tree')
    for folder in ('artifacts', 'data', 'reports'):
        inside(root, root / folder)
    if args.command == 'session-watch':
        from topic16_upgrade.sessions import watch_session
        return watch_session(args.directory)
    os.environ['OMP_NUM_THREADS'] = str(settings['CpuWorkerThreads'])
    os.environ['MKL_NUM_THREADS'] = str(settings['CpuWorkerThreads'])
    baseline = (args.baseline_root or Path(settings.get('BaselineRoot', root.parent))).resolve()
    settings.setdefault('SharedGpuLock', str(baseline / 'artifacts/logs/gpu.lock'))
    if args.command in ('final-plan','final-run','final-ui-check'):
        from topic16_upgrade.final_campaign import prepare,execute
        if args.command=='final-ui-check':
            from topic16_upgrade.final_ui import check
            result=check(root,settings,args.study)
        else:result=prepare(root,settings,args.study) if args.command=='final-plan' else execute(root,settings,args.study,args.resume)
    elif args.command in ('confirmation-plan','confirmation-run'):
        from topic16_upgrade.confirmation import prepare,execute
        result=prepare(root,settings,args.study) if args.command=='confirmation-plan' else execute(root,settings,args.study,args.resume)
    elif args.command in ('research-plan','research-run'):
        from topic16_upgrade.research import prepare,execute
        result=prepare(root,settings,args.study) if args.command=='research-plan' else execute(root,settings,args.study,args.resume)
    elif args.command in ('quality-audit','quality-measure'):
        from topic16_upgrade.quality import materialize_native,audit
        from topic16_upgrade.runtime import gpu_lock
        with gpu_lock(root,{'SharedGpuLock':settings['SharedGpuLock']}):
            split=materialize_native(root,baseline,settings)
            result=audit(root,baseline,settings,split)
        result={k:v for k,v in result.items() if k!='frames'}
        if args.command=='quality-measure':
            from topic16_upgrade.quality_viewer import measure
            result={'parity_report':str(measure(root,settings,baseline,split))}
    elif args.command in ('quality-plan','quality-run'):
        from topic16_upgrade.quality import prepare,execute
        result=prepare(root,settings,baseline,args.study) if args.command=='quality-plan' else execute(root,settings,baseline,args.study,args.resume)
    elif args.command == 'historical-common':
        from topic16_upgrade.full import historical_common
        result=historical_common(root,baseline,args.scene,settings)
    elif args.command in ('full-plan','full-run'):
        from topic16_upgrade.full import prepare,run
        result=prepare(root,settings,baseline,args.study) if args.command=='full-plan' else run(root,settings,baseline,args.study,args.resume)
    elif args.command == 'repair-study':
        from topic16_upgrade.source_pin import create_pin
        result = create_pin(root,args.study)
        result = {k:v for k,v in result.items() if k != 'source_files'}
    elif args.command == 'preflight':
        from topic16_upgrade.study import preflight
        result = preflight(root,settings,baseline,args.study,args.split_path)
    elif args.command in ('render','export'):
        from topic16_upgrade.runtime import render, export
        result = render(root, settings, args.config, args.camera_path) if args.command == 'render' else {'path':str(export(root, settings, args.config))}
        from topic16_upgrade.study import publish
        ledger = root / 'artifacts/jobs/ledger.json'
        publish(root, read_json(ledger) if ledger.exists() else {'jobs': {}})
    elif args.command == 'inventory':
        from topic16_upgrade.preservation import inventory
        result = inventory(root, baseline, args.full_hash)
    elif args.command == 'verify':
        from topic16_upgrade.preservation import inventory, verify_source
        result = {'source': verify_source(root, baseline), 'artifact_runs': len(inventory(root, baseline)['runs'])}
        write_json(root / 'reports/baseline-integrity.json', result)
    elif args.command == 'prepare':
        from topic16_upgrade.preprocessing import prepare_scene, freeze_split
        from topic16_upgrade.runtime import gpu_lock
        # Canonicalization is CPU work; acquire only the shared resource lock.
        with gpu_lock(root, {'SharedGpuLock': settings['SharedGpuLock']}):
            prepare_scene(root, args.scene, settings)
            split = freeze_split(root, args.scene, settings)
            target = root / 'data/captures' / args.scene.replace(':','-') / 'split.json'
            write_json(target, split)
            result = {'scene': args.scene, 'split_path': str(target), 'input_root': str(root),
                      'train_count': len(split['train']), 'eval_count': len(split['eval'])}
    elif args.command == 'audit':
        from topic16_upgrade.capture import audit
        scene = args.scene if ':' in args.scene or args.scene in ('bonsai', 'room', 'garden', 'poster') else 'custom:' + args.scene
        result = audit(root, baseline, scene, args.split_path, settings['AuditImageSize'])
        from topic16_upgrade.study import publish
        ledger = root / 'artifacts/jobs/ledger.json'
        publish(root, read_json(ledger) if ledger.exists() else {'jobs': {}})
        result = {k: v for k, v in result.items() if k not in ('frames','overlap_matrix')}
    elif args.command in ('plan', 'run'):
        from topic16_upgrade.study import plan, execute
        if args.command == 'plan':
            result = plan(root, settings, baseline, args.study, args.split_path)
            result = {**result, 'jobs': [{k: v for k, v in j.items() if k != 'selection'} for j in result['jobs']]}
        else:
            result = execute(root, settings, baseline, args.study, args.resume, args.split_path)
            result = {'runs': len(result['runs']), 'status': 'succeeded', 'index': str(root / 'reports/ui-index.json')}
    elif args.command == 'publish':
        from topic16_upgrade.study import publish
        result = publish(root, read_json(root / 'artifacts/jobs/ledger.json') if (root / 'artifacts/jobs/ledger.json').exists() else {'jobs': {}})
        result = {'runs': len(result['runs']), 'revision': result['revision']}
    elif args.command == 'safety-check':
        from topic16_upgrade.runtime import gpu_lock
        with gpu_lock(root, settings):
            result = {'status': 'passed'}
    else:
        from topic16_upgrade.runtime import assert_runtime, gpu_lock, runtime_snapshot
        with gpu_lock(root, settings):
            assert_runtime(root, settings)
            import torch
            (torch.ones(4, device='cuda') * 2).cpu()
            result = {'status': 'passed', 'dependencies': runtime_snapshot()}
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    from topic16_upgrade.sessions import SessionPaused
    try:
        main()
    except SessionPaused as error:
        print(str(error), flush=True)
        raise SystemExit(75)
