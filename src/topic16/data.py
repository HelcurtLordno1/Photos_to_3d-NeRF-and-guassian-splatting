"""Validate capture inputs and freeze the split returned by the pinned dataparser."""
from __future__ import annotations

from topic16.settings import experiment_settings_hash

from pathlib import Path

from topic16.contracts import digest_json, file_required, inside, native_workspace, read_json, relative, sha256, validate_capture_review, validate_split, write_json

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def cpu_colmap_arguments(arguments: list[str], threads: int) -> list[str]:
    """Bound SIFT/mapping threads and forbid GPU use in the explicit CPU path."""
    if arguments and arguments[0] == '--':
        arguments = arguments[1:]
    if not arguments or arguments[0] not in ('-h', '--help', 'feature_extractor', 'exhaustive_matcher', 'mapper', 'bundle_adjuster'):
        raise ValueError('Unsupported CPU COLMAP stage')
    stage = arguments[0]
    flags = {'feature_extractor': 'SiftExtraction', 'exhaustive_matcher': 'SiftMatching'}
    arguments = list(arguments)
    if stage in flags:
        prefix = flags[stage]
        key = '--' + prefix + '.use_gpu'
        if key not in arguments or arguments[arguments.index(key) + 1] != '0':
            raise ValueError('CPU COLMAP adapter requires explicit use_gpu=0')
        arguments += ['--' + prefix + '.num_threads', str(threads)]
    elif stage == 'mapper':
        arguments += ['--Mapper.num_threads', str(threads)]
    return arguments


def choose_capture_model(models: list[dict], train_count: int, eval_count: int, minimum_ratio: float) -> dict:
    candidates = [model for model in models if model['train_count'] >= train_count * minimum_ratio
                  and model['eval_count'] == eval_count and model['unknown_count'] == 0]
    if not candidates:
        raise ValueError(f'No connected COLMAP model passes train/eval coverage: {models}')
    return sorted(candidates, key=lambda item: (-(item['train_count'] + item['eval_count']), item['model']))[0]


def convert_capture_model(root: Path, scene: str, settings: dict, inputs: dict) -> dict:
    """Select a qualifying connected component; convert through pinned SDK only."""
    import shutil
    from datetime import datetime, timezone
    from nerfstudio.data.utils.colmap_parsing_utils import read_images_binary
    from nerfstudio.process_data import colmap_utils
    directory = scene_source(native_workspace(root), scene)[0]
    models = []
    for path in sorted((directory / 'colmap/sparse').iterdir()):
        if path.is_dir() and (path / 'images.bin').is_file():
            names = [image.name for image in read_images_binary(path / 'images.bin').values()]
            train = [name for name in names if name.startswith('frame_train_')]
            evaluation = [name for name in names if name.startswith('frame_eval_')]
            models.append({'model': path.name, 'train_count': len(train), 'eval_count': len(evaluation),
                           'unknown_count': len(names) - len(train) - len(evaluation)})
    selected = choose_capture_model(models, len(inputs['train']), len(inputs['eval']), settings['MinimumRegistrationRatio'])
    model = directory / 'colmap/sparse' / selected['model']
    selection = {'models': models, 'selected': selected, 'selection': 'largest-connected-component-passing-all-eval-and-minimum-train'}
    write_json(directory / 'model_selection.json', selection)
    if selected['model'] != '0':
        # Preserve the upstream default conversion, including its failed evidence.
        backup = directory / '.attempts' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True)
        for name in ('transforms.json', 'sparse_pc.ply', 'capture.json'):
            if (directory / name).exists():
                shutil.copy2(directory / name, backup / name)
        from topic16.runtime import run_command
        arguments = ['colmap', 'bundle_adjuster', '--input_path', str(model), '--output_path', str(model),
                     '--BundleAdjustment.refine_principal_point', '1']
        run_command(root, arguments, directory / 'selected-bundle-adjustment.log')
        colmap_utils.colmap_to_json(recon_dir=model, output_dir=directory, use_single_camera_mode=True)
    return selection


