# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import weakref

from ggis.core.analysis import resampling as _rs

import numpy as np

from . import style_library as _sl
import logging
_log = logging.getLogger("gmagis")


def _ramp_pts_from_hex(hexes):
    out = []
    n = max(1, len(hexes) - 1)
    for i, h in enumerate(hexes):
        s = str(h).lstrip("#")
        out.append((round(i / n, 3),
                    (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))))
    return tuple(out)

__all__ = [
    "STRETCH_PERCENTILE", "STRETCH_MINMAX", "STRETCH_NONE", "STRETCHES",
    "STRETCH_LABELS",
    "GgsRasterDisplay",
    "get_display", "set_display", "reset_display", "display_key",
    "default_display",
    "sample_array", "band_stats", "histogram", "resolve_stretch",
    "limits_from_stats", "layer_limits", "layer_limits_multi", "stats_for",
    "effective_nodata", "clear_sample_cache",
    "gamma_lut", "raster_attribute_table", "palette",
    "RAMPS", "RAMP_LABELS", "RAMP_NONE", "ramp_control_points",
    "ramp_lut", "ramp_stops", "ramp_hex_stops",
    "MODE_RGB", "MODE_GRAY", "MODE_PSEUDO", "MODE_COLORMAP", "MODE_UNIQUE",
    "MODE_CLASSIFY", "class_steps", "class_color_list", "class_colors_of",
    "class_breaks_of", "class_rgb", "apply_class_colors", "GRAY_POINTS",
    "STRETCHES", "STRETCH_LABELS", "STRETCH_NONE", "STRETCH_MINMAX",
    "STRETCH_PERCENTILE", "STRETCH_STDDEV", "STRETCH_HIST_EQ",
    "STRETCH_HIST_MATCH", "STRETCH_CUSTOM",
    "hist_stretch", "hist_map", "layer_hist_map",
    "CLASS_MODES", "CLASS_MODE_LABELS", "CLASS_CUSTOM", "DEFAULT_CLASS_MODE",
    "class_mode_of", "classify_breaks",
    "default_rgb_bands",
    "RENDER_MODES", "RENDER_MODE_LABELS", "MAX_UNIQUE_COLORS",
    "render_mode", "set_render_mode", "render_palette", "auto_color_map",
    "color_map_of",
]

STRETCH_NONE = "none"
STRETCH_MINMAX = "minmax"
STRETCH_PERCENTILE = "percentile"
STRETCH_STDDEV = "stddev"
STRETCH_HIST_EQ = "hist_eq"
STRETCH_HIST_MATCH = "hist_match"
STRETCH_CUSTOM = "custom"

STRETCHES = (
    (STRETCH_NONE, "无"),
    (STRETCH_MINMAX, "最大最小"),
    (STRETCH_PERCENTILE, "百分比截断"),
    (STRETCH_STDDEV, "标准差"),
    (STRETCH_HIST_EQ, "直方图均衡化"),
    (STRETCH_HIST_MATCH, "直方图规定化"),
    (STRETCH_CUSTOM, "自定义"),
)
STRETCH_LABELS = {code: label for code, label in STRETCHES}

CLASS_CUSTOM = "custom"

CLASS_MODES = (
    ("equal", "等间隔"),
    ("quantile", "分位数"),
    ("jenks", "自然断点"),
    ("stddev", "标准差"),
    ("pretty", "美观断点"),
    ("log", "对数刻度"),
    (CLASS_CUSTOM, "自定义"),
)
CLASS_MODE_LABELS = {code: label for code, label in CLASS_MODES}
DEFAULT_CLASS_MODE = "equal"


MODE_RGB = "rgb"
MODE_GRAY = "gray"
MODE_PSEUDO = "pseudocolor"
MODE_COLORMAP = "colormap"
MODE_UNIQUE = "unique"
MODE_CLASSIFY = "classify"

RENDER_MODES = (
    (MODE_RGB, "色彩合成"),
    (MODE_PSEUDO, "拉伸"),
    (MODE_CLASSIFY, "分类"),
    (MODE_COLORMAP, "色彩映射表"),
    (MODE_UNIQUE, "唯一值"),
)

RENDER_MODE_LABELS = {code: label for code, label in RENDER_MODES}


MAX_UNIQUE_COLORS = 64


def render_mode(display):
    try:
        if int(getattr(display, "band", 0) or 0) == 0:
            return MODE_RGB
        if bool(getattr(display, "use_colormap", False)):
            return MODE_COLORMAP
        if color_map_of(display):
            return MODE_UNIQUE
        if class_steps(display):
            return MODE_CLASSIFY
        return MODE_PSEUDO
    except Exception:
        _log.exception("silent exception in render_mode")
        return MODE_RGB


def class_steps(display):
    try:
        n = int(getattr(display, "class_n", 0) or 0)
    except Exception:
        _log.exception("silent exception in class_steps")
        return None
    return n if n >= 2 else None


def color_map_of(display):
    try:
        cm = getattr(display, "color_map", None)
        return dict(cm) if cm else {}
    except Exception:
        _log.exception("silent exception in color_map_of")
        return {}


def class_colors_of(display):
    try:
        cc = [str(c or "") for c in
              (getattr(display, "class_colors", None) or [])]
    except Exception:
        _log.exception("silent exception in class_colors_of")
        return None
    return cc or None


def class_mode_of(display):
    try:
        m = str(getattr(display, "class_mode", "") or "")
    except Exception:
        _log.exception("silent exception in class_mode_of")
        m = ""
    return m if m in CLASS_MODE_LABELS else DEFAULT_CLASS_MODE


def classify_breaks(layer, band, mode, n, limits=None):
    if layer is None or int(n or 0) < 2:
        return None
    try:
        from ggis.render.renderers import classify as _classify
    except Exception:
        _log.exception("silent exception in classify_breaks")
        return None
    try:
        arr, _ext = sample_array(layer, band=band)
        if arr is None:
            return None
        a = np.asarray(arr)
        if a.ndim == 3:
            i = max(1, int(band or 1)) - 1
            i = max(0, min(i, int(a.shape[0]) - 1))
            a = a[i]
        v = a.ravel().astype("float64")
        nd = None
        try:
            nd = layer.nodata()
        except Exception:
            _log.exception("silent exception in classify_breaks")
            nd = None
        if nd is not None:
            try:
                v = v[v != float(nd)]
            except Exception:
                _log.exception("silent exception in classify_breaks")
        v = v[np.isfinite(v)]
        if v.size < 2:
            return None
        m = str(mode or DEFAULT_CLASS_MODE)
        if m == CLASS_CUSTOM:
            return None
        if m == "equal" and limits:
            lo, hi = float(limits[0]), float(limits[1])
            if lo < hi:
                k = int(n)
                return [lo + (hi - lo) * i / k for i in range(k + 1)]
        b = _classify(v, int(n), m)
        out = [float(x) for x in (b or [])]
        return out if len(out) >= 2 else None
    except Exception:
        _log.exception("silent exception in classify_breaks")
        return None


def class_breaks_of(display):
    try:
        bs = [float(v) for v in
              (getattr(display, "class_breaks", None) or [])]
    except Exception:
        _log.exception("silent exception in class_breaks_of")
        return None
    if len(bs) < 2:
        return None
    for i in range(1, len(bs)):
        if not (bs[i] > bs[i - 1]):
            return None
    return bs


