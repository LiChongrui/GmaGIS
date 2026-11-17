# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import math
import time

from PySide6.QtCore import (QPoint, QPointF, QRectF, Qt, QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetricsF,
                           QImage, QPainter, QPainterPath,
                           QPainterPathStroker, QPen, QPixmap,
                           QPolygonF, QTextCursor, QTransform)
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPathItem,
                               QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsView, QTextEdit,
                               QWidget)

from ggis.ui.views.layout import exporter as EX
from ggis.ui.views.layout.backdrop import BackdropRenderer
from ggis.core.model.layout_model import LayoutItem
from ggis.ui.views.layout.mapframe_nav import MapFrameNav
from ggis.core.app import i18n
from PySide6.QtWidgets import QMenu

_tr = i18n.tr

_log = logging.getLogger("gmagis")

__all__ = ["LayoutScene", "LayoutView", "ItemFrame", "HANDLE_PX",
           "SNAP_MM"]

HANDLE_PX = 7.0
SNAP_MM = 0.5
MIN_MM = 3.0
LABEL_PX = 11.0

SEL_PATH_MODES = ("poly", "lasso", "circle", "line")
LASSO_STEP_MM = 1.2
SEL_PREVIEW_COLOR = "#2E7BE0"

HANDLE_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,
    "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor,
    "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor,
    "w": Qt.CursorShape.SizeHorCursor,
}

BACKDROP_STEPS = ((1.0, 1400), (1.8, 2000), (3.0, 2800), (1e9, 3600))

BACKDROP_FAST_PX = 900
SNAP_MAX_PX = 900
ELEM_OVL_MAX_PX = 3072
ELEM_OVL_MAX_MS = 200
ELEM_PATCH_MAX_MS = 250

DRAG_OVL_WAIT_MS = 40.0

DRAG_RERENDER_MS = 50.0


def _fallback_white(erase):
    try:
        erase.setBrush(QBrush(QColor("#FFFFFF")))
    except Exception:
        exc_note("_fallback_white @ ggis/ui/views/layout/canvas.py:145")
        pass
BACKDROP_SETTLE_MS = 500
RULER_PX = 20
GUIDE_GRAB_PX = 6.0
GUIDE_SNAP_PX = 7.0
MAP_NAV_MS = 1200
MAP_NAV_KICK_MS = 60
MAP_NAV_SETTLE_MS = 250
MAP_NAV_SETTLE_TRIES = 6


class _InlineTextEdit(QTextEdit):

    def __init__(self, parent=None, on_done=None, on_cancel=None):
        super().__init__(parent)
        self._on_done = on_done
        self._on_cancel = on_cancel
        self.setObjectName("GgsLayoutInlineEdit")
        self.setFrameShape(QTextEdit.Shape.NoFrame)
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            if self._on_cancel is not None:
                self._on_cancel()
            e.accept()
            return
        if (k in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and (e.modifiers() & Qt.KeyboardModifier.ControlModifier)):
            if self._on_done is not None:
                self._on_done(self.toPlainText())
            e.accept()
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if self._on_done is not None:
            self._on_done(self.toPlainText())


class _GuideItem(QGraphicsItem):

    def __init__(self, horizontal, pos_mm, scene=None, span_mm=(0.0, 100.0)):
        super().__init__()
        self.horizontal = bool(horizontal)
        self._scene = scene
        self._span = (float(span_mm[0]), float(span_mm[1]))
        self._dragging = False
        self._hot = False
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setAcceptHoverEvents(False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setZValue(5000)
        self.setToolTip("")
        self.set_pos_mm(pos_mm, notify=False)

    def set_pos_mm(self, pos_mm, notify=True):
        g = SNAP_MM if SNAP_MM > 0 else 1.0
        v = round(float(pos_mm) / g) * g
        if self.horizontal:
            self.setPos(0.0, v)
        else:
            self.setPos(v, 0.0)
        if notify and self._scene is not None:
            try:
                self._scene.note_geometry(self)
            except Exception:
                exc_note("set_pos_mm @ ggis/ui/views/layout/canvas.py:274")
                pass

    def _scale(self):
        if self._scene is not None:
            return max(1e-6, self._scene.view_scale())
        return 1.0

    def pos_mm(self):
        return self.pos().y() if self.horizontal else self.pos().x()

    def set_span(self, span_mm):
        a, b = float(span_mm[0]), float(span_mm[1])
        if (a, b) == self._span:
            return
        self.prepareGeometryChange()
        self._span = (a, b)
        self.update()

    def set_hot(self, on):
        on = bool(on)
        if on == self._hot:
            return
        self._hot = on
        self.update()

    def _line(self):
        a, b = self._span
        if self.horizontal:
            return QPointF(a, 0.0), QPointF(b, 0.0)
        return QPointF(0.0, a), QPointF(0.0, b)

    def boundingRect(self):
        px = 4.0 / self._scale()
        p1, p2 = self._line()
        return QRectF(p1, p2).normalized().adjusted(-px, -px, px, px)

    def shape(self):
        return QPainterPath()

    def _set_dragging(self, on):
        on = bool(on)
        if on == self._dragging:
            return
        self._dragging = on
        self.update()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        k = self._scale()
        hot = bool(self._dragging or self._hot)
        pen = QPen(QColor("#2E7BE0") if hot else QColor("#1F9E8F"),
                   (2.0 if hot else 1.2) / k)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([5, 3])
        painter.setPen(pen)
        painter.drawLine(*self._line())
        if hot:
            f = QFont()
            f.setPointSizeF(max(0.5, 9.0 * 0.72 / k))
            painter.setFont(f)
            p1, _p2 = self._line()
            txt = "%g mm" % round(self.pos_mm(), 1)
            if self.horizontal:
                pos = QPointF(p1.x() + 4.0 / k, -3.0 / k)
            else:
                pos = QPointF(4.0 / k, p1.y() + 10.0 / k)
            fm = painter.fontMetrics()
            box = QRectF(pos.x() - 2.0 / k, pos.y() - fm.ascent() - 1.0 / k,
                         fm.horizontalAdvance(txt) + 6.0 / k,
                         fm.height() + 2.0 / k)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(46, 123, 224, 220)))
            painter.drawRoundedRect(box, 2.0 / k, 2.0 / k)
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(pos, txt)



class _MarginItem(QGraphicsItem):

    def __init__(self, scene=None):
        super().__init__()
        self._scene = scene
        self._rect = (0.0, 0.0, 0.0, 0.0)
        self.setZValue(4800)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def set_rect_mm(self, rect):
        self.prepareGeometryChange()
        self._rect = (float(rect.x()), float(rect.y()),
                      float(rect.width()), float(rect.height()))
        self.update()

    def _qr(self):
        x, y, w, h = self._rect
        return QRectF(x, y, w, h)

    def boundingRect(self):
        px = 3.0 / max(1e-6, (self._scene.view_scale()
                              if self._scene is not None else 1.0))
        return self._qr().adjusted(-px, -px, px, px)

    def shape(self):
        path = QPainterPath()
        return path

    def paint(self, painter, option, widget=None):
        r = self._qr()
        if r.width() <= 0 or r.height() <= 0:
            return
        k = 1.0 / max(1e-6, (self._scene.view_scale()
                             if self._scene is not None else 1.0))
        pen = QPen(QColor("#B08A2E"), 1.2 * k)
        pen.setStyle(Qt.PenStyle.DashDotLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)


class _RulerBar(QWidget):

    def __init__(self, view, horizontal=True, parent=None):
        super().__init__(parent if parent is not None else view.viewport())
        self._view = view
        self.horizontal = bool(horizontal)
        self._drag = None
        self._drag_guide = None
        self._grab = False
        self.setMouseTracking(True)
        if self.horizontal:
            self.setFixedHeight(RULER_PX)
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setFixedWidth(RULER_PX)
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        try:
            self.setToolTip("")
        except Exception:
            exc_note("__init__ @ ggis/ui/views/layout/canvas.py:448")
            pass

    def sync_geometry(self):
        vp = self._view.viewport()
        if self.horizontal:
            self.setGeometry(0, 0, max(1, vp.width()), RULER_PX)
        else:
            self.setGeometry(0, 0, RULER_PX, max(1, vp.height()))

    def _steps(self, k):
        if k >= 6.0:
            return 1.0, 10.0
        if k >= 2.0:
            return 5.0, 10.0
        if k >= 1.0:
            return 5.0, 20.0
        if k >= 0.6:
            return 10.0, 50.0
        if k >= 0.3:
            return 20.0, 100.0
        return 50.0, 200.0

    def _label_font(self):
        f = QFont(self.font())
        try:
            f.setPointSizeF(7.5)
        except Exception:
            exc_note("_label_font @ ggis/ui/views/layout/canvas.py:485")
            pass
        return f

    def paintEvent(self, e):
        from ggis.common.styling import icons as _icons
        from ggis.common.styling import themes as _themes
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            dark = bool(_icons.is_dark())
            bg = _themes.theme_color("panel", dark)
            fg_ma = _themes.theme_color("text", dark)
            fg_mi = _themes.theme_color("text_dim", dark)
            edge = _themes.theme_color("border", dark)
        except Exception:
            exc_note("paintEvent @ ggis/ui/views/layout/canvas.py:500")
            bg, fg_ma, fg_mi, edge = (QColor("#242932"), QColor("#e6eaf2"),
                                      QColor("#9aa4b2"), QColor("#333941"))
        p.fillRect(self.rect(), QColor(bg))
        p.setPen(QPen(QColor(edge), 1))
        if self.horizontal:
            p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        else:
            p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

        try:
            k = float(self._view.transform().m11()) or 1.0
        except Exception:
            exc_note("paintEvent @ ggis/ui/views/layout/canvas.py:513")
            k = 1.0
        if k <= 0:
            return
        minor, major = self._steps(k)
        vp = self._view.viewport()
        if self.horizontal:
            a = self._view.mapToScene(0, 0).x()
            b = self._view.mapToScene(vp.width(), 0).x()
        else:
            a = self._view.mapToScene(0, 0).y()
            b = self._view.mapToScene(0, vp.height()).y()
        if b < a:
            a, b = b, a

        p.setFont(self._label_font())
        fm = p.fontMetrics()
        w_self, h_self = self.width(), self.height()
        ln = (h_self if self.horizontal else w_self) - 1
        t_major, t_minor = 5, 3
        baseline = max(fm.ascent() + 1, h_self - t_major - 2)
        px_major = max(1e-6, major * k)
        if px_major >= 30:
            stride = 1
        elif px_major >= 18:
            stride = 2
        elif px_major >= 10:
            stride = 5
        else:
            stride = 0

        v = math.floor(a / minor) * minor
        while v <= b + minor:
            r = self._to_px(v)
            if r is not None:
                ri = int(round(r))
                is_major = abs(v / major - round(v / major)) < 1e-6
                p.setPen(QPen(QColor(fg_ma if is_major else fg_mi), 1))
                t = t_major if is_major else t_minor
                if self.horizontal:
                    p.drawLine(ri, ln - t, ri, ln)
                else:
                    p.drawLine(ln - t, ri, ln, ri)
                if is_major and stride:
                    idx = int(round(v / major))
                    if idx % stride == 0:
                        txt = "%g" % round(v, 1)
                        tw = fm.horizontalAdvance(txt)
                        p.setPen(QPen(QColor(fg_ma), 1))
                        if self.horizontal:
                            x = ri + 3
                            if x + tw > w_self - 2:
                                x = ri - 3 - tw
                            p.drawText(QPointF(x, baseline), txt)
                        else:
                            y0 = ri - tw / 2.0
                            y0 = max(2.0, min(float(h_self - 2) - tw, y0))
                            p.save()
                            p.translate(3.0, y0)
                            p.rotate(90)
                            p.drawText(QPointF(0, 0), txt)
                            p.restore()
            v += minor

        if self._drag is not None:
            pos = (self._drag.x() if self.horizontal else self._drag.y())
            p.setPen(QPen(QColor("#2E7BE0"), 2))
            if self.horizontal:
                p.drawLine(pos, 0, pos, h_self)
            else:
                p.drawLine(0, pos, w_self, pos)

        try:
            for g in (self._view.guides() or []):
                if bool(g.horizontal) == bool(self.horizontal):
                    continue
                r = self._to_px(float(g.pos_mm()))
                if r is None:
                    continue
                ri = int(round(r))
                col = (QColor("#2E7BE0") if getattr(g, "_dragging", False)
                       else QColor("#1F9E8F"))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(col, 2))
                if self.horizontal:
                    p.drawLine(ri, h_self - 1, ri, h_self - 8)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(col))
                    p.drawPolygon(QPolygonF([QPointF(ri - 3.5, h_self - 9.0),
                                             QPointF(ri + 3.5, h_self - 9.0),
                                             QPointF(ri, h_self - 13.0)]))
                else:
                    p.drawLine(w_self - 1, ri, w_self - 8, ri)
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(QBrush(col))
                    p.drawPolygon(QPolygonF([QPointF(w_self - 9.0, ri - 3.5),
                                             QPointF(w_self - 9.0, ri + 3.5),
                                             QPointF(w_self - 13.0, ri)]))
        except Exception:
            exc_note("paintEvent @ ggis/ui/views/layout/canvas.py:625")
            pass

    def _to_px(self, mm):
        try:
            vp = self._view.viewport()
            if self.horizontal:
                return float(self._view.mapFromScene(QPointF(mm, 0.0)).x())
            return float(self._view.mapFromScene(QPointF(0.0, mm)).y())
        except Exception:
            exc_note("_to_px @ ggis/ui/views/layout/canvas.py:635")
            _ = vp
            return None

    def _pos_component(self, vp_pos):
        return int(vp_pos.x()) if self.horizontal else int(vp_pos.y())

    def _guides_here(self):
        out = []
        for g in (self._view.guides() or []):
            if bool(g.horizontal) == bool(self.horizontal):
                continue
            out.append(g)
        return out

    def _hit_guide(self, vp_pos):
        x = self._pos_component(vp_pos)
        best, bd = None, None
        for g in self._guides_here():
            r = self._to_px(float(g.pos_mm()))
            if r is None:
                continue
            d = abs(float(r) - float(x))
            if d <= GUIDE_GRAB_PX and (bd is None or d < bd):
                best, bd = g, d
        return best

    def _mm_at(self, vp_pos):
        try:
            sp = self._view.mapToScene(vp_pos)
            return sp.x() if self.horizontal else sp.y()
        except Exception:
            exc_note("_mm_at @ ggis/ui/views/layout/canvas.py:671")
            return 0.0

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(e)
            return
        try:
            self.grabMouse()
            self._grab = True
        except Exception:
            exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:681")
            self._grab = False
        pos = self._to_local(e)
        self._drag = pos
        g = self._hit_guide(pos)
        self._drag_guide = g
        if g is not None:
            try:
                g._set_dragging(True)
            except Exception:
                exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:693")
                pass
        self.update()
        e.accept()

    def mouseMoveEvent(self, e):
        if self._drag is None:
            super().mouseMoveEvent(e)
            return
        pos = self._to_local(e)
        self._drag = pos
        g = getattr(self, "_drag_guide", None)
        if g is not None:
            try:
                g.set_pos_mm(self._mm_at(pos))
            except Exception:
                exc_note("mouseMoveEvent @ ggis/ui/views/layout/canvas.py:709")
                pass
            self._view._refresh_rulers_marks()
        self.update()
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._drag is None:
            super().mouseReleaseEvent(e)
            return
        pos = self._to_local(e)
        self._drag = None
        g = getattr(self, "_drag_guide", None)
        self._drag_guide = None
        self.update()
        if self._grab:
            try:
                self.releaseMouse()
            except Exception:
                exc_note("mouseReleaseEvent @ ggis/ui/views/layout/canvas.py:727")
                pass
            self._grab = False
        if g is not None:
            try:
                g._set_dragging(False)
                g.set_pos_mm(self._mm_at(pos))
                self._view._refresh_rulers_marks()
            except Exception:
                exc_note("mouseReleaseEvent @ ggis/ui/views/layout/canvas.py:736")
                pass
            e.accept()
            return
        try:
            sp = self._view.mapToScene(pos)
            val = sp.x() if self.horizontal else sp.y()
            self._view.add_guide(not self.horizontal, val)
        except Exception:
            exc_note("mouseReleaseEvent @ ggis/ui/views/layout/canvas.py:748")
            pass
        e.accept()

    def _build_menu(self, g):
        m = GgsRulerMenu(self)
        if g is not None:
            a = m.addAction(_tr("删除这条参考线"))
            a.triggered.connect(
                lambda _c=False, _g=g: self._view.remove_guide(_g))
        a = m.addAction(_tr("清除全部参考线"))
        try:
            n = len(self._view.guides() or [])
        except Exception:
            exc_note("_build_menu @ ggis/ui/views/layout/canvas.py:764")
            n = 0
        a.setEnabled(n > 0)
        a.triggered.connect(lambda _c=False: self._view.clear_guides())
        return m

    def contextMenuEvent(self, e):
        pos = e.pos()
        g = self._hit_guide(pos)
        m = self._build_menu(g)
        try:
            m.exec(e.globalPos())
        except Exception:
            _log.exception("布局：标尺右键菜单失败")
        e.accept()

    def _to_local(self, e):
        try:
            g = e.globalPosition().toPoint()
            return self._view.viewport().mapFromGlobal(g)
        except Exception:
            exc_note("_to_local @ ggis/ui/views/layout/canvas.py:790")
            try:
                return e.position().toPoint()
            except Exception:
                exc_note("_to_local @ ggis/ui/views/layout/canvas.py:793")
                return QPoint(0, 0)