def capture_preview(root: Path, scene: str, settings: dict) -> dict:
    """Export pose/frustum and sparse-point projection evidence without a model."""
    import sys
    from nerfstudio.data.dataparsers.nerfstudio_dataparser import NerfstudioDataParserConfig
    from topic16.runtime import run_command
    source = scene_source(root, scene)[0]
    report = read_json(source / 'capture.json')
    if report['status'] not in ('pending-review', 'ready'):
        raise ValueError('Capture must pass registration before pose preview')
    split = freeze_split(root, scene, settings, check_capture=False)
    if digest_json(split) != report['split_hash']:
        raise ValueError('Capture split changed before pose preview')
    directory = scene_input(native_workspace(root), scene)[0]
    config = NerfstudioDataParserConfig(data=directory, downscale_factor=settings['DownscaleFactor'],
                                      eval_mode='filename', load_3D_points=True)
    points = config.setup().get_dataparser_outputs(split='train').metadata['points3D_xyz'].tolist()
    output = root / 'reports/custom_capture' / scene.split(':')[1]
    output.mkdir(parents=True, exist_ok=True)
    payload = output / '.pose-input.json'
    write_json(payload, {'scene': scene, 'split': split, 'points': points})
    # Torch and NumPy's MKL initialize incompatible OpenMP DLLs on this pinned
    # Windows environment. Plot in a fresh CPU process with no Torch imports.
    # Keep the SDK loader unchanged; never enable KMP_DUPLICATE_LIB_OK.
    entrypoint = ('import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); '
                  'from topic16.data import plot_capture_evidence; '
                  'plot_capture_evidence(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))')
    try:
        run_command(root, [sys.executable, '-c', entrypoint, str(root / 'src'), str(root), str(payload), str(output)],
                    output / 'pose-preview.log')
    finally:
        payload.unlink(missing_ok=True)
    return read_json(output / 'pose_evidence.json')


