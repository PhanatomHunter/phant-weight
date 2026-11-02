# ModelPack V4

**Lossless model-checkpoint and model-folder compression.** NumPy + Python standard library; no GPU, PyTorch or Transformers required.

> **Measured reference, not a promise:** TinyLlama 1.1B's checkpoint compressed from **2,200,119,864 → 1,618,158,289 bytes (26.45% smaller)**. Decoding recovered every original byte. Other checkpoints—particularly already-quantized files—may compress differently or expand slightly.

ModelPack reduces **disk storage and transfer size**. It does not reduce the parameter count, normal inference RAM/VRAM, or prove inference speedups. It is not an extraction of intelligence or model geometry. Decode before ordinary inference.

## Install

Python 3.10+:

```sh
# Run from the extracted repository directory:
python -m pip install .
modelpack --version
modelpack --help
```

Or install the included wheel with `python -m pip install releases/modelpack_v4-0.1.0-py3-none-any.whl`. NumPy must be available from PyPI or an offline wheel. The package is **not published on PyPI**; do not assume `pip install modelpack-v4` will fetch this project.

Module invocation also works: `python -m modelpack_v4 --help`.

## Quick start: one checkpoint

```sh
modelpack pack /path/model.safetensors /path/model.lcv
modelpack verify /path/model.lcv
modelpack unpack /path/model.lcv /path/restored.safetensors
modelpack compare /path/model.safetensors /path/restored.safetensors
```

`verify` streams through the complete archive, reconstructs blocks in memory and checks SHA-256 **without writing restored weights**. `compare` checks both file size and SHA-256. For an independent exact byte comparison on Linux/macOS:

```sh
cmp /path/model.safetensors /path/restored.safetensors
```

No overwrite flag is provided. All output paths must be new, with an existing parent directory. Files are written to temporary files and published only after success.

## Pack a complete local model folder

```sh
modelpack pack /path/local-model /path/local-model.bundle
modelpack verify /path/local-model.bundle
modelpack unpack /path/local-model.bundle /path/restored-model
```

This includes **every regular file** in the source folder: weight shards, index, `config.json`, tokenizer assets, generation configuration, and any other files. It preserves relative paths and empty directories, but **not permissions, timestamps, ownership, symlinks, hard-link identity or extended attributes**. The model's license and any custom code remain your responsibility.

The bundle is a **directory**, not one `.lcv` file. It contains `manifest.json` plus numbered `.lcv` entries. Keep the whole directory intact when transferring it. For one transferable file, an uncompressed tar of the bundle is appropriate; already-compressed payloads usually gain little from another compression pass.

### Hugging Face cache warning

Cached model snapshots commonly use symlinks, which this tool deliberately rejects. First materialize a self-contained local model folder (or copy with symlink dereferencing in a trusted environment). Only pack files you have permission to redistribute. This CLI does not download models, run remote model code, or upload data.

## Limit decoded size

```sh
modelpack verify /path/model.lcv --max-output-bytes 20000000000
modelpack unpack /path/model.lcv /path/restored.safetensors --max-output-bytes 20000000000
```

Limits apply to **total decoded bytes** for folder bundles. They are optional; use them with untrusted archives. Integrity hashes detect accidental corruption, **not authenticity**: an attacker who can replace the archive can also replace its hash.

## How it works

For each 4 MiB block:

1. Pad to a multiple of four bytes (original length is retained).
2. Regard bytes as four interleaved lanes, independently of the file's float dtype.
3. XOR adjacent groups: `delta[i] = group[i] XOR group[i-1]`; retain the first group unchanged.
4. Separate the four byte lanes into contiguous planes.
5. Compress with zlib, level 1.
6. If this is not smaller, store the original block instead.
7. Store framing, original length and a whole-file SHA-256 footer.

