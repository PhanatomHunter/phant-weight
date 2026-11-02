#!/usr/bin/env python3
"""End-to-end benchmark; downloads only with explicit --download-reference."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import urllib.request
import numpy as np

REPO = 'TinyLlama/TinyLlama-1.1B-Chat-v1.0'
REVISION = 'fe8a4ea1ffedaf415f4da2f062534de366a451e6'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--file', type=Path)
    group.add_argument('--download-reference', action='store_true')
    p.add_argument('--workdir', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path, default=Path('benchmark.json'))
    a = p.parse_args()
    if a.output.exists():
        p.error('Output already exists')
    report = {'environment': {'python':sys.version, 'platform':platform.platform(), 'numpy':np.__version__}, 'steps':{}}
    with tempfile.TemporaryDirectory(prefix='modelpack-benchmark-', dir=a.workdir) as directory:
        root = Path(directory)
        if a.download_reference:
            source = root/'reference.safetensors'
            url = f'https://huggingface.co/{REPO}/resolve/{REVISION}/model.safetensors'
            print('Downloading pinned reference (~2.2 GB)', file=sys.stderr)
            with urllib.request.urlopen(url, timeout=120) as r, source.open('wb') as out:
                length = r.headers.get('Content-Length')
                count = 0
                while block := r.read(4*1024*1024):
                    out.write(block)
                    count += len(block)
            if length and count != int(length):
                raise ValueError('Incomplete download')
            report['checkpoint'] = REPO
            report['revision'] = REVISION
        else:
            source = a.file.resolve()
            report['source_file'] = str(source)
        archive, restored = root/'model.lcv', root/'restored'
        commands = [('pack', source, archive), ('verify', archive), ('unpack', archive, restored), ('compare', source, restored)]
        for command in commands:
            start = time.monotonic()
            result = subprocess.run([sys.executable, '-m', 'modelpack_v4', *map(str, command)], capture_output=True, text=True, check=True)
            report['steps'][command[0]] = {'seconds':time.monotonic()-start, 'result':json.loads(result.stdout)}
        with source.open('rb') as original, restored.open('rb') as decoded:
            while True:
                x, y = original.read(4*1024*1024), decoded.read(4*1024*1024)
                if x != y:
                    raise ValueError('Independent byte comparison failed')
                if not x:
                    break
        report['independent_byte_for_byte_equal'] = True
    # Exclusive creation prevents clobbering an existing report.
    with a.output.open('x', encoding='utf-8') as out:
        json.dump(report, out, indent=2)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
