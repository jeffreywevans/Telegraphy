# Contributing to Telegraphy

Thanks for contributing to Telegraphy.

## Development setup

1. Use Python 3.12 or newer.
2. Create and activate a virtual environment.
3. Install the project with development dependencies:

```bash
pip install -e ".[dev]"
```

## Local checks

Before opening a pull request, run:

```bash
ruff check .
ruff format --check .
mypy telegraphy
pytest
```

If you change generation logic, add or update tests in `tests/` to cover both success and failure cases.

## Dataset and behavior changes

- Keep JSON data changes focused and intentional.
- If changing `telegraphy/story_brief/data/*`, run `story-brief --lint-dataset` and at least one generation command to validate behavior.
- Preserve deterministic behavior for seeded generation.

## Pull requests

Please include:

- A clear summary of what changed and why.
- Notes on any schema/data migration impacts.
- The exact local commands you ran and their outcomes.

Keep PRs small when possible.

## Reporting issues and security

- For bugs/feature requests, open a GitHub issue with reproduction steps.
- For security issues, follow `SECURITY.md` and do not disclose publicly first.
