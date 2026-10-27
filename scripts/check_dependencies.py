"""Fail if a runtime dependency or extra lacks a justification in CONTRIBUTING.md.

It reads the installed package's metadata, which uv builds from
``pyproject.toml`` on ``uv sync``. The "Runtime dependencies" and
"Optional extras" lists in CONTRIBUTING.md name each one as a bullet
starting with the package in backticks.
"""

from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_BULLET = re.compile(r"^- `([A-Za-z0-9][A-Za-z0-9._-]*)`")


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _declared() -> set[str]:
    """Every runtime requirement and extra of the installed package (``uv sync``)."""
    names = set()
    for spec in metadata.requires("ensemble-weather") or []:
        match = _NAME.match(spec)
        if match:
            names.add(_normalise(match.group(1)))
    return names


def _justified() -> set[str]:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    section = text.split("## Dependencies", 1)[-1].split("\n## ", 1)[0]
    return {_normalise(m.group(1)) for line in section.splitlines() if (m := _BULLET.match(line))}


def main() -> int:
    """Compare the manifest with the justification list."""
    missing = sorted(_declared() - _justified())
    if missing:
        print("Runtime dependencies without a justification in CONTRIBUTING.md:")
        for name in missing:
            print(f"  - {name}")
        return 1
    print(f"All {len(_declared())} runtime dependencies/extras are justified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
