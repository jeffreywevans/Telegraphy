from __future__ import annotations

import json
import runpy
import tomllib
from pathlib import Path

import pytest

from telegraphy.scripts import generate_sbom


def test_package_url_normalizes_project_names_for_pypi_purls() -> None:
    assert (
        generate_sbom._package_url("Commuted_Telegraphy", "0.4.3")
        == "pkg:pypi/commuted-telegraphy@0.4.3"
    )


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


def test_load_project_metadata_raises_without_exactly_one_dependency(tmp_path) -> None:
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

    with pytest.raises(ValueError, match="exactly one runtime dependency"):
        generate_sbom._load_project_metadata(pyproject_path)


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
