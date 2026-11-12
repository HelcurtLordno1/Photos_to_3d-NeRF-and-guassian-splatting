"""Fresh Room ablations from the saved baseline recipe, without upstream edits."""
from __future__ import annotations

import argparse
import copy
import dataclasses
from enum import Enum
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topic16_upgrade.contracts import (digest_json, file_required, inside, native_workspace,
    read_json, relative, sha256, utc_now, write_json)

ARMS = {'A': ('off', True), 'B': ('SO3xR3', False), 'C': ('off', False)}


def plain(value):
    # Dataclass classes (e.g. Nerfstudio's _target) are callable identities,
    # not instances whose required constructor fields can be traversed.
    if isinstance(value, type) or callable(value):
        return value.__module__ + '.' + value.__qualname__
    if dataclasses.is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Path):
        return str(value.resolve())
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError('Unrecordable recipe value: ' + type(value).__name__)


def differences(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        result = {}
        for key in left:
            result.update(differences(left[key], right[key], prefix + key + '.'))
        return result
    return {} if left == right else {prefix.rstrip('.'): {'before': left, 'after': right}}


def baseline_config(doc):
    import yaml
    baseline = Path(doc['baseline'])
    ref = doc['baselines']['nerfacto']['config']
    path = inside(baseline, ref['path'])
    if sha256(path) != ref['sha256']:
        raise ValueError('Baseline recipe changed')
    config = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.Loader)
    model, parser = config.pipeline.model, config.pipeline.datamanager.dataparser
    if (config.method_name != 'nerfacto' or config.machine.seed != 42
            or config.max_num_iterations != 30000 or parser.downscale_factor != 2
            or model.camera_optimizer.mode != 'SO3xR3' or not model.use_appearance_embedding
            or not model.use_average_appearance_embedding or model.appearance_embed_dim != 32):
        raise ValueError('Historical Room configuration differs from the declared reference')
    for key in ('load_config', 'load_checkpoint', 'load_dir', 'load_step'):
        if getattr(config, key) is not None:
            raise ValueError('Fresh teacher runs cannot load prior model state')
    return config


def build_config(doc, arm, attempt):
    original = baseline_config(doc)
    config = copy.deepcopy(original)
    root, baseline = Path(doc['root']), Path(doc['baseline'])
    mode, appearance = ARMS[arm]
    config.pipeline.model.camera_optimizer.mode = mode
    config.pipeline.model.use_appearance_embedding = appearance
    config.output_dir = native_workspace(root) / 'artifacts/runs'
    config.experiment_name = doc['study'] + '-' + arm
    config.timestamp = attempt
    canonical = Path(doc['canonical'])
    config.pipeline.datamanager.dataparser.data = native_workspace(baseline) / canonical
    config.pipeline.datamanager.max_thread_workers = 4
    delta = differences(plain(original), plain(config))
    allowed = {'output_dir', 'experiment_name', 'timestamp',
        'pipeline.datamanager.dataparser.data', 'pipeline.datamanager.max_thread_workers',
        'pipeline.model.camera_optimizer.mode', 'pipeline.model.use_appearance_embedding'}
    if set(delta) - allowed:
        raise ValueError('Undeclared baseline recipe changes: ' + str(set(delta) - allowed))
    if config.pipeline.datamanager.num_processes != 1:
        raise ValueError('Keep the original single data-loader process')
    return config, delta


def verify_dataset(doc, label, filenames, cameras):
    import numpy as np
    baseline = Path(doc['baseline'])
    expected = read_json(inside(baseline, doc['split']['path']))[label]
    if [p.resolve() for p in filenames] != [inside(baseline, f['path']) for f in expected]:
        raise ValueError('Actual ' + label + ' frame identities differ from the frozen baseline')
    if len(cameras) != len(expected):
        raise ValueError('Actual camera count differs')
    for i, frame in enumerate(expected):
        if not np.allclose(cameras.camera_to_worlds[i].cpu().numpy(), frame['camera_to_world'], atol=1e-6, rtol=1e-6):
            raise ValueError('Actual camera pose differs: ' + label + str(i))
        for key in ('width', 'height', 'fx', 'fy', 'cx', 'cy'):
            if abs(float(getattr(cameras, key)[i].item()) - frame[key]) > 1e-5:
                raise ValueError('Actual camera ' + key + ' differs: ' + label + str(i))
        distortion = cameras.distortion_params[i].tolist() if cameras.distortion_params is not None else []
        if distortion != frame.get('distortion_params', []):
            raise ValueError('Actual distortion differs')
        if int(cameras.camera_type[i].item()) != frame['camera_type']:
            raise ValueError('Actual camera type differs')


