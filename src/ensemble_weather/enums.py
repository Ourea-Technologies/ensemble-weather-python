"""Enumerations used by requests and responses.

Every enumeration is *open*: a value the API adds after this SDK was released
parses to an "unknown" member that keeps the raw string, instead of failing.
Check :attr:`OpenEnum.is_unknown` before relying on a member's identity::

    if hit.type.is_unknown:
        print("new location type:", hit.type.value)

All members are also ``str`` instances, so ``hit.type == "ski_area"`` works.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "AdProvider",
    "AdSlotKind",
    "Aggregation",
    "AstronomicalSeason",
    "AttributionSourceKind",
    "ClampedOption",
    "CurrentSource",
    "DailyCondition",
    "DailyConditionIcon",
    "ElevationSource",
    "FreezingLevelKind",
    "GapFlowStatus",
    "HourlyCondition",
    "HourlyConditionIcon",
    "InversionKind",
    "LocationType",
    "MembersView",
    "MoonPhase",
    "NowcastLayer",
    "Op",
    "OpenEnum",
    "PrecipKind",
    "PrecipitationType",
    "ProvenanceVariable",
    "StormOrientation",
    "TemplateSectionKind",
    "TotalVariable",
    "Unit",
    "UnitSystem",
    "Variable",
    "WindStatus",
]


class OpenEnum(str, Enum):
    """A string enumeration that accepts values it does not know.

    An unknown value becomes a pseudo-member named ``UNKNOWN`` whose
    :attr:`value` is the raw string the server sent.
    """

    @classmethod
    def _missing_(cls, value: object) -> OpenEnum | None:
        if not isinstance(value, str):
            return None
        member = str.__new__(cls, value)
        member._name_ = "UNKNOWN"
        member._value_ = value
        return member

    @property
    def is_unknown(self) -> bool:
        """Whether the server sent a value this SDK version does not know."""
        return self._name_ == "UNKNOWN"

    def __str__(self) -> str:
        """Return the wire value."""
        return str(self.value)


class UnitSystem(OpenEnum):
    """The unit system of a request and its response.

    ``metric`` is °C, mm, m/s and m; ``imperial`` is °F, in, mph and ft;
    ``kelvin`` is metric with temperatures in K.
    """

    METRIC = "metric"
    IMPERIAL = "imperial"
    KELVIN = "kelvin"


class Unit(OpenEnum):
    """A unit for a probability threshold given by the caller."""

    MM = "mm"
    IN = "in"
    DEG_C = "degC"
    DEG_F = "degF"
    K = "K"
    M = "m"
    FT = "ft"
    M_PER_S = "m/s"
    MPH = "mph"


class Variable(OpenEnum):
    """A variable a probability term (``prob=``) can ask about."""

    TEMPERATURE = "temperature"
    WIND_SPEED = "wind_speed"
    SNOW_LEVEL = "snow_level"
    PRECIPITATION = "precipitation"
    SNOWFALL = "snowfall"


class TotalVariable(OpenEnum):
    """A variable a window total (``totals=``) can ask about."""

    PRECIPITATION = "precipitation"
    SNOWFALL = "snowfall"


class Op(OpenEnum):
    """The comparison of a probability term."""

    GE = "ge"
    """At least the threshold."""
    LE = "le"
    """At most the threshold."""


class Aggregation(OpenEnum):
    """How a probability term combines the hours of its window.

    ``total`` (the window total) is the only one for precipitation and
    snowfall. ``any`` (at some hour, the default) and ``all`` (at every hour)
    are for the other variables.
    """

    TOTAL = "total"
    ANY = "any"
    ALL = "all"


class LocationType(OpenEnum):
    """The primary type of a named location."""

    AIRPORT = "airport"
    BACKCOUNTRY = "backcountry"
    BEACH_COAST = "beach_coast"
    CAMPGROUND = "campground"
    CITY_TOWN = "city_town"
    CLIMBING_AREA = "climbing_area"
    COASTAL_POINT = "coastal_point"
    EVENT_VENUE = "event_venue"
    FIRE_LOOKOUT = "fire_lookout"
    FISHING_RIVER_ACCESS = "fishing_river_access"
    GOLF_COURSE = "golf_course"
    HOT_SPRING = "hot_spring"
    LAKE = "lake"
    MOUNTAIN_PASS = "mountain_pass"  # noqa: S105 - a place, not a password
    NATIONAL_PARK = "national_park"
    OBSERVATION_STATION = "observation_station"
    OTHER = "other"
    PARK = "park"
    RECREATION_AREA = "recreation_area"
    RESERVOIR_LAKE = "reservoir_lake"
    SCENIC_TOURIST = "scenic_tourist"
    SKI_AREA = "ski_area"
    STATE_PARK = "state_park"
    SUMMIT = "summit"
    TRAILHEAD = "trailhead"
    VOLCANO = "volcano"
    WATERFALL = "waterfall"
    WINE_AGRITOURISM = "wine_agritourism"


class HourlyCondition(OpenEnum):
    """The stable sky/precipitation code of one forecast hour."""

    SUNNY = "sunny"
    MOSTLY_SUNNY = "mostly_sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    MOSTLY_CLOUDY = "mostly_cloudy"
    CLOUDY = "cloudy"
    CLEAR = "clear"
    MOSTLY_CLEAR = "mostly_clear"
    SLIGHT_CHANCE_SHOWERS = "slight_chance_showers"
    CHANCE_SHOWERS = "chance_showers"
    SHOWERS_LIKELY = "showers_likely"
    RAIN = "rain"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    SLIGHT_CHANCE_RAIN_SNOW_MIX = "slight_chance_rain_snow_mix"
    CHANCE_RAIN_SNOW_MIX = "chance_rain_snow_mix"
    RAIN_SNOW_MIX_LIKELY = "rain_snow_mix_likely"
    RAIN_SNOW_MIX = "rain_snow_mix"
    SLIGHT_CHANCE_SNOW = "slight_chance_snow"
    CHANCE_SNOW = "chance_snow"
    SNOW_LIKELY = "snow_likely"
    SNOW = "snow"
    SLIGHT_CHANCE_FREEZING_RAIN = "slight_chance_freezing_rain"
    CHANCE_FREEZING_RAIN = "chance_freezing_rain"
    FREEZING_RAIN_LIKELY = "freezing_rain_likely"
    FREEZING_RAIN = "freezing_rain"


class HourlyConditionIcon(OpenEnum):
    """The icon name of one forecast hour."""

    SUNNY = "sunny"
    MOSTLY_SUNNY = "mostly_sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    MOSTLY_CLOUDY = "mostly_cloudy"
    CLOUDY = "cloudy"
    SUN_CHANCE_SHOWERS = "sun_chance_showers"
    SUN_SHOWERS_LIKELY = "sun_showers_likely"
    CHANCE_SHOWERS = "chance_showers"
    SHOWERS_LIKELY = "showers_likely"
    RAIN = "rain"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    RAIN_SNOW_MIX = "rain_snow_mix"
    SNOW = "snow"
    FREEZING_RAIN = "freezing_rain"
    NIGHT_CLEAR = "night_clear"
    NIGHT_MOSTLY_CLEAR = "night_mostly_clear"
    NIGHT_PARTLY_CLOUDY = "night_partly_cloudy"
    NIGHT_MOSTLY_CLOUDY = "night_mostly_cloudy"
    NIGHT_CLOUDY = "night_cloudy"
    NIGHT_MOON_CHANCE_SHOWERS = "night_moon_chance_showers"
    NIGHT_MOON_SHOWERS_LIKELY = "night_moon_showers_likely"
    NIGHT_CHANCE_SHOWERS = "night_chance_showers"
    NIGHT_SHOWERS_LIKELY = "night_showers_likely"
    NIGHT_RAIN = "night_rain"
    NIGHT_LIGHT_RAIN = "night_light_rain"
    NIGHT_HEAVY_RAIN = "night_heavy_rain"
    NIGHT_RAIN_SNOW_MIX = "night_rain_snow_mix"
    NIGHT_SNOW = "night_snow"
    NIGHT_FREEZING_RAIN = "night_freezing_rain"


class DailyCondition(OpenEnum):
    """The stable sky/precipitation code of one forecast day."""

    SUNNY = "sunny"
    MOSTLY_SUNNY = "mostly_sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    MOSTLY_CLOUDY = "mostly_cloudy"
    CLOUDY = "cloudy"
    SLIGHT_CHANCE_SHOWERS = "slight_chance_showers"
    CHANCE_SHOWERS = "chance_showers"
    CHANCE_RAIN = "chance_rain"
    SHOWERS_LIKELY = "showers_likely"
    RAIN_LIKELY = "rain_likely"
    SHOWERS = "showers"
    RAIN = "rain"
    SLIGHT_CHANCE_RAIN_SNOW_MIX = "slight_chance_rain_snow_mix"
    CHANCE_RAIN_SNOW_MIX = "chance_rain_snow_mix"
    RAIN_SNOW_MIX_LIKELY = "rain_snow_mix_likely"
    RAIN_SNOW_MIX = "rain_snow_mix"
    SLIGHT_CHANCE_SNOW = "slight_chance_snow"
    CHANCE_SNOW = "chance_snow"
    SNOW_LIKELY = "snow_likely"
    SNOW = "snow"


class DailyConditionIcon(OpenEnum):
    """The icon name of one forecast day."""

    SUNNY = "sunny"
    MOSTLY_SUNNY = "mostly_sunny"
    PARTLY_CLOUDY = "partly_cloudy"
    MOSTLY_CLOUDY = "mostly_cloudy"
    CLOUDY = "cloudy"
    SUN_CHANCE_SHOWERS = "sun_chance_showers"
    SUN_SHOWERS_LIKELY = "sun_showers_likely"
    SUN_SHOWERS = "sun_showers"
    CHANCE_SHOWERS = "chance_showers"
    CHANCE_RAIN = "chance_rain"
    SHOWERS_LIKELY = "showers_likely"
    RAIN_LIKELY = "rain_likely"
    SHOWERS = "showers"
    RAIN = "rain"
    RAIN_SNOW_MIX = "rain_snow_mix"
    SNOW = "snow"


class PrecipitationType(OpenEnum):
    """A precipitation type."""

    RAIN = "rain"
    SNOW = "snow"
    RAIN_SNOW_MIX = "rain_snow_mix"
    FREEZING_RAIN = "freezing_rain"


class PrecipKind(OpenEnum):
    """What a day's precipitation display shows."""

    NONE = "none"
    RAIN = "rain"
    SNOW = "snow"
    RAIN_SNOW_MIX = "rain_snow_mix"
    FREEZING_RAIN = "freezing_rain"


