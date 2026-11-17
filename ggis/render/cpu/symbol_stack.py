# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from collections import OrderedDict

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPolygonF

from . import paint as P
from . import units as U

__all__ = ["SymbolStack", "symbol_stack_from_ggs_symbol", "clear_tile_cache"]

_TILES = OrderedDict()
_TILE_MAX = 64


_MARKER_VECTOR_MAX = 20000


def clear_tile_cache():
    _TILES.clear()


def _marker_tile_cached(layer, ctx, opacity, dpr):
    try:
        sf = round(float(ctx.scale_factor()), 4)
        mup = round(float(ctx.map_units_per_pixel()), 6)
    except Exception:
        exc_note("_marker_tile_cached @ ggis/render/cpu/symbol_stack.py:71")
        sf, mup = 0.0, 0.0
    key = (
        id(layer),
        round(float(getattr(layer, "size", 0.0) or 0.0), 4),
        str(getattr(layer, "size_unit", U.PX)),
        round(float(getattr(layer, "stroke_width", 0.0) or 0.0), 4),
        str(getattr(layer, "stroke_width_unit", U.PX)),
        str(getattr(layer, "color", "")),
        round(float(getattr(layer, "alpha", 1.0) or 0.0), 6),
        str(getattr(layer, "stroke_color", "")),
        round(float(getattr(layer, "stroke_alpha", 1.0) or 0.0), 6),
        round(float(opacity), 6), sf, mup, round(float(dpr), 4))
    hit = _TILES.get(key)
    if hit is not None:
        _TILES.move_to_end(key)
        return hit
    tile, side = P.marker_tile(layer, ctx, opacity, dpr)
    _TILES[key] = (tile, side)
    while len(_TILES) > _TILE_MAX:
        _TILES.popitem(last=False)
    return (tile, side)

_STROKE_ALPHA_FALLBACK = 90.0 / 255.0


class SymbolStack(object):

    __slots__ = ("_layers", "_opacity")

    def __init__(self, layers=None, opacity=1.0):
        self._layers = list(layers or [])
        self._opacity = float(opacity if opacity is not None else 1.0)

    def add(self, layer):
        self._layers.append(layer)
        return self

    def layers(self):
        return list(self._layers)

    def opacity(self):
        return self._opacity

    def set_opacity(self, value):
        self._opacity = float(value if value is not None else 1.0)

    def is_empty(self):
        return not self._layers

    def kinds(self):
        return [getattr(l, "kind", "") for l in self._layers]

    def to_dict(self):
        return {"opacity": round(self._opacity, 6),
                "layers": [l.to_dict() for l in self._layers]}

    def __repr__(self):
        return "<SymbolStack %s x%d opacity=%.3g>" % (
            "+".join(self.kinds()) or "-", len(self._layers), self._opacity)

    def render(self, painter, kind, ctx, path=None, points=None):
        if not self._layers or ctx is None:
            return 0
        n = 0
        op = self._opacity
        if kind == "marker":
            n += self._render_markers(painter, ctx, points, op)
            return n
        if path is None or path.isEmpty():
            return 0
        for lyr in self._layers:
            k = getattr(lyr, "kind", "")
            if k == "fill":
                if P.draw_fill(painter, path, lyr, ctx, op):
                    n += 1
            elif k == "line":
                if P.draw_line(painter, path, lyr, ctx, op):
                    n += 1
        return n

    def _render_markers(self, painter, ctx, points, opacity, force_vector=False):
        if not points:
            return 0
        dpr = 1.0
        try:
            dpr = float(painter.device().devicePixelRatioF() or 1.0)
        except Exception:
            exc_note("_render_markers @ ggis/render/cpu/symbol_stack.py:208")
            dpr = 1.0
        if dpr <= 0.0:
            dpr = 1.0
        n = 0
        for lyr in self._layers:
            if getattr(lyr, "kind", "") != "marker":
                continue
            try:
                size = ctx.convert(lyr.size, lyr.size_unit)
            except Exception:
                exc_note("_render_markers @ ggis/render/cpu/symbol_stack.py:218")
                size = float(getattr(lyr, "size", 0.0) or 0.0)
            if size <= 0.0:
                continue
            ox = oy = 0.0
            try:
                if lyr.offset_x or lyr.offset_y:
                    ox = ctx.convert(lyr.offset_x, lyr.offset_unit)
                    oy = ctx.convert(lyr.offset_y, lyr.offset_unit)
            except Exception:
                exc_note("_render_markers @ ggis/render/cpu/symbol_stack.py:227")
                ox = oy = 0.0
            if force_vector or len(points) <= _MARKER_VECTOR_MAX:
                brush, pen = P.marker_pens(lyr, ctx, opacity)
                poly = QPolygonF()
                poly.reserve(len(points))
                ap = poly.append
                for x, y in points:
                    ap(QPointF(float(x) + ox, float(y) + oy))
                if not poly.isEmpty():
                    painter.save()
                    try:
                        painter.setRenderHint(
                            QPainter.RenderHint.Antialiasing, True)
                        sw = 0.0
                        try:
                            sw = max(0.0, float(pen.widthF()))
                        except Exception:
                            exc_note("_render_markers @ ggis/render/cpu/symbol_stack.py:259")
                            sw = 0.0
                        pen_out = QPen(pen)
                        pen_out.setStyle(Qt.PenStyle.SolidLine)
                        pen_out.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen_out.setWidthF(size + sw)
                        painter.setPen(pen_out)
                        painter.drawPoints(poly)
                        pen_in = QPen(pen_out)
                        pen_in.setColor(brush.color())
                        pen_in.setWidthF(max(0.1, size))
                        painter.setPen(pen_in)
                        painter.drawPoints(poly)
                    finally:
                        painter.restore()
                    n += 1
                continue

            tile, side = _marker_tile_cached(lyr, ctx, opacity, dpr)
            if tile is None or side <= 0.0:
                continue
            half = side / 2.0
            painter.save()
            try:
                painter.setRenderHint(
                    QPainter.RenderHint.SmoothPixmapTransform, True)
                for x, y in points:
                    painter.drawImage(
                        QRectF(float(x) + ox - half, float(y) + oy - half,
                               side, side), tile)
            finally:
                painter.restore()
            n += 1
        return n