GRAY_POINTS = ((0.0, (0, 0, 0)), (1.0, (255, 255, 255)))


def apply_class_colors(lut, steps, colors):
    try:
        k = int(steps or 0)
    except Exception:
        _log.exception("silent exception in apply_class_colors")
        return lut
    if lut is None or k < 2 or not colors:
        return lut
    try:
        n = int(lut.shape[0])
        idx = np.arange(n) * k // n
        for i, c in enumerate(list(colors)[:k]):
            if not c:
                continue
            rgba = parse_color_rgba(c)
            if rgba is None:
                continue
            lut[idx == i] = (int(rgba[0]), int(rgba[1]), int(rgba[2]))
    except Exception:
        _log.exception("silent exception in apply_class_colors")
        return lut
    return lut


def class_color_list(display):
    n = class_steps(display)
    if not n:
        return []
    code = str(getattr(display, "ramp", "") or "")
    pts = ramp_control_points(code) or GRAY_POINTS
    try:
        lut = ramp_lut(code, 256, steps=n, points=pts)
        if lut is None:
            return []
        if bool(getattr(display, "invert_ramp", False)):
            lut = lut[::-1].copy()
        lut = apply_class_colors(lut, n, class_colors_of(display))
        out = []
        for i in range(n):
            m = max(0, min(255, int((i + 0.5) / n * 255)))
            c = lut[m]
            out.append((int(c[0]), int(c[1]), int(c[2])))
        return out
    except Exception:
        _log.exception("silent exception in class_color_list")
        return []


def class_rgb(values, display, limits=None):
    n = class_steps(display)
    if not n:
        return None
    cols = class_color_list(display)
    if len(cols) < n:
        return None
    breaks = class_breaks_of(display)
    if not breaks or len(breaks) != n + 1:
        try:
            lo, hi = float(limits[0]), float(limits[1])
        except Exception:
            _log.exception("silent exception in class_rgb")
            return None
        if not (hi > lo):
            return None
        breaks = [lo + (hi - lo) * i / n for i in range(n + 1)]
    try:
        a = np.asarray(values, dtype="float64")
        inner = np.asarray(breaks[1:-1], dtype="float64")
        idx = np.clip(np.digitize(a, inner), 0, n - 1)
        return np.asarray(cols, dtype="uint8")[idx]
    except Exception:
        _log.exception("silent exception in class_rgb")
        return None


def set_render_mode(display, mode, ramp=None):
    m = str(mode or MODE_RGB)
    try:
        if m == MODE_RGB:
            display.band = 0
            display.use_colormap = False
            display.color_map = {}
            return display
        if int(getattr(display, "band", 0) or 0) == 0:
            display.band = 1
        display.use_colormap = (m == MODE_COLORMAP)
        if m not in (MODE_UNIQUE, MODE_COLORMAP):
            display.color_map = {}
        if m == MODE_CLASSIFY:
            n = int(getattr(display, "class_n", 0) or 0)
            display.class_n = n if n >= 2 else 5
        else:
            display.class_n = 0
        if m == MODE_GRAY:
            display.ramp = RAMP_NONE
        elif m == MODE_PSEUDO:
            cur = str(getattr(display, "ramp", RAMP_NONE) or RAMP_NONE)
            display.ramp = str(ramp or cur or DEFAULT_PSEUDO_RAMP)
    except Exception:
        _log.exception("silent exception in set_render_mode")
    return display


def render_palette(layer, display):
    if display is None:
        return None
    try:
        out = {}
        if bool(getattr(display, "use_colormap", False)):
            out = dict(palette(layer) or {})
        for k, v in color_map_of(display).items():
            rgba = parse_color_rgba(v)
            if rgba is None:
                continue
            try:
                out[int(round(float(k)))] = rgba
            except Exception:
                _log.exception("silent exception in render_palette")
                continue
        return out or None
    except Exception:
        _log.exception("silent exception in render_palette")
        return None
    return None


LEGEND_SWATCH_MAX = 24


def legend_palette(layer, display, limit=LEGEND_SWATCH_MAX):
    if layer is None or display is None:
        return [], {}
    try:
        cmap = dict(render_palette(layer, display) or {})
    except Exception:
        _log.exception("silent exception in legend_palette")
        cmap = {}
    if not cmap:
        return [], {}
    if render_mode(display) == MODE_COLORMAP:
        try:
            ex = existing_values(layer,
                                 band=int(getattr(display, "band", 0) or 0))
        except Exception:
            _log.exception("silent exception in legend_palette")
            ex = None
        if ex:
            keep = set(int(v) for v in ex)
            try:
                for _k in (color_map_of(display) or {}):
                    keep.add(int(round(float(_k))))
            except Exception:
                _log.exception("silent exception in legend_palette")
            sub = {k: v for k, v in cmap.items() if int(k) in keep}
            if sub:
                cmap = sub
    keys = sorted(cmap)
    if limit:
        keys = keys[:int(limit)]
    return keys, cmap


def auto_color_map(layer, max_colors=MAX_UNIQUE_COLORS, band=0, ramp=None):
    info = raster_attribute_table(
        layer, max_unique=max(int(max_colors), MAX_UNIQUE), band=band)
    rows = list(info.get("rows") or [])
    if not rows or str(info.get("kind") or "") == "none":
        return {}
    out = {}
    _rc0 = str(ramp or "")
    if _rc0 and _rc0 != RAMP_NONE:
        try:
            _cols0 = ["#%02X%02X%02X" % tuple(c[:3])
                      for c in ramp_stops(_rc0, max(1, len(rows)))]
        except Exception:
            _log.exception("silent exception in auto_color_map")
            _cols0 = []
        if _cols0:
            _out0 = {}
            for _i0, _row0 in enumerate(rows):
                try:
                    _out0[_map_key(_row0[0])] = _cols0[_i0 % len(_cols0)]
                except Exception:
                    _log.exception("silent exception in auto_color_map")
                    continue
            return _out0
    if str(info.get("kind")) == "palette":
        for row in rows:
            try:
                val, _name, rgba, _n = row
            except Exception:
                _log.exception("silent exception in auto_color_map")
                continue
            if not rgba:
                continue
            try:
                out[_map_key(val)] = "#%02X%02X%02X" % (int(rgba[0]),
                                                        int(rgba[1]),
                                                        int(rgba[2]))
            except Exception:
                _log.exception("silent exception in auto_color_map")
                continue
        return out
    try:
        from ggis.render.renderers import categorical_colors
        cols = categorical_colors(max(1, len(rows)))
    except Exception:
        _log.exception("silent exception in auto_color_map")
        cols = ["#4C9BE8"]
    for i, row in enumerate(rows):
        try:
            val = row[0]
        except Exception:
            _log.exception("silent exception in auto_color_map")
            continue
        out[_map_key(val)] = cols[i % len(cols)]
    return out


def _map_key(value):
    try:
        f = float(value)
    except Exception:
        _log.exception("silent exception in _map_key")
        return str(value)
    if abs(f - round(f)) < 1e-9:
        return "%d" % int(round(f))
    return ("%.6f" % f).rstrip("0").rstrip(".")


RAMP_NONE = "none"

RAMPS = ((RAMP_NONE, "灰度", None),) + tuple(
    (code, _sl.RAMP_TITLES[code], _ramp_pts_from_hex(hexes))
    for code, hexes in _sl.RAMP_STOPS.items())
