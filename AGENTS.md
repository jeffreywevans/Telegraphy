# AGENTS.md

## Purpose
This file defines coding, testing, and review expectations for AI coding agents working in this repository. The objective is to maximize first-pass quality and minimize PR rework under strict automated and human review.

## Core Principles
- Prioritize correctness, security, maintainability, and performance over speed of implementation.
- Prefer explicit, readable code over clever or compressed code.
- Assume all code will be reviewed by static analysis, security scanners, and strict tests.
- Treat every change as production-grade.

## Python Standards
- Target Python 3.11+ syntax unless the repository specifies otherwise.
- Use type hints for all public functions, methods, and module-level constants.
- Avoid `Any` unless unavoidable; prefer precise types (`TypedDict`, `Protocol`, generics, enums).
- Keep functions small and single-purpose.
- Document non-obvious logic with concise docstrings or comments.
- Use dataclasses for structured data when appropriate.
- Avoid hidden side effects; make state transitions explicit.

## Design & Architecture
- Follow existing project architecture and patterns; do not introduce new frameworks without strong justification.
- Keep business logic separate from I/O boundaries (HTTP, DB, filesystem, CLI).
- Use dependency injection patterns where feasible to improve testability.
- Preserve backward compatibility unless the task explicitly allows breaking changes.
- Minimize public API surface area; avoid exposing internals.

## Security Requirements (Non-Negotiable)
- Validate and sanitize all external inputs.
- Never hardcode secrets, tokens, passwords, or private keys.
- Do not log secrets or sensitive personal data.
- Use parameterized queries; never build SQL from string concatenation.
- Avoid unsafe deserialization (`pickle`/`yaml.load` without safe loaders) for untrusted input.
- Avoid shell execution with interpolated user input. If subprocess is required, use argument lists and strict allowlists.
- Use least-privilege access patterns for files, network calls, and credentials.
- Fail securely: explicit errors, safe defaults.

## Reliability & Error Handling
- Raise specific exceptions; avoid broad `except Exception` unless re-raising with context.
- Handle boundary conditions explicitly (empty input, large input, null/None, timeouts, retries).
- Ensure idempotency where operations may be retried.
- Include meaningful error messages that aid debugging without leaking sensitive context.

## Performance Guidelines
- Avoid unnecessary allocations, repeated parsing, and redundant I/O.
- Be mindful of algorithmic complexity; avoid accidental O(n²) behavior on hot paths.
- Stream large payloads where possible rather than loading everything into memory.
- Add micro-optimizations only when they improve measurable bottlenecks.

## Testing Expectations
- Add or update tests for every functional change.
- Cover happy paths, edge cases, and failure modes.
- Prefer deterministic tests; avoid network and time flakiness.
- Use fixtures/factories to keep tests readable and maintainable.
- Include regression tests for bug fixes.
- Aim for strong line and branch coverage in changed code.

## Quality Gates Before Commit
Agents should run relevant checks locally before committing (adjust to project tooling):
- Formatter/linter (e.g., `ruff format`, `ruff check`)
- Type checks (e.g., `mypy` with strict settings where configured)
- Tests (e.g., `pytest` including targeted integration tests when touched)
- Security/static checks if configured in repo

If any check fails:
- Fix root causes rather than suppressing warnings.
- Do not disable rules without explicit justification in the PR.

## Code Review Readiness
Before finalizing a change, verify:
- The implementation is minimal but complete.
- Naming is clear and domain-accurate.
- New dependencies are necessary and justified.
- Docs/comments are updated when behavior changes.
- Migrations/config changes are included if needed.

## PR Description Standards
When preparing PR content, include:
- What changed and why.
- Risks and mitigations.
- Test plan and exact commands run.
- Any follow-up work intentionally deferred.

## Prohibited Shortcuts
- No placeholder logic in production code (`TODO` in critical paths without issue linkage).
- No silent exception swallowing.
- No dead code or commented-out legacy blocks.
- No speculative abstractions not required by the task.

## Agent Behavior
- Ask clarifying questions when requirements are ambiguous.
- If assumptions are required, state them explicitly in the PR summary.
- Prefer small, atomic commits with coherent scope.
- Keep diffs focused; avoid unrelated refactors.

## Definition of Done
A task is done only when:
- Implementation is correct and secure.
- Tests for changed behavior pass locally.
- Static analysis and linting issues in changed code are resolved.
- PR summary clearly explains changes and validation.
