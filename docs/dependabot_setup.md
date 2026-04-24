# Dependabot setup recommendations

This repository is a good fit for two Dependabot ecosystems:

1. **`pip`** for Python dependencies defined in [`pyproject.toml`](../pyproject.toml) (installation instructions are provided in [`docs/requirements.md`](requirements.md) and [`docs/requirements-dev.md`](requirements-dev.md)).
2. **`github-actions`** for GitHub Actions workflow dependencies (for example, `actions/checkout` and `actions/setup-python`).

## Proposed defaults

- **Weekly updates** on Monday mornings (UTC) to avoid excessive PR churn.
- **Focused pip groups** for this repo's current dependencies:
  - `runtime-pyyaml`
  - `build-setuptools`
  - `dev-pytest`
- **Labels** so dependency PRs are easy to filter and triage.
- **PR limits** to avoid backlog growth during busy weeks.

## Where this is configured

- `.github/dependabot.yml`
- A workflow to keep required labels present: [`.github/workflows/ensure-labels.yml`](../.github/workflows/ensure-labels.yml).

## Optional next steps

- Turn on **auto-merge** for patch-level updates once CI has proven stable.
- Add a `CODEOWNERS` entry for `.github/dependabot.yml` so dependency automation changes always get review.
- If this repo adds new ecosystems later (e.g., Docker, npm), add additional `updates` entries.

## Security audit + lock snapshot guidance

For this repository's small dependency footprint, a lightweight CI security audit has high ROI and low maintenance cost.

- Prefer running `pip-audit` in CI against dependency definitions (for example, `pyproject.toml`) before installing the environment.
- Keep Dependabot enabled so known issues can be remediated quickly.
- Treat `pip freeze` snapshots (for example, `requirements-locked.txt`) as optional unless the project needs strict, reproducible dependency pinning across environments.

In other words: `pip-audit` is generally valuable here; committed lock snapshots are useful when reproducibility/compliance needs outweigh update churn.