class ItemFrame(QGraphicsItem):

    def __init__(self, item: LayoutItem, scene=None):
        super().__init__()
        self.item = item
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
                     True)
        self.setAcceptHoverEvents(True)
        self._scene = scene
        self._drag = ""
        self._grab = QPointF()
        self._start = QRectF()
        self._group = []
        self._hover = False
        self.setPos(item.rect_mm.topLeft())
        self.setZValue(1000 + int(item.z))
        self._sync_visible()

    def _sync_visible(self):
        try:
            self.setVisible(bool(getattr(self.item, "visible", True)))
        except Exception:
            exc_note("_sync_visible @ ggis/ui/views/layout/canvas.py:833")
            pass

    def _rect0(self):
        r = self.item.rect_mm
        return QRectF(0.0, 0.0, max(0.5, r.width()), max(0.5, r.height()))

    def boundingRect(self):
        m = self._handle_mm() * 1.6 + self._label_mm()
        return self._rect0().adjusted(-m, -m * 2.0, m, m)

    def shape(self):
        path = QPainterPath()
        try:
            path.setFillRule(Qt.FillRule.WindingFill)
            path.addRect(self._rect0())
            h = self._handle_mm() * 0.9
            for pt in self._handles().values():
                path.addRect(QRectF(pt.x() - h, pt.y() - h, h * 2.0, h * 2.0))
        except Exception:
            _log.exception("布局：元素命中区计算失败（退回整框）")
            return super().shape()
        return path

    def _scale(self):
        if self._scene is not None:
            return max(1e-6, self._scene.view_scale())
        return 1.0

    def _handle_mm(self):
        return HANDLE_PX / self._scale()

    def _label_mm(self):
        return LABEL_PX / self._scale()

    def _handles(self):
        r = self._rect0()
        c = r.center()
        return {"nw": r.topLeft(), "ne": r.topRight(),
                "sw": r.bottomLeft(), "se": r.bottomRight(),
                "n": QPointF(c.x(), r.top()),
                "s": QPointF(c.x(), r.bottom()),
                "w": QPointF(r.left(), c.y()),
                "e": QPointF(r.right(), c.y())}

    def _hit_handle(self, pos):
        h = self._handle_mm() * 0.9
        for name, pt in self._handles().items():
            if QRectF(pt.x() - h, pt.y() - h, h * 2, h * 2).contains(pos):
                return name
        return ""

    def _drag_in_progress(self):
        sc = self._scene
        if sc is None:
            return False
        try:
            for v in sc.views():
                if getattr(v, "_dragging", False):
                    return True
        except Exception:
            exc_note("_drag_in_progress @ ggis/ui/views/layout/canvas.py:943")
            pass
        return False

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self._rect0()
        sel = self.isSelected()
        kmm = 1.0 / self._scale()
        if sel:
            painter.setPen(QPen(QColor("#2E7BE0"), 2.0 * kmm))
            painter.setBrush(QBrush(QColor(46, 123, 224, 26)))
            painter.drawRect(r)
        elif getattr(self, "_hover", False) and not self._drag_in_progress():
            painter.setPen(QPen(QColor("#7B8794"), 1.4 * kmm))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

        if sel:
            f = QFont()
            f.setPointSizeF(max(0.5, LABEL_PX * 0.72 / self._scale()))
            painter.setFont(f)
            painter.setPen(QPen(QColor("#1F6FEB")))
            m2 = self._handle_mm() * 1.6 + self._label_mm()
            room = max(2.0 * kmm, r.width() + m2 - 1.0 * kmm)
            txt = "%s  %g×%gmm" % (getattr(self.item, "label", ""),
                                   self.item.rect_mm.width(),
                                   self.item.rect_mm.height())
            txt = painter.fontMetrics().elidedText(
                txt, Qt.TextElideMode.ElideRight, room)
            painter.drawText(QPointF(r.left(), r.top() - 3.0 * kmm), txt)
            h = self._handle_mm() * 0.5
            painter.setPen(QPen(QColor("#1B4F9C"), 1.2 * kmm))
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            for pt in self._handles().values():
                painter.drawRect(QRectF(pt.x() - h, pt.y() - h, h * 2, h * 2))

        if self._is_activated():
            self._paint_activated(painter, r, kmm)

    def _paint_activated(self, painter, r, kmm):
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor("#E0912F"), 3.0 * kmm)
        try:
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        except Exception:
            exc_note("_paint_activated @ ggis/ui/views/layout/canvas.py:1013")
            pass
        painter.setPen(pen)
        d = 1.5 * kmm
        painter.drawRect(r.adjusted(-d, -d, d, d))
        f = QFont()
        f.setPointSizeF(max(0.5, LABEL_PX * 0.72 / self._scale()))
        f.setBold(True)
        painter.setFont(f)
        txt = _tr("已激活")
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(txt) + 8.0 * kmm
        th = fm.height() + 2.0 * kmm
        box = QRectF(r.left() + 2.0 * kmm, r.top() + 2.0 * kmm, tw, th)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#E0912F")))
        painter.drawRoundedRect(box, 2.0 * kmm, 2.0 * kmm)
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, txt)

    def _notify_overlay(self, action):
        sc = self._scene
        if sc is None:
            return
        for v in sc.views():
            fn = getattr(v, "_elem_overlay_" + action, None)
            if fn is None:
                continue
            try:
                if action == "end":
                    fn()
                else:
                    fn(self)
            except Exception:
                _log.exception("布局：浮层通知 %s 失败", action)

    def _is_activated(self):
        try:
            return (self._scene is not None
                    and getattr(self._scene, "activated", None) is self.item)
        except Exception:
            exc_note("_is_activated @ ggis/ui/views/layout/canvas.py:1064")
            return False

    def _snap(self, v):
        if SNAP_MM <= 0:
            return v
        return round(float(v) / SNAP_MM) * SNAP_MM

    def _ratio_locked(self):
        try:
            return bool(getattr(self.item, "fixed_ratio", False))
        except Exception:
            exc_note("_ratio_locked @ ggis/ui/views/layout/canvas.py:1086")
            return False

    def _scaled_rect(self, d):
        sw = max(MIN_MM, float(self._start.width()))
        sh = max(MIN_MM, float(self._start.height()))
        den = sw * sw + sh * sh
        if self._drag in ("n", "s", "e", "w"):
            st = self._start
            if self._drag in ("e", "w"):
                sgn = 1.0 if self._drag == "e" else -1.0
                w = max(MIN_MM, float(self._snap(
                    sw * max(0.05, 1.0 + sgn * d.x() / sw))))
                h = max(MIN_MM, w * sh / sw)
                x = st.left() if sgn > 0 else st.right() - w
                return QRectF(x, st.center().y() - h * 0.5, w, h)
            sgn = 1.0 if self._drag == "s" else -1.0
            h = max(MIN_MM, float(self._snap(
                sh * max(0.05, 1.0 + sgn * d.y() / sh))))
            w = max(MIN_MM, h * sw / sh)
            y = st.top() if sgn > 0 else st.bottom() - h
            return QRectF(st.center().x() - w * 0.5, y, w, h)
        sx = -1.0 if self._drag in ("nw", "sw") else 1.0
        sy = -1.0 if self._drag in ("nw", "ne") else 1.0
        dx, dy = d.x() * sx, d.y() * sy
        s = 1.0
        if den > 1e-9:
            s += (dx * sw + dy * sh) / den
        s = max(MIN_MM / min(sw, sh), min(20.0, s))
        w = max(MIN_MM, float(self._snap(sw * s)))
        h = max(MIN_MM, w * sh / sw)
        st = self._start
        if self._drag == "se":
            return QRectF(st.left(), st.top(), w, h)
        if self._drag == "nw":
            return QRectF(st.right() - w, st.bottom() - h, w, h)
        if self._drag == "ne":
            return QRectF(st.left(), st.bottom() - h, w, h)
        return QRectF(st.right() - w, st.top(), w, h)

    def _snap_guides(self, p):
        sc = self._scene
        out = []
        if sc is None:
            return p, out
        try:
            guides = list(getattr(sc, "guides", []) or [])
        except Exception:
            exc_note("_snap_guides @ ggis/ui/views/layout/canvas.py:1167")
            return p, out
        if not guides:
            return p, out
        k = max(1e-6, sc.view_scale())
        tol = GUIDE_SNAP_PX / k
        r = self.item.rect_mm
        x, y = float(p.x()), float(p.y())
        best_x = None
        best_y = None
        for g in guides:
            try:
                if not g.isVisible():
                    continue
                if g.horizontal:
                    gy = float(g.pos_mm())
                    for cand in (y, y + r.height()):
                        d = abs(cand - gy)
                        if d <= tol and (best_y is None or d < best_y[0]):
                            best_y = (d, gy - (cand - y))
                            best_y_g = g
                else:
                    gx = float(g.pos_mm())
                    for cand in (x, x + r.width()):
                        d = abs(cand - gx)
                        if d <= tol and (best_x is None or d < best_x[0]):
                            best_x = (d, gx - (cand - x))
                            best_x_g = g
            except Exception:
                exc_note("_snap_guides @ ggis/ui/views/layout/canvas.py:1195")
                continue
        if best_x is not None:
            x = float(best_x[1])
            if best_x_g not in out:
                out.append(best_x_g)
        if best_y is not None:
            y = float(best_y[1])
            if best_y_g not in out:
                out.append(best_y_g)
        return QPointF(x, y), out

    def _set_hot_guides(self, gs):
        prev = getattr(self, "_hot_guides", None) or []
        for g in prev:
            if g not in gs:
                try:
                    g.set_hot(False)
                except Exception:
                    exc_note("_set_hot_guides @ ggis/ui/views/layout/canvas.py:1214")
                    pass
        for g in gs:
            try:
                g.set_hot(True)
            except Exception:
                exc_note("_set_hot_guides @ ggis/ui/views/layout/canvas.py:1219")
                pass
        self._hot_guides = list(gs)

    def mousePressEvent(self, e):
        try:
            sc = self.scene()
            for v in (sc.views() if sc is not None else []):
                for _name in ("sel_path_mode", "draw_kind"):
                    fn = getattr(v, _name, None)
                    if callable(fn) and fn():
                        e.ignore()
                        return
        except Exception:
            exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:1238")
            pass
        if e.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(e)
            return
        name = self._hit_handle(e.pos())
        self._grab = QPointF(e.scenePos())
        self._start = QRectF(self.item.rect_mm)
        self._overlay_armed = True
        if self._scene is not None:
            if not self.isSelected():
                try:
                    self._scene.clearSelection()
                except Exception:
                    exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:1261")
                    pass
            self.setSelected(True)
            self._group = self._group_frames()
        e.accept()
        if name:
            self._drag = name
            return
        self._drag = "move"

    def _group_frames(self):
        out = []
        sc = self._scene
        if sc is None:
            return out
        mov = QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        for f in list(getattr(sc, "frames", []) or []):
            try:
                if f is self or not f.isSelected() or not f.isVisible():
                    continue
                if not (f.flags() & mov):
                    continue
                out.append((f, QPointF(f.pos())))
            except Exception:
                exc_note("_group_frames @ ggis/ui/views/layout/canvas.py:1290")
                continue
        return out

    def mouseMoveEvent(self, e):
        if getattr(self, "_overlay_armed", False):
            self._overlay_armed = False
            self._notify_overlay("begin")
        if self._drag in ("nw", "ne", "sw", "se", "n", "s", "e", "w"):
            d = e.scenePos() - self._grab
            if self._ratio_locked():
                self._apply(self._scaled_rect(d))
                e.accept()
                return
            r = QRectF(self._start)
            if "n" in self._drag:
                r.setTop(min(self._start.bottom() - MIN_MM,
                             self._start.top() + d.y()))
            if "s" in self._drag:
                r.setBottom(max(self._start.top() + MIN_MM,
                                self._start.bottom() + d.y()))
            if "w" in self._drag:
                r.setLeft(min(self._start.right() - MIN_MM,
                              self._start.left() + d.x()))
            if "e" in self._drag:
                r.setRight(max(self._start.left() + MIN_MM,
                               self._start.right() + d.x()))
            r = QRectF(self._snap(r.left()), self._snap(r.top()),
                       max(MIN_MM, self._snap(r.width())),
                       max(MIN_MM, self._snap(r.height())))
            self._apply(r)
            e.accept()
            return
        if self._drag == "move":
            d = e.scenePos() - self._grab
            self.setPos(self._start.topLeft() + d)
            for fr, p0 in list(getattr(self, "_group", []) or []):
                try:
                    fr.setPos(p0 + d)
                except Exception:
                    exc_note("mouseMoveEvent @ ggis/ui/views/layout/canvas.py:1339")
                    pass
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        was = self._drag
        moved = (QRectF(self._start) != QRectF(self.item.rect_mm))
        self._drag = ""
        self._group = []
        super().mouseReleaseEvent(e)
        self._set_hot_guides([])
        if was and moved:
            self._notify_overlay("end_keep")
            self._scene.commit_geometry()
        else:
            self._notify_overlay("end")

    def cancel_drag(self):
        if not self._drag:
            return False
        self._drag = ""
        self._group = []
        self._overlay_armed = False
        try:
            self._apply(QRectF(self._start))
        except Exception:
            _log.exception("布局：取消拖动时复位矩形失败")
        try:
            self._set_hot_guides([])
        except Exception:
            exc_note("cancel_drag @ ggis/ui/views/layout/canvas.py:1385")
            pass
        try:
            self._notify_overlay("end")
        except Exception:
            exc_note("cancel_drag @ ggis/ui/views/layout/canvas.py:1389")
            pass
        return True

    def hoverEnterEvent(self, e):
        self._set_hover(True)
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        self._set_hover(False)
        try:
            self.unsetCursor()
        except Exception:
            exc_note("hoverLeaveEvent @ ggis/ui/views/layout/canvas.py:1402")
            pass
        super().hoverLeaveEvent(e)

    def hoverMoveEvent(self, e):
        if self._scene is not None \
                and getattr(self._scene, "activated", None) is not None:
            return
        try:
            cur = HANDLE_CURSORS.get(self._hit_handle(e.pos()))
            if cur is None:
                cur = Qt.CursorShape.SizeAllCursor
            self.setCursor(cur)
        except Exception:
            exc_note("hoverMoveEvent @ ggis/ui/views/layout/canvas.py:1425")
            pass
        super().hoverMoveEvent(e)

    def _set_hover(self, on):
        if bool(getattr(self, "_hover", False)) == bool(on):
            return
        self._hover = bool(on)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            p = QPointF(value)
            p.setX(self._snap(p.x()))
            p.setY(self._snap(p.y()))
            p, hot = self._snap_guides(p)
            self._set_hot_guides(hot)
            return p
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            r = self.item.rect_mm
            r.moveTo(self.pos().x(), self.pos().y())
            self.item.set_rect_mm(r)
            if self._scene is not None:
                self._scene.note_geometry(self)
        return super().itemChange(change, value)

    def _apply(self, rect):
        rect = QRectF(rect)
        try:
            tp, _hot = self._snap_guides(QPointF(rect.left(), rect.top()))
            rect.moveTo(tp)
        except Exception:
            exc_note("_apply @ ggis/ui/views/layout/canvas.py:1461")
            pass
        self.prepareGeometryChange()
        self.setPos(rect.topLeft())
        self.item.set_rect_mm(rect)
        if self._scene is not None:
            self._scene.note_geometry(self)
        self.update()

    def sync_from_item(self):
        self.prepareGeometryChange()
        r = self.item.rect_mm
        self.setPos(r.topLeft())
        self.setZValue(1000 + int(self.item.z))
        self._sync_visible()
        self.update()


