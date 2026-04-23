# Runtime Dependencies

`pyproject.toml` is the single source of truth for runtime dependencies via
`[project.dependencies]`.

`requirements.txt` exists for environments and tooling that require a
requirements file (for example, some CI systems and security scanners). Keep it
in sync with `pyproject.toml` and include `.` so `pip install -r requirements.txt`
installs this package and its runtime dependencies.

## Install

Preferred:

```bash
pip install .
```

Compatibility path for workflows that require requirements files:

```bash
pip install -r requirements.txt
```

For editable local development installs, use:

```bash
pip install -e .
```
