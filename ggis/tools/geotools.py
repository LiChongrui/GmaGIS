# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor

from ggis.core.app import i18n as _i18n
from .maptools import GgsMapTool
import logging
_log = logging.getLogger("gmagis")

_tr = _i18n.tr

__all__ = ["GgsMapToolDrawLine"]

_LINE_COLOR = "#22d3ee"
_VERTEX_COLOR = "#e0f7ff"
_VERTEX_HALF = 3.0


class GgsMapToolDrawLine(GgsMapTool):

    lineDrawn = Signal(object)
    cancelled = Signal()

    def __init__(self, canvas=None, hint="", expect="line",
                 need_snap=False, parent=None):
        super().__init__("draw_line", canvas,
                         Qt.CursorShape.CrossCursor, parent)
        self._hint = str(hint or "")
        self._expect = str(expect or "line")
        self._need_snap = bool(need_snap)
        self._pts = []
        self._preview = None
        self._snapper = None

    def setSnapper(self, snapper):
        self._snapper = snapper

    def statusHint(self):
        if self._hint:
            return self._hint
        if self._expect == "point":
            return _tr("取参考点")
        return _tr("在地图上画一条参考线：左键落点；"
                   "双击 / 右键 / 回车结束；Esc 取消")

    def isInteractive(self):
        return True

    def _snap(self, pt):
        if not self._need_snap or self._snapper is None:
            return pt
        scale = 1.0
        try:
            scale = float(self.canvas().mapUnitsPerPixel())
        except Exception:
            _log.exception("silent exception in _snap")
        try:
            r = self._snapper.snap((pt.x(), pt.y()), scale)
        except Exception:
            _log.exception("silent exception in _snap")
            r = None
        if r is None:
            return pt
        try:
            return QPointF(float(r.point[0]), float(r.point[1]))
        except Exception:
            _log.exception("silent exception in _snap")
            return pt

    def _to_screen(self, x, y):
        try:
            return self.canvas().to_canvas_coords(x, y)
        except Exception:
            _log.exception("silent exception in _to_screen")
            return None

    def _repaint(self):
        try:
            self.canvas().update()
        except Exception:
            _log.exception("silent exception in _repaint")

    def mousePress(self, event, map_point):
        btn = event.button()
        if btn == Qt.MouseButton.RightButton:
            return self._finish()
        if btn != Qt.MouseButton.LeftButton:
            return False
        mp = self._snap(map_point)
        if self._expect == "point":
            self._pts = [(mp.x(), mp.y())]
            return self._finish()
        self._pts.append((mp.x(), mp.y()))
        self._preview = (mp.x(), mp.y())
        self._repaint()
        return True

    def mouseMove(self, event, map_point):
        if not self._pts:
            return False
        mp = self._snap(map_point)
        self._preview = (mp.x(), mp.y())
        self._repaint()
        return True

    def mouseDoubleClick(self, event, map_point):
        return self._finish()

    def keyPress(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self._reset()
            self.cancelled.emit()
            self._repaint()
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self._finish()
        if k == Qt.Key.Key_Backspace:
            if self._pts:
                self._pts.pop()
                self._repaint()
            return True
        return False

    def _reset(self):
        self._pts = []
        self._preview = None

    def _finish(self):
        pts = list(self._pts)
        self._reset()
        if not pts:
            return False
        geom = None
        try:
            if self._expect == "point":
                from shapely.geometry import Point
                geom = Point(pts[0])
            elif len(pts) >= 2:
                from shapely.geometry import LineString
                geom = LineString(pts)
        except Exception:
            _log.exception("silent exception in _finish")
            geom = None
        self._repaint()
        if geom is None:
            return False
        self.lineDrawn.emit(geom)
        return True

    def paint_overlay(self, painter, settings):
        if not self._pts:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)

        pts = [self._to_screen(x, y) for x, y in self._pts]
        pts = [p for p in pts if p is not None]
        if self._preview is not None:
            pv = self._to_screen(*self._preview)
            if pv is not None:
                pts.append(pv)

        if len(pts) >= 2:
            path = None
            try:
                from PySide6.QtGui import QPainterPath
                path = QPainterPath()
                path.moveTo(pts[0])
                for p in pts[1:]:
                    path.lineTo(p)
            except Exception:
                _log.exception("silent exception in paint_overlay")
                path = None
            painter.setPen(QPen(QColor(_LINE_COLOR), 1.8,
                                Qt.PenStyle.SolidLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if path is not None:
                painter.drawPath(path)
            else:
                for i in range(len(pts) - 1):
                    painter.drawLine(pts[i], pts[i + 1])

        painter.setPen(QPen(QColor("#0d1b26"), 1.0))
        painter.setBrush(QBrush(QColor(_VERTEX_COLOR)))
        for p in pts[:-1] if self._preview is not None else pts:
            painter.drawRect(QRectF(p.x() - _VERTEX_HALF,
                                    p.y() - _VERTEX_HALF,
                                    _VERTEX_HALF * 2, _VERTEX_HALF * 2))
        painter.restore()
