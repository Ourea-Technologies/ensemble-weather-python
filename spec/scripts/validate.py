#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Check the repository: every vector body against the pinned OpenAPI spec, and
every response example in the spec against its own schema.

Run from the repository root: ``python3 scripts/validate.py``.
Needs ``pyyaml`` and ``jsonschema`` (see requirements.txt).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "openapi" / "v1" / "openapi.yaml"

# Which component schema each vector body must satisfy.
BODY_SCHEMA = {
    "forecast-": "ForecastResponse",
    "search": "SearchLocationsResponse",
    "catalog-page-": "PublicCatalogLocationPage",
    "catalog-detail": "PublicCatalogLocationDetail",
    "attribution": "AttributionRegistry",
    "error-": "ErrorResponse",
}
# Deliberately outside the schema: they test forward compatibility (BEHAVIOR.md 1.5).
OUT_OF_SCHEMA = {"forecast-unknown-fields.json", "error-unknown-code.json"}


def validator(spec: dict, schema: dict) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator({**schema, "components": spec["components"]})


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text())
    problems: list[str] = []

    for path in sorted((ROOT / "vectors" / "bodies").glob("*.json")):
        if path.name in OUT_OF_SCHEMA:
            continue
        name = next((s for p, s in BODY_SCHEMA.items() if path.name.startswith(p)), None)
        if name is None:
            problems.append(f"{path.name}: no schema mapped in BODY_SCHEMA")
            continue
        schema = {"$ref": f"#/components/schemas/{name}"}
        for err in validator(spec, schema).iter_errors(json.loads(path.read_text())):
            problems.append(f"vectors/bodies/{path.name}: {err.message} at {'/'.join(map(str, err.absolute_path))}")

    for route, item in spec["paths"].items():
        for method, op in item.items():
            if not isinstance(op, dict):
                continue
            for status, resp in op.get("responses", {}).items():
                if "$ref" in resp:
                    resp = spec["components"]["responses"][resp["$ref"].rsplit("/", 1)[1]]
                content = resp.get("content", {}).get("application/json", {})
                examples = {"example": content["example"]} if "example" in content else {}
                examples |= {k: v.get("value") for k, v in content.get("examples", {}).items()}
                for name, value in examples.items():
                    errs = list(validator(spec, content["schema"]).iter_errors(value))
                    if errs:
                        problems.append(f"spec example {op.get('operationId')} {status} {name}: {len(errs)} errors, first: {errs[0].message}")

    for p in problems:
        print(p, file=sys.stderr)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
