"""Creates the ChromHA View Assist dashboard.

Home Assistant has no public API for a custom integration to register a
storage-mode dashboard. View Assist itself
(github.com/dinki/view_assist_integration, CC BY-NC 4.0 - no code from it is
reused here) works around this by faking a websocket connection and calling
the already-registered `lovelace/dashboards/create` command handler directly
- the same handler a browser's own "Add dashboard" button calls. This module
does the same thing, independently written.

The dashboard itself is a colour-patched clone of the user's own View Assist
dashboard: its `button_card_templates` (read from Lovelace storage) and every
view file under `/config/view_assist/views/` (read from disk), both patched
the same way `examples/view-assist/convert.py` patches a user's own copy -
see `dashboard_converter.py`. Nothing from View Assist is bundled or
redistributed; this only ever reads the user's own live installation.

Rewritten on every rebuild, like the theme file - see `renderer.py`'s
generated-file header. Treat it the same way: a hand edit here does not
survive the next accent or profile change.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from homeassistant.const import CONF_ID, CONF_MODE, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ACCENT, CONF_PROFILE_NAME, CONF_STYLE, DOMAIN
from .dashboard_converter import Converter, patch_dashboard_templates

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL_PATH = "chromha-view-assist"
DASHBOARD_TITLE = "ChromHA View Assist"
DASHBOARD_ICON = "mdi:palette"

# View Assist's own dashboard and views directory, both fixed conventions
# used throughout this project's docs and examples.
VIEW_ASSIST_DASHBOARD_URL_PATH = "view-assist"
VIEW_ASSIST_VIEWS_DIR = ("view_assist", "views")

_CONF_ICON = "icon"
_CONF_TITLE = "title"
_CONF_URL_PATH = "url_path"
_CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"
_CONF_REQUIRE_ADMIN = "require_admin"


class _FakeConnection:
    """Satisfies just enough of the websocket connection interface to call a
    registered command handler directly, with no real websocket involved.

    Command handlers decorated with `@websocket_api.async_response` are
    wrapped into a *sync* function that schedules the real work as a
    background task and returns immediately - calling that wrapper is not
    enough on its own. `send_result`/`send_error` are only called once that
    background task actually finishes, so this waits on an event they set,
    rather than trusting the handler call itself to have completed anything.
    """

    @dataclass
    class _AdminUser:
        is_admin = True

    def __init__(self) -> None:
        self.user = self._AdminUser()
        self.failed = False
        self.done = asyncio.Event()

    def send_result(self, msg_id: int, item: Any = None) -> None:
        self.failed = False
        self.done.set()

    def send_error(self, msg_id: int, code: str, message: str) -> None:
        self.failed = True
        _LOGGER.debug("Dashboard creation failed: %s %s", code, message)
        self.done.set()


async def _call_ws_command(hass: HomeAssistant, command: str, msg: dict) -> bool:
    """Invoke a registered websocket command handler directly, and actually
    wait for it to finish before reporting success."""
    registered = hass.data.get("websocket_api", {}).get(command)
    if not registered:
        return False
    handler, schema = registered
    connection = _FakeConnection()
    try:
        handler(hass, connection, msg if schema is False else schema(msg))
        await asyncio.wait_for(connection.done.wait(), timeout=10)
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


def _read_view_files(hass: HomeAssistant) -> list[tuple[str, str]]:
    """Blocking: read every View Assist view file as (name, raw text).

    Runs in the executor - see `_view_assist_views`. Missing directory is not
    an error; it just means View Assist has no views installed yet.
    """
    root = Path(hass.config.path(*VIEW_ASSIST_VIEWS_DIR))
    if not root.is_dir():
        return []

    out: list[tuple[str, str]] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        path = entry / f"{entry.name}.yaml"
        if not path.is_file():
            continue
        try:
            out.append((entry.name, path.read_text(encoding="utf-8")))
        except OSError as err:
            _LOGGER.debug("Could not read %s: %s", path, err)
    return out


def _title_for(name: str, parsed: Any) -> str:
    """Prefer the view's own declared title, falling back to its slug."""
    if isinstance(parsed, dict):
        title = parsed.get("custom_fields", {}).get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return name.replace("_", " ").replace("-", " ").title()


async def _view_assist_views(hass: HomeAssistant) -> list[dict]:
    """Every View Assist view file, colour-patched and wrapped as a view.

    Each file is a bare `custom:button-card` (View Assist supplies its own
    view metadata when loading it) - a dashboard's `views:` list needs it
    wrapped in `type: panel` / `path` / `cards:` instead. See STATUS.md's
    "two nesting depths" section for why that distinction matters.
    """
    files = await hass.async_add_executor_job(_read_view_files, hass)
    views: list[dict] = []
    for name, text in files:
        converted = Converter(text, name).run()
        try:
            parsed = yaml.safe_load(converted)
        except yaml.YAMLError as err:
            _LOGGER.warning("Could not parse View Assist view %r: %s", name, err)
            continue
        if not isinstance(parsed, dict):
            continue
        views.append(
            {
                "type": "panel",
                "title": _title_for(name, parsed),
                "path": name,
                "cards": [parsed],
            }
        )
    return views


async def _dashboard_templates(hass: HomeAssistant, lovelace: Any) -> dict:
    """Colour-patched `button_card_templates` from the user's real View
    Assist dashboard, or {} if it is not set up."""
    store = lovelace.dashboards.get(VIEW_ASSIST_DASHBOARD_URL_PATH)
    if store is None:
        return {}
    try:
        source = await store.async_load(False)
    except Exception:  # noqa: BLE001 - a bad read here should not be fatal
        _LOGGER.debug("Could not read the View Assist dashboard", exc_info=True)
        return {}
    if not isinstance(source, dict):
        return {}
    patched = patch_dashboard_templates(source)
    return patched.get("button_card_templates", {}) or {}


async def _build_dashboard(hass: HomeAssistant, lovelace: Any) -> dict:
    templates = await _dashboard_templates(hass, lovelace)
    views = await _view_assist_views(hass)
    views.append(_theme_view(hass))

    config: dict = {"views": views}
    if templates:
        config["button_card_templates"] = templates
    return config


async def async_ensure_dashboard(hass: HomeAssistant) -> None:
    """Create the ChromHA View Assist dashboard if needed, and (re)write its
    content to match the user's current View Assist setup and profiles.
    """
    try:
        lovelace = hass.data.get("lovelace")
        if lovelace is None or not hasattr(lovelace, "dashboards"):
            _LOGGER.debug("Lovelace not ready yet, skipping dashboard setup")
            return

        if DASHBOARD_URL_PATH not in lovelace.dashboards:
            created = await _call_ws_command(
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

        await store.async_save(await _build_dashboard(hass, lovelace))
    except Exception:  # noqa: BLE001 - never break theme rebuilds over this
        _LOGGER.debug("Could not set up the ChromHA View Assist dashboard", exc_info=True)
