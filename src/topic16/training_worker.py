"""Pinned Trainer adapter: atomic checkpoints and stop at completed iterations.

No upstream source is edited. The SDK retains forward/backward/model callbacks;
this adapter owns persistence, scheduler restoration and the total step budget.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

from topic16.contracts import read_json, relative, sha256, utc_now, write_json
from topic16.sessions import SessionPaused, average_eval_metrics, remaining_iterations, stop_requested


def controlled_train_loop(local_rank, world_size, config, global_rank=0):
    import numpy as np
    import torch
    from nerfstudio.engine.callbacks import TrainingCallback, TrainingCallbackLocation
    from nerfstudio.engine.trainer import Trainer
    from nerfstudio.scripts.train import _set_random_seed
    from topic16.runtime import close_pipeline

    root = Path(os.environ['TOPIC16_WORKSPACE'])
    logs = root / 'artifacts/logs' / config.experiment_name / config.method_name / config.timestamp
    total = config.max_num_iterations

    class ControlledTrainer(Trainer):
        def _load_checkpoint(self):
            if self.config.load_checkpoint is None:
                return super()._load_checkpoint()
            state = torch.load(self.config.load_checkpoint, map_location='cpu')
            extra = state['topic16_resume']
            self._start_step = state['step'] + 1
            self.pipeline.load_pipeline(state['pipeline'], state['step'])
            # Splatfacto replaces Gaussian Parameter objects on load. Optimizers
            # must be constructed AFTER loading/resizing those parameters.
            self.optimizers = self.setup_optimizers()
            self.optimizers.load_optimizers(state['optimizers'])
            self.optimizers.load_schedulers(state['schedulers'])
            self.grad_scaler.load_state_dict(state['scalers'])
            for name, parameters in self.pipeline.get_param_groups().items():
                bound = self.optimizers.optimizers[name].param_groups[0]['params']
                if len(bound) != len(parameters) or any(a is not b for a, b in zip(bound, parameters)):
                    raise ValueError('Restored optimizer is not bound to live model parameters')
            write_json(logs / 'restore.json', {'saved_step': state['step'], 'next_step': self._start_step,
                'remaining_iterations': remaining_iterations(total, state['step']),
                'optimizer_live_parameters': True, 'scheduler_and_scaler_loaded': True,
                'checkpoint_sha256': sha256(self.config.load_checkpoint)})
            manager, model = self.pipeline.datamanager, self.pipeline.model
            for name, value in extra['manager'].items():
                setattr(manager, name, value)
            if extra.get('manager_rng') is not None:
                manager.random_generator.setstate(extra['manager_rng'])
            if extra.get('strategy_state') is not None:
                model.strategy_state = extra['strategy_state']
                # Strategy accumulators belong on the model's device.
                for name, value in model.strategy_state.items():
                    if isinstance(value, torch.Tensor):
                        model.strategy_state[name] = value.to(self.device)
            random.setstate(extra['python_rng'])
            np.random.set_state(extra['numpy_rng'])
            torch.set_rng_state(extra['torch_rng'])
            torch.cuda.set_rng_state_all(extra['cuda_rng'])
            print(f'Resume loaded model/optimizer/scheduler/scaler/RNG at step {state["step"]}; target {total}', flush=True)

        def save_checkpoint(self, step):
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
            manager, model = self.pipeline.datamanager, self.pipeline.model
            extra = {'python_rng': random.getstate(), 'numpy_rng': np.random.get_state(),
                     'torch_rng': torch.get_rng_state(), 'cuda_rng': torch.cuda.get_rng_state_all(),
                     'manager': {name: getattr(manager, name) for name in
                                 ('train_unseen_cameras', 'eval_unseen_cameras', 'train_count', 'eval_count')
                                 if hasattr(manager, name)},
                     'manager_rng': manager.random_generator.getstate() if hasattr(manager, 'random_generator') else None,
                     'strategy_state': getattr(model, 'strategy_state', None)}
            state = {'step': step, 'pipeline': self.pipeline.state_dict(),
                     'optimizers': {name: value.state_dict() for name, value in self.optimizers.optimizers.items()},
                     'schedulers': {name: value.state_dict() for name, value in self.optimizers.schedulers.items()},
                     'scalers': self.grad_scaler.state_dict(), 'topic16_resume': extra}
            path = self.checkpoint_dir / f'step-{step:09d}.ckpt'
            temporary = path.with_suffix('.tmp')
            torch.save(state, temporary)
            os.replace(temporary, path)
            write_json(logs / 'resume.json', {'status': 'paused' if stop_requested() else 'checkpoint-ready',
                'step': step, 'target_iterations': total, 'saved_at': utc_now(),
                'checkpoint': relative(root, path), 'checkpoint_sha256': sha256(path),
                'config_sha256': sha256(self.base_dir / 'config.yml')})
            for previous in self.checkpoint_dir.glob('*.ckpt'):
                if previous != path:
                    previous.unlink()
            print(f'Committed checkpoint: step {step} / target {total}', flush=True)

    _set_random_seed(config.machine.seed + global_rank)
    trainer = ControlledTrainer(config, local_rank=local_rank, world_size=world_size)
    try:
        trainer.setup()
        def cooperative_average(step=None, output_path=None, get_std=False):
            return average_eval_metrics(trainer.pipeline, step, output_path, get_std)
        trainer.pipeline.get_average_eval_image_metrics = cooperative_average
        if any(value != 1 for value in trainer.gradient_accumulation_steps.values()):
            raise ValueError('Checkpoint adapter requires the pinned methods\' single-step gradient accumulation')
        start = trainer._start_step
        # Upstream loops start .. start + max_num_iterations. Keep config.yml's
        # total budget unchanged, and adjust only the live loop's remaining count.
        config.max_num_iterations = total - start
        if start >= total:
            trainer.save_checkpoint(start - 1)
            return
        def checkpoint_boundary(step):
            if step % 25 == 0 or stop_requested():
                write_json(logs / 'progress.json', {'step': step, 'target_iterations': total, 'updated_at': utc_now()})
            if stop_requested():
                trainer.save_checkpoint(step)
                raise SessionPaused('Training checkpoint committed by stop request')
        trainer.callbacks.append(TrainingCallback([TrainingCallbackLocation.AFTER_TRAIN_ITERATION], checkpoint_boundary))
        try:
            trainer.train()
        except SessionPaused:
            record = read_json(logs / 'resume.json') if (logs / 'resume.json').exists() else {}
            if record.get('status') != 'paused' or record.get('step') != trainer.step:
                trainer.save_checkpoint(trainer.step)
            raise
    finally:
        config.max_num_iterations = total
        if hasattr(trainer, 'pipeline'):
            close_pipeline(trainer.pipeline)


def entrypoint():
    from nerfstudio.scripts import train
    train.train_loop = controlled_train_loop
    try:
        train.entrypoint()
    except SessionPaused as error:
        print(str(error), flush=True)
        raise SystemExit(75)


if __name__ == '__main__':
    entrypoint()
