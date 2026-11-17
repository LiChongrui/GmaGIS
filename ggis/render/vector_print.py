# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (QBrush, QPainterPath, QPen,
                           QPolygonF)

from .rasterize import flat_coords
from .symbol import default_symbol

__all__ = ["draw_layer_vector", "vector_vertex_count",
           "VECTOR_VERTEX_BUDGET"]

VECTOR_VERTEX_BUDGET = 600_000

PRINT_LOD_PIXELS = 0.9

_LINE_FACTORY = {}


def _line_factory_colors(dark_bg):
    key = bool(dark_bg)
    got = _LINE_FACTORY.get(key)
    if got is None:
        try:
            s = default_symbol("line", 0, dark_bg=key)
            got = (s.fill.name(), s.stroke.name())
        except Exception:
            exc_note("_line_factory_colors @ ggis/render/vector_print.py:61")
            got = ("", "")
        _LINE_FACTORY[key] = got
    return got


def resolve_symbols(layer, symbol=None):
    kind = layer.base_kind()
    if symbol is not None:
        return symbol, None, None
    try:
        from .renderers import get_renderer
        renderer = get_renderer(layer)
        try:
            syms = list(renderer.symbols())
        except Exception:
            exc_note("resolve_symbols @ ggis/render/vector_print.py:84")
            syms = []
        if not syms:
            syms = [default_symbol(kind, 0)]
        try:
            cls = renderer.class_array(layer)
        except Exception:
            exc_note("resolve_symbols @ ggis/render/vector_print.py:90")
            cls = None
        if cls is None or len(syms) <= 1:
            return syms[0], None, None
        return syms[0], syms, cls
    except Exception:
        exc_note("resolve_symbols @ ggis/render/vector_print.py:95")
        return default_symbol(kind, 0), None, None


def _fid_set(layer, settings, fids=None):
    if fids is not None:
        a = np.asarray(list(fids) if not isinstance(fids, np.ndarray)
                       else fids)
        return a.astype(np.int64, copy=False)
    n = layer.feature_count()
    if n <= 0:
        return np.zeros(0, dtype=np.int64)
    ext = settings.extent()
    try:
        if ext.contains(layer.extent()):
            return np.arange(n, dtype=np.int64)
    except Exception:
        exc_note("_fid_set @ ggis/render/vector_print.py:112")
        pass
    if n < 2000:
        return np.arange(n, dtype=np.int64)
    try:
        return np.asarray(layer.query_bbox_array(ext.xmin, ext.ymin,
                                                 ext.xmax, ext.ymax),
                          dtype=np.int64)
    except Exception:
        exc_note("_fid_set @ ggis/render/vector_print.py:120")
        return np.arange(n, dtype=np.int64)


def _lod_tol(settings, kind):
    if kind == "point":
        return 0.0
    try:
        mupp = settings.map_units_per_pixel()
    except Exception:
        exc_note("_lod_tol @ ggis/render/vector_print.py:129")
        mupp = 0.0
    return max(0.0, PRINT_LOD_PIXELS * mupp) if mupp > 0 else 0.0


def vector_vertex_count(layer, settings, fids=None):
    kind = layer.base_kind()
    if kind == "point":
        return int(_fid_set(layer, settings, fids).size)
    try:
        data = flat_coords(layer, _lod_tol(settings, kind), kind=kind)
    except Exception:
        exc_note("vector_vertex_count @ ggis/render/vector_print.py:141")
        return 0
    ids = _fid_set(layer, settings, fids)
    if ids.size == 0:
        return 0
    try:
        part_geom = data["part_geom"]
        starts = data["part_starts"]
        ends = data["part_ends"]
    except Exception:
        exc_note("vector_vertex_count @ ggis/render/vector_print.py:150")
        return 0
    hit = np.isin(part_geom, ids)
    if not hit.any():
        return 0
    return int((ends[hit] - starts[hit]).sum())


