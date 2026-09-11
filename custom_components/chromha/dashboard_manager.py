"""Creates the ChromHA View Assist dashboard, once.

Home Assistant has no public API for a custom integration to register a
storage-mode dashboard. View Assist itself
(github.com/dinki/view_assist_integration, CC BY-NC 4.0 - no code from it is
reused here) works around this by faking a websocket connection and calling
the already-registered `lovelace/dashboards/create` command handler directly
- the same handler a browser's own "Add dashboard" button calls - then
writing view content straight onto the resulting dashboard's storage object.
This module does the same thing, independently written.

Deliberately create-once, not sync-forever: after the dashboard exists, this
never calls `async_save()` again. Home Assistant's dashboard storage has no
concept of "regenerate but keep the parts a person edited by hand," and View
Assist's own solution to that (a diffing engine that reapplies local changes
across reinstalls) is a lot of machinery for what ChromHA needs. Once created,
the dashboard is an ordinary storage dashboard - edit it like any other. To
regenerate it from scratch (e.g. after adding more profiles), delete it under
Settings > Dashboards and restart Home Assistant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.const import CONF_ID, CONF_MODE, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import (
    CONF_ACCENT,
    CONF_PROFILE_NAME,
    CONF_STYLE,
    CONF_VIEW_ASSIST_TARGETS,
    DOMAIN,
    ICON_AUTO_URL_BASE,
)

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL_PATH = "chromha-view-assist"
DASHBOARD_TITLE = "ChromHA View Assist"
DASHBOARD_ICON = "mdi:palette"

_CONF_ICON = "icon"
_CONF_TITLE = "title"
_CONF_URL_PATH = "url_path"
_CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"
_CONF_REQUIRE_ADMIN = "require_admin"


class _FakeConnection:
    """Satisfies just enough of the websocket connection interface to call a
    registered command handler directly, with no real websocket involved."""

    @dataclass
    class _AdminUser:
        is_admin = True

    def __init__(self) -> None:
        self.user = self._AdminUser()
        self.failed = False

    def send_result(self, msg_id: int, item: Any = None) -> None:
        self.failed = False

    def send_error(self, msg_id: int, code: str, message: str) -> None:
        self.failed = True
        _LOGGER.debug("Dashboard creation failed: %s %s", code, message)


def _call_ws_command(hass: HomeAssistant, command: str, msg: dict) -> bool:
    """Invoke a registered websocket command handler directly."""
    registered = hass.data.get("websocket_api", {}).get(command)
    if not registered:
        return False
    handler, schema = registered
    connection = _FakeConnection()
    try:
        handler(hass, connection, msg if schema is False else schema(msg))
    except Exception:  # noqa: BLE001 - best effort, logged below
        _LOGGER.debug("Error calling websocket command %s", command, exc_info=True)
        return False
    return not connection.failed


def _profile_entities(hass: HomeAssistant, entry_id: str) -> tuple[str, str] | None:
    """Look up the real accent/style entity ids for a profile's config entry.

    Reads the entity registry rather than guessing a slug from the profile
    name, since Home Assistant's own slugifying of the device name is not
    something to reimplement by hand.
    """
    registry = er.async_get(hass)
    accent = registry.async_get_entity_id("text", DOMAIN, f"{entry_id}_{CONF_ACCENT}")
    style = registry.async_get_entity_id("select", DOMAIN, f"{entry_id}_{CONF_STYLE}")
    if not accent or not style:
        return None
    return accent, style


def _theme_view(hass: HomeAssistant) -> dict:
    """One view, shared by every profile: accent colour + Solid/Glass."""
    cards: list[dict] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        name = entry.options.get(
            CONF_PROFILE_NAME, entry.data.get(CONF_PROFILE_NAME, entry.title)
        )
        entities = _profile_entities(hass, entry.entry_id)
        if entities is None:
            continue
        accent_entity, style_entity = entities
        cards.append(
            {
                "type": "vertical-stack",
                "cards": [
                    {"type": "markdown", "content": f"## {name}"},
                    {"type": "custom:chromha-card", "entity": accent_entity},
                    {
                        "type": "tile",
                        "entity": style_entity,
                        "name": "Glass style",
                        "features": [{"type": "select-options"}],
                    },
                ],
            }
        )

    if not cards:
        cards.append(
            {
                "type": "markdown",
                "content": (
                    "No ChromHA profiles yet. Add one under Settings > "
                    "Devices & Services > ChromHA, then reload this dashboard."
                ),
            }
        )

    return {
        "type": "panel",
        "title": "Theme",
        "path": "theme",
        "icon": "mdi:palette",
        "cards": [{"type": "vertical-stack", "cards": cards}],
    }


def _weather_variables(satellite_entity: str) -> dict:
    """Shared button-card variables: this satellite's weather entity,
    current condition, and formatted temperature."""
    return {
        "var_satellite": satellite_entity,
        "var_weather_entity": (
            "[[[ try { return hass.states[variables.var_satellite]"
            ".attributes.weather_entity || ''; } catch { return ''; } ]]]"
        ),
        "var_condition": (
            "[[[ try { return variables.var_weather_entity ? "
            "hass.states[variables.var_weather_entity].state : ''; } "
            "catch { return ''; } ]]]"
        ),
        "var_temp": (
            "[[[ try {\n"
            "  if (!variables.var_weather_entity) return '';\n"
            "  const w = hass.states[variables.var_weather_entity];\n"
            "  if (!w || w.attributes.temperature === undefined) return '';\n"
            "  return Math.round(w.attributes.temperature) + "
            "(w.attributes.temperature_unit || '');\n"
            "} catch { return ''; } ]]]"
        ),
    }


def _home_view(slug: str, title: str, satellite_entity: str) -> dict:
    """Clock, current weather, and a way into Controls - one per satellite."""
    card = {
        "type": "custom:button-card",
        "show_name": False,
        "show_icon": False,
        "show_label": False,
        "variables": {
            **_weather_variables(satellite_entity),
            "var_time": (
                "[[[ return new Date().toLocaleTimeString([], "
                "{hour: '2-digit', minute: '2-digit'}) ]]]"
            ),
            "var_date": (
                "[[[ return new Date().toLocaleDateString([], "
                "{weekday: 'long', month: 'long', day: 'numeric'}) ]]]"
            ),
        },
        "styles": {
            "card": [
                {"height": "100vh"},
                {"border-radius": "0px"},
                {"background": "var(--lovelace-background, var(--primary-background-color, black))"},
                {"display": "grid"},
            ],
            "grid": [
                {"grid-template-areas": '"weather status"\n"time time"\n"date date"'},
                {"grid-template-rows": "15vh 55vh 15vh"},
                {"grid-template-columns": "1fr 1fr"},
            ],
            "custom_fields": {
                "time": [
                    {"font-size": "20vh"},
                    {"font-weight": "bold"},
                    {"color": "var(--primary-text-color, white)"},
                    {"justify-self": "center"},
                    {"align-self": "center"},
                ],
                "date": [
                    {"font-size": "5vh"},
                    {"color": "var(--secondary-text-color, silver)"},
                    {"justify-self": "center"},
                    {"align-self": "center"},
                ],
                "weather": [
                    {"justify-self": "start"},
                    {"align-self": "center"},
                    {"padding-left": "3vh"},
                    {"color": "var(--primary-text-color, white)"},
                    {"font-size": "4vh"},
                    {"display": "flex"},
                    {"align-items": "center"},
                ],
            },
        },
        "custom_fields": {
            "time": "[[[ return variables.var_time ]]]",
            "date": "[[[ return variables.var_date ]]]",
            "weather": (
                "[[[ return variables.var_condition ? "
                f'`<img src="{ICON_AUTO_URL_BASE}/${{variables.var_condition}}.svg" '
                'style="height:4vh;margin-right:1vh;">${variables.var_temp}` : \'\' ]]]'
            ),
        },
        "tap_action": {
            "action": "navigate",
            "navigation_path": f"/{DASHBOARD_URL_PATH}/{slug}-weather",
        },
        "hold_action": {
            "action": "navigate",
            "navigation_path": f"/{DASHBOARD_URL_PATH}/{slug}-controls",
        },
    }
    return {
        "type": "panel",
        "title": f"{title} - Home",
        "path": f"{slug}-home",
        "cards": [card],
    }


def _weather_view(slug: str, title: str, satellite_entity: str) -> dict:
    """Current conditions only, themed instead of the stock weather card's
    own fixed colours - deliberately no forecast row, to keep this simple."""
    card = {
        "type": "custom:button-card",
        "show_name": False,
        "show_icon": False,
        "show_label": False,
        "variables": _weather_variables(satellite_entity),
        "styles": {
            "card": [
                {"height": "100vh"},
                {"border-radius": "0px"},
                {"background": "var(--lovelace-background, var(--primary-background-color, black))"},
                {"display": "grid"},
                {"place-items": "center"},
            ],
            "custom_fields": {
                "condition": [
                    {"display": "flex"},
                    {"flex-direction": "column"},
                    {"align-items": "center"},
                    {"color": "var(--primary-text-color, white)"},
                ],
            },
        },
        "custom_fields": {
            "condition": (
                "[[[ if (!variables.var_condition) "
                "return 'No weather entity configured for this satellite'; "
                f'return `<img src="{ICON_AUTO_URL_BASE}/${{variables.var_condition}}.svg" '
                'style="height:30vh;"><div style="font-size:10vh;font-weight:bold;">'
                "${variables.var_temp}</div>"
                "<div style=\"font-size:4vh;text-transform:capitalize;\">"
                "${variables.var_condition.replace(/-/g, ' ')}</div>` ]]]"
            ),
        },
        "tap_action": {
            "action": "navigate",
            "navigation_path": f"/{DASHBOARD_URL_PATH}/{slug}-home",
        },
    }
    return {
        "type": "panel",
        "title": f"{title} - Weather",
        "path": f"{slug}-weather",
        "cards": [card],
    }


def _controls_view(slug: str, title: str, satellite_entity: str) -> dict:
    """Assistant/mic controls, read from the satellite - nothing to edit."""
    card = {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "entities",
                "title": f"{title}'s satellite",
                "entities": [
                    {"entity": satellite_entity, "name": "Satellite"},
                ],
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "button",
                        "name": "Do not disturb",
                        "icon": "mdi:minus-circle",
                        "tap_action": {
                            "action": "call-service",
                            "service": "view_assist.set_state",
                            "service_data": {
                                "entity_id": satellite_entity,
                                "do_not_disturb": True,
                            },
                        },
                    },
                    {
                        "type": "button",
                        "name": "Resume",
                        "icon": "mdi:bell-outline",
                        "tap_action": {
                            "action": "call-service",
                            "service": "view_assist.set_state",
                            "service_data": {
                                "entity_id": satellite_entity,
                                "do_not_disturb": False,
                            },
                        },
                    },
                    {
                        "type": "button",
                        "name": "Theme",
                        "icon": "mdi:palette",
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": f"/{DASHBOARD_URL_PATH}/theme",
                        },
                    },
                    {
                        "type": "button",
                        "name": "Home",
                        "icon": "mdi:home",
                        "tap_action": {
                            "action": "navigate",
                            "navigation_path": f"/{DASHBOARD_URL_PATH}/{slug}-home",
                        },
                    },
                ],
            },
        ],
    }
    return {
        "type": "panel",
        "title": f"{title} - Controls",
        "path": f"{slug}-controls",
        "cards": [card],
    }


def _build_views(hass: HomeAssistant) -> list[dict]:
    views = [_theme_view(hass)]

    for entry in hass.config_entries.async_entries(DOMAIN):
        options = {**entry.data, **entry.options}
        targets = options.get(CONF_VIEW_ASSIST_TARGETS) or []
        if not targets:
            continue

        name = options.get(CONF_PROFILE_NAME, entry.title)
        slug = slugify(name)
        satellite_entity = targets[0]

        views.append(_home_view(slug, name, satellite_entity))
        views.append(_weather_view(slug, name, satellite_entity))
        views.append(_controls_view(slug, name, satellite_entity))

    return views


async def async_ensure_dashboard(hass: HomeAssistant) -> None:
    """Create the ChromHA View Assist dashboard if it does not exist yet.

    Never touches it again afterward - see the module docstring.
    """
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None or not hasattr(lovelace, "dashboards"):
            _LOGGER.debug("Lovelace not ready yet, skipping dashboard setup")
            return

        if DASHBOARD_URL_PATH in lovelace.dashboards:
            return

        created = _call_ws_command(
            hass,
            "lovelace/dashboards/create",
            {
                CONF_ID: 1,
                CONF_TYPE: "lovelace/dashboards/create",
                _CONF_ICON: DASHBOARD_ICON,
                _CONF_TITLE: DASHBOARD_TITLE,
                _CONF_URL_PATH: DASHBOARD_URL_PATH,
                CONF_MODE: "storage",
                _CONF_SHOW_IN_SIDEBAR: True,
                _CONF_REQUIRE_ADMIN: False,
            },
        )
        if not created:
            _LOGGER.warning("Could not create the ChromHA View Assist dashboard")
            return

        store = lovelace.dashboards.get(DASHBOARD_URL_PATH)
        if store is None:
            _LOGGER.warning("ChromHA dashboard was created but is not reachable")
            return

        await store.async_save({"views": _build_views(hass)})
        _LOGGER.info("Created the ChromHA View Assist dashboard")
    except Exception:  # noqa: BLE001 - never break theme rebuilds over this
        _LOGGER.debug("Could not set up the ChromHA View Assist dashboard", exc_info=True)
