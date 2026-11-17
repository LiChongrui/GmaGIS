# -*- coding: utf-8 -*-

from __future__ import annotations

import logging

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QPainterPath,
                           QPen, QPolygonF)

from ggis.core.app import i18n
from ggis.core.model import measure as M
from .maptools import GgsMapTool
_log = logging.getLogger("gmagis")

_tr = i18n.tr

__all__ = ["GgsMapToolMeasure", "MEASURE_KINDS"]

MEASURE_KINDS = ("length", "area", "angle")

_LINE_COLOR = "#FFB300"
_VERTEX_FILL = "#FFF3D0"
_BOX_BORDER = "#FFB300"


def _chip_colors():
    try:
        from ggis.core.app import settings as _s
        from ggis.common.styling import themes as _t
        pal = _t.theme_colors(_s.get("theme"))
        if _s.get("theme") == "light":
            return (pal.get("panel") or "#ffffff",
                    pal.get("text") or "#19232D")
        return (pal.get("panel") or "#1B2430",
                pal.get("text") or "#ffffff")
    except Exception:
        _log.exception("silent exception in _chip_colors")
        return ("#1B2430", "#ffffff")


_VERTEX_R = 3.0
_HIT_TEXT_PAD = 5.0


class GgsMapToolMeasure(GgsMapTool):

    measured = Signal(object)

    def __init__(self, canvas=None, kind="length", crs_provider=None,
                 parent=None):
        kind = str(kind or "length")
        if kind not in MEASURE_KINDS:
            kind = "length"
        super().__init__("measure_" + kind, canvas,
                         Qt.CursorShape.CrossCursor, parent)
        self._kind = kind
        self._crs_provider = crs_provider
        self._pts = []
        self._cursor = None
        self._finished = False
        self._result = None
        self._segments = []
        self._azimuths = []
        self._straight = None
        try:
            from ggis.core.app import settings as _s
            self._show_overlay = bool(_s.get("measure_show_overlay", False))
        except Exception:
            _log.exception("silent exception in __init__")
            self._show_overlay = False

    def kind(self):
        return self._kind

    def setKind(self, kind):
        if str(kind) in MEASURE_KINDS:
            self._kind = str(kind)
            self.clear()

    def setCrsProvider(self, fn):
        self._crs_provider = fn

    def setCrs(self, crs):
        self._crs_provider = (lambda c=crs: c)

    def crs(self):
        if self._crs_provider is not None:
            try:
                return self._crs_provider()
            except Exception:
                _log.exception("silent exception in crs")
                return None
        c = self._canvas
        if c is not None:
            try:
                return c.effectiveCrs()
            except Exception:
                _log.exception("silent exception in crs")
                return None
        return None

    def method(self):
        return M.METHOD_AUTO

    def points(self):
        return list(self._pts)

    def result(self):
        return self._result

    def isInteractive(self):
        return True

    def set_show_overlay(self, on):
        self._show_overlay = bool(on)
        self._repaint()

    def show_overlay(self):
        return bool(getattr(self, "_show_overlay", True))

    def detail_text(self):
        parts = []
        if self._kind == "length":
            st = getattr(self, "_straight", None)
            if st is not None and float(getattr(st, "value", 0.0) or 0.0) > 0:
                parts.append(_tr("直线距离 {}").format(st.text))
        elif self._kind == "area":
            per = getattr(self, "_perimeter", None)
            if per is not None and float(getattr(per, "value", 0.0) or 0.0) > 0:
                parts.append(_tr("周长 {}").format(per.text))
        elif self._kind == "angle" and len(self._azimuths) == 2:
            parts.append(_tr("方位角 {} / {}").format(*self._azimuths))
        return ("　|　" if i18n.is_zh() else "  |  ").join(parts)

    def statusHint(self):
        if self._kind == "area":
            return _tr("量测面积")
        if self._kind == "angle":
            return _tr("量测角度")
        return _tr("量测距离")

    def deactivate(self):
        super().deactivate()
        c = self._canvas
        if c is not None:
            try:
                c._overlay_version = getattr(c, "_overlay_version", 0) + 1
                c.update()
            except Exception:
                logging.getLogger("gmagis").warning(
                    "measure deactivate: overlay refresh failed", exc_info=True)

    def clear(self):
        self._pts = []
        self._cursor = None
        self._finished = False
        self._result = None
        self._segments = []
        self._azimuths = []
        self._straight = None
        self.measured.emit("")
        self._repaint()

    def mousePress(self, event, map_point):
        btn = event.button()
        if btn == Qt.MouseButton.RightButton:
            self._finish()
            return True
        if btn != Qt.MouseButton.LeftButton:
            return False
        if self._finished:
            self._pts = []
            self._finished = False
            self._result = None
            self._segments = []
            self._azimuths = []
            self._straight = None
        self._pts.append((round(map_point.x(), 9), round(map_point.y(), 9)))
        if self._kind == "angle" and len(self._pts) >= 3:
            self._update()
            self._finish()
        else:
            self._update()
            self._emit_current()
        self._repaint()
        return True

    def mouseMove(self, event, map_point):
        if self._pts and not self._finished:
            self._cursor = (map_point.x(), map_point.y())
            self._update(preview=self._cursor)
            self._emit_current()
            self._repaint()
        return True

    def mouseDoubleClick(self, event, map_point):
        self._finish()
        return True

    def keyPress(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self.clear()
            return True
        if k == Qt.Key.Key_Backspace:
            if self._pts:
                self._pts.pop()
                self._finished = False
                self._update()
                self._emit_current()
                self._repaint()
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish()
            return True
        return False

    def _finish(self):
        if not self._pts:
            return
        need = 3 if self._kind == "angle" else 2
        if len(self._pts) < need:
            self._pts = []
            self._result = None
            self._segments = []
            self._straight = None
            self.measured.emit("")
            self._repaint()
            return
        self._update()
        self._finished = True
        self._cursor = None
        if self._result is not None:
            self.measured.emit((self._summary(), self.detail_text()))
        self._repaint()

    def _emit_current(self):
        if self._result is not None:
            self.measured.emit((self._summary(), self.detail_text()))
        else:
            self.measured.emit("")

    def _update(self, preview=None):
        pts = list(self._pts)
        if preview is not None and pts:
            pts.append((round(float(preview[0]), 9),
                        round(float(preview[1]), 9)))
        crs = self.crs()
        method = self.method()
        self._segments = []
        self._azimuths = []
        self._result = None
        self._straight = None
        if self._kind == "angle":
            if len(pts) < 3:
                return
            self._result = M.measure_angle(pts[0], pts[1], pts[2],
                                           crs, method)
            try:
                self._azimuths = [
                    M.format_azimuth(M.geodesic_azimuth(pts[1], pts[0], crs)),
                    M.format_azimuth(M.geodesic_azimuth(pts[1], pts[2], crs))]
            except Exception:
                _log.exception("silent exception in _update")
                self._azimuths = []
            return

        if self._kind == "area":
            if len(pts) < 3:
                return
            ring = list(pts) + [pts[0]]
            self._segments = M.segment_lengths(ring, crs, method)
            self._result = M.measure_area(ring, crs, method)
            self._perimeter = M.measure_length(ring, crs, method)
            return

        if len(pts) < 2:
            return
        self._segments = M.segment_lengths(pts, crs, method)
        self._result = M.measure_length(pts, crs, method)
        try:
            if len(pts) >= 2:
                self._straight = M.measure_length([pts[0], pts[-1]],
                                                  crs, method)
        except Exception:
            _log.exception("silent exception in _update")
            self._straight = None

    def _summary(self):
        if self._result is None:
            return ""
        if self._kind == "area":
            return _tr("面积 {}").format(self._result.text)
        if self._kind == "angle":
            return _tr("夹角 {}").format(self._result.text)
        return _tr("长度 {}").format(self._result.text)

    def _repaint(self):
        c = self._canvas
        if c is not None:
            try:
                c.update()
            except Exception:
                _log.exception("silent exception in _repaint")

    def paint_overlay(self, painter, settings):
        if not settings.is_ready():
            return
        preview = list(self._pts)
        if self._cursor is not None and self._pts and not self._finished:
            preview.append(self._cursor)
        if not preview:
            return
        show_nums = self.show_overlay()
        screen = [settings.map_to_pixel(x, y) for x, y in preview]
        painter.save()
        pen = QPen(QColor(_LINE_COLOR), 1.8)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if self._kind == "area" and len(screen) >= 3:
            poly = QPolygonF(screen)
            painter.setBrush(QBrush(QColor(255, 179, 0, 46)))
            painter.drawPolygon(poly)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(QPolygonF(screen + [screen[0]]))
        elif len(screen) >= 2:
            painter.drawPolyline(QPolygonF(screen))

        painter.setPen(QPen(QColor(_chip_colors()[0]), 1.2))
        painter.setBrush(QBrush(QColor(_VERTEX_FILL)))
        for p in screen:
            painter.drawEllipse(p, _VERTEX_R, _VERTEX_R)

        if show_nums and self._segments and self._kind in ("length", "area"):
            f = QFont()
            f.setPointSizeF(8.0)
            painter.setFont(f)
            fm = QFontMetricsF(f)
            for i, seg in enumerate(self._segments):
                if i + 1 >= len(screen):
                    break
                a = screen[i]
                b = screen[i + 1]
                txt = seg.text
                tw = fm.horizontalAdvance(txt)
                th = fm.height()
                mx = (a.x() + b.x()) * 0.5
                my = (a.y() + b.y()) * 0.5
                self._draw_chip(painter, mx - tw * 0.5 - 3, my - th * 0.5 - 2,
                                tw + 6, th + 4, txt, f)

        if self._result is not None and show_nums:
            txt = self._summary()
            f = QFont()
            f.setPointSizeF(9.5)
            f.setBold(True)
            fm = QFontMetricsF(f)
            tw = fm.horizontalAdvance(txt)
            th = fm.height()
            if self._kind == "angle" and len(screen) >= 2:
                ref = screen[1]
            else:
                ref = screen[-1]
            ax = ref.x()
            ay = ref.y()
            bx = min(max(ax + 14, 4), max(4, settings.output_width() - tw - 26))
            by = min(max(ay + 12, 4), max(4, settings.output_height() - th - 24))
            self._draw_chip(painter, bx, by, tw + 20, th + 12, txt, f,
                            big=True)
        painter.restore()

    @staticmethod
    def _draw_chip(painter, x, y, w, h, text, font, big=False):
        bg_hex, fg_hex = _chip_colors()
        r = QRectF(x, y, w, h)
        path = QPainterPath()
        path.addRoundedRect(r, 4.0, 4.0)
        painter.setPen(QPen(QColor(_BOX_BORDER), 1.0))
        bg = QColor(bg_hex)
        bg.setAlpha(238 if big else 210)
        painter.setBrush(QBrush(bg))
        painter.drawPath(path)
        painter.setFont(font)
        painter.setPen(QPen(QColor(fg_hex)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(r, int(Qt.AlignmentFlag.AlignCenter), text)
