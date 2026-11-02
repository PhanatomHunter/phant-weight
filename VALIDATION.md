# Release validation — ModelPack V4 0.1.0

- Local runtime: Python 3.13.16 / NumPy 2.3.5.
- Editable source installation: 46 tests passed.
- Built wheel installed in a separate virtual environment (shared dependency packages): 46 tests passed; import path confirmed the wheel installation.
- Wheel and source distribution built successfully; both passed `twine check`.
- Actual CLI pack → verify → unpack → compare ran on complete TinyLlama 1.1B checkpoint.
- Input: 2,200,119,864 bytes. Archive: 1,618,158,289 bytes. Reduction: 26.451357697482248%.
- Independent byte-for-byte comparison: equal.
- Pack / verify / unpack elapsed: 55.35 / 14.72 / 16.03 seconds in this workspace.
- Whole-folder support tested on synthetic folders containing config, tokenizer, nested weights and empty directories. It was not benchmarked on an entire downloaded Hugging Face model folder.
- 8B compression: not benchmarked; prior estimates remain estimates.
- GitHub CI matrix configured for Python 3.10–3.13, not executed on GitHub here.
- GitHub/PyPI publication: not performed.
- Model weights and temporary multi-GB archives are excluded from this release.

The full-model test preceded only additional bundle-schema checks and added test/benchmark utilities; the file codec used in that run is the same file codec shipped in the release.
