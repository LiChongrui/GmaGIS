# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import numpy as np
import random

from PySide6.QtGui import QColor

from ggis.core.style.raster_display import gamma_lut as _gamma_lut


__all__ = ["GgsSymbol", "default_symbol", "PALETTE", "raster_to_rgba",
           "stretch_limits", "LINE_STYLES", "LINE_PATTERNS", "FILL_STYLES",
           "CAPS", "JOINS"]

from ggis.core.style.symbol_spec import (CAP_DEFAULT as _CAP_DEFAULT,
                                CAPS, DASH_CUSTOM,
                                FILL_SPACING_PX as _FILL_SPACING_PX,
                                FILL_STYLES,
                                FILL_WIDTH_PX as _FILL_WIDTH_PX,
                                JOIN_DEFAULT as _JOIN_DEFAULT, JOINS,
                                LINE_PATTERNS, LINE_STYLES)

PALETTE = [
    "#4C9BE8", "#F2A03D", "#5FBF6A", "#E86A6A", "#A878E0",
    "#C08A5E", "#E67BB0", "#8E9BAF", "#C3C93F", "#3FC3CF",
    "#7C8CE8", "#E0C14C", "#4FBFA8", "#D6705A", "#9C9C9C",
]

from ggis.core.crs.units import DEFAULT_LINE_WIDTH_PX

_DEFAULTS = {
    "point":   (1.00,      DEFAULT_LINE_WIDTH_PX,    4.0),
    "line":    (1.00,      DEFAULT_LINE_WIDTH_PX,    0.0),
    "polygon": (1.00,      DEFAULT_LINE_WIDTH_PX,    0.0),
    "":        (1.00,      DEFAULT_LINE_WIDTH_PX,    3.0),
}

_STROKE_DARK = "#1B2430"
_STROKE_LIGHT = "#0E1420"


from ggis.core.crs.units import (DEFAULT_UNIT, LOGICAL_DPI, MM_PER_INCH,
                          PX_PER_MM, PX_PER_PT, SELECTABLE_UNITS,
                          convert as unit_convert,
                          default_unit as _default_unit,
                          from_px as px_to_unit, to_px as unit_to_px)

SYMBOL_UNIT = DEFAULT_UNIT


def current_unit():
    return _default_unit()


def px_width(value):
    return px_to_unit(value)


def px_size(value):
    return px_to_unit(value)


def color_field_for_kind(kind):
    return "stroke" if str(kind or "").strip().lower().startswith("line") \
        else "fill"


def symbol_color(sym, kind):
    try:
        c = getattr(sym, color_field_for_kind(kind), None)
        return (QColor(c) if c is not None else QColor("#888888")).name()
    except Exception:
        exc_note("symbol_color @ ggis/render/symbol.py:116")
        return "#888888"


def set_symbol_color(sym, kind, color):
    try:
        setattr(sym, color_field_for_kind(kind), QColor(color))
    except Exception:
        exc_note("set_symbol_color @ ggis/render/symbol.py:124")
        pass
    return sym


