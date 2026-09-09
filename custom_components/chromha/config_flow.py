"""Config and options flow for ChromHA."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    ColorRGBSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_ACCENT,
    CONF_MODE,
    CONF_PROFILE_NAME,
    CONF_STYLE,
    CONF_VIEW_ASSIST_TARGETS,
    DEFAULT_ACCENT,
    DEFAULTS,
    DOMAIN,
    MODES,
    STYLES,
)
from .palette import hex_to_rgb, rgb_to_hex


def _hex_to_list(value: str) -> list[int]:
    """'#11ab93' -> [17, 171, 147], the shape ColorRGBSelector expects."""
    try:
        return [round(c * 255) for c in hex_to_rgb(value)]
    except ValueError:
        return [round(c * 255) for c in hex_to_rgb(DEFAULT_ACCENT)]


def _list_to_hex(value: Any) -> str:
    """[17, 171, 147] -> '#11ab93'. Passes a hex string through unchanged.

    Raises ValueError on anything that does not resolve to a colour, so
    callers can surface `invalid_colour` instead of falling back silently.
    """
    if isinstance(value, str):
        return rgb_to_hex(hex_to_rgb(value))
    r, g, b = value
    return rgb_to_hex((r / 255, g / 255, b / 255))


def _schema(
    defaults: dict, *, include_name: bool, include_view_assist_targets: bool = False
) -> vol.Schema:
    fields: dict = {}

    if include_name:
        fields[
            vol.Required(
                CONF_PROFILE_NAME, default=defaults.get(CONF_PROFILE_NAME, "")
            )
        ] = TextSelector()

    fields[
        vol.Required(
            CONF_ACCENT,
            default=_hex_to_list(defaults.get(CONF_ACCENT, DEFAULT_ACCENT)),
        )
    ] = ColorRGBSelector()

    fields[
        vol.Required(CONF_STYLE, default=defaults.get(CONF_STYLE, DEFAULTS[CONF_STYLE]))
    ] = SelectSelector(
        SelectSelectorConfig(options=STYLES, mode=SelectSelectorMode.LIST)
    )

    fields[
        vol.Required(CONF_MODE, default=defaults.get(CONF_MODE, DEFAULTS[CONF_MODE]))
    ] = SelectSelector(SelectSelectorConfig(options=MODES, mode=SelectSelectorMode.LIST))

    if include_view_assist_targets:
        # Opt-in wiring, not a live entity - there is no sensible entity type
        # for "a list of other integrations' entities to push to", so this
        # only ever lives in config entry options.
        fields[
            vol.Optional(
                CONF_VIEW_ASSIST_TARGETS,
                default=defaults.get(CONF_VIEW_ASSIST_TARGETS, []),
            )
        ] = EntitySelector(
            EntitySelectorConfig(integration="view_assist", domain="sensor", multiple=True)
        )

    return vol.Schema(fields)


class ChromHAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create one theme profile per config entry.

    Multiple entries are expected - one per household member - so there is no
    single-instance guard.
    """

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_PROFILE_NAME].strip()

            if not name:
                errors[CONF_PROFILE_NAME] = "name_required"
            else:
                # Theme names key the generated YAML, so they must be unique.
                for entry in self._async_current_entries():
                    existing = entry.options.get(
                        CONF_PROFILE_NAME, entry.data.get(CONF_PROFILE_NAME)
                    )
                    if existing and existing.lower() == name.lower():
                        errors[CONF_PROFILE_NAME] = "name_exists"
                        break

            if not errors:
                try:
                    accent = _list_to_hex(user_input[CONF_ACCENT])
                except ValueError:
                    errors[CONF_ACCENT] = "invalid_colour"
                else:
                    data = {
                        **DEFAULTS,
                        **user_input,
                        CONF_PROFILE_NAME: name,
                        CONF_ACCENT: accent,
                    }
                    return self.async_create_entry(title=name, data=data)

        defaults = {**DEFAULTS, **(user_input or {})}
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults, include_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> ChromHAOptionsFlow:
        return ChromHAOptionsFlow()


class ChromHAOptionsFlow(OptionsFlow):
    """Re-pick the accent, style and mode after setup.

    All three are also entities, so this is a convenience for the colour
    picker rather than the only way to change them.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                accent = _list_to_hex(user_input[CONF_ACCENT])
            except ValueError:
                errors[CONF_ACCENT] = "invalid_colour"
            else:
                return self.async_create_entry(
                    data={
                        **self.config_entry.options,
                        **user_input,
                        CONF_ACCENT: accent,
                    }
                )

        current = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current, include_name=False, include_view_assist_targets=True
            ),
            errors=errors,
        )
