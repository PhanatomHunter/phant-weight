import io
import os
import struct
import subprocess
import sys
import numpy as np
import pytest
from modelpack_v4.codec import BLOCK, MAGIC, FormatError, convert, verify, inverse, transform

@pytest.mark.parametrize('n', [0, 1, 2, 3, 4, 17, 1025, 65539])
def test_transform_lengths(n):
    raw = os.urandom(n)
    assert inverse(transform(raw), n) == raw

@pytest.mark.parametrize('raw', [b'', b'x', b'abcd'*10000, bytes(range(256))*100, np.arange(10000, dtype='<u2').tobytes(), os.urandom(12345)])
def test_roundtrip(tmp_path, raw):
    src, archive, restored = [tmp_path/x for x in ('src', 'a.lcv', 'out')]
    src.write_bytes(raw)
    packed = convert(src, archive)
    checked = verify(archive)
    unpacked = convert(archive, restored, decode=True)
    assert restored.read_bytes() == raw
    assert packed['sha256'] == checked['sha256'] == unpacked['sha256']
    assert packed['input_bytes'] == unpacked['output_bytes'] == len(raw)

def test_multiblock(tmp_path):
    src, archive, restored = [tmp_path/x for x in ('src', 'a', 'out')]
    raw = bytes(range(256))*(BLOCK//256) + os.urandom(1003)
    src.write_bytes(raw)
    assert convert(src, archive)['blocks'] == 2
    convert(archive, restored, decode=True)
    assert restored.read_bytes() == raw

def test_corruption_atomic(tmp_path):
    src, archive, out = [tmp_path/x for x in ('src', 'a', 'out')]
    src.write_bytes(b'abc'*1000)
    convert(src, archive)
    data = bytearray(archive.read_bytes())
    data[-1] ^= 1
    archive.write_bytes(data)
    with pytest.raises(FormatError):
        convert(archive, out, decode=True)
    assert not out.exists()
    assert not list(tmp_path.glob('.modelpack-*'))

@pytest.mark.parametrize('data', [b'', b'bad', MAGIC, MAGIC+struct.pack('<BII', 3, 4, 4), MAGIC+struct.pack('<BII', 0, BLOCK+1, 1), MAGIC+struct.pack('<BII', 255, 1, 0)])
def test_malformed(tmp_path, data):
    p = tmp_path/'bad'
    p.write_bytes(data)
    with pytest.raises(FormatError):
        verify(p)

def test_trailing(tmp_path):
    p, a = tmp_path/'p', tmp_path/'a'
    p.write_bytes(b'foo')
    convert(p, a)
    with a.open('ab') as f:
        f.write(b'X')
    with pytest.raises(FormatError):
        verify(a)

def test_output_limit(tmp_path):
    p, a = tmp_path/'p', tmp_path/'a'
    p.write_bytes(b'abcd'*1000)
    convert(p, a)
    with pytest.raises(FormatError):
        verify(a, max_output_bytes=3999)
    assert verify(a, max_output_bytes=4000)['output_bytes'] == 4000

def test_no_overwrite(tmp_path):
    p, a = tmp_path/'p', tmp_path/'a'
    p.write_bytes(b'abc')
    a.write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        convert(p, a)
    assert a.read_bytes() == b'keep'

def test_v4_reference_format_compatible(tmp_path):
    # Independently construct the original V4 raw-fallback frame.
    import hashlib
    raw = b'original-v4'
    a = tmp_path/'legacy'
    a.write_bytes(MAGIC+struct.pack('<BII', 0, len(raw), len(raw))+raw+struct.pack('<BII',255,0,0)+struct.pack('<Q',len(raw))+hashlib.sha256(raw).digest())
    out = tmp_path/'out'
    convert(a,out,decode=True)
    assert out.read_bytes() == raw

def test_cli(tmp_path):
    src, archive, restored = [tmp_path/x for x in ('src','a','out')]
    src.write_bytes(b'cli test'*1000)
    for args in [('pack',src,archive),('verify',archive),('unpack',archive,restored),('compare',src,restored)]:
        r = subprocess.run([sys.executable,'-m','modelpack_v4',*map(str,args)],capture_output=True,text=True)
        assert r.returncode == 0, r.stderr
    restored.write_bytes(b'wrong')
    r = subprocess.run([sys.executable,'-m','modelpack_v4','compare',str(src),str(restored)],capture_output=True)
    assert r.returncode == 1

def test_cli_invalid_archive_exit_code(tmp_path):
    a=tmp_path/'bad';a.write_bytes(b'not an archive')
    result=subprocess.run([sys.executable,'-m','modelpack_v4','verify',str(a)],capture_output=True,text=True)
    assert result.returncode == 2
    assert 'modelpack:' in result.stderr
    assert 'Traceback' not in result.stderr

def test_benchmark_tool(tmp_path):
    from pathlib import Path
    import json
    tool=Path(__file__).resolve().parents[1]/'tools'/'benchmark_checkpoint.py'
    src=tmp_path/'source';src.write_bytes(b'benchmark'*1000)
    report=tmp_path/'report.json'
    result=subprocess.run([sys.executable,str(tool),'--file',str(src),'--workdir',str(tmp_path),'--output',str(report)],capture_output=True,text=True)
    assert result.returncode == 0,result.stderr
    assert json.loads(report.read_text())['independent_byte_for_byte_equal']
    assert src.exists()
    assert not list(tmp_path.glob('modelpack-benchmark-*'))