_LEGACY_PTS = {code: _ramp_pts_from_hex(hexes)
               for code, hexes in _sl.LEGACY_STOPS.items()}

RAMP_LABELS = {code: label for code, label, _pts in RAMPS}
RAMP_LABELS.update(_sl.LEGACY_TITLES)

DEFAULT_PSEUDO_RAMP = RAMP_NONE


def ramp_control_points(code):
    code = str(code or "")
    if code.startswith("user:"):
        try:
            from . import user_ramps
            return user_ramps.control_points(code)
        except Exception:
            _log.exception("silent exception in ramp_control_points")
            return None
    for c, _label, pts in RAMPS:
        if c == code:
            return pts
    pts = _LEGACY_PTS.get(code)
    if pts is not None:
        return pts
    return None


def ramp_stops(code, n=32):
    pts = ramp_control_points(code)
    if not pts:
        return []
    out = []
    for i in range(n):
        t = i / max(1, n - 1)
        out.append(_ramp_sample(pts, t))
    return out


def ramp_hex_stops(code, n=32):
    stops = []
    if code:
        try:
            stops = list(ramp_stops(code, n) or [])
        except Exception:
            _log.exception("silent exception in ramp_hex_stops")
            stops = []
    if not stops:
        stops = [tuple(int(round(255.0 * i / max(1, n - 1))) for _ in range(3))
                 for i in range(n)]
    out = []
    for c in stops:
        try:
            out.append("#%02X%02X%02X" % (int(c[0]), int(c[1]), int(c[2])))
        except Exception:
            _log.exception("silent exception in ramp_hex_stops")
            continue
    return out