def plot_capture_evidence(root: Path, payload: Path, output: Path) -> dict:
    """CPU plotting worker, isolated from the pinned Torch/OpenMP runtime."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image
    record = read_json(payload)
    scene, split, points = record['scene'], record['split'], np.asarray(record['points'])
    cameras = split['train'] + split['eval']
    rotations = np.asarray([camera['camera_to_world'] for camera in cameras])[:, :, :3]
    error = float(np.max(np.abs(np.swapaxes(rotations, 1, 2) @ rotations - np.eye(3))))
    determinants = np.linalg.det(rotations)
    if error > 1e-3 or np.max(np.abs(determinants - 1)) > 1e-3 or not np.isfinite(points).all():
        raise ValueError('Invalid camera rotations or sparse coordinates')
    sampled = points[::max(1, len(points) // 12000)]
    figure = plt.figure(figsize=(12, 9))
    axis = figure.add_subplot(111, projection='3d')
    axis.scatter(*sampled.T, s=1, c='#999999', alpha=0.3)
    centers = np.asarray([camera['camera_to_world'] for camera in cameras])[:, :, 3]
    for index, camera in enumerate(cameras):
        matrix = np.asarray(camera['camera_to_world'])
        center, rotation = matrix[:, 3], matrix[:, :3]
        depth = 0.06
        width, height = depth * camera['width'] / (2 * camera['fx']), depth * camera['height'] / (2 * camera['fy'])
        corners = np.array([[-width, -height, -depth], [width, -height, -depth],
                            [width, height, -depth], [-width, height, -depth]]) @ rotation.T + center
        color = '#e88424' if index < len(split['train']) else '#1479cb'
        for corner in corners:
            axis.plot(*np.stack([center, corner]).T, color=color, linewidth=0.5)
    bounds = np.concatenate([np.quantile(points, [0.01, 0.99], axis=0), centers])
    midpoint = (bounds.min(axis=0) + bounds.max(axis=0)) / 2
    radius = float((bounds.max(axis=0) - bounds.min(axis=0)).max() / 2)
    for dimension, setter in enumerate((axis.set_xlim, axis.set_ylim, axis.set_zlim)):
        setter(midpoint[dimension] - radius, midpoint[dimension] + radius)
    axis.set_box_aspect((1, 1, 1))
    axis.set_title('Frozen camera frustums: train orange / eval blue; sparse points gray')
    figure.tight_layout()
    figure.savefig(output / 'poses.png', dpi=160)
    plt.close(figure)
    figure, axes = plt.subplots(1, 3, figsize=(12, 8))
    visibility = []
    for axis, index in zip(axes, (0, len(split['eval']) // 2, len(split['eval']) - 1)):
        camera = split['eval'][index]
        matrix = np.asarray(camera['camera_to_world'])
        local = (sampled - matrix[:, 3]) @ matrix[:, :3]
        depth = -local[:, 2]
        valid = depth > 1e-8
        safe_depth = np.where(valid, depth, 1)
        x = camera['fx'] * local[:, 0] / safe_depth + camera['cx']
        y = camera['cy'] - camera['fy'] * local[:, 1] / safe_depth
        visible = valid & (x >= 0) & (y >= 0) & (x < camera['width']) & (y < camera['height'])
        with Image.open(inside(root, camera['path'])) as image:
            axis.imshow(image)
        axis.scatter(x[visible], y[visible], s=1, c='#ff4646', alpha=0.4)
        axis.set_title(f'Eval {index}: sparse projection')
        axis.axis('off')
        visibility.append({'eval_index': index, 'visible_sampled_points': int(visible.sum())})
    figure.tight_layout()
    figure.savefig(output / 'projections.png', dpi=160)
    plt.close(figure)
    evidence = {'scene': scene, 'split_hash': digest_json(split), 'camera_count': len(cameras),
                'sparse_point_count': len(points), 'rotation_orthogonality_max_error': error,
                'rotation_determinant_min': float(determinants.min()), 'rotation_determinant_max': float(determinants.max()),
                'sampled_projection_visibility': visibility, 'visual_approval': False,
                'files': [{'path': relative(root, path), 'sha256': sha256(path)} for path in sorted(output.glob('*.png'))]}
    write_json(output / 'pose_evidence.json', evidence)
    print(f'Pose evidence ready for visual review: {output}')
    return evidence


def preparation_settings(settings: dict) -> dict:
    # GPU safety/demo/video options cannot change the canonical image grid.
    return {key: settings[key] for key in ('NerfstudioCommit', 'TorchVersion', 'DownscaleFactor', 'EvalInterval')}


def verify_preparation_settings(root: Path, destination: Path, record: dict, settings: dict) -> bool:
    expected = digest_json(preparation_settings(settings))
    if 'data_settings_hash' in record:
        return record['data_settings_hash'] == expected
    # Legacy preparations have the full registry hash. Use their immutable run
    # snapshots to prove compatibility; never silently accept a different grid.
    for path in sorted((root / 'artifacts/logs').glob('*/*/*/settings.json')):
        previous = read_json(path)
        if digest_json(previous) == record['settings_hash'] and digest_json(preparation_settings(previous)) == expected:
            return True
    return record['settings_hash'] == experiment_settings_hash(settings)


def capture_inputs(train: Path, evaluation: Path) -> dict:
    from PIL import Image
    result = {}
    for label, directory in (("train", train), ("eval", evaluation)):
        if not directory.is_dir():
            raise ValueError(f"Missing {label} folder: {directory}")
        files = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        if len(files) < (8 if label == "train" else 2):
            raise ValueError("Need at least eight train and two held-out images")
        hashes = set()
        result[label] = []
        for path in files:
            file_required(path)
            with Image.open(path) as image:
                image.verify()
            digest = sha256(path)
            if digest in hashes:
                raise ValueError(f"Duplicate {label} image: {path.name}")
            hashes.add(digest)
            result[label].append({"name": path.name, "sha256": digest})
    if {f["sha256"] for f in result["train"]} & {f["sha256"] for f in result["eval"]}:
        raise ValueError("Train/eval capture leakage")
    # Upstream merges its rename maps keyed by original relative filename.
    if {f["name"] for f in result["train"]} & {f["name"] for f in result["eval"]}:
        raise ValueError("Train/eval original filenames must be distinct for upstream rename mapping")
    return result


def scene_source(root: Path, scene: str) -> tuple[Path, str, str]:
    import re
    if scene == "poster":
        return root / "data/processed/nerfstudio/poster", "nerfstudio-data", "interval"
    if scene in ("garden", "bonsai", "room"):
        return root / "data/raw/mipnerf360" / scene, "colmap", "interval"
    if re.fullmatch(r"custom:[a-z0-9][a-z0-9_-]*", scene):
        return root / "data/processed/custom" / scene.split(":")[1], "nerfstudio-data", "filename"
    raise ValueError(f"Invalid dataset key: {scene}")


def scene_input(root: Path, scene: str) -> tuple[Path, str, str]:
    scene_source(root, scene)  # Validate the key even before constructing a path.
    return root / 'data/processed/canonical' / scene.replace(':', '-'), 'nerfstudio-data', ('filename' if scene.startswith('custom:') else 'interval')


def source_parser(root: Path, scene: str, settings: dict, downscale: int):
    from nerfstudio.data.dataparsers.colmap_dataparser import ColmapDataParserConfig
    from nerfstudio.data.dataparsers.nerfstudio_dataparser import NerfstudioDataParserConfig
    directory, name, mode = scene_source(native_workspace(root), scene)
    if name == 'colmap':
        for filename in ('cameras.bin', 'images.bin', 'points3D.bin'):
            file_required(directory / 'sparse/0' / filename)
        config = ColmapDataParserConfig(data=directory, colmap_path=Path('sparse/0'))
    else:
        metadata = read_json(file_required(directory / 'transforms.json'))
        if not metadata.get('ply_file_path'):
            raise ValueError('Source requires explicit sparse PLY; finish preprocessing first')
        file_required(inside(directory, metadata['ply_file_path']))
        config = NerfstudioDataParserConfig(data=directory)
    config.downscale_factor = downscale
    config.eval_mode = mode
    config.eval_interval = settings['EvalInterval']
    config.load_3D_points = True
    return directory, config.setup()


def prepare_scene(root: Path, scene: str, settings: dict) -> Path:
    """Materialize common pinhole GT using the undistorter from the pinned release.

    Splatfacto's FullImageDatamanager otherwise crops distorted GT while Nerfacto
    renders the original pixels. Both must train/evaluate one canonical image grid.
    Source cameras/splits are read once; transformed sparse points follow those poses.
    """
    import numpy as np
    import open3d as o3d
    import torch
    torch.set_num_threads(settings['CpuWorkerThreads'])
    from PIL import Image
    from nerfstudio.data.datamanagers.full_images_datamanager import _undistort_image
    source, parser = source_parser(root, scene, settings, downscale=1)
    destination, _, _ = scene_input(native_workspace(root), scene)
    if destination.exists():
        record = read_json(destination / 'preparation.json')
        if record['status'] in ('running', 'failed'):
            from datetime import datetime, timezone
            archive = destination.parent / '.failed' / (destination.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
            archive.parent.mkdir(exist_ok=True)
            destination.rename(archive)
            print(f'Interrupted canonical preparation preserved: {archive}', flush=True)
    if destination.exists():
        record = read_json(destination / 'preparation.json')
        if record['status'] != 'succeeded' or not verify_preparation_settings(root, destination, record, settings):
            raise ValueError('Canonical scene is partial or belongs to a different registry; preserve it and use a new scene/protocol version')
        for item in record['source_files']:
            if sha256(file_required(inside(root, item['path']))) != item['sha256']:
                raise ValueError('Source data changed after canonical preparation')
        for item in record['output_files']:
            if sha256(file_required(inside(destination, item['path']))) != item['sha256']:
                raise ValueError('Canonical data modified after preparation')
        if 'data_settings_hash' not in record:
            import shutil
            backup = destination / 'preparation.full-registry.v1.json.bak'
            if not backup.exists():
                shutil.copy2(destination / 'preparation.json', backup)
            record['data_settings_hash'] = digest_json(preparation_settings(settings))
            write_json(destination / 'preparation.json', record)
        return destination
    destination.mkdir(parents=True)
    record = {'schema_version': '1.0', 'status': 'running', 'scene': scene,
              'settings_hash': experiment_settings_hash(settings), 'data_settings_hash': digest_json(preparation_settings(settings)),
              'source_files': [], 'output_files': [],
              'operation': 'pinhole-v1: pinned FullImageDatamanager undistort then Pillow LANCZOS downscale',
              'downscale_factor': settings['DownscaleFactor']}
    write_json(destination / 'preparation.json', record)
    try:
        folders = ['images'] + ([f"images_{settings['DownscaleFactor']}"] if settings['DownscaleFactor'] > 1 else [])
        for folder in folders:
            (destination / folder).mkdir(exist_ok=True)
        metadata = {'camera_model': 'OPENCV', 'orientation_override': 'none', 'ply_file_path': 'sparse_pc.ply',
                    'frames': [], 'train_filenames': [], 'val_filenames': [], 'test_filenames': []}
        points = None
        for label, split_name in (('train', 'train'), ('eval', 'test')):
            outputs = parser.get_dataparser_outputs(split=split_name)
            if outputs.mask_filenames:
                raise ValueError('Masked sources require an explicitly designed paired mask protocol')
            points = outputs.metadata
            for index, source_image in enumerate(outputs.image_filenames):
                record['source_files'].append({'path': relative(root, source_image), 'sha256': sha256(source_image)})
                with Image.open(source_image) as original:
                    pixels = np.asarray(original.convert('RGB')).copy()
                camera = outputs.cameras[index].reshape(())
                K = camera.get_intrinsics_matrices().numpy()
                if camera.distortion_params is not None and torch.any(camera.distortion_params != 0):
                    K, pixels, _ = _undistort_image(camera, camera.distortion_params.numpy(), {}, pixels, K)
                filename = f'frame_{label}_{index:05d}.png'
                image = Image.fromarray(pixels)
                image.save(destination / 'images' / filename)
                factor = settings['DownscaleFactor']
                if factor > 1:
                    image.resize((image.width // factor, image.height // factor), Image.Resampling.LANCZOS).save(destination / f'images_{factor}' / filename)
                pose = outputs.cameras.camera_to_worlds[index].tolist() + [[0.0, 0.0, 0.0, 1.0]]
                path = 'images/' + filename
                metadata['frames'].append({'file_path': path, 'transform_matrix': pose, 'w': image.width,
                    'h': image.height, 'fl_x': float(K[0, 0]), 'fl_y': float(K[1, 1]),
                    'cx': float(K[0, 2]), 'cy': float(K[1, 2]), 'k1': 0.0, 'k2': 0.0, 'p1': 0.0, 'p2': 0.0})
                for field in (('train_filenames',) if label == 'train' else ('val_filenames', 'test_filenames')):
                    metadata[field].append(path)
        if points is None or 'points3D_xyz' not in points or len(points['points3D_xyz']) == 0:
            raise ValueError('Source contains no valid sparse initialization points')
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(points['points3D_xyz'].numpy())
        cloud.colors = o3d.utility.Vector3dVector(points['points3D_rgb'].numpy() / 255.0)
        if not o3d.io.write_point_cloud(str(destination / 'sparse_pc.ply'), cloud):
            raise ValueError('Could not write canonical sparse PLY')
        write_json(destination / 'transforms.json', metadata)
        pose_files = sorted(source.glob('sparse/0/*.bin')) + sorted(source.glob('colmap/sparse/*/*.bin')) + sorted(source.glob('*.ply'))
        if (source / 'transforms.json').exists():
            pose_files.append(source / 'transforms.json')
        record['source_files'] += [{'path': relative(root, path), 'sha256': sha256(path)} for path in pose_files]
        record['output_files'] = [{'path': path.relative_to(destination).as_posix(), 'sha256': sha256(path)}
                                  for path in sorted(destination.rglob('*')) if path.is_file() and path.name != 'preparation.json']
        record['status'] = 'succeeded'
        write_json(destination / 'preparation.json', record)
        return destination
    except BaseException as error:
        record.update(status='failed', failure_reason=str(error))
        write_json(destination / 'preparation.json', record)
        raise


def freeze_split(root: Path, scene: str, settings: dict, check_capture: bool = True) -> dict:
    """Use the actual upstream camera ordering, intrinsics and automatic transforms.

    This deliberately avoids reproducing COLMAP binary parsing or filename ordering.
    No model or optimizer is allocated during this CPU preflight.
    """
    from PIL import Image
    from nerfstudio.data.dataparsers.colmap_dataparser import ColmapDataParserConfig
    from nerfstudio.data.dataparsers.nerfstudio_dataparser import NerfstudioDataParserConfig
    directory, parser_name, mode = scene_input(native_workspace(root), scene)
    if not directory.is_dir():
        raise ValueError(f"Missing scene: {directory}")
    if parser_name == "colmap":
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            file_required(directory / "sparse/0" / name)
        config = ColmapDataParserConfig(data=directory, colmap_path=Path("sparse/0"))
    else:
        file_required(directory / "transforms.json")
        metadata = read_json(directory / "transforms.json")
        if not metadata.get("ply_file_path"):
            raise ValueError("Nerfstudio scene requires an explicit sparse PLY; preprocessing must finish before training")
        file_required(inside(directory, metadata["ply_file_path"]))
        config = NerfstudioDataParserConfig(data=directory)
    config.downscale_factor = settings["DownscaleFactor"]
    config.eval_mode = mode
    config.eval_interval = settings["EvalInterval"]
    # Record the canonical sparse points used by Splatfacto initialization.
    config.load_3D_points = True
    parser = config.setup()
    result = {"schema_version": "1.0", "scene": scene, "downscale_factor": config.downscale_factor}
    for name, split_name in (("train", "train"), ("eval", "test")):
        output = parser.get_dataparser_outputs(split=split_name)
        cameras = output.cameras
        result[name] = []
        for index, path in enumerate(output.image_filenames):
            path = inside(directory, path)
            file_required(path)
            with Image.open(path) as image:
                image.verify()
            result[name].append({
                "path": relative(root, path), "sha256": sha256(path),
                "width": int(cameras.width[index].item()), "height": int(cameras.height[index].item()),
                "fx": float(cameras.fx[index].item()), "fy": float(cameras.fy[index].item()),
                "cx": float(cameras.cx[index].item()), "cy": float(cameras.cy[index].item()),
                "camera_to_world": cameras.camera_to_worlds[index].tolist(),
                "camera_type": int(cameras.camera_type[index].item()),
                "distortion_params": cameras.distortion_params[index].tolist() if cameras.distortion_params is not None else [],
            })
    pose_files = sorted(directory.glob("sparse/0/*.bin")) if parser_name == "colmap" else [directory / "transforms.json"]
    pose_files += sorted(directory.glob("*.ply"))
    pose_files += sorted(directory.glob("colmap/sparse/0/*.bin"))
    result["pose_files"] = [{"path": relative(root, file_required(path)), "sha256": sha256(path)} for path in pose_files]
    validate_split(result)
    if scene.startswith("custom:") and check_capture:
        validate_capture_review(root, scene, result)
    return result


def finish_capture(root: Path, scene: str, settings: dict, inputs: dict) -> dict:
    directory, _, _ = scene_source(root, scene)
    transform = read_json(directory / "transforms.json")
    frames = transform["frames"]
    train_frames = [frame for frame in frames if Path(frame["file_path"]).name.startswith("frame_train_")]
    eval_frames = [frame for frame in frames if Path(frame["file_path"]).name.startswith("frame_eval_")]
    if len(train_frames) + len(eval_frames) != len(frames):
        raise ValueError("Processed capture contains frames with unknown split")
    ratio = len(train_frames) / len(inputs["train"])
    report = {"schema_version": "1.0", "scene": scene, "status": "pending-review", "inputs": inputs,
              "registered_train": len(train_frames), "total_train": len(inputs["train"]),
              "train_registration_ratio": ratio, "registered_eval": len(eval_frames),
              "total_eval": len(inputs["eval"]), "visual_review": {"approved": False}}
    write_json(directory / "capture.json", report)
    if ratio < settings["MinimumRegistrationRatio"] or len(eval_frames) != len(inputs["eval"]):
        report["status"] = "failed"
        write_json(directory / "capture.json", report)
        raise ValueError("Registration gate failed (train >=90%; every eval image must register)")
    prepare_scene(root, scene, settings)
    split = freeze_split(root, scene, settings, check_capture=False)
    report["split_hash"] = digest_json(split)
    write_json(directory / "split.json", split)
    write_json(directory / "capture.json", report)
    return report
