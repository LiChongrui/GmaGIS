# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainter,
                           QPainterPath, QPen, QPixmap)

from ggis.core.app import i18n
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_PREVIEW = 34


def _preview_pixmap(category, item, dark_bg, w=_PREVIEW, h=_PREVIEW):
    pm = QPixmap(int(w), int(h))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        if category == "symbol":
            _paint_symbol(p, item, w, h, dark_bg)
        elif category == "ramp":
            _paint_ramp(p, item, w, h)
        else:
            _paint_text(p, item, w, h, category == "label")
    except Exception:
        _log.exception("silent exception in _preview_pixmap")
    p.end()
    return pm


def _paint_symbol(p, item, w, h, dark_bg=True):
    try:
        from ggis.common.styling.symbol_sample import paint_symbol_sample
        from ...render.style_apply import symbol_from_item
        kind = str(item.get("kind", "point") or "point")
        sym = symbol_from_item(item, kind, dark_bg)
        paint_symbol_sample(p, QRectF(0.0, 0.0, float(w), float(h)), sym,
                            kind, padding=3.0, scale=1.0)
    except Exception:
        _log.exception("silent exception in _paint_symbol")


def _ramp_colors_from_stops(stops, n):
    pts = []
    for pair in (stops or []):
        try:
            pos = max(0.0, min(1.0, float(pair[0])))
            col = QColor(str(pair[1]))
            if col.isValid():
                pts.append((pos, col))
        except Exception:
            _log.exception("silent exception in _ramp_colors_from_stops")
            continue
    if len(pts) < 2:
        return []
    pts.sort(key=lambda t: t[0])
    out = []
    for i in range(max(2, int(n))):
        t = i / float(max(1, int(n) - 1))
        lo = pts[0]
        hi = pts[-1]
        for k in range(len(pts) - 1):
            if pts[k][0] <= t <= pts[k + 1][0]:
                lo, hi = pts[k], pts[k + 1]
                break
        span = max(1e-6, hi[0] - lo[0])
        f = 0.0 if span <= 1e-6 else (t - lo[0]) / span
        r = int(round(lo[1].red() + (hi[1].red() - lo[1].red()) * f))
        g = int(round(lo[1].green() + (hi[1].green() - lo[1].green()) * f))
        b = int(round(lo[1].blue() + (hi[1].blue() - lo[1].blue()) * f))
        out.append(QColor(r, g, b).name())
    return out


def _paint_ramp(p, item, w, h):
    from ...render.renderers import make_ramp
    _n = max(8, int(w))
    _draft = _ramp_colors_from_stops(item.get("stops"), _n)
    colors = _draft or make_ramp(item.get("key", ""), _n)
    band = h * 0.52
    step = w / float(len(colors))
    p.setPen(Qt.PenStyle.NoPen)
    for i, c in enumerate(colors):
        p.setBrush(QColor(c))
        p.drawRect(QRectF(i * step, h * 0.16, step + 1, band))
    picks = make_ramp(item.get("key", ""), 6)
    for i, c in enumerate(picks):
        p.setBrush(QColor(c))
        p.drawRect(QRectF(i * (w / 6.0), h * 0.74, (w / 6.0) - 1, h * 0.14))


def _paint_text(p, item, w, h, with_point):
    fam = item.get("font_family") or ""
    font = QFont(fam) if fam else QFont()
    size = max(4.0, min(24.0, float(item.get("font_size", 9.0))))
    font.setPointSizeF(size)
    font.setBold(bool(item.get("bold")))
    font.setItalic(bool(item.get("italic")))
    text = _tr("示例文字") if float(w) >= 90.0 else "Aa"

    tiny = float(w) < 20.0 or float(h) < 20.0
    hw = 0.0 if tiny else float(item.get("halo_width", 0.0) or 0.0)
    pad = 1.0
    avail_w = max(2.0, float(w) - 2.0 * (pad + hw))
    avail_h = max(2.0, float(h) - 2.0 * (pad + hw))
    fm = QFontMetricsF(font)
    _guard = 0
    while size > 3.0 and _guard < 48 and (
            fm.horizontalAdvance(text) > avail_w or fm.height() > avail_h):
        size -= 0.5
        font.setPointSizeF(size)
        fm = QFontMetricsF(font)
        _guard += 1
    p.setFont(font)
    tw = fm.horizontalAdvance(text)
    if with_point:
        placement = item.get("placement", "auto")
        ox = float(item.get("offset_x", 0.0))
        oy = float(item.get("offset_y", 0.0))
        cx, cy = w * 0.30, h * 0.5
        p.setPen(QPen(QColor("#1B2430"), 1.0))
        p.setBrush(QBrush(QColor("#4C9BE8")))
        p.drawEllipse(QPointF(cx, cy), 4.0, 4.0)
        dx, dy = ox, oy
        if placement == "top":
            dy -= 10.0
        elif placement == "bottom":
            dy += 10.0
        elif placement in ("right", "auto"):
            dx += 8.0
        elif placement == "left":
            dx -= tw + 8.0
        elif placement == "center":
            dx = -tw / 2.0
        x0 = cx + dx
        y0 = cy + dy - fm.height() / 2.0
    else:
        x0 = (w - tw) / 2.0
        y0 = (h - fm.height()) / 2.0
    color = QColor(item.get("color", "#FFFFFF"))
    brush = QBrush(color)
    path = QPainterPath()
    base = (fm.ascent() - fm.descent()) * 0.5
    path.addText(QPointF(x0, y0 + fm.height() / 2.0 + base), font, text)
    if hw > 0:
        halo = QPen(QColor(item.get("halo_color", "#000000")), hw * 2.0)
        halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        halo.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.strokePath(path, halo)
    p.fillPath(path, brush)
