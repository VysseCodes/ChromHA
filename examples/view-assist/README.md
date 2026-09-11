# ChromHA + View Assist

**Most people want [the automatic dashboard](../../README.md#reaching-view-assist-and-music-assistant)
instead of anything in this folder.** ChromHA creates its own "ChromHA View
Assist" dashboard - Settings > Dashboards - that clones your real View Assist
dashboard and views with the same colour patches `convert.py` applies below,
automatically, with no manual copying or editing. This folder is for editing
View Assist's *own* dashboard directly instead - useful if you'd rather keep
using View Assist's dashboard unmodified and don't want a second one.

**If you previously copied `chromhaclock`, `chromhacontrols`, or
`chromhasettings` into `/config/view_assist/views/`: delete them.** They
predate the automatic dashboard, which now covers what they did (a themed
clock/controls and a Theme settings view) - the automatic dashboard skips
them if it finds them, but leaving them in your actual View Assist views
directory just adds confusing, unmaintained duplicate views there.

A script that converts View Assist's own views to follow the theme.

```
view-assist/
├── convert.py                  converts your View Assist files
├── dashboard-edits.md          the same dashboard edits, by hand
└── views/                      deprecated - see the notice above
    ├── chromhaclock/           clock with ChromHA weather icons
    ├── chromhacontrols/        brightness, volume, VA modes
    └── chromhasettings/        theme controls on the tablet
```

The `views/` layout matches View Assist's own, so those folders copy straight
into `/config/view_assist/views/`.

## Why View Assist's views are not included here

View Assist is licensed **CC BY-NC 4.0**, which forbids commercial use.
ChromHA is MIT, which permits it. Shipping converted copies of View Assist's
views would put incompatible terms on the same repository, so this folder
ships the converter instead and leaves the originals where they are.

That is also the more durable arrangement: the script converts whichever View
Assist version you actually have, rather than a snapshot that drifts out of
date.

---

## 0. Optional: push instead of pull

Each ChromHA profile's options can list one or more View Assist devices to
push to (**Push to View Assist**, off by default). When set, every rebuild
calls `view_assist.set_state` on those devices, which lands
`chromha_accent`, `chromha_background`, `chromha_surface`, `chromha_text`,
`chromha_theme_name` and `chromha_transparent_url` on the device's own View
Assist sensor - readable as `state_attr('sensor.<device>_view_assist',
'chromha_accent')`, with no separate ChromHA sensor to name. Useful if you
are editing View Assist's own dashboard by hand (below) and would rather
read ChromHA's colours from a plain state attribute than hardcode a profile
slug into a view.

## 1. Themes are CSS variables

No entity ids, no palette sensor. Home Assistant themes are CSS custom
properties, and custom properties inherit through the shadow DOM - so a
button-card style can say `var(--primary-text-color)` and the theme resolves
it. button-card passes style values straight through to CSS.

| Use | Variable |
|---|---|
| Body and heading text | `var(--primary-text-color)` |
| Dimmer secondary text | `var(--secondary-text-color)` |
| Page background | `var(--lovelace-background, var(--primary-background-color))` |
| Card background | `var(--ha-card-background)` |
| Accent, active icons | `var(--primary-color)` |
| Inactive icons | `var(--state-icon-color)` |
| Dividers | `var(--divider-color)` |

Always give a fallback - `var(--primary-text-color, white)` - so a view still
renders if no theme is applied.

The palette sensor exists for what CSS cannot reach: Jinja templates and
charting cards that hand colours to JavaScript. Not for this.

## 2. Turn off View Assist's background images

View Assist paints its own image over every view, which beats anything the
theme does. It has no "none" option - the choices are a default image, a local
sequence, a local random pick, or an Unsplash download. So point it at
ChromHA's transparent asset:

- Master Config -> **Background Image Source** -> *Default background*
- Master Config -> **Default Background** -> `/chromha_static/transparent.png`

`body_template` sets the background with the CSS `background:` shorthand,
which resets `background-color` to transparent. A transparent image therefore
leaves the button-card with no background at all, and the Lovelace background
behind it - your theme - shows through.

If the result is black rather than your theme colour, `lovelace-background` is
not set. ChromHA only sets it for the Glass style, so either switch the
profile to Glass or add this after the `background:` line in `body_template`,
where a later declaration wins:

```yaml
        - background-color: var(--primary-background-color)
```

## 3. Convert the dashboard and views

View Assist keeps these in two places, so there are two passes.

**The dashboard** holds `button_card_templates` and a placeholder view.
Everything inherits from those templates, so this pass does most of the work.

Copy it out of the raw configuration editor (VA dashboard -> three-dot menu ->
Raw configuration editor -> select all) into `dashboard.yaml`, then:

```bash
python3 convert.py dashboard.yaml --report
python3 convert.py dashboard.yaml -o dashboard-chromha.yaml
```

Paste the result back into the raw editor.

Only three edits land there, and they are the ones that matter most since
every view inherits them. If you would rather make them by hand, or want to
check what the script did, see [dashboard-edits.md](dashboard-edits.md).

**The views** are separate files:

```bash
python3 convert.py --views-dir /config/view_assist/views --report
python3 convert.py --views-dir /config/view_assist/views --in-place
```

Then run `view_assist.load_view` for each one changed - editing a file does
not update the running dashboard.

### Flags

| Flag | Effect |
|---|---|
| `--report` | Summarise and write nothing |
| `--in-place` | Rewrite each file, keeping a `.bak` |
| `--all-yaml` | Include alternates: `advancedcamera`, `clockalt`, `list-nocheckbox`, `music-alternative`, community contributions |
| `--theme-alert` | Also convert the Alert view |

The script is idempotent - a second run reports "nothing to change" - and it
validates its output as YAML before writing. Unmatched patterns are reported,
not guessed at, so a View Assist version it does not recognise produces a
clear list rather than a silent partial conversion.

### What it changes

- `body_template` text colour and `icon_template` icon colour
- Defines `background_color`, activating a fallback branch that exists
  upstream but was never given a value - it emitted `no-repeat undefined`,
  which browsers discard
- Literal card background colours, in any quoting style
- The hardcoded `infobackground.png`, removing the variable and the style that
  uses it **together** - removing only one leaves `url(undefined)`, which is
  worse than leaving both
- Literal white text and icons, including inside `card_mod`

### What it leaves alone

- **`var_background`.** That is View Assist's rotating background feature and
  keeps working. Only `variables.background` is removed.
- **The Alert view.** Bright blue with black text is deliberate; it interrupts
  rather than blends. `--theme-alert` overrides.
- **`rgba()` shader overlays.** Different job.
- Anything it does not recognise.

## 4. Add the ChromHA views (deprecated)

`views/chromhaclock`, `views/chromhacontrols`, and `views/chromhasettings`
are kept for reference, but **do not copy them into
`/config/view_assist/views/` any more** - the automatic dashboard (see the
notice at the top of this file) already gives you a themed clock, controls,
and a Theme settings view, generated from your real profiles instead of a
hardcoded example `var_profile`. If you already have any of these three
installed, delete them - the automatic dashboard skips them if it finds them
rather than cloning them in, but leaving them installed in your actual View
Assist views directory serves no purpose and can produce a confusing
duplicate "Theme" tab with a profile slug that does not match yours.

## Credits

View Assist by [dinki](https://github.com/dinki/View-Assist), CC BY-NC 4.0.
The views in this folder are original work; `convert.py` modifies View Assist
files in place on your own system and redistributes nothing.
