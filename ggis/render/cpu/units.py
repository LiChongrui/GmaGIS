# -*- coding: utf-8 -*-
from __future__ import annotations

from ggis.common.util.exc_report import exc_note
__all__ = [
    "POINTS_TO_MM", "INCH_TO_MM", "METERS_PER_DEGREE",
    "PX", "MM", "PT", "IN", "MU", "METERS_IN_MU", "PERCENT", "ALL_UNITS",
    "default_scale_factor", "MapUnitScale",
    "convert_to_painter_units", "convert_from_painter_units",
    "meters_to_map_units", "unit_from_text",
]

POINTS_TO_MM = 2.83464567

INCH_TO_MM = 25.4

METERS_PER_DEGREE = 111319.49079327358

PX = "px"
MM = "mm"
PT = "pt"
IN = "in"
MU = "mu"
METERS_IN_MU = "m"
PERCENT = "%"

ALL_UNITS = (PX, MM, PT, IN, MU, METERS_IN_MU, PERCENT)

_UNIT_ALIASES = {
    "px": PX, "pixel": PX, "pixels": PX, "像素": PX,
    "mm": MM, "millimeter": MM, "millimeters": MM, "毫米": MM,
    "pt": PT, "point": PT, "points": PT, "点": PT,
    "in": IN, "inch": IN, "inches": IN, "英寸": IN,
    "mu": MU, "mapunit": MU, "mapunits": MU, "地图单位": MU,
    "m": METERS_IN_MU, "meter": METERS_IN_MU, "meters": METERS_IN_MU,
    "米": METERS_IN_MU,
    "%": PERCENT, "percent": PERCENT, "percentage": PERCENT,
}


def unit_from_text(text, default=PX):
    try:
        k = str(text or "").strip().lower()
    except Exception:
        exc_note("unit_from_text @ ggis/render/cpu/units.py:83")
        return default
    return _UNIT_ALIASES.get(k, default)


def _is_set(v):
    try:
        return abs(float(v)) > 1e-9
    except Exception:
        exc_note("_is_set @ ggis/render/cpu/units.py:95")
        return False


def default_scale_factor(dpi=96.0):
    try:
        d = float(dpi)
    except Exception:
        exc_note("default_scale_factor @ ggis/render/cpu/units.py:107")
        d = 96.0
    return (d if d > 0 else 96.0) / INCH_TO_MM


class MapUnitScale(object):

    __slots__ = ("min_scale", "max_scale", "min_size_mm_enabled", "min_size_mm",
                 "max_size_mm_enabled", "max_size_mm")

    def __init__(self, min_scale=0.0, max_scale=0.0):
        self.min_scale = float(min_scale or 0.0)
        self.max_scale = float(max_scale or 0.0)
        self.min_size_mm_enabled = False
        self.min_size_mm = 0.0
        self.max_size_mm_enabled = False
        self.max_size_mm = 0.0

    def is_null(self):
        return (not _is_set(self.min_scale) and not _is_set(self.max_scale)
                and not self.min_size_mm_enabled
                and not self.max_size_mm_enabled)

    def compute_map_units_per_pixel(self, map_units_per_pixel, renderer_scale):
        mup = float(map_units_per_pixel or 0.0)
        rs = float(renderer_scale or 0.0)
        if mup <= 0.0 or rs <= 0.0:
            return mup
        if _is_set(self.min_scale):
            try:
                mup = min(mup / (rs / float(self.min_scale)), mup)
            except ZeroDivisionError:
                exc_note("compute_map_units_per_pixel @ ggis/render/cpu/units.py:157")
                pass
        if _is_set(self.max_scale):
            try:
                mup = max(mup / (rs / float(self.max_scale)), mup)
            except ZeroDivisionError:
                exc_note("compute_map_units_per_pixel @ ggis/render/cpu/units.py:162")
                pass
        return mup


def meters_to_map_units(meters, map_unit_is_degrees=False, center_lat=None):
    try:
        m = float(meters)
    except Exception:
        exc_note("meters_to_map_units @ ggis/render/cpu/units.py:182")
        return 0.0
    if not map_unit_is_degrees:
        return m
    f = 1.0 / METERS_PER_DEGREE
    if center_lat is not None:
        try:
            import math
            c = abs(math.cos(math.radians(float(center_lat))))
            del c
        except Exception:
            exc_note("meters_to_map_units @ ggis/render/cpu/units.py:194")
            pass
    return m * f


def convert_to_painter_units(size, unit, scale_factor,
                             map_units_per_pixel=0.0,
                             map_unit_scale=None,
                             renderer_scale=0.0,
                             symbology_reference_scale=0.0,
                             map_unit_is_degrees=False):
    try:
        s = float(size)
    except Exception:
        exc_note("convert_to_painter_units @ ggis/render/cpu/units.py:232")
        s = 0.0
    u = unit_from_text(unit)
    sf = float(scale_factor or 0.0)
    mup = float(map_units_per_pixel or 0.0)
    rs = float(renderer_scale or 0.0)
    hack = False
    factor = 1.0

    if u == MM:
        factor = sf
    elif u == PT:
        factor = sf / POINTS_TO_MM
    elif u == IN:
        factor = sf * INCH_TO_MM
    elif u in (METERS_IN_MU, MU):
        if u == METERS_IN_MU:
            s = meters_to_map_units(s, map_unit_is_degrees=map_unit_is_degrees)
        if mup > 0.0:
            mus = map_unit_scale
            m = (mus.compute_map_units_per_pixel(mup, rs)
                 if isinstance(mus, MapUnitScale) else mup)
            factor = (1.0 / m) if m > 0.0 else 1.0
        else:
            hack = True
            factor = sf / POINTS_TO_MM
    else:
        factor = 1.0

    out = s * factor

    if u == MU and isinstance(map_unit_scale, MapUnitScale):
        if map_unit_scale.min_size_mm_enabled:
            out = max(out, float(map_unit_scale.min_size_mm) * sf)
        if map_unit_scale.max_size_mm_enabled:
            out = min(out, float(map_unit_scale.max_size_mm) * sf)

    if hack:
        out = min(100.0, max(10.0, out))
    elif symbology_reference_scale and symbology_reference_scale > 0 and rs > 0:
        out *= float(symbology_reference_scale) / rs

    return out


def convert_from_painter_units(size, unit, scale_factor,
                               map_units_per_pixel=0.0,
                               map_unit_is_degrees=False):
    try:
        s = float(size)
    except Exception:
        exc_note("convert_from_painter_units @ ggis/render/cpu/units.py:290")
        s = 0.0
    u = unit_from_text(unit)
    sf = float(scale_factor or 0.0)
    mup = float(map_units_per_pixel or 0.0)

    if u == MM:
        factor = (1.0 / sf) if sf else 1.0
    elif u == PT:
        factor = (POINTS_TO_MM / sf) if sf else 1.0
    elif u == IN:
        factor = (1.0 / (sf * INCH_TO_MM)) if sf else 1.0
    elif u in (METERS_IN_MU, MU):
        if u == METERS_IN_MU:
            per = meters_to_map_units(1.0, map_unit_is_degrees=map_unit_is_degrees)
            s = (s / per) if per else s
        factor = mup if mup > 0.0 else 1.0
    else:
        factor = 1.0
    return s * factor
