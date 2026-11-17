# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QGuiApplication, QImage, QPainter,
                           QPen, QPolygonF)

from ggis.core.expr.query import (features_in_rect, features_intersecting, hit_fids,
                          hit_test_layers, map_tolerance, to_layer_geometry,
                          to_layer_point, to_layer_rect, to_layer_tolerance)
import logging
_log = logging.getLogger("gmagis")

__all__ = [
    "GgsMapTool", "GgsMapToolIdentify", "GgsMapToolSelect",
    "GgsMapToolProfile", "GgsMapToolSpectral",
    "SELECT_SHAPES", "identify_tolerance", "selection_mode",
]

IDENTIFY_TOL_PX = 5.0
DRAG_PX = 4.0
SELECT_MAX = 20000


def _identify_tol_px():
    try:
        from ggis.core.app import settings as _S
        v = _S.get("identify_tolerance_px", IDENTIFY_TOL_PX)
        v = float(v)
        return v if v > 0 else IDENTIFY_TOL_PX
    except Exception:
        _log.exception("silent exception in _identify_tol_px")
        return IDENTIFY_TOL_PX


def identify_tolerance(canvas, pixels=None):
    if canvas is None:
        return 0.0
    if pixels is None:
        pixels = _identify_tol_px()
    try:
        return map_tolerance(canvas.map_settings(), pixels)
    except Exception:
        _log.exception("silent exception in identify_tolerance")
        return 0.0


def selection_mode(modifiers):
    ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
    shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
    if ctrl and shift:
        return "intersect"
    if ctrl:
        return "subtract"
    if shift:
        return "add"
    return "replace"


