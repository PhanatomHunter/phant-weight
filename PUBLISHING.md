# GitHub publication checklist

No repository has been created or pushed by this session. No PyPI release exists.

## Review

1. Choose a GitHub repository name; check package-name availability if planning PyPI publication.
2. Review license/copyright, README, security contact and benchmark evidence.
3. Never commit model weights without license review. Model files, archives and integration working directories are excluded by `.gitignore`.
4. Run tests and build; verify a wheel install in a fresh environment.
5. Preserve benchmark claims as checkpoint-specific results, not guaranteed 26% savings.

## Publish using GitHub CLI

Run these commands yourself from the repository directory after signing in:

```sh
gh auth login
git init
git add .
git commit -m "Initial ModelPack V4 lossless CLI release"
# Replace YOUR_REPOSITORY_NAME with your chosen new repository name.
gh repo create YOUR_REPOSITORY_NAME --public --source=. --remote=origin --push
```

For a private repository, replace `--public` with `--private`.

## Build and release

```sh
python -m pip install -e '.[test]' build twine
python -m pytest -q
python -m build
python -m twine check dist/*
git tag v0.1.0
git push origin v0.1.0
gh release create v0.1.0 dist/* --title "ModelPack V4 0.1.0" --notes-file CHANGELOG.md
```

`dist/` is a temporary local build directory and is not committed. The deliverable also includes copies under `releases/` for convenience. Publishing to GitHub does not publish to PyPI. Do not upload to PyPI until name ownership, metadata and release policy are reviewed. Use trusted publishing rather than embedding API tokens in this repository.
