
Here’s the build-declaration checklist for use for **Telegraphy**. Think of it as the “before you ring the bell and call it a build” ritual. Less ceremony than a release train, more useful than sacrificing a goat to `pip`.

## Telegraphy build declaration checklist

### 1. Version identity

Every declared build must have one clear version number.

Check and update:

```text
pyproject.toml
README.md
CHANGELOG.md
sbom.cdx.json
any __version__ field, if added later
Git tag, if this build is released publicly
```

The version should agree everywhere. No `0.4.0` in `pyproject.toml`, `0.3.3` in README, and `0.2.2` in the SBOM. That is how software becomes haunted.

Recommended rule:

```text
pyproject.toml is the source of truth.
Everything else must match it.
```

---

### 2. Changelog entry

Every build needs a changelog entry before it is declared.

Minimum contents:

```text
Version number
Date
Added
Changed
Fixed
Security, if applicable
Known issues, if applicable
```

For example:

```markdown
## 0.4.1 - 2026-05-03

### Fixed
- Regenerated SBOM to match package version.
- Updated README version references.

### Changed
- Improved GUI error handling for headless environments.

### Known Issues
- GUI does not yet expose seed/date controls.
```

Do not make the changelog a victory parade. Make it useful to future-you at 1:37 AM with a broken install and a grudge.

---

### 3. README status block

Update any project status/version section.

Check for stale phrases like:

```text
Current version
Current status
Latest version
Installation notes
CLI examples
GUI notes
```

If the README says the current package is `0.3.3` and the build is `0.4.0`, the README is lying. It may be lying politely, but still lying.

---

### 4. SBOM regeneration

Regenerate the SBOM for every declared build.

Run:

```bash
python -m telegraphy.scripts.generate_sbom
```

Then verify that `sbom.cdx.json` contains the current version.

At minimum, check:

```text
metadata.component.name
metadata.component.version
dependencies
declared runtime packages
```

Then commit the updated SBOM.

If the SBOM is committed to the repo, it must be treated as a build artifact, not a museum fossil.

---

### 5. Dataset validation

Run the dataset lint:

```bash
python -m telegraphy.story_brief --lint-dataset
```

Expected result:

```text
Dataset lint: no blocking coverage gaps found.
Dataset lint: no warnings.
```

If there are warnings, decide whether they are acceptable for the build. If there are blocking gaps, no build.

Also run strict validation:

```bash
python -m telegraphy.story_brief --validate-strict --seed 42 --date 2000-01-01 --print-only
```

This confirms that the data and generator can produce a valid brief under strict rules.

---

### 6. Test suite

Run the full test suite.

Recommended local command:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

On Windows PowerShell:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"
python -m pytest -q
```

Expected result should be clean, for example:

```text
343 passed
```

If the number changes because tests were added or removed, that is fine. What matters is that the suite passes.

Do not declare a build with skipped failures, mysterious hangs, or “works on my machine if Mercury is in retrograde” logic.

---

### 7. Coverage

Run coverage.

If using pytest-cov explicitly:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --cov=telegraphy --cov-report=term-missing
```

Expected:

```text
Coverage requirement met
```

Current project target appears to be 90%. Given that the project is currently around 98%, I would avoid letting it slide without a reason.

Build rule:

```text
Coverage must remain above threshold.
Any significant drop must be explained in the changelog or PR notes.
```

---

### 8. Static checks

Run Ruff:

```bash
python -m ruff check .
```

Run formatting check if configured:

```bash
python -m ruff format --check .
```

Run mypy:

```bash
python -m mypy telegraphy
```

If CI uses stricter settings than local commands, follow CI.

Build rule:

```text
No lint failures.
No type-check failures.
No “I’ll fix that later” landmines.
```

Later is where landmines breed.

---

### 9. Package build check

Build the package locally:

```bash
python -m build
```

Then inspect the generated artifacts:

