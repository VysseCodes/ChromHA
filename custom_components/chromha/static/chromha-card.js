/**
 * ChromHA colour card.
 *
 * Home Assistant has no colour-picker entity platform, and presenting an
 * accent colour as a light gives it a meaningless on/off state. So the accent
 * stays a plain `text` entity and this card supplies the control.
 *
 * Registered automatically by the integration - no Lovelace resource to add.
 *
 * Usage:
 *   type: custom:chromha-card
 *   entity: text.chromha_ryan_accent
 *
 * With no `entity`, the card finds the first ChromHA accent entity itself.
 */

const HEX = /^#[0-9a-fA-F]{6}$/;

class ChromHACard extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._pending = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 2;
  }

  static getStubConfig(hass) {
    const found = Object.keys(hass.states).find(
      (id) => id.startsWith("text.") && id.includes("chromha") && id.endsWith("accent")
    );
    return { entity: found || "" };
  }

  /** Resolve the accent entity, falling back to autodetection. */
  _entityId() {
    if (this._config?.entity) return this._config.entity;
    return Object.keys(this._hass.states).find(
      (id) => id.startsWith("text.") && id.includes("chromha") && id.endsWith("accent")
    );
  }

  /** The palette sensor belonging to the same device, if there is one. */
  _paletteFor(entityId) {
    const stem = entityId.replace(/^text\./, "").replace(/_accent$/, "");
    return this._hass.states[`sensor.${stem}_palette`];
  }

  async _commit(value) {
    if (!HEX.test(value)) return;
    // Optimistic, so dragging the picker does not snap back while Home
    // Assistant round-trips the state change.
    this._pending = value;
    await this._hass.callService("text", "set_value", {
      entity_id: this._entityId(),
      value,
    });
  }

  _render() {
    const id = this._entityId();
    const state = id ? this._hass.states[id] : undefined;

    if (!state) {
      this.innerHTML = `<ha-card><div class="pad">
        No ChromHA accent entity found. Set <code>entity:</code> in the card
        configuration.</div></ha-card>`;
      this._style();
      return;
    }

    // Once the real state catches up with the optimistic value, drop it.
    if (this._pending && this._pending.toLowerCase() === state.state.toLowerCase()) {
      this._pending = null;
    }
    const value = this._pending || state.state;
    const safe = HEX.test(value) ? value : "#11ab93";

    const palette = this._paletteFor(id);
    const swatches = palette
      ? ["accent", "accent_soft", "background", "surface", "text"]
          .filter((k) => palette.attributes[k])
          .map(
            (k) =>
              `<div class="sw" title="${k}: ${palette.attributes[k]}"
                    style="background:${palette.attributes[k]}"></div>`
          )
          .join("")
      : "";

    if (!this._built) {
      this.innerHTML = `
        <ha-card>
          <div class="pad">
            <div class="row">
              <input type="color" id="wheel">
              <div class="meta">
                <div class="label">Accent</div>
                <input type="text" id="hex" spellcheck="false" maxlength="7">
              </div>
            </div>
            <div class="swatches" id="swatches"></div>
          </div>
        </ha-card>`;
      this._style();
      this._built = true;

      const wheel = this.querySelector("#wheel");
      const hex = this.querySelector("#hex");

      // `input` fires continuously while dragging; `change` fires on release.
      // Only commit on release, so one drag is one service call rather than
      // hundreds - the integration debounces, but there is no reason to make
      // it work for nothing.
      wheel.addEventListener("input", () => {
        hex.value = wheel.value;
      });
      wheel.addEventListener("change", () => this._commit(wheel.value));

      hex.addEventListener("change", () => {
        let v = hex.value.trim();
        if (v && !v.startsWith("#")) v = `#${v}`;
        if (HEX.test(v)) {
          wheel.value = v;
          this._commit(v);
        } else {
          hex.value = wheel.value; // reject silently, restore
        }
      });
    }

    const wheel = this.querySelector("#wheel");
    const hex = this.querySelector("#hex");
    if (document.activeElement !== wheel) wheel.value = safe;
    if (document.activeElement !== hex) hex.value = safe;
    this.querySelector("#swatches").innerHTML = swatches;
  }

  _style() {
    if (this.querySelector("style")) return;
    const style = document.createElement("style");
    style.textContent = `
      .pad { padding: 16px; }
      .row { display: flex; align-items: center; gap: 16px; }
      .meta { flex: 1; }
      .label {
        font-size: 0.9em;
        color: var(--secondary-text-color);
        margin-bottom: 4px;
      }
      /* The native swatch is a small square by default; stretch it into
         something worth tapping on a tablet. */
      #wheel {
        width: 64px; height: 64px;
        padding: 0; border: none; border-radius: 12px;
        background: none; cursor: pointer;
      }
      #wheel::-webkit-color-swatch-wrapper { padding: 0; }
      #wheel::-webkit-color-swatch {
        border: 2px solid var(--divider-color);
        border-radius: 12px;
      }
      #wheel::-moz-color-swatch {
        border: 2px solid var(--divider-color);
        border-radius: 12px;
      }
      #hex {
        width: 100%; box-sizing: border-box;
        font-family: var(--code-font-family, monospace);
        font-size: 1.1em; padding: 8px;
        color: var(--primary-text-color);
        background: var(--secondary-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
      }
      #hex:focus { outline: none; border-color: var(--primary-color); }
      .swatches { display: flex; gap: 6px; margin-top: 14px; }
      .sw {
        flex: 1; height: 22px; border-radius: 6px;
        border: 1px solid var(--divider-color);
      }
      code {
        background: var(--secondary-background-color);
        padding: 1px 4px; border-radius: 4px;
      }`;
    this.appendChild(style);
  }
}

customElements.define("chromha-card", ChromHACard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "chromha-card",
  name: "ChromHA",
  description: "Pick the accent colour a ChromHA theme is derived from.",
  preview: true,
});
