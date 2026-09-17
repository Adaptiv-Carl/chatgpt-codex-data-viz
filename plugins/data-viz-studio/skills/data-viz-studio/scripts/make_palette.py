"""Build a full palette (series colours, ramps, tinted neutrals, readable text variants).

Usage:  python make_palette.py LABEL ACCENT MAIN SECOND [SERIES_HEX ...]
Series colours, if given, are used exactly (in that order) for stacked / multi-series charts.
"""
import colorsys


def _rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(r, g, b):
    return '#%02X%02X%02X' % tuple(round(max(0, min(1, x)) * 255) for x in (r, g, b))


def _hls(c, l, s=None):
    h, L, S = colorsys.rgb_to_hls(*_rgb(c)); return _hex(*colorsys.hls_to_rgb(h, l, S if s is None else s))


def luminance(c):
    f = lambda x: x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in _rgb(c)); return .2126 * r + .7152 * g + .0722 * b


def contrast(a, b="#FFFFFF"):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True); return (la + .05) / (lb + .05)


def readable(c, target=4.5):
    """Darken a colour (same hue) until it reads as text on white."""
    h, L, S = colorsys.rgb_to_hls(*_rgb(c))
    while contrast(_hex(*colorsys.hls_to_rgb(h, L, S))) < target and L > 0:
        L -= .01
    return _hex(*colorsys.hls_to_rgb(h, L, S))


def _ramp(c, n):
    _, L, _ = colorsys.rgb_to_hls(*_rgb(c))
    t = [L, L * .82, L * .66, L * .42, L + (1 - L) * .45, L + (1 - L) * .62, L * .28, L + (1 - L) * .82]
    return [c] + [_hls(c, x) for x in t[1:n]]


def make(label, accent, main, second, series=None, tint=None, bad="#D0364A", good="#2E8B55"):
    t = tint or second
    if series:
        seq = list(series)
        # extra series: shift lightness of different palette colours so a 6th-8th series never mimics the 1st
        def shift(c):
            _, L, _ = colorsys.rgb_to_hls(*_rgb(c))
            return _hls(c, L + (1 - L) * .5) if L < .55 else _hls(c, L * .6)
        order = [seq[2 % len(seq)], seq[1 % len(seq)], seq[3 % len(seq)]]
        seq = (seq + [shift(c) for c in order])[:8]
    else:
        seq = _ramp(main, 8)
    return {"label": label, "accent": accent, "accentText": readable(accent), "main": main, "second": second,
            "mainText": readable(main, 3), "bad": bad, "good": good, "swatches": series or [accent, main, second],
            "bg": _hls(t, .982, .45), "raised": _hls(t, .955, .30), "surface": "#FFFFFF", "text": _hls(t, .075, .15),
            "grey200": _hls(t, .925, .18), "grey400": _hls(t, .84, .12), "grey500": _hls(t, .70, .08), "grey700": _hls(t, .46, .07),
            "selectedTint": _hls(second, .94, .45), "seqMain": seq, "seqSecond": _ramp(second, 7)}


if __name__ == "__main__":
    import json, sys
    a = sys.argv[1:]
    print(json.dumps(make(a[0], a[1], a[2], a[3], a[4:] or None), indent=1))
