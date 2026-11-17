# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen

from . import units as U

__all__ = [
    "FillLayer", "LineLayer", "MarkerLayer",
    "draw_fill", "draw_line", "draw_marker",
    "draw_polygon", "marker_path", "marker_tile",
    "fill_pen", "fill_brush", "line_pen", "marker_pens",
    "ODD_EVEN", "WINDING", "fill_rule", "EMPTY_RECT",
]

ODD_EVEN = "oddeven"
WINDING = "winding"

EMPTY_RECT = QRectF()

_JOIN = {
    "miter": Qt.PenJoinStyle.MiterJoin,
    "bevel": Qt.PenJoinStyle.BevelJoin,
    "round": Qt.PenJoinStyle.RoundJoin,
}
_CAP = {
    "flat": Qt.PenCapStyle.FlatCap,
    "square": Qt.PenCapStyle.SquareCap,
    "round": Qt.PenCapStyle.RoundCap,
}
_PEN_STYLE = {
    "solid": Qt.PenStyle.SolidLine,
    "none": Qt.PenStyle.NoPen,
    "dash": Qt.PenStyle.DashLine,
    "dot": Qt.PenStyle.DotLine,
    "dashdot": Qt.PenStyle.DashDotLine,
    "dashdotdot": Qt.PenStyle.DashDotDotLine,
}
_BRUSH_STYLE = {
    "solid": Qt.BrushStyle.SolidPattern,
    "none": Qt.BrushStyle.NoBrush,
    "horizontal": Qt.BrushStyle.HorPattern,
    "vertical": Qt.BrushStyle.VerPattern,
    "cross": Qt.BrushStyle.CrossPattern,
    "bdiagonal": Qt.BrushStyle.BDiagPattern,
    "fdiagonal": Qt.BrushStyle.FDiagPattern,
    "diagcross": Qt.BrushStyle.DiagCrossPattern,
}

def _enum(text, table, default):
    try:
        return table.get(str(text or "").strip().lower(), default)
    except Exception:
        exc_note("_enum @ ggis/render/cpu/paint.py:105")
        return default


PATTERN_NAMES = ("horizontal", "vertical", "diagonal", "back_diagonal",
                 "cross", "diagonal_cross")

_PATTERN_BRUSH_CACHE: dict = {}
_PATTERN_BRUSH_MAX = 16


def pattern_tile(kind, spacing, width, color):
    s = max(2, int(round(float(spacing))))
    t = max(1.0, float(width))
    k = str(kind or "")
    if k not in PATTERN_NAMES:
        return None
    img = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color))
        pen.setWidthF(t)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)

        def seg(x1, y1, x2, y2):
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        def diag_down():
            seg(0.0, 0.0, float(s), float(s))
            seg(0.0, -s, float(s), 0.0)
            seg(0.0, s, float(s), 2.0 * s)

        def diag_up():
            seg(0.0, float(s), float(s), 0.0)
            seg(0.0, 0.0, float(s), -s)
            seg(0.0, 2.0 * s, float(s), float(s))

        if k == "horizontal":
            seg(0.0, t / 2.0, float(s), t / 2.0)
        elif k == "vertical":
            seg(t / 2.0, 0.0, t / 2.0, float(s))
        elif k == "diagonal":
            diag_up()
        elif k == "back_diagonal":
            diag_down()
        elif k == "cross":
            seg(0.0, t / 2.0, float(s), t / 2.0)
            seg(t / 2.0, 0.0, t / 2.0, float(s))
        else:
            diag_up()
            diag_down()
    finally:
        p.end()
    return img


def pattern_brush(color, kind, spacing, width):
    try:
        key = (str(kind), round(float(spacing), 2), round(float(width), 2),
               int(QColor(color).rgba()))
    except Exception:
        exc_note("pattern_brush @ ggis/render/cpu/paint.py:183")
        return None
    hit = _PATTERN_BRUSH_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        img = pattern_tile(kind, spacing, width, color)
    except Exception:
        exc_note("pattern_brush @ ggis/render/cpu/paint.py:190")
        img = None
    if img is None:
        return None
    try:
        br = QBrush(img)
    except Exception:
        exc_note("pattern_brush @ ggis/render/cpu/paint.py:196")
        return None
    if len(_PATTERN_BRUSH_CACHE) >= _PATTERN_BRUSH_MAX:
        _PATTERN_BRUSH_CACHE.clear()
    _PATTERN_BRUSH_CACHE[key] = br
    return br


