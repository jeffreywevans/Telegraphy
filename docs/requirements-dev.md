# Development Dependencies

This project defines development dependencies in `pyproject.toml` under `[project.optional-dependencies].dev`.
Note that installing the package with the `dev` extra also installs all runtime dependencies defined in `[project.dependencies]`.

## Install

```bash
pip install -e ".[dev]"
```
