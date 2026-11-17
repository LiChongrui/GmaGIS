# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math

__all__ = [
    "WHEEL_DELTA_UNIT", "DEFAULT_WHEEL_STEP", "FINE_ZOOM_DIVISOR",
    "DEFAULT_BOUNDS_POINTS",
    "SCROLL_PHASE_NONE", "SCROLL_PHASE_BEGIN", "SCROLL_PHASE_UPDATE",
    "SCROLL_PHASE_END",
    "wheel_zoom_factor", "signed_wheel_factor", "is_scroll_end",
    "anchor_from_mouse", "zoom_extent", "pan_center",
    "densified_bounds", "map_units_per_pixel",
]

WHEEL_DELTA_UNIT = 120.0

DEFAULT_WHEEL_STEP = 1.5

FINE_ZOOM_DIVISOR = 20.0

DEFAULT_BOUNDS_POINTS = 1000

SCROLL_PHASE_NONE = 0
SCROLL_PHASE_BEGIN = 1
SCROLL_PHASE_UPDATE = 2
SCROLL_PHASE_END = 3


def wheel_zoom_factor(delta_y, step=DEFAULT_WHEEL_STEP, ctrl=False):
    try:
        d = float(delta_y)
    except Exception:
        exc_note("wheel_zoom_factor @ ggis/render/cpu/interaction.py:106")
        return 1.0
    if d == 0:
        return 1.0
    try:
        s = float(step) if float(step) > 1.0 else DEFAULT_WHEEL_STEP
    except Exception:
        exc_note("wheel_zoom_factor @ ggis/render/cpu/interaction.py:112")
        s = DEFAULT_WHEEL_STEP
    f = s
    f = 1.0 + (f - 1.0) / WHEEL_DELTA_UNIT * abs(d)
    if ctrl:
        f = 1.0 + (f - 1.0) / FINE_ZOOM_DIVISOR
    return f


def signed_wheel_factor(delta_y, step=DEFAULT_WHEEL_STEP, ctrl=False):
    f = wheel_zoom_factor(delta_y, step, ctrl)
    if f <= 0:
        return 1.0
    return (1.0 / f) if float(delta_y or 0) > 0 else f


def is_scroll_end(event):
    try:
        method = getattr(event, "phase", None)
        if not callable(method):
            return False
        phase = method()
        if phase is None:
            return False
        return int(getattr(phase, "value", phase)) == SCROLL_PHASE_END
    except Exception:
        exc_note("is_scroll_end @ ggis/render/cpu/interaction.py:173")
        return False


def anchor_from_mouse(old_center, mouse_map, signed_factor):
    try:
        ox, oy = float(old_center[0]), float(old_center[1])
        mx, my = float(mouse_map[0]), float(mouse_map[1])
        k = float(signed_factor)
    except Exception:
        exc_note("anchor_from_mouse @ ggis/render/cpu/interaction.py:193")
        return old_center
    return (mx + (ox - mx) * k, my + (oy - my) * k)


def zoom_extent(extent, factor, center=None):
    if extent is None:
        return extent
    try:
        if extent.is_empty():
            return extent
        r = extent.copy()
        if center is None:
            r.scale(float(factor))
        else:
            r.scale(float(factor), center=(float(center[0]), float(center[1])))
        return r
    except Exception:
        exc_note("zoom_extent @ ggis/render/cpu/interaction.py:218")
        return extent


def pan_center(center, start_map, end_map):
    try:
        cx, cy = float(center[0]), float(center[1])
        sx, sy = float(start_map[0]), float(start_map[1])
        ex, ey = float(end_map[0]), float(end_map[1])
    except Exception:
        exc_note("pan_center @ ggis/render/cpu/interaction.py:241")
        return center
    return (cx - (ex - sx), cy - (ey - sy))


def densified_bounds(bounds, transform, points=DEFAULT_BOUNDS_POINTS):
    if bounds is None or transform is None:
        return None
    try:
        x0, y0, x1, y1 = (float(bounds[0]), float(bounds[1]),
                          float(bounds[2]), float(bounds[3]))
    except Exception:
        exc_note("densified_bounds @ ggis/render/cpu/interaction.py:270")
        return None
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0

    try:
        n = int(points)
    except Exception:
        exc_note("densified_bounds @ ggis/render/cpu/interaction.py:279")
        n = DEFAULT_BOUNDS_POINTS
    n = max(2, min(4096, n))
    k = max(2, int(math.sqrt(n)))
    xs = [x0 + (x1 - x0) * i / (k - 1) for i in range(k)]
    ys = [y0 + (y1 - y0) * j / (k - 1) for j in range(k)]

    out_x0 = out_y0 = float("inf")
    out_x1 = out_y1 = float("-inf")
    hit = 0
    for yy in ys:
        for xx in xs:
            try:
                p = transform(xx, yy)
            except Exception:
                exc_note("densified_bounds @ ggis/render/cpu/interaction.py:294")
                continue
            if p is None:
                continue
            try:
                px, py = float(p[0]), float(p[1])
            except Exception:
                exc_note("densified_bounds @ ggis/render/cpu/interaction.py:300")
                continue
            if not (math.isfinite(px) and math.isfinite(py)):
                continue
            hit += 1
            if px < out_x0:
                out_x0 = px
            if px > out_x1:
                out_x1 = px
            if py < out_y0:
                out_y0 = py
            if py > out_y1:
                out_y1 = py
    if hit == 0:
        return None
    return (out_x0, out_y0, out_x1, out_y1)


def map_units_per_pixel(width, height, extent):
    try:
        w = float(width)
        h = float(height)
        ew = float(extent.width())
        eh = float(extent.height())
    except Exception:
        exc_note("map_units_per_pixel @ ggis/render/cpu/interaction.py:331")
        return (0.0, 0.0)
    if w <= 0 or h <= 0:
        return (0.0, 0.0)
    return (ew / w, eh / h)
