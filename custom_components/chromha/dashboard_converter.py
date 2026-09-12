"""Colour-patches View Assist's own dashboard and views.

Two halves, because View Assist keeps them in two different places:

  * The dashboard itself (`button_card_templates` + a placeholder view) is
    Home Assistant Lovelace storage - a parsed structure, not text, by the
    time `dashboard_manager.py` can reach it. `patch_dashboard_templates`
    walks that structure directly.
  * Each view is its own YAML file under `/config/view_assist/views/`. Those
    are read from disk as raw text, so the same regex-based `Converter`
    already proven in `examples/view-assist/convert.py` applies unchanged -
    this is a parallel copy of that class for use at runtime from inside the
    integration, since the example script is meant to be run standalone and
    cannot import from here. Keep the two in sync by hand.

Operates only on the user's own View Assist installation, read live from
their instance - nothing from View Assist is bundled or redistributed here.
See `examples/view-assist/README.md` for why (CC BY-NC 4.0 vs. MIT).
"""

from __future__ import annotations

import re
from typing import Any

TEXT = "var(--primary-text-color, white)"
ACCENT = "var(--primary-color, white)"
BG = "var(--primary-background-color, black)"
PAGE_BG = "var(--lovelace-background, var(--primary-background-color, black))"

# Literal card backgrounds, per view - as plain values, since a parsed
# structure has already stripped whatever quoting the source YAML used.
CARD_BACKGROUNDS = {"#24292c", "#1c1c1c", "#000000", "#00000", "black"}

# The Alert view's own deliberate blue - kept there, but a card_mod CSS
# string is free-text CSS button-card's own styles: block cannot reach, so
# a view that reuses this exact colour outside the Alert view (the stock
# Weather view's card_mod does) needs a separate pass to catch it.
ALERT_BLUE = ("#059bf1", "#059bf9")


# --- Dashboard templates (dict-based) --------------------------------------


