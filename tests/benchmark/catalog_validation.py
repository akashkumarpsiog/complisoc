"""Validate benchmark control metadata against the production seed catalog."""
from __future__ import annotations

import ast
import pathlib
from urllib.parse import urlparse


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MIGRATIONS = (
    _REPO_ROOT / "backend" / "migrations" / "versions" / "0003_seed_iso27001_annex_a.py",
    _REPO_ROOT / "backend" / "migrations" / "versions" / "0011_correct_iso27001_benchmark_controls.py",
)
_MATCHED_FIELDS = (
    "control_family",
    "title",
    "description",
    "objective",
    "source_url",
)


def _production_controls() -> dict[str, dict]:
    controls: dict[str, dict] = {}
    for migration_path in _MIGRATIONS:
        tree = ast.parse(migration_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "upgrade":
                continue
            for statement in node.body:
                if not isinstance(statement, ast.Assign):
                    continue
                names = {
                    target.id
                    for target in statement.targets
                    if isinstance(target, ast.Name)
                }
                if "controls" in names:
                    for control in ast.literal_eval(statement.value):
                        controls[control["control_id"]] = control
                elif "control_updates" in names:
                    for update in ast.literal_eval(statement.value):
                        controls[update["control_id"]].update(update)
    return controls


def validate_gold_catalog(gold: dict) -> None:
    """Raise ValueError if gold control metadata disagrees with production."""
    framework = gold.get("framework")
    if framework != "ISO/IEC 27001:2022 Annex A" or gold.get("framework_version") != "2022":
        raise ValueError("Benchmark framework must be ISO/IEC 27001:2022 Annex A")

    controls = gold.get("controls")
    if not isinstance(controls, list) or not controls:
        raise ValueError("Benchmark must contain a non-empty control catalog")

    by_id: dict[str, dict] = {}
    production = _production_controls()
    for control in controls:
        control_id = control.get("control_id")
        if not control_id or control_id in by_id:
            raise ValueError(f"Missing or duplicate benchmark control ID: {control_id!r}")
        catalog_control = production.get(control_id)
        if catalog_control is None:
            raise ValueError(f"{control_id} is not present in the production ISO 27001:2022 catalog")
        for field in _MATCHED_FIELDS:
            if control.get(field) != catalog_control.get(field):
                raise ValueError(
                    f"{control_id} {field} does not match the production catalog: "
                    f"{control.get(field)!r} != {catalog_control.get(field)!r}"
                )
        parsed_url = urlparse(control.get("source_url", ""))
        if parsed_url.scheme != "https" or not parsed_url.netloc or "example.test" in parsed_url.netloc:
            raise ValueError(f"{control_id} has a placeholder or invalid source URL")
        by_id[control_id] = control

    mappings = gold.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("Benchmark must contain mappings")
    for mapping in mappings:
        control_id = mapping.get("expected_control_id")
        if control_id not in by_id:
            raise ValueError(
                f"Mapping {mapping.get('scanner_finding_id')!r} references unknown benchmark control {control_id!r}"
            )
        if mapping.get("expected_framework") != framework:
            raise ValueError(
                f"Mapping {mapping.get('scanner_finding_id')!r} has an unexpected framework"
            )
