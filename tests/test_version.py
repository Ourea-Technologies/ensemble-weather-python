"""The package imports and reports its version."""

import re

import ensemble_weather


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", ensemble_weather.__version__)
