"""Materialize independent canonical subsets; never write through baseline paths."""
from pathlib import Path
import shutil
from .contracts import inside, read_json, write_json, sha256, digest_json, relative, validate_split


def scene_input(root, scene):
    if not scene.startswith('custom:') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in scene[7:]):
        raise ValueError('Upgrade dataset must be a safe named canonical condition')
    directory = root / 'data/processed/canonical' / scene[7:]
    inside(root / 'data/processed/canonical', directory)
    # Verify the resolved target, but preserve the ASCII junction spelling for
    # Open3D's Windows file API in the generated Nerfstudio config.
    return directory, 'nerfstudio-data', 'filename'


def prepare_scene(root, scene, settings):
    directory = scene_input(root, scene)[0]
    freeze_split(root, scene, settings)
    return directory


def freeze_split(root, scene, settings, **unused):
    directory = scene_input(root, scene)[0]
    split = read_json(directory / 'split.json')
    validate_split(split)
    if split['scene'] != scene or split['downscale_factor'] != settings['DownscaleFactor']:
        raise ValueError('Subset scene/downscale changed')
    for frame in split['train'] + split['eval'] + split.get('pose_files', []):
        if sha256(inside(root, frame['path'])) != frame['sha256']:
            raise ValueError('Canonical input changed')
    return split


def materialize(root, baseline, frozen, selection, condition):
    from PIL import Image
    directory = scene_input(root, condition)[0]
    if directory.exists():
        saved = read_json(directory / 'selection.json')
        if saved != selection:
            raise ValueError('Existing condition has different selection identity')
        return freeze_split(root, condition, {'DownscaleFactor': frozen['downscale_factor']})
    stage = directory.with_name(directory.name + '.staging')
    if stage.exists():
        # Never erase an interrupted materialization. It remains inspectable.
        stage = directory.with_name(directory.name + '.staging-' + __import__('uuid').uuid4().hex)
    inside(root, stage).mkdir(parents=True)
    (stage / 'images').mkdir(); (stage / 'images_2').mkdir()
    factor = frozen['downscale_factor']
    if factor != 2:
        raise ValueError('Initial paired canonical protocol requires downscale 2')
    selected = [frozen['train'][i] for i in selection['indices']]
    cameras, split = [], {'schema_version': '1.0', 'scene': condition, 'downscale_factor': factor, 'train': [], 'eval': []}
    for label, frames in (('train', selected), ('eval', frozen['eval'])):
        for index, frame in enumerate(frames):
            source = inside(baseline, frame['path'])
            if sha256(source) != frame['sha256']:
                raise ValueError('Frozen image checksum mismatch')
            name = f'frame_{label}_{index:05d}.png'
            shutil.copyfile(source, stage / 'images_2' / name)
            # Full-resolution source is retained; no interpolation of measured GT.
            original = inside(baseline, source.parent.parent / 'images' / source.name)
            with Image.open(original) as image:
                width, height = image.size
            shutil.copyfile(original, stage / 'images' / name)
            camera = {'file_path': 'images/' + name, 'transform_matrix': frame['camera_to_world'] + [[0., 0., 0., 1.]],
                      'w': width, 'h': height, 'fl_x': frame['fx'] * factor, 'fl_y': frame['fy'] * factor,
                      'cx': frame['cx'] * factor, 'cy': frame['cy'] * factor,
                      'k1': 0., 'k2': 0., 'p1': 0., 'p2': 0.}
            cameras.append(camera)
            split[label].append({**frame, 'path': relative(root, directory / 'images_2' / name)})
    canonical = inside(baseline, frozen['train'][0]['path']).parent.parent
    # Freeze the original parser transform of the complete capture for sparse seeds.
    # This does not fit cameras again for each subset.
    from nerfstudio.data.dataparsers.nerfstudio_dataparser import NerfstudioDataParserConfig
    import open3d as o3d
    from .contracts import native_workspace
    canonical_alias = native_workspace(baseline) / canonical.relative_to(baseline)
    parser = NerfstudioDataParserConfig(data=canonical_alias, downscale_factor=factor,
        eval_mode='filename' if frozen['scene'].startswith('custom:') else 'interval', load_3D_points=True).setup()
    outputs = parser.get_dataparser_outputs(split='train')
    # Ensure the canonical loader is the same frame recorded by the frozen split.
    import numpy as np
    if not np.allclose(outputs.cameras.camera_to_worlds.numpy(), np.asarray([f['camera_to_world'] for f in frozen['train']]), atol=1e-6):
        raise ValueError('Canonical sparse initialization frame differs from frozen cameras')
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(outputs.metadata['points3D_xyz'].numpy())
    cloud.colors = o3d.utility.Vector3dVector(outputs.metadata['points3D_rgb'].numpy().astype(float) / 255)
    from .contracts import native_workspace
    alias = native_workspace(root) / stage.relative_to(root)
    if not o3d.io.write_point_cloud(str(alias / 'sparse_pc.ply'), cloud):
        raise ValueError('Cannot write independent sparse seeds')
    metadata = {'camera_model': 'OPENCV', 'orientation_override': 'none', 'ply_file_path': 'sparse_pc.ply',
                'frames': cameras, 'train_filenames': [c['file_path'] for c in cameras if 'frame_train_' in c['file_path']],
                'test_filenames': [c['file_path'] for c in cameras if 'frame_eval_' in c['file_path']]}
    metadata['val_filenames'] = metadata['test_filenames']
    write_json(stage / 'transforms.json', metadata)
    split['pose_files'] = [{'path': relative(root, directory / name), 'sha256': sha256(stage / name)}
                           for name in ('transforms.json', 'sparse_pc.ply')]
    split['capture'] = {'scene_group': frozen['scene'], 'eval_camera_hash': digest_json(frozen['eval']),
                        'selection_id': selection['selection_id'], 'source_split_hash': digest_json(frozen),
                        'scope': 'known-camera / transductive initialization'}
    validate_split(split)
    write_json(stage / 'split.json', split); write_json(stage / 'selection.json', selection)
    stage.rename(directory)
    return split