def apply_dash(pen, dash):
    if not dash:
        return pen
    try:
        pat = [float(v) for v in dash]
    except Exception:
        exc_note("apply_dash @ ggis/render/cpu/paint.py:215")
        return pen
    if len(pat) < 2 or len(pat) % 2 != 0 or any(v <= 0.0 for v in pat):
        return pen
    try:
        pen.setDashPattern(pat)
    except Exception:
        exc_note("apply_dash @ ggis/render/cpu/paint.py:221")
        pass
    return pen


def fill_rule(name):
    return (Qt.FillRule.WindingFill if str(name or "").strip().lower() == WINDING
            else Qt.FillRule.OddEvenFill)


def _color(rgb, alpha):
    c = QColor(str(rgb or "#000000"))
    if not c.isValid():
        c = QColor("#000000")
    try:
        a = float(alpha)
    except Exception:
        exc_note("_color @ ggis/render/cpu/paint.py:239")
        a = 1.0
    c.setAlphaF(0.0 if a <= 0.0 else (1.0 if a >= 1.0 else a))
    return c


class _Layer(object):

    __slots__ = ("kind", "color", "alpha", "offset_x", "offset_y",
                 "offset_unit")
    DEFAULT_UNIT = U.PX

    def __init__(self, color="#000000", alpha=1.0, offset_x=0.0, offset_y=0.0,
                 offset_unit=None):
        self.color = color
        self.alpha = float(alpha)
        self.offset_x = float(offset_x or 0.0)
        self.offset_y = float(offset_y or 0.0)
        self.offset_unit = offset_unit or self.DEFAULT_UNIT

    def to_dict(self):
        out = {"type": self.kind, "color": str(self.color),
               "alpha": round(float(self.alpha), 6)}
        if self.offset_x or self.offset_y:
            out["offset"] = [self.offset_x, self.offset_y]
            out["offset_unit"] = self.offset_unit
        return out

    def __repr__(self):
        return "<%s %s a=%.3g>" % (type(self).__name__, self.color, self.alpha)


class FillLayer(_Layer):

    __slots__ = ("stroke_color", "stroke_alpha", "width", "width_unit",
                 "join", "style", "brush_style", "fill_rule",
                 "dash", "brush_spacing", "brush_width")

    def __init__(self, color="#4C9BE8", alpha=1.0, stroke_color="#000000",
                 stroke_alpha=1.0, width=1.0, width_unit=None,
                 join="bevel", style="solid", brush_style="solid",
                 rule=WINDING, dash=None, brush_spacing=8.0,
                 brush_width=1.0, **kw):
        _Layer.__init__(self, color, alpha, **kw)
        self.kind = "fill"
        self.stroke_color = stroke_color
        self.stroke_alpha = float(stroke_alpha)
        self.width = float(width or 0.0)
        self.width_unit = width_unit or U.PX
        self.join = join
        self.style = style
        self.brush_style = brush_style
        self.fill_rule = rule
        self.dash = dash
        self.brush_spacing = float(brush_spacing or 8.0)
        self.brush_width = float(brush_width or 1.0)

    def to_dict(self):
        out = _Layer.to_dict(self)
        out.update({"stroke_color": str(self.stroke_color),
                    "stroke_alpha": round(float(self.stroke_alpha), 6),
                    "width": round(float(self.width), 4),
                    "width_unit": self.width_unit,
                    "join": self.join, "style": self.style,
                    "brush_style": self.brush_style,
                    "fill_rule": self.fill_rule})
        if self.dash:
            out["dash"] = [float(v) for v in self.dash]
        if str(self.brush_style or "") in PATTERN_NAMES:
            out["brush_spacing"] = round(float(self.brush_spacing), 3)
            out["brush_width"] = round(float(self.brush_width), 3)
        return out


class LineLayer(_Layer):

    __slots__ = ("width", "width_unit", "join", "cap", "style", "dash")

    def __init__(self, color="#4C9BE8", alpha=1.0, width=1.0, width_unit=None,
                 join="bevel", cap="flat", style="solid", dash=None, **kw):
        _Layer.__init__(self, color, alpha, **kw)
        self.kind = "line"
        self.width = float(width or 0.0)
        self.width_unit = width_unit or U.PX
        self.join = join
        self.cap = cap
        self.style = style
        self.dash = dash

    def to_dict(self):
        out = _Layer.to_dict(self)
        out.update({"width": round(float(self.width), 4),
                    "width_unit": self.width_unit, "join": self.join,
                    "cap": self.cap, "style": self.style})
        if self.dash:
            out["dash"] = [float(v) for v in self.dash]
        return out


