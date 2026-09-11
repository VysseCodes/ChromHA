# Changelog

All notable changes to ChromHA are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **Weather view icons were cut off.** The stock Weather view's message area
  had two invalid CSS declarations - `height: 100vdh` (not a real unit) and
  `padding: -10%` (negative padding is invalid) - both silently dropped by
  the browser, leaving the area to size around whatever content fit instead
  of filling its grid row. That is what clipped the weather-forecast card's
  large icons (present on the real View Assist dashboard too). Corrected to
  `height: 100%` and `padding: 0` on the generated dashboard only.


- **A leftover `chromhasettings.yaml` example view cloned in as a second,
  broken "Theme" tab.** Before the automatic dashboard existed,
  `examples/view-assist/README.md` told people to copy
  `chromhaclock`/`chromhacontrols`/`chromhasettings` into
  `/config/view_assist/views/` by hand. Anyone who did still has them there,
  and the dashboard clone had no way to know they were obsolete - so
  `chromhasettings.yaml`'s hardcoded example profile (`chromha_ryan`) cloned
  in as a tab confusingly also titled "Theme", pointing the ChromHA card at
  an accent entity that only exists if your profile happens to be named
  "ryan". These three legacy views are now skipped during cloning (with a
  warning naming the file to delete), and the README no longer recommends
  installing them.

### Changed

- **The ChromHA View Assist dashboard is now a clone of your actual View
  Assist dashboard, not a hand-built substitute.** 0.4.0/0.4.1 generated
  original Home/Weather/Controls views from scratch, gated behind a **Push
  to View Assist** target per profile - a mismatch with what people actually
  wanted, which was their real View Assist dashboard with ChromHA's colours.

  It now reads every view file under `/config/view_assist/views/` plus the
  dashboard's shared `button_card_templates`, and colour-patches both with
  the same substitutions `examples/view-assist/convert.py` already applies
  to a user's own copy - just automatic, and into a separate dashboard
  instead of View Assist's own. A **Theme** view (colour wheel + Solid/Glass
  per profile) is appended. The dashboard is now rewritten on every rebuild
  (previously created once and left alone) so it tracks your real View
  Assist setup as it changes - the same "generated, don't hand-edit"
  contract the theme file already has. New module: `dashboard_converter.py`.

### Fixed

- **The colour picker didn't always stick.** `chromha-card.js` fired an
  unserialised `text.set_value` call on every colour change. Two picks made
  in quick succession (a very ordinary way to use a colour wheel) raced:
  nothing guaranteed the *first* call's write couldn't land *after* the
  second's, silently reverting to an earlier colour depending on timing.
  Commits are now serialised - never more than one write in flight, always
  sending only the latest value - which makes that reordering impossible
  rather than just unlikely.

- **A stale, wrapped View Assist view file produced an invalid card.** If a
  file under `/config/view_assist/views/` was copied in the wrapped
  `views:`/`cards:` shape instead of a bare button-card - as ChromHA's own
  example views did before 0.4.0 - the dashboard clone wrapped it a second
  time, producing a card with no `type` (a broken card in the UI). Detected
  and unwrapped automatically now, with a warning logged pointing at which
  file is still in the wrong shape on disk.

- **Dynamic view titles rendered as literal garbage.** A Lovelace view's own
  `title:` is never template-evaluated - only a button-card's own config is
  - so a view whose title was a `[[[ ... ]]]` expression (View Assist's
  stock `locate` and `music` views both do this) showed that literal text in
  the tab bar instead of anything useful. The generated dashboard now
  rejects a templated title and falls back to a plain name derived from the
  view's own filename - a ChromHA-dashboard-only substitution; the source
  view file is untouched.

- **Weather's background was still blue after conversion.** Not a simple
  `background-color:` line - View Assist's stock Weather view sets it via
  `card_mod` CSS text (`ha-card { background: #059bf9 }`), which the colour
  patcher's structural patterns never looked inside. That exact colour is
  the Alert view's own deliberate blue, reused here seemingly by copy-paste;
  now patched to the theme background everywhere except the Alert view
  itself, in both `dashboard_converter.py` and `examples/view-assist/convert.py`.

