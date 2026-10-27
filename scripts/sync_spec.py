"""Copy ensemble-weather-spec into ``spec/`` at the ref named in ``spec/VERSION``.

Usage::

    scripts/sync-spec            # rewrite spec/ from the ref in spec/VERSION
    scripts/sync-spec 8467faf    # pin a new ref, then rewrite spec/
    scripts/sync-spec --check    # exit 1 if spec/ differs from that ref

The source repository is ``OUREA_SPEC_REPO`` when set (a URL or a local
path), else https://github.com/Ourea-Technologies/ensemble-weather-spec.
"""

from __future__ import annotations

import argparse
import filecmp
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "spec"
VERSION_FILE = SPEC_DIR / "VERSION"
DEFAULT_REPO = "https://github.com/Ourea-Technologies/ensemble-weather-spec"


def _git(*args: str, cwd: Path | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True).stdout


def _export(repo: str, ref: str, dest: Path) -> None:
    """Write the tree of ``repo`` at ``ref`` into ``dest`` (no ``.git``)."""
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "spec"
        _git("clone", "--quiet", "--no-checkout", repo, str(clone))
        archive = _git("archive", "--format=tar", ref, cwd=clone)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")


def _differences(left: Path, right: Path, rel: str = "") -> list[str]:
    cmp = filecmp.dircmp(left, right, ignore=["VERSION"] if not rel else [])
    out = [f"{rel}{n} (only in spec/)" for n in cmp.left_only]
    out += [f"{rel}{n} (missing from spec/)" for n in cmp.right_only]
    _, mismatch, errors = filecmp.cmpfiles(left, right, cmp.common_files, shallow=False)
    out += [f"{rel}{n} (differs)" for n in mismatch + errors]
    for sub in cmp.common_dirs:
        out += _differences(left / sub, right / sub, f"{rel}{sub}/")
    return out


def main() -> int:
    """Run the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ref", nargs="?", help="spec ref to pin (default: spec/VERSION)")
    parser.add_argument("--check", action="store_true", help="verify only; change nothing")
    args = parser.parse_args()

    ref = args.ref or VERSION_FILE.read_text(encoding="utf-8").strip()
    repo = os.environ.get("OUREA_SPEC_REPO", DEFAULT_REPO)

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "fresh"
        fresh.mkdir()
        _export(repo, ref, fresh)
        if args.check:
            diffs = _differences(SPEC_DIR, fresh)
            if diffs:
                print(f"spec/ does not match {repo} at {ref}:", file=sys.stderr)
                for line in diffs:
                    print(f"  {line}", file=sys.stderr)
                return 1
            print(f"spec/ matches {ref}")
            return 0
        shutil.rmtree(SPEC_DIR, ignore_errors=True)
        shutil.copytree(fresh, SPEC_DIR)
    VERSION_FILE.write_text(f"{ref}\n", encoding="utf-8")
    print(f"spec/ synced to {ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
