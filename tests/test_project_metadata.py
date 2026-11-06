from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote

import pytest
from packaging.requirements import Requirement

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
README_PATH = PROJECT_ROOT / "README.md"
WORD_COUNT_TARGETS_PATH = (
    PROJECT_ROOT / "telegraphy" / "story_brief" / "data" / "word_count_targets.json"
)
EXPECTED_DISTRIBUTION_NAME = "Commuted_Telegraphy"
REPOSITORY_BLOB_PREFIX = "https://github.com/jeffreywevans/Telegraphy/blob/HEAD/"


def _load_pyproject() -> dict[str, Any]:
    return tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))


def _read_readme_section(start_heading: str, end_heading: str) -> str:
    readme = README_PATH.read_text(encoding="utf-8")
    return readme.split(start_heading, maxsplit=1)[1].split(end_heading, maxsplit=1)[0]


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


def test_readme_development_tools_match_dev_extra() -> None:
    project = _load_pyproject()["project"]
    development_section = _read_readme_section("For development:", "You can verify that the CLI")

    for raw_requirement in project["optional-dependencies"]["dev"]:
        dependency_name = Requirement(str(raw_requirement)).name
        assert f"- `{dependency_name}`" in development_section


def test_readme_project_facts_list_every_console_script() -> None:
    project = _load_pyproject()["project"]
    facts_section = _read_readme_section("### Project metadata", "### Contribution expectations")

    for script_name, entry_point in project["scripts"].items():
        assert f"`{script_name} = {entry_point}`" in facts_section


def test_readme_word_count_samples_exist_in_dataset() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    samples = [int(value) for value in re.findall(r"^word_count_target: ([0-9]+)$", readme, re.M)]
    payload = cast(
        dict[str, list[int]], json.loads(WORD_COUNT_TARGETS_PATH.read_text(encoding="utf-8"))
    )

    assert samples
    assert set(samples) <= set(payload["word_count_targets"])


def test_readme_repository_file_links_resolve() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    repository_links = re.findall(
        rf"\]\(({re.escape(REPOSITORY_BLOB_PREFIX)}[^)]+)\)",
        readme,
    )

    assert repository_links
    for url in repository_links:
        relative_path = unquote(url.removeprefix(REPOSITORY_BLOB_PREFIX).split("#", maxsplit=1)[0])
        assert (PROJECT_ROOT / relative_path).is_file(), relative_path

    expected_license_url = f"{REPOSITORY_BLOB_PREFIX}LICENSE"
    assert readme.count(expected_license_url) == 2
    assert "https://github.com/jeffreywevans/Telegraphy/license" not in readme


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
