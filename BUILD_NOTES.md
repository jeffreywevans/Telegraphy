# Build Notes — 0.6.0

- Prepared from the supplied 0.5.3 source archive on 2026-10-19.
- Runtime used for validation: Python 3.14.4 on Linux.
- This is a prepared source snapshot; no remote repository, release, or package registry was modified.

## Data layout

The fourteen output fields use thirteen independent field-data files. Both
character fields share `characters.json`. `config.json` contains only metadata
and output ordering; `writing_preamble.json` contains the writing instructions.
The physical file-layout schema version is 2. Canon content and generation
behavior are preserved.

## Verification

- Full suite: 455 tests passed.
- Coverage workflow: passed; 98.34% combined coverage with branch measurement enabled.
- New layout module: 100% measured coverage.
- Ruff lint: passed across the repository.
- Ruff format check: passed for all seven added or modified Python files. Existing formatting differences in untouched files remain outside this refactor.
- Strict mypy: passed for all 34 source files.
- Dataset lint: passed, with no warnings.
- Strict dataset validation and seeded CLI generation: passed.
- Canon payload comparison: identical after accounting for the physical layout schema version.
- Seed/date output comparison: 400 original-versus-refactored Markdown outputs matched byte for byte.
- Source and wheel builds: passed using `python -m build --no-isolation`.
- Package resource check: all fifteen required JSON files are included; old aggregate files are absent.
- Installed-wheel CLI smoke: passed outside the source tree.
- SBOM regenerated for version 0.6.0.

## Scope and limits

This snapshot implements the data-file separation. Existing output-write race
and forced-overwrite reliability concerns, GUI field-reset behavior, weather
weighting behavior, and release-workflow hardening were not part of this
refactor. Native desktop GUI interaction was not tested on Windows or macOS.

The SBOM generator still describes the declared minimum runtime dependency
version rather than independently inventorying a resolved release environment.

## Reproduce the checks

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy telegraphy
pytest -q
python -m telegraphy.scripts.run_coverage_workflow
python -m telegraphy.story_brief --lint-dataset
python -m telegraphy.story_brief --validate-strict --seed 42 --date 2000-01-01 --print-only
python -m telegraphy.scripts.generate_sbom
python -m build
```

See the README for the complete field-file mapping and custom-dataset migration.
