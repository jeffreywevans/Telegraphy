from __future__ import annotations

import json
import re
import tomllib
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
SBOM_PATH = REPO_ROOT / "sbom.cdx.json"
SCHEMA = "https://cyclonedx.org/schema/bom-1.6.schema.json"
PYPI_NORMALIZATION_PATTERN = re.compile(r"[-_.]+")


def _load_project_metadata(pyproject_path: Path) -> tuple[str, str, str]:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = data["project"]
    name = project["name"]
    version = project["version"]
    dependencies = project.get("dependencies", [])
    if len(dependencies) != 1:
        raise ValueError("SBOM generator expects exactly one runtime dependency.")
    dep = dependencies[0]
    dep_name, dep_version = dep.split(">=", maxsplit=1)
    return name, version, f"{dep_name}=={dep_version}"


def _normalize_pypi_name(name: str) -> str:
    return PYPI_NORMALIZATION_PATTERN.sub("-", name).lower()


def _package_url(name: str, version: str) -> str:
    return f"pkg:pypi/{_normalize_pypi_name(name)}@{version}"


def build_sbom() -> dict[str, object]:
    name, version, runtime_dep = _load_project_metadata(PYPROJECT_PATH)
    dep_name, dep_version = runtime_dep.split("==", maxsplit=1)

    project_ref = _package_url(name, version)
    dep_ref = _package_url(dep_name, dep_version)
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
        "components": [
            {
                "bom-ref": dep_ref,
                "type": "library",
                "name": dep_name,
                "version": dep_version,
                "purl": dep_ref,
                "scope": "required",
            }
        ],
        "dependencies": [
            {"ref": project_ref, "dependsOn": [dep_ref]},
            {"ref": dep_ref, "dependsOn": []},
        ],
    }


def main() -> int:
    sbom = build_sbom()
    SBOM_PATH.write_text(f"{json.dumps(sbom, indent=2)}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