```text
dist/*.whl
dist/*.tar.gz
```

Verify that package data is included, especially:

```text
telegraphy/story_brief/data/*.json
```

Then install the wheel into a clean virtual environment if possible:

```bash
python -m venv .venv-build-test
source .venv-build-test/bin/activate
pip install dist/*.whl
story-brief --help
story-brief --print-only --seed 42 --date 2000-01-01
```

PowerShell version:

```powershell
python -m venv .venv-build-test
.venv-build-test\Scripts\Activate.ps1
pip install dist\*.whl
story-brief --help
story-brief --print-only --seed 42 --date 2000-01-01
```

This catches the classic packaging horror: tests pass from source, installed package is missing data files, CLI explodes like a microwave full of forks.

---

### 10. CLI smoke tests

Run these for every build:

```bash
story-brief --help
story-brief --print-only
story-brief --print-only --seed 42
story-brief --print-only --seed 42 --date 2000-01-01
story-brief --validate-strict --print-only --seed 42 --date 2000-01-01
story-brief --lint-dataset
```

Also test safe file output:

```bash
story-brief --seed 42 --date 2000-01-01
```

Confirm that a Markdown file is created with the expected naming convention.

Then test overwrite protection:

```bash
story-brief --seed 42 --date 2000-01-01
```

Expected: should refuse to overwrite unless `--force` is used.

Then:

```bash
story-brief --seed 42 --date 2000-01-01 --force
```

Expected: succeeds.

---

### 11. GUI smoke test

Run:

```bash
telegraphy-gui
```

Confirm:

```text
Window opens
Generate button works
Brief appears
Copy button works
Status text updates correctly
Failure states re-enable the UI
```

For now, also test:

```bash
python -m telegraphy.gui.tablet_app
```

Because users may try both.

If running in a headless environment, document that GUI testing was not performed there. Do not pretend it passed.

---

### 12. Data override test

Because `TELEGRAPHY_DATA_DIR` is a supported feature, test it before declaring a build.

Create a temporary copy of the data directory, then run:

```bash
TELEGRAPHY_DATA_DIR=/path/to/copied/data story-brief --lint-dataset
TELEGRAPHY_DATA_DIR=/path/to/copied/data story-brief --print-only --seed 42 --date 2000-01-01
```

PowerShell:

```powershell
$env:TELEGRAPHY_DATA_DIR="C:\path\to\copied\data"
story-brief --lint-dataset
story-brief --print-only --seed 42 --date 2000-01-01
```

Then clear it:

```powershell
Remove-Item Env:\TELEGRAPHY_DATA_DIR
```

This confirms packaged data and override data both work.

---

### 13. Security sanity check

For every declared build, confirm no new dangerous patterns were added.

Search for:

```bash
grep -R "shell=True" telegraphy
grep -R "eval(" telegraphy
grep -R "exec(" telegraphy
grep -R "pickle" telegraphy
grep -R "yaml.load" telegraphy
grep -R "os.system" telegraphy
```

PowerShell:

```powershell
Select-String -Path telegraphy\**\*.py -Pattern "shell=True","eval\(","exec\(","pickle","yaml.load","os.system"
```

Expected: no unsafe usage, or a clearly reviewed false positive.

Also verify:

```text
No untrusted shell command construction
No unsafe YAML loading
No arbitrary file writes outside intended output directory
No accidental secret files committed
No generated build artifacts containing local paths or private data
```

---

### 14. Dependency check

Before each build, review dependency changes.

Check:

```text
pyproject.toml
requirements*.txt, if present
Dependabot PRs
GitHub Actions pins
SBOM dependency list
```

Run:

```bash
python -m pip list --outdated
```

Do not blindly update everything. That way lies dependency soup. But every declared build should know whether it is shipping with stale or vulnerable dependencies.

For security-sensitive dependency changes, mention them in the changelog.

---

### 15. CI status

Before declaring the build done:

