# -*- coding: utf-8 -*-

import math
import logging
_log = logging.getLogger("gmagis")

__all__ = ["GgsRectangle"]


class GgsRectangle:

    __slots__ = ("xmin", "ymin", "xmax", "ymax")

    def __init__(self, xmin=0.0, ymin=0.0, xmax=0.0, ymax=0.0):
        self.xmin = float(xmin)
        self.ymin = float(ymin)
        self.xmax = float(xmax)
        self.ymax = float(ymax)
        self.normalize()

    @classmethod
    def from_points(cls, xs, ys):
        if xs is None or ys is None or len(xs) == 0 or len(ys) == 0:
            return cls()
        try:
            return cls(min(xs), min(ys), max(xs), max(ys))
        except Exception:
            _log.exception("silent exception in from_points")
            return cls()

    @classmethod
    def from_shapely(cls, geom):
        if geom is None or getattr(geom, "is_empty", True):
            return cls()
        try:
            b = geom.bounds
            return cls(b[0], b[1], b[2], b[3])
        except Exception:
            _log.exception("silent exception in from_shapely")
            return cls()

    def copy(self):
        return GgsRectangle(self.xmin, self.ymin, self.xmax, self.ymax)

    def normalize(self):
        if self.xmin > self.xmax:
            self.xmin, self.xmax = self.xmax, self.xmin
        if self.ymin > self.ymax:
            self.ymin, self.ymax = self.ymax, self.ymin
        return self

    def is_empty(self):
        return (self.xmax <= self.xmin) or (self.ymax <= self.ymin)

    def is_null(self):
        return self.is_empty()

    def is_degenerate(self):
        return self.xmax <= self.xmin or self.ymax <= self.ymin

    def ensure_minimum(self, min_span=None, force=False):
        if self.is_empty() and not force:
            return self
        w, h = self.width(), self.height()
        if w <= 0 and h <= 0:
            span = float(min_span) if min_span else 1.0
            cx, cy = self.xmin, self.ymin
            self.xmin, self.xmax = cx - span / 2.0, cx + span / 2.0
            self.ymin, self.ymax = cy - span / 2.0, cy + span / 2.0
            return self
        if w <= 0:
            span = float(min_span) if min_span else h * 0.2
            cx = self.xmin
            self.xmin, self.xmax = cx - span / 2.0, cx + span / 2.0
        if h <= 0:
            span = float(min_span) if min_span else w * 0.2
            cy = self.ymin
            self.ymin, self.ymax = cy - span / 2.0, cy + span / 2.0
        return self

    def width(self):
        return max(0.0, self.xmax - self.xmin)

    def height(self):
        return max(0.0, self.ymax - self.ymin)

    def area(self):
        return self.width() * self.height()

    def center(self):
        return ((self.xmin + self.xmax) / 2.0,
                (self.ymin + self.ymax) / 2.0)

    def x_center(self):
        return (self.xmin + self.xmax) / 2.0

    def y_center(self):
        return (self.ymin + self.ymax) / 2.0

    def as_tuple(self):
        return (self.xmin, self.ymin, self.xmax, self.ymax)

    def contains(self, x, y=None):
        if y is None:
            other = x
            return (other.xmin >= self.xmin and other.xmax <= self.xmax
                    and other.ymin >= self.ymin and other.ymax <= self.ymax)
        return (self.xmin <= x <= self.xmax) and (self.ymin <= y <= self.ymax)

    def intersects(self, other):
        if other is None or self.is_empty() or other.is_empty():
            return False
        return not (other.xmin > self.xmax or other.xmax < self.xmin
                    or other.ymin > self.ymax or other.ymax < self.ymin)

    def combine_extent_with(self, other):
        if other is None:
            return self
        if other.is_empty():
            return self
        if self.is_empty():
            self.xmin, self.ymin = other.xmin, other.ymin
            self.xmax, self.ymax = other.xmax, other.ymax
            return self
        self.xmin = min(self.xmin, other.xmin)
        self.ymin = min(self.ymin, other.ymin)
        self.xmax = max(self.xmax, other.xmax)
        self.ymax = max(self.ymax, other.ymax)
        return self

    @staticmethod
    def union(a, b):
        r = a.copy() if a is not None else GgsRectangle()
        r.combine_extent_with(b)
        return r

    def grow(self, factor_or_delta, y_delta=None):
        if self.is_empty():
            return self
        if y_delta is None:
            f = float(factor_or_delta)
            dx = self.width() * f
            dy = self.height() * f
        else:
            dx = float(factor_or_delta)
            dy = float(y_delta)
        self.xmin -= dx
        self.xmax += dx
        self.ymin -= dy
        self.ymax += dy
        return self

    def scale(self, factor, center=None):
        if self.is_empty():
            return self
        cx, cy = center if center else self.center()
        f = float(factor)
        self.xmin = cx + (self.xmin - cx) * f
        self.xmax = cx + (self.xmax - cx) * f
        self.ymin = cy + (self.ymin - cy) * f
        self.ymax = cy + (self.ymax - cy) * f
        return self.normalize()

    def expand_to_ratio(self, ratio):
        if self.is_empty() or ratio <= 0:
            return self
        w, h = self.width(), self.height()
        cur = w / h if h else ratio
        if abs(cur - ratio) < 1e-9:
            return self
        if cur < ratio:
            nw = h * ratio
            cx = self.x_center()
            self.xmin = cx - nw / 2.0
            self.xmax = cx + nw / 2.0
        else:
            nh = w / ratio
            cy = self.y_center()
            self.ymin = cy - nh / 2.0
            self.ymax = cy + nh / 2.0
        return self

    def buffered(self, factor_or_delta, y_delta=None):
        r = self.copy()
        return r.grow(factor_or_delta, y_delta)

    def intersect(self, other):
        if other is None or not self.intersects(other):
            return GgsRectangle()
        self.xmin = max(self.xmin, other.xmin)
        self.ymin = max(self.ymin, other.ymin)
        self.xmax = min(self.xmax, other.xmax)
        self.ymax = min(self.ymax, other.ymax)
        return self.normalize()

    def __repr__(self):
        return ("GgsRectangle(xmin=%.6f, ymin=%.6f, xmax=%.6f, ymax=%.6f)"
                % (self.xmin, self.ymin, self.xmax, self.ymax))

    def __eq__(self, other):
        return (isinstance(other, GgsRectangle)
                and math.isclose(self.xmin, other.xmin)
                and math.isclose(self.ymin, other.ymin)
                and math.isclose(self.xmax, other.xmax)
                and math.isclose(self.ymax, other.ymax))

    def __iter__(self):
        yield self.xmin
        yield self.ymin
        yield self.xmax
        yield self.ymax


def layer_extent(layer, dst_crs=None):
    if layer is None:
        return None
    try:
        e = layer.extent()
    except Exception:
        _log.exception("silent exception in layer_extent")
        return None
    if e is None or e.is_empty() or dst_crs is None:
        return e
    try:
        src_crs = layer.crs()
    except Exception:
        _log.exception("silent exception in layer_extent")
        src_crs = None
    try:
        from . import convert_bounds, crs_transformer
        b = convert_bounds((e.xmin, e.ymin, e.xmax, e.ymax),
                           crs_transformer(src_crs, dst_crs))
    except Exception:
        _log.exception("silent exception in layer_extent")
        return e
    if b is None:
        return e
    return GgsRectangle(b[0], b[1], b[2], b[3])
