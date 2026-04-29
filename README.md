# Telegraphy

[![Build](https://github.com/jeffreywevans/Telegraphy/actions/workflows/build.yml/badge.svg)](https://github.com/jeffreywevans/Telegraphy/actions/workflows/build.yml)
[![SonarQube Cloud](https://sonarcloud.io/images/project_badges/sonarcloud-light.svg)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_Telegraphy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Telegraphy is a Python package and command-line tool for generating structured story briefs from a versioned, data-driven canon dataset.

It currently exposes one console command: `story-brief`.

Telegraphy does not write prose. It generates the feedstock: YAML front matter, scenario constraints, style guidance, date-aware character and setting selections, optional sexual-content metadata, and a Markdown drafting scaffold. The result is a repeatable prompt artifact that can be copied into a writing workflow or saved as a Markdown seed file.

## Contents

- [What is this?](#what-is-this)
- [Install](#install)
- [Quickstart](#quickstart)
- [CLI examples](#cli-examples)
- [Data override](#data-override)
- [Validation and linting](#validation-and-linting)
- [How the generator works](#how-the-generator-works)
- [Output files and safety](#output-files-and-safety)
- [Development](#development)
- [Release notes and status](#release-notes-and-status)
- [Maintainer docs](#maintainer-docs)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## What is this?

Telegraphy is the focused story-brief generator for the Commuted fiction universe.

At a practical level, it is:

- a Python package named `telegraphy`;
- a CLI named `story-brief`;
- a packaged JSON dataset under `telegraphy/story_brief/data/`;
- validation and linting tools for keeping that dataset usable;
- tests and CI for preserving deterministic generation behavior.

A generated brief includes:

- title;
- protagonist and secondary character;
- date;
- setting;
- weather;
- central conflict;
- inciting pressure;
- ending type;
- style guidance;
- sexual content level;
- sexual partner metadata when applicable;
- sexual scene tags when applicable;
- word-count target;
- a Markdown story-draft heading.

The generator is date-aware. Character availability, setting availability, and partner distributions are constrained by configured date ranges. That is the point of the tool: it lets the fiction machine throw sparks without setting the continuity barn on fire.

## Install

Telegraphy requires Python 3.12 or newer.

For normal local use from a clone:

```bash
git clone https://github.com/jeffreywevans/Telegraphy.git
cd Telegraphy
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

The development extra installs the tools used by the repository:

- `pytest`
- `pytest-cov`
- `ruff`
- `mypy`
- `types-PyYAML`

You can verify that the CLI is available with:

```bash
story-brief --help
```

You can also run it as a module:

```bash
python -m telegraphy.story_brief --help
```

## Quickstart

Print a generated brief to the terminal:

```bash
story-brief --print-only
```

Generate a reproducible brief for a specific date:

```bash
story-brief --seed 42 --date 2000-01-01 --print-only
```

Write a brief to the default output directory:

```bash
story-brief
```

By default, Telegraphy writes Markdown files under:

```text
output/story-seeds/
```

Use an explicit filename:

```bash
story-brief --filename brief.md
```

Overwrite an existing file only when you mean it:

```bash
story-brief --filename brief.md --force
```

Run dataset linting without generating a brief:

```bash
story-brief --lint-dataset
```

Example clean report:

```text
Dataset lint: no blocking coverage gaps found.
Dataset lint: no warnings.
```

Run strict validation before generation:

```bash
story-brief --validate-strict --print-only
```

## CLI examples

### CLI reference

| Option | Purpose |
| --- | --- |
| `--print-only` | Print Markdown to the terminal and skip file writing. |
| `--seed <int>` | Use deterministic randomness for reproducible briefs. |
| `--date YYYY-MM-DD` | Force the story date for scenario testing. |
| `-o, --output-dir <path>` | Choose the output directory. Defaults to `output/story-seeds`. |
| `--filename <name.md>` | Choose the output filename. |
| `--force` | Allow overwriting an existing output file. |
| `--validate-strict` | Validate date-range generation preconditions before generating. |
| `--lint-dataset` | Run dataset lint diagnostics and exit. |
| `-h, --help` | Show command help. |

### Print only

Use this when you want to copy the generated prompt directly from the terminal.

```bash
story-brief --print-only
```

### Reproducible generation

Seeded output is intended for debugging, tests, reviews, and repeatable creative workflows.

```bash
story-brief --seed 8675309 --print-only
```

Lock both the random seed and the story date:

```bash
story-brief --seed 42 --date 2000-01-01 --print-only
```

That command produces Markdown shaped like this:

```markdown
---
title: It's Only Profound if You're Not Stoned
protagonist: Cremeans
secondary_character: Bill Davenport
time_period: '2000-01-01'
setting: Lenovo Center - Raleigh, NC, USA
weather: lousy
sexual_content_level: none
sexual_partner: null
sexual_scene_tags: []
word_count_target: 6000
---

# It's Only Profound if You're Not Stoned

## Story Draft

*Write a story of approximately 6000 words using the YAML brief above.*
```

### Write to a specific directory

```bash
story-brief --output-dir output/story-seeds
```

The output directory is resolved under the current working directory. Telegraphy intentionally refuses output paths that escape that tree.

### Pick the filename

```bash
story-brief --filename "first-pass.md"
```

Filenames are sanitized and checked for cross-platform safety. Telegraphy rejects path separators, dot-segments, leading or trailing spaces, Windows device names, and other file-system traps.

### Validate before generating

```bash
story-brief --validate-strict --seed 42 --date 2000-01-01 --print-only
```

Strict validation checks generation preconditions across the configured date range before creating output.

### Lint the dataset

```bash
story-brief --lint-dataset
```

Linting emits a concise report and exits without generating a brief.

A clean dataset reports:

```text
Dataset lint: no blocking coverage gaps found.
Dataset lint: no warnings.
```

## Data override

Telegraphy ships with its canonical dataset inside the package:

```text
telegraphy/story_brief/data/
```

The packaged dataset contains five required JSON files:

```text
config.json
entities.json
partner_distributions.json
prompts.json
titles.json
```

For experiments, alternate timelines, review fixtures, or private datasets, point Telegraphy at another directory:

```bash
TELEGRAPHY_DATA_DIR=/absolute/path/to/story-data story-brief --print-only
```

Override directories must:

- be absolute paths after optional current-user `~` expansion;
- already exist;
- contain all five required JSON files;
- avoid parent-directory traversal;
- avoid `~user` expansion;
- avoid NUL bytes.

Only the known dataset filenames are loaded. Telegraphy refuses unknown data-file requests and checks that resolved files remain inside the configured data directory.

### Data-file responsibilities

`titles.json` contains title templates. Supported title tokens are:

```text
@protagonist
@setting
@time_period
```

`entities.json` contains date-bounded character and setting availability.

`prompts.json` contains narrative prompt pools such as conflicts, pressures, endings, style guidance, and weather.

`config.json` contains schema metadata, dataset version, date range, output key order, word-count targets, sexual-content options and weights, tag groups, and the writing preamble.

`partner_distributions.json` contains date-aware weighted partner pools by protagonist. An empty partner list means intentional celibacy for that era. A missing era means absent data and should be treated as a dataset problem.

## Validation and linting

Telegraphy has two related safety nets: validation and linting.

Validation checks whether the dataset can be loaded and normalized. It rejects malformed schema, missing keys, unsupported title tokens, overlapping availability windows for the same entity, invalid dates, broken weight tables, bad ordered keys, invalid partner distributions, and other hard failures.

Strict validation goes farther:

```bash
story-brief --validate-strict --print-only
```

It checks date-range generation preconditions at availability checkpoints, including:

- at least two distinct available characters for each checked date;
- at least one available setting for each checked date.

Linting looks for dataset coverage gaps and fragile areas:

```bash
story-brief --lint-dataset
```

Lint exits with code `0` when no blocking issues are found and code `1` when the report contains errors. Strict validation also exits nonzero on hard failures.

Use linting before committing dataset edits. Use strict validation before trusting a new or heavily edited dataset.

A good minimum review loop for data changes is:

```bash
story-brief --lint-dataset
story-brief --validate-strict --seed 42 --date 2000-01-01 --print-only
pytest -q tests/story_brief
```

## How the generator works

Telegraphy follows a small, deliberate pipeline:

```text
JSON dataset
    -> data_io.load_data()
    -> validation.validate_story_data()
    -> normalized StoryData
    -> generation.pick_story_fields()
    -> rendering.to_markdown()
    -> terminal output or safe Markdown write
```

The main modules are:

| Module | Responsibility |
| --- | --- |
| `telegraphy.story_brief.cli` | Argument parsing and CLI orchestration. |
| `telegraphy.story_brief.data_io` | Dataset discovery, package resources, environment overrides, JSON loading, cache management. |
| `telegraphy.story_brief.validation` | Schema validation, semantic validation, strict date-range preconditions. |
| `telegraphy.story_brief.linting` | Dataset coverage diagnostics and human-facing lint reports. |
| `telegraphy.story_brief.generation` | Date selection, availability filtering, weighted choices, field selection. |
| `telegraphy.story_brief.partner_models` | Partner-distribution parsing and date-aware weighted partner pools. |
| `telegraphy.story_brief.rendering` | YAML front matter and Markdown output. |
| `telegraphy.story_brief.filenames` | Slugging, filename sanitization, output-path safety, write protection. |
| `telegraphy.story_brief.generate_story_brief` | Compatibility facade over the refactored implementation. |

Seeded generation is designed to be stable. When you supply `--seed`, Telegraphy uses a deterministic random source and sorted selection pools so that the same inputs produce the same brief.

When no seed is supplied, Telegraphy uses `secrets.SystemRandom`.

## Output files and safety

Telegraphy is conservative about writes.

By default it writes into:

```text
output/story-seeds/
```

It refuses to overwrite existing files unless `--force` is provided.

It confines output to the current working directory tree. This is intentional: generated files should not be able to wander out of the project and bite the furniture.

It also performs filename checks and sanitization, including:

- cross-platform unsafe characters;
- path separators;
- dot-segments;
- leading or trailing spaces;
- Windows reserved device names;
- UTF-8 byte-length limits;
- optional `O_NOFOLLOW` protection on platforms that provide it.

## Development

Create and activate a virtual environment, then install the development extra:

```bash
python -m pip install -e ".[dev]"
```

Run the local quality checks:

```bash
ruff check .
ruff format .
mypy telegraphy
pytest
```

Install tox if it is not already available:

```bash
python -m pip install tox
```

Run the full tox workflow:

```bash
tox -e py312
```

Run fast tests only:

```bash
tox -e py312-fast
```

Run slow or integration tests:

```bash
tox -e py312-slow
```

The repository uses:

- Ruff for linting and formatting;
- mypy in strict mode for the package;
- pytest for the test suite;
- pytest-cov and coverage settings for branch coverage;
- tox for repeatable local test environments;
- GitHub Actions for CI;
- SonarQube Cloud for quality reporting.

### Project metadata

The package metadata lives in `pyproject.toml`.

Current package facts:

| Field | Value |
| --- | --- |
| Package | `telegraphy` |
| Current version | `0.2.1` |
| Python | `>=3.12` |
| Runtime dependency | `PyYAML>=6.0.3` |
| Console script | `story-brief = telegraphy.story_brief.cli:main` |
| License | MIT |

### Contribution expectations

Before opening a pull request, run the relevant checks and include the commands you ran in the PR notes.

For code changes, include tests that cover success and failure behavior.

For dataset changes, keep diffs focused and run:

```bash
story-brief --lint-dataset
story-brief --validate-strict --print-only
```

For generation changes, preserve deterministic seeded behavior unless the PR explicitly and intentionally changes it.

## Release notes and status

Current status: `0.2.1`.

This release focuses on documentation refreshes and maintainer-focused clarity while preserving the package architecture introduced in 0.2.0.

Highlights:

- streamlined README onboarding and project status narrative;
- improved maintainer-document index and documentation cross-linking;
- added a lightweight project-facing `GREETINGS.md` document;
- tightened top-level documentation consistency.

See [CHANGELOG.md](CHANGELOG.md) for release notes.

### Stability note

Telegraphy is usable as a local CLI and developer tool. The command-line interface and data schema are still young enough that maintainers should treat changes carefully and document migration impact in PRs.

No published package distribution is assumed by this README. Install from the repository unless and until a release workflow says otherwise.

## Maintainer docs

Start here:

- [CONTRIBUTING.md](CONTRIBUTING.md): development setup, local checks, pull-request expectations.
- [CHANGELOG.md](CHANGELOG.md): release notes.
- [GREETINGS.md](GREETINGS.md): lightweight project-facing documentation artifact.
- [SECURITY.md](SECURITY.md): vulnerability reporting.
- [docs/STORY-BRIEF-MAINTAINER.md](docs/STORY-BRIEF-MAINTAINER.md): data strategy, regression coverage, dataset versioning, and maintenance rules.
- [docs/Story Brief Generator Evaluation.md](docs/Story%20Brief%20Generator%20Evaluation.md): current evaluation and constructive criticism.
- [docs/requirements.md](docs/requirements.md): runtime dependency policy.
- [docs/requirements-dev.md](docs/requirements-dev.md): development dependency policy.
- [docs/dependabot_setup.md](docs/dependabot_setup.md): dependency update automation.
- [docs/review_2026-04-27.md](docs/review_2026-04-27.md): code review notes and known follow-up items.
- [docs/test_refactor_proposal.md](docs/test_refactor_proposal.md): test-suite refactor proposal.

## Troubleshooting

### `story-brief` is not found

Install the package in the current environment:

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

Then retry:

```bash
story-brief --help
```

### The selected date is rejected

The date must be inside the configured dataset range. Use ISO format:

```bash
story-brief --date 2000-01-01 --print-only
```

### The data override is rejected

Check that the override is absolute and contains the required JSON files:

```bash
ls /absolute/path/to/story-data
```

Expected files:

```text
config.json
entities.json
partner_distributions.json
prompts.json
titles.json
```

### An output file already exists

Telegraphy will not overwrite files by accident. Use another filename or pass `--force`:

```bash
story-brief --filename brief.md --force
```

### Output path is rejected

Keep `--output-dir` inside the current working directory tree. Absolute paths are allowed only when they resolve inside that tree.

### Linting passes but generation still fails

Run strict validation:

```bash
story-brief --validate-strict --print-only
```

Linting reports dataset health. Strict validation checks generation preconditions across key date boundaries.

## License

Telegraphy is released under the [MIT License](LICENSE).