def draw_layer_vector(painter, layer, settings, symbol=None, fids=None,
                      opacity=None):
    if layer is None or not settings.is_ready():
        return 0
    if layer.is_raster():
        rp = None
        try:
            from .cpu.raster import GgsBuiltinRasterPainter
            rp = GgsBuiltinRasterPainter()
        except Exception:
            exc_note("draw_layer_vector @ ggis/render/vector_print.py:175")
            rp = None
        if rp is None:
            try:
                from .painter import GgsRasterPainter
                rp = GgsRasterPainter()
            except Exception:
                exc_note("draw_layer_vector @ ggis/render/vector_print.py:181")
                return 0
        try:
            rp.MAX_PIXELS = max(rp.MAX_PIXELS, 4096)
        except Exception:
            exc_note("draw_layer_vector @ ggis/render/vector_print.py:186")
            pass
        op = layer.opacity() if opacity is None else opacity
        try:
            return 1 if rp.draw(painter, layer, settings, op) else 0
        except Exception:
            exc_note("draw_layer_vector @ ggis/render/vector_print.py:192")
            try:
                from .painter import GgsRasterPainter
                rp2 = GgsRasterPainter()
                try:
                    rp2.MAX_PIXELS = max(rp2.MAX_PIXELS, 4096)
                except Exception:
                    exc_note("draw_layer_vector @ ggis/render/vector_print.py:198")
                    pass
                return 1 if rp2.draw(painter, layer, settings, op) else 0
            except Exception:
                exc_note("draw_layer_vector @ ggis/render/vector_print.py:201")
                return 0
    if not layer.is_vector():
        return 0
    try:
        ext = settings.extent()
        if not ext.intersects(layer.extent()):
            return 0
    except Exception:
        exc_note("draw_layer_vector @ ggis/render/vector_print.py:209")
        return 0

    kind = layer.base_kind()
    sym, syms, classes = resolve_symbols(layer, symbol)
    if opacity is not None:
        syms = _with_opacity(syms or [sym], opacity)
        sym = syms[0]
    ids = _fid_set(layer, settings, fids)
    if ids.size == 0:
        return 0
    tol = _lod_tol(settings, kind)

    if kind == "point":
        return _points(painter, layer, settings, sym, ids, syms, classes)
    if kind == "line":
        return _lines(painter, layer, settings, sym, ids, tol, syms,
                      classes)
    return _polygons(painter, layer, settings, sym, ids, tol, syms,
                     classes)


def _with_opacity(symbols, opacity):
    from .symbol import GgsSymbol
    out = []
    for s in symbols:
        if s is None:
            out.append(s)
            continue
        c = GgsSymbol(fill=s.fill, stroke=s.stroke, width=s.width,
                      size=s.size, opacity=s.opacity * float(opacity),
                      fill_alpha=s.fill_alpha, dark_bg=s.dark_bg,
                      unit=getattr(s, "unit", None))
        out.append(c)
    return out


def _points(painter, layer, settings, symbol, ids, symbols, classes):
    try:
        xy, offsets, rows, counts = _xy_of(layer)
    except Exception:
        exc_note("_points @ ggis/render/vector_print.py:254")
        return 0
    if xy.shape[0] == 0:
        return 0
    cnt = counts[ids]
    first = rows[ids]
    tot = int(cnt.sum())
    if tot == 0:
        return 0
    idx = np.repeat(first, cnt)
    if tot != ids.size:
        idx = idx + (np.arange(tot, dtype=np.int64)
                     - np.repeat(np.cumsum(cnt) - cnt, cnt))
    pts = xy[idx]

    ext = settings.extent()
    sx, sy = settings.scale_x(), settings.scale_y()
    px = (pts[:, 0].astype(np.float64) - ext.xmin) * sx
    py = (ext.ymax - pts[:, 1].astype(np.float64)) * sy
    w = float(settings.output_width())
    h = float(settings.output_height())
    keep = (px >= -8) & (px <= w + 8) & (py >= -8) & (py <= h + 8)
    px, py = px[keep], py[keep]
    if px.size == 0:
        return 0

    fid_of_pt = np.repeat(ids, cnt)[keep] if tot != ids.size \
        else ids[keep]

    _d_px = symbol.px_size() if callable(
        getattr(symbol, "px_size", None)) else float(symbol.size or 0.0)
    radius = max(0.6, float(_d_px or 0.0) * 0.5)
    if symbols is None or len(symbols) <= 1:
        path = QPainterPath()
        for i in range(px.size):
            path.addEllipse(QPointF(float(px[i]), float(py[i])),
                            radius, radius)
        _paint_shape(painter, path, symbol, is_line=False)
        return int(px.size)

    cls_of_pt = np.asarray(classes, dtype=np.int64)[fid_of_pt]
    for k in np.unique(cls_of_pt):
        if k <= 0 or k > len(symbols):
            continue
        sel = cls_of_pt == k
        s = symbols[k - 1]
        path = QPainterPath()
        for i in np.nonzero(sel)[0]:
            path.addEllipse(QPointF(float(px[i]), float(py[i])),
                            radius, radius)
        _paint_shape(painter, path, s, is_line=False)
    return int(px.size)


