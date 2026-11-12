"""Read train-only COLMAP track identities via the canonical preparation map."""
import struct
from pathlib import Path
from .contracts import read_json, inside, sha256


def read_tracks(path, wanted):
    result = {}
    with path.open('rb') as stream:
        count, = struct.unpack('<Q', stream.read(8))
        if count > 1_000_000:
            raise ValueError('Unreasonable COLMAP image count')
        for _ in range(count):
            stream.read(64)  # image ID, quaternion, translation, camera ID
            name = bytearray()
            while True:
                value = stream.read(1)
                if not value or len(name) > 4096:
                    raise ValueError('Invalid COLMAP image name')
                if value == b'\0': break
                name.extend(value)
            name = name.decode('utf-8')
            observations, = struct.unpack('<Q', stream.read(8))
            if observations > 10_000_000:
                raise ValueError('Unreasonable COLMAP observation count')
            if name in wanted:
                tracks = set()
                for _ in range(observations):
                    _, _, point = struct.unpack('<ddq', stream.read(24))
                    if point >= 0: tracks.add(point)
                result[name] = tracks
            else:
                # No held-out observation IDs, RGB or feature values are read.
                stream.seek(observations * 24, 1)
    return result


def training_visibility(baseline: Path, split):
    canonical = inside(baseline, split['train'][0]['path']).parent.parent
    prep_path = canonical / 'preparation.json'
    if not prep_path.exists():
        return None, {'status':'unavailable','reason':'Canonical preparation map unavailable'}
    preparation = read_json(prep_path)
    images = [f for f in preparation['source_files'] if Path(f['path']).suffix.lower() in ('.png','.jpg','.jpeg','.tif','.tiff')]
    count = len(split['train'])
    if len(images) != count + len(split['eval']):
        return None, {'status':'unavailable','reason':'Observation-to-canonical map length differs'}
    source_names = [Path(f['path']).name for f in images[:count]]
    # Mapping is accepted only when canonical train frame indices are the
    # documented sequential preparation order; never infer it from visual similarity.
    if any(Path(f['path']).stem != f'frame_train_{i:05d}' for i,f in enumerate(split['train'])):
        return None, {'status':'unavailable','reason':'Canonical train ordering is not the documented preparation mapping'}
    candidates = [f for f in preparation['source_files'] if Path(f['path']).name == 'images.bin']
    source_root = inside(baseline, images[0]['path']).parent.parent
    model_selection = source_root / 'model_selection.json'
    selection_hash = None
    if len(candidates) > 1 and model_selection.exists():
        selected = read_json(model_selection)['selected']['model']
        candidates = [f for f in candidates if Path(f['path']).parent.name == selected]
        selection_hash = sha256(model_selection)
    if len(candidates) != 1:
        return None, {'status':'unavailable','reason':'No unambiguous registered sparse observation model'}
    source = candidates[0]; path = inside(baseline,source['path'])
    if sha256(path) != source['sha256']:
        raise ValueError('Sparse observations changed from canonical preparation')
    tracks = read_tracks(path,set(source_names))
    if any(name not in tracks for name in source_names):
        return None, {'status':'unavailable','reason':'Sparse image names do not match the verified preparation map'}
    return [tracks[name] for name in source_names], {'status':'available','kind':'train-only sparse track Jaccard',
        'source_path':source['path'],'source_sha256':source['sha256'],'mapping_sha256':sha256(prep_path),
        'model_selection_sha256':selection_hash,
        'sfm_scope':'transductive SfM; held-out observations excluded from overlap aggregation'}
