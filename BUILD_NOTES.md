# Build Notes — 0.5.1

- Version: `0.5.1`
- Build date (UTC): `2026-05-11`
- Commit hash at build-check start: `3b46dfd960b7998c72764b10b29d31f10002d2f1`
- Python version: `Python 3.14.4`

## Quality and validation summary

- Dataset lint: pass (`python -m telegraphy.story_brief --lint-dataset`)
- Strict validation smoke: pass (`python -m telegraphy.story_brief --validate-strict --seed 42 --date 2000-01-01 --print-only`)
- Test suite: pass (`391 passed`)
- Coverage: blocked in this environment (`pytest-cov` not available locally)
- Ruff lint: pass
- Ruff format check: repository currently not format-clean (`python -m ruff format --check .` reports files needing reformat)
- mypy: pass
- Package build: blocked in this environment (`python -m build` unavailable; `build` could not be installed due package index/network restrictions)
- GUI smoke: not validated (headless/non-interactive shell)

## Artifact notes

- `dist/` artifacts were not produced in this environment because `python -m build` could not run.
- SBOM was regenerated for `0.5.1` via `python -m telegraphy.scripts.generate_sbom`.