def ramp_lut(code, n=256, steps=None, points=None):
    pts = points if points else ramp_control_points(code)
    if not pts:
        return None
    n = max(2, int(n))
    xs = np.linspace(0.0, 1.0, n)
    out = np.empty((n, 3), dtype="uint8")
    for i, t in enumerate(xs):
        out[i] = _ramp_sample(pts, float(t))
    try:
        k = int(steps) if steps else 0
    except Exception:
        _log.exception("silent exception in ramp_lut")
        k = 0
    if k >= 2:
        k = min(k, n)
        seg = np.minimum((np.arange(n) * k) // n, k - 1)
        mids = np.minimum(((np.arange(k) + 0.5) / k * (n - 1)).astype(int),
                          n - 1)
        out = out[mids][seg]
    return out


def _ramp_sample(pts, t):
    t = min(1.0, max(0.0, float(t)))
    prev = pts[0]
    for pos, col in pts:
        if t <= pos:
            if pos <= prev[0]:
                return tuple(int(v) for v in col)
            k = (t - prev[0]) / (pos - prev[0])
            return tuple(int(round(prev[1][i] + (col[i] - prev[1][i]) * k))
                         for i in range(3))
        prev = (pos, col)
    return tuple(int(v) for v in pts[-1][1])

SAMPLE_SIZE = 1024

MAX_UNIQUE = 256

NODATA_TRANSPARENT = "#00000000"


def parse_color_rgba(text):
    if text is None:
        return None
    s = str(text).strip().lstrip("#")
    try:
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        if len(s) == 6:
            r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4))
            return (r, g, b, 255)
        if len(s) == 8:
            a, r, g, b = (int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
            return (r, g, b, a)
    except Exception:
        _log.exception("silent exception in parse_color_rgba")
        return None
    return None


def _fmt_value(v):
    try:
        f = float(v)
    except Exception:
        _log.exception("silent exception in _fmt_value")
        return str(v)
    if f != f:
        return "NaN"
    if abs(f - round(f)) < 1e-9 and abs(f) < 1e15:
        return "%d" % int(round(f))
    return ("%.4f" % f).rstrip("0").rstrip(".")


def sample_point(layer, x, y):
    if layer is None or not layer.is_raster():
        return None
    try:
        ext = layer.extent()
    except Exception:
        _log.exception("silent exception in sample_point")
        return None
    if ext is None or ext.is_empty():
        return None
    try:
        if not ext.contains(float(x), float(y)):
            return None
    except Exception:
        _log.exception("silent exception in sample_point")
        return None
    try:
        rx, ry = layer.resolution()
        rx, ry = abs(float(rx)), abs(float(ry))
    except Exception:
        _log.exception("silent exception in sample_point")
        rx = ry = 0.0
    if rx <= 0 or ry <= 0:
        return None
    try:
        n = int(layer.band_count() or 1)
    except Exception:
        _log.exception("silent exception in sample_point")
        n = 1
    if n <= 0:
        return None
    bands = list(range(1, n + 1))
    box = None
    try:
        from ggis.core.crs.extent import GgsRectangle
        box = GgsRectangle(float(x) - rx * 0.5, float(y) - ry * 0.5,
                           float(x) + rx * 0.5, float(y) + ry * 0.5)
    except Exception:
        _log.exception("silent exception in sample_point")
        return None
    try:
        arr, _e = layer.read_window(box, (1, 1), resample=0, bands=bands)
    except Exception:
        _log.exception("silent exception in sample_point")
        return None
    if arr is None:
        return None
    try:
        vals = np.asarray(arr).reshape(-1)
    except Exception:
        _log.exception("silent exception in sample_point")
        return None
    if vals.size == 0:
        return None
    nd = None
    try:
        d = get_display(layer)
        if d is not None and getattr(d, "use_nodata", True):
            nd = getattr(d, "nodata", None)
            nd = None if nd is None else float(nd)
    except Exception:
        _log.exception("silent exception in sample_point")
        nd = None
    if nd is None:
        try:
            lnd = _layer_nodata(layer)
            nd = None if lnd is None else float(lnd)
        except Exception:
            _log.exception("silent exception in sample_point")
            nd = None
    out_bands, out_vals = [], []
    for i in range(min(n, int(vals.size))):
        try:
            v = vals[i]
        except Exception:
            _log.exception("silent exception in sample_point")
            continue
        out_bands.append(i + 1)
        is_nd = False
        try:
            fv = float(v)
            is_nd = (fv != fv) or (nd is not None and abs(fv - nd) < 1e-9)
        except Exception:
            _log.exception("silent exception in sample_point")
            fv = None
        out_vals.append(None if (is_nd or fv is None) else fv)
    if not out_bands:
        return None
    col = row = -1
    try:
        col = int((float(x) - float(ext.xmin)) / rx)
        row = int((float(ext.ymax) - float(y)) / ry)
    except Exception:
        _log.exception("silent exception in sample_point")
    return {"bands": out_bands, "values": out_vals,
            "pixel": (col, row),
            "any_nodata": any(v is None for v in out_vals)}


def sample_axis(layer, x, y, axis="x", max_samples=512, band=1):
    if layer is None or not layer.is_raster():
        return None, None
    try:
        rx, ry = layer.resolution()
        rx, ry = abs(float(rx)), abs(float(ry))
    except Exception:
        _log.exception("silent exception in sample_axis")
        return None, None
    if rx <= 0 or ry <= 0:
        return None, None
    try:
        ext = layer.extent()
    except Exception:
        _log.exception("silent exception in sample_axis")
        ext = None
    if ext is None or ext.is_empty():
        return None, None
    try:
        from ggis.core.crs.extent import GgsRectangle
    except Exception:
        _log.exception("silent exception in sample_axis")
        return None, None
    n = max(2, int(max_samples))
    ax = str(axis or "x").lower()
    if ax.startswith("y"):
        box = GgsRectangle(float(x) - rx * 0.5, float(ext.ymin),
                           float(x) + rx * 0.5, float(ext.ymax))
        size = (1, n)
    else:
        box = GgsRectangle(float(ext.xmin), float(y) - ry * 0.5,
                           float(ext.xmax), float(y) + ry * 0.5)
        size = (n, 1)
    try:
        arr, _e = layer.read_window(box, size, resample=0,
                                    bands=[int(band or 1)])
    except Exception:
        _log.exception("silent exception in sample_axis")
        return None, None
    if arr is None:
        return None, None
    try:
        vals = [float(v) for v in np.asarray(arr).reshape(-1)]
    except Exception:
        _log.exception("silent exception in sample_axis")
        return None, None
    if not vals:
        return None, None
    coords = []
    if ax.startswith("y"):
        span = float(ext.height())
        coords = [float(ext.ymax) - span * (i + 0.5) / len(vals)
                  for i in range(len(vals))]
    else:
        span = float(ext.width())
        coords = [float(ext.xmin) + span * (i + 0.5) / len(vals)
                  for i in range(len(vals))]
    nd = None
    try:
        d = get_display(layer)
        if d is not None and getattr(d, "use_nodata", True):
            nd = getattr(d, "nodata", None)
            nd = None if nd is None else float(nd)
    except Exception:
        _log.exception("silent exception in sample_axis")
        nd = None
    if nd is None:
        try:
            lnd = _layer_nodata(layer)
            nd = None if lnd is None else float(lnd)
        except Exception:
            _log.exception("silent exception in sample_axis")
            nd = None
    out = []
    for v in vals:
        if v != v or (nd is not None and abs(v - nd) < 1e-9):
            out.append(None)
        else:
            out.append(v)
    return coords, out


def nodata_rgba(display):
    if display is None:
        return None
    rgba = parse_color_rgba(getattr(display, "nodata_color", ""))
    if rgba is None or rgba[3] <= 0:
        return None
    return rgba


def bg_rgba(display):
    if display is None or not getattr(display, "bg_enabled", False):
        return None
    if getattr(display, "bg_value", None) is None:
        return None
    rgba = parse_color_rgba(getattr(display, "bg_color", "") or "")
    if rgba is None or rgba[3] <= 0:
        return None
    return rgba


def bg_value(display):
    if display is None or not getattr(display, "bg_enabled", False):
        return None
    bv = getattr(display, "bg_value", None)
    if bv is None:
        return None
    try:
        return float(bv)
    except Exception:
        _log.exception("silent exception in bg_value")
        return None


def _norm_rgb_bands(value):
    if value is None:
        return None
    try:
        seq = list(value)
    except Exception:
        _log.exception("silent exception in _norm_rgb_bands")
        return None
    if len(seq) != 3:
        return None
    out = []
    for v in seq:
        try:
            n = int(v)
        except Exception:
            _log.exception("silent exception in _norm_rgb_bands")
            return None
        if n < 1:
            return None
        out.append(n)
    return tuple(out)


def _norm_color_map(value):
    if not value:
        return {}
    out = {}
    try:
        items = list(value.items())
    except Exception:
        _log.exception("silent exception in _norm_color_map")
        return {}
    for k, v in items:
        s = str(v or "").strip()
        if not s:
            continue
        if parse_color_rgba(s) is None:
            continue
        h = s.lstrip("#")
        out[str(k)] = ("#" + h).upper()
    return out


def _norm_class_colors(value):
    if not value:
        return []
    try:
        items = list(value)
    except Exception:
        _log.exception("silent exception in _norm_class_colors")
        return []
    out = []
    for v in items:
        s = str(v or "").strip()
        if s and parse_color_rgba(s) is not None:
            out.append(("#" + s.lstrip("#")).upper())
        else:
            out.append("")
    return out


def _norm_class_breaks(value):
    if not value:
        return []
    try:
        items = list(value)
    except Exception:
        _log.exception("silent exception in _norm_class_breaks")
        return []
    out = []
    for v in items:
        try:
            out.append(float(v))
        except Exception:
            _log.exception("silent exception in _norm_class_breaks")
            return []
    return out


def _norm_class_mode(value):
    m = str(value or "").strip()
    return m if m in CLASS_MODE_LABELS else DEFAULT_CLASS_MODE


class GgsRasterDisplay:

    __slots__ = ("opacity", "stretch", "low", "high", "vmin", "vmax",
                 "band", "gamma", "nodata", "use_nodata", "nodata_color",
                 "bg_enabled", "bg_value", "bg_color",
                 "ramp", "invert_ramp", "interp", "interp_out",
                 "rgb_bands", "color_map", "use_colormap",
                 "class_n",
                 "class_colors",
                 "class_breaks",
                 "class_mode",
                 "alpha_band",
                 "stretch_ref_band",
                 "stddev_k",
                 "anno_max", "anno_min")

    def __init__(self, opacity=1.0, stretch=STRETCH_PERCENTILE, low=2.0,
                 high=98.0, vmin=None, vmax=None, band=0, gamma=1.0,
                 nodata=None, use_nodata=True, nodata_color="",
                 bg_enabled=False, bg_value=None, bg_color="",
                 ramp=RAMP_NONE, invert_ramp=False, interp="nearest",
                 interp_out="nearest", rgb_bands=None, color_map=None,
                 use_colormap=False, class_n=0, class_colors=None,
                 class_breaks=None, class_mode=DEFAULT_CLASS_MODE,
                 alpha_band=0, stretch_ref_band=0, stddev_k=2.0,
                 anno_max="", anno_min=""):
        self.opacity = float(opacity)
        self.stretch = str(stretch)
        self.low = float(low)
        self.high = float(high)
        self.vmin = vmin
        self.vmax = vmax
        self.band = int(band or 0)
        self.gamma = float(gamma or 1.0)
        self.nodata = nodata
        self.use_nodata = bool(use_nodata)
        self.nodata_color = str(nodata_color or "")
        self.bg_enabled = bool(bg_enabled)
        self.bg_value = None if bg_value is None else float(bg_value)
        self.bg_color = str(bg_color or "")
        self.ramp = str(ramp or RAMP_NONE)
        self.invert_ramp = bool(invert_ramp)
        self.interp = _rs.normalize(interp)
        self.interp_out = _rs.normalize(interp_out)
        self.rgb_bands = _norm_rgb_bands(rgb_bands)
        self.color_map = _norm_color_map(color_map)
        self.use_colormap = bool(use_colormap)
        self.class_n = max(0, int(class_n or 0))
        self.class_colors = _norm_class_colors(class_colors)
        self.class_breaks = _norm_class_breaks(class_breaks)
        self.class_mode = _norm_class_mode(class_mode)
        try:
            self.alpha_band = max(0, int(alpha_band or 0))
        except Exception:
            _log.exception("silent exception in __init__")
            self.alpha_band = 0
        try:
            self.stretch_ref_band = max(0, int(stretch_ref_band or 0))
        except Exception:
            _log.exception("silent exception in __init__")
            self.stretch_ref_band = 0
        try:
            self.stddev_k = float(stddev_k or 2.0)
        except Exception:
            _log.exception("silent exception in __init__")
            self.stddev_k = 2.0
        self.anno_max = str(anno_max or "")
        self.anno_min = str(anno_min or "")

    def copy(self):
        return GgsRasterDisplay(
            opacity=self.opacity, stretch=self.stretch, low=self.low,
            high=self.high, vmin=self.vmin, vmax=self.vmax, band=self.band,
            gamma=self.gamma, nodata=self.nodata,
            use_nodata=self.use_nodata, nodata_color=self.nodata_color,
            bg_enabled=self.bg_enabled, bg_value=self.bg_value,
            bg_color=str(self.bg_color or ""),
            ramp=self.ramp, invert_ramp=self.invert_ramp,
            interp=self.interp, interp_out=self.interp_out,
            rgb_bands=self.rgb_bands, color_map=dict(self.color_map or {}),
            use_colormap=self.use_colormap, class_n=self.class_n,
            class_colors=list(self.class_colors or []),
            class_breaks=list(self.class_breaks or []),
            class_mode=str(self.class_mode or DEFAULT_CLASS_MODE),
            alpha_band=int(self.alpha_band or 0),
            stretch_ref_band=int(self.stretch_ref_band or 0),
            anno_max=str(self.anno_max or ""), anno_min=str(self.anno_min or ""))

    def clamp(self):
        self.opacity = min(1.0, max(0.0, self.opacity))
        if self.stretch not in STRETCH_LABELS:
            self.stretch = STRETCH_PERCENTILE
        if not (0.0 <= self.low < self.high <= 100.0):
            self.low, self.high = 2.0, 98.0
        self.gamma = min(5.0, max(0.1, self.gamma))
        self.stddev_k = min(5.0, max(0.5, float(getattr(self, "stddev_k", 2.0)
                                                       or 2.0)))
        self.band = max(0, int(self.band))
        self.ramp = str(self.ramp or RAMP_NONE)
        if (self.ramp != RAMP_NONE
                and ramp_control_points(self.ramp) is None):
            self.ramp = RAMP_NONE
        if self.nodata_color and parse_color_rgba(self.nodata_color) is None:
            self.nodata_color = ""
        self.bg_enabled = bool(getattr(self, "bg_enabled", False))
        try:
            self.bg_value = None if self.bg_value is None else float(self.bg_value)
        except Exception:
            _log.exception("silent exception in clamp")
            self.bg_value = None
        if self.bg_color and parse_color_rgba(self.bg_color) is None:
            self.bg_color = ""
        self.interp = _rs.normalize(self.interp)
        self.interp_out = _rs.normalize(self.interp_out)
        self.rgb_bands = _norm_rgb_bands(self.rgb_bands)
        self.color_map = _norm_color_map(self.color_map)
        self.use_colormap = bool(self.use_colormap) and int(self.band) != 0
        try:
            _cn = int(self.class_n or 0)
        except Exception:
            _log.exception("silent exception in clamp")
            _cn = 0
        self.class_n = 0 if _cn < 2 else min(64, _cn)
        self.class_colors = _norm_class_colors(self.class_colors)
        if self.class_n < 2:
            self.class_colors = []
        elif self.class_colors:
            self.class_colors = (list(self.class_colors[:self.class_n])
                                 + [""] * max(0, self.class_n
                                              - len(self.class_colors)))
            if not any(self.class_colors):
                self.class_colors = []
        self.class_breaks = _norm_class_breaks(self.class_breaks)
        if self.class_n < 2 or len(self.class_breaks) != self.class_n + 1:
            self.class_breaks = []
        else:
            for _i in range(1, len(self.class_breaks)):
                if not (self.class_breaks[_i] > self.class_breaks[_i - 1]):
                    self.class_breaks = []
                    break
        self.class_mode = _norm_class_mode(self.class_mode)
        try:
            self.alpha_band = max(0, min(200, int(self.alpha_band or 0)))
        except Exception:
            _log.exception("silent exception in clamp")
            self.alpha_band = 0
        try:
            self.stretch_ref_band = max(0, min(200,
                                               int(self.stretch_ref_band or 0)))
        except Exception:
            _log.exception("silent exception in clamp")
            self.stretch_ref_band = 0
        self.anno_max = str(getattr(self, "anno_max", "") or "").strip()[:48]
        self.anno_min = str(getattr(self, "anno_min", "") or "").strip()[:48]
        return self

    def is_default(self):
        d = GgsRasterDisplay()
        return self == d

    def key(self):
        return (round(self.opacity, 3),) + self.rgb_key()

    def rgb_key(self):
        return (self.stretch, round(self.low, 3), round(self.high, 3),
                self.vmin, self.vmax, self.band, round(self.gamma, 3),
                self.nodata if self.nodata is None else float(self.nodata),
                self.use_nodata, self.ramp, self.invert_ramp,
                self.interp, self.interp_out,
                self.rgb_bands, self.use_colormap,
                tuple(sorted((str(k), str(v))
                             for k, v in (self.color_map or {}).items())),
                str(self.nodata_color or ""),
                bool(self.bg_enabled),
                self.bg_value if self.bg_value is None else float(self.bg_value),
                str(self.bg_color or ""),
                int(self.class_n or 0),
                tuple(str(c or "") for c in (self.class_colors or [])),
                tuple(float(v) for v in (self.class_breaks or [])),
                int(self.alpha_band or 0),
                int(self.stretch_ref_band or 0),
                round(float(self.stddev_k), 3))

    def to_dict(self):
        return {"opacity": self.opacity, "stretch": self.stretch,
                "low": self.low, "high": self.high, "vmin": self.vmin,
                "vmax": self.vmax, "band": self.band, "gamma": self.gamma,
                "nodata": self.nodata, "use_nodata": self.use_nodata,
                "nodata_color": self.nodata_color,
                "bg_enabled": bool(self.bg_enabled),
                "bg_value": (float(self.bg_value)
                             if self.bg_value is not None else None),
                "bg_color": str(self.bg_color or ""),
                "class_n": self.class_n,
                "ramp": self.ramp, "invert_ramp": self.invert_ramp,
                "interp": self.interp, "interp_out": self.interp_out,
                "rgb_bands": (list(self.rgb_bands)
                              if self.rgb_bands else None),
                "color_map": dict(self.color_map or {}),
                "class_colors": (list(self.class_colors)
                                 if self.class_colors else None),
                "class_breaks": (list(self.class_breaks)
                                 if self.class_breaks else None),
                "class_mode": str(self.class_mode or DEFAULT_CLASS_MODE),
                "alpha_band": int(self.alpha_band or 0),
                "stretch_ref_band": int(self.stretch_ref_band or 0),
                "anno_max": (str(self.anno_max) if self.anno_max else None),
                "anno_min": (str(self.anno_min) if self.anno_min else None),
                "stddev_k": float(self.stddev_k),
                "use_colormap": bool(self.use_colormap)}

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {})
        d = cls()
        for k in cls.__slots__:
            if k in data and data[k] is not None:
                setattr(d, k, data[k])
        return d.clamp()

    def __eq__(self, other):
        if not isinstance(other, GgsRasterDisplay):
            return NotImplemented
        return self.key() == other.key()

    def __repr__(self):
        return ("<GgsRasterDisplay opacity=%.2f %s %.1f-%.1f band=%d "
                "gamma=%.2f>" % (self.opacity, self.stretch, self.low,
                                 self.high, self.band, self.gamma))


