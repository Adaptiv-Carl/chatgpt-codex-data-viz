# Design system

Layout, type scale and spacing mirror the reference dashboard: 212px sidebar on a raised panel, filter pills in a raised bar, KPI tiles (uppercase label, 24px heading-font value), white chart cards with 1px borders and 8px radius, two-column grid collapsing to one below 980px.

Fonts: Sora (headings) and DM Sans (body) from Google Fonts, falling back to system fonts offline.

## Tone structure (keep this when making new palettes)
| Token | Role | Rule |
|---|---|---|
| `accent` | Highlight colour | Sparingly: active nav, one highlighted KPI. Never the main chart colour. |
| `accentText` | Accent used as text | Auto-darkened (same hue) to 4.5:1 on white, so light accents stay readable. |
| `main` | Main data colour | Single-series bars and lines. |
| `second` | Muted/strong data colour | Comparison series, selected controls, grain toggle (white text on it). |
| `good` / `bad` | Signals only | Keep clear of the accent hue (Signal uses a darker red for this reason). |
| `bg`, `raised`, `surface` | Page / panels / cards | Near-white, lightly tinted. Cards pure white. |
| `grey200–700`, `text` | Lines, muted text, body | Low-saturation tints. |
| `seqMain` (8) | Stacked / multi-series | The palette's own colours first, ordered dark/light alternating, then 3 lightness-shifted extras from different hues. Thin white gaps separate segments. |
| `seqSecond` (7) | Alternative ramp | Generated from `second`. |

## Shipped palettes
| Palette | Source colours | Accent | Main | Second | Notes |
|---|---|---|---|---|---|
| Sage | `#BBDB9B #ABC4A1 #9DB4AB #8D9D90 #878E76` | `#BBDB9B` (text `#58812E`) | `#9DB4AB` | `#878E76` | Soft, low contrast. |
| Signal (default) | `#006BA6 #0496FF #FFBC42 #D81159 #8F2D56` | `#D81159` | `#0496FF` | `#006BA6` | Highest contrast; bad = `#B3261E`. |
| Lilac | `#DDC4DD #DCCFEC #A997DF #4F517D #1A3A3A` | `#A997DF` (text `#7F64CF`) | `#4F517D` | `#1A3A3A` | Neutrals tinted lilac. |

## Custom palette
Pass accent, main, second, then the source colours in the order you want series to appear (alternate darker and lighter):
```bash
python scripts/make_palette.py "Client" "#ACCENT" "#MAIN" "#SECOND" "#S1" "#S2" "#S3" "#S4" "#S5"
```
Put the output in the config as `customPalette` and set `"palette": "custom"`. To add it permanently, add it to `assets/palettes.json` under a new key.