class GgsSymbol:

    __slots__ = ("fill", "stroke", "width", "size", "opacity",
                 "fill_alpha", "dark_bg", "unit",
                 "line_style", "fill_style", "fill_spacing", "fill_width",
                 "cap", "join", "dash_custom")

    def __init__(self, fill="#4C9BE8", stroke=None,
                 width=None, size=None,
                 opacity=1.0, fill_alpha=1.0, dark_bg=True, unit=None,
                 line_style="solid", fill_style="solid",
                 fill_spacing=None, fill_width=None,
                 cap=None, join=None, dash_custom=()):
        _u = str(unit or current_unit())
        self.fill = QColor(fill)
        self.stroke = QColor(stroke or (_STROKE_LIGHT if dark_bg
                                        else _STROKE_DARK))
        self.width = float(px_to_unit(DEFAULT_LINE_WIDTH_PX, _u)) \
            if width is None else float(width)
        self.size = float(px_to_unit(4.0, _u)) if size is None \
            else float(size)
        self.opacity = float(opacity)
        self.fill_alpha = float(fill_alpha)
        self.dark_bg = bool(dark_bg)
        self.unit = _u
        self.line_style = str(line_style) \
            if (str(line_style) in LINE_STYLES
                or str(line_style) == DASH_CUSTOM) \
            else "solid"
        self.fill_style = str(fill_style) if str(fill_style) in FILL_STYLES \
            else "solid"
        self.dash_custom = tuple(float(v) for v in (dash_custom or ())
                                 if float(v) > 0)
        self.fill_spacing = float(px_to_unit(_FILL_SPACING_PX, _u)) \
            if fill_spacing is None else float(fill_spacing)
        self.fill_width = float(px_to_unit(_FILL_WIDTH_PX, _u)) \
            if fill_width is None else float(fill_width)
        self.cap = str(cap) if str(cap) in CAPS else _CAP_DEFAULT
        self.join = str(join) if str(join) in JOINS else _JOIN_DEFAULT

    def px_width(self):
        return unit_to_px(self.width, self.unit)

    def px_size(self):
        return unit_to_px(self.size, self.unit)

    def px_fill_spacing(self):
        return unit_to_px(self.fill_spacing, self.unit)

    def px_fill_width(self):
        return unit_to_px(self.fill_width, self.unit)

    def line_pattern(self):
        if str(self.line_style) == DASH_CUSTOM:
            pat = tuple(self.dash_custom or ())
            if not pat:
                return None
            if len(pat) % 2:
                pat = pat + (pat[-1],)
            return pat
        return LINE_PATTERNS.get(self.line_style)

    def has_fill_pattern(self):
        return self.fill_style != "solid"

    def clone(self):
        return GgsSymbol(fill=QColor(self.fill), stroke=QColor(self.stroke),
                         width=self.width, size=self.size,
                         opacity=self.opacity, fill_alpha=self.fill_alpha,
                         dark_bg=self.dark_bg, unit=self.unit,
                         line_style=self.line_style,
                         fill_style=self.fill_style,
                         fill_spacing=self.fill_spacing,
                         fill_width=self.fill_width,
                         cap=self.cap, join=self.join,
                         dash_custom=tuple(self.dash_custom or ()))

    def fill_color(self):
        c = QColor(self.fill)
        c.setAlphaF(max(0.0, min(1.0, c.alphaF() * self.fill_alpha
                                   * self.opacity)))
        return c

    def stroke_color(self):
        c = QColor(self.stroke)
        c.setAlphaF(max(0.0, min(1.0, c.alphaF() * self.opacity)))
        return c

    def __repr__(self):
        return "GgsSymbol(%s, w=%s, size=%s)" % (
            self.fill.name(), self.width, self.size)


def default_symbol(kind, index=0, dark_bg=True):
    color = random.choice(PALETTE)
    alpha, width, size = _DEFAULTS.get(kind, _DEFAULTS[""])
    return GgsSymbol(fill=color, width=px_width(width), size=px_size(size),
                     fill_alpha=alpha, dark_bg=dark_bg)


def stretch_limits(arr, nodata=None, low=2.0, high=98.0, max_samples=200000):
    a = np.asarray(arr)
    if nodata is not None:
        try:
            a = a[a != nodata]
        except Exception:
            exc_note("stretch_limits @ ggis/render/symbol.py:309")
            pass
    a = a[np.isfinite(a)] if np.issubdtype(a.dtype, np.floating) else a
    if a.size == 0:
        return 0.0, 1.0
    if a.size > max_samples:
        idx = np.linspace(0, a.size - 1, max_samples).astype(np.int64)
        a = a[idx]
    try:
        lo = float(np.percentile(a, low))
        hi = float(np.percentile(a, high))
    except Exception:
        exc_note("stretch_limits @ ggis/render/symbol.py:320")
        lo, hi = float(a.min()), float(a.max())
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo = float(np.nanmin(a)) if a.size else 0.0
        hi = float(np.nanmax(a)) if a.size else 1.0
        if hi <= lo:
            hi = lo + 1.0
    return lo, hi


