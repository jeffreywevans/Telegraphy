from __future__ import annotations

import json
from pathlib import Path

import tomllib

from telegraphy.scripts import generate_sbom


def test_build_sbom_includes_component_bom_refs() -> None:
    sbom = generate_sbom.build_sbom()

    root_component = sbom["metadata"]["component"]
    dependency_component = sbom["components"][0]

    assert root_component["bom-ref"] == root_component["purl"]
    assert dependency_component["bom-ref"] == dependency_component["purl"]


def test_build_sbom_matches_pyproject_version_and_dependency() -> None:
    pyproject_data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject_data["project"]
    dependency_spec = project["dependencies"][0]
    dep_name, dep_version = dependency_spec.split(">=", maxsplit=1)

    sbom = generate_sbom.build_sbom()
    root_component = sbom["metadata"]["component"]
    dependency_component = sbom["components"][0]

    assert root_component["version"] == project["version"]
    assert dependency_component["name"] == dep_name
    assert dependency_component["version"] == dep_version


def test_main_writes_valid_json(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "sbom.cdx.json"
    monkeypatch.setattr(generate_sbom, "SBOM_PATH", output_path)

    assert generate_sbom.main() == 0

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["bomFormat"] == "CycloneDX"