class InversionKind(OpenEnum):
    """The kind of a temperature inversion."""

    SURFACE_SHALLOW = "surface_shallow"
    COLD_POOL = "cold_pool"
    ELEVATED = "elevated"


class FreezingLevelKind(OpenEnum):
    """Where the freezing level is."""

    BELOW_SURFACE = "below_surface"
    HEIGHT = "height"
    ABOVE_PROFILE = "above_profile"


class MembersView(OpenEnum):
    """Which member variables a forecast carries (Free: plume; Pro: full)."""

    PLUME = "plume"
    FULL = "full"


class NowcastLayer(OpenEnum):
    """A nowcast input that was unavailable for a response."""

    OBSERVATION = "observation"
    RADAR = "radar"
    CLOUD = "cloud"
    NEAREST_SENSORS = "nearest_sensors"


class ClampedOption(OpenEnum):
    """A request option the server clamped to the caller's tier."""

    MAX_HOURS = "max_hours"
    MAX_DAYS = "max_days"


class CurrentSource(OpenEnum):
    """Where current conditions came from."""

    NOWCAST = "nowcast"
    MODEL = "model"


class ElevationSource(OpenEnum):
    """Where a point forecast's elevation came from."""

    REQUEST = "request"
    DEM_3DEP_10M = "dem_3dep_10m"


