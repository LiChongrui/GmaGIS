# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen, QPolygonF

from ggis.core.app import i18n
from ..core.crs import crs_transformer
from ggis.core.expr.query import crs_of, to_layer_point, to_layer_tolerance
from ggis.core.model.snapping import (ALL_SNAP_KINDS, SNAP_EDGE, SNAP_ENDPOINT,
                            SNAP_INTERSECTION, SNAP_MIDPOINT, SNAP_VERTEX)
from .maptools import GgsMapTool, identify_tolerance
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

DRAG_PX = 4
VERTEX_HALF = 4


class GgsEditTool(GgsMapTool):

    finished = Signal()

    def __init__(self, name, canvas=None, session=None, layer=None,
                 snapper=None, layer_provider=None, selection=None,
                 parent=None):
        super().__init__(name, canvas, Qt.CursorShape.CrossCursor, parent)
        self._session = session
        self._layer = layer
        self._snapper = snapper
        self._layer_provider = layer_provider
        self._selection = selection
        self.snap_enabled = True
        self.snap_kinds = set(ALL_SNAP_KINDS)
        self._snap_result = None

    def setSession(self, session):
        self._session = session

    def session(self):
        return self._session

    def setLayer(self, layer):
        self._layer = layer

    def layer(self):
        if self._layer is not None:
            return self._layer
        if self._layer_provider is not None:
            try:
                return self._layer_provider()
            except Exception:
                _log.exception("silent exception in layer")
                return None
        return None

    def setCanvas(self, canvas):
        super().setCanvas(canvas)
        if canvas is not None:
            try:
                self._selection = canvas.selection()
            except Exception:
                _log.exception("silent exception in setCanvas")

    def _layer_pt(self, map_point):
        lyr = self.layer()
        if lyr is None or map_point is None:
            return map_point
        try:
            x, y = to_layer_point(lyr, map_point.x(), map_point.y(),
                                  self._canvas)
        except Exception:
            _log.exception("silent exception in _layer_pt")
            return map_point
        return QPointF(float(x), float(y))

    def _layer_tol(self, tol):
        lyr = self.layer()
        if lyr is None:
            return tol
        try:
            return to_layer_tolerance(lyr, tol, self._canvas)
        except Exception:
            _log.exception("silent exception in _layer_tol")
            return tol

    def setSnapper(self, snapper):
        self._snapper = snapper

    _SNAP_TOOL = False

    def isEditTool(self):
        return True

    def isInteractive(self):
        return True

    def _editing(self):
        s = self._session
        if s is None:
            return None
        if not s.is_active():
            try:
                s.start()
            except Exception:
                _log.exception("silent exception in _editing")
                return None
        return s

    def _snap_exclude(self):
        lyr = self.layer()
        fid = int(getattr(self, "_fid", -1))
        vi = int(getattr(self, "_vi", -1))
        if lyr is None or fid < 0 or vi < 0:
            return None
        try:
            return (str(lyr.id()), fid, vi)
        except Exception:
            _log.exception("silent exception in _snap_exclude")
            return None

    def _snap(self, map_point, exclude_vertex=None):
        map_point = self._layer_pt(map_point)
        self._snap_result = None
        if (not self._SNAP_TOOL or not self.snap_enabled
                or self._snapper is None):
            return QPointF(float(map_point.x()), float(map_point.y()))
        scale = 1.0
        c = self._canvas
        try:
            scale = float(c.mapUnitsPerPixel())
        except Exception:
            _log.exception("silent exception in _snap")
        scale = self._layer_tol(scale)
        try:
            if exclude_vertex is None and getattr(self, "_drag_from",
                                                  None) is not None:
                exclude_vertex = self._snap_exclude()
            r = self._snapper.snap((map_point.x(), map_point.y()), scale,
                                   self.snap_kinds,
                                   exclude_vertex=exclude_vertex)
        except Exception:
            _log.exception("silent exception in _snap")
            r = None
        if r is None:
            return QPointF(float(map_point.x()), float(map_point.y()))
        self._snap_result = r
        return QPointF(float(r.point[0]), float(r.point[1]))

    def _previewing(self):
        return bool(getattr(self, "_pts", None))

    def _repaint(self):
        c = self._canvas
        if c is None:
            return
        if not self._previewing():
            try:
                ie = getattr(c, "invalidate_edit", None)
                if ie is not None:
                    ie(self.layer())
                    return
            except Exception:
                _log.exception("silent exception in _repaint")
        try:
            c.update()
        except Exception:
            _log.exception("silent exception in _repaint")

    def _hover_repaint(self):
        c = self._canvas
        if c is None:
            return
        try:
            c.update()
        except Exception:
            _log.exception("silent exception in _hover_repaint")

    def _to_screen(self, x, y):
        c = self._canvas
        if c is None:
            return None
        try:
            p = c.to_canvas_coords(x, y)
        except Exception:
            _log.exception("silent exception in _to_screen")
            return None
        if isinstance(p, QPointF):
            return p
        try:
            return QPointF(float(p[0]), float(p[1]))
        except Exception:
            _log.exception("silent exception in _to_screen")
            try:
                return QPointF(p.x(), p.y())
            except Exception:
                _log.exception("silent exception in _to_screen")
                return None

    def _to_screen_layer(self, x, y):
        lyr = self.layer()
        if lyr is not None and self._canvas is not None:
            try:
                tf = crs_transformer(crs_of(lyr), crs_of(self._canvas))
            except Exception:
                _log.exception("silent exception in _to_screen_layer")
                tf = None
            if tf is not None:
                try:
                    x, y = tf.transform(float(x), float(y))
                except Exception:
                    _log.exception("silent exception in _to_screen_layer")
        return self._to_screen(x, y)

    _SNAP_COLORS = {
        SNAP_ENDPOINT: "#4dff88",
        SNAP_VERTEX: "#4dc3ff",
        SNAP_INTERSECTION: "#ffb84d",
        SNAP_MIDPOINT: "#c98cff",
        SNAP_EDGE: "#4ddbc4",
    }
    _SNAP_LABELS = {
        SNAP_ENDPOINT: "端点",
        SNAP_VERTEX: "节点",
        SNAP_INTERSECTION: "交点",
        SNAP_MIDPOINT: "中点",
        SNAP_EDGE: "边",
    }

    def paint_overlay(self, painter, settings):
        self._paint_snap_marker(painter)

    def _paint_snap_marker(self, painter):
        r = self._snap_result
        if r is None:
            return
        sp = self._to_screen_layer(r.point[0], r.point[1])
        if sp is None:
            return
        color = QColor(self._SNAP_COLORS.get(r.kind, "#ffffff"))
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(color, 1.6)
        painter.setPen(pen)
        s = 5.0
        painter.drawRect(QRectF(sp.x() - s, sp.y() - s, s * 2, s * 2))
        painter.setPen(QPen(color, 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(sp.x() - s * 1.8, sp.y()),
                         QPointF(sp.x() + s * 1.8, sp.y()))
        painter.drawLine(QPointF(sp.x(), sp.y() - s * 1.8),
                         QPointF(sp.x(), sp.y() + s * 1.8))
        f = QFont()
        f.setPointSize(8)
        painter.setFont(f)
        painter.setPen(QPen(color, 1.0))
        painter.drawText(QPointF(sp.x() + s + 3, sp.y() - s - 2),
                         _tr(self._SNAP_LABELS.get(r.kind, r.kind)))
        painter.restore()

    def _hit_fids(self, map_point):
        lyr = self.layer()
        if lyr is None or not lyr.is_vector():
            return []
        tol = self._layer_tol(identify_tolerance(self._canvas, 6))
        mp = self._layer_pt(map_point)
        try:
            from ggis.core.expr.query import hit_fids
            return hit_fids(lyr, mp.x(), mp.y(), tol)
        except Exception:
            _log.exception("silent exception in _hit_fids")
            return []


class GgsMapToolAddFeature(GgsEditTool):

    featureAdded = Signal(int)

    def __init__(self, canvas=None, session=None, layer=None, snapper=None,
                 layer_provider=None, selection=None, parent=None):
        super().__init__("add_feature", canvas, session, layer, snapper,
                         layer_provider, parent)
        self._pts = []
        self._preview = None

    def statusHint(self):
        return _tr("添加要素")

    def _geom_type(self):
        lyr = self.layer()
        if lyr is None:
            return ""
        try:
            return str(lyr.geometry_type() or lyr.base_kind())
        except Exception:
            _log.exception("silent exception in _geom_type")
            return ""

    def _is_point(self):
        return "Point" in self._geom_type()

    def mousePress(self, event, map_point):
        btn = event.button()
        if btn == Qt.MouseButton.RightButton:
            return self._finish()
        if btn != Qt.MouseButton.LeftButton:
            return False
        mp = self._snap(map_point)
        if self._is_point():
            self._pts = [(mp.x(), mp.y())]
            self._commit()
            return True
        self._pts.append((mp.x(), mp.y()))
        self._preview = (mp.x(), mp.y())
        self._repaint()
        return True

    def mouseMove(self, event, map_point):
        if not self._pts:
            self._snap(map_point)
            self._hover_repaint()
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
            self._pts = []
            self._preview = None
            self._hover_repaint()
            return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return self._finish()
        if k == Qt.Key.Key_Backspace:
            if self._pts:
                self._pts.pop()
                self._hover_repaint()
            return True
        return False

    def _commit(self):
        s = self._editing()
        lyr = self.layer()
        if s is None or lyr is None or not self._pts:
            return
        from shapely.geometry import Point, Polygon

        kind = self._geom_type()
        pts = list(self._pts)
        if "Point" in kind:
            geom = Point(*pts[0])
        elif "Polygon" in kind:
            if len(pts) < 3:
                return
            geom = Polygon(pts)
        else:
            if len(pts) < 2:
                return
            from shapely.geometry import LineString
            geom = LineString(pts)
        attrs = self._blank_attrs(lyr)
        self._pts = []
        self._preview = None
        try:
            fid = s.add_feature(geom, attrs)
        except Exception:
            _log.exception("silent exception in _commit")
            return
        self.featureAdded.emit(int(fid))
        self._repaint()

    @staticmethod
    def _blank_attrs(lyr):
        out = {}
        try:
            for name, _t in lyr.fields() or []:
                out[str(name)] = None
        except Exception:
            _log.exception("silent exception in _blank_attrs")
        return out

    def _finish(self):
        if not self._pts:
            return False
        self._commit()
        return True

    def paint_overlay(self, painter, settings):
        super().paint_overlay(painter, settings)
        if not self._pts:
            return
        pts = [self._to_screen_layer(x, y) for x, y in self._pts]
        pts = [p for p in pts if p is not None]
        if not pts:
            return
        if self._preview is not None:
            pv = self._to_screen_layer(*self._preview)
            if pv is not None:
                pts = pts + [pv]
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#4dc3ff"), 1.4, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if len(pts) >= 2:
            painter.drawPolyline(pts)
        if len(pts) >= 3 and "Polygon" in self._geom_type():
            painter.setPen(QPen(QColor(77, 195, 255, 40), 1.0))
            painter.setBrush(QBrush(QColor(77, 195, 255, 40)))
            painter.drawPolygon(pts)
        painter.setPen(QPen(QColor("#4dc3ff"), 1.2))
        painter.setBrush(QBrush(QColor("#0d1b26")))
        for p in pts:
            painter.drawRect(QRectF(p.x() - 3, p.y() - 3, 6, 6))
        painter.restore()


class GgsMapToolMoveFeature(GgsEditTool):

    moved = Signal(object)

    def __init__(self, canvas=None, session=None, layer=None, snapper=None,
                 layer_provider=None, selection=None, parent=None):
        super().__init__("move_feature", canvas, session, layer, snapper,
                         layer_provider, parent)
        self._selection = selection
        self._press = None
        self._delta = (0.0, 0.0)
        self._fids = []
        self._orig = {}
        self._ovl = []
        self._ovl_anchor = None

    def statusHint(self):
        return _tr("移动要素")

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        lyr = self.layer()
        if lyr is None:
            return False
        fids = self._target_fids(lyr, map_point)
        if not fids:
            return False
        self._fids = fids
        _pp = self._layer_pt(map_point)
        self._press = (float(_pp.x()), float(_pp.y()))
        self._delta = (0.0, 0.0)
        self._orig = {}
        geoms = lyr.geoms()
        for f in fids:
            if 0 <= f < len(geoms):
                self._orig[f] = geoms[f]
        self._build_overlay()
        return True

    def _build_overlay(self):
        self._ovl = []
        self._ovl_anchor = None
        if self._press is None:
            return
        try:
            for _f, g in self._orig.items():
                for _p, _r, coords in _iter_coords(g):
                    pts = []
                    for x, y in coords:
                        q = self._to_screen_layer(x, y)
                        if q is not None:
                            pts.append(q)
                    if pts:
                        self._ovl.append(pts)
            self._ovl_anchor = self._to_screen_layer(self._press[0],
                                                     self._press[1])
        except Exception:
            _log.exception("silent exception in _build_overlay")
            self._ovl = []
            self._ovl_anchor = None

    def _previewing(self):
        return self._press is not None

    def mouseMove(self, event, map_point):
        if self._press is None:
            self._snap(map_point)
            self._hover_repaint()
            return False
        mp = self._snap(map_point)
        self._delta = (mp.x() - self._press[0], mp.y() - self._press[1])
        self._repaint()
        return True

    def mouseRelease(self, event, map_point):
        if self._press is None:
            return False
        s = self._editing()
        dx, dy = self._delta
        fids = list(self._fids)
        self._press = None
        self._delta = (0.0, 0.0)
        self._fids = []
        self._orig = {}
        self._ovl = []
        self._ovl_anchor = None
        if s is None or (abs(dx) < 1e-12 and abs(dy) < 1e-12):
            self._hover_repaint()
            return True
        s.move_features(fids, dx, dy)
        self.moved.emit(fids)
        self._repaint()
        return True

    def keyPress(self, event):
        if event.key() == Qt.Key.Key_Escape and self._press is not None:
            self._press = None
            self._delta = (0.0, 0.0)
            self._ovl = []
            self._ovl_anchor = None
            self._hover_repaint()
            return True
        return False

    def press_on_selected(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        lyr = self.layer()
        sel = self._selection
        if lyr is None or sel is None:
            return False
        try:
            fids = set(int(f) for f in sel.fids(lyr))
        except Exception:
            _log.exception("silent exception in press_on_selected")
            return False
        if not fids:
            return False
        if not (set(int(f) for f in self._hit_fids(map_point)) & fids):
            return False
        return self.mousePress(event, map_point)

    def _target_fids(self, lyr, map_point):
        sel = self._selection
        if sel is not None:
            try:
                fids = sel.fids(lyr)
                if fids:
                    return [int(f) for f in fids]
            except Exception:
                _log.exception("silent exception in _target_fids")
        return [int(f) for f in self._hit_fids(map_point)]

    def paint_overlay(self, painter, settings):
        super().paint_overlay(painter, settings)
        if self._press is None or not self._ovl:
            return
        dx, dy = self._delta
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:
            return
        a = self._ovl_anchor
        a_now = self._to_screen_layer(self._press[0], self._press[1])
        if a_now is None:
            return
        if a is None or (abs(a_now.x() - a.x()) > 0.5
                         or abs(a_now.y() - a.y()) > 0.5):
            self._build_overlay()
            a = self._ovl_anchor
            if a is None or not self._ovl:
                return
        cur = self._to_screen_layer(self._press[0] + dx, self._press[1] + dy)
        if cur is None:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#ffd24d"), 1.4, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.translate(cur.x() - a.x(), cur.y() - a.y())
        for pts in self._ovl:
            if len(pts) >= 2:
                painter.drawPolyline(pts)
            else:
                painter.drawEllipse(pts[0], 3.0, 3.0)
        painter.restore()


def _iter_coords(geom):
    from ggis.core.model.snapping import _iter_parts
    return _iter_parts(geom) or ()


class GgsMapToolDeleteFeature(GgsEditTool):

    deleted = Signal(object)

    def __init__(self, canvas=None, session=None, layer=None, snapper=None,
                 layer_provider=None, selection=None, parent=None):
        super().__init__("delete_feature", canvas, session, layer, snapper,
                         layer_provider, parent)
        self._selection = selection

    def statusHint(self):
        return _tr("删除要素")

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        lyr = self.layer()
        sel = self._selection
        if lyr is None or sel is None:
            return False
        fids = [int(f) for f in self._hit_fids(map_point)]
        if not fids:
            return True
        mod = event.modifiers()
        add = bool(mod & (Qt.KeyboardModifier.ControlModifier
                          | Qt.KeyboardModifier.ShiftModifier))
        try:
            if add:
                sel.add_fids(lyr, fids)
            else:
                sel.set_fids(lyr, fids)
        except Exception:
            _log.exception("silent exception in mousePress")
            return True
        self._hover_repaint()
        return True


class GgsMapToolVertexEdit(GgsEditTool):

    vertexMoved = Signal(int, int)

    draftCommitted = Signal(object)

    draftChanged = Signal(bool)

    VERTEX_MODES = ("all", "select", "add", "move", "delete",
                    "select_rect", "select_lasso")

    _SNAP_TOOL = True

    def __init__(self, canvas=None, session=None, layer=None, snapper=None,
                 layer_provider=None, selection=None, parent=None):
        super().__init__("vertex_edit", canvas, session, layer, snapper,
                         layer_provider, parent)
        self._selection = selection
        self._mode = "all"
        self._fid = -1
        self._vi = -1
        self._part = 0
        self._ring = 0
        self._drag_from = None
        self._cur = None
        self._hover = None
        self._sel = set()
        self._draft = {}
        self._draft_flag = False
        self._drag_batch = False
        self._drag_base = {}
        self._band_from = None
        self._band_cur = None
        self._band_pts = []
        self._rel_at = None

    def setMode(self, mode):
        m = str(mode or "all")
        self._mode = m if m in self.VERTEX_MODES else "all"
        self._fid = self._vi = -1
        self._drag_from = self._cur = None
        self._drag_batch = False
        self._drag_base = {}
        self._band_from = self._band_cur = None
        self._band_pts = []
        self._hover_repaint()
        return self._mode

    def mode(self):
        return self._mode

    def statusHint(self):
        return {
            "select": _tr("选择折点"),
            "select_rect": _tr("折点：拖出矩形，框选范围内的折点"),
            "select_lasso": _tr("套索选择折点"),
            "add": _tr("折点：在线段上单击插入新折点"),
            "move": _tr("折点：按住折点拖动，整组一起移动"),
            "delete": _tr("删除折点"),
        }.get(self._mode,
              _tr("编辑折点"))

    def _selected_fids(self, lyr):
        sel = self._selection
        if sel is None:
            return []
        try:
            return [int(f) for f in sel.fids(lyr)]
        except Exception:
            _log.exception("silent exception in _selected_fids")
            return []

    def _near_fids(self, lyr, map_point, tol):
        try:
            from ggis.core.expr.query import hit_fids
            return set(int(f) for f in
                       hit_fids(lyr, map_point.x(), map_point.y(), tol))
        except Exception:
            _log.exception("silent exception in _near_fids")
            return None

    def _pick_vertex(self, lyr, map_point):
        map_point = self._layer_pt(map_point)
        tol = self._layer_tol(identify_tolerance(self._canvas, 8))
        sel = self._selected_fids(lyr)
        if not sel:
            return None
        near = self._near_fids(lyr, map_point, tol)
        if near is not None:
            sel = [f for f in sel if f in near or f in self._draft]
            if not sel:
                return None
        best = None
        from ggis.core.model.snapping import _iter_parts
        try:
            import numpy as _np
        except Exception:
            _log.exception("silent exception in _pick_vertex")
            _np = None
        _mx = float(map_point.x())
        _my = float(map_point.y())
        _tol2 = float(tol) * float(tol)
        for fid in sel:
            _g = self._geom_of(lyr, fid)
            if _g is None:
                continue
            for part, ring, coords in _iter_parts(_g) or ():
                if not coords:
                    continue
                if _np is not None and len(coords) >= 16:
                    try:
                        a = _np.asarray(coords, dtype=float)
                        dx = a[:, 0] - _mx
                        dy = a[:, 1] - _my
                        d2 = dx * dx + dy * dy
                        k = int(_np.argmin(d2))
                        d2min = float(d2[k])
                        if d2min <= _tol2 and (best is None
                                               or d2min < best[0] * best[0]):
                            _x, _y = coords[k]
                            best = (d2min ** 0.5, fid, part, ring, k, _x, _y)
                        continue
                    except Exception:
                        _log.exception("silent exception in _pick_vertex")
                for i, (x, y) in enumerate(coords):
                    d = math.hypot(x - _mx, y - _my)
                    if d <= tol and (best is None or d < best[0]):
                        best = (d, fid, part, ring, i, x, y)
        return best

    def _pick_segment(self, lyr, map_point):
        map_point = self._layer_pt(map_point)
        tol = self._layer_tol(identify_tolerance(self._canvas, 8))
        sel = self._selected_fids(lyr)
        if not sel:
            return None
        near = self._near_fids(lyr, map_point, tol)
        if near is not None:
            sel = [f for f in sel if f in near or f in self._draft]
            if not sel:
                return None
        best = None
        from ggis.core.model.snapping import _iter_parts
        for fid in sel:
            _g = self._geom_of(lyr, fid)
            if _g is None:
                continue
            for part, ring, coords in _iter_parts(_g) or ():
                for i in range(len(coords) - 1):
                    ax, ay = coords[i]
                    bx, by = coords[i + 1]
                    px, py = map_point.x(), map_point.y()
                    vx, vy = bx - ax, by - ay
                    L2 = vx * vx + vy * vy
                    if L2 <= 0:
                        continue
                    t = ((px - ax) * vx + (py - ay) * vy) / L2
                    if t < 0 or t > 1:
                        continue
                    qx, qy = ax + t * vx, ay + t * vy
                    d = math.hypot(qx - px, qy - py)
                    if d <= tol and (best is None or d < best[0]):
                        best = (d, fid, part, ring, i, qx, qy)
        return best

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        lyr = self.layer()
        s = self._editing()
        if lyr is None or s is None:
            return False
        mode = self._mode

        if mode in ("select_rect", "select_lasso"):
            p = (event.position().x(), event.position().y())
            self._band_from = self._band_cur = p
            self._band_pts = [p]
            self._fid = self._vi = -1
            self._hover_repaint()
            return True

        if mode == "delete" and self._sel:
            self._draft_delete_vertices(
                lyr, [(f, 0, 0, k) for f, k in self._sel])
            self._sel = set()
            self._fid = self._vi = -1
            self._drag_from = self._cur = None
            self._hover_repaint()
            return True

        if mode == "add":
            seg = self._pick_segment(lyr, map_point)
            if seg is None:
                return True
            _d, fid, part, ring, i, qx, qy = seg
            if self._draft_insert_vertex(lyr, fid, i, qx, qy,
                                         part=part, ring=ring) is not None:
                self._hover_repaint()
            return True

        hit = self._pick_vertex(lyr, map_point)
        if hit is None:
            self._fid = self._vi = -1
            self._drag_from = self._cur = None
            self._hover_repaint()
            return True
        _d, fid, part, ring, i, x, y = hit

        if mode == "delete":
            self._draft_delete_vertex(lyr, fid, i, part=part, ring=ring)
            self._fid = self._vi = -1
            self._drag_from = self._cur = None
            self._hover_repaint()
            return True

        self._fid, self._part, self._ring, self._vi = fid, part, ring, i
        if mode == "select":
            self._sel = {(int(fid), int(i))}
            self._drag_from = self._cur = None
            self._hover_repaint()
            return True
        self._drag_batch = bool(self._sel and len(self._sel) > 1
                                and (int(fid), int(i)) in self._sel)
        self._drag_from = (x, y)
        self._cur = (x, y)
        self._drag_base = {}
        if self._drag_batch:
            for _f, _i in self._sel:
                _c = self._draft_coords(lyr, int(_f), 0, 0)
                if _c is not None and 0 <= int(_i) < len(_c):
                    self._drag_base[(int(_f), int(_i))] = _c[int(_i)]
        self._repaint()
        return True


    def _notify_draft(self):
        now = bool(self._draft)
        if now == self._draft_flag:
            return
        self._draft_flag = now
        try:
            self.draftChanged.emit(now)
        except Exception:
            _log.exception("silent exception in _notify_draft")

    def has_draft(self):
        return bool(self._draft)

    def reset_draft(self):
        had = self._discard_draft()
        if had:
            try:
                self._canvas.showMessage(
                    _tr("已重置折点编辑：未确认的改动已丢弃"))
            except Exception:
                _log.exception("silent exception in reset_draft")
        return had

    def cancel_edit(self):
        had = self._discard_draft()
        self._sel = set()
        try:
            self._hover_repaint()
        except Exception:
            _log.exception("silent exception in cancel_edit")
        return had

    def _discard_draft(self):
        had = bool(self._draft)
        self._draft.clear()
        self._notify_draft()
        self._drag_batch = False
        self._drag_base = {}
        self._fid = self._vi = -1
        self._drag_from = self._cur = None
        self._band_from = self._band_cur = None
        self._band_pts = []
        if had:
            self._hover_repaint()
        return had

    def commit_draft(self):
        s = self._editing()
        lyr = self.layer()
        if s is None or lyr is None or not self._draft:
            return False
        try:
            gcount = len(lyr.geoms())
            attrs = lyr.attrs()
        except Exception:
            _log.exception("silent exception in commit_draft")
            return False
        items = []
        for _f, _g in list(self._draft.items()):
            f = int(_f)
            try:
                a = dict(attrs[f]) if 0 <= f < len(attrs) and attrs[f] else {}
            except Exception:
                _log.exception("silent exception in commit_draft")
                a = {}
            items.append((f, _g, a))
        self._draft.clear()
        self._notify_draft()
        self._fid = self._vi = -1
        self._sel = set()
        if not items:
            return False
        new_fids = []
        s.begin_batch()
        try:
            s.delete_features(sorted([f for f, _g, _a in items if f < gcount],
                                     reverse=True))
            for _f, g, a in items:
                try:
                    _nf = s.add_feature(g, a)
                except Exception:
                    _log.exception("silent exception in commit_draft")
                    _nf = None
                if _nf is not None:
                    new_fids.append(int(_nf))
        finally:
            s.end_batch()
        try:
            if self._selection is not None:
                self._selection.clear(lyr)
        except Exception:
            _log.exception("silent exception in commit_draft")
        try:
            self._canvas.showMessage(
                _tr("已确认 {0} 个要素的折点编辑").format(len(items)))
        except Exception:
            _log.exception("silent exception in commit_draft")
        self._repaint()
        try:
            self.draftCommitted.emit(list(new_fids))
        except Exception:
            _log.exception("silent exception in commit_draft")
        return True

    def _geom_of(self, lyr, fid):
        g = self._draft.get(int(fid))
        if g is not None:
            return g
        try:
            geoms = lyr.geoms()
            if 0 <= int(fid) < len(geoms):
                return geoms[int(fid)]
        except Exception:
            _log.exception("silent exception in _geom_of")
        return None

    def _draft_coords(self, lyr, fid, part, ring):
        geom = self._geom_of(lyr, fid)
        if geom is None:
            return None
        from ggis.core.model.snapping import _iter_parts
        for p, r, coords in _iter_parts(geom) or ():
            if p == part and r == ring:
                return list(coords)
        return None

    def _draft_apply(self, lyr, fid, part, ring, coords):
        base = self._geom_of(lyr, fid)
        if base is None:
            return None
        new = None
        s = self.session()
        if s is not None:
            try:
                new = s._rebuild_geom(base, part, ring, coords)
            except Exception:
                _log.exception("silent exception in _draft_apply")
                new = None
        if new is None:
            return None
        self._draft[int(fid)] = new
        self._notify_draft()
        return new

    def _draft_move_vertex(self, lyr, fid, index, x, y, part=0, ring=0):
        coords = self._draft_coords(lyr, fid, part, ring)
        if coords is None or not (0 <= index < len(coords)):
            return None
        coords[index] = (float(x), float(y))
        closed = len(coords) > 2 and coords[0] == coords[-1]
        if closed and index == 0:
            coords[-1] = (float(x), float(y))
        elif closed and index == len(coords) - 1:
            coords[0] = (float(x), float(y))
        return self._draft_apply(lyr, fid, part, ring, coords)

    def _draft_insert_vertex(self, lyr, fid, segment, x, y, part=0, ring=0):
        coords = self._draft_coords(lyr, fid, part, ring)
        if coords is None:
            return None
        i = int(segment) + 1
        if not (0 < i < len(coords)):
            return None
        coords.insert(i, (float(x), float(y)))
        return self._draft_apply(lyr, fid, part, ring, coords)

    def _draft_delete_vertex(self, lyr, fid, index, part=0, ring=0):
        coords = self._draft_coords(lyr, fid, part, ring)
        if coords is None or not (0 <= index < len(coords)):
            return None
        closed = len(coords) > 2 and coords[0] == coords[-1]
        if closed:
            if len(coords) <= 4:
                return None
            if index == 0:
                coords.pop(-1)
                coords[0] = coords[-1]
                coords.append(coords[0])
                return self._draft_apply(lyr, fid, part, ring, coords)
            if index == len(coords) - 1:
                coords.pop(-1)
                coords[0] = coords[-1]
                coords.append(coords[0])
                return self._draft_apply(lyr, fid, part, ring, coords)
            coords.pop(index)
        else:
            if len(coords) <= 2:
                return None
            coords.pop(index)
        return self._draft_apply(lyr, fid, part, ring, coords)

    def _draft_move_vertices(self, lyr, fid, moves, part=0, ring=0):
        coords = self._draft_coords(lyr, fid, part, ring)
        if coords is None:
            return None
        closed = len(coords) > 2 and coords[0] == coords[-1]
        hit = False
        for item in moves or ():
            try:
                index, x, y = int(item[0]), float(item[1]), float(item[2])
            except Exception:
                _log.exception("silent exception in _draft_move_vertices")
                continue
            if not (0 <= index < len(coords)):
                continue
            coords[index] = (x, y)
            hit = True
            if closed and index == 0:
                coords[-1] = (x, y)
            elif closed and index == len(coords) - 1:
                coords[0] = (x, y)
        if not hit:
            return None
        return self._draft_apply(lyr, fid, part, ring, coords)

    def _draft_drag_to(self, lyr, x, y):
        if lyr is None or self._drag_from is None:
            return
        try:
            dx = float(x) - float(self._drag_from[0])
            dy = float(y) - float(self._drag_from[1])
        except Exception:
            _log.exception("silent exception in _draft_drag_to")
            return
        if self._drag_batch:
            by_fid = {}
            for (_f, _i), (_bx, _by) in (self._drag_base or {}).items():
                by_fid.setdefault(int(_f), []).append(
                    (int(_i), _bx + dx, _by + dy))
            for _f, moves in by_fid.items():
                self._draft_move_vertices(lyr, _f, moves, part=0, ring=0)
            return
        if self._fid < 0:
            return
        self._draft_move_vertex(lyr, self._fid, self._vi, x, y,
                                part=self._part, ring=self._ring)

    def _draft_delete_vertices(self, lyr, ids):
        groups = {}
        for item in ids or ():
            try:
                fid, part, ring, index = (int(item[0]), int(item[1]),
                                          int(item[2]), int(item[3]))
            except Exception:
                _log.exception("silent exception in _draft_delete_vertices")
                continue
            groups.setdefault((fid, part, ring), set()).add(index)
        total = 0
        for (fid, part, ring), idxs in groups.items():
            coords = self._draft_coords(lyr, fid, part, ring)
            if coords is None:
                continue
            closed = len(coords) > 2 and coords[0] == coords[-1]
            floor = 4 if closed else 2
            removed = 0
            for i in sorted(idxs, reverse=True):
                if not (0 <= i < len(coords)) or len(coords) <= floor:
                    continue
                coords.pop(i)
                removed += 1
            if closed and removed:
                coords[-1] = coords[0]
            if removed:
                self._draft_apply(lyr, fid, part, ring, coords)
                total += removed
        return total

    def _previewing(self):
        return (self._drag_from is not None) or (self._band_from is not None)

    def mouseMove(self, event, map_point):
        lyr = self.layer()
        if lyr is None:
            return False
        if self._band_from is not None:
            p = (event.position().x(), event.position().y())
            self._band_cur = p
            if self._mode == "select_lasso":
                self._band_pts.append(p)
            self._repaint()
            return True
        if self._fid < 0 or self._drag_from is None:
            hit = self._pick_vertex(lyr, map_point)
            self._hover = (hit[1], hit[4], hit[5], hit[6]) if hit else None
            self._snap(map_point)
            self._hover_repaint()
            return False
        mp = self._snap(map_point, exclude_vertex=self._snap_exclude())
        self._cur = (mp.x(), mp.y())
        self._draft_drag_to(lyr, mp.x(), mp.y())
        self._repaint()
        return True

    def mouseRelease(self, event, map_point):
        try:
            import time as _time
            self._rel_at = _time.monotonic()
        except Exception:
            _log.exception("silent exception in mouseRelease")
            self._rel_at = None
        if self._band_from is not None:
            lyr = self.layer()
            if lyr is not None:
                n = self._apply_band(lyr)
                try:
                    self._canvas.showMessage(
                        _tr("已选中 {0} 个折点").format(n))
                except Exception:
                    _log.exception("silent exception in mouseRelease")
            self._band_from = self._band_cur = None
            self._band_pts = []
            self._hover_repaint()
            return True
        if self._fid < 0 or self._drag_from is None:
            return False
        s = self._editing()
        lyr = self.layer()
        if lyr is None:
            self._hover_repaint()
            return True
        fid, vi = self._fid, self._vi
        part, ring = self._part, self._ring
        x, y = self._cur or (None, None)
        fx, fy = self._drag_from or (None, None)
        self._fid = self._vi = -1
        self._drag_from = None
        self._cur = None
        if s is None or x is None:
            self._hover_repaint()
            return True
        if abs(x - fx) < 1e-12 and abs(y - fy) < 1e-12:
            self._drag_batch = False
            self._hover_repaint()
            return True
        if self._drag_batch and self._sel:
            self._drag_batch = False
            dx = x - fx
            dy = y - fy
            by_fid = {}
            for (_f, _i), (_bx, _by) in (self._drag_base or {}).items():
                by_fid.setdefault(int(_f), []).append(
                    (int(_i), _bx + dx, _by + dy))
            for _f, moves in by_fid.items():
                self._draft_move_vertices(lyr, _f, moves, part=0, ring=0)
            self._drag_base = {}
            self._hover_repaint()
            return True
        self._drag_batch = False
        self._drag_base = {}
        self._draft_move_vertex(lyr, fid, vi, x, y, part=part, ring=ring)
        self._hover_repaint()
        return True

    def mouseDoubleClick(self, event, map_point):
        return self.commit_draft()

    def keyPress(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            return bool(self._discard_draft())
        if k != Qt.Key.Key_Delete:
            return False
        lyr = self.layer()
        s = self._editing()
        if lyr is None or s is None:
            return False
        if self._sel:
            self._draft_delete_vertices(
                lyr, [(f, 0, 0, i) for f, i in self._sel])
            self._sel = set()
        elif self._fid >= 0:
            self._draft_delete_vertices(
                lyr, [(self._fid, self._part, self._ring, self._vi)])
        else:
            return False
        self._fid = self._vi = -1
        self._hover_repaint()
        return True

    def paint_overlay(self, painter, settings):
        super().paint_overlay(painter, settings)
        lyr = self.layer()
        if lyr is None:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing, True)
        from ggis.core.model.snapping import _iter_parts
        try:
            if self._draft:
                painter.setPen(QPen(QColor("#ffd24d"), 1.8))
                painter.setBrush(QBrush(QColor(255, 210, 77, 45)))
                _tf = None
                try:
                    if lyr is not None and self._canvas is not None:
                        _tf = crs_transformer(crs_of(lyr),
                                              crs_of(self._canvas))
                except Exception:
                    _log.exception("silent exception in paint_overlay")
                    _tf = None
                try:
                    import numpy as _np
                except Exception:
                    _log.exception("silent exception in paint_overlay")
                    _np = None
                _sx = _sy = 0.0
                _x0 = _y1 = 0.0
                try:
                    _st = self._canvas._map_settings() if self._canvas else None
                    if _st is not None and _st.is_ready():
                        _e = _st.extent()
                        _sx = float(_st.scale_x())
                        _sy = float(_st.scale_y())
                        _x0 = float(_e.xmin)
                        _y1 = float(_e.ymax)
                except Exception:
                    _log.exception("silent exception in paint_overlay")
                    _sx = _sy = 0.0
                for _g in list(self._draft.values()):
                    for _p, _r, coords in _iter_coords(_g):
                        if len(coords) < 2:
                            continue
                        pts = None
                        if _np is not None and len(coords) >= 8 \
                                and _sx > 0.0:
                            try:
                                from ..core.crs import convert_xy
                                _a = _np.asarray(coords, dtype=float)
                                if _tf is not None:
                                    _a = convert_xy(_a, _tf)
                                _px = (_a[:, 0] - _x0) * _sx
                                _py = (_y1 - _a[:, 1]) * _sy
                                pts = [QPointF(_u, _v) for _u, _v in
                                       zip(_px.tolist(), _py.tolist())]
                            except Exception:
                                _log.exception("silent exception in paint_overlay")
                                pts = None
                        if pts is None:
                            pts = [self._to_screen_layer(x, y)
                                   for x, y in coords]
                            pts = [q for q in pts if q is not None]
                        if len(pts) >= 2:
                            painter.drawPolyline(QPolygonF(pts))
        except Exception:
            _log.exception("silent exception in paint_overlay")
        self._paint_vertex_handles(painter, lyr)
        self._paint_band(painter)
        painter.restore()

    def _handle_state_fingerprint(self, lyr, settings):
        try:
            e = settings.extent()
            vp = (round(float(e.xmin), 9), round(float(e.ymin), 9),
                  round(float(e.xmax), 9), round(float(e.ymax), 9),
                  int(settings.output_width()),
                  int(settings.output_height()),
                  round(float(self._canvas.devicePixelRatioF()), 4)
                  if self._canvas is not None else 1.0)
        except Exception:
            _log.exception("silent exception in _handle_state_fingerprint")
            vp = None
        try:
            sel_ids = tuple(sorted(int(f) for f in self._selected_fids(lyr)))
        except Exception:
            _log.exception("silent exception in _handle_state_fingerprint")
            sel_ids = ()
        try:
            draft_ids = tuple(sorted(int(k) for k in self._draft))
        except Exception:
            _log.exception("silent exception in _handle_state_fingerprint")
            draft_ids = ()
        live = self._live_vertex_keys()
        band = (self._mode, self._band_from, self._band_cur,
                len(self._band_pts))
        nsel = len(self._sel)
        sel_head = tuple(sorted(self._sel)[:8]) if nsel <= 4096 else ()
        from ggis.core.model.snapping import _iter_parts
        try:
            npts = sum(len(c) for g in self._draft.values()
                       for _p, _r, c in _iter_parts(g))
        except Exception:
            _log.exception("silent exception in _handle_state_fingerprint")
            npts = -1
        return (vp, sel_ids, live, band, nsel, sel_head,
                draft_ids, npts)

    _JUST_FINISHED_S = 0.35

    def _is_interacting_now(self):
        c = self._canvas
        if c is None:
            return False
        try:
            if bool(getattr(c, "_interacting", False)):
                return True
            if bool(getattr(c, "_panning", False)):
                return True
        except Exception:
            _log.exception("silent exception in _is_interacting_now")
        try:
            import time as _time
            t = getattr(c, "_last_wheel_t", None)
            if t is not None and (_time.monotonic() - float(t)) \
                    < float(self._JUST_FINISHED_S):
                return True
        except Exception:
            _log.exception("silent exception in _is_interacting_now")
        return False

    def _just_released(self):
        if getattr(self, "_rel_at", None) is None:
            return False
        try:
            import time as _time
            return (_time.monotonic() - float(self._rel_at)) \
                < float(self._JUST_FINISHED_S)
        except Exception:
            _log.exception("silent exception in _just_released")
            return False

    def _live_vertex_keys(self):
        out = set()
        if self._fid is not None and self._fid >= 0 and self._vi is not None \
                and self._vi >= 0:
            out.add((int(self._fid), int(self._vi)))
        if self._hover:
            try:
                out.add((int(self._hover[0]), int(self._hover[1])))
            except Exception:
                _log.exception("silent exception in _live_vertex_keys")
        return frozenset(out)

    def _paint_vertex_handles(self, painter, lyr):
        try:
            from PySide6.QtGui import QImage, QPainter
        except Exception:
            _log.exception("silent exception in _paint_vertex_handles")
            QImage = None
            QPainter = None
        if QImage is None or painter.device() is None:
            self._draw_handles_direct(painter, lyr)
            return
        try:
            settings = self._canvas._map_settings()
        except Exception:
            _log.exception("silent exception in _paint_vertex_handles")
            self._draw_handles_direct(painter, lyr)
            return
        try:
            dpr = float(self._canvas.devicePixelRatioF())
            w = max(1, int(round(painter.device().width() * dpr)))
            h = max(1, int(round(painter.device().height() * dpr)))
        except Exception:
            _log.exception("silent exception in _paint_vertex_handles")
            self._draw_handles_direct(painter, lyr)
            return
        gap = 0.0
        if self._is_interacting_now() or self._drag_from is not None \
                or self._band_from is not None:
            gap = 6.0
        elif self._just_released():
            gap = 6.0
        key = self._handle_state_fingerprint(lyr, settings) + (gap,)
        img = getattr(self, "_handle_img", None)
        if (img is None or getattr(self, "_handle_key", None) != key
                or img.isNull() or img.width() != w or img.height() != h):
            live = self._live_vertex_keys()
            img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
            img.setDevicePixelRatio(dpr)
            img.fill(0)
            p = QPainter(img)
            try:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                self._draw_handles_direct(p, lyr, w / dpr, h / dpr, live,
                                          gap)
            finally:
                p.end()
            self._handle_img = img
            self._handle_key = key
        try:
            painter.drawImage(0.0, 0.0, img)
        except Exception:
            _log.exception("silent exception in _paint_vertex_handles")
            self._draw_handles_direct(painter, lyr)
            return
        self._draw_live_handles(painter, lyr)

    def _vertex_style(self, fid, i):
        active = ((int(fid), int(i)) in self._sel
                  or (fid == self._fid and i == self._vi))
        hov = bool(self._hover and self._hover[0] == fid
                   and self._hover[1] == i)
        if active:
            return QColor("#ffd24d"), 1.6, QColor("#ffd24d")
        if hov:
            return QColor("#4dc3ff"), 1.4, QColor("#4dc3ff")
        return QColor("#ffffff"), 1.0, QColor("#0d1b26")

    def _draw_live_handles(self, painter, lyr):
        from ggis.core.model.snapping import _iter_parts
        keys = self._live_vertex_keys()
        if not keys:
            return
        h = float(VERTEX_HALF)
        d = h * 2.0
        for fid, vi in sorted(keys):
            try:
                _g = self._geom_of(lyr, fid)
                if _g is None:
                    continue
                coords = None
                for _p, _r, c in _iter_parts(_g) or ():
                    if 0 <= vi < len(c):
                        coords = c
                        break
                if coords is None:
                    continue
                x, y = coords[vi]
                if fid == self._fid and vi == self._vi and self._cur:
                    x, y = self._cur
                sp = self._to_screen_layer(x, y)
                if sp is None:
                    continue
                pen_c, pw, brush_c = self._vertex_style(fid, vi)
                painter.setPen(QPen(pen_c, pw))
                painter.setBrush(QBrush(brush_c))
                painter.drawRect(QRectF(sp.x() - h, sp.y() - h, d, d))
            except Exception:
                _log.exception("silent exception in _draw_live_handles")
                continue

    def _draw_handles_direct(self, painter, lyr, w=0, h=0, skip=(), gap=0.0):
        from ggis.core.model.snapping import _iter_parts
        tf = None
        try:
            if lyr is not None and self._canvas is not None:
                tf = crs_transformer(crs_of(lyr), crs_of(self._canvas))
        except Exception:
            _log.exception("silent exception in _draw_handles_direct")
            tf = None
        buckets = ([], [], [])
        try:
            from ..core.crs import convert_xy
            import numpy as _np
        except Exception:
            _log.exception("silent exception in _draw_handles_direct")
            _np = None
        sx_k = sy_k = 0.0
        x0 = y1 = 0.0
        try:
            st = self._canvas._map_settings() if self._canvas else None
            if st is not None and st.is_ready():
                _e = st.extent()
                sx_k = float(st.scale_x())
                sy_k = float(st.scale_y())
                x0 = float(_e.xmin)
                y1 = float(_e.ymax)
        except Exception:
            _log.exception("silent exception in _draw_handles_direct")
            sx_k = sy_k = 0.0
        for fid in self._selected_fids(lyr):
            _g = self._geom_of(lyr, fid)
            if _g is None:
                continue
            for _part, _ring, coords in _iter_parts(_g) or ():
                if not coords:
                    continue
                keep_idx = None
                if _np is not None and len(coords) >= 8 and sx_k > 0.0:
                    try:
                        arr = _np.asarray(coords, dtype=float)
                        if tf is not None:
                            arr = convert_xy(arr, tf)
                        px = (arr[:, 0] - x0) * sx_k
                        py = (y1 - arr[:, 1]) * sy_k
                        xs_l = px.tolist()
                        ys_l = py.tolist()
                        n_r = len(xs_l)
                        if w > 0 and h > 0:
                            inx = [i for i in range(n_r)
                                   if -16.0 <= xs_l[i] <= w + 16.0]
                        else:
                            inx = None
                        if gap > 0.5:
                            ig = int(gap)
                            seen_c = set()
                            sel_i = []
                            rng = inx if inx is not None else range(n_r)
                            for i in rng:
                                c2 = (int(xs_l[i]) // ig, int(ys_l[i]) // ig)
                                if c2 in seen_c:
                                    continue
                                seen_c.add(c2)
                                sel_i.append(i)
                            inx = sel_i
                        keep_idx = [(i, QPointF(xs_l[i], ys_l[i]))
                                    for i in (inx if inx is not None
                                              else range(n_r))]
                    except Exception:
                        _log.exception("silent exception in _draw_handles_direct")
                        keep_idx = None
                if keep_idx is None:
                    keep_idx = [(i, self._to_screen_layer(x, y))
                                for i, (x, y) in enumerate(coords)]
                _sel_set = self._sel
                _hv = self._hover
                _fid_c = self._fid
                _vi_c = self._vi
                b0, b1, b2 = buckets
                for i, sp in keep_idx:
                    if sp is None:
                        continue
                    if w > 0 and h > 0 and (
                            sp.x() < -16.0 or sp.x() > w + 16.0
                            or sp.y() < -16.0 or sp.y() > h + 16.0):
                        continue
                    if (int(fid), int(i)) in skip:
                        continue
                    if ((int(fid), int(i)) in _sel_set
                            or (fid == _fid_c and i == _vi_c)):
                        b2.append(sp)
                    elif _hv is not None and _hv[0] == fid and _hv[1] == i:
                        b1.append(sp)
                    else:
                        b0.append(sp)
        h = float(VERTEX_HALF)
        styles = ((QColor("#ffffff"), 1.0, QColor("#0d1b26")),
                  (QColor("#4dc3ff"), 1.4, QColor("#4dc3ff")),
                  (QColor("#ffd24d"), 1.6, QColor("#ffd24d")))
        d = h * 2.0
        g = float(gap or 0.0)
        for gi, pts in enumerate(buckets):
            if not pts:
                continue
            pen_c, pw, brush_c = styles[gi]
            pen = QPen(pen_c, pw)
            brush = QBrush(brush_c)
            painter.setPen(pen)
            painter.setBrush(brush)
            dr = painter.drawRect
            if g > 0.5 and len(pts) > 64:
                seen = set()
                ig = int(g)
                for sp in pts:
                    cell = (int(sp.x()) // ig, int(sp.y()) // ig)
                    if cell in seen:
                        continue
                    seen.add(cell)
                    dr(QRectF(sp.x() - h, sp.y() - h, d, d))
            else:
                for sp in pts:
                    dr(QRectF(sp.x() - h, sp.y() - h, d, d))

    def _band_points(self):
        a, b = self._band_from, self._band_cur
        if a is None or b is None:
            return []
        if self._mode == "select_lasso":
            return list(self._band_pts)
        x0, y0 = a
        x1, y1 = b
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    @staticmethod
    def _pt_in_poly(px, py, poly):
        inside = False
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            if (y0 > py) != (y1 > py):
                xin = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
                if px < xin:
                    inside = not inside
        return inside

    def _apply_band(self, lyr):
        poly = self._band_points()
        if len(poly) < 3:
            self._sel = set()
            return 0
        from ggis.core.model.snapping import _iter_parts
        picked = set()
        for fid in self._selected_fids(lyr):
            _g = self._geom_of(lyr, fid)
            if _g is None:
                continue
            for _part, _ring, coords in _iter_parts(_g) or ():
                for i, (x, y) in enumerate(coords):
                    sp = self._to_screen_layer(x, y)
                    if sp is None:
                        continue
                    if self._pt_in_poly(sp.x(), sp.y(), poly):
                        picked.add((int(fid), int(i)))
        self._sel = picked
        return len(picked)

    def _paint_band(self, painter):
        if self._band_from is None or self._band_cur is None:
            return
        poly = self._band_points()
        if len(poly) < 2:
            return
        painter.setPen(QPen(QColor("#4dc3ff"), 1.0, Qt.PenStyle.DashLine))
        painter.setBrush(QBrush(QColor(77, 195, 255, 36)))
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in poly]))
