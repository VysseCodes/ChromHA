#!/usr/bin/env python3
"""Convert a View Assist dashboard to a ChromHA-themed one.

Works on your own dashboard rather than a reconstruction, so it matches
whatever View Assist version you are running and cannot introduce typos in
the parts it does not touch. Re-runnable: safe after a View Assist update.

View Assist keeps its views in separate files, so there are two halves:

    # 1. The dashboard: templates only, plus a placeholder view.
    #    VA dashboard > three-dot menu > Raw configuration editor,
    #    select all, paste into dashboard.yaml
    python3 chromha_dashboard.py dashboard.yaml --report
    python3 chromha_dashboard.py dashboard.yaml -o dashboard-chromha.yaml

    # 2. The views themselves.
    python3 chromha_dashboard.py --views-dir /config/view_assist/views --report
    python3 chromha_dashboard.py --views-dir /config/view_assist/views --in-place

Paste the dashboard output back into the raw configuration editor, then run
`view_assist.load_view` for each view you changed - editing the file does not
update the running dashboard on its own.

What it changes
---------------
  * body_template text colour   -> var(--primary-text-color)
  * icon_template icon colour   -> var(--primary-color)
  * variable_template           -> defines background_color, which activates
                                   body_template's existing fallback branch
  * per-view hardcoded card background colours -> theme background
  * hardcoded background images in info / infopic / list -> removed
  * url(undefined) in calendar / camera -> removed
  * card_mod literal colours    -> CSS variables

What it leaves alone
--------------------
  * The Alert view. Bright blue with black text is deliberate; it is meant to
    interrupt rather than blend in. Pass --theme-alert to convert it anyway.
  * Anything it does not recognise. Unmatched patterns are reported, not
    guessed at.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

TEXT = "var(--primary-text-color, white)"
ACCENT = "var(--primary-color, white)"
BG = "var(--primary-background-color, black)"
PAGE_BG = "var(--lovelace-background, var(--primary-background-color, black))"

# Literal card backgrounds, per view. Values are matched exactly as they
# appear in the stock dashboard, quotes and all.
CARD_BACKGROUNDS = [
    "'#24292c'",  # alarm
    "'#1c1c1c'",  # sports, thermostat
    "'#000000'",  # intent
    "'#00000'",   # webpage - five digits, never valid, never did anything
    "black;",     # music
    "black",      # locate
]

ALERT_BLUE = ["'#059bf1'", "#059bf1", "#059bf9"]

# A bare mapping key: an identifier, then a colon, and nothing else.
# Deliberately strict, so nothing inside a block scalar can match.
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:$")


class Converter:
    """Applies the edits appropriate to whichever kind of file this is.

    Two shapes exist. The dashboard holds `button_card_templates` and a
    placeholder view. Each view file is a bare button-card - no `views:`
    wrapper - because View Assist injects it into the dashboard itself.
    """

    def __init__(self, text: str, name: str, *, theme_alert: bool) -> None:
        self.text = text
        self.name = name
        self.theme_alert = theme_alert
        self.is_dashboard = "button_card_templates:" in text
        self.is_alert = name.startswith("alert")
        self.changes: list[str] = []
        self.skipped: list[str] = []

    def _sub(self, pattern: str, repl: str, label: str, *, flags=0) -> None:
        new, count = re.subn(pattern, repl, self.text, flags=flags)
        if count:
            self.text = new
            self.changes.append(f"{label} ({count})")
        else:
            self.skipped.append(label)

    # --- dashboard only ---------------------------------------------------

    def body_text_colour(self) -> None:
        """The default text colour every view inherits."""
        self._sub(
            r"(\n\s+- )color: white(?=\n)",
            rf"\g<1>color: {TEXT}",
            "body_template text colour",
        )

    def icon_colour(self) -> None:
        self._sub(
            r"(\n\s+- display: grid\n\s+- )color: white",
            rf"\g<1>color: {ACCENT}",
            "icon_template icon colour",
        )

    def background_variable(self) -> None:
        """Define background_color, activating body_template's fallback branch.

        The branch exists upstream but nothing ever set the variable, so it
        emitted "no-repeat undefined" and the browser dropped the declaration.
        """
        if re.search(r"^      background_color:", self.text, re.M):
            self.skipped.append("background_color already defined")
            return
        self._sub(
            r"(  variable_template:\n    variables:\n)",
            rf"\g<1>      background_color: {PAGE_BG}\n",
            "background_color variable",
        )

    # --- view files -------------------------------------------------------

    def card_backgrounds(self) -> None:
        """Literal card background colours, however they happen to be quoted.

        Deliberately does not touch rgba() values - those are the semi
        transparent shader overlays, which are doing a different job.
        """
        if self.is_alert and not self.theme_alert:
            self.skipped.append("alert view colours (use --theme-alert)")
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
        """Remove the hardcoded background image, variable and use together.

        These have to go as a pair. Removing only the variable leaves the
        style pointing at url(undefined), which the browser discards - worse
        than leaving it alone.

        Only touches `variables.background`, which is either the bundled PNG
        or a reference nothing defines. `var_background` is View Assist's own
        rotating background and is left working.
        """
        before = self.text

        # The style line that consumes it, plus its background-size partner.
        # Upstream writes this three ways - single quoted, double quoted, and
        # as a >- block scalar - so all three have to be matched.
        self.text = re.sub(
            r"\n[ \t]+- background:[ \t]*(?:[>|]-[ \t]*\n)?[ \t]*"
            r"[\"']?\[\[\[ return `center / cover no-repeat"
            # Only `variables.background` - the hardcoded PNG, or an
            # undefined reference. `var_background` is View Assist's own
            # rotating background feature and is left alone.
            r"[^\]]*?\$\{variables\.background\}[^\]]*?\]\]\][\"']?"
            r"(\n[ \t]+- background-size: cover)?",
            "",
            self.text,
            flags=re.S,
        )
        # The variable naming the PNG.
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
        """Remaining hardcoded white text and icons inside views."""
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

    # --- shared -----------------------------------------------------------

    def prune_empty(self) -> None:
        """Drop mapping keys left with no children.

        Removing a background image can empty the `styles: card:` block that
        held it. That is valid YAML - the value is null - but button-card does
        not expect it. Repeats, since removing one key can empty its parent.

        Only plain identifier keys are considered. This pass is line based
        and cannot see when it is inside a block scalar, where a line such
        as `"camera camera"` :` also ends in a colon and would otherwise be
        deleted - silently corrupting the JavaScript it belongs to.
        """
        total = 0
        while True:
            lines = self.text.split("\n")
            keep: list[str] = []
            removed = 0
            for i, line in enumerate(lines):
                stripped = line.strip()
                if KEY_RE.match(stripped):
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
        if self.is_dashboard:
            # Icons first: the body-text pattern also matches the icon rule's
            # `color: white`, so running it first would claim both.
            self.icon_colour()
            self.body_text_colour()
            self.background_variable()
        else:
            self.card_backgrounds()
            self.background_images()
            self.literal_whites()
        self.prune_empty()
        return self.text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "inputs", nargs="*", help="YAML files to convert"
    )
    ap.add_argument(
        "--views-dir",
        help="a View Assist views directory; converts every <name>/<name>.yaml",
    )
    ap.add_argument("-o", "--output", help="write here instead of stdout")
    ap.add_argument(
        "--all-yaml",
        action="store_true",
        help="with --views-dir, also convert alternate views (advancedcamera, "
        "list-nocheckbox, community contributions)",
    )
    ap.add_argument(
        "--in-place",
        action="store_true",
        help="rewrite each input, keeping a .bak copy",
    )
    ap.add_argument("--report", action="store_true", help="summarise, write nothing")
    ap.add_argument(
        "--theme-alert",
        action="store_true",
        help="also convert the Alert view, which is deliberately loud",
    )
    args = ap.parse_args()

    targets: list[pathlib.Path] = [pathlib.Path(p) for p in args.inputs]

    if args.views_dir:
        root = pathlib.Path(args.views_dir)
        if not root.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            return 1
        if args.all_yaml:
            # Alternates like advancedcamera.yaml and list-nocheckbox.yaml
            # live alongside the main view and would otherwise be skipped.
            targets += sorted(
                p for p in root.rglob("*.yaml") if not p.name.endswith(".bak")
            )
        else:
            # View Assist stores each view as <views>/<name>/<name>.yaml.
            found = sorted(d / f"{d.name}.yaml" for d in root.iterdir() if d.is_dir())
            targets += [p for p in found if p.is_file()]

    if not targets:
        print("nothing to do: pass files or --views-dir", file=sys.stderr)
        return 1

    if args.output and len(targets) > 1:
        print("-o only works with a single input; use --in-place", file=sys.stderr)
        return 1

    failures = 0
    for src in targets:
        if not src.is_file():
            print(f"not found: {src}", file=sys.stderr)
            failures += 1
            continue

        conv = Converter(
            src.read_text(encoding="utf-8"), src.name, theme_alert=args.theme_alert
        )
        result = conv.run()

        header = src.name if len(targets) > 1 else str(src)
        print(f"\n=== {header}", file=sys.stderr)
        if conv.changes:
            for line in conv.changes:
                print(f"  + {line}", file=sys.stderr)
        else:
            print("  (nothing to change)", file=sys.stderr)
        if conv.skipped and len(targets) == 1:
            print("  not found:", file=sys.stderr)
            for line in conv.skipped:
                print(f"    - {line}", file=sys.stderr)

        try:
            import yaml

            yaml.safe_load(result)
        except ImportError:
            pass
        except Exception as err:  # noqa: BLE001
            print(f"  !! output is NOT valid YAML: {err}", file=sys.stderr)
            failures += 1
            continue

        if args.report or not conv.changes:
            continue

        if args.in_place:
            # Keep a copy. These files are the only record of any hand edits.
            src.with_suffix(src.suffix + ".bak").write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8"
            )
            src.write_text(result, encoding="utf-8")
            print(f"  wrote {src} (backup at {src.name}.bak)", file=sys.stderr)
        elif args.output:
            pathlib.Path(args.output).write_text(result, encoding="utf-8")
            print(f"  wrote {args.output}", file=sys.stderr)
        else:
            print(result)

    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
