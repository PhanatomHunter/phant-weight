import json
import os
from pathlib import Path
import pytest
from modelpack_v4.bundle import pack_folder, unpack_folder, verify_folder, manifest
from modelpack_v4.codec import FormatError

def fixture(tmp_path):
    src = tmp_path/'model'
    (src/'sub'/'empty').mkdir(parents=True)
    (src/'config.json').write_text('{"model_type":"llama"}')
    (src/'tokenizer.json').write_text('{"vocab": {}}')
    (src/'sub'/'weights.safetensors').write_bytes(os.urandom(15003))
    return src

def test_folder_roundtrip(tmp_path):
    src = fixture(tmp_path)
    bundle,out = tmp_path/'bundle',tmp_path/'out'
    r = pack_folder(src,bundle)
    assert r['files'] == 3
    assert verify_folder(bundle)['verified']
    assert unpack_folder(bundle,out)['files'] == 3
    for p in src.rglob('*'):
        target = out/p.relative_to(src)
        assert target.is_dir() if p.is_dir() else target.read_bytes() == p.read_bytes()
    assert (out/'sub'/'empty').is_dir()

def test_empty_folder(tmp_path):
    src=tmp_path/'empty';src.mkdir()
    pack_folder(src,tmp_path/'b')
    assert unpack_folder(tmp_path/'b',tmp_path/'out')['files'] == 0

@pytest.mark.parametrize('evil', ['../escape','/absolute','a/../../b','a\\evil','C:/evil','a//b','./foo'])
def test_traversal(tmp_path, evil):
    src=fixture(tmp_path);b=tmp_path/'b';pack_folder(src,b)
    m=json.loads((b/'manifest.json').read_text());m['files'][0]['path']=evil
    (b/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(FormatError):
        unpack_folder(b,tmp_path/'out')
    assert not (tmp_path/'out').exists()

def test_manifest_mismatch(tmp_path):
    src=fixture(tmp_path);b=tmp_path/'b';pack_folder(src,b)
    m=json.loads((b/'manifest.json').read_text());m['files'][0]['sha256']='0'*64
    (b/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(FormatError):
        verify_folder(b)
    with pytest.raises(FormatError):
        unpack_folder(b,tmp_path/'out')
    assert not (tmp_path/'out').exists()

def test_folder_limits(tmp_path):
    src=fixture(tmp_path);b=tmp_path/'b';pack_folder(src,b)
    with pytest.raises(FormatError):verify_folder(b,1)
    with pytest.raises(FormatError):unpack_folder(b,tmp_path/'out',1)

def test_output_inside_source(tmp_path):
    src=fixture(tmp_path)
    with pytest.raises(ValueError):pack_folder(src,src/'bundle')

def test_symlink_rejected(tmp_path):
    src=fixture(tmp_path)
    try:(src/'link').symlink_to(src/'config.json')
    except OSError:pytest.skip('Symlink creation not permitted')
    with pytest.raises(ValueError):pack_folder(src,tmp_path/'b')
    assert not (tmp_path/'b').exists()

def test_duplicate_paths(tmp_path):
    src=fixture(tmp_path);b=tmp_path/'b';pack_folder(src,b)
    m=json.loads((b/'manifest.json').read_text());m['files'][1]['path']=m['files'][0]['path'];(b/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(FormatError):manifest(b)

@pytest.mark.parametrize('data', [[], {'format':'modelpack-v4-folder-1','files':[None],'directories':[]}, {'format':'modelpack-v4-folder-1','files':[{}],'directories':[]}])
def test_invalid_manifest_schema(tmp_path, data):
    b=tmp_path/'b';b.mkdir();(b/'manifest.json').write_text(json.dumps(data))
    with pytest.raises(FormatError):manifest(b)