Decoding reverses the byte-plane arrangement and uses cumulative XOR to recover original bytes. This is exact for arbitrary file contents: FP32, BF16, FP16, quantized tensors, tokenizer files and JSON. No arithmetic is performed on floating-point weights. It uses standard reversible transforms; no novelty claim is made.

See [FORMAT.md](FORMAT.md) for byte layout and [SECURITY.md](SECURITY.md) for safety limitations.

## Results and limits

The original V4 reference run used TinyLlama/TinyLlama-1.1B-Chat-v1.0 at revision `fe8a4ea1ffedaf415f4da2f062534de366a451e6`. Reference evidence is in `benchmarks/tinyllama-v4-reference.json`. The release CLI is independently re-tested against the same full checkpoint; its results are in `benchmarks/release-cli-tinyllama.json` when validation succeeds.

| Reference result | Measurement |
|---|---:|
| Input | 2,200,119,864 bytes |
| Output | 1,618,158,289 bytes |
| Reduction | 26.45% |
| Recovered file | Byte-for-byte identical |
| Original V4 encode / decode | 54.74 s / 16.25 s |

Times are environment-specific, not universal throughput guarantees. No 8B model was benchmarked. An FP16 8B checkpoint of approximately 16 GB would be approximately **11.77 GB if the same ratio held**; that is an estimate, not a result.

### Disk and memory planning

For a file of size `S` and archive size `C`:

- Pack while retaining the source: approximately `S + C` disk space, plus filesystem overhead.
- Unpack while retaining the archive: approximately `C + S`.
- Retain original, archive and restored file for comparison: approximately `2S + C`.

The file codec uses bounded 4 MiB blocks, not the entire model in RAM. NumPy intermediates and zlib buffers add working memory; no measured peak-RSS claim is made. Folder manifests hold metadata in memory (up to 100,000 entries / 10 MiB manifest). Folder compression is sequential. Tiny files and incompressible inputs can expand due to framing. The source must not be modified during packing.

## Reproduce the end-to-end benchmark

```sh
# Your own local checkpoint (no network):
python tools/benchmark_checkpoint.py --file /path/model.safetensors --workdir /large/scratch --output my-benchmark.json

# Explicitly download and benchmark the pinned TinyLlama reference:
python tools/benchmark_checkpoint.py --download-reference --workdir /large/scratch --output tinyllama-benchmark.json
```

The benchmark runs the installed CLI's pack, verify, unpack and compare commands, then independently compares every byte. It records runtime versions, sizes and timings. The downloaded source (if requested), encoded archive and restored copy are temporary and removed after the benchmark; your supplied local source is retained. Budget approximately **6.1 GB** scratch for the TinyLlama reference while all three files coexist, plus safety margin. An 8B test needs substantially more disk. The benchmark script is separate from the CLI and uses the network only with the explicit download flag.

## Exit codes

- `0`: success / matching comparison.
- `1`: `compare` found a mismatch.
- `2`: argument, format, integrity, filesystem, or supported validation error.

Commands print JSON results to stdout and errors to stderr. They do not load or execute model code.

## Development and tests

```sh
python -m pip install -e '.[test]'
python -m pytest -q
python -m pip install build
python -m build
```

Tests cover exact roundtrips, raw/compressed/empty/multi-block files, legacy framing, corruption, truncation, invalid framing, output limits, no-overwrite behavior, CLI commands, complete folder restoration, empty directories, manifest mismatches, path traversal and symlink rejection. See `TEST_RESULTS.txt` for the local run. GitHub Actions is configured for Python 3.10–3.13 on Ubuntu; that matrix is **configured, not claimed already executed**.

## Publish to GitHub

See [PUBLISHING.md](PUBLISHING.md). This folder is prepared for publication; it has **not** been pushed to GitHub or published to PyPI. Review files and pick your repository name before publishing. The included project name is not a verified reserved PyPI name.

## License

MIT for this code. Model weights retain their original licenses. See [LICENSE](LICENSE).
