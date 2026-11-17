# -*- coding: utf-8 -*-
import os

from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import (Qt, QSize, QPoint, QRect, QRectF, QPointF,
                            Signal, QTimer, QEvent)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics,
                           QIcon, QPainter, QPainterPath, QPalette, QPen)
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                               QMenu, QSizePolicy, QToolButton,
                               QWidgetAction)

from ggis.common.styling import icons as _icons
from ggis.common.styling import themes as _themes
from ggis.core.app import settings as _settings

def _is_dark_color(c):
    try:
        return (c.red() * 299 + c.green() * 587 + c.blue() * 114) < 128000
    except Exception:
        exc_note("_is_dark_color @ ggis/common/widgets/standard.py:109")
        return True



def contrast_halo_color(color):
    try:
        c = QColor(color)
        lum = (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 255000.0
    except Exception:
        exc_note("contrast_halo_color @ ggis/common/widgets/standard.py:1425")
        return QColor("#3A4552")
    return QColor("#3A4552") if lum > 0.62 else QColor("#E8EAED")



def paint_checkerboard(painter, rect, radius=3.0, step=6,
                       dark="#B0B0B0", light="#E8E8E8"):
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(dark)))
    painter.drawRoundedRect(rect, radius, radius)
    painter.setBrush(QBrush(QColor(light)))
    _clip = QPainterPath()
    _clip.addRoundedRect(rect, radius, radius)
    painter.save()
    painter.setClipPath(_clip, Qt.ClipOperation.IntersectClip)
    try:
        yy = 0
        while yy * step < rect.height():
            xx = 0
            while xx * step < rect.width():
                if (xx + yy) % 2 == 0:
                    x0 = rect.left() + xx * step
                    y0 = rect.top() + yy * step
                    w = min(step, rect.right() - x0)
                    h = min(step, rect.bottom() - y0)
                    if w > 0 and h > 0:
                        painter.drawRect(QRectF(x0, y0, w, h))
                xx += 1
            yy += 1
    finally:
        painter.restore()



class GgsColorSwatch(QWidget):

    def __init__(self, color="#FFFFFF", shape="rect", parent=None):
        super().__init__(parent)
        self.setObjectName("GgsColorSwatch")
        self._color = QColor(color)
        self._shape = str(shape or "rect")
        if self._shape not in ("rect", "line", "dot"):
            self._shape = "rect"
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def shape(self):
        return self._shape

    def setShape(self, shape):
        s = str(shape or "rect")
        if s in ("rect", "line", "dot") and s != self._shape:
            self._shape = s
            self.update()

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        c = QColor(color)
        if c.isValid():
            self._color = c
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)
            if r.width() <= 0 or r.height() <= 0:
                return
            if not self.isEnabled():
                p.setOpacity(0.35)
            if self._shape == "rect" and self._color.alpha() < 255:
                paint_checkerboard(p, r, 3.0, 6)
            if self._shape == "line":
                y = r.center().y()
                pen = QPen(self._color, 3.0)
                pen.setCapStyle(Qt.PenCapStyle.FlatCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            elif self._shape == "dot":
                d = min(r.width(), r.height())
                c = r.center()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(contrast_halo_color(self._color)))
                p.drawEllipse(QPointF(c.x(), c.y()), d / 2.0, d / 2.0)
                p.setBrush(QBrush(self._color))
                p.drawEllipse(QPointF(c.x(), c.y()),
                              max(1.0, d / 2.0 - 1.0), max(1.0, d / 2.0 - 1.0))
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(self._color))
                p.drawRoundedRect(r, 3.0, 3.0)
            if self._color.alpha() == 0:
                self._paint_no_color(p, r)
        finally:
            p.end()

    @staticmethod
    def _paint_no_color(p, r):
        pen = QPen(QColor("#E5484D"))
        pen.setWidthF(1.5)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(r.left(), r.top()),
                   QPointF(r.right(), r.bottom()))



class GgsColorRampBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsColorRampBar")
        self.setMinimumHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self._code = "none"
        self._invert = False
        self._colors = []

    def setRamp(self, code, invert=False):
        self._code = str(code or "none")
        self._invert = bool(invert)
        self._colors = []
        self.update()

    def setColors(self, colors):
        self._colors = [str(c) for c in (colors or [])]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            r = self.rect().adjusted(0, 0, -1, -1)
            stops = []
            if self._colors:
                for _c in self._colors:
                    try:
                        _q = QColor(_c)
                        stops.append((_q.red(), _q.green(), _q.blue()))
                    except Exception:
                        exc_note("paintEvent @ ggis/common/widgets/standard.py:2714")
                        continue
            else:
                try:
                    from ggis.core.style import raster_display as rd
                    stops = rd.ramp_stops(self._code, max(2, r.width()))
                except Exception:
                    exc_note("paintEvent @ ggis/common/widgets/standard.py:2720")
                    stops = []
                if self._invert:
                    stops = list(reversed(stops))
            if not stops:
                stops = [(int(255 * i / max(1, r.width() - 1)),) * 3
                         for i in range(max(2, r.width()))]
            n = len(stops)
            for i in range(n):
                x = r.left() + int(round(i * (r.width() - 1) / max(1, n - 1)))
                x2 = r.left() + int(round((i + 1) * (r.width() - 1)
                                          / max(1, n - 1)))
                p.fillRect(x, r.top(), max(1, x2 - x + 1), r.height() + 1,
                           QColor(int(stops[i][0]), int(stops[i][1]),
                                  int(stops[i][2])))
            p.setPen(QPen(QColor(_themes.theme_colors(
                _settings.get("theme")).get("border")
                or "#8a929c"), 1))
            p.drawRect(r)
        except Exception:
            exc_note("paintEvent @ ggis/common/widgets/standard.py:2740")
            pass
        finally:
            p.end()



_RAMP_ICON_CACHE = {}


def ramp_strip_pixmap(colors, w, h, tag=""):
    key = (tuple(colors), int(w), int(h), str(tag))
    hit = _RAMP_ICON_CACHE.get(key)
    if hit is not None:
        return hit
    from PySide6.QtGui import QPixmap
    pm = QPixmap(int(w), int(h))
    pm.fill(Qt.GlobalColor.transparent)
    n = len(colors)
    if n <= 0:
        return pm
    p = QPainter(pm)
    try:
        for x in range(int(w)):
            t = (x / max(1, int(w) - 1)) * (n - 1)
            i = min(int(t), n - 2) if n > 1 else 0
            f = (t - i) if n > 1 else 0.0
            c0 = QColor(colors[i])
            c1 = QColor(colors[min(i + 1, n - 1)])
            col = QColor(int(c0.red() + (c1.red() - c0.red()) * f),
                         int(c0.green() + (c1.green() - c0.green()) * f),
                         int(c0.blue() + (c1.blue() - c0.blue()) * f))
            p.setPen(col)
            p.drawLine(x, 0, x, int(h) - 1)
    finally:
        p.end()
    if len(_RAMP_ICON_CACHE) > 96:
        _RAMP_ICON_CACHE.clear()
    _RAMP_ICON_CACHE[key] = pm
    return pm


def _menu_color(key, fallback):
    try:
        from ggis.common.styling import icons as _icons
        from ggis.common.styling import themes as _th
        name = "dark" if _icons.is_dark() else "light"
        pal = _th.theme_colors(name)
        c = QColor(pal.get(key) or "")
        if c.isValid():
            return c
    except Exception:
        exc_note("_menu_color @ ggis/common/widgets/standard.py:3858")
        pass
    return QColor(fallback)


def _menu_hover_color():
    return _menu_color("panel_hi", "#e7e9ed")


def _menu_current_bg():
    return _menu_color("accent_soft", "#c9d3df")


def _menu_accent_color():
    return _menu_color("accent", "#0078d4")


class _MenuRow(QWidget):

    clicked = Signal()

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = str(text)
        self.setObjectName("GgsRampMenuRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:3922")
            pass
        self._hover = False

    def _set_hover(self, on):
        on = bool(on)
        if on != self._hover:
            self._hover = on
            self.update()

    def set_hover(self, on):
        self._set_hover(on)

    def enterEvent(self, e):
        self._set_hover(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._set_hover(False)
        super().leaveEvent(e)

    def text(self):
        return self._text

    def setText(self, t):
        self._text = str(t)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            r = self.rect()
            if self._hover or self.underMouse():
                p.save()
                try:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(_menu_hover_color())
                    p.drawRoundedRect(r, 4, 4)
                finally:
                    p.restore()
            try:
                p.setPen(self.palette().color(QPalette.ColorRole.Text))
            except Exception:
                exc_note("paintEvent @ ggis/common/widgets/standard.py:3972")
                pass
            fm = p.fontMetrics()
            p.drawText(r, int(Qt.AlignmentFlag.AlignCenter),
                       fm.elidedText(self._text, Qt.TextElideMode.ElideRight,
                                     max(8, r.width() - 8)))
        finally:
            p.end()

    def mouseReleaseEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(e.position().toPoint())):
            self.clicked.emit()
            e.accept()
            return
        super().mouseReleaseEvent(e)