def _stretch_band(band, nodata=None, low=2.0, high=98.0, limits=None):
    a = np.asarray(band)
    lo, hi = limits if limits else stretch_limits(a, nodata, low, high)
    lo32 = np.float32(min(max(float(lo), -3.0e38), 3.0e38))
    hi32 = np.float32(min(max(float(hi), -3.0e38), 3.0e38))
    span = max(hi32 - lo32, np.float32(1e-9))
    out = np.clip(a, lo32, hi32).astype(np.float32, copy=False)
    out -= lo32
    out *= (np.float32(255.0) / span)
    np.clip(out, 0, 255, out=out)
    if out.dtype.kind == "f":
        np.nan_to_num(out, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
    return out.astype(np.uint8)


def _to_u8(band, nodata=None, low=2.0, high=98.0, limits=None, hist=None):
    if hist is not None:
        try:
            from ggis.core.style import raster_display as _rd
            g = _rd.hist_map(band, hist[0], hist[1])
            if g is not None:
                return g
        except Exception:
            exc_note("_to_u8 @ ggis/render/symbol.py:378")
            pass
    return _stretch_band(band, nodata, low, high, limits)


def _to_u8_direct(band):
    a = np.asarray(band)
    if a.dtype == np.uint8:
        return a.astype(np.uint8, copy=False)
    lo = hi = None
    try:
        _info = np.iinfo(a.dtype)
        lo, hi = np.float32(_info.min), np.float32(_info.max)
    except (ValueError, TypeError):
        exc_note("_to_u8_direct @ ggis/render/symbol.py:400")
        try:
            _fin = np.finfo(a.dtype)
            lo, hi = np.float32(_fin.min), np.float32(_fin.max)
        except (ValueError, TypeError):
            exc_note("_to_u8_direct @ ggis/render/symbol.py:404")
            lo = hi = None
    if lo is None or hi is None:
        if a.size:
            return _stretch_band(a, None,
                                 (float(np.nanmin(a)), float(np.nanmax(a))))
        return np.zeros(a.shape[-2:] if a.ndim >= 2 else a.shape, np.uint8)
    span = max(hi - lo, np.float32(1e-9))
    out = np.clip(a, lo, hi).astype(np.float32, copy=False)
    out -= lo
    out *= (np.float32(255.0) / span)
    np.clip(out, 0, 255, out=out)
    if out.dtype.kind == "f":
        np.nan_to_num(out, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
    return out.astype(np.uint8)


def _hist_at(hist, i):
    if hist is None:
        return None
    try:
        if isinstance(hist, (list, tuple)) and hist \
                and isinstance(hist[0], (list, tuple)):
            return hist[i] if i < len(hist) else hist[-1]
    except Exception:
        exc_note("_hist_at @ ggis/render/symbol.py:431")
        pass
    return hist


def raster_to_rgba(arr, nodata=None, opacity=1.0, low=2.0, high=98.0,
                   display=None, limits=None, palette=None,
                   valid_mask=None, hist=None):
    out = _raster_to_rgba_core(arr, nodata, opacity, low, high, display,
                               limits, palette, valid_mask, hist)
    try:
        from .cpu.raster import _apply_alpha_band
    except Exception:
        exc_note("raster_to_rgba @ ggis/render/symbol.py:449")
        return out
    return _apply_alpha_band(out, arr, display)


def _raster_to_rgba_core(arr, nodata=None, opacity=1.0, low=2.0, high=98.0,
                         display=None, limits=None, palette=None,
                         valid_mask=None, hist=None):
    a = np.asarray(arr)
    if a.ndim not in (2, 3) or a.size == 0:
        return None
    if a.ndim == 3 and a.shape[0] == 1:
        a = a[0]
    if a.ndim == 3 and a.shape[0] == 2:
        a = np.stack([a[0], a[1], a[1]], axis=0)

    vm = None
    if valid_mask is not None:
        try:
            vm = np.asarray(valid_mask, dtype=bool)
            if vm.shape != a.shape[-2:]:
                vm = None
        except Exception:
            exc_note("_raster_to_rgba_core @ ggis/render/symbol.py:495")
            vm = None

    nd = nodata
    gamma = None
    nd_rgba = None
    bg = None
    bg_rgba = None
    if display is not None:
        if not display.use_nodata:
            nd = None
        elif display.nodata is not None:
            nd = display.nodata
        try:
            from ggis.core.style import raster_display as _rd
            nd_rgba = _rd.nodata_rgba(display)
        except Exception:
            exc_note("_raster_to_rgba_core @ ggis/render/symbol.py:514")
            nd_rgba = None
        try:
            bg = _rd.bg_value(display)
            if bg is not None:
                bg_rgba = _rd.bg_rgba(display)
        except Exception:
            exc_note("_raster_to_rgba_core @ ggis/render/symbol.py:520")
            bg = None
            bg_rgba = None
        try:
            gamma = _gamma_lut(display.gamma)
        except Exception:
            exc_note("_raster_to_rgba_core @ ggis/render/symbol.py:525")
            gamma = None
        b = int(display.band or 0)
        if b and a.ndim == 3:
            i = b - 1
            if 0 <= i < a.shape[0]:
                a = a[i]
                limits = _shared_limits(limits)
            else:
                a = a[0]
                limits = _shared_limits(limits)

    alpha_v = int(round(255 * max(0.0, min(1.0, float(opacity)))))
    alpha_v = max(0, min(255, alpha_v))

    if palette and a.ndim == 2:
        rgb = _apply_palette(a, palette)
        if rgb is not None:
            mask = _merge_mask(_nodata_mask(a, nd), vm)
            bg_mask = _bg_mask(a, bg)
            return _compose(rgb, mask, alpha_v, None, nd_rgba, bg_rgba, bg_mask)

    if a.ndim == 2:
        try:
            from ggis.core.style import raster_display as _rd
            rgb = _rd.class_rgb(a, display, _limits_at(limits, 0))
        except Exception:
            exc_note("_raster_to_rgba_core @ ggis/render/symbol.py:560")
            rgb = None
        if rgb is not None:
            mask = _merge_mask(_nodata_mask(a, nd), vm)
            bg_mask = _bg_mask(a, bg)
            return _compose(rgb, mask, alpha_v, None, nd_rgba, bg_rgba, bg_mask)

    _no_stretch = False
    try:
        from ggis.core.style import raster_display as _rd
        _no_stretch = (display is not None
                       and str(getattr(display, "stretch", "") or "")
                       == _rd.STRETCH_NONE)
    except Exception:
        exc_note("_raster_to_rgba_core @ ggis/render/symbol.py:578")
        _no_stretch = False
    if a.ndim == 3:
        if _no_stretch:
            r = _to_u8_direct(a[0])
            g = _to_u8_direct(a[1])
            b = _to_u8_direct(a[2])
        else:
            r = _to_u8(a[0], nd, low, high, _limits_at(limits, 0), _hist_at(hist, 0))
            g = _to_u8(a[1], nd, low, high, _limits_at(limits, 1), _hist_at(hist, 1))
            b = _to_u8(a[2], nd, low, high, _limits_at(limits, 2), _hist_at(hist, 2))
        rgb = np.dstack([r, g, b])
        mask = _nodata_mask(a[:3], nd)
        bg_mask = _bg_mask(a[:3], bg)
        mask = None if mask is None else mask.any(axis=0)
    else:
        if _no_stretch:
            g = _to_u8_direct(a)
        else:
            g = _to_u8(a, nd, low, high, _limits_at(limits, 0), _hist_at(hist, 0))
        ramp_rgb = _ramp_rgb(g, display)
        if ramp_rgb is not None:
            rgb = ramp_rgb
        else:
            rgb = np.dstack([g, g, g])
        mask = _nodata_mask(a, nd)
        bg_mask = _bg_mask(a, bg)
    mask = _merge_mask(mask, vm)
    return _compose(rgb, mask, alpha_v, gamma, nd_rgba, bg_rgba, bg_mask)


def _merge_mask(mask, valid_mask):
    if valid_mask is None:
        return mask
    try:
        vm = np.asarray(valid_mask, dtype=bool)
    except Exception:
        exc_note("_merge_mask @ ggis/render/symbol.py:636")
        return mask
    inv = ~vm
    return inv if mask is None else (mask | inv)


def _ramp_rgb(gray, display):
    if display is None:
        return None
    code = str(getattr(display, "ramp", "") or "")
    if not code or code == "none":
        return None
    try:
        from ggis.core.style import raster_display as rd
        lut = rd.ramp_lut(code, 256, steps=rd.class_steps(display))
        if lut is None:
            return None
        if getattr(display, "invert_ramp", False):
            lut = lut[::-1].copy()
        lut = rd.apply_class_colors(lut, rd.class_steps(display),
                                    rd.class_colors_of(display))
        idx = np.asarray(gray)
        return lut[idx]
    except Exception:
        exc_note("_ramp_rgb @ ggis/render/symbol.py:666")
        return None


def _apply_palette(a, palette):
    try:
        keys = sorted(palette)
        if not keys:
            return None
        kk = np.asarray(keys, dtype="float64")
        cols = np.asarray([[palette[k][0], palette[k][1], palette[k][2]]
                           for k in keys], dtype="uint8")
        shape = np.asarray(a).shape

        is_int = (all(float(k).is_integer() and k >= 0 for k in keys)
                  and np.asarray(a).dtype.kind in ("u", "i", "b"))
        top = int(max(keys)) if is_int else -1

        if is_int and top < 1 << 20:
            grid = np.arange(top + 1, dtype="float64")
            lut = cols[_nearest_index(grid, kk)]
            flat = np.clip(np.asarray(a).ravel().astype("int64"), 0, top)
            return lut[flat].reshape(shape + (3,))

        flat = np.asarray(a, dtype="float64").ravel()
        return cols[_nearest_index(flat, kk)].reshape(shape + (3,))
    except Exception:
        exc_note("_apply_palette @ ggis/render/symbol.py:703")
        return None


def _nearest_index(values, keys):
    pos = np.clip(np.searchsorted(keys, values), 0, keys.size - 1)
    left = np.clip(pos - 1, 0, keys.size - 1)
    dl = np.abs(values - keys[left])
    dr = np.abs(keys[pos] - values)
    return np.where(dl < dr, left, pos)


def _shared_limits(limits):
    pairs = None
    if isinstance(limits, (list, tuple)) and limits \
            and isinstance(limits[0], (list, tuple)):
        pairs = [p for p in limits if p]
    if not pairs:
        return limits
    return (min(p[0] for p in pairs), max(p[1] for p in pairs))


def _limits_at(limits, i):
    if limits is None:
        return None
    if isinstance(limits, (list, tuple)) and limits \
            and isinstance(limits[0], (list, tuple)):
        return limits[i] if i < len(limits) else limits[-1]
    return limits


def _nodata_mask(a, nodata):
    mask = None
    try:
        if np.asarray(a).dtype.kind == "f":
            mask = ~np.isfinite(a)
    except Exception:
        exc_note("_nodata_mask @ ggis/render/symbol.py:751")
        mask = None
    if nodata is not None:
        try:
            m = (a == nodata)
            mask = m if mask is None else (mask | m)
        except Exception:
            exc_note("_nodata_mask @ ggis/render/symbol.py:757")
            pass
    return mask


def _bg_mask(a, bg):
    if bg is None:
        return None
    try:
        m = (np.asarray(a) == bg)
        if m.ndim == 3:
            m = m.any(axis=0)
        return m
    except Exception:
        exc_note("_bg_mask @ ggis/render/symbol.py:774")
        return None


def _compose(rgb, mask, alpha_v, gamma, nd_rgba=None, bg_rgba=None, bg_mask=None):
    if gamma is not None:
        try:
            rgb = gamma[np.asarray(rgb)]
        except Exception:
            exc_note("_compose @ ggis/render/symbol.py:789")
            pass
    h, w = rgb.shape[0], rgb.shape[1]
    alpha = np.full((h, w), alpha_v, dtype=np.uint8)
    if mask is not None:
        try:
            m = np.asarray(mask, dtype=bool)
            if nd_rgba is None:
                alpha = np.where(m, 0, alpha).astype(np.uint8)
            else:
                rgb = np.array(rgb, copy=True)
                rgb[m] = np.asarray(nd_rgba[:3], dtype=np.uint8)
                if int(nd_rgba[3]) < 255:
                    alpha = np.where(m, int(nd_rgba[3]),
                                     alpha).astype(np.uint8)
        except Exception:
            exc_note("_compose @ ggis/render/symbol.py:804")
            pass
    if bg_mask is not None:
        try:
            bm = np.asarray(bg_mask, dtype=bool)
            if bg_rgba is None:
                alpha = np.where(bm, 0, alpha).astype(np.uint8)
            else:
                rgb = np.array(rgb, copy=True)
                rgb[bm] = np.asarray(bg_rgba[:3], dtype=np.uint8)
                if int(bg_rgba[3]) < 255:
                    alpha = np.where(bm, int(bg_rgba[3]),
                                     alpha).astype(np.uint8)
        except Exception:
            exc_note("_compose @ ggis/render/symbol.py:817")
            pass
    return np.dstack([rgb, alpha])
