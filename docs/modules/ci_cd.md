# CI/CD

GitHub Actions pipelines for automated testing and PyPI publishing.

## Files

- `.github/workflows/ci.yml`: test pipeline (push + PR)
- `.github/workflows/publish.yml`: PyPI publish pipeline (GitHub release)

## Test pipeline (`ci.yml`)

Runs on every push to `main` and on pull requests.

- **Matrix**: Python 3.11, 3.12, 3.13 on `ubuntu-latest`
- **Steps**: checkout → setup Python → install dependencies → run `pytest`
- Current test count: 3500+

## Publish pipeline (`publish.yml`)

Runs when a GitHub release is published.

- Builds the package with `python -m build` (hatchling backend)
- Publishes to PyPI via `pypa/gh-action-pypi-publish`
- Requires `PYPI_API_TOKEN` secret in the `pypi` environment

### Creating a release

```bash
# Tag the release
git tag v1.0.1
git push origin v1.0.1

# Create the release on GitHub (triggers publish)
gh release create v1.0.1 --title "v1.0.1" --notes "Release notes here"
```

## PyPI package

- Package name: `sygen`
- Install: `pip install sygen` or `pipx install sygen`
- Build system: hatchling
- Entry point: `sygen` CLI command
