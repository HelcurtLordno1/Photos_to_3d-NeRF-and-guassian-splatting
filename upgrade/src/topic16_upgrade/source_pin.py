"""Replay the immutable training adapter while recording the repaired controller.

Existing source archives and run identities are never rewritten. A study pin
is explicit recovery evidence, not permission to accept arbitrary source drift.
"""
import os
import zipfile
import shutil
from pathlib import Path
from .contracts import inside, relative, sha256, digest_json, read_json, write_json, utc_now, file_required

PIN_ENV = 'TOPIC16_UPGRADE_SOURCE_PIN'
SOURCE_SUFFIXES = ('.py', '.ps1', '.psd1', '.json')


def source_files(root):
    return {relative(root,p):sha256(p) for folder in ('src','scripts','configs')
            for p in sorted((root/folder).rglob('*')) if p.is_file() and p.suffix in SOURCE_SUFFIXES}


def identity(files):
    return digest_json({k:v for k,v in files.items() if Path(k).suffix in ('.py','.ps1','.psd1')})


def verify_pin(root, path, study=None):
    path = inside(root/'artifacts/source-pins', path)
    record = read_json(path)
    if record.get('schema_version') != 'training-source-pin-1' or (study and record['study'] != study):
        raise ValueError('Invalid study training-source pin')
    tree = inside(root/'artifacts/source-pins', inside(root,record['tree']))
    archive = inside(root/'artifacts/source-pins', inside(root,record['archive']))
    if sha256(file_required(archive)) != record['archive_sha256']:
        raise ValueError('Pinned training source archive changed')
    if source_files(tree) != record['source_files'] or identity(record['source_files']) != record['source_id']:
        raise ValueError('Pinned training source bytes changed')
    # Registry/dependencies/protocols stay exact. Operational repairs belong to
    # a separately archived controller, never to an expanded training schedule.
    if sha256(root/'configs/project.psd1') != record['source_files']['configs/project.psd1']:
        raise ValueError('Registry changed since the pinned training study')
    return record, tree


def activate(root, study):
    pointer = root/'artifacts/jobs'/f'{study}-source-pin.json'
    os.environ.pop(PIN_ENV, None)
    if pointer.exists():
        reference = read_json(pointer)
        path = inside(root,reference['path'])
        if sha256(path) != reference['sha256']:
            raise ValueError('Study source-pin reference changed')
        verify_pin(root,path,study)
        os.environ[PIN_ENV] = str(path)


def execution_sources(root):
    pin = os.environ.get(PIN_ENV)
    if pin:
        record, tree = verify_pin(root,Path(pin))
        return tree, record['source_files'], record
    return root, source_files(root), None


def create_pin(root, study):
    plan = read_json(root/'artifacts/jobs'/f'{study}-plan.json')
    expected = {j['identity']['source_id'] for j in plan['jobs']}
    if len(expected) != 1:
        raise ValueError('Study has mixed training source identities')
    expected = expected.pop()
    ledger = read_json(root/'artifacts/jobs/ledger.json')
    candidates = [j for j in ledger['jobs'].values() if j['study']==study and j.get('config')]
    if not candidates:
        raise ValueError('No recorded training archive for this study')
    config = inside(root/'artifacts/runs',inside(root,candidates[0]['config']))
    logs = root/'artifacts/logs'/config.parent.relative_to(root/'artifacts/runs')
    provenance = read_json(logs/'provenance.json')
    archive = file_required(logs/'source.zip')
    if identity(provenance['source_files']) != expected or sha256(archive) != provenance['source_archive_sha256']:
        raise ValueError('Study source archive differs from the original experiment key')
    directory = root/'artifacts/source-pins'/expected
    directory.mkdir(parents=True,exist_ok=True)
    target_archive = directory/'source.zip'
    if target_archive.exists():
        if sha256(target_archive) != provenance['source_archive_sha256']:
            raise ValueError('Existing recovery source archive differs')
    else:
        shutil.copyfile(archive,target_archive)
    tree = directory/'tree'
    with zipfile.ZipFile(target_archive) as snapshot:
        if set(snapshot.namelist()) != set(provenance['source_files']):
            raise ValueError('Recovery archive file list differs')
        import hashlib
        for name, expected_hash in provenance['source_files'].items():
            payload = snapshot.read(name)
            if hashlib.sha256(payload).hexdigest() != expected_hash:
                raise ValueError('Recovery archive member checksum mismatch')
            target = inside(tree,name)
            if target.exists():
                if sha256(target) != expected_hash: raise ValueError('Existing pinned source differs')
            else:
                target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(payload)
    path = directory/f'{study}.json'
    record = {'schema_version':'training-source-pin-1','study':study,'source_id':expected,
              'created_at':utc_now(),'archive':relative(root,target_archive),'archive_sha256':sha256(target_archive),
              'tree':relative(root,tree),'source_files':provenance['source_files'],
              'original_config':relative(root,config),
              'scope':'Original training adapter replay; live validation/controller repairs recorded separately'}
    if not path.exists(): write_json(path,record)
    verify_pin(root,path,study)
    write_json(root/'artifacts/jobs'/f'{study}-source-pin.json',{'path':relative(root,path),'sha256':sha256(path)})
    return read_json(path)


def freeze_current(root, study, reference=None):
    """Pin a new declared study before its first GPU job, or share a verified pin."""
    if reference:
        record, tree = verify_pin(root,reference)
        files=record['source_files'];directory=tree.parent;archive=inside(root,record['archive'])
    else:
        files=source_files(root);sid=identity(files)
        directory=root/'artifacts/source-pins'/sid;directory.mkdir(parents=True,exist_ok=True)
        archive=directory/'source.zip';tree=directory/'tree'
        if not archive.exists():
            with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as snapshot:
                for name in files:snapshot.write(inside(root,name),name)
        with zipfile.ZipFile(archive) as snapshot:
            import hashlib
            if set(snapshot.namelist())!=set(files):raise ValueError('Existing source pin differs')
            for name,expected in files.items():
                payload=snapshot.read(name)
                if hashlib.sha256(payload).hexdigest()!=expected:raise ValueError('Source pin member differs')
                destination=inside(tree,name)
                if destination.exists():
                    if sha256(destination)!=expected:raise ValueError('Frozen source tree changed')
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(payload)
    path=directory/f'{study}.json'
    value={'schema_version':'training-source-pin-1','study':study,'source_id':identity(files),
           'created_at':utc_now(),'tree':relative(root,tree),'archive':relative(root,archive),
           'archive_sha256':sha256(archive),'source_files':files,
           'scope':'Full-study source frozen before execution; controller archived separately'}
    if path.exists():
        previous=read_json(path)
        if previous['source_files']!=files:raise ValueError('Study already uses another source')
    else:write_json(path,value)
    verify_pin(root,path,study)
    pointer=root/'artifacts/jobs'/f'{study}-source-pin.json'
    target={'path':relative(root,path),'sha256':sha256(path)}
    if pointer.exists() and read_json(pointer)!=target:raise ValueError('Existing study pin must not be replaced')
    write_json(pointer,target)
    return path