## [0.4.1] - 2026-09-11

### Fixed

- **The ChromHA View Assist dashboard came out blank.** Home Assistant wraps
  the `lovelace/dashboards/create` command handler into a fire-and-forget
  background task, so calling it and immediately checking the result (as
  `dashboard_manager.py` did) always reported success before the dashboard
  was actually created - a plain missing `await` compounded it, since the
  call was async but never awaited at its call site either. `_call_ws_command`
  now waits on an event the handler's own completion sets, instead of racing
  ahead of it.

  Since ChromHA never rewrites the dashboard once it exists (see its module
  docstring), this only fixes *new* creations - an already-blank dashboard
  needs deleting under Settings > Dashboards so it gets rebuilt correctly.

## [0.4.0] - 2026-09-11

### Fixed

- **White text on a white background.** `text-on-state-color` - a text
  colour, meant for text drawn on a coloured state badge/pill - was set to
  `var(--ha-card-background)`. In Light mode that background is white (or
  near-white), so anything using this token rendered as invisible white text
  on the page's own light surfaces.

### Added

- **The ChromHA View Assist dashboard.** A storage-mode dashboard ChromHA
  creates for itself the first time it loads (`Settings > Dashboards >
  ChromHA View Assist`), separate from View Assist's own dashboard - so
  ChromHA no longer needs to touch View Assist's tracked views or
  `button_card_templates`, which was causing View Assist to prompt for an
  update on every one of its cards.

  One shared **Theme** view lists every ChromHA profile's colour wheel and a
  Solid/Glass toggle. For each profile with a **Push to View Assist** target
  configured, it also adds a Home, Weather, and Controls view wired to that
  profile's satellite. The Weather view is an original, theme-coloured
  replacement for the stock weather card's fixed background - deliberately
  current-conditions only, no forecast row.

  Created once and never rewritten afterward: after the first creation it is
  an ordinary dashboard, safe to customise by hand. To regenerate it from
  scratch (e.g. after adding more profiles), delete it under Settings >
  Dashboards and restart Home Assistant. Requires the `lovelace` component,
  now a manifest dependency.

  This relies on Home Assistant's internal dashboard-storage mechanism
  (there is no public API for a custom integration to register a storage
  dashboard) - the same approach View Assist itself uses for its own
  dashboard, independently implemented here. Not exercised against a real
  Home Assistant instance yet.

## [0.3.0] - 2026-08-29

### Changed

- **Text is now a tint of the accent rather than white or black.** Previously
  the palette mixed 4% of the accent into a near-neutral, which read as plain
  white on dark themes and plain black on light ones - the accent was visible
  only on icons and controls.

  Text now takes the accent's own hue at a fixed OKLab lightness with chroma
  pulled back: L 0.93 on dark themes, L 0.28 on light. A rose accent gives
  warm off-white text, a blue accent gives cool. Contrast enforcement is
  unchanged, and all ten former presets still clear 4.5:1 in both modes -
  measured 11.3:1 to 13.2:1 dark, 13.8:1 to 15.2:1 light.

  Achromatic accents (pure white, pure black, grey) degrade to neutral text,
  which is correct - there is no hue to tint with.

- **The accent is now a colour picker.** The ten-preset dropdown is gone. With
  the whole palette derived from one colour, presets were a shorter list than
  the spectrum rather than a feature - so the config flow uses Home
  Assistant's native RGB picker instead.
