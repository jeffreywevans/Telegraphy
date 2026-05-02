# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.0] - 2026-05-02

Released Telegraphy 0.4.0 with a new desktop GUI experience and the supporting quality/reliability updates completed alongside it.

### Added
- Added a new `telegraphy-gui` desktop command that launches a tkinter tablet-style interface for story-brief generation.
- Added the `telegraphy.gui` package and `TelegraphyTablet` app shell, including threaded generation and clipboard-copy workflow.
- Added substantial unit coverage for the GUI module, including rendering, worker queue, subprocess execution, decode fallback, and clipboard behaviors.

### Changed
- Updated tox configuration for Tox 4 compatibility and cleaner environment labels used in CI and local QA runs.
- Improved GUI internals for maintainability (style/font constant deduplication, typing fixes for tkinter polygon creation, and clearer test call structure).

### Fixed
- Hardened GUI subprocess output decoding to gracefully handle invalid preferred encoding names and non-UTF-8 byte streams.
- Fixed style and lint issues in GUI-focused tests (line-length/readability cleanups and Ruff E731 remediation).

## [0.3.3] - 2026-05-02

Released Telegraphy 0.3.3 to document and ship the substantive security, reliability, and CI workflow improvements delivered since 0.3.2.

### Added
- Added a dedicated CodeQL analysis workflow to continuously scan Python and GitHub Actions code paths.

### Changed
- Hardened `data_io` path validation to mitigate uncontrolled path-expression risks while preserving correct symlink and absolute-path behavior.
- Improved `story_brief` CLI entrypoint testability and coverage via focused `__main__` / `_run` refinements.
- Simplified CodeQL workflow behavior and tuned triggers/concurrency to reduce runtime churn while maintaining analysis coverage.
- Updated CI actions to improve reproducibility and performance by pinning `actions/setup-python` to immutable references and enabling pip caching.
- Removed an obsolete Node.js environment override from the CodeQL workflow to reduce configuration noise.

### Fixed
- Resolved failures loading `titles.json` for absolute data-directory inputs by correcting story-brief data path validation logic.


## [0.3.2] - 2026-05-02

Released Telegraphy 0.3.2 to formalize project metadata and documentation consistency.

### Changed
- Bumped package metadata and project-facing release references from 0.3.1 to 0.3.2 to keep tooling, docs, and release notes in sync.


## [0.3.1] - 2026-05-02

Released Telegraphy 0.3.1 to capture recent normalization logic hardening and documentation-link cleanup.

### Changed
- Simplified scene-tag weight normalization to use a single-pass, deterministic adjustment path, including explicit handling for under-one and over-one totals.
- Covered previously untested normalization branches with targeted tests to strengthen line and condition coverage guarantees.
- Updated README badge and documentation links for cross-renderer compatibility and correct license-link targets.
- Bumped package metadata and project-facing release references from 0.3.0 to 0.3.1.

## [0.3.0] - 2026-05-01

Released Telegraphy 0.3.0 as the new project baseline after recent generator, validation, and documentation updates.

### Changed
- Updated package metadata and top-level documentation to consistently report version 0.3.0.
- Refreshed release-status text in the README to align with the 0.3.0 declaration.

## [0.2.2] - 2026-04-30

### Changed
- Consolidated positive-weight validation messaging through a shared helper while keeping existing validation behavior and test expectations intact.
- Refined generation internals with explicit RNG typing and cleaner partner normalization logic for more predictable maintenance.
- Updated project documentation to reflect current behavior after legacy-path cleanup.

### Removed
- Support for the legacy `COMMUTED_STORY_BRIEF_DATA_DIR` environment variable override.
- Legacy partner index fallback paths that were retained only for backward compatibility.

## [0.2.1] - 2026-04-29

### Added
- Added `GREETINGS.md` as a lightweight project-facing documentation artifact.

### Changed
- Rewrote and streamlined the README to improve project onboarding clarity and reduce duplicated content.
- Removed duplicate SonarQube badge and tightened top-level project documentation consistency.
- Standardized changelog structure to align with Keep a Changelog conventions and explicit release-date formatting.

## [0.2.0] - 2026-04-27

This release marks the transition from a single-purpose generator script into a structured Python package.

### Added
- Stricter validation for configuration, datasets, availability windows, partner distributions, and output structure.
- Dataset linting and coverage checks.
- Expanded tests across the core generation workflow.
- Integration with quality tooling: Ruff, mypy, pytest, coverage, and SonarQube.

### Changed
- Refactored story brief generation into focused modules (CLI, data loading, validation, linting, etc.).
- Hardened output-path handling and filename generation.

[Unreleased]: https://github.com/jeffreywevans/Telegraphy/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/jeffreywevans/Telegraphy/compare/v0.3.3...v0.4.0
[0.3.3]: https://github.com/jeffreywevans/Telegraphy/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/jeffreywevans/Telegraphy/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/jeffreywevans/Telegraphy/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/jeffreywevans/Telegraphy/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/jeffreywevans/Telegraphy/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/jeffreywevans/Telegraphy/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/jeffreywevans/Telegraphy/releases/tag/v0.2.0