def default_display(layer):
    d = GgsRasterDisplay()
    try:
        if palette(layer):
            d.band = 1
            d.use_colormap = True
            return d
    except Exception:
        _log.exception("silent exception in default_display")
    try:
        n = int(layer.band_count() or 0)
    except Exception:
        _log.exception("silent exception in default_display")
        n = 0
    if n >= 3:
        d.band = 0
        d.rgb_bands = default_rgb_bands(n)
    elif n > 0:
        d.band = 1
        d.ramp = DEFAULT_PSEUDO_RAMP
    return d


def default_rgb_bands(count):
    try:
        n = int(count or 0)
    except Exception:
        _log.exception("silent exception in default_rgb_bands")
        return None
    if n <= 0:
        return None
    return (min(1, n), min(2, n), min(3, n))


def get_display(layer):
    d = getattr(layer, "_raster_display", None)
    if isinstance(d, GgsRasterDisplay):
        try:
            d.opacity = float(layer.opacity())
        except Exception:
            _log.exception("silent exception in get_display")
        return d
    d = default_display(layer)
    try:
        d.opacity = float(layer.opacity())
    except Exception:
        _log.exception("silent exception in get_display")
    try:
        layer._raster_display = d
    except Exception:
        _log.exception("silent exception in get_display")
    return d


