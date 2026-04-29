## Telegraphy 0.2.0

This release marks the transition from a single-purpose generator script into a structured Python package.

Highlights:

- Refactored story brief generation into focused modules for CLI handling, data loading, validation, linting, generation, rendering, and filename safety.
- Added stricter validation for configuration, datasets, availability windows, partner distributions, and output structure.
- Improved dataset linting and coverage checks.
- Hardened output-path handling and filename generation.
- Added or expanded tests across the core generation workflow.
- Integrated quality tooling with Ruff, mypy, pytest, coverage, and SonarQube.
- Confirmed SonarQube quality gate passes with 100% reported coverage and 0.0% duplication.
- Quality Gate: Passed
- Security: A, 0 open issues
- Reliability: A, 0 open issues
- Maintainability: A, 0 open issues
- Coverage: 100%
- Duplications: 0.0%
