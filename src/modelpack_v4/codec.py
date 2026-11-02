"""LCV1: reversible XOR byte-plane coding with SHA-256 verification."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import zlib
import numpy as np

MAGIC = b'LCV1\x00'
BLOCK = 4 * 1024 * 1024

class FormatError(ValueError):
    """Malformed, truncated, or integrity-invalid archive."""

def transform(raw: bytes) -> bytes:
    a = np.frombuffer(raw + b'\0' * (-len(raw) % 4), dtype=np.uint8).reshape(-1, 4)
    delta = a.copy()
    if len(a) > 1:
        delta[1:] = a[1:] ^ a[:-1]
    return delta.T.copy().tobytes()

def inverse(data: bytes, length: int) -> bytes:
    if len(data) != ((length + 3) // 4) * 4:
        raise FormatError('Invalid transformed size')
    a = np.frombuffer(data, dtype=np.uint8).reshape(4, -1).T.copy()
    return np.bitwise_xor.accumulate(a, axis=0).tobytes()[:length]

def _read(stream, n):
    data = stream.read(n)
    if len(data) != n:
        raise FormatError('Truncated archive')
    return data

def _encode(source, target):
    digest = hashlib.sha256()
    size = blocks = 0
    target.write(MAGIC)
    while raw := source.read(BLOCK):
        digest.update(raw)
        size += len(raw)
        blocks += 1
        compressed = zlib.compress(transform(raw), 1)
        mode = int(len(compressed) < len(raw))
        payload = compressed if mode else raw
        target.write(struct.pack('<BII', mode, len(raw), len(payload)))
        target.write(payload)
    target.write(struct.pack('<BII', 255, 0, 0))
    target.write(struct.pack('<Q', size))
    target.write(digest.digest())
    return {'input_bytes': size, 'blocks': blocks, 'sha256': digest.hexdigest()}

def _decode(source, target=None, max_output_bytes=None):
    if _read(source, len(MAGIC)) != MAGIC:
        raise FormatError('Invalid magic/version')
    digest = hashlib.sha256()
    size = blocks = 0
    while True:
        mode, n, k = struct.unpack('<BII', _read(source, 9))
        if mode == 255:
            if n or k:
                raise FormatError('Invalid end marker')
            break
        if mode not in (0, 1) or not 0 < n <= BLOCK or not 0 < k <= BLOCK:
            raise FormatError('Invalid block framing')
        if max_output_bytes is not None and size + n > max_output_bytes:
            raise FormatError('Output size limit exceeded')
        payload = _read(source, k)
        if mode == 0:
            if n != k:
                raise FormatError('Raw block size mismatch')
            raw = payload
        else:
            decoder = zlib.decompressobj()
            try:
                data = decoder.decompress(payload, ((n + 3) // 4) * 4 + 1)
            except zlib.error as exc:
                raise FormatError('Invalid zlib payload') from exc
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise FormatError('Invalid compressed stream')
            raw = inverse(data, n)
        digest.update(raw)
        size += len(raw)
        blocks += 1
        if target is not None:
            target.write(raw)
    footer = _read(source, 40)
    if struct.unpack('<Q', footer[:8])[0] != size or footer[8:] != digest.digest():
        raise FormatError('Length or SHA-256 verification failed')
    if source.read(1):
        raise FormatError('Trailing archive data')
    return {'output_bytes': size, 'blocks': blocks, 'sha256': digest.hexdigest()}

def convert(source, destination, decode=False, max_output_bytes=None):
    """Publish only completed outputs; never overwrite an existing destination."""
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file():
        raise ValueError('Source must be a regular, non-symlink file')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(str(destination))
    if not destination.parent.is_dir():
        raise ValueError('Destination parent directory must exist')
    fd, temp = tempfile.mkstemp(prefix='.modelpack-', dir=destination.parent)
    try:
        with source.open('rb') as src, os.fdopen(fd, 'wb') as out:
            result = _decode(src, out, max_output_bytes) if decode else _encode(src, out)
            out.flush()
            os.fsync(out.fileno())
        # Hard-link publication is atomic and refuses an existing destination.
        os.link(temp, destination)
        result['archive_bytes'] = source.stat().st_size if decode else destination.stat().st_size
        if not decode:
            result['size_reduction_percent'] = (100 * (1 - result['archive_bytes'] / result['input_bytes'])) if result['input_bytes'] else None
        return result
    finally:
        Path(temp).unlink(missing_ok=True)

def verify(source, max_output_bytes=None):
    with Path(source).open('rb') as src:
        return _decode(src, max_output_bytes=max_output_bytes)

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(BLOCK):
            h.update(block)
    return h.hexdigest()