class GgsMapTool(QObject):

    toolFinished = Signal()

    def __init__(self, name="", canvas=None, cursor=None, parent=None):
        super().__init__(parent)
        self._name = str(name or "")
        self._canvas = canvas
        self._cursor = cursor
        self._prev_cursor = None

    def name(self):
        return self._name

    def canvas(self):
        return self._canvas

    def setCanvas(self, canvas):
        self._canvas = canvas

    def isEditTool(self):
        return False

    def isInteractive(self):
        return False

    def statusHint(self):
        return ""

    def activate(self):
        c = self._canvas
        if c is not None and self._cursor is not None:
            try:
                self._prev_cursor = c.cursor()
                c.setCursor(self._cursor)
            except Exception:
                _log.exception("silent exception in activate")

    def deactivate(self):
        c = self._canvas
        if c is not None and self._prev_cursor is not None:
            try:
                c.setCursor(self._prev_cursor)
            except Exception:
                _log.exception("silent exception in deactivate")
        self._prev_cursor = None

    def mousePress(self, event, map_point):
        return False

    def mouseMove(self, event, map_point):
        return False

    def mouseRelease(self, event, map_point):
        return False

    def mouseDoubleClick(self, event, map_point):
        return False

    def keyPress(self, event):
        return False

    def paint_overlay(self, painter, settings):
        return

    @staticmethod
    def _draw_sample_marker(painter, sp):
        try:
            _dev = painter.device()
            _dpr = float(getattr(_dev, "devicePixelRatioF", lambda: 1.0)() or 1.0)
        except Exception:
            _log.exception("silent exception in _draw_sample_marker")
            _dpr = 1.0
        if _dpr <= 0:
            _dpr = 1.0
        r = 6.5
        ext = r + 3.0
        pad = 5.0
        half = ext + pad
        w = 2.0 * half
        h = 2.0 * half
        img = QImage(max(1, int(round(w * _dpr))),
                     max(1, int(round(h * _dpr))),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(_dpr)
        img.fill(0)
        ip = QPainter(img)
        try:
            ip.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            ip.translate(-(sp.x() - half), -(sp.y() - half))
            pen = QPen(QColor(0, 191, 255), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            ip.setPen(pen)
            ip.setBrush(Qt.BrushStyle.NoBrush)
            ip.drawEllipse(sp, r, r)
            ip.drawLine(QPointF(sp.x() - ext, sp.y()),
                        QPointF(sp.x() + ext, sp.y()))
            ip.drawLine(QPointF(sp.x(), sp.y() - ext),
                        QPointF(sp.x(), sp.y() + ext))
        finally:
            ip.end()
        painter.drawImage(QPointF(sp.x() - half, sp.y() - half), img)

    @staticmethod
    def _draw_coord_dot(painter, sp):
        try:
            _dev = painter.device()
            _dpr = float(getattr(_dev, "devicePixelRatioF", lambda: 1.0)() or 1.0)
        except Exception:
            _log.exception("silent exception in _draw_coord_dot")
            _dpr = 1.0
        if _dpr <= 0:
            _dpr = 1.0
        r = 4.0
        pad = 4.0
        half = r + pad
        w = 2.0 * half
        h = 2.0 * half
        img = QImage(max(1, int(round(w * _dpr))),
                     max(1, int(round(h * _dpr))),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(_dpr)
        img.fill(0)
        ip = QPainter(img)
        try:
            ip.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            ip.translate(-(sp.x() - half), -(sp.y() - half))
            pen = QPen(QColor(255, 120, 0), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            ip.setPen(pen)
            ip.setBrush(Qt.BrushStyle.NoBrush)
            ip.drawEllipse(sp, r, r)
        finally:
            ip.end()
        painter.drawImage(QPointF(sp.x() - half, sp.y() - half), img)

    def _repaint(self):
        if self._canvas is not None:
            try:
                self._canvas.update()
            except Exception:
                _log.exception("silent exception in _repaint")


class GgsMapToolProfile(GgsMapTool):

    picked = Signal(float, float)

    def __init__(self, canvas=None, parent=None):
        super().__init__("raster_profile", canvas,
                         Qt.CursorShape.CrossCursor, parent)
        self._pt = None

    def isInteractive(self):
        return True

    def statusHint(self):
        return "剖面曲线：点击地图上的位置（再点其他位置就换一张图）"

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        try:
            self.picked.emit(float(map_point.x()), float(map_point.y()))
        except Exception:
            _log.exception("silent exception in mousePress")
            return False
        return True

    def set_display_point(self, cx, cy):
        self._pt = (float(cx), float(cy))
        self._repaint()

    def clear_display_point(self):
        self._pt = None
        self._repaint()

    def paint_overlay(self, painter, settings):
        pt = self._pt
        if not pt:
            return
        cv = self._canvas
        ext = None
        try:
            ext = cv.extent()
        except Exception:
            _log.exception("silent exception in paint_overlay")
            ext = None
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(QColor(0, 191, 255))
            pen.setCosmetic(True)
            pen.setWidthF(1.5)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            px, py = pt[0], pt[1]
            try:
                sp = settings.map_to_pixel(px, py)
            except Exception:
                _log.exception("silent exception in paint_overlay")
                sp = None
            if ext is not None and sp is not None:
                a = settings.map_to_pixel(ext.xmin, py)
                b = settings.map_to_pixel(ext.xmax, py)
                painter.drawLine(a, b)
                c = settings.map_to_pixel(px, ext.ymin)
                d = settings.map_to_pixel(px, ext.ymax)
                painter.drawLine(c, d)
            if sp is not None:
                self._draw_sample_marker(painter, sp)
        finally:
            painter.restore()


class GgsMapToolSpectral(GgsMapTool):

    picked = Signal(float, float)

    def __init__(self, canvas=None, parent=None):
        super().__init__("spectral", canvas,
                         Qt.CursorShape.CrossCursor, parent)
        self._pt = None

    def isInteractive(self):
        return True

    def statusHint(self):
        return "光谱曲线：点击地图取一个取样点（多图层共用）"

    def set_display_point(self, cx, cy):
        self._pt = (float(cx), float(cy))
        self._repaint()

    def clear_display_point(self):
        self._pt = None
        self._repaint()

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        try:
            self.picked.emit(float(map_point.x()), float(map_point.y()))
        except Exception:
            _log.exception("silent exception in mousePress")
            return False
        return True

    def paint_overlay(self, painter, settings):
        pt = self._pt
        if not pt:
            return
        try:
            sp = settings.map_to_pixel(pt[0], pt[1])
        except Exception:
            _log.exception("silent exception in paint_overlay")
            return
        painter.save()
        try:
            self._draw_sample_marker(painter, sp)
        finally:
            painter.restore()


class GgsMapToolAddCoord(GgsMapTool):

    picked = Signal(float, float)

    def __init__(self, canvas=None, parent=None):
        super().__init__("coord_add", canvas,
                         Qt.CursorShape.CrossCursor, parent)
        self._pts = []

    def isInteractive(self):
        return True

    def statusHint(self):
        return "坐标转换：左键点击地图添加坐标点"

    def set_display_points(self, pts):
        self._pts = list(pts or [])
        self._repaint()

    def clear_display_points(self):
        self._pts = []
        self._repaint()

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        try:
            self.picked.emit(float(map_point.x()), float(map_point.y()))
        except Exception:
            _log.exception("silent exception in mousePress")
            return False
        return True

    def paint_overlay(self, painter, settings):
        if not self._pts:
            return
        for (x, y) in self._pts:
            try:
                sp = settings.map_to_pixel(x, y)
            except Exception:
                _log.exception("silent exception in paint_overlay")
                continue
            self._draw_coord_dot(painter, sp)


class GgsMapToolIdentify(GgsMapTool):

    identified = Signal(object)

    def __init__(self, canvas=None, layer_provider=None, parent=None):
        super().__init__("identify", canvas,
                         Qt.CursorShape.CrossCursor, parent)
        self._layer_provider = layer_provider
        self.tol_px = _identify_tol_px()
        self._identify_pt = None
        self._hl_items = []

    def isInteractive(self):
        return True

    def statusHint(self):
        return "识别：左键点击地图上的要素"

    def last_point(self):
        pt = self._identify_pt
        if pt is None:
            return None
        try:
            return (float(pt.x()), float(pt.y()))
        except Exception:
            _log.exception("silent exception in last_point")
            return None

    def setLayerProvider(self, fn):
        self._layer_provider = fn

    def _layers(self):
        if self._layer_provider is not None:
            try:
                return list(self._layer_provider())
            except Exception:
                _log.exception("silent exception in _layers")
                return []
        c = self._canvas
        if c is not None:
            try:
                return list(c.project().layers())
            except Exception:
                _log.exception("silent exception in _layers")
                return []
        return []

    def mousePress(self, event, map_point):
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._identify_pt = QPointF(map_point)
        self._repaint()
        try:
            _cv = self._canvas
            if _cv is not None:
                _sel = _cv.selection()
                if _sel is not None:
                    _sel.clear()
        except Exception:
            _log.exception("silent exception in mousePress")
        tol = identify_tolerance(self._canvas, self.tol_px)
        try:
            hits = hit_test_layers(self._layers(), map_point.x(),
                                   map_point.y(), tol,
                                   source=self._canvas, with_raster=True)
        except Exception:
            _log.exception("silent exception in mousePress")
            hits = []
        self._store_highlight(hits)
        self.identified.emit(hits)
        self._repaint()
        return True

    def paint_overlay(self, painter, settings):
        self._draw_identify_highlight(painter, settings)
        pt = self._identify_pt
        if pt is None:
            return
        try:
            sp = settings.map_to_pixel(pt.x(), pt.y())
        except Exception:
            _log.exception("silent exception in paint_overlay")
            return
        painter.save()
        try:
            self._draw_sample_marker(painter, sp)
        finally:
            painter.restore()

    def clear_marks(self):
        self._hl_items = []
        self._identify_pt = None
        self._repaint()

    def _store_highlight(self, hits):
        self._hl_items = []
        for h in (hits or []):
            if (getattr(h, "geom", None) is not None
                    and getattr(h, "layer", None) is not None):
                self._hl_items.append((h.geom, h.layer))

    def _draw_identify_highlight(self, painter, settings):
        items = self._hl_items
        if not items or self._canvas is None:
            return
        from ..render.painter import _selection_style
        _fill_txt, _line_txt, _fill_alpha, _w_fix = _selection_style()
        _stroke_color = QColor(_line_txt)
        _fill_color = QColor(_fill_txt)
        _stroke_w = max(float(_w_fix or 0.0), 2.0)
        _fill_alpha = max(0.0, min(1.0, float(_fill_alpha or 0.0)))
        painter.save()
        try:
            for (g, layer) in items:
                _sg = g.as_shapely() if hasattr(g, "as_shapely") else g
                if _sg is None:
                    continue
                from ..core.crs import crs_transformer
                _dst = self._canvas.effectiveCrs()
                _src = layer.crs() if layer is not None else None
                _tf = (crs_transformer(_src, _dst)
                       if (_src is not None and _dst is not None) else None)

                def _screen(x, y):
                    if _tf is not None:
                        x, y = _tf.transform(float(x), float(y))
                    return settings.map_to_pixel(float(x), float(y))

                _gt = _sg.geom_type
                _pen = QPen(_stroke_color, _stroke_w)
                _pen.setCosmetic(True)
                painter.setPen(_pen)
                if _gt in ("Polygon", "MultiPolygon", "Point", "MultiPoint"):
                    _bc = QColor(_fill_color)
                    _bc.setAlpha(int(_fill_alpha * 255))
                    painter.setBrush(QBrush(_bc))
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                if _gt in ("Polygon", "MultiPolygon"):
                    for _poly in (_sg.geoms if _gt == "MultiPolygon" else (_sg,)):
                        _pts = [_screen(*c) for c in _poly.exterior.coords]
                        if len(_pts) >= 2:
                            painter.drawPolygon(QPolygonF(_pts))
                elif _gt in ("LineString", "LinearRing", "MultiLineString"):
                    for _line in (_sg.geoms if _gt == "MultiLineString" else (_sg,)):
                        _pts = [_screen(*c) for c in _line.coords]
                        if len(_pts) >= 2:
                            painter.drawPolyline(QPolygonF(_pts))
                elif _gt in ("Point", "MultiPoint"):
                    from ..render.renderers import get_renderer
                    _rs = get_renderer(layer).symbols()
                    _d = max(1.0, float(_rs[0].px_size())) if _rs else 4.0
                    _sw_body = (float(_rs[0].px_width())
                                if _rs else 1.0)
                    _outer = _d + _sw_body
                    _pr = max(0.5, (_outer - _stroke_w) / 2.0)
                    for _pt in (_sg.geoms if _gt == "MultiPoint" else (_sg,)):
                        painter.drawEllipse(_screen(_pt.x, _pt.y), _pr, _pr)
                else:
                    _pts = [_screen(*c) for c in list(_sg.coords)]
                    if len(_pts) >= 2:
                        painter.drawPolyline(QPolygonF(_pts))
        finally:
            painter.restore()




SELECT_SHAPES = ("rect", "polygon", "lasso", "circle", "line")

LASSO_MIN_PX = 2.5
MIN_VERTICES = 3
MIN_LINE_PTS = 2

_SEL_COLOR = "#FFE14D"
_SEL_FILL = (255, 225, 77, 38)


def _band_pen():
    return QPen(QColor(_SEL_COLOR), 1.0, Qt.PenStyle.DashLine)


def _band_brush():
    return QBrush(QColor(*_SEL_FILL))


def _polygon_geometry(pts):
    try:
        from shapely.geometry import Polygon
    except Exception:
        _log.exception("silent exception in _polygon_geometry")
        return None
    try:
        poly = Polygon(pts)
    except Exception:
        _log.exception("silent exception in _polygon_geometry")
        return None
    if getattr(poly, "is_valid", True):
        return poly
    try:
        from shapely.validation import make_valid
        fixed = make_valid(poly)
        return fixed if fixed is not None and not fixed.is_empty else poly
    except Exception:
        _log.exception("silent exception in _polygon_geometry")
        return poly


def _line_geometry(pts):
    try:
        from shapely.geometry import LineString
    except Exception:
        _log.exception("silent exception in _line_geometry")
        return None
    try:
        return LineString(pts)
    except Exception:
        _log.exception("silent exception in _line_geometry")
        return None


def _circle_geometry(cx, cy, r):
    try:
        from shapely.geometry import Point
    except Exception:
        _log.exception("silent exception in _circle_geometry")
        return None
    try:
        return Point(float(cx), float(cy)).buffer(float(r), quad_segs=32)
    except Exception:
        _log.exception("silent exception in _circle_geometry")
        return None


class _PressEventSnapshot:

    __slots__ = ("_pos", "_btn")

    def __init__(self, pos, btn):
        self._pos = QPointF(pos)
        self._btn = btn

    def position(self):
        return QPointF(self._pos)

    def button(self):
        return self._btn


class GgsMapToolSelect(GgsMapTool):

    selectionRequested = Signal(object, object, str)
    bandChanged = Signal()

    def __init__(self, canvas=None, layer_provider=None, parent=None,
                 shape="rect", move_tool=None):
        sh = shape if shape in SELECT_SHAPES else "rect"
        super().__init__(("select_%s" % sh) if sh != "rect" else "select",
                         canvas, Qt.CursorShape.CrossCursor, parent)
        self._layer_provider = layer_provider
        self._shape = sh
        self._press_screen = None
        self._press_map = None
        self._band = QRectF()
        self._circle_edge = None
        self._dragging = False
        self._pts_screen = []
        self._pts_map = []
        self._hover_screen = None
        self._lasso_on = False
        self._move_tool = move_tool
        self._moving = False
        self._pending_move_tool = None
        self._pending_move_event = None
        self._pending_move_map = None
        self.tol_px = _identify_tol_px()

    def shape(self):
        return self._shape

    def setShape(self, shape):
        self._shape = shape if shape in SELECT_SHAPES else "rect"
        self._reset()

    def set_move_tool(self, tool):
        self._move_tool = tool

    def _move_tool_obj(self):
        t = self._move_tool
        if t is not None:
            return t
        try:
            p = self.parent()
            t = (getattr(p, "_tools", None) or {}).get("move_feature")
        except Exception:
            _log.exception("silent exception in _move_tool_obj")
            t = None
        return t

    def _drop_pending_move(self):
        self._pending_move_tool = None
        self._pending_move_event = None
        self._pending_move_map = None

    @staticmethod
    def _shift_held(event):
        try:
            return bool(event.modifiers()
                        & Qt.KeyboardModifier.ShiftModifier)
        except Exception:
            _log.exception("silent exception in _shift_held")
            return False

    def isInteractive(self):
        return True

    def statusHint(self):
        return {
            "polygon": "多边形选择：逐点点击，双击 / 右键 / 回车闭合；"
                       "Esc 取消，Backspace 退一点",
            "lasso": "套索选择：按住左键拖出任意形状，松手完成",
            "circle": "圆形选择：按下定圆心，拖动定半径",
            "line": "折线选择：逐点点击，双击 / 右键 / 回车结束；"
                    "选中与折线相交的要素",
        }.get(self._shape,
              "选择要素：左键点选 / 拖动框选；"
              "Shift 加选，Ctrl 减选，Ctrl+Shift 交集")

    def setLayerProvider(self, fn):
        self._layer_provider = fn

    def _layers(self):
        if self._layer_provider is not None:
            try:
                return [l for l in self._layer_provider() if l is not None]
            except Exception:
                _log.exception("silent exception in _layers")
                return []
        c = self._canvas
        if c is not None:
            try:
                return [l for l in c.project().layers()
                        if l.is_vector() and l.is_visible()]
            except Exception:
                _log.exception("silent exception in _layers")
                return []
        return []

    def band(self):
        return QRectF(self._band)

    def points(self):
        return list(self._pts_screen)

    def mousePress(self, event, map_point):
        b = event.button()
        if b == Qt.MouseButton.RightButton:
            if self._shape in ("polygon", "line") and self._pts_screen:
                self._finish()
                return True
            return False
        if b != Qt.MouseButton.LeftButton:
            return False
        _mt = self._move_tool_obj()
        if _mt is not None and not self._shift_held(event):
            try:
                _mp = map_point if isinstance(map_point, QPointF) \
                    else QPointF(float(map_point[0]), float(map_point[1]))
            except Exception:
                _log.exception("silent exception in mousePress")
                _mp = None
            if _mp is not None:
                self._pending_move_tool = _mt
                self._pending_move_map = _mp
                try:
                    self._pending_move_event = _PressEventSnapshot(
                        event.position(), event.button())
                except Exception:
                    _log.exception("silent exception in mousePress")
                    self._pending_move_event = None
        pos = QPointF(event.position())
        sh = self._shape
        if sh == "rect":
            self._press_screen = pos
            self._press_map = QPointF(map_point)
            self._band = QRectF(pos, pos)
            self._dragging = False
            return True
        if sh == "circle":
            self._press_screen = pos
            self._press_map = QPointF(map_point)
            self._circle_edge = pos
            self._dragging = False
            return True
        if sh == "lasso":
            self._lasso_on = True
            self._pts_screen = [pos]
            self._pts_map = [QPointF(map_point)]
            self.bandChanged.emit()
            self._repaint()
            return True
        self._pts_screen.append(pos)
        self._pts_map.append(QPointF(map_point))
        self._hover_screen = pos
        self.bandChanged.emit()
        self._repaint()
        return True

    def mouseMove(self, event, map_point):
        if self._moving:
            _mt = self._move_tool_obj()
            if _mt is not None:
                try:
                    _mt.mouseMove(event, map_point)
                except Exception:
                    _log.exception("silent exception in mouseMove")
                return True
        if self._pending_move_tool is not None:
            _pm = self._pending_move_tool
            _pe = self._pending_move_event
            _pt = self._pending_move_map
            self._pending_move_tool = None
            self._pending_move_event = None
            self._pending_move_map = None
            try:
                if _pm is not None and _pe is not None:
                    d = QPointF(event.position()) - QPointF(
                        _pe.position())
                    if (abs(d.x()) >= DRAG_PX or abs(d.y()) >= DRAG_PX) \
                            and _pm.press_on_selected(_pe, _pt):
                        self._moving = True
                        _pm.mousePress(_pe, _pt)
                        _pm.mouseMove(event, map_point)
                        return True
            except Exception:
                _log.exception("silent exception in mouseMove")
        pos = QPointF(event.position())
        sh = self._shape
        if sh == "rect":
            if self._press_screen is None:
                return False
            if not self._dragging:
                d = pos - self._press_screen
                if abs(d.x()) < DRAG_PX and abs(d.y()) < DRAG_PX:
                    return True
                self._dragging = True
            self._band = QRectF(self._press_screen, pos).normalized()
            self.bandChanged.emit()
            self._repaint()
            return True
        if sh == "circle":
            if self._press_screen is None:
                return False
            if not self._dragging:
                d = pos - self._press_screen
                if (d.x() ** 2 + d.y() ** 2) ** 0.5 < DRAG_PX:
                    return True
                self._dragging = True
            self._circle_edge = pos
            self.bandChanged.emit()
            self._repaint()
            return True
        if sh == "lasso":
            if not self._lasso_on:
                return False
            last = self._pts_screen[-1] if self._pts_screen else None
            if last is not None:
                d = pos - last
                if (d.x() ** 2 + d.y() ** 2) ** 0.5 < LASSO_MIN_PX:
                    return True
            self._pts_screen.append(pos)
            self._pts_map.append(QPointF(map_point))
            self.bandChanged.emit()
            self._repaint()
            return True
        if sh in ("polygon", "line"):
            if not self._pts_screen:
                return False
            self._hover_screen = pos
            self._repaint()
            return True
        return False

    def mouseRelease(self, event, map_point):
        if self._moving:
            self._moving = False
            _mt = self._move_tool_obj()
            if _mt is not None:
                try:
                    _mt.mouseRelease(event, map_point)
                except Exception:
                    _log.exception("silent exception in mouseRelease")
                return True
        self._drop_pending_move()
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        sh = self._shape
        mode = selection_mode(event.modifiers())
        layers = self._layers()
        if sh == "rect":
            if self._press_screen is None:
                return False
            if self._dragging:
                self._apply_rect(layers, mode)
            else:
                self._apply_point(layers, map_point, mode)
            self._reset()
            return True
        if sh == "circle":
            if self._press_screen is None:
                return False
            if self._dragging:
                self._apply_circle(layers, mode)
            else:
                self._apply_point(layers, map_point, mode)
            self._reset()
            return True
        if sh == "lasso":
            if not self._lasso_on:
                return False
            self._lasso_on = False
            self._apply_polygon(layers, mode)
            self._reset()
            return True
        return False

    def mouseDoubleClick(self, event, map_point):
        if self._shape not in ("polygon", "line"):
            return False
        if len(self._pts_screen) >= 2:
            d = self._pts_screen[-1] - self._pts_screen[-2]
            if abs(d.x()) < 2.0 and abs(d.y()) < 2.0:
                self._pts_screen.pop()
                self._pts_map.pop()
        self._finish()
        return True

    def keyPress(self, event):
        k = event.key()
        if k == Qt.Key.Key_Escape:
            if self._has_state():
                self._reset()
                return True
            return False
        sh = self._shape
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if sh in ("polygon", "line") and self._pts_screen:
                self._finish()
                return True
            return False
        if k == Qt.Key.Key_Backspace:
            if sh in ("polygon", "line") and self._pts_screen:
                self._pts_screen.pop()
                self._pts_map.pop()
                if not self._pts_screen:
                    self._hover_screen = None
                self.bandChanged.emit()
                self._repaint()
                return True
            return False
        return False

    def _has_state(self):
        return bool(self._pts_screen) or self._press_screen is not None \
            or self._lasso_on

    def _reset(self):
        self._press_screen = None
        self._press_map = None
        self._dragging = False
        self._band = QRectF()
        self._circle_edge = None
        self._pts_screen = []
        self._pts_map = []
        self._hover_screen = None
        self._lasso_on = False
        self._moving = False
        self._drop_pending_move()
        self.bandChanged.emit()
        self._repaint()

    def _finish(self):
        sh = self._shape
        layers = self._layers()
        try:
            mods = QGuiApplication.keyboardModifiers()
        except Exception:
            _log.exception("silent exception in _finish")
            mods = Qt.KeyboardModifier.NoModifier
        mode = selection_mode(mods)
        if sh == "polygon":
            self._apply_polygon(layers, mode)
        elif sh == "line":
            self._apply_line(layers, mode)
        self._reset()


    def _apply_point(self, layers, map_point, mode):
        tol = identify_tolerance(self._canvas, self.tol_px)
        for lyr in layers:
            x, y = to_layer_point(lyr, map_point.x(), map_point.y(),
                                  self._canvas)
            t = to_layer_tolerance(lyr, tol, self._canvas)
            try:
                fids = hit_fids(lyr, x, y, t)
            except Exception:
                _log.exception("silent exception in _apply_point")
                fids = []
            self.selectionRequested.emit(lyr, fids, mode)

    def _apply_rect(self, layers, mode):
        r = self._band
        if r.isNull() or r.width() <= 0 or r.height() <= 0:
            return
        c = self._canvas
        if c is None:
            return
        try:
            p1 = c.to_map_coords(r.topLeft())
            p2 = c.to_map_coords(r.bottomRight())
        except Exception:
            _log.exception("silent exception in _apply_rect")
            return
        xmin, xmax = sorted((p1[0], p2[0]))
        ymin, ymax = sorted((p1[1], p2[1]))
        for lyr in layers:
            q = to_layer_rect(lyr, (xmin, ymin, xmax, ymax), c)
            try:
                fids = features_in_rect(lyr, q)
            except Exception:
                _log.exception("silent exception in _apply_rect")
                fids = []
            if len(fids) > SELECT_MAX:
                fids = fids[:SELECT_MAX]
            self.selectionRequested.emit(lyr, fids, mode)

    def _apply_circle(self, layers, mode):
        c = self._canvas
        if c is None or self._press_screen is None \
                or self._circle_edge is None:
            return
        try:
            cx, cy = c.to_map_coords(self._press_screen)
            ex, ey = c.to_map_coords(self._circle_edge)
        except Exception:
            _log.exception("silent exception in _apply_circle")
            return
        r = ((ex - cx) ** 2 + (ey - cy) ** 2) ** 0.5
        if not (r > 0):
            return
        self._emit_geometry(layers, mode, _circle_geometry(cx, cy, r))

    def _apply_polygon(self, layers, mode):
        pts = [(p.x(), p.y()) for p in self._pts_map]
        if len(pts) < MIN_VERTICES:
            return
        self._emit_geometry(layers, mode, _polygon_geometry(pts))

    def _apply_line(self, layers, mode):
        pts = [(p.x(), p.y()) for p in self._pts_map]
        if len(pts) < MIN_LINE_PTS:
            return
        self._emit_geometry(layers, mode, _line_geometry(pts), kind="line")

    def _emit_geometry(self, layers, mode, geom, kind="area"):
        if geom is None:
            return
        c = self._canvas
        for lyr in layers:
            g = to_layer_geometry(lyr, geom, c)
            try:
                fids = features_intersecting(lyr, g)
            except Exception:
                _log.exception("silent exception in _emit_geometry")
                fids = []
            if len(fids) > SELECT_MAX:
                fids = fids[:SELECT_MAX]
            self.selectionRequested.emit(lyr, fids, mode)

    def paint_overlay(self, painter, settings):
        if self._moving:
            _mt = self._move_tool_obj()
            _fn = getattr(_mt, "paint_overlay", None) if _mt is not None else None
            if _fn is not None:
                try:
                    _fn(painter, settings)
                except Exception:
                    _log.exception("silent exception in paint_overlay")
            return
        painter.save()
        try:
            if self._shape in ("rect", "circle"):
                self._paint_ring(painter)
            else:
                self._paint_path(painter)
        finally:
            painter.restore()

    def _paint_ring(self, painter):
        painter.setPen(_band_pen())
        painter.setBrush(_band_brush())
        if self._shape == "rect":
            r = self._band
            if r.isNull() or r.width() <= 0 or r.height() <= 0:
                return
            painter.drawRect(r)
            return
        c, e = self._press_screen, self._circle_edge
        if c is None or e is None:
            return
        d = e - c
        rad = (d.x() ** 2 + d.y() ** 2) ** 0.5
        if rad <= 0.5:
            return
        painter.drawEllipse(c, rad, rad)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(_SEL_COLOR), 1.0))
        painter.drawLine(c, e)

    def _paint_path(self, painter):
        pts = list(self._pts_screen)
        if not pts:
            return
        sh = self._shape
        closed = sh in ("polygon", "lasso")
        seq = list(pts)
        if sh in ("polygon", "line") and self._hover_screen is not None:
            seq.append(self._hover_screen)
        if len(seq) >= 2:
            if closed and len(seq) >= 3:
                poly = QPolygonF([QPointF(p.x(), p.y()) for p in seq])
                painter.setBrush(_band_brush())
                painter.setPen(_band_pen())
                painter.drawPolygon(poly)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(_band_pen())
                for i in range(len(seq) - 1):
                    painter.drawLine(seq[i], seq[i + 1])
        if sh == "lasso":
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(_SEL_COLOR)))
        for p in pts:
            painter.drawRect(QRectF(p.x() - 2.5, p.y() - 2.5, 5.0, 5.0))
