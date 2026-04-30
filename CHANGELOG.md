# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
