# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note
from ggis.common.styling import themes
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap


def _theme(key, dark, fallback="#000000"):
    try:
        return QColor(themes.theme_color(key, dark))
    except Exception:
        exc_note("_theme @ ggis/common/styling/symbol_sample.py:39")
        return QColor(fallback)


def _pen_ends(sym, pen):
    try:
        from ggis.render.cpu import paint as _P
        pen.setCapStyle(_P._enum(getattr(sym, "cap", "flat"), _P._CAP,
                                 Qt.PenCapStyle.FlatCap))
        pen.setJoinStyle(_P._enum(getattr(sym, "join", "bevel"), _P._JOIN,
                                  Qt.PenJoinStyle.BevelJoin))
    except Exception:
        exc_note("_pen_ends @ ggis/common/styling/symbol_sample.py:54")
        pass
    return pen


def _dash_pen(sym, pen):
    try:
        pat = sym.line_pattern()
    except Exception:
        exc_note("_dash_pen @ ggis/common/styling/symbol_sample.py:67")
        pat = None
    if pat:
        try:
            pen.setDashPattern([float(v) for v in pat])
        except Exception:
            exc_note("_dash_pen @ ggis/common/styling/symbol_sample.py:72")
            pass
    return pen


def _pattern_brush(sym, color):
    try:
        if not sym.has_fill_pattern():
            return None
        from ggis.render.cpu.paint import pattern_brush as _pb
        return _pb(color, sym.fill_style, sym.px_fill_spacing(),
                   sym.px_fill_width())
    except Exception:
        exc_note("_pattern_brush @ ggis/common/styling/symbol_sample.py:89")
        return None


_ZOOM_MIN = 0.25
_ZOOM_MAX = 3.0
_ZOOM_STEP = 1.15


def _preview_scale(avail_w, avail_h):
    try:
        s = min(float(avail_w) / 300.0, float(avail_h) / 60.0)
    except Exception:
        exc_note("_preview_scale @ ggis/common/styling/symbol_sample.py:126")
        return 1.0
    return max(0.35, min(1.6, s))


def paint_symbol_sample(painter, rect, sym, kind, padding=6.0, scale=None,
                        fill_cell=False):
    r = QRectF(rect).adjusted(padding, padding, -padding, -padding)
    if r.width() <= 0 or r.height() <= 0:
        return
    if scale is None:
        scale = _preview_scale(r.width(), r.height())
    try:
        scale = max(0.1, float(scale))
    except Exception:
        exc_note("paint_symbol_sample @ ggis/common/styling/symbol_sample.py:163")
        scale = 1.0
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        fill = QColor(sym.fill_color())
        stroke = QColor(sym.stroke_color())
        lw = max(1.0, float(sym.px_width()))
        if str(kind) == "line":
            pen = QPen(stroke, min(lw, max(1.0, r.height() * 0.5)))
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            _pen_ends(sym, pen)
            _dash_pen(sym, pen)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            half = r.width() * (0.46 if fill_cell else 0.35)
            y = r.center().y()
            painter.drawLine(QPointF(r.center().x() - half, y),
                             QPointF(r.center().x() + half, y))
        elif str(kind) == "point":
            if fill_cell:
                d = max(float(sym.px_size()) * scale, 2.0)
                d = min(max(d, min(r.height() * 0.55,
                                   min(r.width(), r.height()))),
                        min(r.width(), r.height()))
            else:
                d = max(2.0, float(sym.px_size()) * scale)
            pen = QPen(stroke, min(lw, 4.0))
            _pen_ends(sym, pen)
            _dash_pen(sym, pen)
            painter.setPen(pen)
            br = _pattern_brush(sym, fill)
            painter.setBrush(QBrush(fill) if br is None else br)
            c = r.center()
            painter.drawEllipse(c, d / 2.0, d / 2.0)
        else:
            if fill_cell:
                bw = r.width() * 0.98
                bh = r.height() * 0.98
            else:
                bw = max(8.0, min(r.width(),
                                  r.height() * 0.62 * 1.7)) * scale
                bh = bw / 1.7
            box = QRectF(r.center().x() - bw / 2.0, r.center().y() - bh / 2.0,
                         bw, bh)
            pen = QPen(stroke, min(lw, 6.0))
            _pen_ends(sym, pen)
            _dash_pen(sym, pen)
            painter.setPen(pen)
            br = _pattern_brush(sym, fill)
            painter.setBrush(QBrush(fill) if br is None else br)
            painter.drawRoundedRect(box, 2.0, 2.0)
    finally:
        painter.restore()


def sample_pixmap(sym, kind, size, dark, border=True, fill=False):
    try:
        from ggis.common.styling import icons as _icons
        dpr = float(_icons.device_pixel_ratio())
    except Exception:
        exc_note("sample_pixmap @ ggis/common/styling/symbol_sample.py:263")
        dpr = 1.0
    w = max(1, int(round(size.width() * dpr)))
    h = max(1, int(round(size.height() * dpr)))
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    try:
        card = QRectF(0.0, 0.0, float(size.width()), float(size.height()))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if border:
            p.setPen(QPen(_theme("border", dark), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), 3.0, 3.0)
            inner = card.adjusted(1.0, 1.0, -1.0, -1.0)
        else:
            inner = card
        paint_symbol_sample(p, inner, sym, kind,
                            padding=(2.0 if fill else 5.0), scale=1.0,
                            fill_cell=bool(fill))
    finally:
        p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def _category_pixmap(category, item, dark, size):
    try:
        from ggis.ui.dialogs.style_preview import _preview_pixmap
        return _preview_pixmap(category, item, dark,
                               int(size.width()), int(size.height()))
    except Exception:
        exc_note("_category_pixmap @ ggis/common/styling/symbol_sample.py:315")
        return QPixmap()
