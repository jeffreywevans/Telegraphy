# Development Dependencies

This project defines development dependencies in `pyproject.toml` under `[project.optional-dependencies].dev`.

For requirements-file-based workflows, development dependencies are listed in
`requirements-dev.txt` and include runtime dependencies.

## Install

```bash
pip install -r requirements-dev.txt
```

or install editable package + extras:

```bash
pip install -e ".[dev]"
```
