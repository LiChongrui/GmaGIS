# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from . import units as U

__all__ = ["GgsRenderContext"]


class GgsRenderContext(object):

    __slots__ = ("_extent", "_w", "_h", "_dpi", "_crs", "_mup",
                 "_renderer_scale", "_reference_scale", "_map_unit_is_degrees")

    def __init__(self, extent, output_width, output_height, dpi=96.0,
                 destination_crs=None, map_units_per_pixel=1.0,
                 renderer_scale=0.0, symbology_reference_scale=0.0):
        self._extent = extent
        try:
            self._w = max(0, int(output_width))
            self._h = max(0, int(output_height))
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/context.py:49")
            self._w, self._h = 0, 0
        try:
            self._dpi = float(dpi)
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/context.py:53")
            self._dpi = 96.0
        if not (self._dpi > 0):
            self._dpi = 96.0
        self._crs = destination_crs
        try:
            self._mup = float(map_units_per_pixel)
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/context.py:60")
            self._mup = 1.0
        try:
            self._renderer_scale = float(renderer_scale or 0.0)
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/context.py:64")
            self._renderer_scale = 0.0
        try:
            self._reference_scale = float(symbology_reference_scale or 0.0)
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/context.py:68")
            self._reference_scale = 0.0
        is_deg = False
        try:
            is_deg = str(destination_crs.map_units() or "") == "degrees"
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/context.py:75")
            is_deg = False
        self._map_unit_is_degrees = is_deg

    def extent(self):
        return self._extent

    def output_size(self):
        return (self._w, self._h)

    def output_width(self):
        return self._w

    def output_height(self):
        return self._h

    def dpi(self):
        return self._dpi

    def destination_crs(self):
        return self._crs

    def map_units_per_pixel(self):
        return self._mup

    def renderer_scale(self):
        return self._renderer_scale

    def scale_factor(self):
        return U.default_scale_factor(self._dpi)

    def map_unit_is_degrees(self):
        return self._map_unit_is_degrees

    def is_ready(self):
        try:
            if self._extent is None or self._extent.is_empty():
                return False
        except Exception:
            exc_note("is_ready @ ggis/render/cpu/context.py:127")
            return False
        return self._w > 0 and self._h > 0

    def convert(self, size, unit=U.PX, scale=None):
        return U.convert_to_painter_units(
            size, unit, self.scale_factor(),
            map_units_per_pixel=self._mup,
            map_unit_scale=scale,
            renderer_scale=self._renderer_scale,
            symbology_reference_scale=self._reference_scale,
            map_unit_is_degrees=self._map_unit_is_degrees)

    def from_painter(self, size, unit=U.PX):
        return U.convert_from_painter_units(
            size, unit, self.scale_factor(),
            map_units_per_pixel=self._mup,
            map_unit_is_degrees=self._map_unit_is_degrees)

    @classmethod
    def from_map_settings(cls, settings, project_crs=None,
                          symbology_reference_scale=0.0, dpi=None):
        try:
            size = settings.output_size()
            w, h = int(size.width()), int(size.height())
        except Exception:
            exc_note("from_map_settings @ ggis/render/cpu/context.py:165")
            w = h = 0
        try:
            d = float(dpi) if dpi is not None else float(settings.dpi())
        except Exception:
            exc_note("from_map_settings @ ggis/render/cpu/context.py:169")
            d = 96.0
        crs = project_crs
        if crs is None:
            try:
                crs = settings.destination_crs()
            except Exception:
                exc_note("from_map_settings @ ggis/render/cpu/context.py:175")
                crs = None
        try:
            mup = float(settings.map_units_per_pixel())
        except Exception:
            exc_note("from_map_settings @ ggis/render/cpu/context.py:179")
            mup = 1.0
        rs = 0.0
        try:
            rs = float(settings.scale(crs) if crs is not None else settings.scale())
        except Exception:
            exc_note("from_map_settings @ ggis/render/cpu/context.py:184")
            rs = 0.0
        extent = None
        try:
            extent = settings.extent()
        except Exception:
            exc_note("from_map_settings @ ggis/render/cpu/context.py:189")
            extent = None
        return cls(extent, w, h, dpi=d, destination_crs=crs,
                   map_units_per_pixel=mup, renderer_scale=rs,
                   symbology_reference_scale=symbology_reference_scale)

    def __repr__(self):
        return ("<GgsRenderContext %dx%d dpi=%.1f mup=%.6g scale=%.0f %s>"
                % (self._w, self._h, self._dpi, self._mup,
                   self._renderer_scale,
                   "deg" if self._map_unit_is_degrees else "linear"))
