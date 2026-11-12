"""Q1.5: fixed checkpoint, exact camera scaling, float RGB area integration."""
import copy
import time
import numpy as np
from PIL import Image
from .contracts import read_json, write_json, sha256, digest_json, inside, relative, load_run, utc_now
from .sessions import check_stop


def scaled_camera(frame, factor):
    if not isinstance(factor, int) or factor < 1:
        raise ValueError('Supersampling must be a positive integer')
    result = copy.deepcopy(frame)
    for key in ('width', 'height', 'fx', 'fy', 'cx', 'cy'):
        result[key] *= factor
    # Nerfstudio/gsplat use pixel centers at i+0.5, so K scales directly.
    return result


def verify_projection(frame, factor):
    """Ray invariance at matching subpixel locations, including off-center K."""
    enlarged = scaled_camera(frame, factor)
    points = np.array([[.5, .5], [frame['width']-.5, frame['height']-.5], [frame['cx'], frame['cy']]])
    rays = (points - [frame['cx'], frame['cy']]) / [frame['fx'], frame['fy']]
    larger_rays = (points*factor - [enlarged['cx'], enlarged['cy']]) / [enlarged['fx'], enlarged['fy']]
    error = float(np.max(np.abs(rays-larger_rays)))
    if error > 1e-12:
        raise ValueError('Supersampling changed camera rays')
    return error


def render_variant(root, settings, config, frames, directory, factor, mode):
    import torch
    import torch.nn.functional as F
    from nerfstudio.cameras.cameras import Cameras
    from .runtime import gpu_lock, load_pipeline, close_pipeline, validate_loaded_split
    from .safety import current_guard
    from .evidence import score_saved_images, EVALUATOR
    run = load_run(root, config, require_eval=True)
    identity = {'checkpoint_sha256': sha256(run['checkpoint']), 'config_sha256': sha256(config),
                'camera_hash': digest_json(frames), 'supersample': factor, 'rasterize_mode': mode,
                'filter': 'torch-area-float-rgb-v1', 'evaluator_id': EVALUATOR,
                'warmup': 3, 'repeats': 3, 'timing': 'synchronized CUDA render + float area; excludes image IO'}
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'renders.json'
    if path.exists():
        record = read_json(path)
        if record['identity'] != identity or record['status'] != 'succeeded':
            raise ValueError('Q1.5 render identity changed')
        for row in record['frames']:
            for key in ('gt','pred'):
                if sha256(directory/row[key]) != row[key+'_sha256']:
                    raise ValueError('Q1.5 image changed')
    else:
        pipeline = None
        with gpu_lock(root, settings):
            try:
                _, pipeline, _ = load_pipeline(root, run)
                validate_loaded_split(root, run, pipeline)
                pipeline.model.config.rasterize_mode = mode
                torch.cuda.reset_peak_memory_stats()
                cameras = []
                for frame in frames:
                    verify_projection(frame, factor)
                    enlarged = scaled_camera(frame, factor)
                    cameras.append(Cameras(camera_to_worlds=torch.tensor([frame['camera_to_world']],dtype=torch.float32),
                        **{k: enlarged[k] for k in ('width','height','fx','fy','cx','cy')}).to(pipeline.device))
                def draw(index):
                    rgb = pipeline.model.get_outputs_for_camera(cameras[index])['rgb']
                    if factor != 1:
                        rgb = F.interpolate(rgb.permute(2,0,1)[None], size=(frames[index]['height'],frames[index]['width']),
                                            mode='area')[0].permute(1,2,0)
                    return rgb.clamp(0,1)
                durations = []
                with torch.no_grad():
                    for i in range(3):
                        check_stop(); draw(i % len(frames))
                    for repeat in range(3):
                        torch.cuda.synchronize(); start = time.perf_counter()
                        for i in range(len(frames)):
                            check_stop(); draw(i)
                        torch.cuda.synchronize(); durations.append(time.perf_counter()-start)
                    saved = []
                    for i, frame in enumerate(frames):
                        check_stop()
                        rgb = draw(i)
                        Image.fromarray((rgb.cpu().numpy()*255).round().astype('uint8')).save(directory/f'pred_{i:04d}.png')
                        source = inside(root,frame['path'])
                        if sha256(source) != frame['sha256']:
                            raise ValueError('Q1.5 ground truth changed')
                        with Image.open(source) as gt:
                            gt.convert('RGB').save(directory/f'gt_{i:04d}.png')
                        row = {k: f'{k}_{i:04d}.png' for k in ('gt','pred')}
                        row.update({k+'_sha256': sha256(directory/row[k]) for k in ('gt','pred')})
                        saved.append(row)
                record = {'status':'succeeded','identity':identity,'frames':saved,'durations_seconds':durations,
                          'fps':len(frames)*3/sum(durations), 'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),
                          'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved(),
                          'gpu_safety_path':relative(root,current_guard().path),'finished_at':utc_now()}
                # A render is committed only after the guard has closed successfully.
            finally:
                if pipeline is not None: close_pipeline(pipeline)
        write_json(path,record)
    common = score_saved_images([{k:directory/f[k] for k in ('gt','pred')} for f in record['frames']],
                                identity,directory/'common.json',settings['CpuWorkerThreads'])
    return {'path':relative(root,path),'sha256':sha256(path), 'common':relative(root,directory/'common.json'),
            'common_sha256':sha256(directory/'common.json'),'metrics':common['metrics'],
            'fps':record['fps'],'peak_cuda_allocated_bytes':record['peak_cuda_allocated_bytes']}


def execute(root,settings,output):
    from .quality import references
    q1 = read_json(root/'artifacts/jobs/quality/tea-quality-v2.json')
    if q1['status'] != 'succeeded' or sha256(inside(root,q1['report'])) != q1['report_sha256']:
        raise ValueError('Q1 must be completed and unchanged')
    control = references(root,root.parent)[1][2]
    candidate = inside(root,q1['config'])
    native = load_run(root,candidate,require_eval=True)['split']['eval']
    half = load_run(root,control,require_eval=True)['split']['eval']
    for a,b in zip(native,half):
        if not np.allclose(a['camera_to_world'],b['camera_to_world'],atol=1e-6):
            raise ValueError('Native and half poses differ')
    rows=[]
    for label,config in [('half-control',control),('q1-native',candidate)]:
        for resolution,frames in [('native',native),('half',half)]:
            for variant,factor,mode in [('direct',1,'classic'),('area2x',2,'classic'),('aa2d',1,'antialiased')]:
                check_stop();tag=f'{label}-{resolution}-{variant}'
                print('Q1.5 '+tag,flush=True)
                rows.append({'tag':tag, **render_variant(root,settings,config,frames,output/tag,factor,mode)})
    record={'schema_version':'tea-multiscale-1','status':'succeeded','rows':rows,
            'camera_checks': {'maximum_ray_error':max(verify_projection(f,2) for f in native+half),
                              'native_size':[native[0]['width'],native[0]['height']],
                              'half_size':[half[0]['width'],half[0]['height']],
                              'half_supersampled_size':[half[0]['width']*2,half[0]['height']*2],
                              'note':'718x1278 supersampling preserves half-camera K; resizing native 719x1279 is a different sampling grid.'},
            'scope':'Fixed inference-only comparison. aa2d is not full Mip-Splatting. Tea test already inspected; exploratory.',
            'finished_at':utc_now()}
    write_json(output/'report.json',record)
    return record
