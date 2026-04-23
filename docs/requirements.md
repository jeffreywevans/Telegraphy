# Runtime Dependencies

`pyproject.toml` is the source of truth for runtime dependencies via
`[project.dependencies]`.

`requirements.txt` is a compatibility file for environments and tooling that
require a requirements file (for example, some CI systems and security
scanners). It is a manually maintained mirror of `[project.dependencies]` in
`pyproject.toml`, so update both files together to avoid dependency drift.

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