```text
All GitHub Actions pass
CodeQL passes
Tests pass
Coverage passes
Ruff passes
mypy passes
SBOM check passes, if added
```

Do not declare a build from a dirty branch with failing CI unless it is explicitly marked as an internal dirty build.

Recommended build labels:

```text
clean build
dirty local build
release candidate
public release
hotfix
```

That vocabulary prevents confusion.

---

### 16. Git hygiene

Before declaration:

```bash
git status
git diff
git log --oneline -5
```

Confirm:

```text
No accidental generated files
No local-only scratch files
No stale dist/ artifacts unless intentionally committed
No private notes
No zip files committed by accident
No test output files left behind
```

Then commit with a build-specific message:

```bash
git commit -m "Prepare Telegraphy 0.4.1 build"
```

If public release:

```bash
git tag v0.4.1
git push origin main --tags
```

---

### 17. Release artifact check

If producing a zip, wheel, or source distribution, record:

```text
Version
Commit hash
Build date
Python version used
Test result
Coverage result
Artifact filenames
```

Optional but useful:

```bash
git rev-parse HEAD
python --version
python -m pip freeze
```

Store this in a `BUILD_NOTES.md` or release notes section if you want better traceability.

---

### 18. Final human smoke test

Before calling it done, generate three briefs:

```bash
story-brief --print-only --seed 1 --date 1990-01-01
story-brief --print-only --seed 42 --date 2000-01-01
story-brief --print-only --seed 8675309 --date 2014-01-09
```

Read them.

Not skim. Read.

Confirm:

```text
No canon-impossible pairings
No broken YAML
No weird nulls
No missing fields
No malformed Markdown
No date-inappropriate character/setting choices
No obviously repetitive or degenerate output
```

Automated tests catch logic. Human reading catches “the robot technically obeyed but produced cursed oatmeal.”

## Minimum build gate

If you want the short hard gate, every declared build must satisfy this:

```text
Version updated consistently
CHANGELOG updated
README status updated
SBOM regenerated
Dataset lint passes
Strict validation passes
Tests pass
Coverage passes
Ruff passes
mypy passes
Package builds
Installed wheel smoke-tested
CLI smoke-tested
GUI smoke-tested or explicitly marked untested
CI green
Git tree clean
Tag created if public release
```

## Recommended `BUILD_CHECKLIST.md`

You could drop this into the repo:

```markdown
# Telegraphy Build Checklist

## Version
- [ ] `pyproject.toml` version updated
- [ ] README version/status updated
- [ ] CHANGELOG entry added
- [ ] SBOM regenerated
- [ ] SBOM version matches package version

## Validation
- [ ] `story-brief --lint-dataset` passes
- [ ] `story-brief --validate-strict --print-only --seed 42 --date 2000-01-01` passes

## Tests
- [ ] Full pytest suite passes
- [ ] Coverage meets threshold
- [ ] Ruff passes
- [ ] Ruff format check passes
- [ ] mypy passes

## Packaging
- [ ] `python -m build` succeeds
- [ ] Wheel installs in clean venv
- [ ] Packaged JSON data is present
- [ ] `story-brief --help` works from installed wheel

## Smoke Tests
- [ ] CLI print-only works
- [ ] CLI seeded generation works
- [ ] CLI date-specific generation works
- [ ] CLI output file creation works
- [ ] CLI overwrite protection works
- [ ] GUI launches
- [ ] GUI generates brief
- [ ] GUI copy button works

## Security
- [ ] No unsafe shell usage added
- [ ] No unsafe YAML loading added
- [ ] No arbitrary file-write paths added
- [ ] No secrets or private files committed
- [ ] Dependencies reviewed

## CI / Git
- [ ] GitHub Actions pass
- [ ] CodeQL passes
- [ ] Working tree clean
- [ ] Commit hash recorded
- [ ] Tag created, if public release
- [ ] Release notes published, if public release
```
