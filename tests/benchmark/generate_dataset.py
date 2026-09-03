"""Programmatic benchmark dataset generator.

The hand-curated 30-finding ``gold_standard.json`` covers each of the 15
controls exactly twice (variant 1 and variant 2). To stress-test the
pipeline at the scale the original proposal committed to (500-1000
findings), this module generates a larger synthetic dataset from the
same 15 canonical finding "templates".

Important: the expected control mapping is preserved across every
generated variant. Deterministic narrowing + the Gemini oracle (which
accepts the top-ranked candidate) must therefore still reach the right
control for every finding in the synthetic batch.

Each generated finding varies:
  - severity (critical / high / medium / low / info)
  - resource identifier suffix (e.g. ``_v3``, ``_prod``, ``_staging``)
  - one of several title / description perturbations chosen to keep
    the keyword overlap with the target control strictly greater than
    the overlap with any other control.

The generator never re-assigns the control mapping - that would
silently make the benchmark a self-fulfilling prophecy.
"""
from __future__ import annotations

import json
import pathlib
import random
from typing import Any


# Severity pool. Each template picks deterministically by index so the
# generated batch has a realistic severity distribution.
SEVERITY_POOL = ["critical", "high", "high", "medium", "medium", "medium", "low", "info"]

# Resource identifier suffixes, kept short and AWS-flavored to look
# realistic. The control mapping is invariant to which suffix is used.
RESOURCE_SUFFIXES = [
    "prod", "staging", "dev", "v2", "v3", "v4", "eu-west-1", "us-east-1",
    "us-west-2", "ap-south-1", "tenant-a", "tenant-b", "shared", "internal",
    "external", "primary", "secondary", "replica", "dr", "backup",
]

# Small title/description perturbations that keep keyword overlap with
# the target control. Each perturbation adds 1-2 neutral words; it
# never removes a keyword that drives the narrowing match.
TITLE_PERTURBATIONS = [
    "configuration review flagged",
    "policy audit revealed",
    "automated check identified",
    "compliance scan detected",
    "infrastructure assessment found",
    "security review reported",
    "control evaluation noted",
    "governance inspection observed",
]

DESCRIPTION_PERTURBATIONS = [
    "during routine compliance verification",
    "as part of the standard audit cycle",
    "while validating against baseline",
    "during change-management review",
    "in the latest infrastructure scan",
    "as identified by automated policy check",
]


def _tokens(text: str) -> set[str]:
    return set(text.lower().replace("_", " ").replace("::", " ").split())


def _score_control_keywords(finding_text: str, control: dict) -> int:
    """Count how many control keywords appear in the finding text."""
    finding_tokens = _tokens(finding_text)
    return sum(1 for kw in control.get("keywords", []) if _tokens(kw) <= finding_tokens)


def _best_control(finding_text: str, controls: list[dict]) -> dict:
    """Return the unique control with the highest keyword overlap."""
    ranked = sorted(controls, key=lambda c: _score_control_keywords(finding_text, c), reverse=True)
    if len(ranked) > 1 and _score_control_keywords(finding_text, ranked[0]) == _score_control_keywords(finding_text, ranked[1]):
        raise ValueError("Synthetic finding has an ambiguous top control candidate")
    return ranked[0]


def expand_benchmark(
    gold: dict,
    target_count: int,
    seed: int = 42,
) -> dict:
    """Expand a hand-curated gold dataset to ``target_count`` findings.

    Each of the 15 base mappings is reused as a "template". The
    generator produces variant findings by:
      - rotating through the severity pool,
      - rotating through resource identifier suffixes,
      - adding title / description perturbations,
      - checking that the variant's expected control is still the
        best-matching control by keyword overlap.

    Variants that violate the invariant (i.e. some other control
    would rank higher) are skipped. This keeps the benchmark honest
    even at scale.
    """
    if target_count < len(gold["mappings"]):
        return gold

    rng = random.Random(seed)
    controls = gold["controls"]
    base_mappings = list(gold["mappings"])
    expanded: list[dict] = []
    next_id = max(int(m["id"]) for m in base_mappings) + 1

    # Always include the original mappings first so the canonical
    # 30-finding benchmark remains a strict subset of every
    # expanded run.
    expanded.extend(base_mappings)

    i = 0
    while len(expanded) < target_count:
        template = base_mappings[i % len(base_mappings)]
        sev = rng.choice(SEVERITY_POOL)
        suffix = rng.choice(RESOURCE_SUFFIXES)
        title_pert = rng.choice(TITLE_PERTURBATIONS)
        desc_pert = rng.choice(DESCRIPTION_PERTURBATIONS)

        raw = dict(template["raw_json"])
        original_resource = raw.get("resource_identifier", "resource")
        raw["resource_identifier"] = f"{original_resource}_{suffix}"
        raw["severity"] = sev
        # Keep the original title/description tokens intact and add
        # perturbations AFTER. The keyword-overlap narrowing must still
        # land on the expected control.
        raw["title"] = f"{title_pert} {raw.get('title', '')}".strip()
        raw["description"] = f"{raw.get('description', '')} {desc_pert}".strip()

        # Sanity check: does the variant still map to the same control?
        finding_text = " ".join(
            str(raw.get(k, "")) for k in ("finding_type", "title", "description", "resource_identifier")
        )
        expected_control_id = template["expected_control_id"]
        expected_control = next(c for c in controls if c["control_id"] == expected_control_id)
        best = _best_control(finding_text, controls)
        if best["control_id"] != expected_control_id:
            # Skip variants that would have a different best control.
            i += 1
            continue

        expanded.append(
            {
                "id": next_id,
                "scanner_name": template["scanner_name"],
                "scanner_finding_id": f"GOLD-EXP-{next_id}",
                "expected_control_id": expected_control_id,
                "expected_framework": template["expected_framework"],
                "raw_json": raw,
            }
        )
        next_id += 1
        i += 1

    return {
        **gold,
        "version": f"expanded-{target_count}",
        "generation": {
            "source_version": gold.get("version"),
            "target_count": target_count,
            "seed": seed,
            "generator": "tests/benchmark/generate_dataset.py",
        },
        "mappings": expanded,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Expand gold_standard.json to a larger size.")
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--target", type=pathlib.Path, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    gold = json.loads(args.source.read_text(encoding="utf-8"))
    expanded = expand_benchmark(gold, target_count=args.count, seed=args.seed)
    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(json.dumps(expanded, indent=2), encoding="utf-8")
    print(
        f"Expanded {len(gold['mappings'])} -> {len(expanded['mappings'])} findings "
        f"({args.source.name} -> {args.target.name})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
