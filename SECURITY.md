# Security and data safety

This is an alpha research utility, not a security-audited archival standard. Keep backups and independently verify important data before deleting originals.

- Integrity uses SHA-256 and original lengths. This detects corruption, not malicious modification by someone who can regenerate hashes. There is no encryption, authentication or signature.
- Decoder framing and decompression output are bounded per block. Use `--max-output-bytes` to bound total output. Without it, archives can legitimately decode to very large files and use disk/time.
- Model code and pickle are never executed. Only bytes and JSON are processed.
- Bundle paths are validated; symlinks and non-regular source entries are rejected. Concurrent mutation of source files or the destination filesystem is not supported. Do not run on directories controlled by a hostile concurrent process.
- Single-file outputs use temporary files, fsync and hard-link publication. Existing destinations are refused. The filesystem must support hard links. Folder results are staged and renamed; this is not a transaction across power failures, nor a defense against adversarial directory races.
- SHA-256 may appear in logs. File paths and names appear in manifests. Sensitive model files remain sensitive after compression.
- Folder metadata (permissions, ownership, timestamps and extended attributes) is not preserved. Restoration should occur in a trusted private directory.
- Errors remove temporary outputs on normal exception handling. Abrupt termination or power loss can leave hidden `.modelpack-*` temporary files; inspect and clean these manually after confirming no process is active.

Report issues privately to your repository maintainer. No maintainer contact is invented in this template. Add a private reporting channel before accepting security reports on a public release.