def _num(v, default):
    try:
        out = float(v() if callable(v) else v)
    except Exception:
        exc_note("_num @ ggis/render/cpu/symbol_stack.py:306")
        return default
    return out if out == out else default


def symbol_stack_from_ggs_symbol(sym, kind, clamp=True):
    k = str(kind or "")
    if sym is None:
        return SymbolStack()
    fill = sym.fill if hasattr(sym, "fill") else "#4C9BE8"
    stroke = sym.stroke if hasattr(sym, "stroke") else "#000000"
    try:
        fill_name = fill.name()
    except Exception:
        exc_note("symbol_stack_from_ggs_symbol @ ggis/render/cpu/symbol_stack.py:333")
        fill_name = str(fill)
    try:
        stroke_name = stroke.name()
    except Exception:
        exc_note("symbol_stack_from_ggs_symbol @ ggis/render/cpu/symbol_stack.py:337")
        stroke_name = str(stroke)
    unit = U.unit_from_text(getattr(sym, "unit", None), U.PX)
    width = _num(getattr(sym, "width", 1.0), 1.0)
    size = _num(getattr(sym, "size", 4.0), 4.0)
    _sf = U.default_scale_factor(96.0)

    def _clamp_px(v, lo, hi):
        px_ = U.convert_to_painter_units(v, unit, _sf)
        px_ = max(lo, min(px_, hi))
        return U.convert_from_painter_units(px_, unit, _sf)
    try:
        fa = float(sym.fill_color().alphaF())
    except Exception:
        exc_note("symbol_stack_from_ggs_symbol @ ggis/render/cpu/symbol_stack.py:360")
        fa = 1.0
    try:
        sa = float(sym.stroke_color().alphaF())
    except Exception:
        exc_note("symbol_stack_from_ggs_symbol @ ggis/render/cpu/symbol_stack.py:364")
        sa = 1.0
    dash = None
    try:
        _pat = sym.line_pattern()
        if _pat:
            dash = [float(v) for v in _pat]
    except Exception:
        exc_note("symbol_stack_from_ggs_symbol @ ggis/render/cpu/symbol_stack.py:374")
        dash = None
    fill_style = str(getattr(sym, "fill_style", "solid") or "solid")
    brush_spacing = _num(getattr(sym, "px_fill_spacing", None), 8.0)
    brush_width = _num(getattr(sym, "px_fill_width", None), 1.0)
    cap = str(getattr(sym, "cap", "flat") or "flat")
    join = str(getattr(sym, "join", "bevel") or "bevel")

    if k == "polygon":
        if clamp:
            width = _clamp_px(width, 0.6, 3.0)
        if sa <= 0.0:
            sa = _STROKE_ALPHA_FALLBACK
        return SymbolStack([P.FillLayer(
            color=fill_name, alpha=fa, stroke_color=stroke_name,
            stroke_alpha=sa, width=width, width_unit=unit,
            join=join, style="solid", brush_style=fill_style,
            dash=dash, brush_spacing=brush_spacing,
            brush_width=brush_width,
            rule=P.WINDING)])
    if k == "line":
        if clamp:
            width = _clamp_px(width, 0.8, 6.0)
        if sa <= 0.0:
            sa = _STROKE_ALPHA_FALLBACK
        return SymbolStack([P.LineLayer(
            color=stroke_name, alpha=sa, width=width, width_unit=unit,
            join=join, cap=cap, style="solid", dash=dash)])
    if k == "point":
        if clamp:
            width = _clamp_px(width, 0.8, 6.0)
        if sa <= 0.0:
            sa = _STROKE_ALPHA_FALLBACK
        return SymbolStack([P.MarkerLayer(
            color=fill_name, alpha=fa, size=size, size_unit=unit,
            stroke_color=stroke_name, stroke_alpha=sa,
            stroke_width=width, stroke_width_unit=unit,
            join=join, cap=cap, stroke_style="solid", shape="circle",
            brush_style=fill_style, brush_spacing=brush_spacing,
            brush_width=brush_width, dash=dash)])
    return SymbolStack([P.FillLayer(color=fill_name, alpha=fa,
                                    stroke_color=stroke_name,
                                    stroke_alpha=sa, width=width,
                                    width_unit=unit, rule=P.WINDING,
                                    join=join, brush_style=fill_style,
                                    dash=dash,
                                    brush_spacing=brush_spacing,
                                    brush_width=brush_width)])