class LayoutScene(QGraphicsScene):

    geometryChanged = Signal()
    selectionChanged2 = Signal(object)

    def __init__(self, layout=None, project=None, parent=None):
        super().__init__(parent)
        self.layout = layout
        self.project = project
        self._scale = 1.0
        self._backdrop_w = 0
        self._back_dirty = False
        self._fast_frame = False
        self._frame_w = 0
        self._prog_sel = False
        self._back = QGraphicsPixmapItem()
        self._back.setZValue(-1000)
        self._back.setTransformationMode(
            Qt.TransformationMode.SmoothTransformation)
        try:
            self._back.setCacheMode(
                QGraphicsItem.CacheMode.DeviceCoordinateCache)
        except Exception:
            exc_note("__init__ @ ggis/ui/views/layout/canvas.py:1514")
            pass
        self.addItem(self._back)
        self.frames = []
        self.guides = []
        self.activated = None
        self._margin_item = _MarginItem(self)
        self._margin_item.setVisible(False)
        self.addItem(self._margin_item)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._do_refresh)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(max(50, int(BACKDROP_SETTLE_MS)))
        self._settle.timeout.connect(self._do_settle)
        self._pending = False
        self._defer = 0
        self._bd = BackdropRenderer(self)
        self._bd.rendered.connect(self._on_backdrop_ready)
        self._bd.patch_ready.connect(self._on_patch_ready)
        self._bd.elem_ready.connect(self._on_elem_ready)
        self._bd_seq = 0
        self._bd_w = 0
        self._bd_after = ""
        self._mapr = None
        self._mapr_dirty = False
        self._mapr_wait = QTimer(self)
        self._mapr_wait.setSingleShot(True)
        self._mapr_wait.setInterval(1500)
        self._mapr_wait.timeout.connect(
            lambda: self._flush_map_frames(force=True))
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.
                               BspTreeIndex)
        self.selectionChanged.connect(self._on_sel)

    def view_scale(self):
        return self._scale

    def set_view_scale(self, s):
        s = max(0.05, float(s))
        if abs(s - self._scale) < 1e-6:
            return
        self._scale = s
        if self._backdrop_width() != self._backdrop_w:
            self._back_dirty = True
        for f in self.frames:
            f.prepareGeometryChange()
        self.update()

    def _backdrop_width(self):
        s = float(self._scale or 1.0)
        for limit, px in BACKDROP_STEPS:
            if s <= limit + 1e-9:
                return int(px)
        return int(BACKDROP_STEPS[-1][1])

    def sync_backdrop_detail(self):
        if not self._back_dirty:
            return
        self._settle.start()

    def set_layout(self, layout, project=None):
        if project is not None:
            self.project = project
        self.layout = layout
        self.rebuild()

    def rebuild(self):
        for v in self.views():
            for _name in ("_drop_map_overlay", "_drop_element_overlay"):
                fn = getattr(v, _name, None)
                if fn is None:
                    continue
                try:
                    fn()
                except Exception:
                    _log.exception("布局：重建前收浮层失败（%s）", _name)
            try:
                v._dragging = False
            except Exception:
                exc_note("rebuild @ ggis/ui/views/layout/canvas.py:1654")
                pass
        try:
            g = self.mouseGrabberItem()
            if g is not None:
                g.ungrabMouse()
        except Exception:
            exc_note("rebuild @ ggis/ui/views/layout/canvas.py:1668")
            pass
        for _m in ("setFocusItem", "clearSelection"):
            fn = getattr(self, _m, None)
            if fn is None:
                continue
            try:
                if _m == "setFocusItem":
                    fn(None)
                else:
                    fn()
            except Exception:
                exc_note("rebuild @ ggis/ui/views/layout/canvas.py:1679")
                pass
        lay = self.layout
        if lay is None:
            self._hide_and_drop(list(self.frames))
            self.frames = []
            self.setSceneRect(QRectF(0, 0, 100, 100))
            self._back.setPixmap(QPixmap())
            return
        by_item = {}
        for f in self.frames:
            try:
                by_item[id(f.item)] = f
            except Exception:
                exc_note("rebuild @ ggis/ui/views/layout/canvas.py:1700")
                pass
        keep = []
        for item in lay.items:
            fr = by_item.pop(id(item), None)
            if fr is None:
                fr = ItemFrame(item, self)
                self.addItem(fr)
            else:
                try:
                    fr.sync_from_item()
                except Exception:
                    _log.exception("布局：复用元素框时同步失败")
            keep.append(fr)
        self.frames = keep
        self._hide_and_drop(list(by_item.values()))
        _busy_on = None
        try:
            from ggis.ui.dialogs.busy import is_busy as _busy_on
        except Exception:
            exc_note("rebuild @ ggis/ui/views/layout/canvas.py:1727")
            _busy_on = None
        if _busy_on is not None and _busy_on():
            try:
                self.request_backdrop()
            except Exception:
                _log.exception("布局：重建时后台渲染投递失败 ⇒ 退回同步渲染")
                self.refresh_now()
        else:
            self.refresh_now()
        self.refresh_rect()

    def _hide_and_drop(self, frames):
        if not frames:
            return
        for f in frames:
            try:
                f.setVisible(False)
            except Exception:
                exc_note("_hide_and_drop @ ggis/ui/views/layout/canvas.py:1751")
                pass

        def _drop():
            for f in frames:
                try:
                    self.removeItem(f)
                except Exception:
                    exc_note("_drop @ ggis/ui/views/layout/canvas.py:1758")
                    pass

        try:
            QTimer.singleShot(0, _drop)
        except Exception:
            exc_note("_hide_and_drop @ ggis/ui/views/layout/canvas.py:1763")
            _drop()

    def frame_of(self, item):
        for f in self.frames:
            if f.item is item:
                return f
        return None

    def refresh_rect(self):
        if self.layout is None:
            return
        w_mm, h_mm = self.layout.page_mm()
        pad = 25.0
        self.setSceneRect(QRectF(-pad, -pad, w_mm + pad * 2,
                                 h_mm + pad * 2))
        try:
            self._margin_item.set_rect_mm(self.layout.content_rect_mm())
        except Exception:
            exc_note("refresh_rect @ ggis/ui/views/layout/canvas.py:1783")
            pass
        _ = (w_mm, h_mm)

    def add_guide(self, horizontal, pos_mm):
        try:
            w_mm, h_mm = self.layout.page_mm() if self.layout else (100.0, 100.0)
            span = (0.0, w_mm) if horizontal else (0.0, h_mm)
            g = _GuideItem(horizontal, float(pos_mm), self, span_mm=span)
            self.addItem(g)
            self.guides.append(g)
            return g
        except Exception:
            _log.exception("布局：添加参考线失败")
            return None

    def clear_guides(self):
        for g in list(self.guides):
            try:
                self.removeItem(g)
            except Exception:
                exc_note("clear_guides @ ggis/ui/views/layout/canvas.py:1818")
                pass
        self.guides = []
        QTimer.singleShot(0, lambda: None)

    def set_guides_visible(self, on):
        for g in list(self.guides):
            try:
                g.setVisible(bool(on))
            except Exception:
                exc_note("set_guides_visible @ ggis/ui/views/layout/canvas.py:1829")
                pass
        self.update()

    def set_margins_visible(self, on):
        try:
            if on:
                self._margin_item.set_rect_mm(self.layout.content_rect_mm())
            self._margin_item.setVisible(bool(on))
        except Exception:
            exc_note("set_margins_visible @ ggis/ui/views/layout/canvas.py:1838")
            pass

    def _map_renderer(self):
        if self._mapr is None:
            try:
                from ggis.ui.views.layout.maprender import MapFrameRenderer
                r = MapFrameRenderer(self, blocked=self._map_proc_blocked)
                r.rendered.connect(self._on_map_frame_ready)
                self._mapr = r
            except Exception:
                _log.exception("布局：地图框子进程渲染器创建失败（回退主进程渲染）")
                return None
        return self._mapr

    def _map_proc_blocked(self):
        try:
            for v in self.views():
                cv = getattr(v.window(), "canvas", None)
                if cv is not None and hasattr(cv, "_edit_proc_block"):
                    return bool(cv._edit_proc_block)
        except Exception:
            exc_note("_map_proc_blocked @ ggis/ui/views/layout/canvas.py:1872")
            pass
        return False

    def _map_dpi(self, width_px):
        try:
            w_mm, _h_mm = self.layout.page_mm()
        except Exception:
            exc_note("_map_dpi @ ggis/ui/views/layout/canvas.py:1881")
            return 0.0
        if w_mm <= 0:
            return 0.0
        return float(width_px) / w_mm * 25.4

    def kick_map_frames(self, width_px):
        lay = self.layout
        if lay is None or self.project is None:
            return 0
        r = self._map_renderer()
        if r is None:
            return 0
        dpi = self._map_dpi(width_px)
        if dpi <= 0:
            return 0
        n = 0
        for item in list(getattr(lay, "items", []) or []):
            if str(getattr(item, "type_name", "")) != "map_frame":
                continue
            if not bool(getattr(item, "visible", True)):
                continue
            try:
                plan = item.render_plan(self.project, dpi)
            except Exception:
                _log.exception("布局：地图框渲染计划失败（跳过）")
                continue
            if not plan:
                continue
            try:
                if plan["key"] in (item._map_cache or {}):
                    continue
            except Exception:
                exc_note("kick_map_frames @ ggis/ui/views/layout/canvas.py:1922")
                pass
            try:
                ok = r.request(item, plan["key"], self.project, plan["extent"],
                               plan["w_px"], plan["h_px"], plan["dpi"],
                               getattr(item, "background", "#FFFFFF"),
                               crs=plan.get("crs"))
            except Exception:
                _log.exception("布局：地图框渲染投递失败（跳过）")
                ok = False
            if ok:
                n += 1
        return n

    def _flush_map_frames(self, force=False):
        if not self._mapr_dirty:
            return
        if not force:
            try:
                if self._interacting():
                    try:
                        self._mapr_wait.start()
                    except Exception:
                        exc_note("_flush_map_frames @ ggis/ui/views/layout/canvas.py:1954")
                        pass
                    return
            except Exception:
                exc_note("_flush_map_frames @ ggis/ui/views/layout/canvas.py:1957")
                pass
        self._mapr_dirty = False
        try:
            self.request_backdrop(width_px=int(self._frame_w or 0) or None)
        except Exception:
            _log.exception("布局：地图框到图后的底图重渲失败")

    def _on_map_frame_ready(self, img, seq, mf, key):
        del seq
        if img is None or img.isNull() or mf is None:
            return
        if not mf.store_layers_image(key, img):
            return
        self._mapr_dirty = True
        self._flush_map_frames()

    def _backdrop_target_width(self, width_px=None):
        target = int(self._backdrop_width())
        w = int(width_px or target)
        cur = int(getattr(self, "_frame_w", 0) or 0)
        if cur > 0 and w < cur:
            w = cur
        self._backdrop_w = target
        return int(w)

    def _apply_backdrop(self, img, w):
        if img is None or img.isNull():
            _log.warning("布局：底图渲染返回空图（保留上一张）")
            return False
        self._frame_w = int(w)
        w_mm, h_mm = self.layout.page_mm()
        pm = QPixmap.fromImage(img)
        self._back.setPixmap(pm)
        self._back.setTransform(
            QTransform().scale(w_mm / max(1, img.width()),
                               h_mm / max(1, img.height())))
        return True

    def refresh_backdrop(self, width_px=None):
        if self.layout is None:
            return False
        w = self._backdrop_target_width(width_px)
        self.kick_map_frames(w)
        try:
            img = EX.preview_image(self.layout, self.project, width_px=w)
        except Exception:
            _log.exception("布局：底图渲染失败")
            img = QImage()
        return self._apply_backdrop(img, w)

    def request_backdrop(self, width_px=None, after=""):
        if self.layout is None:
            return False
        w = self._backdrop_target_width(width_px)
        self.kick_map_frames(w)
        self._bd_w = int(w)
        self._bd_after = str(after or "")
        self._bd_seq += 1
        try:
            frozen = EX.freeze_snapshot(self.layout, self.project)
        except Exception:
            _log.exception("布局：底图快照失败（回退到同步渲染）")
            self.refresh_backdrop(width_px=w)
            # 同步渲染已出图，档位链到此结束；清脏位，避免下次 _end_fast
            # 又启动一次 _settle 渐进重渲（多一轮无谓刷新）。
            self._back_dirty = False
            return None
        return bool(self._bd.request(self._bd_seq, frozen[0], frozen[1], w))

    def _drop_all_overlays(self):
        for v in self.views():
            try:
                if bool(getattr(v, "_dragging", False)):
                    continue
            except Exception:
                exc_note("_drop_all_overlays @ ggis/ui/views/layout/canvas.py:2082")
                pass
            for name in ("_drop_map_overlay", "_drop_element_overlay"):
                fn = getattr(v, name, None)
                if fn is None:
                    continue
                try:
                    fn()
                except Exception:
                    exc_note("_drop_all_overlays @ ggis/ui/views/layout/canvas.py:2090")
                    pass

    def _finish_backdrop(self):
        self._drop_all_overlays()
        after = str(self._bd_after or "")
        if after == "settle":
            if self._backdrop_width() > int(BACKDROP_FAST_PX):
                self._settle.start()
        elif after == "chain":
            if self._next_step_width() is not None:
                self._settle.start()
            else:
                self._fast_frame = False
                self._back_dirty = False

    def _on_backdrop_ready(self, img, seq):
        if int(seq) != int(self._bd_seq):
            return
        if img is None or img.isNull():
            self._drop_all_overlays()
            return
        if not self._apply_backdrop(img, self._bd_w):
            return
        self._finish_backdrop()

    def _on_patch_ready(self, img, seq):
        if img is None or img.isNull():
            return
        for v in self.views():
            fn = getattr(v, "_apply_erase_patch", None)
            if fn is None:
                continue
            try:
                fn(img, seq)
            except Exception:
                _log.exception("布局：贴原位置背景补丁失败")

    def _on_elem_ready(self, img, seq):
        if img is None or img.isNull():
            return
        for v in self.views():
            fn = getattr(v, "_apply_elem_bitmap", None)
            if fn is None:
                continue
            try:
                fn(img, seq)
            except Exception:
                _log.exception("布局：换上拖动中的元素位图失败")

    def shutdown(self):
        for v in self.views():
            try:
                nav = getattr(v, "_nav", None)
                if nav is not None:
                    nav.close()
            except Exception:
                exc_note("shutdown @ ggis/ui/views/layout/canvas.py:2167")
                pass
        for t in (self._timer, self._settle):
            try:
                t.stop()
            except Exception:
                exc_note("shutdown @ ggis/ui/views/layout/canvas.py:2172")
                pass
        self._bd_seq += 1
        try:
            self._bd.stop()
        except Exception:
            exc_note("shutdown @ ggis/ui/views/layout/canvas.py:2177")
            pass
        try:
            if self._mapr is not None:
                self._mapr.stop()
        except Exception:
            exc_note("shutdown @ ggis/ui/views/layout/canvas.py:2183")
            pass
        self._mapr = None

    def backdrop_pixmap(self):
        try:
            return self._back.pixmap()
        except Exception:
            exc_note("backdrop_pixmap @ ggis/ui/views/layout/canvas.py:2195")
            return None

    def _interacting(self):
        settling = False
        for v in self.views():
            try:
                if getattr(v, "_nav_settling", False):
                    if getattr(v, "_dragging", False):
                        return True
                    settling = True
            except Exception:
                exc_note("_interacting @ ggis/ui/views/layout/canvas.py:2227")
                continue
        if settling:
            return False
        for v in self.views():
            try:
                if getattr(v, "_dragging", False):
                    return True
                if v._nav_active():
                    return True
            except Exception:
                exc_note("_interacting @ ggis/ui/views/layout/canvas.py:2237")
                continue
        return False

    def _do_refresh(self):
        self._pending = False
        if self._interacting() and int(getattr(self, "_defer", 0)) < 30:
            self._defer = int(getattr(self, "_defer", 0)) + 1
            self._timer.start()
            return
        self._defer = 0
        fast = bool(self._fast_frame) and int(
            getattr(self, "_frame_w", 0) or 0) <= 0
        ok = False
        try:
            ok = self.request_backdrop(
                width_px=(BACKDROP_FAST_PX if fast else None),
                after=("settle" if fast else ""))
        except Exception:
            _log.exception("布局：底图刷新投递失败")
            ok = False
        if ok is None:
            self._finish_backdrop()
        elif not ok:
            _log.warning("布局：底图刷新未投递（保留浮层，画面偏旧）")

    def _do_settle(self):
        if self._timer.isActive():
            return
        if self._interacting():
            self._settle.start()
            return
        if self._bd.is_busy():
            self._settle.start()
            return
        nxt = self._next_step_width()
        if nxt is None:
            self._fast_frame = False
            self._back_dirty = False
            return
        try:
            self.request_backdrop(width_px=nxt, after="chain")
        except Exception:
            _log.exception("布局：升档渲染投递失败")

    def _next_step_width(self):
        try:
            target = int(self._backdrop_width())
            cur = int(getattr(self, "_frame_w", 0) or 0)
            if cur <= 0 or cur >= target:
                return None
            for _limit, px in BACKDROP_STEPS:
                px = int(px)
                if px > cur:
                    return min(px, target)
            return target
        except Exception:
            exc_note("_next_step_width @ ggis/ui/views/layout/canvas.py:2337")
            return None

    def set_backdrop_smooth(self, smooth):
        try:
            self._back.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation if smooth
                else Qt.TransformationMode.FastTransformation)
        except Exception:
            exc_note("set_backdrop_smooth @ ggis/ui/views/layout/canvas.py:2354")
            pass

    def note_geometry(self, frame):
        is_elem = isinstance(frame, ItemFrame)
        for v in self.views():
            fn = getattr(v, "_elem_overlay_move" if is_elem
                         else "_refresh_rulers_marks", None)
            if fn is not None:
                try:
                    fn(frame)
                except Exception:
                    exc_note("note_geometry @ ggis/ui/views/layout/canvas.py:2397")
                    pass
            fn = getattr(v, "begin_fast", None)
            if fn is not None:
                try:
                    fn()
                except Exception:
                    exc_note("note_geometry @ ggis/ui/views/layout/canvas.py:2406")
                    pass

    def commit_geometry(self):
        self._fast_frame = False
        self._back_dirty = True
        self._timer.start()
        self.geometryChanged.emit()

    def notify_changed(self):
        self._fast_frame = True
        self._timer.start()
        self.geometryChanged.emit()

    def refresh_now(self):
        self._timer.stop()
        self._settle.stop()
        self._fast_frame = False
        self._bd_seq += 1
        try:
            self._bd.invalidate()
            if not self._bd.wait_idle():
                _log.warning("布局：后台渲染未在 4s 内结束 ⇒ 仍继续同步渲染")
        except Exception:
            exc_note("refresh_now @ ggis/ui/views/layout/canvas.py:2455")
            pass
        self.refresh_backdrop()

    def _on_sel(self):
        if self._prog_sel:
            return
        cur = self.selectedItems()
        frame = cur[-1] if cur else None
        self.selectionChanged2.emit(frame if isinstance(frame, ItemFrame)
                                    else None)

    def selected_item(self):
        cur = self.selectedItems()
        if not cur:
            return None
        for f in cur:
            if isinstance(f, ItemFrame):
                return f.item
        return None

    def sync_frames(self):
        for f in list(self.frames):
            try:
                f.sync_from_item()
            except Exception:
                exc_note("sync_frames @ ggis/ui/views/layout/canvas.py:2491")
                pass

    def select_item(self, item):
        self._prog_sel = True
        try:
            self.clearSelection()
            if item is not None:
                f = self.frame_of(item)
                if f is not None:
                    f.setSelected(True)
        finally:
            self._prog_sel = False

    def ensure_item_visible(self, item, margin=40):
        try:
            f = self.frame_of(item)
            views = self.views()
            if f is None or not views:
                return False
            v = views[0]
            vp = v.viewport()
            seen = v.mapFromScene(f.sceneBoundingRect()).boundingRect()
            if vp.rect().intersects(seen):
                return False
            v.ensureVisible(f, margin, margin)
            return True
        except Exception:
            exc_note("ensure_item_visible @ ggis/ui/views/layout/canvas.py:2537")
            return False

    def add_frame(self, item):
        fr = ItemFrame(item, self)
        self.addItem(fr)
        self.frames.append(fr)
        self.select_item(item)
        self.ensure_item_visible(item)
        self.notify_changed()
        return fr

    def remove_frame(self, item):
        f = self.frame_of(item)
        if f is None:
            return
        try:
            for _v in self.views():
                if getattr(_v, "_activated", None) is item:
                    _log.info("布局：被激活的地图框被删除 ⇒ 自动退出激活")
                    _v.set_map_activate(False)
        except Exception:
            _log.exception("布局：删除被激活的地图框时退出激活失败")
        try:
            f.setSelected(False)
        except Exception:
            exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2592")
            pass
        try:
            self.clearSelection()
        except Exception:
            exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2596")
            pass
        try:
            self.setFocusItem(None)
        except Exception:
            exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2602")
            pass
        for _step in (lambda: f.setAcceptHoverEvents(False),
                      lambda: f.setEnabled(False),
                      lambda: f.setVisible(False)):
            try:
                _step()
            except Exception:
                exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2609")
                pass
        try:
            f._scene = None
        except Exception:
            exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2613")
            pass
        try:
            self.removeItem(f)
        except Exception:
            exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2617")
            pass
        try:
            self.frames.remove(f)
        except Exception:
            exc_note("remove_frame @ ggis/ui/views/layout/canvas.py:2621")
            pass
        QTimer.singleShot(0, lambda _keep=f: None)
        self.notify_changed()


