import argparse
import json
from pathlib import Path
import sys
from . import __version__
from .codec import convert, verify, sha256_file
from .bundle import pack_folder, unpack_folder, verify_folder

def main(argv=None):
    parser = argparse.ArgumentParser(description='Lossless model file/folder compression. Ratios vary; 26.45% is one reference benchmark, not a guarantee.')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('pack', 'unpack'):
        p = sub.add_parser(name)
        p.add_argument('source', type=Path)
        p.add_argument('destination', type=Path)
        if name == 'unpack':
            p.add_argument('--max-output-bytes', type=int)
    p = sub.add_parser('verify', help='Decode and check integrity without writing restored files')
    p.add_argument('source', type=Path)
    p.add_argument('--max-output-bytes', type=int)
    p = sub.add_parser('compare', help='Compare SHA-256 and size of two regular files')
    p.add_argument('original', type=Path)
    p.add_argument('restored', type=Path)
    a = parser.parse_args(argv)
    try:
        limit = getattr(a, 'max_output_bytes', None)
        if limit is not None and limit < 0:
            raise ValueError('Output limit must be nonnegative')
        if a.command == 'pack':
            result = pack_folder(a.source, a.destination) if a.source.is_dir() else convert(a.source, a.destination)
        elif a.command == 'unpack':
            result = unpack_folder(a.source, a.destination, limit) if a.source.is_dir() else convert(a.source, a.destination, decode=True, max_output_bytes=limit)
        elif a.command == 'verify':
            result = verify_folder(a.source, limit) if a.source.is_dir() else verify(a.source, limit)
            result['verified'] = True
        else:
            match = a.original.stat().st_size == a.restored.stat().st_size and sha256_file(a.original) == sha256_file(a.restored)
            result = {'equal_size_and_sha256': match}
            print(json.dumps(result, indent=2))
            return 0 if match else 1
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print('modelpack: ' + str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