class _RampMenuItem(QWidget):

    picked = Signal(str)

    def __init__(self, code, label, colors, w, h, parent=None,
                 name_col_w=None):
        super().__init__(parent)
        self._code = str(code)
        self._label = str(label)
        self._name_col_w = None if name_col_w is None else int(name_col_w)
        self._colors = list(colors or [])
        self._h = int(h)
        self._bar_w = max(40, int(w))
        self._show_name = False
        self._current = False
        self._pm = None
        self._rebuild_pm()
        self.setObjectName("GgsRampMenuItem")
        self.setToolTip(str(label))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:4033")
            pass
        self._hover = False
        self._apply_size()

    def _set_hover(self, on):
        on = bool(on)
        if on != self._hover:
            self._hover = on
            self.update()

    def set_hover(self, on):
        self._set_hover(on)

    def enterEvent(self, e):
        self._set_hover(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._set_hover(False)
        super().leaveEvent(e)

    def _name_w(self):
        if not self._show_name:
            return 0
        try:
            if self._name_col_w is not None:
                w = int(self._name_col_w) + 8
            elif not self._label:
                return 0
            else:
                w = QFontMetrics(self.font()).horizontalAdvance(self._label) + 8
        except Exception:
            exc_note("_name_w @ ggis/common/widgets/standard.py:4078")
            w = 60
        cap = max(24, int(int(self._bar_w) * 0.45))
        return int(min(max(24, w), cap))

    def _rebuild_pm(self):
        nw = self._name_w()
        w = max(24, int(self._bar_w) - nw)
        self._pm = ramp_strip_pixmap(
            self._colors, w, int(self._h),
            tag="menu-%d-%d" % (int(self._bar_w), int(nw)))

    def _apply_size(self):
        self.setFixedSize(int(self._bar_w) + 10, int(self._h) + 8)

    def setShowName(self, on):
        on = bool(on)
        if on == self._show_name:
            return
        self._show_name = on
        self._rebuild_pm()
        self._apply_size()
        self.update()

    def setCurrent(self, on):
        on = bool(on)
        if on != self._current:
            self._current = on
            self.update()

    def set_width(self, w):
        w = max(40, int(w))
        if w == self._bar_w:
            return
        self._bar_w = w
        self._rebuild_pm()
        self._apply_size()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            r = self.rect()
            hover = bool(self._hover or self.underMouse())
            if hover:
                p.save()
                try:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(_menu_hover_color())
                    p.drawRoundedRect(r, 4, 4)
                finally:
                    p.restore()
            if self._current:
                p.save()
                try:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(_menu_current_bg())
                    p.drawRoundedRect(r, 4, 4)
                finally:
                    p.restore()
            nw = self._name_w()
            _y = 4
            _pm = self._pm
            if _pm is not None and not _pm.isNull():
                try:
                    _y = max(0, min(4, self.height() - _pm.height()))
                except Exception:
                    exc_note("paintEvent @ ggis/common/widgets/standard.py:4201")
                    _y = 4
                p.drawPixmap(5 + nw, _y, _pm)
            if nw:
                self._draw_label(p, nw)
            if self._current:
                p.fillRect(QRectF(1, 1, 2, self.height() - 2),
                           _menu_accent_color())
        finally:
            p.end()

    def _draw_label(self, p, w):
        f = p.font()
        try:
            f.setPointSizeF(max(7.0, f.pointSizeF() - 0.5))
        except Exception:
            exc_note("_draw_label @ ggis/common/widgets/standard.py:4223")
            pass
        p.setFont(f)
        fm = p.fontMetrics()
        try:
            pen = self.palette().color(QPalette.ColorRole.Text)
        except Exception:
            exc_note("_draw_label @ ggis/common/widgets/standard.py:4229")
            pen = QColor("#000000")
        p.setPen(pen)
        tw = max(4, int(w) - 8)
        p.drawText(QRectF(5, 0, tw, self.height()),
                   int(Qt.AlignmentFlag.AlignVCenter
                       | Qt.AlignmentFlag.AlignLeft),
                   fm.elidedText(self._label, Qt.TextElideMode.ElideRight, tw))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self._code)
            e.accept()
            return
        super().mouseReleaseEvent(e)


