#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
"""Copy the Ourea server's public OpenAPI file into openapi/v1/openapi.yaml.

The contract is generated in the server repository (``docs/openapi-public.yaml``,
built from its full spec); this repository only ever holds a byte-for-byte
copy, with the server commit it came from in ``openapi/v1/SOURCE``.

    python3 scripts/sync_openapi.py --source <server repo> [--ref <commit>]
    python3 scripts/sync_openapi.py --source <server repo> --check

``--check`` fails when the copy differs from the server's file at the commit
recorded in ``openapi/v1/SOURCE`` (or ``--ref``), so a hand edit, or a sync
that skipped a server change, is caught. After a sync, re-run
``scripts/build_vectors.py`` and ``scripts/validate.py``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "openapi" / "v1" / "openapi.yaml"
RECORD = ROOT / "openapi" / "v1" / "SOURCE"
SERVER_PATH = "docs/openapi-public.yaml"


def git(source: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(source), *args], check=True, capture_output=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path, help="a clone of the Ourea server repository")
    ap.add_argument("--ref", help="server commit (default: HEAD, or the recorded one with --check)")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    recorded = RECORD.read_text().split()[0] if RECORD.exists() else None
    ref = a.ref or (recorded if a.check and recorded else "HEAD")
    full = git(a.source, "rev-parse", f"{ref}^{{commit}}").decode().strip()
    want = git(a.source, "show", f"{full}:{SERVER_PATH}")

    if a.check:
        if not OUT.exists() or OUT.read_bytes() != want:
            print(f"openapi drift: {OUT.relative_to(ROOT)} differs from {SERVER_PATH} at {full[:8]}; re-run the sync", file=sys.stderr)
            return 1
        print(f"openapi/v1/openapi.yaml matches the server's {SERVER_PATH} at {full[:8]}")
        return 0

    OUT.write_bytes(want)
    RECORD.write_text(f"{full[:8]} {SERVER_PATH}\n")
    print(f"copied {SERVER_PATH} at {full[:8]} ({len(want)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
