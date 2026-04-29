# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - YYYY-MM-DD

This release marks the transition from a single-purpose generator script into a structured Python package.

### Added
- Stricter validation for configuration, datasets, availability windows, partner distributions, and output structure.
- Dataset linting and coverage checks.
- Expanded tests across the core generation workflow.
- Integration with quality tooling: Ruff, mypy, pytest, coverage, and SonarQube.

### Changed
- Refactored story brief generation into focused modules (CLI, data loading, validation, linting, etc.).
- Hardened output-path handling and filename generation.
