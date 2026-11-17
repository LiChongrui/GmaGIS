# -*- coding: utf-8 -*-

from ._canvas_cfg import (
    _BOX_ZOOM,
    _CAUSE_JUMP,
    _CAUSE_PAN,
    _CAUSE_RESIZE,
    _CAUSE_ZOOM,
    _HOVER_GRAB_CURSOR,
    _INTERACTIVE_CAUSES,
    _MIN_BOX_PX,
    _PHASE_INTERACTING,
    _PHASE_SETTLING,
    _RESIZE_KEEP_FRAME,
    _WHEEL_PAN_X,
    _ZOOM_LIMITS,
    _ZOOM_OUT_MAX_FACTOR,
    _ZOOM_RIGHT_DBLCLICK,
    _ZOOM_STEP,
)

from ..core.crs import (GgsCrs, convert_bounds,
                        crs_transformer, needs_reproject)
from ggis.core.crs.extent import GgsRectangle
from PySide6.QtGui import QColor, QImage, QPainter

from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from .cpu import interaction as _IZ
from ggis.core.app.i18n import tr as _tr
from ggis.common.util.exc_report import exc_note
from ggis.core.app import settings
import time


class CanvasStateMixin:


    def set_forced_dpr(self, dpr):
        try:
            self._forced_dpr = max(0.0, float(dpr or 0.0))
        except Exception:
            exc_note("set_forced_dpr @ ggis/render/map_canvas.py")
            self._forced_dpr = 0.0

    def _eff_dpr(self):
        f = getattr(self, "_forced_dpr", 0.0)
        if f > 0.0:
            return float(f)
        try:
            return float(self.devicePixelRatioF()) or 1.0
        except Exception:
            exc_note("_eff_dpr @ ggis/render/map_canvas.py")
            return 1.0

    def project(self):
        return self._project

    def setCanvasColor(self, color):
        try:
            self._color = QColor(color)
            self.update()
        except Exception:
            exc_note("setCanvasColor @ ggis/render/map_canvas.py:822")
            pass

    def canvasColor(self):
        return QColor(self._color)

    def _fit_canvas_ratio(self, rect):
        try:
            r = rect.copy() if isinstance(rect, GgsRectangle) \
                else GgsRectangle(*rect)
            if r.is_empty():
                return None
            r.ensure_minimum(force=True)
            ratio = max(1, self.width()) / float(max(1, self.height()))
            r.expand_to_ratio(ratio)
            return r
        except Exception:
            exc_note("_fit_canvas_ratio @ ggis/render/map_canvas.py:855")
            return None

    def setDestinationCrs(self, crs):
        old = self._extent_crs
        try:
            obj = crs if isinstance(crs, GgsCrs) else \
                GgsCrs.from_user_input(crs)
        except Exception:
            exc_note("setDestinationCrs @ ggis/render/map_canvas.py:879")
            return
        if obj is not None and not obj.is_valid():
            return
        try:
            if (old is not None and obj is not None
                    and not self._extent.is_empty()
                    and needs_reproject(old, obj)):
                b = convert_bounds((self._extent.xmin, self._extent.ymin,
                                    self._extent.xmax, self._extent.ymax),
                                   crs_transformer(old, obj))
                if b is not None:
                    _r = self._fit_canvas_ratio(
                        GgsRectangle(b[0], b[1], b[2], b[3]))
                    if _r is not None:
                        self._extent = _r
                        self._extent_crs = obj
        except Exception:
            exc_note("setDestinationCrs @ ggis/render/map_canvas.py:905")
            pass
        try:
            self._crs = obj.authid() if (obj is not None and obj.is_valid()) else ""
            self._crs_obj = obj
            self._crs_explicit = True
            if obj is not None and obj.is_valid():
                self._extent_crs = obj
            self.crsChanged.emit()
        except Exception:
            exc_note("setDestinationCrs @ ggis/render/map_canvas.py:929")
            return
        try:
            self._arm_render(immediate=True)
        except Exception:
            exc_note("setDestinationCrs @ ggis/render/map_canvas.py:939")
            self.update()
        try:
            self._prune_unrenderable_tiles()
        except Exception:
            exc_note("setDestinationCrs @ ggis/render/map_canvas.py:944")
            pass

    def _notify(self, text, level="Warning"):
        host = None
        p = self.parent()
        while p is not None:
            if hasattr(p, "_host"):
                h = getattr(p, "_host", None)
                if h is not None:
                    host = h
                    break
            p = p.parent()
        if host is not None and hasattr(host, "show_message"):
            try:
                host.show_message(text, level)
                return
            except Exception:
                exc_note("_notify @ ggis/render/map_canvas.py:989")
                pass
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.warn(self, _tr("提示"), text)
        except Exception:
            exc_note("_notify @ ggis/render/map_canvas.py:995")
            pass

    def adopt_project_crs(self):
        try:
            c = settings.default_crs()
        except Exception:
            exc_note("adopt_project_crs @ ggis/render/map_canvas.py:1057")
            return
        try:
            if c is not None and c.is_valid():
                self._crs_obj = c
                self._crs = c.authid()
                self._crs_explicit = True
        except Exception:
            exc_note("adopt_project_crs @ ggis/render/map_canvas.py:1066")
            return
        try:
            self._on_crs_changed()
        except Exception:
            exc_note("adopt_project_crs @ ggis/render/map_canvas.py:1071")
            pass

    def hasExplicitCrs(self):
        return bool(getattr(self, "_crs_explicit", False))

    def destinationCrs(self):
        c = self.effectiveCrs()
        if c is not None and c.is_valid():
            return c.authid()
        return ""

    def effectiveCrs(self):
        try:
            own = getattr(self, "_crs_obj", None)
            if own is not None and own.is_valid():
                return own
        except Exception:
            exc_note("effectiveCrs @ ggis/render/map_canvas.py:1129")
            pass
        try:
            layers = list(self._layer_source())
        except Exception:
            exc_note("effectiveCrs @ ggis/render/map_canvas.py:1134")
            layers = []
        fallback = None
        for lyr in layers:
            try:
                if lyr.is_tile():
                    if fallback is None:
                        fallback = lyr.crs()
                    continue
                lc = lyr.crs()
                if lc is not None and lc.is_valid():
                    return lc
            except Exception:
                exc_note("effectiveCrs @ ggis/render/map_canvas.py:1146")
                continue
        try:
            if fallback is not None and fallback.is_valid():
                return fallback
        except Exception:
            exc_note("effectiveCrs @ ggis/render/map_canvas.py:1151")
            pass
        return None

    def enableAntiAliasing(self, on):
        self._anti_alias = bool(on)
        self.update()

    def antiAliasingEnabled(self):
        return bool(self._anti_alias)

    def setParallelRenderingEnabled(self, on):
        return None

    def setFrameShape(self, shape):
        self._frame_shape = shape

    def frameShape(self):
        return getattr(self, "_frame_shape", 0)

    def setWheelFactor(self, f):
        try:
            self._zoom_step = float(f)
        except Exception:
            exc_note("setWheelFactor @ ggis/render/map_canvas.py:1174")
            pass

    def extent(self):
        return self._extent.copy()

    def _sync_view_state(self, cause):
        self._cause = cause
        self._phase = (_PHASE_INTERACTING
                       if cause in _INTERACTIVE_CAUSES
                       else _PHASE_SETTLING)
        self._dirty = True
        if cause in _INTERACTIVE_CAUSES:
            self._interacting = True

    def setExtent(self, rect, emit=True, cause=None):
        return self.set_view(rect, cause or _CAUSE_JUMP, emit=emit)

    def set_view(self, rect, cause, emit=True, schedule=True):
        try:
            r = rect.copy() if isinstance(rect, GgsRectangle) \
                else GgsRectangle(*rect)
        except Exception:
            exc_note("set_view @ ggis/render/map_canvas.py")
            return False
        if r.is_empty():
            return False
        r.ensure_minimum(force=True)
        w, h = max(1, self.width()), max(1, self.height())
        r.expand_to_ratio(w / h)
        self._extent = r
        try:
            self._extent_crs = self.effectiveCrs()
        except Exception:
            exc_note("set_view @ ggis/render/map_canvas.py")
            self._extent_crs = None
        self._sync_view_state(cause)
        if schedule:
            self._arm_render()
        self.update()
        if emit:
            self._emit_scale()
        return True

    def fullExtent(self):
        return self._project.full_extent(dst_crs=self.effectiveCrs())

    def zoomToFullExtent(self):
        if self.isScaleLocked():
            return
        ext = self._project.full_extent(dst_crs=self.effectiveCrs(),
                                        include_tiles=True)
        if ext.is_empty():
            self.update()
            return
        self._hold_partial_begin()
        self.setExtent(ext, cause=_CAUSE_JUMP)

    def zoomToSelected(self, layer=None):
        if layer is None:
            self.zoomToFullExtent()
        else:
            self.zoomToLayer(layer)

    def zoomToLayer(self, layer):
        if layer is not None and layer.is_table():
            return
        if self.isScaleLocked():
            return
        try:
            ext = self._project.layer_extent(layer,
                                             dst_crs=self.effectiveCrs())
        except Exception:
            exc_note("zoomToLayer @ ggis/render/map_canvas.py:1286")
            ext = GgsRectangle()
        if ext.is_empty():
            return
        self._hold_partial_begin()
        self.setExtent(ext, cause=_CAUSE_JUMP)

    def setScaleLocked(self, on):
        self._scale_locked = bool(on)

    def isScaleLocked(self):
        return bool(getattr(self, "_scale_locked", False))

    def zoomToExtent(self, rect, margin=1.0):
        if self.isScaleLocked():
            return False
        if rect is None or rect.is_empty():
            return False
        try:
            r = rect.copy().scale(float(margin)) if margin \
                and float(margin) != 1.0 else rect.copy()
        except Exception:
            exc_note("zoomToExtent @ ggis/render/map_canvas.py:1337")
            r = rect
        self.setExtent(r, cause=_CAUSE_JUMP)
        return True

    def zoomIn(self, anchor=None):
        self._zoom_by(1.0 / _ZOOM_STEP, anchor)

    def zoomOut(self, anchor=None):
        self._zoom_by(_ZOOM_STEP, anchor)

    def _one_to_one_width(self):
        try:
            n = self.scale()
        except Exception:
            exc_note("_one_to_one_width @ ggis/render/map_canvas.py:1362")
            n = 0.0
        if not n or n <= 0:
            return 0.0
        w = float(self._extent.width())
        if w <= 0:
            return 0.0
        return w / n

    def _zoom_limit_widths(self):
        if not _ZOOM_LIMITS:
            return None
        try:
            full = self._project.full_extent(dst_crs=self.effectiveCrs())
        except Exception:
            exc_note("_zoom_limit_widths @ ggis/render/map_canvas.py:1389")
            return None
        if full is None or full.is_empty():
            return None
        w = float(full.width())
        if w <= 0:
            return None
        lo = self._one_to_one_width()
        hi_w = w
        try:
            dst = self.effectiveCrs()
            hi_rect = full.copy()
            for lyr in self._layer_source():
                try:
                    if not lyr.is_tile() or not lyr.is_visible():
                        continue
                    te = lyr.extent()
                except Exception:
                    exc_note("_zoom_limit_widths @ ggis/render/map_canvas.py:1408")
                    continue
                if te is None or te.is_empty():
                    continue
                try:
                    if lyr.crs() is not None and dst is not None \
                            and lyr.crs().authid() == dst.authid():
                        r = GgsRectangle(te.xmin, te.ymin, te.xmax, te.ymax)
                    else:
                        tf = crs_transformer(lyr.crs(), dst)
                        b = convert_bounds((te.xmin, te.ymin,
                                            te.xmax, te.ymax), tf) \
                            if tf is not None else None
                        r = GgsRectangle(b[0], b[1], b[2], b[3]) \
                            if b is not None else GgsRectangle()
                except Exception:
                    exc_note("_zoom_limit_widths @ ggis/render/map_canvas.py:1426")
                    r = GgsRectangle()
                if not r.is_empty():
                    hi_rect.combine_extent_with(r)
            hw = float(hi_rect.width())
            if hw > 0:
                hi_w = max(w, hw)
        except Exception:
            exc_note("_zoom_limit_widths @ ggis/render/map_canvas.py:1433")
            pass
        hi = max(w * _ZOOM_OUT_MAX_FACTOR, hi_w * 1.2)
        return (lo, hi)

    def _clamp_zoom(self, r, ax=None, ay=None):
        lim = self._zoom_limit_widths()
        if lim is None:
            return True
        lo, hi = lim
        try:
            cur = float(r.width())
            old = float(self._extent.width())
        except Exception:
            exc_note("_clamp_zoom @ ggis/render/map_canvas.py:1455")
            return True
        if cur <= 0 or (lo <= cur <= hi):
            return True
        at_edge = ((cur < lo and old <= lo * 1.0001)
                   or (cur > hi and old >= hi * 0.9999))
        if at_edge:
            return False
        k = (lo / cur) if cur < lo else (hi / cur)
        try:
            if ax is not None and ay is not None:
                r.scale(k, center=(ax, ay))
            else:
                r.scale(k)
        except Exception:
            exc_note("_clamp_zoom @ ggis/render/map_canvas.py:1469")
            return True
        return True

    def _pan_by_wheel(self, e, dx):
        try:
            ext = self._extent.copy()
        except Exception:
            exc_note("_pan_by_wheel @ ggis/render/map_canvas.py:1482")
            return
        s = self._map_settings()
        if ext.is_empty() or not s.is_ready():
            return
        px = 0.0
        try:
            pd = e.pixelDelta()
            if pd.x():
                px = float(pd.x())
        except Exception:
            exc_note("_pan_by_wheel @ ggis/render/map_canvas.py:1493")
            px = 0.0
        if not px:
            px = float(dx) / 8.0
        try:
            mx = px / s.scale_x()
        except Exception:
            exc_note("_pan_by_wheel @ ggis/render/map_canvas.py:1499")
            return
        ext.xmin -= mx
        ext.xmax -= mx
        try:
            self._last_wheel_t = time.monotonic()
        except Exception:
            exc_note("_pan_by_wheel @ ggis/render/map_canvas.py")
        self._interacting = True
        self.setExtent(ext, cause=_CAUSE_PAN)
        if _IZ.is_scroll_end(e):
            self._arm_render(immediate=True)
        try:
            e.accept()
        except Exception:
            exc_note("_pan_by_wheel @ ggis/render/map_canvas.py:1517")
            pass

    def _paint_box_zoom(self):
        if not self._box_zoom_on or self._box_p0 is None \
                or self._box_p1 is None:
            return
        try:
            from PySide6.QtGui import QBrush, QPen
            r = QRectF(QPointF(self._box_p0), QPointF(self._box_p1)).normalized()
            if r.width() < 2 or r.height() < 2:
                return
            p = QPainter(self)
            try:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                p.setPen(QPen(QColor(40, 120, 220), 1,
                              Qt.PenStyle.DashLine))
                p.setBrush(QBrush(QColor(40, 120, 220, 40)))
                p.drawRect(r)
            finally:
                p.end()
        except Exception:
            exc_note("_paint_box_zoom @ ggis/render/map_canvas.py:1685")
            pass

    def _zoom_by(self, factor, anchor=None):
        if self._extent.is_empty():
            return
        if self.isScaleLocked():
            return
        r = self._extent.copy()
        ax = ay = None
        if anchor is not None:
            s = self._map_settings()
            ax, ay = s.pixel_to_map(anchor.x(), anchor.y())
            r.scale(factor, center=(ax, ay))
        else:
            r.scale(factor)
        if not self._clamp_zoom(r, ax, ay):
            return
        self._interacting = True
        self._hold_partial_begin()
        self.setExtent(r, cause=_CAUSE_ZOOM)

    def zoomScale(self, scale):
        cur = self.scale()
        if cur <= 0 or scale <= 0:
            return
        self._zoom_by(scale / cur)

    def scale(self):
        s = self._map_settings()
        return s.scale(self.effectiveCrs())

    def mapUnitsPerPixel(self):
        return self._map_settings().map_units_per_pixel()

    def hideEvent(self, e):
        try:
            if self._render_poll is not None:
                self._render_poll.stop()
            if getattr(self, "_render_busy", False):
                self._render_busy = False
                self._render_text = ""
                self.renderComplete.emit()
                self.renderStatus.emit("")
        except Exception:
            exc_note("hideEvent @ ggis/render/map_canvas.py:2009")
            pass
        super().hideEvent(e)

    def to_map_coords(self, pos):
        return self._map_settings().pixel_to_map(pos.x(), pos.y())

    def to_canvas_coords(self, x, y):
        return self._map_settings().map_to_pixel(x, y)

    def _is_dark_bg(self):
        try:
            c = self._color
            return (c.red() * 299 + c.green() * 587 + c.blue() * 114) \
                < 128000
        except Exception:
            exc_note("_is_dark_bg @ ggis/render/map_canvas.py:2176")
            return True

    def refresh_canvas_color(self):
        self._refresh_scene(keep_frame=False)


    @staticmethod
    def _in_scale(lyr, settings):
        try:
            d = float(settings.scale())
        except Exception:
            exc_note("_in_scale @ ggis/render/map_canvas.py:5134")
            return True
        try:
            return bool(lyr.is_in_scale_range(d))
        except Exception:
            exc_note("_in_scale @ ggis/render/map_canvas.py:5138")
            return True

    def wheelEvent(self, e):
        try:
            delta = e.angleDelta().y()
            dx = e.angleDelta().x()
        except Exception:
            exc_note("wheelEvent @ ggis/render/map_canvas.py:5873")
            return
        if self._extent.is_empty():
            return
        if _WHEEL_PAN_X and dx and abs(dx) > abs(delta):
            self._pan_by_wheel(e, dx)
            return
        if delta == 0:
            return
        ctrl = False
        try:
            ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)
        except Exception:
            exc_note("wheelEvent @ ggis/render/map_canvas.py:5896")
            ctrl = False
        factor = _IZ.signed_wheel_factor(delta, _ZOOM_STEP, ctrl=ctrl)
        try:
            self._last_wheel_t = time.monotonic()
        except Exception:
            exc_note("wheelEvent @ ggis/render/map_canvas.py")
        self._zoom_by(factor, QPointF(e.position()))
        if _IZ.is_scroll_end(e):
            self._arm_render(immediate=True)
        e.accept()

    def mousePressEvent(self, e):
        if self._tool_consumes():
            try:
                if self._tool.mousePress(e, self._map_point(e)):
                    e.accept()
                    return
            except Exception:
                exc_note("mousePressEvent @ ggis/render/map_canvas.py:5928")
                pass
        if _BOX_ZOOM and e.button() == Qt.MouseButton.LeftButton:
            try:
                shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            except Exception:
                exc_note("mousePressEvent @ ggis/render/map_canvas.py:5934")
                shift = False
            if shift:
                self._box_zoom_on = True
                self._box_p0 = e.position()
                self._box_p1 = e.position()
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.update()
                e.accept()
                return
        if e.button() in (Qt.MouseButton.LeftButton,
                          Qt.MouseButton.MiddleButton):
            self._panning = True
            self._interacting = True
            self._last_pos = e.position().toPoint()
            self._press_pos = self._last_pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._tool_consumes():
            try:
                if self._tool.mouseMove(e, self._map_point(e)):
                    self._emit_xy(e)
                    e.accept()
                    return
            except Exception:
                exc_note("mouseMoveEvent @ ggis/render/map_canvas.py:5982")
                pass
        if self._box_zoom_on:
            self._box_p1 = e.position()
            self.update()
            e.accept()
            return
        if self._panning:
            dx = pos.x() - self._last_pos.x()
            dy = pos.y() - self._last_pos.y()
            self._last_pos = pos
            ext = self._extent.copy()
            s = self._map_settings()
            if not ext.is_empty() and s.is_ready():
                mx = dx / s.scale_x()
                my = dy / s.scale_y()
                ext.xmin -= mx
                ext.xmax -= mx
                ext.ymin += my
                ext.ymax += my
                self._extent = ext
                self._cause = _CAUSE_PAN
                self._phase = _PHASE_INTERACTING
                self.update()
            e.accept()
            return
        self._emit_xy(e)
        if _HOVER_GRAB_CURSOR and self._tool is None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(e)

    def _emit_xy(self, e):
        try:
            x, y = self.to_map_coords(QPointF(e.position()))
            self.xyCoordinates.emit(QPointF(x, y))
        except Exception:
            exc_note("_emit_xy @ ggis/render/map_canvas.py:6048")
            pass

    def mouseReleaseEvent(self, e):
        if self._tool_consumes():
            try:
                if self._tool.mouseRelease(e, self._map_point(e)):
                    e.accept()
                    return
            except Exception:
                exc_note("mouseReleaseEvent @ ggis/render/map_canvas.py:6057")
                pass
        if self._box_zoom_on:
            self._box_zoom_on = False
            p0, p1 = self._box_p0, self._box_p1
            self._box_p0 = self._box_p1 = None
            if _HOVER_GRAB_CURSOR:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.unsetCursor()
            self.update()
            try:
                if p0 is not None and p1 is not None:
                    r = QRectF(QPointF(p0), QPointF(p1)).normalized()
                    if (r.width() >= _MIN_BOX_PX
                            and r.height() >= _MIN_BOX_PX):
                        s = self._map_settings()
                        x0, y0 = s.pixel_to_map(r.left(), r.top())
                        x1, y1 = s.pixel_to_map(r.right(), r.bottom())
                        self.setExtent((min(x0, x1), min(y0, y1),
                                        max(x0, x1), max(y0, y1)),
                                       cause=_CAUSE_ZOOM)
                        self._emit_scale()
            except Exception:
                exc_note("mouseReleaseEvent @ ggis/render/map_canvas.py:6080")
                import traceback
                traceback.print_exc()
            e.accept()
            return
        if self._panning:
            self._panning = False
            if _HOVER_GRAB_CURSOR:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.unsetCursor()
            self._freeze_scrolled()
            self.update()
            self._emit_scale()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self._tool_consumes():
            try:
                if self._tool.mouseDoubleClick(e, self._map_point(e)):
                    e.accept()
                    return
            except Exception:
                exc_note("mouseDoubleClickEvent @ ggis/render/map_canvas.py:6107")
                pass
        if e.button() == Qt.MouseButton.LeftButton:
            self._zoom_by(1.0 / _ZOOM_STEP, QPointF(e.position()))
            e.accept()
            return
        if _ZOOM_RIGHT_DBLCLICK and e.button() == Qt.MouseButton.RightButton:
            self._zoom_by(_ZOOM_STEP, QPointF(e.position()))
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        if self._tool_consumes():
            try:
                if self._tool.keyPress(e):
                    e.accept()
                    return
            except Exception:
                exc_note("keyPressEvent @ ggis/render/map_canvas.py:6126")
                pass
        super().keyPressEvent(e)

    def _is_dock_squeeze(self):
        if self._prev_mainw_size is None:
            return False
        mw = self.window()
        if mw is None:
            return False
        return mw.size() == self._prev_mainw_size

    def _extent_keep_scale(self):
        if self._prev_canvas_w <= 0 or self._prev_canvas_h <= 0:
            return self._extent.copy()
        s = self._extent.width() / self._prev_canvas_w
        nw = max(1.0, self.width() * s)
        nh = max(1.0, self.height() * s)
        dx = dy = 0.0
        if self._prev_canvas_x is not None and self._prev_canvas_y is not None:
            dx = float(self.x()) - float(self._prev_canvas_x)
            dy = float(self.y()) - float(self._prev_canvas_y)
        x0 = self._extent.xmin + dx * s
        y1 = self._extent.ymax - dy * s
        return GgsRectangle(x0, y1 - nh, x0 + nw, y1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._panning or not _RESIZE_KEEP_FRAME or self._extent.is_empty():
            self._clear_frozen()
        if not self._extent.is_empty():
            if _RESIZE_KEEP_FRAME and not self._panning:
                self._interacting = True
                self._hold_partial_begin()
            if self._is_dock_squeeze():
                self.set_view(self._extent_keep_scale(), _CAUSE_RESIZE,
                              schedule=False)
            else:
                self.setExtent(self._extent, cause=_CAUSE_RESIZE)
        else:
            self.update()
        self._prev_canvas_w = self.width()
        self._prev_canvas_h = self.height()
        self._prev_canvas_x = self.x()
        self._prev_canvas_y = self.y()
        mw = self.window()
        self._prev_mainw_size = mw.size() if mw is not None else None

    def _emit_scale(self):
        try:
            self.scaleChanged.emit(float(self.scale()))
        except Exception:
            exc_note("_emit_scale @ ggis/render/map_canvas.py:6192")
            pass
        try:
            self.extentChanged.emit()
        except Exception:
            exc_note("_emit_scale @ ggis/render/map_canvas.py:6196")
            pass

    def _sync_extent_to_crs(self):
        from ..core.crs import crs_key
        try:
            old_obj = self._crs_obj
            now_obj = self.effectiveCrs()
            old = self._crs
            now = crs_key(now_obj)
            if (old_obj is None or now_obj is None or not old
                    or not now or old == now):
                self._crs_obj = now_obj
                self._crs = now or ""
                return False
            if self._extent.is_empty():
                self._crs_obj = now_obj
                self._crs = now
                return False
            from ..core.crs import convert_bounds, crs_transformer
            b = convert_bounds((self._extent.xmin, self._extent.ymin,
                                self._extent.xmax, self._extent.ymax),
                               crs_transformer(old_obj, now_obj))
            if b is None:
                return False
            _r = self._fit_canvas_ratio(GgsRectangle(b[0], b[1], b[2], b[3]))
            self._extent = _r if _r is not None else \
                GgsRectangle(b[0], b[1], b[2], b[3])
            self._crs_obj = now_obj
            self._crs = now
            return True
        except Exception:
            exc_note("_sync_extent_to_crs @ ggis/render/map_canvas.py:6370")
            return False

    def _on_crs_changed(self):
        self._sync_extent_to_crs()
        self._sel_img = None
        self._sel_key = None
        self._refresh_scene(keep_frame=False)
        self._emit_scale()

    def _tool_consumes(self):
        t = self._tool
        if t is None:
            return False
        fn = getattr(t, "isInteractive", None)
        if fn is None:
            return False
        try:
            return bool(fn())
        except Exception:
            exc_note("_tool_consumes @ ggis/render/map_canvas.py:6502")
            return False

    def _map_point(self, e):
        try:
            x, y = self.to_map_coords(QPointF(e.position()))
            return QPointF(x, y)
        except Exception:
            exc_note("_map_point @ ggis/render/map_canvas.py:6509")
            return QPointF(0.0, 0.0)

    def setMapTool(self, tool):
        if isinstance(tool, str) or tool is None:
            old = self._tool
            self._tool = None
            self._tool_name = tool or ""
            self._deactivate(old)
            self.unsetCursor()
            self.update()
            try:
                self.mapToolSet.emit(tool)
            except Exception:
                exc_note("setMapTool @ ggis/render/map_canvas.py:6527")
                pass
            return
        old = self._tool
        if old is tool:
            return
        self._deactivate(old)
        self._tool = tool
        self._tool_name = getattr(tool, "name", lambda: "")()
        try:
            tool.setCanvas(self)
            tool.activate()
        except Exception:
            exc_note("setMapTool @ ggis/render/map_canvas.py:6539")
            pass
        self.update()
        try:
            self.mapToolSet.emit(tool)
        except Exception:
            exc_note("setMapTool @ ggis/render/map_canvas.py:6544")
            pass

    @staticmethod
    def _deactivate(tool):
        if tool is None:
            return
        try:
            tool.deactivate()
        except Exception:
            exc_note("_deactivate @ ggis/render/map_canvas.py:6553")
            pass

    def mapTool(self):
        return self._tool

    def mapToolName(self):
        return getattr(self, "_tool_name", "")

    def unsetMapTool(self, tool=None):
        if tool is not None and tool is not self._tool:
            return
        self.setMapTool(None)

    def viewport(self):
        return self

    def sizeHint(self):
        return QSize(640, 480)
