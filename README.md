# Telegraphy

[![Build](https://github.com/jeffreywevans/Telegraphy/actions/workflows/build.yml/badge.svg)](https://github.com/jeffreywevans/Telegraphy/actions/workflows/build.yml)
[![SonarQube Cloud](https://sonarcloud.io/images/project_badges/sonarcloud-light.svg)](https://sonarcloud.io/summary/new_code?id=jeffreywevans_Telegraphy)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/jeffreywevans/Telegraphy/license)

Telegraphy is a Python package and command-line tool for generating structured story briefs from a versioned, data-driven canon dataset.

It exposes two user-facing entry points:

- `story-brief` (CLI)
- `telegraphy-gui` (desktop GUI)

Telegraphy does not write prose. It generates the feedstock: YAML front matter, scenario constraints, style guidance, date-aware character and setting selections, optional sexual-content metadata, and a Markdown drafting scaffold. The result is a repeatable prompt artifact that can be copied into a writing workflow or saved as a Markdown seed file.

## Contents

- [What is this?](#what-is-this)
- [Install](#install)
- [Quickstart](#quickstart)
- [GUI quickstart](#gui-quickstart)
- [Using the GUI](#using-the-gui)
- [CLI examples](#cli-examples)
- [Data override](#data-override)
- [Validation and linting](#validation-and-linting)
- [Software bill of materials (SBOM)](#software-bill-of-materials-sbom)
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

You can verify that the GUI launcher is available with:

```bash
telegraphy-gui --help
```

If you prefer module execution:

```bash
python -m telegraphy.gui.tablet_app
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

## GUI quickstart

Start the GUI:

```bash
telegraphy-gui
```

Press **GENERATE!** to run the same generator used by the CLI (`python -m telegraphy.story_brief --print-only`).

Use the **Seed** and **Date** fields to forward `--seed` and `--date` to the CLI for reproducible GUI runs.

Press **COPY!** to copy the most recent successful brief to your clipboard.

## Using the GUI

The 0.4.1 GUI is intentionally focused: it is a tablet-shaped desktop wrapper around the existing `story-brief` engine.

### What happens when you click GENERATE!

1. The GUI disables both buttons to avoid overlapping runs.
2. It starts a background worker thread so the window stays responsive.
3. The worker executes: `python -m telegraphy.story_brief --print-only`.
4. On success, the generated Markdown is displayed in the output pane and cached as the latest output.
5. On failure, stderr/stdout diagnostics are shown in the output pane and copy is disabled for empty output.

### GUI layout

- **Header**: app title and subtitle.
- **Toolbar**:
  - **GENERATE!**: run generation.
  - **COPY!**: copy last successful output.
  - **Status**: live state (Ready, Generating, Generated, Failed, Copied).
- **Output pane**: read-only text area with scrollbar showing Markdown output or errors.

### GUI behavior details

- Uses your local Python interpreter (`sys.executable`) and inherited environment (`os.environ`) by design; this is convenient for virtualenv workflows, but also means local environment changes can alter behavior.
- GUI CLI worker has a default 30-second timeout (override with `telegraphy-gui --timeout <seconds>`).
- `telegraphy-gui --help` is supported without launching a window.
- In headless environments, startup fails cleanly with a user-facing error instead of a tkinter traceback.
- Decodes CLI output using your preferred locale encoding, then falls back to UTF-8 with replacement for robust display.
- Never writes files directly; it always requests `--print-only` output from the CLI.
- Clipboard copy only works after a successful generation.

### GUI troubleshooting

- If `telegraphy-gui` fails to launch, ensure `tkinter` is available in your Python build.
- If generation fails, read the output pane: the GUI surfaces the underlying CLI error message.
- For reproducible debugging, run the CLI directly with explicit flags (for example `story-brief --seed 42 --date 2000-01-01 --print-only`).

## CLI examples

### CLI reference

| Option | Purpose |
| --- | --- |
| `--print-only` | Print Markdown to the terminal and skip file writing. |
| `--seed <int>` | Use deterministic randomness for reproducible briefs; omit it to use OS-backed entropy. |
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

`TELEGRAPHY_DATA_DIR` is the only supported environment variable override. The legacy `COMMUTED_STORY_BRIEF_DATA_DIR` override was removed and is intentionally ignored.

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

## Software bill of materials (SBOM)

Telegraphy ships a CycloneDX SBOM at:

```text
sbom.cdx.json
```

You can use this file for dependency transparency, supply-chain review, and security tooling that ingests CycloneDX JSON.

To regenerate the SBOM after dependency or version changes:

```bash
python -m telegraphy.scripts.generate_sbom
```

The repository includes `sbom.cdx.json` in source distributions via `MANIFEST.in`.

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

When no seed is supplied, Telegraphy uses `secrets.SystemRandom`, so unseeded runs draw OS-backed entropy instead of using a deterministic PRNG.

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

### GitHub Actions pinning policy

This repository has a strong preference for pinning GitHub Actions to immutable commit SHAs.
Pinned SHAs reduce supply-chain risk from mutable tags and make CI behavior easier to reproduce.

Where practical, workflow `uses:` references should follow this style:

```yaml
- uses: owner/action@<40-character-commit-sha> # v1.2.3
```

In a small number of cases, we intentionally keep a trusted GitHub-maintained action (for example,
from the `actions/` or `github/` organizations) on a major tag (for example `@v4`) instead of a SHA.
When we do this, the trade-off is explicit: the repository chooses to trust GitHub's managed release
process for that core toolchain, and to accept the small reduction in strict immutability in exchange
for simpler maintenance.

### Project metadata

The package metadata lives in `pyproject.toml`.

Current package facts:

| Field | Value |
| --- | --- |
| Package | `telegraphy` |
| Current version | `0.4.1` |
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

Current status: `0.4.1`.

This release establishes the 0.4.1 line, reflecting the GUI launch plus follow-up build consistency updates across metadata, docs, and SBOM artifacts.

Highlights:

- launched the desktop `telegraphy-gui` command with a tablet-style interface backed by the existing CLI engine;
- strengthened GUI reliability with threaded generation flow, robust subprocess decode fallback, and expanded GUI unit coverage;
- kept package metadata, changelog references, README status text, and SBOM artifact versioning aligned for build consistency.

See [CHANGELOG.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/CHANGELOG.md) for release notes.

### Stability note

Telegraphy is usable as a local CLI and developer tool. The command-line interface and data schema are still young enough that maintainers should treat changes carefully and document migration impact in PRs.

No published package distribution is assumed by this README. Install from the repository unless and until a release workflow says otherwise.

## Maintainer docs

Start here:

- [CONTRIBUTING.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/CONTRIBUTING.md): development setup, local checks, pull-request expectations.
- [CHANGELOG.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/CHANGELOG.md): release notes.
- [GREETINGS.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/GREETINGS.md): lightweight project-facing documentation artifact.
- [SECURITY.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/SECURITY.md): vulnerability reporting.
- [docs/STORY-BRIEF-MAINTAINER.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/docs/STORY-BRIEF-MAINTAINER.md): data strategy, regression coverage, dataset versioning, and maintenance rules.
- [docs/Story Brief Generator Evaluation.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/docs/Story%20Brief%20Generator%20Evaluation.md): current evaluation and constructive criticism.
- [docs/requirements.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/docs/requirements.md): runtime dependency policy.
- [docs/requirements-dev.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/docs/requirements-dev.md): development dependency policy.
- [docs/dependabot_setup.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/docs/dependabot_setup.md): dependency update automation.
- [docs/review_2026-04-27.md](https://github.com/jeffreywevans/Telegraphy/blob/HEAD/docs/review_2026-04-27.md): code review notes and known follow-up items.

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

Telegraphy is released under the [MIT License](https://github.com/jeffreywevans/Telegraphy/license).