def _xy_of(layer):
    from .painter import _xy_cache
    return _xy_cache(layer)


def _tolerance_loop(layer, settings, kind, tol, budget):
    data = None
    for _ in range(6):
        data = flat_coords(layer, tol, kind=kind)
        n = int(data["xy"].shape[0]) if data else 0
        if n <= budget or tol <= 0:
            return data
        tol = max(tol, 1e-9) * 3.0
    return data


def _lines(painter, layer, settings, symbol, ids, tol, symbols, classes):
    data = _tolerance_loop(layer, settings, kind="line", tol=tol,
                           budget=VECTOR_VERTEX_BUDGET)
    if not data or data["xy"].shape[0] < 2:
        return 0
    xy = data["xy"]
    starts = data["part_starts"]
    ends = data["part_ends"]
    part_geom = data["part_geom"]
    hit = np.isin(part_geom, ids)
    if not hit.any():
        return 0

    ext = settings.extent()
    sx, sy = settings.scale_x(), settings.scale_y()
    gx = (xy[:, 0].astype(np.float64) - ext.xmin) * sx
    gy = (ext.ymax - xy[:, 1].astype(np.float64)) * sy
    n_drawn = 0

    if symbols is None or len(symbols) <= 1:
        path = QPainterPath()
        for p in np.nonzero(hit)[0]:
            a, b = int(starts[p]), int(ends[p])
            if b - a < 2:
                continue
            path.moveTo(float(gx[a]), float(gy[a]))
            for i in range(a + 1, b):
                path.lineTo(float(gx[i]), float(gy[i]))
            n_drawn += 1
        _paint_shape(painter, path, symbol, is_line=True)
        return n_drawn

    cls_of_part = np.asarray(classes, dtype=np.int64)[part_geom]
    for k in np.unique(cls_of_part[hit]):
        if k <= 0 or k > len(symbols):
            continue
        s = symbols[k - 1]
        path = QPainterPath()
        for p in np.nonzero(hit & (cls_of_part == k))[0]:
            a, b = int(starts[p]), int(ends[p])
            if b - a < 2:
                continue
            path.moveTo(float(gx[a]), float(gy[a]))
            for i in range(a + 1, b):
                path.lineTo(float(gx[i]), float(gy[i]))
            n_drawn += 1
        _paint_shape(painter, path, s, is_line=True)
    return n_drawn


