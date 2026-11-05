from __future__ import annotations

import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
EXPECTED_DISTRIBUTION_NAME = "Commuted_Telegraphy"


def _load_pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def test_project_metadata_uses_pypi_distribution_name() -> None:
    project = _load_pyproject()["project"]

    assert project["name"] == EXPECTED_DISTRIBUTION_NAME


def test_project_metadata_declares_release_metadata() -> None:
    project = _load_pyproject()["project"]

    assert project["readme"] == {"file": "README.md", "content-type": "text/markdown"}
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert "License :: OSI Approved :: MIT License" not in project["classifiers"]
    assert project["requires-python"] == ">=3.14"
    assert any(dep.casefold().startswith("pyyaml") for dep in project["dependencies"])
    assert project["urls"]["Repository"] == "https://github.com/jeffreywevans/Telegraphy.git"


def test_setuptools_package_discovery_keeps_import_package_name() -> None:
    setuptools_config = _load_pyproject()["tool"]["setuptools"]

    assert setuptools_config["packages"]["find"]["include"] == ["telegraphy*"]
    assert setuptools_config["packages"]["find"]["namespaces"] is False
    assert setuptools_config["package-data"]["telegraphy.story_brief.data"] == ["*.json"]


@pytest.mark.integration
def test_built_wheel_excludes_repository_tooling(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
        ],
        cwd=PYPROJECT_PATH.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1

    with zipfile.ZipFile(wheels[0]) as wheel:
        archived_paths = wheel.namelist()

    assert not any(path.startswith("telegraphy/scripts/") for path in archived_paths)
    assert not any(path.startswith("scripts/") for path in archived_paths)
