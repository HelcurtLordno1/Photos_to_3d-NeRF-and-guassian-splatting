"""Freeze final-campaign inputs without changing historical data or cameras."""
from pathlib import Path
import copy
import random
import shutil
import time
import numpy as np
from .contracts import read_json,write_json,sha256,digest_json,inside,relative,validate_split,native_workspace


def validation_indices(frames,count=15,seed=42):
    if not 0<count<len(frames):raise ValueError('Validation must leave training views')
    poses=np.asarray([f['camera_to_world'] for f in frames],dtype=float)
    positions=poses[:,:3,3];scale=max(float(np.linalg.norm(positions-positions.mean(0),axis=1).max()),1e-8)
    directions=-poses[:,:3,2];features=np.c_[(positions-positions.mean(0))/scale,directions*.5]
    selected=[random.Random(seed).randrange(len(frames))]
    distances=np.full(len(frames),np.inf)
    for _ in range(1,count):
        distances=np.minimum(distances,np.sum((features-features[selected[-1]])**2,axis=1));distances[selected]=-1
        selected.append(int(np.argmax(distances)))
    return sorted(selected)


def prepare_validation(root):
    base=read_json(root/'artifacts/jobs/research/tea-research-v4/declaration.json')
    original=read_json(inside(root,base['split']));indices=validation_indices(original['train'])
    output=root/'reports/final-quality-v1/validation';output.mkdir(parents=True,exist_ok=True)
    split={**copy.deepcopy(original),'scene':'custom:tea-final-validation',
           'train':[f for i,f in enumerate(original['train']) if i not in indices],
           'eval':[original['train'][i] for i in indices],
           'validation_scope':{'parent_split':base['split'],'parent_split_hash':digest_json(original),
               'indices_from_train':indices,'seed':42,'selection':'pose-only farthest coverage; sorted capture order',
               'sfm':'Original frozen SfM scope, not regenerated from90views; exploratory same-capture validation'}}
    validate_split(split);path=output/'split.json'
    if path.exists():
        if read_json(path)!=split:raise ValueError('Validation split changed')
    else:write_json(path,split)
    from PIL import Image,ImageDraw
    sheet=output/'ground-truth.jpg'
    if not sheet.exists():
        image=Image.new('RGB',(5*180,3*345),'#222');draw=ImageDraw.Draw(image)
        for i,frame in enumerate(split['eval']):
            p=inside(root,frame['path'])
            if sha256(p)!=frame['sha256']:raise ValueError('Validation GT changed')
            with Image.open(p) as item:
                item=item.convert('RGB');item.thumbnail((180,320));image.paste(item,((i%5)*180,(i//5)*345+22))
            draw.text(((i%5)*180+2,(i//5)*345+2),f'val{i} / train{indices[i]}',fill='white')
        image.save(sheet,quality=94)
    return path


def materialize_scene(root,baseline,scene,campaign):
    """Copy only measured-resolution pixels, and transform existing sparse points.

    No original-image duplication, resizing, pose fitting or new SfM processing.
    """
    from .capture import capture_split
    from .improved_adapter import verify_camera
    frozen,provenance=capture_split(baseline,scene)
    output=root/'data/processed/final'/campaign/scene;path=output/'split.json'
    if path.exists():
        saved=read_json(path)
        if saved['baseline_capture']!=provenance:raise ValueError('Final canonical capture changed')
        for f in saved['train']+saved['eval']+saved['pose_files']:
            if sha256(inside(root,f['path']))!=f['sha256']:raise ValueError('Final canonical input changed')
        return path
    stage=output.with_name(output.name+'.staging-'+str(time.time_ns()));(stage/'images').mkdir(parents=True)
    split={**copy.deepcopy(frozen),'scene':scene,'baseline_capture':provenance,'train':[],'eval':[]}
    for label in ('train','eval'):
        for i,frame in enumerate(frozen[label]):
            verify_camera(frame);source=inside(baseline,frame['path'])
            if sha256(source)!=frame['sha256']:raise ValueError('Baseline pixels changed')
            name=f'{label}_{i:04d}'+source.suffix;shutil.copyfile(source,stage/'images'/name)
            split[label].append({**frame,'path':relative(root,output/'images'/name)})
    from nerfstudio.data.dataparsers.nerfstudio_dataparser import NerfstudioDataParserConfig
    import open3d as o3d
    canonical=inside(baseline,frozen['train'][0]['path']).parent.parent
    parser=NerfstudioDataParserConfig(data=native_workspace(baseline)/canonical.relative_to(baseline),
        downscale_factor=frozen['downscale_factor'],eval_mode='filename' if scene.startswith('custom:') else 'interval',load_3D_points=True).setup()
    parsed=parser.get_dataparser_outputs(split='train')
    if not np.allclose(parsed.cameras.camera_to_worlds.numpy(),[f['camera_to_world'] for f in frozen['train']],atol=1e-6):
        raise ValueError('Sparse point frame differs from frozen baseline cameras')
    cloud=o3d.geometry.PointCloud();cloud.points=o3d.utility.Vector3dVector(parsed.metadata['points3D_xyz'].numpy())
    cloud.colors=o3d.utility.Vector3dVector(parsed.metadata['points3D_rgb'].numpy().astype(float)/255)
    alias=native_workspace(root)/stage.relative_to(root)
    if not o3d.io.write_point_cloud(str(alias/'sparse_pc.ply'),cloud):raise ValueError('Cannot freeze sparse points')
    write_json(stage/'capture.json',provenance)
    split['pose_files']=[{'path':relative(root,output/name),'sha256':sha256(stage/name)} for name in ('sparse_pc.ply','capture.json')]
    validate_split(split);write_json(stage/'split.json',split);stage.rename(output)
    return path