def verify_pipeline(doc, arm, pipeline):
    mode, appearance = ARMS[arm]
    model = pipeline.model
    if model.camera_optimizer.config.mode != mode:
        raise ValueError('Live camera optimizer mode did not take effect')
    field = model.field
    if (field.embedding_appearance is not None) != appearance:
        raise ValueError('Live appearance conditioning did not take effect')
    if field.appearance_embedding_dim != (32 if appearance else 0):
        raise ValueError('Live appearance input dimension differs')
    groups = pipeline.get_param_groups()
    if bool(groups.get('camera_opt')) != (mode != 'off'):
        raise ValueError('Live camera optimizer parameter group differs')
    for label, dataset in [('train', pipeline.datamanager.train_dataset), ('eval', pipeline.datamanager.eval_dataset)]:
        verify_dataset(doc, label, dataset.image_filenames, dataset.cameras)
    return {'camera_optimizer': mode, 'appearance_enabled': appearance,
        'appearance_dimension': field.appearance_embedding_dim,
        'eval_appearance': 'average' if appearance else 'absent',
        'camera_optimizer_group': bool(groups.get('camera_opt')),
        'train_views': 272, 'eval_views': 39, 'all_camera_and_frame_checks': True}


def preflight(doc, output):
    import yaml
    records = {}
    output.mkdir(parents=True, exist_ok=True)
    for arm in ARMS:
        config, delta = build_config(doc, arm, 'preflight')
        parser = config.pipeline.datamanager.dataparser.setup()
        for label, split in [('train', 'train'), ('eval', 'test')]:
            parsed = parser.get_dataparser_outputs(split=split)
            verify_dataset(doc, label, parsed.image_filenames, parsed.cameras)
        path = output / (arm + '-config.yml')
        path.write_text(yaml.dump(config), encoding='utf-8')
        records[arm] = {'config': str(path), 'sha256': sha256(path), 'recipe_changes': delta,
            'fresh_initialization': True, 'all_parser_cameras_match': True}
    write_json(output / 'preflight.json', {'status': 'passed', 'arms': records,
        'finished_at': utc_now(), 'scope': 'CPU parser/config audit; live field audit occurs before the first update'})


def train(doc, arm, attempt, output):
    import torch
    from nerfstudio.engine import trainer as trainer_module
    from topic16_upgrade.training_worker import controlled_train_loop
    config, delta = build_config(doc, arm, attempt)
    config.save_config()
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'recipe-diff.json', delta)
    original_trainer = trainer_module.Trainer

    class AuditedTrainer(original_trainer):
        def setup(self, *args, **kwargs):
            super().setup(*args, **kwargs)
            if self._start_step != 0 or any(getattr(self.config, k) is not None for k in
                    ('load_config', 'load_checkpoint', 'load_dir', 'load_step')):
                raise ValueError('Teacher ablation must start fresh at zero')
            proof = verify_pipeline(doc, arm, self.pipeline)
            proof.update(start_step=0, loaded_checkpoint=None, checked_at=utc_now(),
                config_sha256=sha256(config.get_base_dir() / 'config.yml'))
            write_json(output / 'initialization.json', proof)
            print('[teacher] LIVE INITIALIZATION PASS ' + arm + ' | ' + str(proof), flush=True)

        def train_iteration(self, step):
            result = super().train_iteration(step)
            loss = float(result[0].detach())
            if not torch.isfinite(result[0]).item():
                raise ValueError('Nonfinite training loss')
            if step % 100 == 0:
                print(f'[teacher] {arm} {step}/30000 loss={loss:.8f}', flush=True)
            return result

    trainer_module.Trainer = AuditedTrainer
    os.environ['TOPIC16_WORKSPACE'] = doc['root']
    started = time.perf_counter()
    try:
        controlled_train_loop(0, 1, config)
    finally:
        trainer_module.Trainer = original_trainer
    checkpoint = file_required(config.get_checkpoint_dir() / 'step-000029999.ckpt')
    state = torch.load(checkpoint, map_location='cpu')
    if state['step'] != 29999:
        raise ValueError('Final checkpoint is not the declared 30k result')
    pose = next((v for k, v in state['pipeline'].items() if k.endswith('camera_optimizer.pose_adjustment')), None)
    pose_summary = {'enabled': ARMS[arm][0] != 'off'}
    if pose is not None:
        pose_summary.update(translation_l2_mean=float(pose[:, :3].norm(dim=-1).mean()),
            translation_l2_max=float(pose[:, :3].norm(dim=-1).max()),
            rotation_l2_mean=float(pose[:, 3:].norm(dim=-1).mean()),
            rotation_l2_max=float(pose[:, 3:].norm(dim=-1).max()))
    path = config.get_base_dir() / 'config.yml'
    write_json(output / 'training.json', {'status': 'succeeded', 'arm': arm, 'attempt': attempt,
        'step': state['step'], 'iterations': 30000, 'fresh_initialization': True,
        'config': relative(Path(doc['root']), path), 'config_sha256': sha256(path),
        'checkpoint': relative(Path(doc['root']), checkpoint), 'checkpoint_sha256': sha256(checkpoint),
        'training_seconds': time.perf_counter() - started, 'camera_corrections': pose_summary,
        'finished_at': utc_now()})


