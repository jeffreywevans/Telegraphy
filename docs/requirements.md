# Runtime Dependencies

This project defines runtime dependencies in `pyproject.toml` under `[project.dependencies]`.

For environments that install with requirements files (for example, some CI systems),
`requirements.txt` lists direct runtime dependencies for environments that require
a requirements file.

## Install

```bash
pip install .
```

For editable local development installs, use:

```bash
pip install -e .
```