class MarkerLayer(_Layer):

    __slots__ = ("size", "size_unit", "stroke_color", "stroke_alpha",
                 "stroke_width", "stroke_width_unit", "join", "cap",
                 "stroke_style", "shape",
                 "brush_style", "brush_spacing", "brush_width", "dash")

    def __init__(self, color="#4C9BE8", alpha=1.0, size=4.0, size_unit=None,
                 stroke_color="#000000", stroke_alpha=1.0, stroke_width=0.3,
                 stroke_width_unit=None, join="bevel", cap="flat",
                 stroke_style="solid", shape="circle",
                 brush_style="solid", brush_spacing=8.0, brush_width=1.0,
                 dash=None, **kw):
        _Layer.__init__(self, color, alpha, **kw)
        self.kind = "marker"
        self.size = float(size or 0.0)
        self.size_unit = size_unit or U.PX
        self.stroke_color = stroke_color
        self.stroke_alpha = float(stroke_alpha)
        self.stroke_width = float(stroke_width or 0.0)
        self.stroke_width_unit = stroke_width_unit or U.PX
        self.join = join
        self.cap = cap
        self.stroke_style = stroke_style
        self.shape = shape
        self.brush_style = brush_style or "solid"
        self.brush_spacing = float(brush_spacing or 8.0)
        self.brush_width = float(brush_width or 1.0)
        self.dash = list(dash) if dash else None

    def to_dict(self):
        out = _Layer.to_dict(self)
        out.update({"size": round(float(self.size), 4),
                    "size_unit": self.size_unit,
                    "stroke_color": str(self.stroke_color),
                    "stroke_alpha": round(float(self.stroke_alpha), 6),
                    "stroke_width": round(float(self.stroke_width), 4),
                    "stroke_width_unit": self.stroke_width_unit,
                    "join": self.join, "cap": self.cap,
                    "stroke_style": self.stroke_style, "shape": self.shape})
        if self.brush_style and self.brush_style != "solid":
            out["brush_style"] = self.brush_style
            out["brush_spacing"] = round(float(self.brush_spacing), 3)
            out["brush_width"] = round(float(self.brush_width), 3)
        if self.dash:
            out["dash"] = list(self.dash)
        return out


def _apply_offset(painter, layer, ctx):
    try:
        ox, oy = float(layer.offset_x or 0.0), float(layer.offset_y or 0.0)
    except Exception:
        exc_note("_apply_offset @ ggis/render/cpu/paint.py:426")
        ox = oy = 0.0
    if ox == 0.0 and oy == 0.0:
        return None
    try:
        ox = ctx.convert(ox, layer.offset_unit)
        oy = ctx.convert(oy, layer.offset_unit)
    except Exception:
        exc_note("_apply_offset @ ggis/render/cpu/paint.py:433")
        pass
    painter.translate(ox, oy)
    return (ox, oy)


def fill_pen(layer, ctx, opacity=1.0):
    col = _color(layer.stroke_color, float(layer.stroke_alpha) * float(opacity))
    pen = QPen(col)
    try:
        w = ctx.convert(layer.width, layer.width_unit)
    except Exception:
        exc_note("fill_pen @ ggis/render/cpu/paint.py:449")
        w = float(layer.width or 0.0)
    pen.setWidthF(max(0.0, float(w)))
    pen.setCosmetic(True)
    pen.setStyle(_enum(layer.style, _PEN_STYLE, Qt.PenStyle.SolidLine))
    pen.setJoinStyle(_enum(layer.join, _JOIN, Qt.PenJoinStyle.BevelJoin))
    apply_dash(pen, getattr(layer, "dash", None))
    return pen


def fill_brush(layer, ctx, opacity=1.0):
    col = _color(layer.color, float(layer.alpha) * float(opacity))
    style = str(getattr(layer, "brush_style", "solid") or "solid")
    if style in PATTERN_NAMES:
        br = pattern_brush(col, style,
                           getattr(layer, "brush_spacing", 8.0),
                           getattr(layer, "brush_width", 1.0))
        if br is not None:
            return br
    return QBrush(col, _enum(style, _BRUSH_STYLE,
                             Qt.BrushStyle.SolidPattern))


def line_pen(layer, ctx, opacity=1.0):
    col = _color(layer.color, float(layer.alpha) * float(opacity))
    pen = QPen(col)
    try:
        w = ctx.convert(layer.width, layer.width_unit)
    except Exception:
        exc_note("line_pen @ ggis/render/cpu/paint.py:485")
        w = float(layer.width or 0.0)
    pen.setWidthF(max(0.0, float(w)))
    pen.setCosmetic(True)
    pen.setStyle(_enum(layer.style, _PEN_STYLE, Qt.PenStyle.SolidLine))
    pen.setJoinStyle(_enum(layer.join, _JOIN, Qt.PenJoinStyle.BevelJoin))
    pen.setCapStyle(_enum(layer.cap, _CAP, Qt.PenCapStyle.FlatCap))
    apply_dash(pen, getattr(layer, "dash", None))
    return pen


