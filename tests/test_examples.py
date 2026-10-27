"""Every example runs, against the local stub server (never the real API)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from stub_server import StubServer

if TYPE_CHECKING:
    from collections.abc import Iterator

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))
REQUIRED = {
    "quickstart",
    "point_forecast",
    "chance_of_snow",
    "storm_total",
    "search_and_catalog",
    "current_and_alerts",
    "error_handling",
    "units",
}


@pytest.fixture(scope="module")
def stub() -> Iterator[StubServer]:
    with StubServer() as server:
        yield server


def _run(example: Path, stub: StubServer, api_key: str | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OUREA_")}
    env["OUREA_BASE_URL"] = stub.url
    env["PYTHONIOENCODING"] = "utf-8"
    if api_key is not None:
        env["OUREA_API_KEY"] = api_key
    return subprocess.run(  # noqa: S603 - our own example files
        [sys.executable, str(example)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_every_required_example_exists() -> None:
    assert {p.stem for p in EXAMPLES} >= REQUIRED


@pytest.mark.parametrize("example", EXAMPLES, ids=[p.stem for p in EXAMPLES])
@pytest.mark.parametrize("api_key", [None, "ow_ci_example_key"], ids=["anonymous", "keyed"])
def test_example_runs(example: Path, api_key: str | None, stub: StubServer) -> None:
    done = _run(example, stub, api_key)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip(), "an example prints what it shows"
    assert "ow_ci_example_key" not in done.stdout + done.stderr


def test_examples_have_a_header_docstring() -> None:
    for example in EXAMPLES:
        assert example.read_text(encoding="utf-8").startswith('"""'), example.name


def test_readme_quickstart_is_the_example() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", readme, flags=re.DOTALL)
    quickstart = (ROOT / "examples" / "quickstart.py").read_text(encoding="utf-8")
    assert blocks, "README has no Python code"
    code = quickstart.split('"""', 2)[2].lstrip("\n")
    assert blocks[0] == code, "the README quickstart must be examples/quickstart.py verbatim"


def test_point_forecast_without_key_says_so(stub: StubServer) -> None:
    done = _run(ROOT / "examples" / "point_forecast.py", stub, None)
    assert done.returncode == 0
    assert "OUREA_API_KEY" in done.stdout
