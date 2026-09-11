"""Writes the generated theme file and asks the frontend to reload it."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer

from .const import (
    CONF_ACCENT,
    CONF_CONTRAST,
    CONF_MODE,
    CONF_PROFILE_NAME,
    CONF_VIEW_ASSIST_TARGETS,
    DEFAULT_ACCENT,
    DEFAULTS,
    DOMAIN,
    MODE_DARK,
    MODE_LIGHT,
    MODE_SUN,
    REBUILD_DEBOUNCE,
    SUN_ENTITY,
    THEME_DIR,
    THEME_FILE,
    TRANSPARENT_URL,
)
from .dashboard_manager import async_ensure_dashboard
from .palette import build_palette, hex_to_rgb, rgb_to_hex
from .renderer import render_file

_LOGGER = logging.getLogger(__name__)


def resolve_accent(options: dict) -> str:
    """Normalise the stored accent to a #rrggbb string."""
    raw = options.get(CONF_ACCENT) or DEFAULT_ACCENT
    try:
        return rgb_to_hex(hex_to_rgb(raw))
    except ValueError:
        _LOGGER.warning("Invalid accent colour %r, falling back to default", raw)
        return DEFAULT_ACCENT


class ThemeManager:
    """Owns the generated theme file.

    All config entries share one file. Any entry change triggers a debounced
    rebuild of the whole thing, so profiles can never drift out of sync.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._path = Path(hass.config.path(THEME_DIR)) / THEME_FILE
        self._last_written: str | None = None
        self._debouncer = Debouncer(
            hass,
            _LOGGER,
            cooldown=REBUILD_DEBOUNCE,
            immediate=False,
            function=self._rebuild,
        )

    async def async_request_rebuild(self) -> None:
        await self._debouncer.async_call()

    def is_night(self) -> bool:
        """True when the sun is below the horizon.

        Falls back to daytime if the sun integration is unavailable, so a
        missing sun.sun degrades to day artwork rather than erroring.
        """
        state = self.hass.states.get(SUN_ENTITY)
        return bool(state and state.state == "below_horizon")

    def collect_profiles(self) -> dict[str, dict]:
        """Build the render input from every loaded config entry."""
        night = self.is_night()
        profiles: dict[str, dict] = {}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            options = {**DEFAULTS, **entry.data, **entry.options}
            options["resolved_accent"] = resolve_accent(options)
            options["is_night"] = night
            name = options.get(CONF_PROFILE_NAME) or entry.title
            profiles[f"ChromHA {name}"] = options
        return profiles

    async def _rebuild(self) -> None:
        profiles = self.collect_profiles()

        # Idempotent - only ever does anything the first time. See
        # dashboard_manager's module docstring for why it stops there.
        await async_ensure_dashboard(self.hass)

        if not profiles:
            await self.hass.async_add_executor_job(self._remove)
            self._last_written = None
            await self._reload_frontend()
            return

        text = render_file(profiles)

        # Skip the write and the reload if nothing actually changed. Sliders
        # generate a lot of no-op updates.
        if text == self._last_written:
            return

        try:
            await self.hass.async_add_executor_job(self._write, text)
        except OSError as err:
            _LOGGER.error("Could not write %s: %s", self._path, err)
            return

        self._last_written = text
        _LOGGER.debug("Wrote %d theme profile(s) to %s", len(profiles), self._path)
        await self._reload_frontend()
        await self._push_view_assist(profiles)

    def _write(self, text: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self._path)

    def _remove(self) -> None:
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass

    async def _reload_frontend(self) -> None:
        try:
            await self.hass.services.async_call(
                "frontend", "reload_themes", blocking=True
            )
        except Exception:  # noqa: BLE001 - frontend may not be ready at startup
            _LOGGER.debug("Could not reload themes yet", exc_info=True)

    async def _push_view_assist(self, profiles: dict[str, dict]) -> None:
        """Push each profile's palette onto any View Assist targets it names.

        `view_assist.set_state` merges arbitrary keyword attributes into the
        target sensor's `extra_data`, which is already part of its
        `extra_state_attributes` - so a dashboard can read these straight off
        its own View Assist entity instead of cross-referencing a separate
        ChromHA sensor. Entirely opt-in: a profile with no targets configured
        triggers no service call at all.
        """
        for theme_name, options in profiles.items():
            targets = options.get(CONF_VIEW_ASSIST_TARGETS) or []
            if not targets:
                continue

            mode = options.get(CONF_MODE, DEFAULTS[CONF_MODE])
            if mode == MODE_LIGHT:
                dark = False
            elif mode == MODE_DARK:
                dark = True
            elif mode == MODE_SUN:
                dark = bool(options.get("is_night"))
            else:  # Auto - no client to ask here, so default to dark.
                dark = True

            pal = build_palette(
                options["resolved_accent"],
                dark=dark,
                contrast_boost=options.get(CONF_CONTRAST, DEFAULTS[CONF_CONTRAST]),
            )

            attrs = {f"chromha_{key}": value for key, value in pal.as_dict().items()}
            attrs["chromha_theme_name"] = theme_name
            attrs["chromha_transparent_url"] = TRANSPARENT_URL

            try:
                await self.hass.services.async_call(
                    "view_assist",
                    "set_state",
                    {"entity_id": targets, **attrs},
                    blocking=True,
                )
            except Exception:  # noqa: BLE001 - view_assist may not be installed
                _LOGGER.debug(
                    "Could not push palette to View Assist targets %s", targets,
                    exc_info=True,
                )
