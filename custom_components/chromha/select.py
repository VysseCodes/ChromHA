"""Select entities: accent, style, mode, icon set."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ICON_DAYNIGHT,
    CONF_ICON_SET,
    CONF_MODE,
    CONF_STYLE,
    DAYNIGHT_MODES,
    ICON_SETS,
    MODES,
    STYLES,
)
from .entity import ChromHAEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            ChromHASelect(entry, CONF_STYLE, "Style", STYLES, "mdi:layers-outline"),
            ChromHASelect(entry, CONF_MODE, "Mode", MODES, "mdi:theme-light-dark"),
            ChromHASelect(entry, CONF_ICON_SET, "Weather icons", ICON_SETS,
                         "mdi:weather-partly-cloudy"),
            ChromHASelect(entry, CONF_ICON_DAYNIGHT, "Icon day/night",
                         DAYNIGHT_MODES, "mdi:weather-night-partly-cloudy"),
        ]
    )


class ChromHASelect(ChromHAEntity, SelectEntity):
    """A single option chosen from a fixed list."""

    def __init__(self, entry, key, name, options, icon) -> None:
        super().__init__(entry, key, name)
        self._attr_options = list(options)
        self._attr_icon = icon

    @property
    def current_option(self) -> str | None:
        value = self._value()
        return value if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        await self._async_store(option)
