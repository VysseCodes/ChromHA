"""Palette sensor.

Publishes the resolved hex values as attributes so dashboards and custom
cards can read the theme as data rather than trying to resolve CSS variables.

This is what lets a button-card template do:

    hass.states['sensor.chromha_<profile>_palette'].attributes.text

instead of hoping var(--primary-text-color) inherits correctly through a
shadow DOM boundary.
"""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_CONTRAST,
    CONF_ICON_DAYNIGHT,
    CONF_MODE,
    CONF_STYLE,
    DAYNIGHT_OFF,
    DAYNIGHT_SUN,
    DAYNIGHT_THEME,
    DEFAULTS,
    ICON_AUTO_URL_BASE,
    ICON_URL_BASE,
    MODE_DARK,
    MODE_LIGHT,
    MODE_SUN,
    SUN_ENTITY,
    TRANSPARENT_URL,
    WEATHER_ICON_MAP,
    icon_map,
)
from .const import ICON_DIR
from .entity import ChromHAEntity

_ICON_DIR = Path(__file__).parent / ICON_DIR
from .palette import build_palette
from .theme_manager import resolve_accent


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([ChromHAPaletteSensor(entry)])


class ChromHAPaletteSensor(ChromHAEntity, SensorEntity):
    """Resolved colours for the current settings.

    Not needed for theming - Home Assistant themes are CSS custom properties,
    so `var(--primary-text-color)` works directly in button-card styles and in
    card_mod. This exists for the places CSS cannot reach: Jinja templates
    (automations, notifications, matching an LED strip to the accent) and
    charting cards that pass colours into a JavaScript library rather than
    emitting CSS.

    Diagnostic, so it sits apart from the controls rather than looking like
    one of them.
    """

    _attr_icon = "mdi:palette-swatch-variant"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "palette", "Palette")

    def _options(self) -> dict:
        return {**DEFAULTS, **self._entry.data, **self._entry.options}

    @property
    def _is_night(self) -> bool:
        state = self.hass.states.get(SUN_ENTITY)
        return bool(state and state.state == "below_horizon")

    def _night_icons(self, options: dict, *, dark: bool) -> bool:
        choice = options.get(CONF_ICON_DAYNIGHT, DEFAULTS[CONF_ICON_DAYNIGHT])
        if choice == DAYNIGHT_SUN:
            return self._is_night
        if choice == DAYNIGHT_THEME:
            return dark
        return False

    @property
    def native_value(self) -> str:
        return resolve_accent(self._options())

    @property
    def extra_state_attributes(self) -> dict:
        options = self._options()
        accent = resolve_accent(options)
        mode = options.get(CONF_MODE, DEFAULTS[CONF_MODE])
        boost = options.get(CONF_CONTRAST, DEFAULTS[CONF_CONTRAST])
        night = self._is_night

        attrs: dict = {
            "profile": self._profile_name,
            "theme_name": f"ChromHA {self._profile_name}",
            "mode": mode,
            "style": options.get(CONF_STYLE, DEFAULTS[CONF_STYLE]),
            "icon_base_url": ICON_URL_BASE,
            # Point View Assist's default background here to disable its
            # background images, since it has no option to turn them off.
            "transparent_url": TRANSPARENT_URL,
            "is_night": night,
            "icon_daynight": options.get(
                CONF_ICON_DAYNIGHT, DEFAULTS[CONF_ICON_DAYNIGHT]
            ),
        }

        # In Auto mode both variants are published, since the integration
        # cannot know which one a given client is currently showing.
        if mode == MODE_LIGHT:
            attrs.update(build_palette(accent, dark=False, contrast_boost=boost).as_dict())
            dark_now = False
        elif mode == MODE_DARK:
            attrs.update(build_palette(accent, dark=True, contrast_boost=boost).as_dict())
            dark_now = True
        elif mode == MODE_SUN:
            # Sun mode resolves to exactly one variant, so the top-level
            # values are unambiguous.
            attrs.update(build_palette(accent, dark=night, contrast_boost=boost).as_dict())
            dark_now = night
        else:
            attrs.update(build_palette(accent, dark=True, contrast_boost=boost).as_dict())
            attrs["light"] = build_palette(
                accent, dark=False, contrast_boost=boost
            ).as_dict()
            attrs["dark"] = build_palette(
                accent, dark=True, contrast_boost=boost
            ).as_dict()
            dark_now = True

        # The icon set a card should actually use right now, matching whatever
        # the theme file currently carries.
        use_night = self._night_icons(options, dark=dark_now)
        attrs["weather_icons_are_night"] = use_night

        # Everything bundled, not just the mapped conditions. Home Assistant
        # has no condition for frost, sleet or a tropical storm, but a card
        # can still use the artwork.
        attrs["icon_library"] = {
            path.stem: f"{ICON_URL_BASE}/{path.stem}.svg"
            for path in sorted(_ICON_DIR.glob("*.svg"))
        }

        if options.get(CONF_ICON_DAYNIGHT, DEFAULTS[CONF_ICON_DAYNIGHT]) == DAYNIGHT_SUN:
            # Stable URLs that resolve themselves; a card can use these
            # directly and never needs to re-read this attribute.
            attrs["weather_icons"] = {
                condition: f"{ICON_AUTO_URL_BASE}/{condition}.svg"
                for condition in WEATHER_ICON_MAP
            }
        else:
            attrs["weather_icons"] = {
                condition: f"{ICON_URL_BASE}/{filename}.svg"
                for condition, filename in icon_map(use_night).items()
            }
        return attrs
