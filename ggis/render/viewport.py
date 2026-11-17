# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QPointF, QSize, QSizeF

from ggis.core.crs.extent import GgsRectangle

__all__ = ["GgsMapSettings"]


class GgsMapSettings:

    def __init__(self, extent=None, size=None, dpi=96.0, destination_crs=None):
        self._extent = GgsRectangle()
        if extent is not None:
            self._extent = extent.copy()
        self._size = QSizeF(0, 0)
        if size is not None:
            self.set_output_size(size)
        self._dpi = float(dpi or 96.0)
        self._dst_crs = destination_crs
        self._lod_ref_w = 0.0

    def set_destination_crs(self, crs):
        if isinstance(crs, str):
            try:
                from ..core.crs import GgsCrs
                _c = GgsCrs.from_user_input(crs)
                if _c is not None and _c.is_valid():
                    crs = _c
            except Exception:
                exc_note("set_destination_crs @ ggis/render/viewport.py:73")
                pass
        self._dst_crs = crs
        return self

    def destination_crs(self):
        return self._dst_crs

    def set_extent(self, extent):
        self._extent = extent.copy() if extent is not None else GgsRectangle()
        return self

    def extent(self):
        return self._extent.copy()

    def set_output_size(self, size):
        if isinstance(size, QSizeF):
            self._size = QSizeF(size)
        elif isinstance(size, QSize):
            self._size = QSizeF(size.width(), size.height())
        else:
            try:
                self._size = QSizeF(float(size[0]), float(size[1]))
            except Exception:
                exc_note("set_output_size @ ggis/render/viewport.py:96")
                self._size = QSizeF(0, 0)
        return self

    def output_size(self):
        return QSizeF(self._size)

    def output_width(self):
        return float(self._size.width())

    def output_height(self):
        return float(self._size.height())

    def set_dpi(self, dpi):
        self._dpi = float(dpi or 96.0)

    def dpi(self):
        return self._dpi

    def set_lod_reference_width(self, w):
        try:
            self._lod_ref_w = max(0.0, float(w or 0.0))
        except Exception:
            exc_note("set_lod_reference_width @ ggis/render/viewport.py:124")
            self._lod_ref_w = 0.0
        return self

    def lod_reference_width(self):
        if self._lod_ref_w > 0:
            return self._lod_ref_w
        return float(self._size.width())

    def is_ready(self):
        return (not self._extent.is_empty()
                and self._size.width() > 0 and self._size.height() > 0)

    def map_units_per_pixel(self):
        if not self.is_ready():
            return 1.0
        w = self.lod_reference_width()
        if w <= 0:
            return 1.0
        return self._extent.width() / w

    def scale_x(self):
        w = self._extent.width()
        if w <= 0:
            return 1.0
        return self._size.width() / w

    def scale_y(self):
        h = self._extent.height()
        if h <= 0:
            return 1.0
        return self._size.height() / h

    def map_to_pixel(self, x, y):
        if not self.is_ready():
            return QPointF(0.0, 0.0)
        sx = (float(x) - self._extent.xmin) * self.scale_x()
        sy = (self._extent.ymax - float(y)) * self.scale_y()
        return QPointF(sx, sy)

    def pixel_to_map(self, px, py):
        if not self.is_ready():
            return (0.0, 0.0)
        x = self._extent.xmin + float(px) / self.scale_x()
        y = self._extent.ymax - float(py) / self.scale_y()
        return (x, y)

    def to_map_point(self, point):
        return self.pixel_to_map(point.x(), point.y())

    def map_to_pixel_rect(self, rect):
        from PySide6.QtCore import QRectF
        if not self.is_ready() or rect is None:
            return QRectF()
        p0 = self.map_to_pixel(rect.xmin, rect.ymax)
        p1 = self.map_to_pixel(rect.xmax, rect.ymin)
        return QRectF(p0, p1).normalized()

    def scale(self, crs=None):
        if not self.is_ready():
            return 1.0
        mupp = self.map_units_per_pixel()
        m_per_unit = 1.0
        if crs is not None:
            try:
                m_per_unit = float(crs.meters_per_unit())
            except Exception:
                exc_note("scale @ ggis/render/viewport.py:215")
                m_per_unit = 1.0
        meters_per_pixel = mupp * m_per_unit
        meters_on_screen = 0.0254 / max(self._dpi, 1.0)
        n = meters_per_pixel / meters_on_screen
        return n if n > 0 else 1.0

    def zoom(self, factor, anchor_px=None):
        if not self.is_ready() or not factor:
            return self
        if anchor_px is not None:
            ax, ay = self.pixel_to_map(anchor_px.x(), anchor_px.y())
            self._extent.scale(float(factor), center=(ax, ay))
        else:
            self._extent.scale(float(factor))
        return self

    def pan_pixels(self, dx, dy):
        if not self.is_ready():
            return self
        mx = dx / self.scale_x()
        my = dy / self.scale_y()
        self._extent.xmin -= mx
        self._extent.xmax -= mx
        self._extent.ymin += my
        self._extent.ymax += my
        return self

    def set_center(self, x, y):
        if not self.is_ready():
            return self
        w = self._extent.width() / 2.0
        h = self._extent.height() / 2.0
        self._extent.xmin = x - w
        self._extent.xmax = x + w
        self._extent.ymin = y - h
        self._extent.ymax = y + h
        return self

    def __repr__(self):
        return "GgsMapSettings(extent=%r, size=%dx%d)" % (
            self._extent, self._size.width(), self._size.height())
