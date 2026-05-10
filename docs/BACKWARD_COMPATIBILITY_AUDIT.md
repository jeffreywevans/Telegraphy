# Backward Compatibility Audit

Date: 2026-05-10

## Files containing explicit backward-compatibility code

1. `telegraphy/story_brief/generate_story_brief.py`
   - Re-exports legacy constants (filenames and metadata) as compatibility aliases.
   - Provides `get_data()`, `load_story_data()`, `pick_story_fields()`, and `to_markdown()` as backward-compatible wrappers.
   - Compatibility intent is explicit in comments/docstrings.

2. `telegraphy/story_brief/validation.py`
   - Entire module is a backward-compatible facade that re-exports validation APIs after internal module split.
   - Keeps existing import surface stable while implementation is decomposed.

3. `telegraphy/story_brief/data_io.py`
   - Contains resource-resolution fallback logic (`resolve_data_dir()` -> `_fallback_data_dir()`) to preserve operability when package resources are unavailable.
   - This is operational compatibility rather than API compatibility, but still legacy-tolerant behavior.

## Documentation references to compatibility policy (non-runtime code)

1. `README.md`
   - Documents removal of legacy env var behavior and legacy tag-schema keys.
   - Clarifies that runtime migration is intentionally not performed.

2. `CHANGELOG.md`
   - Records prior removals of legacy compatibility paths and variables.

## Commentary

- The codebase appears to be intentionally moving toward **strict canonical schemas** and **limited, explicit compatibility shims**.
- Existing compatibility layers are small and concentrated in facade modules, which is a maintainable pattern.
- If maintainers want to continue reducing compatibility debt, the likely next candidates are:
  - alias-only wrapper functions/constants in `generate_story_brief.py`, and
  - facade-only re-export modules like `validation.py` (once downstream imports are migrated).
- The `data_io` fallback is likely worth keeping because it improves resilience in editable installs, tests, and packaging edge cases.