def _walk(node: Any):
    """Yield every dict found anywhere in a nested structure."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def patch_dashboard_templates(config: dict) -> dict:
    """Colour-patch `button_card_templates` in a loaded dashboard config.

    Mirrors `Converter.body_text_colour`, `.icon_colour` and
    `.background_variable`, but structurally: button-card's
    `styles: {card: [{prop: value}, ...]}` shape parses into single-key
    dicts, so each patch just replaces a value in place rather than
    matching source text.
    """
    templates = config.get("button_card_templates")
    if not isinstance(templates, dict):
        return config

    body = templates.get("body_template", {})
    for entry in _walk(body.get("styles", {}).get("card", [])):
        if entry.get("color") == "white":
            entry["color"] = TEXT

    icon = templates.get("icon_template", {})
    for entry in _walk(icon.get("styles", {}).get("icon", [])):
        if entry.get("color") == "white":
            entry["color"] = ACCENT

    variables = templates.setdefault("variable_template", {}).setdefault(
        "variables", {}
    )
    variables.setdefault("background_color", PAGE_BG)

    return config


# --- Individual view files (text-based) -------------------------------------
#
# A parallel copy of examples/view-assist/convert.py's Converter class - see
# the module docstring for why this cannot just import that file instead.

# A bare mapping key: an identifier, then a colon, and nothing else.
# Deliberately strict, so nothing inside a block scalar can match.
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:$")


class Converter:
    """Applies the view-file edits appropriate to whichever kind of file
    this is - see `examples/view-assist/convert.py` for the full explanation
    of each pattern; this is kept in sync with it by hand."""

    def __init__(self, text: str, name: str, *, theme_alert: bool = False) -> None:
        self.text = text
        self.name = name
        self.theme_alert = theme_alert
        self.is_alert = name.startswith("alert")
        self.changes: list[str] = []
        self.skipped: list[str] = []

    def _sub(self, pattern: str, repl: str, label: str, *, flags: int = 0) -> None:
        new, count = re.subn(pattern, repl, self.text, flags=flags)
        if count:
            self.text = new
            self.changes.append(f"{label} ({count})")
        else:
            self.skipped.append(label)

    def card_backgrounds(self) -> None:
        if self.is_alert and not self.theme_alert:
            self.skipped.append("alert view colours (deliberately left alone)")
            return
        self._sub(
            r'- background-color: (["\']?)(#[0-9a-fA-F]{3,6}|black)\1;?(?=\s*\n)',
            f"- background-color: {BG}",
            "literal card background colour",
        )
        self._sub(
            r'- background: (["\']?)black\1;?(?=\s*\n)',
            f"- background: {BG}",
            "literal card background",
        )

    def background_images(self) -> None:
        before = self.text
        self.text = re.sub(
            r"\n[ \t]+- background:[ \t]*(?:[>|]-[ \t]*\n)?[ \t]*"
            r"[\"']?\[\[\[ return `center / cover no-repeat"
            r"[^\]]*?\$\{variables\.background\}[^\]]*?\]\]\][\"']?"
            r"(\n[ \t]+- background-size: cover)?",
            "",
            self.text,
            flags=re.S,
        )
        self.text = re.sub(
            r"\n\s+background: /view_assist/dashboard/\S+\.png",
            "",
            self.text,
        )
        if self.text != before:
            self.changes.append("hardcoded background image")
        else:
            self.skipped.append("hardcoded background image")

    def literal_whites(self) -> None:
        self._sub(
            r"(\n\s+- )color: white(?=\n)",
            rf"\g<1>color: {TEXT}",
            "literal white colour",
        )
        self._sub(
            r"color: white !important;",
            f"color: {TEXT} !important;",
            "card_mod white colour",
        )
        self._sub(
            r"(ha-check-list-item \{\n\s+)color: white;",
            r"\g<1>color: var(--primary-text-color);",
            "list view todo colour",
        )

    def js_hardcoded_white(self) -> None:
        """A hardcoded `return "white"` inside a button-card JS template -
        as the stock Clock view's `var_font_color`/`var_font_color_night`
        do - never reaches a plain `- color: white` YAML line, so text or
        icon colour driven by it never follows the theme. `red` and
        `transparent` (the same views' night-mode indicators) are
        deliberate and left alone - only the literal white return value is
        replaced.
        """
        if self.is_alert:
            self.skipped.append("view's own colours (deliberate)")
            return
        # \s+ rather than a literal space: a YAML folded block scalar (>-)
        # wraps its source across physical lines, so "return" and the
        # quoted value can have a newline (plus indentation) between them
        # in the raw text even though YAML folds it back into one line.
        self._sub(r'return\s+"white"', f'return "{TEXT}"', 'JS return "white"')
        self._sub(r"return\s+'white'", f"return '{TEXT}'", "JS return 'white'")

    def alert_blue_elsewhere(self) -> None:
        """The Alert view's blue is deliberate and already skipped in
        `card_backgrounds()` via `is_alert`. Anywhere else that reuses the
        exact same colour - typically a card_mod CSS string reaching into a
        third-party card button-card's own `styles:` block cannot touch,
        such as the stock Weather view's `ha-card { background: #059bf9 }` -
        is not the Alert view and should not stay blue.
        """
        if self.is_alert:
            self.skipped.append("view's own blue (deliberate)")
            return
        for hexcode in ALERT_BLUE:
            self._sub(re.escape(hexcode), BG, f"alert-blue literal ({hexcode})")

    def prune_empty(self) -> None:
        """Drop mapping keys left with no children - see convert.py's
        docstring for the block-scalar corruption this guards against."""
        total = 0
        while True:
            lines = self.text.split("\n")
            keep: list[str] = []
            removed = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if _KEY_RE.match(stripped):
                    indent = len(line) - len(line.lstrip())
                    nxt = next((n for n in lines[i + 1 :] if n.strip()), None)
                    if nxt is None or (len(nxt) - len(nxt.lstrip())) <= indent:
                        removed += 1
                        continue
                keep.append(line)
            self.text = "\n".join(keep)
            total += removed
            if not removed:
                break
        if total:
            self.changes.append(f"pruned empty keys ({total})")

    def run(self) -> str:
        self.card_backgrounds()
        self.background_images()
        self.literal_whites()
        self.js_hardcoded_white()
        self.alert_blue_elsewhere()
        self.prune_empty()
        return self.text
