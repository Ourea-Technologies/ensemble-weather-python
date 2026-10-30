"""Models, enums and spec drift against the pinned OpenAPI document."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import json_body
from ensemble_weather import AsyncClient, Client, Quantiles, UsageError, models
from ensemble_weather.enums import LocationType, UnitSystem
from ensemble_weather.errors import error_class

SPEC = Path(__file__).resolve().parent.parent / "spec" / "openapi" / "v1" / "openapi.yaml"
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
OPENAPI: dict[str, Any] = yaml.load(SPEC.read_text(encoding="utf-8"), Loader=_LOADER)  # noqa: S506

OUT_OF_SCOPE = {"getMapsToken"}  # BEHAVIOR 3: a web-map credential, not in the 0.x SDKs

# operationId -> the method that exposes it (the vectors runner uses the same names).
EXPOSED = {
    "getLocationForecast": "forecast",
    "getPointForecast": "get_point_forecast",
    "getCurrentConditions": "current",
    "getCurrentByCoordinates": "current_at",
    "getLocationAlerts": "alerts",
    "getAlertsByCoordinates": "alerts_at",
    "getNearbyLocations": "nearby",
    "getNearbyByCoordinates": "nearby_at",
    "searchLocations": "search",
    "getAllLocations": "list_locations",
    "getLocations": "list_locations",
    "listCatalogLocations": "list_catalog_locations",
    "getCatalogLocation": "catalog_location",
    "listCatalogStations": "list_catalog_stations",
    "getCatalogStation": "catalog_station",
    "getAvailableRuns": "runs",
    "getAttribution": "attribution",
}


def _operations() -> dict[str, dict[str, Any]]:
    return {
        op["operationId"]: op
        for item in OPENAPI["paths"].values()
        for method, op in item.items()
        if method == "get"
    }


def test_every_operation_is_exposed() -> None:
    missing = set(_operations()) - OUT_OF_SCOPE - set(EXPOSED)
    assert not missing, f"the spec has operations the SDK does not expose: {missing}"
    for name in EXPOSED.values():
        assert callable(getattr(Client, name))
        assert callable(getattr(AsyncClient, name))


def test_every_schema_has_a_model() -> None:
    # ErrorResponse becomes the exceptions; UnitSystem is an enum; ModelMeans is
    # a list of ModelStats (each with its model id); the three FreezingLevel
    # variants are one FreezingLevel model discriminated by ``kind``.
    # ConditionIcon and NullReason are enums; NextCursor is ``str | None``.
    elsewhere = {
        "ErrorResponse",
        "UnitSystem",
        "ConditionIcon",
        "NullReason",
        "NextCursor",
        "ModelMeans",
        "FreezingLevelBelowSurface",
        "FreezingLevelHeight",
        "FreezingLevelAboveProfile",
    }
    for name in OPENAPI["components"]["schemas"]:
        if name in elsewhere:
            continue
        assert hasattr(models, name), f"no model for schema {name}"
    assert hasattr(models, "ModelStats")


def test_every_error_code_maps_to_a_category() -> None:
    codes = OPENAPI["components"]["schemas"]["ErrorResponse"]["properties"]["error"]["enum"]
    for code in codes:
        assert error_class(400, code) is not None


def _unknown_keys(example: Any, encoded: Any, path: str) -> list[str]:
    out: list[str] = []
    if isinstance(example, dict) and isinstance(encoded, dict):
        for key, value in example.items():
            if value is None:
                continue
            if key not in encoded:
                out.append(f"{path}.{key}")
            else:
                out += _unknown_keys(value, encoded[key], f"{path}.{key}")
    elif isinstance(example, list) and isinstance(encoded, list):
        for i, (a, b) in enumerate(zip(example, encoded, strict=False)):
            out += _unknown_keys(a, b, f"{path}[{i}]")
    return out


def _examples() -> list[Any]:
    cases = []
    for op_id, op in sorted(_operations().items()):
        if op_id in OUT_OF_SCOPE:
            continue
        content = op["responses"].get("200", {}).get("content", {}).get("application/json", {})
        schema = content.get("schema", {}).get("$ref", "").rsplit("/", 1)[-1]
        examples = content.get("examples", {})
        if "example" in content:
            examples = {"example": {"value": content["example"]}}
        for name, example in examples.items():
            cases.append(pytest.param(schema, example["value"], id=f"{op_id}-{name}"))
    return cases


@pytest.mark.parametrize(("schema", "example"), _examples())
def test_openapi_examples_round_trip(schema: str, example: dict[str, Any]) -> None:
    cls = getattr(models, schema)
    model = cls.from_dict(example)
    assert _unknown_keys(example, model.to_dict(), "$") == [], "example fields the model drops"
    assert cls.from_dict(model.to_dict()) == model


@pytest.mark.parametrize(
    "name",
    ["forecast-metric.json", "forecast-prob-mixed.json", "forecast-totals.json"],
)
def test_vector_bodies_round_trip(name: str) -> None:
    data = json_body(name)
    model = models.ForecastResponse.from_dict(data)
    assert _unknown_keys(data, model.to_dict(), "$") == []
    assert models.ForecastResponse.from_dict(model.to_dict()) == model


def test_quantiles_views() -> None:
    q = Quantiles(p10=1.0, p25=2.0, p50=3.0, p75=4.0, p90=5.0)
    assert q.median == 3.0
    assert q.range() == (1.0, 5.0)
    assert q.range(25, 75) == (2.0, 4.0)
    assert Quantiles(p10=1.0).range(10, 90) is None  # absent, not 0
    with pytest.raises(UsageError):
        q.range(5, 95)  # no interpolation


def test_missing_quantile_is_absent_not_zero() -> None:
    q = Quantiles.from_dict({"mean": 1.0})
    assert q.p10 is None
    assert q.mean == 1.0


def test_unknown_enum_keeps_raw_value() -> None:
    value = LocationType("a_type_added_later")
    assert value.is_unknown
    assert value.value == "a_type_added_later"
    assert str(value) == "a_type_added_later"
    assert not LocationType.SKI_AREA.is_unknown
    assert LocationType("ski_area") is LocationType.SKI_AREA
    assert UnitSystem("imperial") is UnitSystem.IMPERIAL


def test_wind_direction_is_left_circular() -> None:
    body = json_body("forecast-metric.json")
    forecast = models.ForecastResponse.from_dict(body)
    wind = forecast.forecast.timeseries[0].ensemble.wind_direction
    assert isinstance(wind, models.CircularStats)
    assert wind.sector_50.from_ == 355.0  # clockwise across north: from > to
    assert wind.sector_50.to == 15.0
    assert wind.sector_90.from_ == 340.0
    assert wind.sector_90.to == 30.0


def test_coordinate_location_has_no_slug() -> None:
    body = json_body("forecast-metric.json")
    body["location"] = {**body["location"], "slug": None, "type": None}
    location = models.ForecastResponse.from_dict(body).location
    assert location.slug is None
    assert location.type is None
    with pytest.raises(UsageError):
        Client(api_key=None).forecast(location)


def test_hourly_dataframe() -> None:
    forecast = models.ForecastResponse.from_dict(json_body("forecast-metric.json"))
    frame = forecast.to_dataframe()
    assert len(frame) == 3
    assert frame["temperature.p50"].tolist() == [-2.0, -1.0, 0.0]
    assert frame.index.name == "valid_time"
    assert forecast.forecast.daily_dataframe().empty
