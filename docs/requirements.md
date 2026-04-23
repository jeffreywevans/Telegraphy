# Runtime Dependencies

This project defines runtime dependencies in `pyproject.toml` under `[project.dependencies]`.

For environments that install with requirements files (for example, some CI systems),
`requirements.txt` references the local project so dependency resolution comes from
`pyproject.toml` as the single source of truth.

## Install

```bash
pip install -r requirements.txt
```

For editable local development installs, use:

```bash
pip install -e .
```
