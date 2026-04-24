# Development Dependencies

This project defines development dependencies in `pyproject.toml` under `[project.optional-dependencies].dev`.
Installing the `dev` extra also installs all runtime dependencies from `[project.dependencies]`.

## Install

```bash
pip install -e ".[dev]"
```