def evaluate(doc, arm, output):
    import numpy as np
    import torch
    from PIL import Image
    from nerfstudio.utils.eval_utils import eval_setup
    from topic16_upgrade.runtime import close_pipeline
    from topic16_upgrade.sessions import average_eval_metrics
    root = Path(doc['root'])
    trained = read_json(output / 'training.json')
    config_path, checkpoint = inside(root, trained['config']), inside(root, trained['checkpoint'])
    if sha256(config_path) != trained['config_sha256'] or sha256(checkpoint) != trained['checkpoint_sha256']:
        raise ValueError('Trained config/checkpoint changed before evaluation')
    images = output / 'images'; images.mkdir(exist_ok=True)
    pipeline = None
    def configure(config):
        # eval_setup's public callback selects the exact committed final step.
        if config.load_checkpoint is not None or config.load_dir is not None:
            raise ValueError('Fresh serialized configuration contains a warm-start')
        config.load_step = 29999
        return config
    try:
        _, pipeline, loaded, step = eval_setup(config_path, test_mode='test', update_config_callback=configure)
        if loaded.resolve() != checkpoint.resolve() or step != 29999:
            raise ValueError('Evaluation selected a different checkpoint')
        live = verify_pipeline(doc, arm, pipeline)
        with torch.no_grad():
            metrics = average_eval_metrics(pipeline, output_path=images, get_std=True)
        expected = read_json(inside(Path(doc['baseline']), doc['split']['path']))['eval']
        if len(list(images.glob('eval_img_*.png'))) != len(expected):
            raise ValueError('Incomplete held-out image output')
        frames = []
        baseline = Path(doc['baseline'])
        old = doc['baselines']['nerfacto']
        old_eval = read_json(inside(baseline, old['evaluation']['path']))
        for i, frame in enumerate(expected):
            with Image.open(images / f'eval_img_{i:04d}.png') as image:
                width, height = frame['width'], frame['height']
                if image.size != (width * 2, height):
                    raise ValueError('Held-out render dimensions differ')
                gt, pred = image.crop((0, 0, width, height)), image.crop((width, 0, width * 2, height))
                old_gt = inside(baseline, old['render_directory']) / old_eval['frames'][i]['gt']
                with Image.open(old_gt) as original:
                    if not np.array_equal(np.asarray(gt.convert('RGB')), np.asarray(original.convert('RGB'))):
                        raise ValueError('Evaluation GT pixels differ from the original baseline')
                gt.save(images / f'gt_{i:04d}.png'); pred.save(images / f'pred_{i:04d}.png')
            frames.append({k: {'path': relative(root, images / f'{k}_{i:04d}.png'),
                'sha256': sha256(images / f'{k}_{i:04d}.png')} for k in ('gt', 'pred')})
        write_json(output / 'evaluation.json', {'status': 'succeeded', 'step': step,
            'config_sha256': sha256(config_path), 'checkpoint_sha256': sha256(checkpoint),
            'native_metrics': metrics, 'frames': frames, 'live_checks': live,
            'all39_gt_pixels_equal_historical': True, 'finished_at': utc_now()})
    finally:
        if pipeline is not None:
            close_pipeline(pipeline)


