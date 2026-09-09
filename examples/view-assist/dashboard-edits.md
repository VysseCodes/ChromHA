# Dashboard edits, by hand

`convert.py` makes these three changes automatically. This is the reference
for doing them yourself, or for checking what the script did.

The View Assist dashboard is not included in this repository - View Assist is
CC BY-NC 4.0 and ChromHA is MIT, so its files stay where they are and get
edited in place.

**Where:** the View Assist dashboard, three-dot menu, **Raw configuration
editor**. Everything below lives in `button_card_templates`, at the top of
that file, above `views:`.

**Back it up first.** `view_assist.load_view` will not touch this block, but a
View Assist dashboard update can. Copy it somewhere safe before editing.

These three cover every view, because every view inherits from these
templates. Individual views only need attention where they override the
defaults - see the main README.

---

## 1. Body text colour

In `body_template` -> `styles` -> `card`:

```diff
       - font-family: |-
           [[[
             return `"${variables.var_assistsat_entity_font_style}", sans-serif`;
           ]]]
-      - color: white
+      - color: var(--primary-text-color, white)
       - font-weight: 300
```

The default text colour for every view.

## 2. Status icon colour

In `icon_template` -> `styles` -> `icon`:

```diff
       icon:
         - display: grid
-        - color: white
+        - color: var(--primary-color, white)
```

Covers the status icons, the menu, and every `dynamic_*_item`.

Do this one **before** the body text edit if you are using search and replace.
Both are `- color: white`, and a careless replace-all will convert the icon
rule to the text colour and leave your status icons wrong.

## 3. The background fallback

In `variable_template` -> `variables`, as the first entry:

```diff
   variable_template:
     variables:
+      background_color: var(--lovelace-background, var(--primary-background-color, black))
       dashboardversion: 1.3.2
```

This one is a latent bug rather than a preference. `body_template` already
ends with:

```yaml
              } else {
                return `center / cover no-repeat ${variables.background_color}`
              }
```

but nothing upstream ever defined `background_color`, so that branch produced
`center / cover no-repeat undefined`. A CSS declaration containing an invalid
value is discarded entirely, so the view fell back to whatever was behind it.
Defining the variable activates a branch that was already written.

---

## Checking your work

After saving, refresh the dashboard - changes to `button_card_templates` apply
on reload, with no `view_assist.load_view` needed, since this is not a view
file.

If a view goes blank, a `[[[ ]]]` block is returning `undefined` for a CSS
value and the browser is discarding the declaration. Plain `var(--...)`
strings cannot fail that way, which is the reason to prefer them over reading
the palette sensor.

To confirm the edits took, open a view in desktop Chrome, inspect the
button-card, and check that `color` resolves through `--primary-text-color`
rather than being a literal `white`.
