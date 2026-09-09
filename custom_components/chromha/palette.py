"""Colour maths and palette derivation.

Everything is computed in OKLab, which keeps perceived lightness steady when
shifting a hue. The whole palette is derived from a single accent colour plus
a mode (light/dark), so the user only ever picks one colour.

Deliberately pure Python with no dependencies: the resolved hex values are
published as sensor attributes, and CSS colour functions can't be read back
out of a stylesheet.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# --- sRGB <-> OKLab --------------------------------------------------------


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * (c ** (1 / 2.4)) - 0.055


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    """Parse #rgb or #rrggbb into 0..1 floats."""
    match = _HEX_RE.match(value.strip())
    if not match:
        raise ValueError(f"not a hex colour: {value!r}")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return tuple(int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(
        f"{max(0, min(255, round(c * 255))):02x}" for c in rgb
    )


def rgb_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_srgb_to_linear(c) for c in rgb)

    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    l_, m_, s_ = (math.copysign(abs(v) ** (1 / 3), v) for v in (l, m, s))

    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def oklab_to_rgb(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    big_l, a, b = lab

    l_ = big_l + 0.3963377774 * a + 0.2158037573 * b
    m_ = big_l - 0.1055613458 * a - 0.0638541728 * b
    s_ = big_l - 0.0894841775 * a - 1.2914855480 * b

    l, m, s = (v**3 for v in (l_, m_, s_))

    lin = (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    return tuple(min(1.0, max(0.0, _linear_to_srgb(c))) for c in lin)  # type: ignore[return-value]


# --- Manipulation ----------------------------------------------------------


def adjust(value: str, *, lightness: float = 0.0, chromha: float = 1.0) -> str:
    """Shift lightness by an absolute amount and scale chromha."""
    big_l, a, b = rgb_to_oklab(hex_to_rgb(value))
    big_l = min(1.0, max(0.0, big_l + lightness))
    return rgb_to_hex(oklab_to_rgb((big_l, a * chromha, b * chromha)))


def with_lightness(value: str, lightness: float, chroma: float = 1.0) -> str:
    """Set an absolute OKLab lightness, keeping the hue.

    Used for text. Mixing toward a neutral washes the hue out almost
    entirely; anchoring lightness and scaling chroma instead keeps the colour
    recognisably the accent while landing where it needs to for contrast.
    """
    big_l, a, b = rgb_to_oklab(hex_to_rgb(value))
    return rgb_to_hex(oklab_to_rgb((lightness, a * chroma, b * chroma)))


def mix(a: str, b: str, weight: float) -> str:
    """Blend two colours in OKLab. weight=0 returns a, 1 returns b."""
    la = rgb_to_oklab(hex_to_rgb(a))
    lb = rgb_to_oklab(hex_to_rgb(b))
    return rgb_to_hex(
        oklab_to_rgb(tuple(x + (y - x) * weight for x, y in zip(la, lb)))  # type: ignore[arg-type]
    )


def relative_luminance(value: str) -> float:
    r, g, b = (_srgb_to_linear(c) for c in hex_to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def readable_on(background: str, *, dark: str = "#12131a", light: str = "#f4f5f7") -> str:
    """Pick whichever of two text colours contrasts better with the background."""
    return dark if contrast_ratio(background, dark) >= contrast_ratio(background, light) else light


def ensure_contrast(foreground: str, background: str, target: float = 4.5) -> str:
    """Nudge a foreground colour until it clears a contrast ratio."""
    if contrast_ratio(foreground, background) >= target:
        return foreground

    darken = relative_luminance(background) > 0.5
    candidate = foreground
    for _ in range(40):
        candidate = adjust(candidate, lightness=-0.025 if darken else 0.025)
        if contrast_ratio(candidate, background) >= target:
            return candidate
        if candidate in ("#000000", "#ffffff"):
            break
    return candidate


# --- Palette ---------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    """A fully resolved set of colours. All values are hex strings."""

    accent: str
    accent_soft: str
    accent_strong: str
    background: str
    surface: str
    surface_raised: str
    text: str
    text_muted: str
    divider: str
    disabled: str
    icon: str
    icon_active: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def build_palette(accent: str, *, dark: bool, contrast_boost: bool = False) -> Palette:
    """Derive a complete palette from one accent colour.

    Neutrals are tinted slightly toward the accent so the interface reads as
    one colour scheme rather than an accent floating on grey.
    """
    accent = rgb_to_hex(hex_to_rgb(accent))  # normalise

    if dark:
        background = mix("#0c0d10", accent, 0.06)
        surface = mix("#191b20", accent, 0.07)
        surface_raised = mix("#232630", accent, 0.08)
        # A light tint of the accent rather than plain white: high lightness,
        # chroma pulled back to stay comfortable for long reading.
        text = with_lightness(accent, 0.93, chroma=0.55)
        accent_soft = adjust(accent, lightness=+0.12, chromha=0.85)
        accent_strong = adjust(accent, lightness=-0.06, chromha=1.05)
    else:
        background = mix("#f4f5f7", accent, 0.05)
        surface = "#ffffff"
        surface_raised = mix("#ffffff", accent, 0.05)
        # The same idea inverted: a dark tint of the accent, not plain black.
        text = with_lightness(accent, 0.28, chroma=0.60)
        accent_soft = adjust(accent, lightness=+0.15, chromha=0.7)
        accent_strong = adjust(accent, lightness=-0.10, chromha=1.05)

    target = 7.0 if contrast_boost else 4.5
    text = ensure_contrast(text, surface, target)

    text_muted = ensure_contrast(mix(text, background, 0.45), surface, 3.0)
    divider = mix(background, text, 0.18)
    disabled = mix(background, text, 0.32)

    # The accent has to stay legible against the card, not just the page.
    icon_active = ensure_contrast(accent, surface, 3.0)

    return Palette(
        accent=accent,
        accent_soft=accent_soft,
        accent_strong=accent_strong,
        background=background,
        surface=surface,
        surface_raised=surface_raised,
        text=text,
        text_muted=text_muted,
        divider=divider,
        disabled=disabled,
        icon=text_muted,
        icon_active=icon_active,
    )
