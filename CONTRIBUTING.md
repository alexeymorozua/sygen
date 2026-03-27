# Contributing to Sygen

Thanks for your interest in contributing!

## Before You Start

- Read the [CLA](CLA.md). By opening a PR you agree to its terms.
- Check [existing issues](https://github.com/alexeymorozua/sygen/issues) before creating new ones.

## Development Setup

```bash
git clone https://github.com/alexeymorozua/sygen.git
cd sygen
pip install -e ".[dev]"
pytest
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Keep changes focused — one feature or fix per PR.
3. Add tests for new functionality.
4. Ensure `pytest` passes locally.
5. Include `I have read the CLA and agree to its terms.` in your PR description.

## Code Style

- Python 3.11+
- Follow existing code conventions in the project.
- No unnecessary comments or docstrings — code should be self-explanatory.

## Reporting Issues

Use [GitHub Issues](https://github.com/alexeymorozua/sygen/issues). Include:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS

## License

Contributions are licensed under the project's [BSL 1.1](LICENSE) license.