class MoonPhase(OpenEnum):
    """The moon's phase on a date."""

    NEW_MOON = "new_moon"
    WAXING_CRESCENT = "waxing_crescent"
    FIRST_QUARTER = "first_quarter"
    WAXING_GIBBOUS = "waxing_gibbous"
    FULL_MOON = "full_moon"
    WANING_GIBBOUS = "waning_gibbous"
    LAST_QUARTER = "last_quarter"
    WANING_CRESCENT = "waning_crescent"


class AstronomicalSeason(OpenEnum):
    """The astronomical season of a date."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class StormOrientation(OpenEnum):
    """How snow density changes through a storm."""

    RIGHT_SIDE_UP = "right_side_up"
    UPSIDE_DOWN = "upside_down"
    MIXED = "mixed"


class WindStatus(OpenEnum):
    """A day's wind category."""

    CALM = "calm"
    LIGHT = "light"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"
    EXTREME = "extreme"


class GapFlowStatus(OpenEnum):
    """The strength of a gap-flow wind event."""

    NONE = "none"
    MODERATE = "moderate"
    STRONG = "strong"
    EXTREME = "extreme"


class AttributionSourceKind(OpenEnum):
    """The kind of a data source in the attribution registry."""

    MODEL = "model"
    PEER = "peer"
    OBSERVATION = "observation"
    ALERTS = "alerts"
    CLIMATOLOGY = "climatology"
    TERRAIN = "terrain"
    PLACES = "places"
    BASEMAP = "basemap"


class ProvenanceVariable(OpenEnum):
    """A variable named in an hour's provenance tags."""

    TEMPERATURE = "temperature"
    DEWPOINT = "dewpoint"
    PRECIPITATION = "precipitation"
    SNOWFALL = "snowfall"
    WIND_SPEED = "wind_speed"
    WIND_GUST = "wind_gust"
    SNOW_LEVEL = "snow_level"
    CLOUD_COVER = "cloud_cover"


class TemplateSectionKind(OpenEnum):
    """The kind of one section of a catalog page template."""

    WEATHER_PANEL = "weather_panel"
    CONTENT_SLOT = "content_slot"
    AD_SLOT = "ad_slot"
    MEDIA = "media"


class AdSlotKind(OpenEnum):
    """Whether a catalog ad slot is a house or a third-party placement."""

    HOUSE = "house"
    THIRD_PARTY = "third_party"


class AdProvider(OpenEnum):
    """The provider of a third-party ad placement."""

    ADSENSE = "adsense"
    GAM = "gam"
    CUSTOM = "custom"
