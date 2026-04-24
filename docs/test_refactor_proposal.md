# Test Suite Refactor Proposal (Duplication Reduction)

## Goals

1. Reduce duplicated dataset setup logic across tests.
2. Keep behavior and coverage unchanged.
3. Make future test additions easier and less error-prone.

## Current duplication hotspots

### 1) CLI tests repeatedly clone and mutate dataset files
In `tests/story_brief/test_cli_subprocess_behavior.py`, multiple tests repeat:
- create temp data dir
- copy `titles.json`, `entities.json`, `prompts.json`, `config.json`, `partner_distributions.json`
- mutate one file
- execute CLI with `TELEGRAPHY_DATA_DIR`

### 2) Ad-hoc mutation blocks inline in tests
Several tests contain long inline JSON mutation logic that obscures test intent.

### 3) Similar subprocess assertion patterns
A number of CLI tests assert the same shape:
- non-zero exit code
- expected message in stdout/stderr
- no traceback

## Proposed refactor

### Phase 1 (low risk, high ROI)

#### A. Add shared dataset helpers in `tests/conftest.py`
Add fixtures/helpers:

- `@pytest.fixture def source_story_data_dir() -> Path`
  - returns canonical data directory (`telegraphy/story_brief/data`)

- `def clone_story_dataset(destination: Path) -> Path`
  - copies the five JSON files to `destination`
  - returns destination path

- `def patch_json(path: Path, mutator: Callable[[dict[str, Any]], None]) -> None`
  - load JSON, mutate in callback, write back

- `@pytest.fixture def cli_dataset_factory(tmp_path) -> Callable[[str], Path]`
  - creates named dataset folder under temp path
  - clones baseline dataset into it

This concentrates file I/O and JSON copy/patch patterns into one place.

#### B. Extract CLI command wrapper fixtures
In `tests/story_brief/test_cli_subprocess_behavior.py`:

- keep `run_cli` but add optional `data_dir` argument
- if `data_dir` is provided, inject `TELEGRAPHY_DATA_DIR` automatically

This removes repetitive env override construction.

### Phase 2 (medium risk, readability win)

#### C. Parametrize repetitive CLI error-shape tests
Add a table-driven test for simple invalid-input cases.

Example table dimensions:
- `args`
- `expected_substring`
- `expected_returncode_nonzero`

Shared assertions:
- expected message present
- `Traceback` absent

This shortens multiple similar negative tests while preserving intent.

#### D. Split very long scenario tests into arrange helpers
For larger scenario tests (e.g., lint-vs-validate precedence), move setup to named helper functions:
- `make_single_character_single_setting_dataset(data_dir: Path)`
- `remove_prompt_key(data_dir: Path, key: str)`

These helpers reveal intent and reduce per-test noise.

### Phase 3 (optional)

#### E. Add `tests/story_brief/helpers.py`
If `conftest.py` grows too large, move pure helper functions there and keep fixtures in `conftest.py`.

## Non-goals

- No production code behavior changes.
- No changes to test semantics/coverage targets.
- No migration to another framework/plugin.

## Safety checks

After each phase:

1. Run full tests with `PYTHONPATH=. pytest -q`.
2. Run durations with `PYTHONPATH=. pytest -q --durations=15` to ensure no regressions.
3. Confirm integration marker behavior remains unchanged.

## Suggested implementation order

1. Add helper utilities/fixtures.
2. Migrate 2–3 CLI tests as proof of pattern.
3. Migrate remaining duplicated CLI setup.
4. Introduce targeted parameterization for repetitive error-shape tests.
5. Re-run and compare durations.

## Expected benefits

- Smaller, more declarative tests.
- Lower chance of inconsistent fixture/data setup.
- Faster onboarding for contributors editing tests.
- Easier expansion of CLI negative-path coverage.
