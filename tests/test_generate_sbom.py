from __future__ import annotations

import json
import runpy
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from telegraphy.scripts import generate_sbom


def test_package_url_normalizes_project_names_for_pypi_purls() -> None:
    assert (
        generate_sbom._package_url("Commuted_Telegraphy", "0.4.3")
        == "pkg:pypi/commuted-telegraphy@0.4.3"
    )


@pytest.mark.parametrize("requirement_text", ["alpha", "alpha>=1,<2"])
def test_exact_requirement_version_rejects_non_single_specifiers(
    requirement_text: str,
) -> None:
    assert generate_sbom._exact_requirement_version(Requirement(requirement_text)) is None


def test_build_sbom_includes_component_bom_refs() -> None:
    sbom = generate_sbom.build_sbom()

    root_component = sbom["metadata"]["component"]
    dependency_component = sbom["components"][0]

    assert root_component["bom-ref"] == root_component["purl"]
    assert dependency_component["bom-ref"] == dependency_component["purl"]


def test_build_sbom_matches_pyproject_version_and_dependency() -> None:
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject_data["project"]
    dependency = Requirement(project["dependencies"][0])

    sbom = generate_sbom.build_sbom()
    root_component = sbom["metadata"]["component"]
    dependency_component = sbom["components"][0]

    assert root_component["version"] == project["version"]
    assert dependency_component["name"] == dependency.name
    assert "version" not in dependency_component
    assert dependency_component["purl"] == "pkg:pypi/pyyaml"
    assert dependency_component["properties"] == [
        {
            "name": "telegraphy:declared-requirement",
            "value": str(dependency),
        }
    ]


def test_main_writes_valid_json(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "sbom.cdx.json"
    monkeypatch.setattr(generate_sbom, "SBOM_PATH", output_path)

    assert generate_sbom.main() == 0

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["bomFormat"] == "CycloneDX"


def test_build_sbom_supports_multiple_runtime_dependencies(tmp_path, monkeypatch) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "telegraphy"
version = "0.1.0"
dependencies = ["alpha>=1", "bravo==2.0"]
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(generate_sbom, "PYPROJECT_PATH", pyproject_path)

    sbom = generate_sbom.build_sbom()

    assert [component["name"] for component in sbom["components"]] == ["alpha", "bravo"]
    assert sbom["components"][0]["purl"] == "pkg:pypi/alpha"
    assert sbom["components"][1]["purl"] == "pkg:pypi/bravo@2.0"
    assert sbom["components"][1]["version"] == "2.0"
    assert sbom["dependencies"][0]["dependsOn"] == [
        "pkg:pypi/alpha",
        "pkg:pypi/bravo@2.0",
    ]


def test_load_project_metadata_accepts_no_runtime_dependencies(tmp_path) -> None:
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(
        """
[project]
name = "telegraphy"
version = "0.1.0"
dependencies = []
""".strip(),
        encoding="utf-8",
    )

    name, version, dependencies = generate_sbom._load_project_metadata(pyproject_path)

    assert (name, version) == ("telegraphy", "0.1.0")
    assert dependencies == ()


def test_module_entrypoint_exits_cleanly_and_writes_output(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_write_text(self: Path, data: str, encoding: str = "utf-8") -> int:
        captured["path"] = self
        captured["data"] = data
        captured["encoding"] = encoding
        return len(data)

    monkeypatch.setattr(Path, "write_text", _fake_write_text)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(generate_sbom.__file__), run_name="__main__")

    assert exc_info.value.code == 0
    assert captured["path"] == generate_sbom.SBOM_PATH
    assert captured["encoding"] == "utf-8"
    assert '"bomFormat": "CycloneDX"' in str(captured["data"])
