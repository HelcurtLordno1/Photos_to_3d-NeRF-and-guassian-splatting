"""Common PNG evaluator and strict, intervention-aware comparison contracts."""
from pathlib import Path
import time
import numpy as np
from PIL import Image
from .contracts import read_json, write_json, sha256, digest_json, load_run, utc_now

EVALUATOR = 'common-rgb8-psnr-tmssim-alexlpips-v1'


def score_saved_images(images, identity, path: Path, threads=4):
    import torch
    from torchmetrics.functional.image import structural_similarity_index_measure
    from torchmetrics.image.lpip import LearnedPerceptualImagePatchSimilarity
    from .sessions import check_stop
    from .contracts import validate_metrics
    torch.set_num_threads(threads)
    if path.exists():
        saved = read_json(path)
        if saved['identity'] != identity or saved.get('status')!='succeeded' or len(saved.get('frames',[]))!=len(images):
            raise ValueError('Common evaluation identity changed')
        validate_metrics({'results':saved['metrics']})
        return saved
    start = time.perf_counter()
    lpips = LearnedPerceptualImagePatchSimilarity(net_type='alex', normalize=True).eval()
    scores = []
    for index, frame in enumerate(images):
        check_stop()
        values = []
        for name in ('gt', 'pred'):
            with Image.open(frame[name]) as image:
                values.append(torch.from_numpy(np.asarray(image.convert('RGB')).copy()).permute(2, 0, 1)[None].float() / 255)
        gt, pred = values
        with torch.no_grad():
            mse = torch.mean((gt - pred)**2).item()
            scores.append({'index': index, 'psnr': float(-10 * np.log10(max(mse, 1e-12))),
                           'ssim': float(structural_similarity_index_measure(pred, gt, data_range=1.)),
                           'lpips': float(lpips(pred, gt))})
            lpips.reset()
    record = {'status': 'succeeded', 'identity': identity, 'frames': scores,
              'metrics': {k: float(np.mean([s[k] for s in scores])) for k in ('psnr', 'ssim', 'lpips')},
              'cpu_seconds': time.perf_counter() - start, 'finished_at': utc_now(),
              'scope': 'same CPU evaluator on saved 8-bit RGB; method-native metrics retained separately'}
    validate_metrics({'results':record['metrics']})
    write_json(path, record)
    return record


def evaluate_common(root: Path, config: Path):
    run = load_run(root, config, require_eval=True)
    path = run['paths']['metrics'] / 'common-metrics.json'
    identity = {'evaluator_id': EVALUATOR, 'evaluation_sha256': sha256(run['paths']['metrics'] / 'evaluation.json'),
                'runtime_id': run['provenance']['runtime_sha256']}
    images=[{k:run['paths']['renders']/frame[k] for k in ('gt','pred')} for frame in run['evaluation']['frames']]
    settings=read_json(run['paths']['logs']/'settings.json')
    return score_saved_images(images,identity,path,settings['CpuWorkerThreads'])


PAIR_FIELDS = ('scene_group', 'method', 'budget', 'seed', 'downscale', 'source_id',
               'runtime_id', 'evaluator_id', 'eval_camera_hash', 'safety_id', 'pool_hash')


def compare(left, right):
    mismatch = [key for key in PAIR_FIELDS if left.get(key) != right.get(key)]
    if left.get('variant') != 'upgrade' or right.get('variant') != 'upgrade':
        mismatch.append('historical-reference')
    if left.get('views') != right.get('views'):
        mismatch.append('views: requires separately declared view-count intervention')
    if mismatch:
        return {'status': 'trade-off-only', 'mismatch': mismatch, 'delta': None}
    return {'status': 'controlled-pair', 'left': left['run_key'], 'right': right['run_key'],
            'delta': {k: right['metrics'][k] - left['metrics'][k] for k in ('psnr', 'ssim', 'lpips')},
            'units': {'psnr': 'dB', 'ssim': 'absolute', 'lpips': 'absolute'}}
