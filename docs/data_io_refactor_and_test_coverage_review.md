# data_io.py refactor + test-coverage review

## Verdict
A **complete refactor is not currently justified**. The module has cohesive responsibilities (directory resolution, filename validation, safe JSON loading, and cache boundary) and has dedicated tests for each security-sensitive branch.

## Why this does not look abandoned
- Path override validation (`_resolve_override_data_dir`) is explicitly exercised for blank, NUL, traversal, non-absolute, missing-dir, existing-file, and OSError paths.
- Filename hardening (`_validate_data_filename`) is exercised for unknown names, unicode normalization collisions, and long unicode names.
- Directory-containment checks (`_contained_child_path`) are exercised for escape and non-directory-base behavior.
- Error-message behavior in `load_data` is exercised for both configured and default directory contexts.
- `get_data` and cache APIs are covered with mutation-isolation checks.

## Potential redundancy (small, not alarming)
There appears to be overlap in fallback-path assertions in `tests/story_brief/linting/test_coverage_gaps.py`:
- `test_data_file_repo_relative_when_resources_are_unavailable`
- `test_data_file_falls_back_to_repo_relative_when_resources_unavailable`

These both force `ModuleNotFoundError` from `importlib.resources.files(...)` and assert repo-relative fallback path shape. Consolidating them into a single parametrized test preserves behavior confidence while reducing maintenance overhead.

## Recommendation for 100/100 goals
- Keep security and error-path tests in `tests/story_brief/data_io/` as they are high-value.
- If pruning, consolidate duplicated fallback tests into a single parametrized test.
- Prefer adding narrow tests for any currently uncovered branches instead of broad refactor churn.

In short: **targeted cleanup + branch-specific tests**, not a full rewrite.
