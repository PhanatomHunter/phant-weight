"""Folder bundles: every regular file, including config and tokenizer assets."""
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from .codec import convert, verify, FormatError

MANIFEST = 'manifest.json'

def _relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or '\x00' in value:
        raise FormatError('Unsafe manifest path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')):
        raise FormatError('Unsafe manifest path')
    return Path(*p.parts)

def manifest(source):
    path = Path(source) / MANIFEST
    if path.is_symlink() or path.stat().st_size > 10 * 1024 * 1024:
        raise FormatError('Invalid or oversized manifest')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('format') != 'modelpack-v4-folder-1' or not isinstance(data.get('files'), list) or not isinstance(data.get('directories'), list):
        raise FormatError('Invalid bundle format')
    if len(data['files']) + len(data['directories']) > 100000:
        raise FormatError('Too many bundle entries')
    seen = set()
    archives = set()
    for entry in data['files']:
        if not isinstance(entry, dict) or not all(key in entry for key in ('path', 'bytes', 'sha256', 'archive')):
            raise FormatError('Invalid file entry')
        _relative(entry['path'])
        if entry['path'] in seen:
            raise FormatError('Duplicate path')
        seen.add(entry['path'])
        if not isinstance(entry['bytes'], int) or entry['bytes'] < 0 or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            raise FormatError('Invalid manifest metadata')
        if not re.fullmatch(r'[0-9]{6}\.lcv', entry['archive']) or entry['archive'] in archives:
            raise FormatError('Invalid archive path')
        archives.add(entry['archive'])
    for name in data['directories']:
        _relative(name)
        if name in seen:
            raise FormatError('Duplicate directory path')
        seen.add(name)
    return data

def _check_source(source):
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Expected a real directory, not a symlink')

def _destination(destination):
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(str(destination))
    if not destination.parent.is_dir():
        raise ValueError('Destination parent must exist')

def pack_folder(source, destination):
    source, destination = Path(source), Path(destination)
    _check_source(source)
    _destination(destination)
    if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents:
        raise ValueError('Bundle destination must be outside source directory')
    temp = Path(tempfile.mkdtemp(prefix='.modelpack-bundle-', dir=destination.parent))
    try:
        entries, directories = [], []
        for path in sorted(source.rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlinks are not supported: ' + str(path))
            rel = path.relative_to(source).as_posix()
            _relative(rel)
            if path.is_dir():
                directories.append(rel)
            elif path.is_file():
                archive = f'{len(entries):06d}.lcv'
                result = convert(path, temp / archive)
                entries.append({'path': rel, 'archive': archive, 'bytes': result['input_bytes'], 'sha256': result['sha256']})
            else:
                raise ValueError('Non-regular filesystem entry')
        data = {'format': 'modelpack-v4-folder-1', 'files': entries, 'directories': directories}
        (temp / MANIFEST).write_text(json.dumps(data, indent=2), encoding='utf-8')
        manifest(temp)  # Validate generated bundle before publishing.
        _destination(destination)
        temp.rename(destination)
        return {'files': len(entries), 'input_bytes': sum(e['bytes'] for e in entries), 'bundle_bytes': sum(p.stat().st_size for p in destination.iterdir())}
    finally:
        if temp.exists():
            shutil.rmtree(temp)

def verify_folder(source, max_output_bytes=None):
    source = Path(source)
    _check_source(source)
    data = manifest(source)
    total = sum(e['bytes'] for e in data['files'])
    if max_output_bytes is not None and total > max_output_bytes:
        raise FormatError('Output size limit exceeded')
    for entry in data['files']:
        path = source / entry['archive']
        if path.is_symlink() or not path.is_file():
            raise FormatError('Missing or unsafe archive')
        result = verify(path, entry['bytes'])
        if result['sha256'] != entry['sha256'] or result['output_bytes'] != entry['bytes']:
            raise FormatError('Manifest does not match archive')
    return {'files': len(data['files']), 'output_bytes': total, 'verified': True}

def unpack_folder(source, destination, max_output_bytes=None):
    source, destination = Path(source), Path(destination)
    _check_source(source)
    _destination(destination)
    data = manifest(source)
    total = sum(e['bytes'] for e in data['files'])
    if max_output_bytes is not None and total > max_output_bytes:
        raise FormatError('Output size limit exceeded')
    temp = Path(tempfile.mkdtemp(prefix='.modelpack-bundle-', dir=destination.parent))
    try:
        for name in data['directories']:
            (temp / _relative(name)).mkdir(parents=True, exist_ok=True)
        for entry in data['files']:
            archive = source / entry['archive']
            if archive.is_symlink() or not archive.is_file():
                raise FormatError('Missing or unsafe archive')
            path = temp / _relative(entry['path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            result = convert(archive, path, decode=True, max_output_bytes=entry['bytes'])
            if result['sha256'] != entry['sha256'] or result['output_bytes'] != entry['bytes']:
                raise FormatError('Manifest does not match archive')
        _destination(destination)
        temp.rename(destination)
        return {'files': len(data['files']), 'output_bytes': total, 'verified': True}
    finally:
        if temp.exists():
            shutil.rmtree(temp)
