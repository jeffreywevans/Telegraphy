#!/usr/bin/env python3
"""Run pytest and produce combined coverage outputs."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

COVERAGE_CONFIG_FILE = "tox.ini"


def main() -> int:
    project_root = Path(os.environ.get("TOX_PROJECT_ROOT", Path.cwd())).resolve()
    coverage_config_file = project_root / COVERAGE_CONFIG_FILE
    tests_dir = project_root / "tests"
    junit_xml = project_root / "test-results.xml"
    coverage_xml = project_root / "coverage.xml"

    print("Running pytest with coverage...", flush=True)
    pytest_rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov=telegraphy",
            f"--cov-config={coverage_config_file}",
            "--cov-branch",
            "--cov-report=",
            f"--junitxml={junit_xml}",
            str(tests_dir),
        ],
    ).returncode

    covfile = os.environ.get("COVERAGE_FILE", ".coverage")
    combine_dir = os.path.dirname(covfile) or "."
    combine_rc = 0
    if glob.glob(covfile + ".*"):
        print("Combining coverage files...", flush=True)
        combine_rc = subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "combine",
                f"--rcfile={coverage_config_file}",
                combine_dir,
            ],
        ).returncode

    print("Writing coverage.xml...", flush=True)
    xml_rc = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "xml",
            f"--rcfile={coverage_config_file}",
            "-o",
            str(coverage_xml),
        ],
    ).returncode
    print("Writing terminal coverage report...", flush=True)
    report_rc = subprocess.run(
        [sys.executable, "-m", "coverage", "report", f"--rcfile={coverage_config_file}"],
    ).returncode

    if pytest_rc != 0:
        return pytest_rc
    if combine_rc != 0:
        return combine_rc
    if xml_rc != 0:
        return xml_rc
    if report_rc != 0:
        return report_rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