def set_display(layer, display):
    if layer is None or not isinstance(display, GgsRasterDisplay):
        return
    display.clamp()
    try:
        layer._raster_display = display
        layer.set_opacity(display.opacity)
    except Exception:
        _log.exception("silent exception in set_display")
    _bump(layer)


def reset_display(layer):
    set_display(layer, default_display(layer))


def _bump(layer):
    try:
        layer._render_version = int(
            layer.__dict__.get("_render_version", 0)) + 1
    except Exception:
        _log.exception("silent exception in _bump")


def display_key(layer, display=None, with_opacity=False):
    try:
        d = display if display is not None else get_display(layer)
        return d.key() if with_opacity else d.rgb_key()
    except Exception:
        _log.exception("silent exception in display_key")
        d = GgsRasterDisplay()
        return d.key() if with_opacity else d.rgb_key()


_SAMPLE_CACHE = {}
_SAMPLE_LIMIT = 24

_STATS_CACHE = {}
_STATS_LIMIT = 64


def clear_sample_cache(layer=None):
    for cache in (_SAMPLE_CACHE, _STATS_CACHE):
        if layer is None:
            cache.clear()
            continue
        for key in [k for k, v in cache.items() if v[0]() is layer]:
            cache.pop(key, None)
    try:
        from ggis.io import raster_pyramid as _pyr
        src = None
        if layer is not None:
            src = layer.source() if hasattr(layer, "source") else None
            if not src:
                return
        _pyr.clear_quicklook(src)
    except Exception:
        _log.exception("silent exception in clear_sample_cache")


def sample_array(layer, max_size=SAMPLE_SIZE, band=0):
    if layer is None:
        return None, None
    key = (id(layer), int(band or 0), int(max_size))
    hit = _SAMPLE_CACHE.get(key)
    if hit is not None and hit[0]() is layer:
        return hit[1], hit[2]
    _SAMPLE_CACHE.pop(key, None)

    arr, ext = _read_sample(layer, max_size, band)
    if arr is not None:
        if len(_SAMPLE_CACHE) >= _SAMPLE_LIMIT:
            _SAMPLE_CACHE.pop(next(iter(_SAMPLE_CACHE)), None)
        try:
            _SAMPLE_CACHE[key] = (weakref.ref(layer), arr, ext)
        except TypeError:
            exc_note("sample_array @ ggis/core/style/raster_display.py:1936")
            pass
    return arr, ext


def _read_sample(layer, max_size, band):
    try:
        ext = layer.extent()
        if ext is None or ext.is_empty():
            return None, None
        sw = sh = 0
        try:
            sw, sh = int(layer.width() or 0), int(layer.height() or 0)
        except Exception:
            _log.exception("silent exception in _read_sample")
            sw = sh = 0
        if sw > 0 and sh > 0:
            ratio = min(float(max_size) / sw, float(max_size) / sh)
            ratio = min(1.0, ratio)
            ow = max(1, int(round(sw * ratio)))
            oh = max(1, int(round(sh * ratio)))
        else:
            ow = oh = max(1, int(max_size))
        bands = [int(band)] if band else None

        try:
            from ggis.io import raster_pyramid as _pyr
            src = layer.source() if hasattr(layer, "source") else None
            if src:
                arr_a, ok = _pyr.read_overview(src, ext, (ow, oh), bands=bands)
                if ok and arr_a is not None:
                    return np.asarray(arr_a), ext
        except Exception:
            _log.exception("silent exception in _read_sample")

        try:
            from ggis.io import raster_pyramid as _pyr
            src = layer.source() if hasattr(layer, "source") else None
            if src:
                thumb = _pyr.read_thumbnail(src)
                if thumb is not None:
                    return thumb, ext
        except Exception:
            _log.exception("silent exception in _read_sample")

        try:
            from ggis.io import raster_pyramid as _pyr
            src = layer.source() if hasattr(layer, "source") else None
            if src:
                q = _pyr.quicklook(src, (ow, oh), bands=bands)
                if q is not None:
                    return np.asarray(q), ext
        except Exception:
            _log.exception("silent exception in _read_sample")

        arr, _ = layer.read_window(ext, (ow, oh), resample=1, bands=bands)
        if arr is None:
            return None, None
        return np.asarray(arr), ext
    except Exception:
        _log.exception("silent exception in _read_sample")
        return None, None


def stats_for(layer, display=None, band=0):
    d = display or get_display(layer)
    band = int(band or d.band or 0)
    nd = effective_nodata(layer, d)
    lo, hi = (float(d.low), float(d.high)) if d is not None else (2.0, 98.0)
    key = (id(layer), band, None if nd is None else float(nd),
           round(lo, 4), round(hi, 4))
    hit = _STATS_CACHE.get(key)
    if hit is not None and hit[0]() is layer:
        return hit[1]
    _STATS_CACHE.pop(key, None)

    arr, _ = sample_array(layer, band=band)
    st = band_stats(arr, nd, percentiles=(lo, hi))
    if len(_STATS_CACHE) >= _STATS_LIMIT:
        _STATS_CACHE.pop(next(iter(_STATS_CACHE)), None)
    try:
        _STATS_CACHE[key] = (weakref.ref(layer), st)
    except TypeError:
        exc_note("stats_for @ ggis/core/style/raster_display.py:2053")
        pass
    return st


def effective_nodata(layer, display):
    if display is not None:
        if not display.use_nodata:
            return None
        if display.nodata is not None:
            return float(display.nodata)
    return _layer_nodata(layer)


def _layer_nodata(layer):
    try:
        if getattr(layer, "use_nodata", True):
            return layer.nodata()
    except Exception:
        _log.exception("silent exception in _layer_nodata")
    return None