- `select.<profile>_accent` has been **removed**. The accent is now available
  three ways:
  - **A bundled Lovelace card**, `custom:chromha-card`. Home Assistant has no
    colour-picker entity platform, and dressing the accent up as a light gave
    it a meaningless on/off state, so ChromHA ships its own card instead. It
    registers itself as a frontend module - there is no Lovelace resource to
    add. Add it from the card picker, or:

    ```yaml
    type: custom:chromha-card
    entity: text.chromha_ryan_accent
    ```

    With no `entity` it finds the accent entity itself. It also previews the
    derived palette underneath, reading the palette sensor on the same device.
  - `text.<profile>_accent` - the hex value, for automations.
  - Settings > Devices & Services > ChromHA > **Configure** - the same picker
    in a dialog.
- Added an **options flow**: Settings > Devices & Services > ChromHA >
  Configure re-opens the picker along with style and mode.

- `sensor.<profile>_palette` is now a **diagnostic** entity, so it sits apart
  from the controls. It is not needed for theming - CSS variables cover that -
  but it remains the only way to reach the resolved colours from a Jinja
  template or a charting card that passes colours into JavaScript.

- `examples/view-assist/convert.py` no longer prunes lines inside block
  scalars. The pass that removes emptied mapping keys is line based, and
  a line such as `"camera camera"` :` inside a JavaScript template also
  ends in a colon - so it was deleted, silently corrupting the View
  Assist camera view. Only plain identifier keys are considered now.

### Added

- Config entry migration from version 1. Preset names resolve to their hex
  values and the separate `accent_hex` key is folded in, so existing profiles
  keep their colour with nothing to redo.
- **Push to View Assist**, an optional per-profile setting in the options
  flow. Pick one or more View Assist devices and every rebuild calls
  `view_assist.set_state` on them, landing `chromha_accent`,
  `chromha_background`, `chromha_surface`, `chromha_text`,
  `chromha_theme_name` and `chromha_transparent_url` directly on that
  device's own View Assist sensor - readable from a dashboard with no
  separate ChromHA sensor to name. Off by default; a missing `view_assist`
  integration is handled the same way a not-yet-ready frontend is.

### Fixed

- `light.py` implemented an accent-as-a-light entity that was never in
  `PLATFORMS` and so never loaded. Removed - the bundled `chromha-card.js`
  and `text.<profile>_accent` already cover that UI.
- Invalid accent input now surfaces `invalid_colour` in both the setup and
  options flow, instead of silently substituting the default accent.
- `examples/view-assist/views/*` are now the bare `custom:button-card` shape
  View Assist's own `views/<name>/<name>.yaml` expects, rather than wrapped
  in `views:` / `type: panel` / `cards:` - a mismatch between what the files
  actually contained and what their own header comments and the example
  README told you to do with them.

### Upgrading from 0.2.x

Profiles migrate automatically on load. `select.<profile>_accent` and
`text.<profile>_custom_accent` will linger as unavailable entities - Home
Assistant keeps removed entities rather than deleting them. Remove them from
any dashboard and delete them under Settings > Devices & Services > Entities.

## [0.2.1] - 2026-08-29

### Added

- **Transparent background asset**, bundled and served at
  `/chromha_static/transparent.png`, with the URL also published on the
  palette sensor as `transparent_url`.

  View Assist paints its own background image over every view and has no
  option to turn that off - the choices are a default image, a local sequence,
  a local random pick, or an Unsplash download. Pointing its **Default
  Background** at this file disables backgrounds across every view at once:
  the image still loads, it just shows nothing, and the ChromHA background
  shows through.

  `body_template` sets the background with the CSS `background:` shorthand,
  which resets `background-color` to transparent - so a transparent image
  leaves the button-card with no background at all and the Lovelace background
  behind it takes over.

- Static assets are served from a new `/chromha_static` prefix, registered
  alongside the icon path.

## [0.2.0] - 2026-08-29

### Fixed

- **Weather icons tiled instead of scaling.** The upstream SVGs ship with a
  fixed `width`/`height` and no `viewBox`, which gives them an intrinsic size
  as a CSS background - so Home Assistant repeated them across any element
  larger than 56x48. All bundled icons are now normalised by
  `scripts/normalize_icons.py`: fixed dimensions removed, `viewBox` and
  `preserveAspectRatio` added, nothing else touched. The script is idempotent
  and should be re-run after pulling new icons from upstream.

### Changed

- **Precipitation intensity now follows the condition** rather than being a
  user-selectable option, and `select.*_icon_intensity` has been removed. The
  `-1`/`-2`/`-3` suffixes encode rainfall intensity, so choosing one as a
  style preference showed a drizzle icon during a downpour. Home Assistant
  already makes the distinction it can: `rainy` uses `rainy-2`, `pouring` uses
  `rainy-3`.

  Live intensity cannot be driven from the theme. A theme supplies one URL per
  condition and the weather card reuses it for forecast rows, so an icon
  tracking current rainfall would put today's rate on next week's forecast.
  For live intensity, read `icon_library` from the palette sensor in a card
  template - that is per-element and does not affect forecasts.

### Upgrading from 0.1.0

`select.<profile>_icon_intensity` no longer exists. Home Assistant keeps
showing removed entities as unavailable rather than deleting them, so after
updating, remove it from any dashboard that references it and delete it from
Settings > Devices & Services > Entities. Nothing else carries over.

- The sun-aware endpoint drops its tier path segment: it is now
  `/chromha_icons_auto/<condition>.svg`.

### Added

- `examples/view-assist/` - three views written for ChromHA (clock, theme
  settings, device controls) laid out to copy straight into
  `/config/view_assist/views/`, plus `convert.py`, which converts View
  Assist's own dashboard and views to follow the theme.

  View Assist's views are deliberately **not** redistributed here: View Assist
  is CC BY-NC 4.0 and ChromHA is MIT, so bundling converted copies would put
  incompatible terms on one repository. Converting in place also stays correct
  across View Assist updates.
- `CHANGELOG.md` and `RELEASE.md`.

## [0.1.0] - 2026-08-29

First public release.

### Added

- **Entity-driven themes.** One config entry per profile, each generating its
  own Home Assistant theme. Add one per household member; themes are global
  but selection is per-user, so everyone tunes their own independently.
- **OKLab palette derivation.** The entire palette is computed from a single
  accent colour. Neutrals are tinted toward the accent so the interface reads
  as one scheme rather than an accent floating on grey.
- **Contrast enforcement.** Text is checked against the card background and
  adjusted until it clears 4.5:1, or 7:1 with the high-contrast switch.
- **Four modes.** Light and Dark pin the theme; Auto emits both variants and
  lets the client choose; Sun follows sunrise and sunset, which is what makes
  a wall tablet with no OS-level dark mode actually change.
- **Glass style.** Backdrops are gradients generated from the accent colour,
  so there are no image files and the backdrop follows the selected colour.
- **Animated weather icons**, bundled and served from the integration.
- **Sun-aware icon endpoint**, resolving day or night artwork when the request
  arrives, so following the sun needs no theme rewrite and no frontend reload.
- **Palette sensor.** Publishes every resolved colour as an attribute, plus
  `icon_library` listing every bundled icon URL - for work that happens in
  JavaScript, where CSS variables cannot reach.

### Known gaps

- HA 2026.5 moved switches and checkboxes to a new component library and
  dropped several `switch-*` variables. Current names are set but not fully
  verified.
- Nothing from the 2025.8 semantic colour scale (`--md-sys-color-*`) is set,
  so some newer components fall back to Home Assistant defaults.
- `exceptional` maps to `severe-thunderstorm`, which is approximate.

[0.4.1]: https://github.com/vyssecodes/chromha/releases/tag/v0.4.1
[0.4.0]: https://github.com/vyssecodes/chromha/releases/tag/v0.4.0
[0.3.0]: https://github.com/vyssecodes/chromha/releases/tag/v0.3.0
[0.2.1]: https://github.com/vyssecodes/chromha/releases/tag/v0.2.1
[0.2.0]: https://github.com/vyssecodes/chromha/releases/tag/v0.2.0
[0.1.0]: https://github.com/vyssecodes/chromha/releases/tag/v0.1.0