def _polygons(painter, layer, settings, symbol, ids, tol, symbols, classes):
    data = _tolerance_loop(layer, settings, kind="polygon", tol=tol,
                           budget=VECTOR_VERTEX_BUDGET)
    if not data or data["xy"].shape[0] < 3:
        return 0
    xy = data["xy"]
    starts = data["part_starts"]
    ends = data["part_ends"]
    part_geom = data["part_geom"]
    hit = np.isin(part_geom, ids)
    if not hit.any():
        return 0

    ext = settings.extent()
    sx, sy = settings.scale_x(), settings.scale_y()
    gx = (xy[:, 0].astype(np.float64) - ext.xmin) * sx
    gy = (ext.ymax - xy[:, 1].astype(np.float64)) * sy

    def build(sel):
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for p in np.nonzero(sel)[0]:
            a, b = int(starts[p]), int(ends[p])
            if b - a < 3:
                continue
            poly = QPolygonF([QPointF(float(gx[i]), float(gy[i]))
                              for i in range(a, b)])
            path.addPolygon(poly)
            path.closeSubpath()
        return path

    if symbols is None or len(symbols) <= 1:
        _paint_shape(painter, build(hit), symbol, is_line=False)
        return int(hit.sum())

    cls_of_part = np.asarray(classes, dtype=np.int64)[part_geom]
    for k in np.unique(cls_of_part[hit]):
        if k <= 0 or k > len(symbols):
            continue
        _paint_shape(painter, build(hit & (cls_of_part == k)),
                     symbols[k - 1], is_line=False)
    return int(hit.sum())


_CAP_QT = {"flat": Qt.PenCapStyle.FlatCap,
           "square": Qt.PenCapStyle.SquareCap,
           "round": Qt.PenCapStyle.RoundCap}
_JOIN_QT = {"miter": Qt.PenJoinStyle.MiterJoin,
            "bevel": Qt.PenJoinStyle.BevelJoin,
            "round": Qt.PenJoinStyle.RoundJoin}


def _pen_ends(symbol, pen):
    try:
        pen.setCapStyle(_CAP_QT.get(str(symbol.cap or "flat"),
                                    Qt.PenCapStyle.FlatCap))
    except Exception:
        exc_note("_pen_ends @ ggis/render/vector_print.py:445")
        pass
    try:
        pen.setJoinStyle(_JOIN_QT.get(str(symbol.join or "bevel"),
                                      Qt.PenJoinStyle.BevelJoin))
    except Exception:
        exc_note("_pen_ends @ ggis/render/vector_print.py:450")
        pass
    return pen


def _paint_shape(painter, path, symbol, is_line=False):
    if path.isEmpty() or symbol is None:
        return
    _w_px = symbol.px_width() if callable(
        getattr(symbol, "px_width", None)) else float(symbol.width or 1.0)
    w = max(0.4, float(_w_px or 1.0))
    dash = None
    try:
        _pat = symbol.line_pattern()
        if _pat:
            dash = [float(v) for v in _pat]
    except Exception:
        exc_note("_paint_shape @ ggis/render/vector_print.py:470")
        dash = None
    if is_line:
        fill_c = symbol.fill_color()
        stroke_c = symbol.stroke_color()
        pen_col = stroke_c
        try:
            d_fill, d_stroke = _line_factory_colors(
                getattr(symbol, "dark_bg", True))
            if (d_fill and fill_c.name() != d_fill
                    and stroke_c.name() == d_stroke):
                pen_col = fill_c
        except Exception:
            exc_note("_paint_shape @ ggis/render/vector_print.py:491")
            pass
        pen = QPen(pen_col, w)
        _pen_ends(symbol, pen)
        if dash:
            try:
                pen.setDashPattern(dash)
            except Exception:
                exc_note("_paint_shape @ ggis/render/vector_print.py:498")
                pass
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        return
    fill = symbol.fill_color()
    stroke = symbol.stroke_color()
    if fill.alpha() > 0:
        br = None
        try:
            if symbol.has_fill_pattern():
                from .cpu.paint import pattern_brush as _pb
                br = _pb(fill, symbol.fill_style, symbol.px_fill_spacing(),
                         symbol.px_fill_width())
        except Exception:
            exc_note("_paint_shape @ ggis/render/vector_print.py:513")
            br = None
        painter.setBrush(QBrush(fill) if br is None else br)
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
    if stroke.alpha() > 0:
        pen = QPen(stroke, w)
        _pen_ends(symbol, pen)
        if dash:
            try:
                pen.setDashPattern(dash)
            except Exception:
                exc_note("_paint_shape @ ggis/render/vector_print.py:524")
                pass
        painter.setPen(pen)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPath(path)
