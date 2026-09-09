"""Constants for ChromHA."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "chromha"

# Where the generated theme file is written, relative to the config dir.
THEME_DIR: Final = "themes"
THEME_FILE: Final = "chromha.yaml"

# URL prefix the bundled weather icons are served from.
ICON_URL_BASE: Final = "/chromha_icons"
# Separate prefix so the static route below cannot swallow it. Requests here
# are resolved against sun.sun at request time by icon_view.py.
ICON_AUTO_URL_BASE: Final = "/chromha_icons_auto"

# Static assets bundled with the integration.
STATIC_URL_BASE: Final = "/chromha_static"
STATIC_DIR: Final = "static"

# A 1x1 fully transparent PNG.
#
# View Assist has no "no background" option - the choices are a default image,
# a local sequence, a local random pick, or an Unsplash download. Pointing its
# default background at this file is the way to turn it off: the image still
# loads, it just shows nothing, and the theme background shows through.
TRANSPARENT_URL: Final = f"{STATIC_URL_BASE}/transparent.png"

# The bundled Lovelace card, auto-registered so there is no resource for the
# user to add by hand.
CARD_URL: Final = f"{STATIC_URL_BASE}/chromha-card.js"
ICON_DIR: Final = "icons"

# --- Option keys -----------------------------------------------------------

CONF_PROFILE_NAME: Final = "profile_name"
# Stores a hex string like "#11ab93". Named `accent` since 0.3.0; the old
# preset-name + accent_hex pair is migrated on load.
CONF_ACCENT: Final = "accent"
CONF_STYLE: Final = "style"
CONF_MODE: Final = "mode"
CONF_RADIUS: Final = "corner_radius"
CONF_OPACITY: Final = "card_opacity"
CONF_ICON_SET: Final = "icon_set"
CONF_ICON_DAYNIGHT: Final = "icon_daynight"
CONF_CONTRAST: Final = "contrast_boost"
# View Assist sensor entity ids to push this profile's palette to via
# view_assist.set_state, on every rebuild. Empty (the default) means "do
# nothing" - this is opt-in wiring, not a live entity, so it only exists in
# the options flow.
CONF_VIEW_ASSIST_TARGETS: Final = "view_assist_targets"

# --- Choices ---------------------------------------------------------------

DEFAULT_ACCENT: Final = "#11ab93"

# Only used to migrate config entries created before 0.3.0, when the accent
# was chosen from a dropdown instead of a colour picker.
LEGACY_ACCENT_PRESETS: Final[dict[str, str]] = {
    "Rose": "#aa3151",
    "Purple": "#904eab",
    "Blue": "#009bb5",
    "Aqua": "#11ab93",
    "Green": "#6ca049",
    "Yellow": "#d6a245",
    "Orange": "#d25f36",
    "Coral": "#fa6e5e",
    "Pink": "#f36f92",
    "Slate": "#7d8794",
}

STYLE_SOLID: Final = "Solid"
STYLE_GLASS: Final = "Glass"
STYLES: Final = [STYLE_SOLID, STYLE_GLASS]

MODE_LIGHT: Final = "Light"
MODE_DARK: Final = "Dark"
MODE_AUTO: Final = "Auto"
# Sun mode ignores the client's light/dark setting and follows sun.sun
# instead. Wall tablets have no OS-level dark mode to inherit, so this is
# usually what you want on one.
MODE_SUN: Final = "Sun"
MODES: Final = [MODE_LIGHT, MODE_DARK, MODE_AUTO, MODE_SUN]

ICON_SET_ANIMATED: Final = "Animated"
ICON_SET_NONE: Final = "None"
ICON_SETS: Final = [ICON_SET_ANIMATED, ICON_SET_NONE]

# How the night icon variants get chosen.
#
#   Day only     - always the day artwork, the simplest option
#   Follow theme - night icons in the dark variant, day icons in the light one.
#                  Costs nothing: both variants already exist in the same file
#                  and the client picks. Assumes dark mode means night, which
#                  is usually but not always true.
#   Follow sun   - night icons whenever sun.sun is below the horizon. Accurate
#                  regardless of theme, at the cost of a theme rewrite and a
#                  frontend reload at sunrise and sunset.
DAYNIGHT_OFF: Final = "Day only"
DAYNIGHT_THEME: Final = "Follow theme"
DAYNIGHT_SUN: Final = "Follow sun"
DAYNIGHT_MODES: Final = [DAYNIGHT_OFF, DAYNIGHT_THEME, DAYNIGHT_SUN]


# --- Defaults --------------------------------------------------------------

DEFAULTS: Final[dict] = {
    CONF_ACCENT: DEFAULT_ACCENT,
    CONF_STYLE: STYLE_SOLID,
    CONF_MODE: MODE_AUTO,
    CONF_RADIUS: 12,
    CONF_OPACITY: 15,
    CONF_ICON_SET: ICON_SET_ANIMATED,
    CONF_ICON_DAYNIGHT: DAYNIGHT_THEME,
    CONF_CONTRAST: False,
    CONF_VIEW_ASSIST_TARGETS: [],
}

# --- Weather icons ---------------------------------------------------------
#
# 51 icons ship with the integration. Home Assistant only defines 19 weather
# conditions, so the surplus is used three ways:
#
#   * day/night pairs, for every condition that has one
#   * intensity tiers, driven by the condition itself
#   * the rest published on the palette sensor as `icon_library`, so cards can
#     use them directly for things HA has no condition for (frost, sleet,
#     tropical storm)
#
# `{dn}` is substituted with -day or -night.
#
# The -1/-2/-3 suffixes in the icon set are precipitation intensity, so they
# are chosen by the condition, not by the user. Home Assistant already draws
# the distinction it can: `rainy` versus `pouring`. A theme supplies one URL
# per condition and the weather card reuses it for forecast rows, so an icon
# that tracked current intensity would put today's rain rate on next week's
# forecast.

_ICON_TEMPLATES: Final[dict[str, str]] = {
    "sunny": "clear{dn}",
    "clear-night": "clear-night",
    "partlycloudy": "cloudy-1{dn}",
    "cloudy": "cloudy",
    "fog": "fog{dn}",
    "hazy": "haze{dn}",
    "rainy": "rainy-2{dn}",
    "pouring": "rainy-3{dn}",
    "snowy": "snowy-2{dn}",
    "snowy-rainy": "rain-and-snow-mix",
    "hail": "hail",
    "lightning": "thunderstorms",
    "lightning-rainy": "scattered-thunderstorms{dn}",
    "windy": "wind",
    "windy-variant": "wind",
    "dust": "dust",
    "tornado": "tornado",
    "hurricane": "hurricane",
    "exceptional": "severe-thunderstorm",
}

# Files with no -day/-night counterpart. Substituting {dn} on these would
# produce names that do not exist.
_NO_DAYNIGHT: Final[frozenset[str]] = frozenset(
    {"cloudy", "rain-and-snow-mix", "hail", "thunderstorms", "wind", "dust",
     "tornado", "hurricane", "severe-thunderstorm"}
)

SUN_ENTITY: Final = "sun.sun"


def icon_map(night: bool = False) -> dict[str, str]:
    """Condition to bundled filename for a given sun state."""
    out: dict[str, str] = {}
    for condition, template in _ICON_TEMPLATES.items():
        # clear-night is already a night icon; never append a suffix to it.
        if template in _NO_DAYNIGHT or template == "clear-night":
            out[condition] = template
            continue
        out[condition] = template.format(dn="-night" if night else "-day")
    return out


# Every condition Home Assistant can report, in mapping order.
WEATHER_ICON_MAP: Final[dict[str, str]] = icon_map()


# Debounce window for theme rebuilds, in seconds. A number slider fires once
# per tick, so this keeps us from rewriting the file dozens of times.
REBUILD_DEBOUNCE: Final = 1.5