class LayoutView(QGraphicsView):

    itemPicked = Signal(object)
    textEdited = Signal(object, str)
    deleteRequested = Signal(object)
    deleteManyRequested = Signal(list)
    itemDoubleClicked = Signal(object)
    guidesShown = Signal()
    contextMenuRequested = Signal(object)
    rectDrawn = Signal(object)
    viewHistoryChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsLayoutView")
        self.setRenderHints(QPainter.RenderHint.Antialiasing
                            | QPainter.RenderHint.TextAntialiasing
                            | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(self._workspace_color()))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        try:
            self.setOptimizationFlag(
                QGraphicsView.OptimizationFlag.DontSavePainterState, True)
            self.setOptimizationFlag(
                QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        except Exception:
            exc_note("__init__ @ ggis/ui/views/layout/canvas.py:2686")
            pass
        self._fast = False
        self._fast_timer = QTimer(self)
        self._fast_timer.setSingleShot(True)
        self._fast_timer.setInterval(450)
        self._fast_timer.timeout.connect(self._end_fast)

        self._zoom = 1.0
        self._auto_fit = True
        self._scene = LayoutScene()
        self.setScene(self._scene)
        self._scene.selectionChanged2.connect(self._on_sel)
        self._sel_mode = "rect"
        self._sel_pts = []
        self._sel_drag = False
        self._sel_hover = None
        self._draw_kind = ""
        self._draw_rect = None

        self._ruler_h = _RulerBar(self, horizontal=True)
        self._ruler_v = _RulerBar(self, horizontal=False)
        self._ruler_h.hide()
        self._ruler_v.hide()
        self._rulers_on = False
        self._hist = []
        self._hist_idx = -1
        self._hist_timer = QTimer(self)
        self._hist_timer.setSingleShot(True)
        self._hist_timer.setInterval(400)
        self._hist_timer.timeout.connect(self._push_history)
        self._activated = None
        self._map_drag = None
        self._mid_drag = None
        self._nav_cache = None
        self._nav = MapFrameNav(self)
        self._map_nav_timer = QTimer(self)
        self._map_nav_timer.setSingleShot(True)
        self._map_nav_timer.setInterval(int(MAP_NAV_MS))
        self._map_nav_timer.timeout.connect(self._end_map_nav)
        self._map_done_timer = QTimer(self)
        self._map_done_timer.setSingleShot(True)
        self._map_done_timer.setInterval(int(MAP_NAV_SETTLE_MS))
        self._map_done_timer.timeout.connect(self._finish_map_nav_now)
        self._map_done_tries = 0
        self._elem_clip = None
        self._elem_pix = None
        self._elem_erase = None
        self._elem_snap_rect = None
        self._elem_item_rect = None
        self._elem_base = 1.0
        self._dragging = False
        self._elem_patch = None
        self._elem_patch_tried = False
        self._patch_seq = 0
        self._patch_snap = None
        self._patch_erase = None
        self._edit_erase = None
        self._elem_req_seq = 0
        self._elem_req_waiting = False
        self._elem_req_rect = None
        self._elem_pad = 0.0
        self._elem_topup_done = True
        self._ghost_pix = None

    @staticmethod
    def _workspace_color():
        try:
            from ggis.common.styling import icons as _icons
            from ggis.common.styling import themes as _themes
            return QColor(_themes.theme_color(
                "workspace", bool(_icons.is_dark())))
        except Exception:
            exc_note("_workspace_color @ ggis/ui/views/layout/canvas.py:2819")
            return QColor("#8A8F96")

    def retheme(self):
        try:
            self.setBackgroundBrush(QBrush(self._workspace_color()))
            self.viewport().update()
        except Exception:
            exc_note("retheme @ ggis/ui/views/layout/canvas.py:2833")
            pass

    def set_rulers(self, on):
        self._rulers_on = bool(on)
        for w in (self._ruler_h, self._ruler_v):
            try:
                w.setVisible(self._rulers_on)
            except Exception:
                exc_note("set_rulers @ ggis/ui/views/layout/canvas.py:2842")
                pass
        self._sync_rulers()

    def rulers_on(self):
        return bool(self._rulers_on)

    def _sync_rulers(self):
        self._sync_guides_span()
        if not self._rulers_on:
            return
        for w in (self._ruler_h, self._ruler_v):
            try:
                w.sync_geometry()
                w.update()
            except Exception:
                exc_note("_sync_rulers @ ggis/ui/views/layout/canvas.py:2864")
                pass

    def _refresh_rulers_marks(self, *_a):
        for w in (getattr(self, "_ruler_h", None),
                  getattr(self, "_ruler_v", None)):
            if w is None:
                continue
            try:
                w.update()
            except Exception:
                exc_note("_refresh_rulers_marks @ ggis/ui/views/layout/canvas.py:2883")
                pass

    def _sync_guides_span(self):
        try:
            guides = list(getattr(self._scene, "guides", None) or [])
        except Exception:
            exc_note("_sync_guides_span @ ggis/ui/views/layout/canvas.py:2900")
            return
        if not guides:
            return
        try:
            vp = self.viewport()
            tl = self.mapToScene(vp.rect().topLeft())
            br = self.mapToScene(vp.rect().bottomRight())
            x0, x1 = min(tl.x(), br.x()), max(tl.x(), br.x())
            y0, y1 = min(tl.y(), br.y()), max(tl.y(), br.y())
            dx, dy = (x1 - x0) * 0.5, (y1 - y0) * 0.5
            x0, y0, x1, y1 = x0 - dx, y0 - dy, x1 + dx, y1 + dy
            try:
                pw, ph = self._scene.layout.page_mm()
            except Exception:
                exc_note("_sync_guides_span @ ggis/ui/views/layout/canvas.py:2914")
                pw = ph = 0.0
            x0, y0 = min(x0, 0.0), min(y0, 0.0)
            x1, y1 = max(x1, float(pw)), max(y1, float(ph))
        except Exception:
            exc_note("_sync_guides_span @ ggis/ui/views/layout/canvas.py:2918")
            return
        for g in guides:
            try:
                g.set_span((x0, x1) if g.horizontal else (y0, y1))
            except Exception:
                exc_note("_sync_guides_span @ ggis/ui/views/layout/canvas.py:2923")
                pass

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self._sync_rulers()
        self._hist_timer.start()

    def add_guide(self, horizontal, pos_mm):
        g = self._scene.add_guide(horizontal, pos_mm)
        if g is None:
            return None
        if not self._guides_on():
            self.set_guides_visible(True)
            try:
                self.guidesShown.emit()
            except Exception:
                exc_note("add_guide @ ggis/ui/views/layout/canvas.py:2947")
                pass
        try:
            self._scene.update()
        except Exception:
            exc_note("add_guide @ ggis/ui/views/layout/canvas.py:2951")
            pass
        self._sync_guides_span()
        self._refresh_rulers_marks()
        return g

    def add_guide_at(self, horizontal, scene_pos=None, pos_mm=None):
        if pos_mm is None:
            if scene_pos is not None:
                try:
                    pos_mm = (float(scene_pos.y()) if horizontal
                              else float(scene_pos.x()))
                except Exception:
                    exc_note("add_guide_at @ ggis/ui/views/layout/canvas.py:2980")
                    pos_mm = None
        if pos_mm is None:
            try:
                c = self.mapToScene(self.viewport().rect().center())
                pos_mm = c.y() if horizontal else c.x()
            except Exception:
                exc_note("add_guide_at @ ggis/ui/views/layout/canvas.py:2986")
                try:
                    w_mm, h_mm = self._scene.layout.page_mm()
                except Exception:
                    exc_note("add_guide_at @ ggis/ui/views/layout/canvas.py:2989")
                    w_mm, h_mm = 100.0, 100.0
                pos_mm = (h_mm * 0.5) if horizontal else (w_mm * 0.5)
        g = SNAP_MM if SNAP_MM > 0 else 1.0
        val = round(float(pos_mm) / g) * g
        return self.add_guide(horizontal, val)

    def contextMenuEvent(self, e):
        if self.draw_kind():
            self.cancel_draw()
            e.accept()
            return
        if (self.sel_path_mode() and self._sel_mode == "poly"
                and self._sel_drag):
            self._apply_sel_path()
            e.accept()
            return
        try:
            self.contextMenuRequested.emit(e.globalPos())
        except Exception:
            exc_note("contextMenuEvent @ ggis/ui/views/layout/canvas.py:3019")
            pass
        e.accept()

    def _guides_on(self):
        return bool(getattr(self, "_guides_visible", False))

    def set_guides_visible(self, on):
        self._guides_visible = bool(on)
        self._scene.set_guides_visible(bool(on))

    def sync_frames(self):
        try:
            self._scene.sync_frames()
        except Exception:
            exc_note("sync_frames @ ggis/ui/views/layout/canvas.py:3038")
            pass

    def clear_guides(self):
        self._scene.clear_guides()

    def guides(self):
        return list(getattr(self._scene, "guides", []) or [])

    def set_margins_visible(self, on):
        self._scene.set_margins_visible(bool(on))

    def remove_guide(self, g):
        if g is None:
            return False
        sc = self._scene

        def _do():
            try:
                sc.removeItem(g)
            except Exception:
                exc_note("_do @ ggis/ui/views/layout/canvas.py:3064")
                pass
            try:
                sc.guides.remove(g)
            except Exception:
                exc_note("_do @ ggis/ui/views/layout/canvas.py:3068")
                pass
            self._refresh_rulers_marks()
            try:
                sc.update()
            except Exception:
                exc_note("_do @ ggis/ui/views/layout/canvas.py:3073")
                pass

        QTimer.singleShot(0, _do)
        return True

    def selected_items(self):
        out = []
        try:
            for f in self._scene.selectedItems():
                it = getattr(f, "item", None)
                if it is not None:
                    out.append(it)
        except Exception:
            exc_note("selected_items @ ggis/ui/views/layout/canvas.py:3090")
            pass
        return out

    def select_all(self):
        try:
            for f in self._scene.frames:
                f.setSelected(True)
            if self._scene.frames:
                self.itemPicked.emit(self._scene.frames[-1].item)
        except Exception:
            exc_note("select_all @ ggis/ui/views/layout/canvas.py:3101")
            pass

    def clear_selection(self):
        try:
            self._scene.clearSelection()
            self.itemPicked.emit(None)
        except Exception:
            exc_note("clear_selection @ ggis/ui/views/layout/canvas.py:3108")
            pass

    def delete_selected(self):
        items = self.selected_items()
        if not items:
            return
        QTimer.singleShot(0, lambda _lst=list(items):
                          self.deleteManyRequested.emit(_lst))

    def set_select_mode(self, mode):
        m = str(mode or "rect").lower()
        if m == "point" or m in SEL_PATH_MODES:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            m = "rect"
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self._sel_mode = m
        self._cancel_sel_path()

    def select_mode(self):
        return str(getattr(self, "_sel_mode", "rect"))

    def sel_path_mode(self):
        return self.select_mode() in SEL_PATH_MODES

    def begin_draw(self, kind):
        self._draw_kind = str(kind or "")
        self._draw_rect = None
        self._cancel_sel_path()
        try:
            self.setCursor(Qt.CursorShape.CrossCursor)
        except Exception:
            exc_note("begin_draw @ ggis/ui/views/layout/canvas.py:3172")
            pass
        return bool(self._draw_kind)

    def draw_kind(self):
        return str(getattr(self, "_draw_kind", "") or "")

    def cancel_draw(self):
        self._draw_kind = ""
        self._draw_rect = None
        try:
            self.unsetCursor()
        except Exception:
            exc_note("cancel_draw @ ggis/ui/views/layout/canvas.py:3186")
            pass
        try:
            self.viewport().update()
        except Exception:
            exc_note("cancel_draw @ ggis/ui/views/layout/canvas.py:3190")
            pass

    def _finish_draw(self):
        r = self._draw_rect
        kind = self.draw_kind()
        if r is None or not kind:
            self.cancel_draw()
            return
        r = QRectF(r).normalized()
        if r.width() < 3.0 or r.height() < 3.0:
            self.cancel_draw()
            return
        try:
            self.rectDrawn.emit(r)
        except Exception:
            _log.exception("布局：画框插入失败（kind=%s）", kind)
        finally:
            self.cancel_draw()

    @staticmethod
    def _ev_pos(e):
        try:
            return e.position().toPoint()
        except Exception:
            exc_note("_ev_pos @ ggis/ui/views/layout/canvas.py:3226")
            return e.pos()

    def cancel_sel_path(self):
        self._cancel_sel_path()

    def _cancel_sel_path(self):
        self._sel_pts = []
        self._sel_drag = False
        self._sel_hover = None
        try:
            self.viewport().update()
        except Exception:
            exc_note("_cancel_sel_path @ ggis/ui/views/layout/canvas.py:3239")
            pass

    def _apply_sel_path(self):
        pts = list(self._sel_pts or [])
        mode = self.select_mode()
        self._cancel_sel_path()
        path = QPainterPath()
        try:
            if mode in ("poly", "lasso"):
                if len(pts) < 3:
                    return
                path.addPolygon(QPolygonF(pts))
                path.closeSubpath()
            elif mode == "circle":
                if len(pts) < 2:
                    return
                r = QRectF(pts[0], pts[-1]).normalized()
                if r.width() < 0.5 or r.height() < 0.5:
                    return
                path.addEllipse(r)
            elif mode == "line":
                if len(pts) < 2:
                    return
                lp = QPainterPath(pts[0])
                lp.lineTo(pts[-1])
                st = QPainterPathStroker()
                st.setWidth(max(0.4, 6.0 / max(1e-6, float(self._zoom))))
                path = st.createStroke(lp)
            else:
                return
            self._scene.setSelectionArea(path)
        except Exception:
            _log.exception("布局：路径选择失败（mode=%s）", mode)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        dr = self._draw_rect
        if dr is not None and self.draw_kind():
            try:
                pen = QPen(QColor(SEL_PREVIEW_COLOR))
                pen.setCosmetic(True)
                pen.setWidthF(1.4)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                fill = QColor(SEL_PREVIEW_COLOR)
                fill.setAlpha(28)
                painter.setBrush(QBrush(fill))
                painter.drawRect(QRectF(dr).normalized())
                painter.setBrush(Qt.BrushStyle.NoBrush)
            except Exception:
                exc_note("drawForeground @ ggis/ui/views/layout/canvas.py:3298")
                pass
            return
        pts = list(self._sel_pts or [])
        if not pts or not self._sel_drag:
            return
        try:
            pen = QPen(QColor(SEL_PREVIEW_COLOR))
            pen.setCosmetic(True)
            pen.setWidthF(1.4)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            mode = self.select_mode()
            if mode == "circle" and len(pts) >= 2:
                painter.drawEllipse(QRectF(pts[0], pts[-1]).normalized())
            elif mode == "line" and len(pts) >= 2:
                painter.drawLine(pts[0], pts[-1])
            elif mode == "lasso" and len(pts) >= 2:
                painter.drawPolyline(QPolygonF(pts))
            elif mode == "poly":
                for i in range(1, len(pts)):
                    painter.drawLine(pts[i - 1], pts[i])
                hv = getattr(self, "_sel_hover", None)
                if hv is not None:
                    painter.drawLine(pts[-1], hv)
                if len(pts) >= 3:
                    painter.drawLine(pts[-1], pts[0])
                painter.drawEllipse(pts[0], 1.0, 1.0)
        except Exception:
            exc_note("drawForeground @ ggis/ui/views/layout/canvas.py:3327")
            pass

    def select_by_type(self, type_name, clear=True):
        t = str(type_name or "")
        if not t:
            return 0
        hit = []
        for f in list(getattr(self._scene, "frames", None) or []):
            it = getattr(f, "item", None)
            if it is None:
                continue
            if str(getattr(it, "type_name", "")) == t:
                hit.append(f)
        if not hit:
            return 0
        if clear:
            try:
                self._scene.clearSelection()
            except Exception:
                exc_note("select_by_type @ ggis/ui/views/layout/canvas.py:3355")
                pass
        for f in hit:
            try:
                f.setSelected(True)
            except Exception:
                exc_note("select_by_type @ ggis/ui/views/layout/canvas.py:3360")
                pass
        return len(hit)

    def select_by_location(self, rel="intersect"):
        base = self.selected_items()
        if not base:
            return 0
        path = QPainterPath()
        for it in base:
            f = None
            try:
                f = self._scene.frame_of(it)
            except Exception:
                exc_note("select_by_location @ ggis/ui/views/layout/canvas.py:3380")
                f = None
            if f is None:
                continue
            try:
                path.addRect(QRectF(f.sceneBoundingRect()))
            except Exception:
                exc_note("select_by_location @ ggis/ui/views/layout/canvas.py:3386")
                pass
        if path.isEmpty():
            return 0
        before = len(self.selected_items())
        try:
            self._scene.setSelectionArea(
                path, Qt.ItemSelectionOperation.AddToSelection,
                Qt.ItemSelectionMode.ContainsItemShape
                if str(rel) == "within"
                else Qt.ItemSelectionMode.IntersectsItemShape)
        except Exception:
            _log.exception("布局：按位置选择失败")
            return 0
        return len(self.selected_items()) - before

    def layout_scene(self):
        return self._scene

    def _on_sel(self, frame):
        self.itemPicked.emit(getattr(frame, "item", None))

    def begin_fast(self):
        self._fast = True
        self._fast_timer.start()

    def _end_fast(self):
        self._fast = False
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._scene is not None:
            self._scene.set_backdrop_smooth(True)
            try:
                self._scene.sync_backdrop_detail()
            except Exception:
                exc_note("_end_fast @ ggis/ui/views/layout/canvas.py:3439")
                pass
        self.viewport().update()

    def zoom(self):
        return self._zoom

    def set_zoom(self, z, anchor=None):
        z = max(0.05, min(24.0, float(z)))
        if abs(z - self._zoom) < 1e-9:
            return
        vp = self.viewport()
        if anchor is None:
            try:
                p = vp.mapFromGlobal(QCursor.pos())
                anchor = (p if vp.rect().contains(p) else vp.rect().center())
            except Exception:
                exc_note("set_zoom @ ggis/ui/views/layout/canvas.py:3479")
                anchor = vp.rect().center()
        anchor = QPointF(anchor)
        self.begin_fast()
        before = self.mapToScene(QPoint(int(round(anchor.x())),
                                        int(round(anchor.y()))))
        self._zoom = z
        self.resetTransform()
        self.scale(z, z)
        for _ in range(2):
            after = self.viewportTransform().map(before)
            dx = after.x() - anchor.x()
            dy = after.y() - anchor.y()
            if abs(dx) < 0.5 and abs(dy) < 0.5:
                break
            hb = self.horizontalScrollBar()
            vb = self.verticalScrollBar()
            hb.setValue(hb.value() + int(round(dx)))
            vb.setValue(vb.value() + int(round(dy)))
        self._scene.set_view_scale(z)
        self._sync_rulers()
        self._hist_timer.start()

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.25)

    def set_pan_mode(self, on):
        try:
            self.setDragMode(
                QGraphicsView.DragMode.ScrollHandDrag if on
                else QGraphicsView.DragMode.NoDrag)
        except Exception:
            exc_note("set_pan_mode @ ggis/ui/views/layout/canvas.py:3520")
            pass

    def pan_mode(self):
        try:
            return (self.dragMode()
                    == QGraphicsView.DragMode.ScrollHandDrag)
        except Exception:
            exc_note("pan_mode @ ggis/ui/views/layout/canvas.py:3527")
            return False

    def fit_page(self):
        self.begin_fast()
        self.fitInView(self._scene.sceneRect(),
                       Qt.AspectRatioMode.KeepAspectRatio)
        t = self.transform()
        self._zoom = max(0.05, t.m11())
        self._scene.set_view_scale(self._zoom)
        self._sync_rulers()

    def zoom_actual(self):
        try:
            dpi = float(self.logicalDpiX() or 96.0)
        except Exception:
            exc_note("zoom_actual @ ggis/ui/views/layout/canvas.py:3551")
            dpi = 96.0
        self.set_zoom(max(0.05, dpi / 25.4), anchor=None)

    def _view_state(self):
        try:
            return (float(self._zoom),
                    int(self.horizontalScrollBar().value()),
                    int(self.verticalScrollBar().value()))
        except Exception:
            exc_note("_view_state @ ggis/ui/views/layout/canvas.py:3561")
            return None

    def _push_history(self):
        st = self._view_state()
        if st is None:
            return
        if self._hist and self._hist_idx >= 0:
            try:
                if self._hist[self._hist_idx] == st:
                    return
            except Exception:
                exc_note("_push_history @ ggis/ui/views/layout/canvas.py:3573")
                pass
        try:
            del self._hist[self._hist_idx + 1:]
        except Exception:
            exc_note("_push_history @ ggis/ui/views/layout/canvas.py:3578")
            self._hist = []
        self._hist.append(st)
        if len(self._hist) > 40:
            self._hist.pop(0)
        self._hist_idx = len(self._hist) - 1
        self._note_history()

    def _apply_hist(self, st):
        z, h, v = st
        self._zoom = max(0.05, min(24.0, float(z)))
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self._scene.set_view_scale(self._zoom)
        try:
            self.horizontalScrollBar().setValue(int(h))
            self.verticalScrollBar().setValue(int(v))
        except Exception:
            exc_note("_apply_hist @ ggis/ui/views/layout/canvas.py:3596")
            pass
        self._sync_rulers()
        self.viewport().update()

    def can_prev_view(self):
        return self._hist_idx > 0

    def can_next_view(self):
        return 0 <= self._hist_idx < len(self._hist) - 1

    def prev_view(self):
        if not self.can_prev_view():
            return
        self._hist_idx -= 1
        self._apply_hist(self._hist[self._hist_idx])
        self._note_history()

    def next_view(self):
        if not self.can_next_view():
            return
        self._hist_idx += 1
        self._apply_hist(self._hist[self._hist_idx])
        self._note_history()

    def _note_history(self):
        try:
            self.viewHistoryChanged.emit()
        except Exception:
            exc_note("_note_history @ ggis/ui/views/layout/canvas.py:3626")
            pass

    def set_map_activate(self, on):
        from ggis.core.model import layout_items as _LI
        it = self._activated if on else None
        if on:
            sel = self.selected_items()
            it = next((x for x in sel if isinstance(x, _LI.MapFrame)), None)
            if it is None:
                try:
                    for it2 in self._scene.layout.items_in_draw_order():
                        if isinstance(it2, _LI.MapFrame):
                            it = it2
                            break
                except Exception:
                    exc_note("set_map_activate @ ggis/ui/views/layout/canvas.py:3652")
                    it = None
        self._activated = it if on else None
        self._nav_cache = None
        try:
            for f in self._scene.frames:
                f.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                          not bool(on))
        except Exception:
            exc_note("set_map_activate @ ggis/ui/views/layout/canvas.py:3663")
            pass
        try:
            self.setCursor(Qt.CursorShape.OpenHandCursor if on
                           else Qt.CursorShape.ArrowCursor)
        except Exception:
            exc_note("set_map_activate @ ggis/ui/views/layout/canvas.py:3668")
            pass
        try:
            self._scene.activated = self._activated
            for f in list(self._scene.frames or []):
                f.update()
        except Exception:
            exc_note("set_map_activate @ ggis/ui/views/layout/canvas.py:3683")
            pass
        try:
            if self._activated is not None:
                self._nav.begin(self._activated)
            else:
                self._map_nav_timer.stop()
                try:
                    self._map_done_timer.stop()
                except Exception:
                    exc_note("set_map_activate @ ggis/ui/views/layout/canvas.py:3695")
                    pass
                self._nav.close()
        except Exception:
            exc_note("set_map_activate @ ggis/ui/views/layout/canvas.py:3698")
            pass
        return self._activated

    def activated_frame(self):
        return self._activated

    def _elem_overlay_begin(self, frame):
        if not isinstance(frame, ItemFrame):
            return False
        self._dragging = True
        return self._grab_element_snapshot(frame)

    def _elem_overlay_move(self, frame):
        if not isinstance(frame, ItemFrame):
            return
        self._move_element_overlay(frame)

    def _elem_overlay_end(self):
        self._dragging = False
        self._clear_item_hover()
        self._drop_element_overlay()

    def _elem_overlay_end_keep(self, *_a):
        self._dragging = False
        self._clear_item_hover()

    def _clear_item_hover(self):
        try:
            sc = self._scene
            if sc is None:
                return
            for f in list(getattr(sc, "frames", []) or []):
                if getattr(f, "_hover", False):
                    f._hover = False
                    f.update()
        except Exception:
            exc_note("_clear_item_hover @ ggis/ui/views/layout/canvas.py:3765")
            pass

    def _grab_element_snapshot(self, frame):
        self._drop_element_overlay()
        sc = self._scene
        if frame is None or sc is None or sc.layout is None:
            return False
        try:
            r = QRectF(frame.item.rect_mm)
            if r.width() <= 0 or r.height() <= 0:
                return False
            pad = self._overlay_pad_mm(frame.item)
            self._elem_pad = float(pad)
            self._elem_topup_done = False
            sub = self._element_bitmap(frame.item, r, pad=pad)
            box = QRectF(-pad, -pad, r.width() + 2.0 * pad,
                         r.height() + 2.0 * pad)
            clip = QGraphicsRectItem(box)
            clip.setPen(QPen(Qt.PenStyle.NoPen))
            clip.setBrush(Qt.BrushStyle.NoBrush)
            clip.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            clip.setZValue(999)
            clip.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            clip.setPos(r.topLeft())
            k = 1.0
            pix = None
            if sub is not None and not sub.isNull():
                pix = QGraphicsPixmapItem(sub, clip)
                pix.setTransformationMode(
                    Qt.TransformationMode.SmoothTransformation)
                k = max(1e-9, float(box.width())) / max(1, sub.width())
                pix.setTransform(QTransform().scale(k, k))
                pix.setPos(QPointF(-pad, -pad))
            sc.addItem(clip)
            self._elem_clip = clip
            self._elem_pix = pix
            erase = QGraphicsPathItem()
            erase.setPen(QPen(Qt.PenStyle.NoPen))
            if self._is_opaque_item(frame.item):
                erase.setBrush(QBrush(QColor("#FFFFFF")))
            else:
                erase.setBrush(Qt.BrushStyle.NoBrush)
            erase.setZValue(900)
            erase.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            sc.addItem(erase)
            self._elem_erase = erase
            self._elem_snap_rect = QRectF(
                QRectF(r).adjusted(-pad, -pad, pad, pad)) if pad > 0 \
                else QRectF(r)
            self._elem_item_rect = QRectF(r)
            self._elem_base = float(k)
            self._elem_patch = None
            self._elem_patch_tried = False
            self._elem_last_scale = None
            self._elem_erase_rect = None
            self._elem_bmp_rect = QRectF(r)
            self._elem_bmp_ms = (time.monotonic() * 1000.0
                                 if pix is not None else 0.0)
            return True
        except Exception:
            _log.exception("布局：元素内容快照失败")
            self._drop_element_overlay()
            return False

    def _show_content_ghost(self, frame):
        sc = self._scene
        if frame is None or sc is None or sc.layout is None:
            return False
        try:
            old = self._ghost_pix
            self._ghost_pix = None
            if old is not None:
                sc.removeItem(old)
                QTimer.singleShot(0, lambda _k=old: None)
        except Exception:
            exc_note("_show_content_ghost @ ggis/ui/views/layout/canvas.py:3910")
            pass
        try:
            r = QRectF(frame.item.rect_mm)
            if r.width() <= 0 or r.height() <= 0:
                return False
            pad = self._overlay_pad_mm(frame.item)
            sub = self._element_bitmap(frame.item, r, pad=pad, wait_ms=150.0)
            if sub is None or sub.isNull():
                return False
            box = QRectF(-pad, -pad, r.width() + 2.0 * pad,
                         r.height() + 2.0 * pad)
            clip = QGraphicsRectItem(box)
            clip.setPen(QPen(Qt.PenStyle.NoPen))
            clip.setBrush(Qt.BrushStyle.NoBrush)
            clip.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            clip.setZValue(999)
            clip.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            clip.setPos(r.topLeft())
            pix = QGraphicsPixmapItem(sub, clip)
            pix.setTransformationMode(
                Qt.TransformationMode.SmoothTransformation)
            k = max(1e-9, float(box.width())) / max(1, sub.width())
            pix.setTransform(QTransform().scale(k, k))
            pix.setPos(QPointF(-pad, -pad))
            sc.addItem(clip)
            self._ghost_pix = clip
            return True
        except Exception:
            _log.exception("布局：就地编辑后压住新内容失败")
            return False

    def _is_opaque_item(self, item):
        try:
            from ggis.core.model import layout_items as _LI
            return isinstance(item, (_LI.MapFrame, _LI.ImageItem))
        except Exception:
            exc_note("_is_opaque_item @ ggis/ui/views/layout/canvas.py:3953")
            return True

    def _overlay_pad_mm(self, item):
        try:
            from ggis.core.model import layout_items as _LI
        except Exception:
            exc_note("_overlay_pad_mm @ ggis/ui/views/layout/canvas.py:3986")
            return 0.0
        base = 1.0
        ok = isinstance(item, (_LI.GridFrame, _LI.ScaleBar))
        if not ok:
            ok = (isinstance(item, _LI.MapFrame)
                  and getattr(item, "grid", None) is not None)
        if not ok:
            return base
        try:
            r = QRectF(item.rect_mm)
            base = max(6.0, min(24.0, 0.10 * max(r.width(), r.height())))
            if isinstance(item, _LI.MapFrame):
                return max(base, 10.0)
            return base
        except Exception:
            exc_note("_overlay_pad_mm @ ggis/ui/views/layout/canvas.py:4007")
            return 6.0

    def _element_bitmap(self, item, r, budget_ms=None, slice_rect=None,
                        pad=None, wait_ms=None):
        sc = self._scene
        k_px = self._view_px()
        pad = max(0.0, float(self._elem_pad if pad is None else pad))
        w = int(max(24, min(ELEM_OVL_MAX_PX,
                            round((r.width() + 2.0 * pad) * k_px))))
        budget = float(ELEM_OVL_MAX_MS if budget_ms is None else budget_ms)
        wait = float(150.0 if wait_ms is None else wait_ms)
        try:
            if not sc._bd.wait_idle(max(10.0, min(wait, budget))):
                return None
        except Exception:
            exc_note("_element_bitmap @ ggis/ui/views/layout/canvas.py:4049")
            pass
        t0 = time.perf_counter()
        try:
            img = EX.preview_item(sc.layout, item, sc.project, w,
                                  background="#00000000", pad_mm=pad)
            dt = (time.perf_counter() - t0) * 1000.0
            if img is not None and not img.isNull():
                if dt > budget:
                    _log.warning("布局：元素真渲染 %.0f ms（超 %.0f ms）⇒ 退回底图切片",
                                 dt, budget)
                else:
                    return QPixmap.fromImage(img)
        except Exception:
            _log.exception("布局：元素浮层渲染失败（退回底图切片）")
        return self._backdrop_slice(slice_rect if slice_rect is not None else r)

    def _view_px(self):
        try:
            k = float(self.transform().m11())
        except Exception:
            exc_note("_view_px @ ggis/ui/views/layout/canvas.py:4083")
            k = 1.0
        return max(1e-6, k * self._dpr())

    def _dpr(self):
        try:
            return max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            exc_note("_dpr @ ggis/ui/views/layout/canvas.py:4091")
            return 1.0

    def _backdrop_slice(self, r):
        sc = self._scene
        pm = sc.backdrop_pixmap() if sc is not None else None
        if pm is None or pm.isNull():
            return None
        try:
            w_mm, h_mm = sc.layout.page_mm()
            sx = pm.width() / max(1e-9, float(w_mm))
            sy = pm.height() / max(1e-9, float(h_mm))
            sub = pm.copy(int(round(r.x() * sx)), int(round(r.y() * sy)),
                          max(1, int(round(r.width() * sx))),
                          max(1, int(round(r.height() * sy))))
            if sub.isNull():
                return None
            try:
                want = int(round(float(r.width()) * self._view_px()))
            except Exception:
                exc_note("_backdrop_slice @ ggis/ui/views/layout/canvas.py:4119")
                want = int(SNAP_MAX_PX)
            cap = int(max(int(SNAP_MAX_PX), min(ELEM_OVL_MAX_PX, want)))
            mx = max(int(sub.width()), int(sub.height()))
            if mx > cap:
                _r = float(cap) / float(mx)
                sub = sub.scaled(
                    max(1, int(round(sub.width() * _r))),
                    max(1, int(round(sub.height() * _r))),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
            return sub
        except Exception:
            _log.exception("布局：底图切片失败")
            return None

    def _move_element_overlay(self, frame):
        c = self._elem_clip
        if c is None or frame is None:
            return
        try:
            r = QRectF(frame.item.rect_mm)
            snap = self._elem_snap_rect
            px = self._elem_pix
            bmp_rect = getattr(self, "_elem_bmp_rect", None)
            size_changed = (bmp_rect is None
                            or abs(r.width() - bmp_rect.width()) > 1e-9
                            or abs(r.height() - bmp_rect.height()) > 1e-9)
            if size_changed:
                self._request_elem_bitmap(frame.item, r, self._elem_pad)
                self._elem_topup_done = False
            elif px is None:
                if self._is_opaque_item(frame.item):
                    self._topup_elem_slice(frame.item, r)
                if not getattr(self, "_elem_topup_done", True):
                    self._elem_topup_done = True
                    self._request_elem_bitmap(frame.item, r, self._elem_pad)
            sx = sy = 1.0
            if (bmp_rect is not None and bmp_rect.width() > 1e-6
                    and bmp_rect.height() > 1e-6):
                sx = max(0.02, r.width() / bmp_rect.width())
                sy = max(0.02, r.height() / bmp_rect.height())
            box = QRectF(-float(self._elem_pad), -float(self._elem_pad),
                         max(0.01, r.width()) + 2.0 * float(self._elem_pad),
                         max(0.01, r.height()) + 2.0 * float(self._elem_pad))
            changed = False
            if c.rect() != box:
                c.setRect(box)
                changed = True
            if c.pos() != r.topLeft():
                c.setPos(r.topLeft())
                changed = True
            p = self._elem_pix
            if p is not None:
                base = float(getattr(self, "_elem_base", 1.0) or 1.0)
                want = (base * sx, base * sy)
                if getattr(self, "_elem_last_scale", None) != want:
                    p.setTransform(QTransform().scale(want[0], want[1]))
                    self._elem_last_scale = want
                    changed = True
            if changed:
                c.update()
            e = self._elem_erase
            if e is not None and snap is not None:
                if getattr(self, "_elem_erase_rect", None) != snap:
                    whole = QPainterPath()
                    whole.addRect(snap)
                    e.setPath(whole)
                    self._elem_erase_rect = QRectF(snap)
                    e.update()
                iref = getattr(self, "_elem_item_rect", None) or snap
                if (not getattr(self, "_elem_patch_tried", True)
                        and self._elem_patch is None
                        and (abs(r.x() - iref.x()) > 1e-9
                             or abs(r.y() - iref.y()) > 1e-9
                             or abs(r.width() - iref.width()) > 1e-9
                             or abs(r.height() - iref.height()) > 1e-9)):
                    self._elem_patch_tried = True
                    self._set_erase_patch(frame.item, snap)
        except Exception:
            exc_note("_move_element_overlay @ ggis/ui/views/layout/canvas.py:4246")
            pass

    def _set_erase_patch(self, item, snap, erase=None):
        e = self._elem_erase if erase is None else erase
        sc = self._scene
        if e is None or sc is None or sc.layout is None or snap is None:
            return False
        self._patch_erase = e
        w = 0
        dpi = 0.0
        try:
            base_w = int(getattr(sc, "_frame_w", 0) or 0)
            w_mm, _h_mm = sc.layout.page_mm()
            if base_w > 0 and w_mm > 0:
                dpi = base_w / float(w_mm) * 25.4
                w = int(max(16, round(snap.width() * dpi / 25.4)))
        except Exception:
            exc_note("_set_erase_patch @ ggis/ui/views/layout/canvas.py:4283")
            w = 0
            dpi = 0.0
        if w <= 0:
            try:
                k_px = max(1e-6, float(self.transform().m11()))
            except Exception:
                exc_note("_set_erase_patch @ ggis/ui/views/layout/canvas.py:4289")
                k_px = 1.0
            w = int(max(16, min(int(SNAP_MAX_PX),
                                round(snap.width() * k_px))))
        self._patch_seq += 1
        self._patch_snap = QRectF(snap)
        try:
            frozen = EX.freeze_snapshot(sc.layout, sc.project)
        except Exception:
            _log.exception("布局：补丁快照失败 ⇒ 退回白底")
            _fallback_white(e)
            return False
        try:
            ok = bool(sc._bd.request_patch(self._patch_seq, frozen[0], frozen[1],
                                           QRectF(snap), item, w, (dpi or None)))
        except Exception:
            _log.exception("布局：补丁投递失败 ⇒ 退回白底")
            _fallback_white(e)
            return False
        if not ok:
            _log.warning("布局：补丁未投递（后台线程忙）⇒ 退回白底")
            _fallback_white(e)
            return False
        return True

    def _apply_erase_patch(self, img, seq):
        e = getattr(self, "_patch_erase", None) or self._elem_erase
        snap = self._patch_snap
        if e is None or snap is None:
            return
        if int(seq) != int(self._patch_seq):
            return
        try:
            pm = QPixmap.fromImage(img)
            if pm.isNull():
                return
            try:
                want = int(round(float(snap.width()) * self._view_px()))
                if want > 0 and pm.width() > int(want * 1.12):
                    _pm2 = pm.scaled(
                        want,
                        max(1, int(round(pm.height() * want / pm.width()))),
                        Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)
                    if not _pm2.isNull():
                        pm = _pm2
            except Exception:
                exc_note("_apply_erase_patch @ ggis/ui/views/layout/canvas.py:4352")
                pass
            br = QBrush(pm)
            br.setTransform(QTransform()
                            .translate(snap.x(), snap.y())
                            .scale(snap.width() / max(1, pm.width()),
                                   snap.height() / max(1, pm.height())))
            e.setBrush(br)
            self._elem_patch = pm
            e.update()
        except Exception:
            _log.exception("布局：设置原位置背景补丁失败")

    def _topup_elem_slice(self, item, r):
        c = self._elem_clip
        if c is None or item is None:
            return False
        try:
            pad = float(getattr(self, "_elem_pad", 0.0) or 0.0)
            box = QRectF(-pad, -pad, max(0.01, r.width()) + 2.0 * pad,
                         max(0.01, r.height()) + 2.0 * pad)
            sub = self._backdrop_slice(
                QRectF(r).adjusted(-pad, -pad, pad, pad))
            if sub is None or sub.isNull():
                return False
            self._elem_pix = self._set_overlay_pixmap(sub)
            self._elem_base = float(box.width()) / max(1, sub.width())
            self._elem_last_scale = None
            self._elem_bmp_rect = QRectF(r)
            self._elem_bmp_ms = time.monotonic() * 1000.0
            c.update()
            return True
        except Exception:
            _log.exception("布局：元素切片兜底失败（保持现状）")
            return False

    def _request_elem_bitmap(self, item, r, pad=0.0):
        sc = self._scene
        if sc is None or sc.layout is None or item is None:
            return False
        if bool(getattr(self, "_elem_req_waiting", False)):
            return False
        k_px = self._view_px()
        pad = max(0.0, float(pad or 0.0))
        w = int(max(24, min(ELEM_OVL_MAX_PX,
                            round((r.width() + 2.0 * pad) * k_px))))
        try:
            frozen = EX.freeze_snapshot(sc.layout, sc.project)
        except Exception:
            _log.exception("布局：元素位图快照失败（这一帧不投）")
            return False
        self._elem_req_seq += 1
        try:
            ok = bool(sc._bd.request_elem(self._elem_req_seq, frozen[0],
                                          frozen[1], item, w, pad))
        except Exception:
            _log.exception("布局：元素位图投递失败")
            ok = False
        if ok:
            self._elem_req_waiting = True
            self._elem_req_rect = QRectF(r)
        return ok

    def _apply_elem_bitmap(self, img, seq):
        if int(seq) != int(getattr(self, "_elem_req_seq", 0)):
            return
        self._elem_req_waiting = False
        c = self._elem_clip
        if c is None:
            return
        try:
            pm = QPixmap.fromImage(img)
            if pm.isNull():
                return
            self._elem_pix = self._set_overlay_pixmap(pm)
            pad = float(getattr(self, "_elem_pad", 0.0) or 0.0)
            rr = getattr(self, "_elem_req_rect", None)
            base_w = (float(rr.width()) + 2.0 * pad) if rr is not None else 0.0
            if base_w <= 1e-9:
                base_w = float(pm.width()) / max(1e-9, self._view_px())
            self._elem_base = base_w / max(1, pm.width())
            self._elem_last_scale = None
            self._elem_bmp_rect = QRectF(rr) if rr is not None else None
            self._elem_bmp_ms = time.monotonic() * 1000.0
            try:
                c.update()
            except Exception:
                exc_note("_apply_elem_bitmap @ ggis/ui/views/layout/canvas.py:4465")
                pass
        except Exception:
            _log.exception("布局：换上元素位图失败")

    def _set_overlay_pixmap(self, pm):
        c = self._elem_clip
        px = self._elem_pix
        if c is None:
            return px
        if px is None:
            px = QGraphicsPixmapItem(pm, c)
            px.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            px.setPos(QPointF(-float(self._elem_pad or 0.0),
                              -float(self._elem_pad or 0.0)))
            self._elem_pix = px
        else:
            px.setPixmap(pm)
        return px

    def _drop_element_overlay(self):
        c = self._elem_clip
        e = self._elem_erase
        g = self._ghost_pix
        if c is None and e is None and g is None:
            return
        for obj in (c, e, g):
            if obj is None:
                continue
            try:
                self._scene.removeItem(obj)
            except Exception:
                exc_note("_drop_element_overlay @ ggis/ui/views/layout/canvas.py:4498")
                pass
            QTimer.singleShot(0, lambda _k=obj: None)
        self._elem_clip = None
        self._elem_pix = None
        self._elem_erase = None
        self._elem_snap_rect = None
        self._elem_patch = None
        self._elem_patch_tried = False
        self._elem_last_scale = None
        self._patch_seq += 1
        self._patch_snap = None
        self._patch_erase = None
        self._elem_pad = 0.0
        self._ghost_pix = None
        self._elem_req_seq += 1
        self._elem_req_waiting = False
        self._elem_req_rect = None
        self._elem_erase_rect = None
        self._elem_bmp_rect = None
        self._elem_bmp_ms = 0.0
        self._elem_topup_done = True
        try:
            self._scene.update()
        except Exception:
            exc_note("_drop_element_overlay @ ggis/ui/views/layout/canvas.py:4526")
            pass

    def _drop_map_overlay(self):
        try:
            nav = self._nav
            if nav.can_drop():
                nav.drop_layer()
                self._nav_settling = False
        except Exception:
            _log.exception("布局：收掉地图框帧层失败")

    def _force_drop_map_overlay(self):
        try:
            nav = self._nav
            if nav.item is not None and nav.layer is not None \
                    and not nav.can_drop():
                _log.info("布局：地图框帧层没对上当前视野 ⇒ 收掉它，由底图接管")
                nav.drop_layer()
                self._nav_settling = False
        except Exception:
            _log.exception("布局：强制收地图框帧层失败")

    def _nav_active(self):
        try:
            return bool(self._nav.active())
        except Exception:
            exc_note("_nav_active @ ggis/ui/views/layout/canvas.py:4585")
            return False

    def _map_nav_touch(self):
        self._nav_settling = False

        try:
            self._map_done_timer.stop()
        except Exception:
            exc_note("_map_nav_touch @ ggis/ui/views/layout/canvas.py:4606")
            pass
        try:
            self.begin_fast()
        except Exception:
            exc_note("_map_nav_touch @ ggis/ui/views/layout/canvas.py:4610")
            pass
        try:
            self._map_nav_timer.start()
        except Exception:
            exc_note("_map_nav_touch @ ggis/ui/views/layout/canvas.py:4614")
            pass

    def _end_map_nav(self):
        try:
            self._nav.end()
        except Exception:
            exc_note("_end_map_nav @ ggis/ui/views/layout/canvas.py:4639")
            pass
        self._nav_settling = True
        try:
            self._nav.kick(force=True)
        except Exception:
            exc_note("_end_map_nav @ ggis/ui/views/layout/canvas.py:4646")
            pass
        try:
            QTimer.singleShot(
                int(MAP_NAV_SETTLE_MS) * int(MAP_NAV_SETTLE_TRIES) + 400,
                self._force_drop_map_overlay)
        except Exception:
            exc_note("_end_map_nav @ ggis/ui/views/layout/canvas.py:4654")
            pass
        try:
            self._map_done_tries = 0
            self._map_done_timer.start()
        except Exception:
            exc_note("_end_map_nav @ ggis/ui/views/layout/canvas.py:4660")
            self._finish_map_nav_now()

    def _finish_map_nav_now(self):
        nav = self._nav
        tries = int(getattr(self, "_map_done_tries", 0)) + 1
        self._map_done_tries = tries
        try:
            if (nav.item is not None and nav.layer is not None
                    and not nav.can_drop()
                    and tries < int(MAP_NAV_SETTLE_TRIES)):
                self._map_done_timer.start()
                return
        except Exception:
            exc_note("_finish_map_nav_now @ ggis/ui/views/layout/canvas.py:4679")
            pass
        try:
            self._end_fast()
        except Exception:
            exc_note("_finish_map_nav_now @ ggis/ui/views/layout/canvas.py:4683")
            pass
        pending = False
        try:
            sc = self._scene
            w = int(getattr(sc, "_frame_w", 0) or 0) if sc is not None else 0
            if sc is not None and w > 0:
                pending = bool(sc.kick_map_frames(w))
                if pending:
                    sc._mapr_dirty = True
                    sc._mapr_wait.start()
        except Exception:
            exc_note("_finish_map_nav_now @ ggis/ui/views/layout/canvas.py:4694")
            pending = False
        if pending:
            return
        try:
            self._scene.notify_changed()
        except Exception:
            exc_note("_finish_map_nav_now @ ggis/ui/views/layout/canvas.py:4700")
            pass

    def _nav_base_extent(self, it):
        try:
            cur = tuple(float(x) for x in (it.extent or []))
        except Exception:
            exc_note("_nav_base_extent @ ggis/ui/views/layout/canvas.py:4727")
            cur = ()
        c = getattr(self, "_nav_cache", None)
        if (c is not None and c.get("it") is it
                and c.get("mode") == str(getattr(it, "mode", ""))
                and c.get("written") == cur):
            return c.get("ext")
        ext = None
        try:
            ctx = None
            try:
                from ggis.ui.views.layout import exporter as _EX
                ctx = _EX._prepare(self._scene.layout, self._scene.project,
                                   float(self._scene.layout.dpi or 300))
            except Exception:
                exc_note("_nav_base_extent @ ggis/ui/views/layout/canvas.py:4741")
                ctx = None
            ext = it.compute_extent(self._scene.project, ctx)
        except Exception:
            exc_note("_nav_base_extent @ ggis/ui/views/layout/canvas.py:4744")
            ext = None
        if ext is None or ext.is_empty():
            return None
        self._nav_cache = {"it": it, "ext": ext,
                           "mode": str(getattr(it, "mode", "")),
                           "written": cur}
        return ext

    def _nav_write_extent(self, it, ext):
        it.mode = "extent"
        it.extent = [ext.xmin, ext.ymin, ext.xmax, ext.ymax]
        try:
            self._nav_cache = {
                "it": it, "ext": ext, "mode": "extent",
                "written": tuple(float(x) for x in it.extent)}
        except Exception:
            exc_note("_nav_write_extent @ ggis/ui/views/layout/canvas.py:4761")
            self._nav_cache = None

    def _map_pan(self, dx_mm, dy_mm):
        nav = self._nav
        if nav.item is None:
            return False
        ok = nav.pan(dx_mm, dy_mm)
        if ok:
            self._map_nav_touch()
        return ok

    def _map_zoom(self, factor, anchor_scene=None):
        it = self._nav.item
        if it is None:
            return False
        try:
            r = it.rect_mm
            if anchor_scene is None:
                ax, ay = 0.5, 0.5
            else:
                ax = (anchor_scene.x() - r.x()) / max(1e-6, float(r.width()))
                ay = (anchor_scene.y() - r.y()) / max(1e-6, float(r.height()))
        except Exception:
            exc_note("_map_zoom @ ggis/ui/views/layout/canvas.py:4795")
            ax, ay = 0.5, 0.5
        ok = self._nav.zoom(factor, (ax, ay))
        if ok:
            self._map_nav_touch()
        return ok

    def _frame_text_at(self, pos):
        frame = self.itemAt(pos)
        if frame is None:
            return None, None
        it = getattr(frame, "item", None)
        if it is None:
            return None, None
        try:
            from ggis.core.model.layout_items import TextItem
        except Exception:
            exc_note("_frame_text_at @ ggis/ui/views/layout/canvas.py:4812")
            return None, None
        if not isinstance(it, TextItem):
            return None, None
        return frame, it

    def mouseDoubleClickEvent(self, e):
        if (self.sel_path_mode() and self._sel_mode == "poly"
                and self._sel_drag):
            self._apply_sel_path()
            e.accept()
            return
        pos = e.position().toPoint()
        frame, item = self._frame_text_at(pos)
        if item is not None:
            self._begin_inline_edit(frame, item)
            e.accept()
            return
        fr = self._frame_at(pos)
        el = getattr(fr, "item", None) if fr is not None else None
        if el is None:
            super().mouseDoubleClickEvent(e)
            return
        try:
            from ggis.core.model import layout_items as _LI
        except Exception:
            exc_note("mouseDoubleClickEvent @ ggis/ui/views/layout/canvas.py:4846")
            _LI = None
        if _LI is not None and isinstance(el, _LI.MapFrame):
            self.select_item(el)
            self.set_map_activate(True)
            e.accept()
            return
        self.select_item(el)
        try:
            self.itemDoubleClicked.emit(el)
        except Exception:
            _log.exception("布局：双击元素通知失败")
        e.accept()

    def _frame_at(self, pos):
        try:
            it = self.itemAt(pos)
        except Exception:
            exc_note("_frame_at @ ggis/ui/views/layout/canvas.py:4868")
            return None
        return it if isinstance(it, ItemFrame) else None

    def _begin_inline_edit(self, frame, item):
        self._end_inline_edit()
        ed = _InlineTextEdit(
            self.viewport(),
            on_done=lambda t: self._commit_inline(item, t),
            on_cancel=self._end_inline_edit)
        sr = frame.sceneBoundingRect()
        try:
            sr = QRectF(item.rect_mm)
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4891")
            sr = frame.sceneBoundingRect()
        r = self.mapFromScene(sr).boundingRect()
        if r.height() < 18:
            r.moveTop(int(r.center().y()) - 9)
            r.setHeight(18)
        if r.width() < 24:
            r.setWidth(24)
        ed.setGeometry(r)
        ed.setPlainText(str(getattr(item, "content", "") or ""))
        try:
            k = float(self.transform().m11())
            if k <= 0:
                k = 1.0
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4910")
            k = 1.0
        line_h = 14.0
        try:
            px = max(6.0, float(getattr(item, "font_size_pt", 12.0) or 12.0)
                     * (25.4 / 72.0) * k)
            f = ed.font()
            f.setPixelSize(int(round(px)))
            f.setBold(bool(getattr(item, "bold", False)))
            f.setItalic(bool(getattr(item, "italic", False)))
            fam = str(getattr(item, "font_family", "") or "")
            if fam:
                f.setFamily(fam)
            ed.setFont(f)
            try:
                line_h = float(QFontMetricsF(f).height())
            except Exception:
                exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4926")
                line_h = px * 1.3
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4928")
            pass
        try:
            ed.document().setDocumentMargin(0.0)
            ed.setContentsMargins(0, 0, 0, 0)
            ed.setViewportMargins(0, 0, 0, 0)
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4936")
            pass
        try:
            if str(getattr(item, "valign", "middle") or "middle") == "middle":
                top = int(round((max(0.0, float(r.height())) - line_h) * 0.5))
                if top > 0:
                    ed.setViewportMargins(0, top, 0, 0)
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4946")
            pass
        try:
            from ggis.common.styling import icons as _icons
            dark = bool(_icons.is_dark())
            col = str(getattr(item, "color", "") or "") or "#1A1A1A"
            tc = QColor(col)
            base = QColor("#1E2229") if dark else QColor("#FFFFFF")
            lum = (0.299 * tc.red() + 0.587 * tc.green() + 0.114 * tc.blue())
            base_lum = (0.299 * base.red() + 0.587 * base.green()
                        + 0.114 * base.blue())
            if abs(lum - base_lum) < 70:
                col = "#E6EAF2" if dark else "#1A1A1A"
            ed.setStyleSheet(
                "#GgsLayoutInlineEdit{background:transparent;"
                "border:1px dashed rgba(46,123,224,0.9);color:%s;"
                "padding:0px;}" % col)
            try:
                ed.viewport().setAutoFillBackground(False)
            except Exception:
                exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4977")
                pass
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4979")
            pass
        try:
            ed.setAlignment(item._flags())
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4983")
            pass
        ed.show()
        ed.setFocus(Qt.FocusReason.MouseFocusReason)
        try:
            c = ed.textCursor()
            c.movePosition(QTextCursor.MoveOperation.End)
            ed.setTextCursor(c)
        except Exception:
            exc_note("_begin_inline_edit @ ggis/ui/views/layout/canvas.py:4994")
            pass
        try:
            self._begin_inline_backdrop(frame, item)
        except Exception:
            _log.exception("布局：编辑期遮住原文失败（可能出现重影）")
        self._inline = ed

    def _commit_inline(self, item, text):
        if getattr(self, "_committing", False):
            return
        self._committing = True
        try:
            text = str(text or "")
            changed = text != str(getattr(item, "content", "") or "")
            if changed:
                item.content = text
            if changed:
                try:
                    sc = self._scene
                    fr = sc.frame_of(item) if sc is not None else None
                except Exception:
                    exc_note("_commit_inline @ ggis/ui/views/layout/canvas.py:5025")
                    fr = None
                if fr is not None:
                    self._show_content_ghost(fr)
            self._end_inline_edit()
            if changed:
                self.textEdited.emit(item, text)
            try:
                self.viewport().update()
            except Exception:
                exc_note("_commit_inline @ ggis/ui/views/layout/canvas.py:5034")
                pass
        finally:
            self._committing = False

    def _end_inline_edit(self):
        ed = getattr(self, "_inline", None)
        self._inline = None
        try:
            self._end_inline_backdrop()
        except Exception:
            _log.exception("布局：收编辑期遮罩失败")
        if ed is None:
            return
        try:
            ed.blockSignals(True)
            ed.hide()
            ed.deleteLater()
        except Exception:
            exc_note("_end_inline_edit @ ggis/ui/views/layout/canvas.py:5054")
            pass

    def _begin_inline_backdrop(self, frame, item):
        sc = self._scene
        if frame is None or sc is None or sc.layout is None:
            return False
        self._end_inline_backdrop()
        try:
            r = QRectF(item.rect_mm)
        except Exception:
            exc_note("_begin_inline_backdrop @ ggis/ui/views/layout/canvas.py:5075")
            return False
        if r.width() <= 0 or r.height() <= 0:
            return False
        pad = max(1.0, self._overlay_pad_mm(item))
        snap = QRectF(r).adjusted(-pad, -pad, pad, pad)
        e = QGraphicsPathItem()
        e.setPen(QPen(Qt.PenStyle.NoPen))
        e.setBrush(Qt.BrushStyle.NoBrush)
        e.setZValue(901)
        e.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        p = QPainterPath()
        p.addRect(snap)
        e.setPath(p)
        sc.addItem(e)
        self._edit_erase = e
        self._set_erase_patch(item, snap, erase=e)
        return True

    def _end_inline_backdrop(self):
        e = getattr(self, "_edit_erase", None)
        self._edit_erase = None
        if e is None:
            return
        self._patch_seq += 1
        self._patch_erase = None
        try:
            sc = self._scene
            if sc is not None:
                sc.removeItem(e)
            QTimer.singleShot(0, lambda _k=e: None)
        except Exception:
            exc_note("_end_inline_backdrop @ ggis/ui/views/layout/canvas.py:5109")
            pass

    def wheelEvent(self, e):
        self.begin_fast()
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            super().wheelEvent(e)
            return
        delta = e.angleDelta().y()
        if not delta:
            super().wheelEvent(e)
            return
        try:
            pos = e.position().toPoint()
        except Exception:
            exc_note("wheelEvent @ ggis/ui/views/layout/canvas.py:5137")
            pos = None
        if self._activated_ok():
            anchor_scene = None
            try:
                if pos is not None:
                    anchor_scene = self.mapToScene(pos)
            except Exception:
                exc_note("wheelEvent @ ggis/ui/views/layout/canvas.py:5147")
                anchor_scene = None
            factor = (1 / 1.15) if delta > 0 else 1.15
            if self._map_zoom(factor, anchor_scene):
                e.accept()
                return
        self.set_zoom(self._zoom * (1.15 if delta > 0 else 1 / 1.15),
                      anchor=pos)
        e.accept()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._auto_fit:
            try:
                vp = self.viewport()
                if vp.width() > 60 and vp.height() > 60:
                    self._auto_fit = False
                    self.fit_page()
                    return
            except Exception:
                exc_note("resizeEvent @ ggis/ui/views/layout/canvas.py:5173")
                pass
        if self._zoom <= 0:
            self.fit_page()
        self._sync_rulers()

    def _activated_ok(self):
        it = self._activated
        if it is None:
            return False
        try:
            for x in (self._scene.layout.items_in_draw_order() or []):
                if x is it:
                    return True
        except Exception:
            exc_note("_activated_ok @ ggis/ui/views/layout/canvas.py:5207")
            return True
        _log.info("布局：被激活的地图框已不在页面里 ⇒ 自动退出激活")
        try:
            self.set_map_activate(False)
        except Exception:
            _log.exception("布局：自动退出激活失败")
            self._activated = None
        return False

    def _hit_activated(self, vp_pos):
        it = self._activated
        if it is None:
            return False
        try:
            sp = self.mapToScene(vp_pos)
            r = QRectF(it.rect_mm)
            tol = 4.0 / max(1e-6, float(self.transform().m11()))
            return bool(r.adjusted(-tol, -tol, tol, tol).contains(sp))
        except Exception:
            exc_note("_hit_activated @ ggis/ui/views/layout/canvas.py:5235")
            return True

    def mousePressEvent(self, e):
        if self.draw_kind() and e.button() == Qt.MouseButton.LeftButton:
            p = self.mapToScene(self._ev_pos(e))
            self._draw_rect = QRectF(p, p)
            try:
                self.viewport().update()
            except Exception:
                exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:5250")
                pass
            e.accept()
            return
        if self.sel_path_mode() and e.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(self._ev_pos(e))
            if self._sel_mode == "poly":
                self._sel_pts.append(pos)
            else:
                self._sel_pts = [pos, pos]
            self._sel_drag = True
            try:
                self.viewport().update()
            except Exception:
                exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:5265")
                pass
            e.accept()
            return
        if e.button() == Qt.MouseButton.MiddleButton:
            self._mid_drag = e.position().toPoint()
            try:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            except Exception:
                exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:5276")
                pass
            e.accept()
            return
        if e.button() == Qt.MouseButton.LeftButton and self._activated_ok():
            if self._hit_activated(e.position().toPoint()):
                self._map_drag = e.position().toPoint()
                try:
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                except Exception:
                    exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:5290")
                    pass
                e.accept()
                return
            try:
                self.set_map_activate(False)
            except Exception:
                exc_note("mousePressEvent @ ggis/ui/views/layout/canvas.py:5296")
                self._activated = None
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._draw_rect is not None and self.draw_kind():
            p = self.mapToScene(self._ev_pos(e))
            self._draw_rect = QRectF(self._draw_rect.topLeft(), p)
            try:
                self.setCursor(Qt.CursorShape.CrossCursor)
            except Exception:
                exc_note("mouseMoveEvent @ ggis/ui/views/layout/canvas.py:5310")
                pass
            try:
                self.viewport().update()
            except Exception:
                exc_note("mouseMoveEvent @ ggis/ui/views/layout/canvas.py:5314")
                pass
            e.accept()
            return
        if getattr(self, "_mid_drag", None) is not None:
            cur = e.position().toPoint()
            d = cur - self._mid_drag
            self._mid_drag = cur
            hb = self.horizontalScrollBar()
            vb = self.verticalScrollBar()
            hb.setValue(hb.value() - d.x())
            vb.setValue(vb.value() - d.y())
            e.accept()
            return
        if self._activated is not None and \
                getattr(self, "_map_drag", None) is not None:
            cur = e.position().toPoint()
            d = cur - self._map_drag
            self._map_drag = cur
            k = max(1e-6, float(self.transform().m11()))
            self._map_pan(-d.x() / k, d.y() / k)
            e.accept()
            return
        if self._sel_drag and self.sel_path_mode():
            pos = self.mapToScene(self._ev_pos(e))
            if self._sel_mode == "lasso":
                if not self._sel_pts:
                    self._sel_pts = [pos]
                elif (pos - self._sel_pts[-1]).manhattanLength() >= LASSO_STEP_MM:
                    self._sel_pts.append(pos)
            elif self._sel_mode == "poly":
                self._sel_hover = pos
            elif len(self._sel_pts) >= 2:
                self._sel_pts[-1] = pos
            else:
                self._sel_pts = [pos, pos]
            try:
                self.viewport().update()
            except Exception:
                exc_note("mouseMoveEvent @ ggis/ui/views/layout/canvas.py:5356")
                pass
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if (self._draw_rect is not None and self.draw_kind()
                and e.button() == Qt.MouseButton.LeftButton):
            self._finish_draw()
            e.accept()
            return
        if getattr(self, "_mid_drag", None) is not None:
            self._mid_drag = None
            try:
                self.setCursor(Qt.CursorShape.OpenHandCursor
                               if self._activated is not None
                               else Qt.CursorShape.ArrowCursor)
            except Exception:
                exc_note("mouseReleaseEvent @ ggis/ui/views/layout/canvas.py:5375")
                pass
            e.accept()
            return
        if getattr(self, "_map_drag", None) is not None:
            self._map_drag = None
            try:
                self.setCursor(Qt.CursorShape.OpenHandCursor
                               if self._activated is not None
                               else Qt.CursorShape.ArrowCursor)
            except Exception:
                exc_note("mouseReleaseEvent @ ggis/ui/views/layout/canvas.py:5385")
                pass
            e.accept()
            return
        if self._sel_drag and self.sel_path_mode():
            if self._sel_mode != "poly":
                self._apply_sel_path()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        k = e.key()
        if self.draw_kind() and k == Qt.Key.Key_Escape:
            self.cancel_draw()
            e.accept()
            return
        if self.sel_path_mode() and self._sel_drag:
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._apply_sel_path()
                e.accept()
                return
            if k == Qt.Key.Key_Escape:
                self._cancel_sel_path()
                e.accept()
                return
        if k == Qt.Key.Key_Escape:
            self._end_inline_edit()
            if self._cancel_drag():
                e.accept()
                return
            if self._activated_ok():
                try:
                    self.set_map_activate(False)
                except Exception:
                    exc_note("keyPressEvent @ ggis/ui/views/layout/canvas.py:5426")
                    self._activated = None
                e.accept()
                return
            if self.selected_items():
                self.clear_selection()
            e.accept()
            return
        if k in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                 Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = SNAP_MM * (10.0 if (e.modifiers()
                                       & Qt.KeyboardModifier.ShiftModifier)
                              else 1.0)
            dx = (-step if k == Qt.Key.Key_Left else
                  (step if k == Qt.Key.Key_Right else 0.0))
            dy = (-step if k == Qt.Key.Key_Up else
                  (step if k == Qt.Key.Key_Down else 0.0))
            if self._nudge_selected(dx, dy):
                e.accept()
                return
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            scene = self.scene()
            many = self.selected_items()
            if len(many) > 1:
                self._end_inline_edit()
                self.delete_selected()
                e.accept()
                return
            item = scene.selected_item() if scene else None
            if item is not None:
                it = item
                self._end_inline_edit()
                QTimer.singleShot(0, lambda _i=it: self.deleteRequested.emit(_i))
                e.accept()
                return
        super().keyPressEvent(e)

    def _cancel_drag(self):
        n = 0
        try:
            for f in list(self._scene.frames or []):
                if not getattr(f, "_drag", ""):
                    continue
                try:
                    if f.cancel_drag():
                        n += 1
                except Exception:
                    _log.exception("布局：取消拖动失败")
        except Exception:
            _log.exception("布局：取消拖动（遍历元素框）失败")
        return n > 0

    def _nudge_selected(self, dx_mm, dy_mm):
        if self._activated is not None:
            return False
        mov = QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        moved = 0
        for f in list(self._scene.frames or []):
            try:
                if not f.isSelected() or not f.isVisible():
                    continue
                if not (f.flags() & mov):
                    continue
                f.setPos(f.pos() + QPointF(float(dx_mm), float(dy_mm)))
                moved += 1
            except Exception:
                _log.exception("布局：方向键微移失败")
        if moved:
            try:
                self._scene.commit_geometry()
            except Exception:
                exc_note("_nudge_selected @ ggis/ui/views/layout/canvas.py:5526")
                pass
        return bool(moved)


class GgsRulerMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRulerMenu")