def integration(doc, arm, output):
    """Two optimizer updates on TRAIN rays, excluded from scientific results."""
    import torch
    import gc
    from nerfstudio.engine.trainer import Trainer
    from nerfstudio.engine.callbacks import TrainingCallbackLocation
    from nerfstudio.scripts.train import _set_random_seed
    from nerfstudio.utils.eval_utils import eval_setup
    from topic16_upgrade.runtime import close_pipeline
    config, delta = build_config(doc, arm, 'qa-' + str(time.time_ns()))
    config.save_config(); _set_random_seed(config.machine.seed)
    trainer = Trainer(config, local_rank=0, world_size=1)
    pipeline = None
    try:
        trainer.setup()
        proof = verify_pipeline(doc, arm, trainer.pipeline)
        if trainer._start_step != 0: raise ValueError('Integration run is not fresh')
        losses = []
        for step in range(2):
            trainer.step = step; trainer.pipeline.train()
            for callback in trainer.callbacks:
                callback.run_callback_at_location(step, TrainingCallbackLocation.BEFORE_TRAIN_ITERATION)
            loss, _, _ = trainer.train_iteration(step)
            if not torch.isfinite(loss).item(): raise ValueError('Integration training loss is not finite')
            losses.append(float(loss.detach()))
            for callback in trainer.callbacks:
                callback.run_callback_at_location(step, TrainingCallbackLocation.AFTER_TRAIN_ITERATION)
        trainer.save_checkpoint(1)
        checkpoint = config.get_checkpoint_dir() / 'step-000000001.ckpt'
        close_pipeline(trainer.pipeline); trainer = None
        gc.collect(); torch.cuda.empty_cache()
        def configure(saved):
            if saved.load_checkpoint is not None or saved.load_dir is not None:
                raise ValueError('Serialized fresh QA config contains a warm-start')
            saved.load_step = 1
            return saved
        _, pipeline, loaded, loaded_step = eval_setup(config.get_base_dir() / 'config.yml',
            test_mode='test', update_config_callback=configure)
        if loaded_step != 1 or loaded.resolve() != checkpoint.resolve():
            raise ValueError('Exact-checkpoint evaluation callback failed')
        verify_pipeline(doc, arm, pipeline)
        # Only TRAIN rays exercise the serialized inference path. No test score
        # is inspected or used for choosing a configuration during integration QA.
        camera = pipeline.datamanager.train_dataset.cameras[0:1].to(pipeline.device)
        camera.rescale_output_resolution(.05)
        with torch.no_grad():
            rendered = pipeline.model.get_outputs_for_camera(camera)['rgb']
        if not torch.isfinite(rendered).all().item():
            raise ValueError('Serialized checkpoint inference is nonfinite')
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / ('integration-' + arm + '.json'), {'status': 'passed', 'arm': arm,
            'live_initialization': proof, 'train_losses': losses, 'recipe_changes': delta,
            'exact_checkpoint_eval_step': loaded_step, 'train_render_shape': list(rendered.shape),
            'checkpoint_sha256': sha256(checkpoint),
            'scope': 'Two fresh TRAIN updates and serialized checkpoint TRAIN inference; not a completed30k arm, no held-out quality result',
            'finished_at': utc_now()})
    finally:
        if trainer is not None and hasattr(trainer, 'pipeline'): close_pipeline(trainer.pipeline)
        if pipeline is not None: close_pipeline(pipeline)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--declaration', type=Path, required=True)
    parser.add_argument('--mode', choices=['preflight', 'integration', 'train', 'evaluate'], required=True)
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--attempt')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    doc = read_json(args.declaration)
    from topic16_upgrade.runtime import assert_runtime, validate_runtime_snapshot
    assert_runtime(Path(doc['root']), doc['settings'])
    validate_runtime_snapshot(doc['runtime_sha256'])
    import torch
    torch.set_num_threads(4)
    if args.mode == 'preflight':
        preflight(doc, args.output)
    elif args.mode == 'integration':
        integration(doc, args.arm, args.output)
    elif args.mode == 'train':
        train(doc, args.arm, args.attempt, args.output)
    else:
        evaluate(doc, args.arm, args.output)


if __name__ == '__main__':
    from topic16_upgrade.sessions import SessionPaused
    try:
        main()
    except SessionPaused as error:
        print(str(error), flush=True)
        raise SystemExit(75)