def marker_pens(layer, ctx, opacity=1.0):
    brush = None
    try:
        fs = str(getattr(layer, "brush_style", "solid") or "solid")
        if fs and fs != "solid":
            brush = pattern_brush(
                layer.color, fs,
                float(getattr(layer, "brush_spacing", 8.0) or 8.0),
                float(getattr(layer, "brush_width", 1.0) or 1.0))
    except Exception:
        exc_note("marker_pens @ ggis/render/cpu/paint.py:516")
        brush = None
    if brush is None:
        brush = QBrush(_color(layer.color, float(layer.alpha) * float(opacity)))
    col = _color(layer.stroke_color,
                 float(layer.stroke_alpha) * float(opacity))
    pen = QPen(col)
    try:
        w = ctx.convert(layer.stroke_width, layer.stroke_width_unit)
    except Exception:
        exc_note("marker_pens @ ggis/render/cpu/paint.py:525")
        w = float(layer.stroke_width or 0.0)
    pen.setWidthF(max(0.0, float(w)))
    pen.setCosmetic(True)
    pen.setStyle(_enum(layer.stroke_style, _PEN_STYLE, Qt.PenStyle.SolidLine))
    pen.setJoinStyle(_enum(layer.join, _JOIN, Qt.PenJoinStyle.BevelJoin))
    pen.setCapStyle(_enum(layer.cap, _CAP, Qt.PenCapStyle.FlatCap))
    try:
        pen = apply_dash(pen, getattr(layer, "dash", None))
    except Exception:
        exc_note("marker_pens @ ggis/render/cpu/paint.py:534")
        pass
    return brush, pen


def draw_polygon(painter, path, layer, ctx, opacity=1.0):
    if path is None or path.isEmpty():
        return False
    pen = fill_pen(layer, ctx, opacity)
    brush = fill_brush(layer, ctx, opacity)
    off = _apply_offset(painter, layer, ctx)
    try:
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawPath(path)
    finally:
        if off is not None:
            painter.translate(-off[0], -off[1])
    return True


def draw_line(painter, path, layer, ctx, opacity=1.0):
    if path is None or path.isEmpty():
        return False
    pen = line_pen(layer, ctx, opacity)
    off = _apply_offset(painter, layer, ctx)
    try:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        painter.drawPath(path)
    finally:
        if off is not None:
            painter.translate(-off[0], -off[1])
    return True


def marker_tile(layer, ctx, opacity=1.0, dpr=1.0, min_side=3.0):
    try:
        size = ctx.convert(layer.size, layer.size_unit)
    except Exception:
        exc_note("marker_tile @ ggis/render/cpu/paint.py:625")
        size = float(getattr(layer, "size", 0.0) or 0.0)
    if size <= 0.0:
        return None, 0.0
    try:
        sw = ctx.convert(layer.stroke_width, layer.stroke_width_unit)
    except Exception:
        exc_note("marker_tile @ ggis/render/cpu/paint.py:631")
        sw = float(getattr(layer, "stroke_width", 0.0) or 0.0)
    side = max(float(min_side), float(size) + max(0.0, float(sw)) + 2.0)
    px = max(1, int(round(side * max(1.0, float(dpr)))))
    img = QImage(px, px, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    if dpr and dpr != 1.0:
        img.setDevicePixelRatio(float(dpr))
    brush, pen = marker_pens(layer, ctx, opacity)
    p = QPainter(img)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(pen)
        p.setBrush(brush)
        half = float(size) / 2.0
        c = side / 2.0
        p.drawEllipse(QRectF(c - half, c - half, size, size))
    finally:
        p.end()
    return img, side


def marker_path(center_x, center_y, size_px):
    p = QPainterPath()
    r = max(0.0, float(size_px) * 0.5)
    if r <= 0.0:
        return p
    p.addEllipse(QPointF(float(center_x), float(center_y)), r, r)
    return p


def draw_marker(painter, x, y, layer, ctx, opacity=1.0):
    try:
        size = ctx.convert(layer.size, layer.size_unit)
    except Exception:
        exc_note("draw_marker @ ggis/render/cpu/paint.py:675")
        size = float(layer.size or 0.0)
    if size <= 0.0:
        return False
    path = marker_path(x, y, size)
    if path.isEmpty():
        return False
    brush, pen = marker_pens(layer, ctx, opacity)
    off = _apply_offset(painter, layer, ctx)
    try:
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawPath(path)
    finally:
        if off is not None:
            painter.translate(-off[0], -off[1])
    return True


def draw_fill(painter, path, layer, ctx, opacity=1.0):
    return draw_polygon(painter, path, layer, ctx, opacity)
