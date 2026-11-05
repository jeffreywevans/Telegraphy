from __future__ import annotations

import json
import re
import tomllib
import uuid
from pathlib import Path

from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SBOM_PATH = REPO_ROOT / "sbom.cdx.json"
SCHEMA = "https://cyclonedx.org/schema/bom-1.6.schema.json"
PYPI_NORMALIZATION_PATTERN = re.compile(r"[-_.]+")


def _load_project_metadata(pyproject_path: Path) -> tuple[str, str, tuple[Requirement, ...]]:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data["project"]
    name = str(project["name"])
    version = str(project["version"])
    dependencies = tuple(Requirement(str(value)) for value in project.get("dependencies", []))
    return name, version, dependencies


def _normalize_pypi_name(name: str) -> str:
    return PYPI_NORMALIZATION_PATTERN.sub("-", name).lower()


def _package_url(name: str, version: str | None = None) -> str:
    version_suffix = f"@{version}" if version is not None else ""
    return f"pkg:pypi/{_normalize_pypi_name(name)}{version_suffix}"


def _exact_requirement_version(requirement: Requirement) -> str | None:
    specifiers = list(requirement.specifier)
    if len(specifiers) != 1:
        return None
    specifier = specifiers[0]
    if specifier.operator != "==" or "*" in specifier.version:
        return None
    return specifier.version


def _dependency_component(requirement: Requirement) -> tuple[str, dict[str, object]]:
    exact_version = _exact_requirement_version(requirement)
    dependency_ref = _package_url(requirement.name, exact_version)
    component: dict[str, object] = {
        "bom-ref": dependency_ref,
        "type": "library",
        "name": requirement.name,
        "purl": dependency_ref,
        "scope": "required",
        "properties": [
            {
                "name": "telegraphy:declared-requirement",
                "value": str(requirement),
            }
        ],
    }
    if exact_version is not None:
        component["version"] = exact_version
    return dependency_ref, component


def build_sbom() -> dict[str, object]:
    name, version, runtime_dependencies = _load_project_metadata(PYPROJECT_PATH)

    project_ref = _package_url(name, version)
    dependency_entries = [
        _dependency_component(requirement) for requirement in runtime_dependencies
    ]
    dependency_refs = [reference for reference, _component in dependency_entries]
    dependency_components = [component for _reference, component in dependency_entries]
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"https://pypi.org/project/{name}/{version}/")

    return {
        "$schema": SCHEMA,
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": project_ref,
                "type": "application",
                "name": name,
                "version": version,
                "purl": project_ref,
                "licenses": [{"license": {"id": "MIT"}}],
            }
        },
        "components": dependency_components,
        "dependencies": [
            {"ref": project_ref, "dependsOn": dependency_refs},
            *({"ref": dependency_ref, "dependsOn": []} for dependency_ref in dependency_refs),
        ],
    }


def main() -> int:
    sbom = build_sbom()
    SBOM_PATH.write_text(f"{json.dumps(sbom, indent=2)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
