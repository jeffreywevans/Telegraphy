# Legacy Tag-System Inventory (Phase 1)

This document inventories references and runtime touchpoints related to the previous tag schema, focused on sexual-scene tag count configuration.

## Scope and search method

Commands used:

- `rg -n "legacy|migration|sexual_scene_tag_count_options|sexual_scene_tag_count_weights|sexual_content_options|sexual_content_weights|by-presence|canonical" README.md docs telegraphy tests CHANGELOG.md`

Out of scope for this inventory:

- Generic uses of the word `tag` unrelated to legacy schema migration.
- Git release tag references.
- UI canvas `tags` arguments.

## Classification rubric

- **Required current behavior**: needed to enforce or document the current canonical contract.
- **Naming debt**: behavior is correct, but naming or wording implies old migration semantics.
- **Potential dead/legacy compatibility path**: likely removable or simplifiable in Phase 2+, pending parity verification.

## Inventory

### 1) Runtime code paths

1. `telegraphy/story_brief/schema_validation.py`
   - `_apply_legacy_config_migrations` rejects removed keys:
     - `sexual_content_options`
     - `sexual_content_weights`
     - `sexual_scene_tag_count_weights`
   - Also injects defaults for:
     - `sexual_content_story_role_options`
     - `sexual_content_story_role_weights`
     - `sexual_scene_optional_tag_groups`
   - **Classification**: mixed
     - Rejection behavior: **Required current behavior**.
     - Function name + docstring (“migrations”): **Naming debt**.
     - Coupling rejection and defaults in one helper: **Potential simplification target**.

2. `telegraphy/story_brief/generation.py`
   - Internal weighted-choice labels still use strings:
     - `"sexual_content_options"`
     - `"sexual_content_weights"`
   - These are labels for diagnostics/validation context, not config keys.
   - **Classification**: **Naming debt** (can confuse with removed legacy config keys).

3. `telegraphy/story_brief/normalization.py`
   - Canonical field usage only (`sexual_scene_tag_count_weights_by_presence`).
   - **Classification**: **Required current behavior** (no legacy compatibility observed).

4. `telegraphy/story_brief/generate_story_brief.py`
   - Comment references “Backward-compatible aliases re-exported from the canonical mapping.”
   - Needs confirmation whether aliases are public API stability (intentional) vs legacy residue.
   - **Classification**: **Potential legacy compatibility path** pending API audit.

### 2) Tests

1. `tests/story_brief/validation/test_schema_validation.py`
   - `test_schema_validation_rejects_legacy_tag_config_keys` enforces rejection of old keys.
   - **Classification**: **Required current behavior**.

2. Data-loading and generation tests consistently reference canonical by-presence schema.
   - **Classification**: **Required current behavior**.

### 3) Documentation and changelog

1. `README.md`
   - Explicit migration section listing removed keys and canonical replacement.
   - States legacy keys fail fast.
   - **Classification**: **Required current behavior** (user-facing migration guidance).

2. `CHANGELOG.md`
   - Records legacy cleanup and migration documentation.
   - Includes historical note about removed env-var override.
   - **Classification**: historical record; keep unless release-history policy says otherwise.

3. `docs/STORY-BRIEF-MAINTAINER.md`
   - Advises parity verification before removing legacy tables.
   - **Classification**: **Required process guidance**.

## Preliminary removal/simplification candidates for Phase 2

1. Rename `_apply_legacy_config_migrations` to reflect present behavior (reject unsupported keys + apply supported defaults).
2. Split concerns:
   - one helper for rejecting removed keys,
   - one helper for applying current defaults.
3. Evaluate whether weighted-choice label strings in `generation.py` should avoid removed-key terminology to reduce ambiguity.
4. Audit `generate_story_brief.py` alias comment/API to confirm intentional compatibility contract; remove if stale.

## Risks to manage in subsequent phases

- Accidentally removing explicit legacy-key rejection (contract regression).
- Breaking backward-compatible API exports relied on by callers.
- Altering error messages that tests or downstream tooling parse.

## Exit criteria for Phase 1

- [x] Inventory of all legacy-schema references in runtime, tests, and docs.
- [x] Classification into required behavior vs naming debt vs potential removal targets.
- [x] Candidate cleanup list prepared for Phase 2 implementation.