def _flat_finite(arr, nodata=None):
    if arr is None:
        return np.zeros(0, dtype="float64")
    try:
        a = np.asarray(arr).ravel()
    except Exception:
        _log.exception("silent exception in _flat_finite")
        return np.zeros(0, dtype="float64")
    if a.size == 0:
        return a.astype("float64")
    try:
        a = a.astype("float64", copy=False)
    except (TypeError, ValueError):
        exc_note("_flat_finite @ ggis/core/style/raster_display.py:2094")
        return np.zeros(0, dtype="float64")
    a = a[np.isfinite(a)]
    if nodata is not None:
        try:
            a = a[a != float(nodata)]
        except Exception:
            _log.exception("silent exception in _flat_finite")
    return a


def band_stats(arr, nodata=None, percentiles=(2.0, 98.0)):
    v = _flat_finite(arr, nodata)
    out = {"count": int(v.size), "min": None, "max": None, "mean": None,
           "std": None, "median": None, "p_low": None, "p_high": None}
    if v.size == 0:
        return out
    out["min"] = float(v.min())
    out["max"] = float(v.max())
    out["mean"] = float(v.mean())
    out["std"] = float(v.std())
    try:
        out["median"] = float(np.median(v))
    except Exception:
        _log.exception("silent exception in band_stats")
        out["median"] = None
    lo, hi = percentiles
    out["p_low"] = float(np.percentile(v, lo))
    out["p_high"] = float(np.percentile(v, hi))
    return out


def histogram(arr, bins=256, nodata=None, vmin=None, vmax=None):
    v = _flat_finite(arr, nodata)
    if v.size and (vmin is None or vmax is None):
        s = band_stats(arr, nodata)
        if s["count"] == 0:
            return np.zeros(bins, dtype="int64"), np.zeros(bins + 1)
        if vmin is None:
            vmin = s["p_low"]
        if vmax is None:
            vmax = s["p_high"]
        if not (vmin < vmax):
            vmin, vmax = s["min"], s["max"]
    if v.size == 0 or vmin is None or vmax is None or not (vmin < vmax):
        return np.zeros(bins, dtype="int64"), np.zeros(bins + 1)
    counts, edges = np.histogram(v, bins=int(bins), range=(float(vmin),
                                                           float(vmax)))
    return counts.astype("int64"), edges


def resolve_stretch(arr, nodata, display):
    if display is None:
        return None
    if display.stretch == STRETCH_NONE:
        return None
    s = band_stats(arr, nodata, percentiles=(display.low, display.high))
    return limits_from_stats(s, display)


def limits_from_stats(stats, display):
    if display is None or stats is None:
        return None
    if display.stretch == STRETCH_NONE:
        return None
    if display.stretch == STRETCH_CUSTOM:
        if display.vmin is None or display.vmax is None:
            lo, hi = stats.get("min"), stats.get("max")
            return (lo, hi) if (lo is not None and hi is not None
                                and lo < hi) else None
        lo, hi = float(display.vmin), float(display.vmax)
        return (lo, hi) if lo < hi else None
    if not stats.get("count") or stats.get("min") is None:
        return None
    if display.stretch == STRETCH_MINMAX:
        lo, hi = stats["min"], stats["max"]
    elif display.stretch == STRETCH_STDDEV:
        mu = stats.get("mean")
        sd = stats.get("std")
        if mu is None or not sd:
            lo, hi = stats["min"], stats["max"]
        else:
            _k = float(getattr(display, "stddev_k", 2.0) or 2.0)
            lo = max(float(stats["min"]), float(mu) - _k * float(sd))
            hi = min(float(stats["max"]), float(mu) + _k * float(sd))
    elif display.stretch in (STRETCH_HIST_EQ, STRETCH_HIST_MATCH):
        lo, hi = stats["min"], stats["max"]
    else:
        lo, hi = stats.get("p_low"), stats.get("p_high")
        if lo is None or hi is None or not (lo < hi):
            lo, hi = stats["min"], stats["max"]
    return (lo, hi) if lo < hi else None


def _gauss_ppf(p):
    p = np.clip(np.asarray(p, dtype="float64"), 1e-9, 1.0 - 1e-9)
    x = 2.0 * p - 1.0
    a = 0.147
    ln = np.log1p(-x * x)
    t = 2.0 / (np.pi * a) + ln / 2.0
    y = np.sqrt(np.sqrt(t * t - ln / a) - t)
    return np.sign(x) * np.sqrt(2.0) * y


def hist_stretch(values, nodata=None, mode=STRETCH_HIST_EQ, bins=256,
                 sample_max=None, target_cdf=None):
    a = np.asarray(values)
    if a.ndim == 3:
        a = a[0]
    a = a.ravel()
    if a.dtype.kind == "f":
        a = a[np.isfinite(a)]
    if nodata is not None:
        try:
            a = a[a != nodata]
        except Exception:
            _log.exception("silent exception in hist_stretch")
    n_keep = int(sample_max or (SAMPLE_SIZE * SAMPLE_SIZE))
    if a.size < 4:
        return None, None
    if a.size > n_keep:
        idx = np.linspace(0, a.size - 1, n_keep).astype("int64")
        a = a[idx]
    lo, hi = float(np.min(a)), float(np.max(a))
    if not (hi > lo):
        return None, None
    k = max(8, int(bins))
    counts, edges = np.histogram(a, bins=k, range=(lo, hi))
    cdf = np.cumsum(counts).astype("float64")
    total = float(cdf[-1]) or 1.0
    cdf /= total
    if str(mode) == STRETCH_HIST_MATCH:
        tg = None
        if target_cdf is not None:
            try:
                _c = np.asarray(target_cdf, dtype="float64").ravel()
                _c = _c[np.isfinite(_c)]
                if _c.size >= 4:
                    tg = np.interp(np.linspace(0.0, 1.0, k),
                                   np.linspace(0.0, 1.0, _c.size), _c)
                    _lo = float(tg.min())
                    _sp = float(tg.max()) - _lo
                    tg = (tg - _lo) / (_sp if _sp > 0 else 1.0)
                    tg = np.maximum.accumulate(tg)
            except Exception:
                _log.exception("silent exception in hist_stretch")
                tg = None
        if tg is None:
            t = np.linspace(1.0 / (2.0 * k), 1.0 - 1.0 / (2.0 * k), k)
            target = _gauss_ppf(t)
            span = float(target.max() - target.min()) or 1.0
            tg = (target - target.min()) / span
        out = np.interp(cdf, tg, np.linspace(0.0, 255.0, k))
    else:
        out = cdf * 255.0
    centers = (edges[:-1] + edges[1:]) * 0.5
    return centers, out


def hist_map(values, edges, out):
    if edges is None or out is None:
        return None
    try:
        a = np.asarray(values, dtype="float32")
        g = np.interp(a, np.asarray(edges, dtype="float64"),
                      np.asarray(out, dtype="float64"))
        return np.clip(g, 0.0, 255.0).astype("uint8")
    except Exception:
        _log.exception("silent exception in hist_map")
        return None


_HIST_CACHE = {}


