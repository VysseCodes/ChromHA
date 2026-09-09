# ChromHA — where things stand

Written as a handoff. Read this first if you are picking the project back up,
or if you are an AI assistant working in this repository.

---

## What ChromHA is

A Home Assistant custom integration that generates themes from a single accent
colour. One config entry per person; each becomes its own theme, so a
household shares one dashboard while each user gets their own palette.

The whole palette is derived in OKLab from that one colour — backgrounds,
surfaces, text, dividers — with contrast enforced against the card background.
It also bundles 51 animated weather icons and serves them itself.

**Repo:** github.com/VysseCodes/chromha
**Manifest version:** 0.3.0
**Released so far:** 0.1.0, 0.2.0, 0.2.1
**0.3.0 is written but NOT tagged.**

---

## Layout

```
custom_components/chromha/
  __init__.py        setup, static paths, sun listener, card registration
  config_flow.py     config + options flow, RGB colour picker
  const.py           options, icon mapping, weather condition templates
  entity.py          base entity; state lives in config entry options
  palette.py         OKLab maths, contrast, palette derivation
  renderer.py        turns palettes into theme YAML
  theme_manager.py   debounced write of /config/themes/chromha.yaml
  icon_view.py       /chromha_icons_auto/<condition>.svg, sun-aware
  number|select|switch|text|sensor.py    the entities
  icons/             51 animated SVGs
  static/            chromha-card.js, transparent.png
examples/view-assist/  views and a converter for View Assist
scripts/normalize_icons.py
```

## How it works

Home Assistant has no API to register a theme at runtime, so ChromHA writes
`/config/themes/chromha.yaml` and calls `frontend.reload_themes`. Writes are
debounced 1.5s and skipped when the rendered text is unchanged.

Settings live in each config entry's **options**, which gives persistence and
one update listener to trigger rebuilds. Entities read and write there.

Weather icons are served two ways: `/chromha_icons/<file>.svg` for fixed
artwork, and `/chromha_icons_auto/<condition>.svg` which picks day or night
from `sun.sun` *at request time* — so following the sun needs no theme rewrite.

---

## Entities, per profile

| Entity | Purpose |
|---|---|
| `text.*_accent` | Accent colour as hex |
| `select.*_style` | Solid / Glass |
| `select.*_mode` | Light / Dark / Auto / Sun |
| `select.*_weather_icons` | Animated / None |
| `select.*_icon_daynight` | Day only / Follow theme / Follow sun |
| `number.*_corner_radius` | 0–32px |
| `number.*_card_opacity` | Glass only |
| `switch.*_high_contrast_text` | AA → AAA target |
| `sensor.*_palette` | Resolved colours, diagnostic |

The colour picker is in **Configure** on the config entry, and in the bundled
`custom:chromha-card`.

---

## Open items

### 1. Tag 0.3.0
Written, not released. `RELEASE.md` has the steps. Changelog section is ready.

### 2. Glass style never verified
Reported as not showing its gradient background. The generated YAML was
confirmed correct — `lovelace-background` with the gradient is present and
parses — so the problem is downstream: either the theme is not reaching the
page, the browser has not repainted, or a View Assist panel view is covering
it. Never resolved.

Note there is no theme variable for `backdrop-filter`, so Glass is translucent
cards plus a tinted gradient, not frosted blur. It may simply be subtler than
expected. The mix weights are in `_glass_background()` in `renderer.py`.

### 3. Integration surface is lightly tested
The palette maths and renderer are well covered. These have had little or no
real exercise: `async_register_static_paths`, the options flow, the v1→v2
config entry migration, `add_extra_js_url` card registration, and the icon
view. Icons and themes are confirmed working on hardware.

### 4. `examples/view-assist/views/` is in the wrong shape
Those three files are wrapped in `views:` / `type: panel` / `cards:`, which
suits pasting into a dashboard. View Assist's own views directory wants a
**bare button-card** with no wrapper. See the warning below.

---

## The thing that caused the most trouble

**Two nesting depths, not interchangeable.**

- `/config/view_assist/views/<name>/<name>.yaml` → a bare button-card starting
  at `type: custom:button-card`, column 0. View Assist supplies the view
  metadata itself.
- A dashboard's raw config → the same card wrapped in `views:` /
  `type: panel` / `cards:`, and therefore indented **two levels deeper**.

Converting between them by eye is where most breakage came from. A block
landing at the wrong depth fails silently: it parses fine, it just stops being
read. The symptom was a tiny weather temperature, caused by a `styles:` block
sitting as a sibling of `card:` instead of inside it.

**Two related lessons:**

- Never edit lines *inside* a YAML block scalar. A pass that deleted
  lines looking like empty keys destroyed a line of JavaScript
  (`"camera camera"` :`) inside the View Assist camera view, because it ends
  in a colon. Replace whole blocks instead.
- Never move a block scalar's opening line without reindenting its body.

---

## View Assist integration

Requires **two lines** in the View Assist dashboard's `button_card_templates`
that no view file can reach:

```yaml
# body_template -> styles -> card
- color: white   ->   - color: var(--primary-text-color, white)

# icon_template -> styles -> icon
- color: white   ->   - color: var(--primary-color, white)
```

Do the icon one first — both are the same string, and a replace-all gets it
wrong.

Everything else is in the views. `examples/view-assist/convert.py` converts
View Assist's own dashboard and views; it is idempotent and reports what it
does not recognise rather than guessing.

**Do not commit converted View Assist views to this repo.** View Assist is
CC BY-NC 4.0 and ChromHA is MIT — incompatible. The converter runs on the
user's own copies. See `examples/view-assist/README.md`.

Also: View Assist has no "no background" option, so point its **Default
Background** at `/chromha_static/transparent.png` or its images cover
everything the theme does.

---

## Attribution that must survive any fork

Weather icons come from Makin-Things/weather-icons (MIT), themselves derived
from the amCharts free animated weather icons (**CC BY 4.0**). amCharts must
be credited by anyone redistributing them. See `NOTICE.md`.

The idea came from the Caule Themes Pack by Ricardo Correia (MIT). No code is
shared with it.
