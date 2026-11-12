"""Teacher-first Room A/B/C queue; only a complete supplement unlocks GS work."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import zipfile

from .contracts import (digest_json, file_required, inside, load_run, read_json,
    relative, sha256, utc_now, validate_metrics, write_json)
from .sessions import check_stop, SessionPaused
from .source_pin import freeze_current, verify_pin, source_files, identity


def reference(base, path):
    return {'path': relative(base, path), 'sha256': sha256(file_required(path))}


def resolve(base, ref):
    path = inside(base, ref['path'])
    if sha256(file_required(path)) != ref['sha256']:
        raise ValueError('Teacher evidence changed: ' + ref['path'])
    return path


def validate_profile(spec):
    expected = {'SchemaVersion': 'teacher-room-ablation-1', 'Study': 'teacher-room-v1',
        'Scene': 'room', 'Arms': ['A', 'B', 'C'], 'Iterations': 30000, 'Seed': 42,
        'DownscaleFactor': 2, 'TrainViews': 272, 'EvalViews': 39,
        'MaximumArmSeconds': 10800, 'MinimumFreeGiB': 30,
        'ContinueFinalCampaign': True, 'FinalStudy': 'final-quality-v1'}
    if spec != expected:
        raise ValueError('Teacher matrix differs from the approved fresh Room A/B/C protocol')


def qa_sources(root):
    return {name: sha256(root / 'src/topic16_upgrade' / name) for name in
        ('teacher.py', 'teacher_worker.py', 'teacher_report.py', 'training_worker.py')}


def baseline_records(root, baseline):
    from .capture import capture_split
    frozen, capture = capture_split(baseline, 'room')
    pairs = [p for path in (baseline / 'artifacts/logs/matrices').glob('topic16-full-*.json')
        for scene, p in read_json(path)['pairs'].items() if scene == 'room']
    if len(pairs) != 1 or (len(frozen['train']), len(frozen['eval'])) != (272, 39):
        raise ValueError('Room baseline matrix/split is ambiguous')
    records = {}
    for method in ('nerfacto', 'splatfacto'):
        run = load_run(baseline, inside(baseline, pairs[0]['runs'][method]), require_eval=True)
        if run['split'] != frozen:
            raise ValueError('Historical methods have different frozen cameras/GT')
        records[method] = {name: reference(baseline, p) for name, p in [
            ('config', run['config']), ('checkpoint', run['checkpoint']),
            ('evaluation', run['paths']['metrics'] / 'evaluation.json'),
            ('metrics', run['paths']['metrics'] / 'metrics.json'),
            ('manifest', run['paths']['logs'] / 'manifest.json'),
            ('provenance', run['paths']['logs'] / 'provenance.json')]}
        records[method]['render_directory'] = relative(baseline, run['paths']['renders'])
    return frozen, reference(baseline, Path(capture['split_path'])), records


def verify_inputs(doc):
    baseline = Path(doc['baseline'])
    frozen = read_json(resolve(baseline, doc['split']))
    for item in frozen['train'] + frozen['eval'] + frozen.get('pose_files', []):
        resolve(baseline, item)
    for record in doc['baselines'].values():
        for key in ('config', 'checkpoint', 'evaluation', 'metrics', 'manifest', 'provenance'):
            resolve(baseline, record[key])
        evaluation = read_json(resolve(baseline, record['evaluation']))
        for frame in evaluation['frames']:
            for kind in ('gt', 'pred'):
                resolve(baseline, {'path': record['render_directory'] + '/' + frame[kind],
                    'sha256': frame[kind + '_sha256']})
    return frozen


def prepare(root, settings, study):
    from .preservation import verify_source
    from .runtime import runtime_snapshot, validate_runtime_snapshot
    spec = settings['Teacher']; validate_profile(spec)
    if study != spec['Study']:
        raise ValueError('Unknown teacher study')
    baseline = Path(settings['BaselineRoot']).resolve()
    directory = root / 'artifacts/jobs/teacher' / study
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'declaration.json'
    if path.exists():
        doc = read_json(path); state = read_json(directory / 'state.json')
        if doc['spec'] != spec or digest_json(settings) != doc['settings_sha256']:
            raise ValueError('Teacher frozen protocol/settings changed')
        if sha256(path) != state['declaration_sha256']:
            raise ValueError('Teacher declaration changed')
        resolve(root, doc['source_pin']); verify_pin(root, resolve(root, doc['source_pin']), study)
        validate_runtime_snapshot(doc['runtime_sha256']); verify_inputs(doc)
        return state
    verify_source(root, baseline)
    candidates = sorted((root / 'artifacts/teacher/qa').glob('*/qa.json'), reverse=True)
    matching = [p for p in candidates if read_json(p).get('status') == 'passed'
        and read_json(p).get('source_files') == qa_sources(root)
        and read_json(p).get('settings_sha256') == digest_json(settings)]
    if not matching:
        raise ValueError('Run Test-TeacherRoom.ps1: all three live integration proofs must pass on these source/settings bytes')
    qa_proof = matching[0]
    for ref in read_json(qa_proof)['evidence'] + read_json(qa_proof)['proofs']:
        resolve(root, ref)
    frozen, split, records = baseline_records(root, baseline)
    if shutil.disk_usage(root).free < (spec['MinimumFreeGiB'] + 12) * 2**30:
        raise ValueError('Diagnostic output allowance would violate disk reserve')
    old_session = root / 'artifacts/logs/sessions/topic16-final-quality-v1/state.json'
    if read_json(old_session)['status'] != 'paused':
        raise ValueError('Pause the previous final campaign before the teacher handoff')
    handoff = root / 'artifacts/research/final-quality-v1-bonsai/runs/improvedgs/latest.json'
    latest = read_json(handoff)
    # The original two rolling slots will advance after the GS queue resumes.
    # Keep a separate immutable handoff copy, including optimizer/RNG state.
    archive = directory / 'handoff'; archive.mkdir(exist_ok=True)
    original_checkpoint = inside(handoff.parent, latest['path'])
    if sha256(original_checkpoint) != latest['sha256']:
        raise ValueError('Paused Bonsai checkpoint differs from its index')
    checkpoint_copy = archive / ('bonsai-step-' + str(latest['step']) + '.pt')
    if not checkpoint_copy.exists(): shutil.copy2(original_checkpoint, checkpoint_copy)
    if sha256(checkpoint_copy) != latest['sha256']:
        raise ValueError('Immutable handoff checkpoint copy differs')
    index_copy, session_copy = archive / 'bonsai-latest.json', archive / 'previous-session.json'
    for source, target in [(handoff, index_copy), (old_session, session_copy)]:
        if not target.exists(): shutil.copyfile(source, target)
        if sha256(target) != sha256(source): raise ValueError('Previous handoff archive differs')
    old_provenance = read_json(resolve(baseline, records['nerfacto']['provenance']))
    try:
        validate_runtime_snapshot(old_provenance['runtime_sha256']); comparable_runtime = True
    except ValueError:
        comparable_runtime = False
    pin = freeze_current(root, study)
    canonical = Path(frozen['train'][0]['path']).parent.parent
    doc = {'schema_version': 'teacher-room-declaration-1', 'study': study,
        'root': str(root), 'baseline': str(baseline), 'spec': spec, 'settings': settings,
        'settings_sha256': digest_json(settings), 'runtime_sha256': digest_json(runtime_snapshot()),
        'baseline_runtime_matches_current': comparable_runtime,
        'source_pin': reference(root, pin), 'split': split, 'baselines': records,
        'integration_qa': reference(root, qa_proof),
        'canonical': canonical.as_posix(), 'created_at': utc_now(),
        'master_plan_sha256': sha256(baseline / 'upgrade_to_baseline.md'),
        'handoff': {'previous_session': reference(root, session_copy),
            'checkpoint_index': reference(root, index_copy), 'checkpoint': reference(root, checkpoint_copy),
            'checkpoint_record': latest},
        'scope': 'Fresh Room A/B/C, historical on/average reference, common evaluator; no test-time fitting'}
    verify_inputs(doc)
    write_json(path, doc)
    state = {'study': study, 'status': 'planned', 'phase': 'preflight', 'stages': {},
        'arms': {}, 'declaration_sha256': sha256(path), 'created_at': utc_now(),
        'resume_policy': 'Skip committed stages; interrupted teacher training restarts fresh, never loads partial weights'}
    write_json(directory / 'state.json', state)
    return state


def qa(root, settings):
    """Exercise every real arm before freezing the long-running declaration."""
    from .runtime import assert_runtime, gpu_lock, run_command, runtime_snapshot
    from .safety import current_guard
    from .preservation import verify_source
    validate_profile(settings['Teacher'])
    source_files = qa_sources(root)
    baseline = Path(settings['BaselineRoot']).resolve(); verify_source(root, baseline)
    frozen, split, records = baseline_records(root, baseline)
    output = root / 'artifacts/teacher/qa' / str(time.time_ns()); output.mkdir(parents=True)
    doc = {'root': str(root), 'baseline': str(baseline), 'study': 'teacher-room-qa',
        'canonical': Path(frozen['train'][0]['path']).parent.parent.as_posix(),
        'settings': settings, 'baselines': records, 'split': split,
        'runtime_sha256': digest_json(runtime_snapshot())}
    verify_inputs(doc); declaration = output / 'job.json'; write_json(declaration, doc)
    evidence = []
    for mode, arm in [('preflight', None), ('integration', 'A'), ('integration', 'B'), ('integration', 'C')]:
        command = [sys.executable, str(root / 'src/topic16_upgrade/teacher_worker.py'),
            '--declaration', str(declaration), '--mode', mode, '--output', str(output)]
        if arm: command += ['--arm', arm]
        with gpu_lock(root, settings):
            assert_runtime(root, settings); safety = current_guard().path
            run_command(root, command, output / (mode + '-' + str(arm) + '.log'))
        evidence.append(reference(root, safety))
    path = output / 'qa.json'
    if qa_sources(root) != source_files:
        raise ValueError('QA source changed during execution; repeat QA on the final bytes')
    write_json(path, {'status': 'passed', 'source_files': source_files,
        'settings_sha256': digest_json(settings),
        'evidence': evidence, 'proofs': [reference(root, p) for p in
            [output / 'preflight.json', *sorted(output.glob('integration-*.json'))]],
        'finished_at': utc_now()})
    return {'status': 'passed', 'report': str(path)}


def score_baseline(root, doc, method):
    from .evidence import score_saved_images, EVALUATOR
    baseline = Path(doc['baseline']); record = doc['baselines'][method]
    evaluation = read_json(resolve(baseline, record['evaluation']))
    directory = inside(baseline, record['render_directory'])
    images = [{k: directory / f[k] for k in ('gt', 'pred')} for f in evaluation['frames']]
    for frame in evaluation['frames']:
        for k in ('gt', 'pred'):
            if sha256(directory / frame[k]) != frame[k + '_sha256']:
                raise ValueError('Historical evaluation pixels changed')
    identity = {'evaluator': EVALUATOR, 'runtime': doc['runtime_sha256'],
        'evaluation': record['evaluation'], 'images': digest_json(evaluation['frames'])}
    path = root / 'reports' / doc['study'] / 'historical' / (method + '-common.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    score_saved_images(images, identity, path, 4)
    return path


def score_arm(root, doc, output):
    from .evidence import score_saved_images, EVALUATOR
    evaluation = read_json(output / 'evaluation.json')
    images = [{k: resolve(root, f[k]) for k in ('gt', 'pred')} for f in evaluation['frames']]
    identity = {'evaluator': EVALUATOR, 'runtime': doc['runtime_sha256'],
        'evaluation_sha256': sha256(output / 'evaluation.json'), 'frames_sha256': digest_json(evaluation['frames'])}
    path = output / 'common.json'
    score_saved_images(images, identity, path, 4)
    return path


def execute(root, settings, study, resume=False):
    from .runtime import gpu_lock, run_command, gpu_monitor, peak_vram
    from .safety import current_guard
    prepare(root, settings, study)
    directory = root / 'artifacts/jobs/teacher' / study
    doc = read_json(directory / 'declaration.json'); state = read_json(directory / 'state.json')
    if state['status'] == 'succeeded':
        return state
    if state['status'] != 'planned' and not resume:
        raise ValueError('Teacher queue has started; use Resume')
    _, tree = verify_pin(root, resolve(root, doc['source_pin']), study)

    def save(phase=None):
        if phase:
            state.update(status='running', phase=phase); state.pop('error', None)
            print('[teacher] ' + study + ' | ' + phase, flush=True)
        state['updated_at'] = utc_now(); write_json(directory / 'state.json', state)

    def done(key):
        for ref in state['stages'].get(key, []):
            resolve(root, ref)
        return key in state['stages']

    def commit(key, paths):
        state['stages'][key] = [reference(root, p) for p in paths]; save()

    def guarded(mode, output, arm=None, attempt=None):
        check_stop()
        if shutil.disk_usage(root).free < doc['spec']['MinimumFreeGiB'] * 2**30:
            raise SessionPaused('Teacher disk reserve reached; no further work started')
        output.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(tree / 'src/topic16_upgrade/teacher_worker.py'),
            '--declaration', str(directory / 'declaration.json'), '--mode', mode, '--output', str(output)]
        if arm: command += ['--arm', arm]
        if attempt: command += ['--attempt', attempt]
        invocation = output / (mode + '-invocation-' + str(time.time_ns()) + '.json')
        write_json(invocation, {'argv': command, 'cold_start': mode == 'train', 'started_at': utc_now()})
        with gpu_lock(root, settings):
            safety = current_guard().path
            write_json(output / (mode + '-safety-reference.json'), {'path': relative(root, safety),
                'invocation': relative(root, invocation), 'started_at': utc_now()})
            session = Path(os.environ['TOPIC16_SESSION_DIRECTORY'])
            limit = doc['spec']['MaximumArmSeconds'] if mode == 'train' else 3600
            timer = threading.Timer(limit, lambda: write_json(session / 'stop.json',
                {'requested': True, 'reason': 'Declared teacher stage time budget reached'}))
            timer.daemon = True; timer.start()
            try:
                with gpu_monitor(root, output / (mode + '-gpu.csv'), settings['GpuSampleSeconds']):
                    run_command(root, command, output / (mode + '-' + str(time.time_ns()) + '.log'),
                        cooperative_training=mode == 'train', environment_overrides={
                            'TOPIC16_TRAIN_TIME_LIMIT': str(doc['spec']['MaximumArmSeconds']),
                            'MKL_THREADING_LAYER': 'SEQUENTIAL'})
            finally:
                timer.cancel()
        safety_record = read_json(safety)
        if safety_record['status'] != 'succeeded':
            raise ValueError('Teacher stage did not finish under its safety guard')
        proof = output / (mode + '-execution.json')
        write_json(proof, {'status': 'succeeded', 'safety': reference(root, safety),
            'invocation': reference(root, invocation),
            'sampled_peak_device_vram_mb': peak_vram(output / (mode + '-gpu.csv')),
            'gpu': safety_record.get('first_sample'), 'finished_at': utc_now()})
        return [proof, safety, invocation, output / (mode + '-gpu.csv')]

    with gpu_lock(root, {'SharedGpuLock': str(directory / 'queue.lock')}):
        try:
            for key in state['stages']: done(key)
            # Operational repairs are separate from the immutable trainer pin.
            # Never rewrite a completed scientific declaration to fix Resume.
            controller_files = source_files(root)
            controller_id = identity(controller_files)
            archive = directory / 'controllers' / controller_id / 'source.zip'
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as snapshot:
                    for name in controller_files: snapshot.write(root / name, name)
            controller = {'source_id': controller_id, 'archive': reference(root, archive),
                'source_files': controller_files, 'scope': 'Controller only; child trainer keeps original frozen source'}
            if controller not in state.setdefault('controllers', []):
                state['controllers'].append(controller); save()
            if not done('preflight'):
                save('preflight'); output = directory / ('preflight-' + str(time.time_ns()))
                evidence = guarded('preflight', output)
                if read_json(output / 'preflight.json')['status'] != 'passed':
                    raise ValueError('Teacher all-arm preflight failed')
                commit('preflight', [output / 'preflight.json', *output.glob('*-config.yml'), *evidence])
            for arm in doc['spec']['Arms']:
                check_stop(); train_key, eval_key, common_key = (arm + '-' + k for k in ('train', 'eval', 'common'))
                if not done(train_key):
                    attempt = str(time.time_ns())
                    output = root / 'artifacts/teacher' / study / arm / attempt
                    previous = state['arms'].get(arm, {})
                    history = previous.get('attempts', [])
                    history.append({'attempt': attempt, 'output': relative(root, output), 'started_at': utc_now(),
                        'initialization': 'fresh; no baseline/partial checkpoint loaded'})
                    state['arms'][arm] = {'attempt': attempt, 'output': relative(root, output),
                        'attempts': history, 'status': 'training'}
                    session = Path(os.environ['TOPIC16_SESSION_DIRECTORY'])
                    write_json(session / 'active-run.json', {'teacher_arm': arm, 'attempt': attempt,
                        'progress': f'artifacts/logs/{study}-{arm}/nerfacto/{attempt}/progress.json',
                        'resume_policy': 'Interrupted teacher arm restarts fresh'})
                    save(train_key); evidence = guarded('train', output, arm, attempt)
                    trained = read_json(output / 'training.json')
                    commit(train_key, [output / 'training.json', output / 'initialization.json',
                        output / 'recipe-diff.json', resolve(root, {'path': trained['config'], 'sha256': trained['config_sha256']}),
                        resolve(root, {'path': trained['checkpoint'], 'sha256': trained['checkpoint_sha256']}), *evidence])
                    state['arms'][arm]['attempts'][-1].update(status='trained', training_finished_at=utc_now())
                    save()
                output = inside(root, state['arms'][arm]['output'])
                if not done(eval_key):
                    save(eval_key); evidence = guarded('evaluate', output, arm)
                    evaluated = read_json(output / 'evaluation.json')
                    paths = [resolve(root, f[k]) for f in evaluated['frames'] for k in ('gt', 'pred')]
                    commit(eval_key, [output / 'evaluation.json', *paths, *evidence])
                if not done(common_key):
                    save(common_key); commit(common_key, [score_arm(root, doc, output)])
                state['arms'][arm]['status'] = 'complete'; save()
                if not done('teacher-report'):
                    from .teacher_report import publish
                    publish(root, doc, state, final=False)
            for method in ('nerfacto', 'splatfacto'):
                key = method + '-historical-common'
                if not done(key):
                    save(key); commit(key, [score_baseline(root, doc, method)])
            if not done('teacher-report'):
                save('teacher-report')
                from .teacher_report import publish
                paths = publish(root, doc, state, final=True)
                commit('teacher-report', paths)
            # Report gate is technical completeness, never a PSNR target.
            report = read_json(root / 'reports' / study / 'report.json')
            if report['status'] != 'complete' or set(report['completed_arms']) != {'A', 'B', 'C'}:
                raise ValueError('Teacher supplement must be complete before any GS work')
            state['teacher_assignment'] = 'complete'; save()
            if doc['spec']['ContinueFinalCampaign']:
                check_stop(); save('upgrade-final')
                from .final_campaign import execute as final_execute
                final_settings = copy.deepcopy(settings); final_settings.pop('Teacher', None)
                final_settings['DownscaleFactor'] = 1
                os.environ['MKL_THREADING_LAYER'] = 'SEQUENTIAL'
                final_execute(root, final_settings, doc['spec']['FinalStudy'], resume=True)
            state.update(status='succeeded', phase='computed-awaiting-ui', finished_at=utc_now()); save()
            return state
        except BaseException as error:
            arm = state.get('phase', '').removesuffix('-train')
            if arm in state['arms'] and state['arms'][arm].get('status') == 'training':
                state['arms'][arm]['attempts'][-1].update(status='paused' if isinstance(error, SessionPaused) else 'failed',
                    error=str(error), finished_at=utc_now())
            state.update(status='paused' if isinstance(error, SessionPaused) else 'failed',
                error=str(error) or type(error).__name__)
            save(); raise