def layer_hist_map(layer, display=None, band=0):
    d = display if display is not None else get_display(layer)
    if d is None:
        return None
    st = str(getattr(d, "stretch", "") or "")
    if st not in (STRETCH_HIST_EQ, STRETCH_HIST_MATCH):
        return None
    try:
        key = (id(layer), display_key(layer, d), int(band or 0))
    except Exception:
        _log.exception("silent exception in layer_hist_map")
        key = None
    if key is not None:
        hit = _HIST_CACHE.get(key)
        if hit is not None:
            return hit
    edges = out = None
    try:
        arr, _ext = sample_array(layer, band=band)
        if arr is not None and getattr(arr, "size", 0):
            nd = effective_nodata(layer, d)
            tg = None
            if st == STRETCH_HIST_MATCH:
                ref = int(getattr(d, "stretch_ref_band", 0) or 0)
                if ref > 0 and ref != int(band or 0):
                    try:
                        rarr, _re = sample_array(layer, band=ref)
                        if rarr is not None and getattr(rarr, "size", 0):
                            _redges, rout = hist_stretch(
                                rarr, nd, STRETCH_HIST_EQ)
                            if rout is not None and len(rout) >= 4:
                                tg = np.asarray(rout, dtype="float64") / 255.0
                    except Exception:
                        _log.exception("silent exception in layer_hist_map")
                        tg = None
            edges, out = hist_stretch(arr, nd, st, target_cdf=tg)
    except Exception:
        _log.exception("silent exception in layer_hist_map")
        edges = out = None
    if edges is None:
        return None
    if key is not None:
        if len(_HIST_CACHE) > 64:
            _HIST_CACHE.clear()
        _HIST_CACHE[key] = (edges, out)
    return (edges, out)


def layer_limits(layer, display=None, band=0):
    d = display if display is not None else get_display(layer)
    if d is None or d.stretch == STRETCH_NONE:
        return None
    if (str(getattr(d, "stretch", "") or "") == STRETCH_CUSTOM
            and d.vmin is not None and d.vmax is not None):
        lo, hi = float(d.vmin), float(d.vmax)
        return (lo, hi) if lo < hi else None
    return limits_from_stats(stats_for(layer, d, band=band), d)


def layer_limits_multi(layer, display=None, count=3, first=1):
    if count <= 0:
        return None
    out = []
    for b in range(int(first), int(first) + int(count)):
        out.append(layer_limits(layer, display, band=b))
    if all(x is None for x in out):
        return None
    return out


def gamma_lut(gamma):
    g = float(gamma or 1.0)
    if abs(g - 1.0) < 1e-6:
        return None
    x = np.arange(256, dtype="float64") / 255.0
    return np.clip((x ** (1.0 / g)) * 255.0, 0, 255).astype("uint8")


def raster_attribute_table(layer, max_unique=MAX_UNIQUE, band=0):
    out = {"kind": "none", "rows": [], "reason": "", "band": 1,
           "count": 0}
    if layer is None or not getattr(layer, "is_raster", lambda: False)():
        out["reason"] = "不是栅格图层"
        return out

    cmap = palette(layer)
    if cmap:
        counts = _value_counts(layer, max_unique=max(max_unique, len(cmap)))
        keys = sorted(k for k in cmap if counts.get(int(k)))
        if not keys:
            keys = sorted(cmap)
        rows = []
        for val in keys:
            name = _category_name(layer, val)
            rows.append((val, name, cmap[val], counts.get(int(val))))
        out.update(kind="palette", rows=rows, count=len(rows))
        return out

    arr, _ = sample_array(layer, band=band)
    if arr is None:
        out["reason"] = "读不出像素（数据源可能已失效）"
        return out
    nd = layer.nodata() if getattr(layer, "use_nodata", True) else None
    v = _flat_finite(arr, nd)
    if v.size == 0:
        out["reason"] = "整幅都是无数据值"
        return out
    uniq = np.unique(v)
    if uniq.size > int(max_unique):
        out["reason"] = ("连续值栅格（抽样 %d 个像素里有超过 %d 个不同取值），"
                         "没有属性表" % (min(v.size, SAMPLE_SIZE * SAMPLE_SIZE),
                                     int(max_unique)))
        return out
    vv, cc = np.unique(v, return_counts=True)
    rows = [(float(x), "", None, int(c))
            for x, c in zip(vv, cc) if not np.isnan(x)]
    out.update(kind="unique", rows=rows, count=len(rows))
    return out


def existing_values(layer, band=0, max_n=MAX_UNIQUE, cached_only=True):
    if layer is None:
        return None
    arr = None
    try:
        if cached_only:
            cands = []
            for _b in (band, 0, 1):
                if _b not in cands:
                    cands.append(_b)
            for _b in cands:
                hit = _SAMPLE_CACHE.get((id(layer), int(_b), int(SAMPLE_SIZE)))
                if hit is not None and hit[0]() is layer:
                    arr = hit[1]
                    break
            if arr is None:
                return None
        else:
            arr, _ext = sample_array(layer, band=band)
    except Exception:
        _log.exception("silent exception in existing_values")
        return None
    if arr is None:
        return None
    try:
        import numpy as np
        a = np.asarray(arr)
        if a.ndim == 3:
            a = a[0]
        if a.size == 0:
            return None
        if a.dtype.kind == "f":
            a = a[np.isfinite(a)]
        nd = _layer_nodata(layer)
        if nd is not None:
            a = a[a != nd]
        if a.size == 0:
            return None
        u = np.unique(a)
        if u.size == 0 or u.size > int(max_n):
            return None
        return [int(round(float(v))) for v in u]
    except Exception:
        _log.exception("silent exception in existing_values")
        return None


def band_is_integer(layer, band=0):
    ds = getattr(layer, "dataset", None)
    if callable(ds):
        try:
            ds = ds()
        except Exception:
            _log.exception("silent exception in band_is_integer")
            ds = None
    dtypes = getattr(ds, "dtypes", None) or ()
    if dtypes:
        if band and 1 <= int(band) <= len(dtypes):
            dt = str(dtypes[int(band) - 1])
        else:
            dt = str(dtypes[0])
    else:
        dt = str(getattr(layer, "dtype", lambda: "")() or "")
    return bool(dt) and "float" not in dt


def palette(layer):
    try:
        ds = layer.dataset()
        if ds is None:
            return {}
        for bidx in (1,):
            try:
                cm = ds.colormap(bidx)
            except Exception as _pe:
                if isinstance(_pe, ValueError):
                    cm = None
                else:
                    _log.exception("silent exception in palette")
                    cm = None
            if cm:
                return {int(k): tuple(int(x) for x in v)
                        for k, v in cm.items()}
    except Exception:
        _log.exception("silent exception in palette")
    return {}


def _category_name(layer, value):
    try:
        ds = layer.dataset()
        if ds is None:
            return ""
        tags = ds.tags(1) or {}
    except Exception:
        _log.exception("silent exception in _category_name")
        return ""
    for key in ("CATEGORY_NAMES", "CLASS_NAMES", "RAT_NAMES"):
        raw = tags.get(key)
        if not raw:
            continue
        try:
            names = [s for s in str(raw).split(",")]
            i = int(value)
            if 0 <= i < len(names):
                return names[i]
        except Exception:
            _log.exception("silent exception in _category_name")
            continue
    return ""


def _value_counts(layer, max_unique=MAX_UNIQUE):
    arr, _ = sample_array(layer)
    if arr is None:
        return {}
    try:
        nd = layer.nodata()
    except Exception:
        _log.exception("silent exception in _value_counts")
        nd = None
    v = _flat_finite(arr, nd)
    if v.size == 0:
        return {}
    vv, cc = np.unique(v, return_counts=True)
    if vv.size > int(max_unique):
        return {}
    return {int(x): int(c) for x, c in zip(vv, cc)}
