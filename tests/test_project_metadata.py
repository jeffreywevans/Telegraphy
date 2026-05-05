from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PYPROJECT_PATH = Path("pyproject.toml")
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
    assert project["requires-python"] == ">=3.12"
    assert project["dependencies"] == ["PyYAML>=6.0.3"]
    assert project["urls"]["Repository"] == "https://github.com/jeffreywevans/Telegraphy.git"


def test_setuptools_package_discovery_keeps_import_package_name() -> None:
    setuptools_config = _load_pyproject()["tool"]["setuptools"]

    assert setuptools_config["packages"]["find"]["include"] == ["telegraphy*"]
    assert setuptools_config["packages"]["find"]["namespaces"] is False
    assert setuptools_config["package-data"]["telegraphy.story_brief.data"] == ["*.json"]
