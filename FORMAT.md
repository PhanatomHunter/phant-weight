# LCV1 file format

All integers are unsigned little-endian. The file starts with five bytes `4c 43 56 31 00` (`LCV1\0`).

Each data frame:

| Field | Bytes | Meaning |
|---|---:|---|
| mode | 1 | 0 = raw, 1 = XOR/byte-plane/zlib |
| original_length | 4 | 1 through 4,194,304 |
| payload_length | 4 | 1 through 4,194,304 |
| payload | payload_length | Data |

For raw frames, original and payload lengths must match. For compressed frames, decoding must produce `ceil(original_length/4)*4` transformed bytes. Padding is removed after inverse transformation.

The terminal frame is mode 255, original length 0, payload length 0. It is followed by an 8-byte total original length and 32-byte SHA-256 digest over all original bytes. Trailing data is forbidden. Zero data frames represents an empty file.

Transform for a block:

```text
padded bytes → N×4 uint8 groups A
D[0] = A[0]
D[i] = A[i] XOR A[i-1] for i > 0
transformed bytes = row-major serialization of D transpose
payload = zlib.compress(transformed bytes, level=1)
```

Inverse: reshape transformed bytes to 4×N, transpose, cumulatively XOR along N, flatten and truncate to original length. Each block resets its predictor. Compressors may select raw fallback when zlib does not save bytes.

## Folder bundle v1

A directory with `manifest.json`:

```json
{
  "format": "modelpack-v4-folder-1",
  "files": [{"path":"config.json","archive":"000000.lcv","bytes":123,"sha256":"64 lowercase hex characters"}],
  "directories": []
}
```

`path` is a relative POSIX path. Absolute paths, `..`, `.`, empty segments, colons, backslashes and NULs are rejected. Archive names are six digits followed by `.lcv`. Duplicate paths/archive identifiers are rejected. Entries must be real files, not symlinks. File content hashes and lengths are checked against both the LCV1 footer and the manifest. Extra files in a bundle directory are ignored and never restored. Platform-specific filesystem restrictions can cause safe failures during restoration.
