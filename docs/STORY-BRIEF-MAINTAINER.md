# Story Brief Maintainer Guide

This document consolidates maintainer-facing guidance for the story brief system: data organization, regression coverage, and dataset versioning.

## 1) Data strategy

### Recommendation

Use a **small set of domain-based JSON files** (not one giant file, and not one file per key):

- `telegraphy/story_brief/data/titles.json`
- `telegraphy/story_brief/data/entities.json` (characters, settings, availability windows)
- `telegraphy/story_brief/data/prompts.json` (conflicts, pressures, endings, style)
- `telegraphy/story_brief/data/config.json` (ordered keys, weights, date range, word-count targets)
- `telegraphy/story_brief/data/partner_distributions.json` (date-aware weighted `sexual_partner` pools; `[]` indicates celibacy, while omitted era data—a date window not covered by any era—indicates absent data)

### Why this split

Compared with one giant JSON file, domain-based files reduce merge conflicts and keep diffs easier to review.
Compared with one-file-per-key, domain-based files avoid sprawl while keeping related content together.

### Future-proofing

1. Keep `ordered_keys` and key metadata in `config.json`.
2. Validate required keys/types/ranges with loader checks.
3. Maintain defaults/fallback behavior so adding a key does not break older datasets.
4. Keep `schema_version` in `config.json` and validate at load time.

### Practical migration checklist

1. Move constants into `telegraphy/story_brief/data/*.json`.
2. Keep loader validation centralized.
3. Preserve compatibility aliases during transitional refactors.
4. Keep smoke tests for loading + seeded generation.
5. Remove legacy in-code tables only after parity verification.

## 2) Regression suite strategy

### Current status

- Regression tests are implemented under `tests/story_brief/` with `pytest`.
- Coverage includes schema/loader behavior, availability boundaries, markdown output, deterministic generation, and CLI behavior.
- Next maintainer focus should remain strict dataset-health behavior (date coverage and generation preconditions), not only schema shape.

### Required gate

Treat `pytest -q tests/story_brief` as a required check for any change to:

- `telegraphy/story_brief/generate_story_brief.py`
- `telegraphy/story_brief/data/*.json`
- story-brief test modules

### Test module boundaries

Keep files separated by behavior area and consolidate only shared fixtures/helpers:

- `test_schema_validation.py`
- `test_weighted_choice.py`
- `test_generation_determinism.py`
- `test_markdown_output.py`
- `test_cli_behavior.py`

Use shared utilities in `tests/story_brief/conftest.py` and/or a helper module as needed.

### High-ROI minimum checks

If adding only a few tests during a change window, prioritize:

1. baseline schema validates,
2. duplicate `ordered_keys` fails,
3. all-zero weighted-choice fails,
4. same seed gives deterministic output,
5. `--print-only` does not write files.

### Suggested ongoing rollout

1. Keep `pytest -q` green locally and in CI.
2. Add/maintain strict data-health checks that ensure each selectable date has:
   - at least one setting,
   - at least two distinct characters.
3. Add diagnostics for dead windows/unreachable availability records.
4. Keep CI coverage across supported Python versions.
5. Add lightweight representative seed/date regression checks.

### Definition of done for story-brief changes

- `pytest -q tests/story_brief` passes.
- CI passes for the change.
- Any bug fix includes a regression test.

## 3) Dataset versioning policy

### Short answer

- Per-file version numbers are usually unnecessary.
- Structured top-level version tracking is recommended.

### Project policy

Store and validate versions in `telegraphy/story_brief/data/config.json`:

1. `schema_version` for structure compatibility.
2. `dataset_version` for content snapshot/version identity.

Use semantic or date-style dataset versions (for example, `1.3.0` or `2026.04.10`) and bump `dataset_version` only for material data/config changes.

### Why not per-file versions

Git already provides per-file history. Per-file counters add bookkeeping and can drift out of sync.
Use Git history (and optional release tags) for file-level evolution.

### Optional enhancement

Maintain a concise data changelog such as `telegraphy/story_brief/data/CHANGELOG.md` for human-readable release notes.

## 4) Maintainer workflow summary

When editing story brief behavior or data:

1. Update data/config files using the domain-based split.
2. Keep schema + dataset version fields correct in `config.json`.
3. Run `pytest -q tests/story_brief` before commit.
4. Add/adjust regression tests for any bug fix or behavior change.
5. If strict health checks fail, fix data gaps before merge.
