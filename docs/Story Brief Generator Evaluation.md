# Evaluation: Story Brief Generator (Constructive Criticism Refresh)

## Executive Summary

The generator is in a **healthy, production-usable state** with strong validation and a meaningful regression suite.  
Quality has **improved** over recent iterations (especially around schema checks, deterministic behavior, and test coverage), but there are still practical opportunities to improve **efficiency**, **security posture**, **maintainability**, and **author experience**.

**Current quality score (subjective): 8.4 / 10.**

---

## What Improved Recently (Progress)

1. **Validation now catches config/date overlap issues at load time**
   - `validate_story_data` now verifies that `config.date_start/date_end` overlaps both character and setting availability windows.
   - This shifts failures left (load time) instead of surfacing late during generation.

2. **Availability parsing logic is de-duplicated**
   - A shared helper now tupleizes availability rows for both characters and settings.
   - Less duplicate code = lower maintenance burden.

3. **Utility simplification**
   - Stable dedupe now uses Python-native `dict.fromkeys`, reducing custom logic.

4. **Test suite depth increased**
   - Added direct boundary tests for `available_characters` and `available_settings`.
   - Updated tests to rely on `get_data()` and behavioral assertions (instead of legacy aliases / brittle implementation assumptions).

5. **Data cleanup aligned with configured timeline**
   - Early dead pre-range setting windows were normalized to align with configured story start dates.

---

## Current Strengths

- **Data-driven architecture** keeps content and logic separated cleanly.
- **Fast failure modes** produce actionable messages for malformed input.
- **Deterministic generation support** (`--seed`, `--date`) is solid for repro/debug.
- **Cross-platform file safety** through filename sanitization.
- **Reasonable runtime safety defaults** (`yaml.safe_dump`, explicit overwrite behavior).
- **Regression suite coverage is pragmatic** (schema, determinism, weighted choice, markdown, CLI, availability filters).

---

## Constructive Criticism (What Still Needs Work)

### 1) Quality / Correctness

- **Dataset-level reachability is still shallowly validated.**
  - Current overlap checks ensure “at least one row intersects config range,” but do not ensure:
    - every date in range has at least one setting,
    - every date in range has at least two distinct characters (generator invariant),
    - title token placeholders always resolve to non-empty strings under all paths.
  - **Recommendation:** add an optional strict validator mode (`--validate-strict`) that sweeps the date range and checks generation preconditions.

### 2) Efficiency

- **Repeated full-date sweeps could become expensive as data scales.**
  - The current filtering approach is fine for current dataset size, but linearly scans lists each generation.
  - **Recommendation:** keep current behavior (simple and readable), but add optional indexing if data volume grows (e.g., year buckets or interval index built once per load).

### 3) Security / Robustness

- **Environment override path is trusted implicitly.**
  - This is expected for local tooling, but operationally it can load untrusted JSON from arbitrary directories.
  - **Recommendation:** document trust expectations explicitly and consider a “read-only trusted mode” in CI or production wrappers.

### 4) Ease of Use

- **Validation guidance could be more discoverable.**
  - Users likely discover malformed data only when running generator/tests.
  - **Recommendation:** add a first-class CLI command (or mode), e.g.:
    - `python commuted_calligraphy/story_brief/generate_story_brief.py --validate-data`
    - output concise pass/fail summary and top actionable fixes.

### 5) Documentation Quality

- **Docs are good but fragmented.**
  - Useful information is spread across multiple files and planning docs.
  - **Recommendation:** add a concise “Story Brief Maintenance Guide” with:
    - edit workflow for JSON files,
    - validation/test commands,
    - common failure messages + fixes,
    - definition of done for data PRs.

### 6) Missing Features / “Wistful Wishes”

- Add **date-range coverage report**:
  - Which dates have no settings?
  - Which dates have <2 distinct characters?
  - Which entities are unreachable?
- Add **dataset linting command** that flags dead windows, overlapping risks, and typo-prone near-duplicates.
- Add **snapshot test fixtures** for representative generated output at selected seeds/dates.
- Add **CI matrix** on multiple Python versions for compatibility confidence.

---

## Suggested 30/60/90 Day Hardening Plan

### 0–30 days (High ROI)
- Add `--validate-data` CLI mode.
- Add tests for “at least two distinct characters per selectable date” in strict mode.
- Add a short maintainer playbook doc.

### 31–60 days
- Add dataset health report (coverage + dead-window diagnostics).
- Add CI Python matrix (`3.11`, `3.12`, latest `3.x`).

### 61–90 days
- Optional performance indexing if entity counts grow.
- Add richer snapshot/regression corpus for output quality drift detection.

---

## Bottom Line

This project has moved from “promising and somewhat brittle” to **well-engineered and dependable** for day-to-day use.  
The next quality jump comes from **tooling around data stewardship**: strict validation mode, coverage diagnostics, and maintainer-facing documentation.
