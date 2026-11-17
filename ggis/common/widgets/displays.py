# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from ggis.common.styling import themes


class GgsSpinner(QWidget):

    def __init__(self, parent=None, diameter=14):
        super().__init__(parent)
        self._d = diameter
        self._angle = 0
        self.setFixedSize(self._d + 4, self._d + 4)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self.show()
        self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            try:
                color = QColor(themes.accent())
            except Exception:
                exc_note("paintEvent @ ggis/common/widgets/spinner.py:51")
                color = QColor("#3d7fd1")
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            r = self.rect().adjusted(3, 3, -3, -3)
            p.drawArc(r, -self._angle * 16, 90 * 16)
            pen2 = QPen(color, 2)
            pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen2)
            p.drawArc(r, -(self._angle - 60) * 16, 30 * 16)
        finally:
            p.end()



class GgsRenderStatus(QWidget):

    BUSY = "busy"
    DONE = "done"

    clicked = Signal(str)

    _ICON_OF = {DONE: "refresh"}

    def __init__(self, text="", parent=None, diameter=14):
        super().__init__(parent)
        self.setObjectName("GgsRenderStatusHost")
        self._clickable = True
        self._state = self.DONE
        self._d = max(8, int(diameter))
        self._px = self._d + 6
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._spin = None
        try:
            self._spin = GgsSpinner(self, diameter=self._d)
            self._spin.setFixedSize(self._px, self._px)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/generated.py:1098")
            self._spin = None
        if self._spin is not None:
            lay.addWidget(self._spin, 0, Qt.AlignmentFlag.AlignCenter)
        self._ico = QLabel(self)
        self._ico.setObjectName("GgsRenderStatusIcon")
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setFixedSize(self._px, self._px)
        lay.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(self._px, self._px)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_state(self.DONE)

    @staticmethod
    def _t(s):
        try:
            from ggis.core.app.i18n import tr
            return tr(s)
        except Exception:
            exc_note("_t @ ggis/common/widgets/generated.py:1121")
            return s

    def state(self):
        return self._state

    def set_state(self, state):
        st = str(state or self.DONE)
        if st != self.BUSY:
            st = self.DONE
        self._state = st
        busy = (st == self.BUSY) and self._spin is not None
        if self._spin is not None:
            try:
                if busy:
                    self._spin.setVisible(True)
                    self._spin.start()
                else:
                    self._spin.stop()
                    self._spin.setVisible(False)
            except Exception:
                exc_note("set_state @ ggis/common/widgets/generated.py:1143")
                pass
        try:
            self._ico.setVisible(not busy)
        except Exception:
            exc_note("set_state @ ggis/common/widgets/generated.py:1147")
            pass
        self._refresh_icon()
        self.update()

    def set_busy(self, text=""):
        self.set_state(self.BUSY)

    def set_done(self, text=""):
        self.set_state(self.DONE)

    def set_clickable(self, on):
        on = bool(on)
        if on == getattr(self, "_clickable", True):
            return
        self._clickable = on
        try:
            self.setEnabled(on)
        except Exception:
            exc_note("set_clickable @ ggis/common/widgets/generated.py:1174")
            pass
        try:
            self.setCursor(Qt.CursorShape.PointingHandCursor if on
                           else Qt.CursorShape.ArrowCursor)
        except Exception:
            exc_note("set_clickable @ ggis/common/widgets/generated.py:1179")
            pass
        self._refresh_icon()

    def retheme(self):
        try:
            self._refresh_icon()
        except Exception:
            exc_note("retheme @ ggis/common/widgets/generated.py:1187")
            pass

    def setText(self, text):
        self.set_busy(text)

    def text(self):
        return ""

    def _refresh_icon(self):
        pm = self._pixmap_for(self._state)
        if pm is not None:
            try:
                self._ico.setPixmap(pm)
            except Exception:
                exc_note("_refresh_icon @ ggis/common/widgets/generated.py:1204")
                pass
        try:
            self.setToolTip(self._t(self._tip_now()))
        except Exception:
            exc_note("_refresh_icon @ ggis/common/widgets/generated.py:1208")
            pass

    def _pixmap_for(self, st):
        name = self._ICON_OF.get(st)
        if name is None:
            return None
        try:
            from ggis.common.styling import icons, themes
        except Exception:
            exc_note("_pixmap_for @ ggis/common/widgets/generated.py:1223")
            return None
        try:
            if getattr(self, "_clickable", True):
                col = icons.default_color()
            else:
                col = themes.text_dim()
            return icons.icon(name, color=col, size=self._px).pixmap(
                self._px, self._px)
        except Exception:
            exc_note("_pixmap_for @ ggis/common/widgets/generated.py:1238")
            return None

    def _tip_now(self):
        if not getattr(self, "_clickable", True):
            return "没有图层，无需渲染"
        if self._state == self.BUSY:
            return "渲染中（点击停止渲染）"
        return "渲染完成（点击重新渲染）"

    def mouseReleaseEvent(self, e):
        try:
            if not getattr(self, "_clickable", True):
                if e is not None:
                    e.accept()
                return
            if e is not None and e.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(self._state)
                e.accept()
                return
        except Exception:
            exc_note("mouseReleaseEvent @ ggis/common/widgets/generated.py:1260")
            pass
        super().mouseReleaseEvent(e)


class GgsDimLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsDimLabel")

