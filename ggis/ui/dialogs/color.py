# -*- coding: utf-8 -*-
import re

from PySide6.QtCore import (Qt, QSize, QPoint, QPointF, QRectF, Signal,
                            QEvent, QEventLoop, QObject)
from PySide6.QtGui import (QColor, QCursor, QPainter, QPen, QBrush,
                           QLinearGradient)
from PySide6.QtWidgets import (
                               QApplication,
                               QComboBox,
                               QDialogButtonBox,
                               QFrame,
                               QGridLayout,
                               QHBoxLayout,
                               QLabel,
                               QPushButton,
                               QSizePolicy,
                               QSpinBox,
                               QStyle,
                               QStyleOption,
                               QToolButton,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n as _i18n
from ggis.core.app import recent as _recent
from ggis.common.styling import icons, themes
from ggis.common.widgets.inputs import GgsSliderSpin
from ggis.common.widgets.colors import contrast_halo_color, paint_checkerboard
from ggis.common.base.dialog import GgsDialog
from ggis.common.widgets.displays import GgsDimLabel
import logging
from PySide6.QtWidgets import QLineEdit
_log = logging.getLogger("gmagis")

_HUES = (0, 25, 45, 60, 90, 120, 160, 190, 210, 240, 280, 320)


def _hsv(h, s, v):
    return QColor.fromHsv(int(h), int(s), int(v)).name().upper()


def _build_standard():
    out = [_hsv(0, 0, v) for v in (0, 40, 80, 120, 160, 200, 235, 255)]
    for v in (255, 200, 150):
        for h in _HUES:
            out.append(_hsv(h, 255, v))
    return out


def _build_gray():
    step = 255 // 15
    return ["#%02X%02X%02X" % ((i * step,) * 3) for i in range(16)]


def _build_hue():
    return [_hsv(int(i * 360 / 24), 220, 235) for i in range(24)]


_BREWER = [
    "#E41A1C", "#377EB8", "#4DAF4A", "#984EA3", "#FF7F00",
    "#FFFF33", "#A65628", "#F781BF", "#999999",
    "#1B9E77", "#D95F02", "#7570B3", "#E7298A", "#66A61E",
    "#E6AB02", "#A6761D", "#666666",
    "#A6CEE3", "#1F78B4", "#B2DF8A", "#33A02C", "#FB9A99",
    "#E31A1C", "#FDBF6F", "#CAB2D6", "#6A3D9A", "#FFFF99", "#B15928",
]

PALETTES = [
    ("标准色", _build_standard()),
    ("灰阶", _build_gray()),
    ("色相环", _build_hue()),
    ("ColorBrewer", _BREWER),
]

_PAL_COLS = 12
_PAL_CELL = 16
_PAL_SP = 2


def _palette_box(cols=None, cell=None, spacing=None):
    cols = _PAL_COLS if cols is None else int(cols)
    cell = _PAL_CELL if cell is None else int(cell)
    spacing = _PAL_SP if spacing is None else int(spacing)
    rows = 1
    for _title, colors in PALETTES:
        rows = max(rows, (len(colors) + cols - 1) // cols)
    return (cols * cell + (cols - 1) * spacing,
            rows * cell + (rows - 1) * spacing)


class _PaletteHolder(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsPaletteHolder")
        self.setFixedSize(QSize(*_palette_box()))
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(0)
        self._row = QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(0)
        vl.addLayout(self._row)
        vl.addStretch(1)
        self._row.addStretch(1)
        self._grid = None

    def grid(self):
        return self._grid

    def set_grid(self, widget):
        old = self._grid
        self._grid = widget
        if old is not None:
            try:
                self._row.removeWidget(old)
                old.hide()
                old.setParent(None)
                old.deleteLater()
            except Exception:
                _log.exception("silent exception in set_grid")
        self._row.insertWidget(
            0, widget, 0, Qt.AlignmentFlag.AlignTop
            | Qt.AlignmentFlag.AlignLeft)
        return widget


class _ColorCell(QWidget):

    picked = Signal(object)

    def __init__(self, color, size=16, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(QSize(int(size), int(size)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setToolTip(self._color.name().upper())

    def color(self):
        return QColor(self._color)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(QColor(self._color))

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            hover = bool(self._hover)
            inset = 1.5 if hover else 1.0
            r = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(r, 2.5, 2.5)
            try:
                pen = QPen(QColor(themes.accent() if hover
                                  else themes.text_dim()),
                           2.0 if hover else 1.0)
            except Exception:
                _log.exception("silent exception in paintEvent")
                pen = QPen(QColor("#888888"), 1.0)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 2.5, 2.5)
        finally:
            p.end()


class _PaletteGrid(QWidget):

    picked = Signal(object)

    def __init__(self, colors, cols=12, cell=16, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsPaletteGrid")
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        for i, hexs in enumerate(colors):
            c = _ColorCell(hexs, cell, self)
            c.picked.connect(self.picked)
            grid.addWidget(c, i // max(1, int(cols)), i % max(1, int(cols)))


class _HueBar(QWidget):

    hueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0
        self.setFixedHeight(14)
        self.setMinimumWidth(140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hue(self):
        return self._hue

    def setHue(self, h):
        h = max(0, min(359, int(h)))
        if h != self._hue:
            self._hue = h
            self.update()

    def _apply_x(self, x):
        r = self._bar_rect()
        if r.width() <= 0:
            return
        t = min(1.0, max(0.0, (float(x) - r.left()) / r.width()))
        self.setHue(round(t * 359))
        self.hueChanged.emit(self._hue)

    def _bar_rect(self):
        return QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)

    def mousePressEvent(self, e):
        self._apply_x(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._apply_x(e.position().x())

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r = self._bar_rect()
            g = QLinearGradient(r.topLeft(), r.topRight())
            for i in range(7):
                g.setColorAt(i / 6.0, QColor.fromHsv(min(359, i * 60), 255, 240))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 3.0, 3.0)
            x = r.left() + (self._hue / 359.0) * r.width()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#FFFFFF"), 2.0))
            p.drawLine(QPoint(int(x), int(r.top()) - 1),
                       QPoint(int(x), int(r.bottom()) + 1))
            p.setPen(QPen(QColor("#303030"), 1.0))
            p.drawRoundedRect(r, 3.0, 3.0)
        finally:
            p.end()


class _SVSquare(QWidget):

    svChanged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue = 0
        self._sat = 255
        self._val = 255
        self.setObjectName("GgsSVSquare")
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def hsv(self):
        return self._hue, self._sat, self._val

    def setHue(self, h):
        self._hue = max(0, min(359, int(h)))
        self.update()

    def setSV(self, s, v):
        s = max(0, min(255, int(s)))
        v = max(0, min(255, int(v)))
        if (s, v) != (self._sat, self._val):
            self._sat, self._val = s, v
            self.update()

    def _apply_pos(self, pos):
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        if r.width() <= 0 or r.height() <= 0:
            return
        tx = min(1.0, max(0.0, (pos.x() - r.left()) / r.width()))
        ty = min(1.0, max(0.0, (pos.y() - r.top()) / r.height()))
        self.setSV(round(tx * 255), round((1.0 - ty) * 255))
        self.svChanged.emit(self._sat, self._val)

    def mousePressEvent(self, e):
        self._apply_pos(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._apply_pos(e.position())

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
            pure = QColor.fromHsv(self._hue, 255, 255)
            g1 = QLinearGradient(r.topLeft(), r.topRight())
            g1.setColorAt(0.0, QColor(255, 255, 255))
            g1.setColorAt(1.0, pure)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g1))
            p.drawRect(r)
            g2 = QLinearGradient(r.topLeft(), r.bottomLeft())
            g2.setColorAt(0.0, QColor(0, 0, 0, 0))
            g2.setColorAt(1.0, QColor(0, 0, 0, 255))
            p.setBrush(QBrush(g2))
            p.drawRect(r)
            x = r.left() + (self._sat / 255.0) * r.width()
            y = r.top() + (1.0 - self._val / 255.0) * r.height()
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#FFFFFF"), 2.0))
            p.drawEllipse(QPoint(int(x), int(y)), 5, 5)
            p.setPen(QPen(QColor("#303030"), 1.0))
            p.drawEllipse(QPoint(int(x), int(y)), 6, 6)
        finally:
            p.end()


def _canvas_of(w):
    node = w
    while node is not None:
        cv = getattr(node, "canvas", None)
        if cv is not None:
            return cv
        node = node.parentWidget() if hasattr(node, "parentWidget") else None
    return None


_PICK_CODE = 0x7AC1


def _grab_snapshot(widget):
    try:
        img = widget.grab().toImage()
        if img is None or img.isNull():
            return None, 1.0
        try:
            dpr = float(img.devicePixelRatio() or 1.0)
        except Exception:
            _log.exception("silent exception in _grab_snapshot")
            dpr = 1.0
        return img, dpr
    except Exception:
        _log.exception("silent exception in _grab_snapshot")
        return None, 1.0


def _pixel_of(img, pos, dpr=1.0):
    if img is None:
        return QColor()
    try:
        d = float(dpr or 1.0)
        px = min(max(0, int(round(pos.x() * d))), img.width() - 1)
        py = min(max(0, int(round(pos.y() * d))), img.height() - 1)
        return QColor(img.pixel(px, py))
    except Exception:
        _log.exception("silent exception in _pixel_of")
        return QColor()


def _picker_cursor_pixmap(size=32):
    try:
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QPixmap
        from PySide6.QtSvg import QSvgRenderer
        body = icons._BODY.get("eyedropper")
        if not body:
            return None
        body = re.sub(r'\s*stroke-width="[^"]*"', "", body)
        try:
            dpr = float(icons.device_pixel_ratio() or 1.0)
        except Exception:
            _log.exception("silent exception in _picker_cursor_pixmap")
            dpr = 1.0
        n = int(round(size * dpr))
        pm = QPixmap(n, n)
        pm.fill(Qt.GlobalColor.transparent)
        tpl = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               'width="{w}" height="{w}" fill="none" stroke="{c}" '
               'stroke-width="{sw}" stroke-linecap="round" '
               'stroke-linejoin="round">{b}</svg>')
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for color, sw in (("#000000", "2.9"), ("#ffffff", "1.35")):
            svg = tpl.format(w=n, c=color, sw=sw, b=body)
            QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p)
        p.end()
        pm.setDevicePixelRatio(dpr)
        return pm
    except Exception:
        _log.exception("silent exception in _picker_cursor_pixmap")
        return None


def picker_cursor():
    pm = _picker_cursor_pixmap(32)
    if pm is not None and not pm.isNull():
        return QCursor(pm, 16, 27)
    return QCursor(Qt.CursorShape.CrossCursor)


def _modal_ancestor_blocking(parent, canvas):
    try:
        cv_win = canvas.window()
    except Exception:
        _log.exception("silent exception in _modal_ancestor_blocking")
        cv_win = None
    w = parent.window() if parent is not None else None
    seen = set()
    while w is not None and len(seen) < 8:
        if id(w) in seen:
            break
        seen.add(id(w))
        if w is not cv_win and w is not canvas:
            try:
                if w.isVisible() and w.isModal():
                    return w
            except Exception:
                _log.exception("silent exception in _modal_ancestor_blocking")
        try:
            pw = w.parentWidget()
        except Exception:
            _log.exception("silent exception in _modal_ancestor_blocking")
            pw = None
        w = pw.window() if pw is not None else None
    return None


class _PickerHUD(QWidget):

    SIDE = 26
    BORDER = 1
    RADIUS = 5
    INNER_RADIUS = 4

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool
                         | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setObjectName("GgsPickerHud")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedSize(self.SIDE, self.SIDE)
        self._color = QColor()

    def set_color(self, color):
        if color is not None and color.isValid():
            self._color = QColor(color)
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        try:
            opt = QStyleOption()
            opt.initFrom(self)
            self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget,
                                      opt, p, self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            b = self.BORDER
            r = QRectF(self.rect().adjusted(b, b, -b, -b))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self._color)
            p.drawRoundedRect(r, self.INNER_RADIUS, self.INNER_RADIUS)
        finally:
            p.end()


_FROZEN_DURING_PICK = (
    QEvent.Type.ToolTip,
    QEvent.Type.HoverEnter, QEvent.Type.HoverMove, QEvent.Type.HoverLeave,
    QEvent.Type.Enter, QEvent.Type.Leave,
)


def _clear_widget_hover(root):
    try:
        widgets = [root] + list(root.findChildren(QWidget))
    except Exception:
        _log.exception("silent exception in _clear_widget_hover")
        return
    for w in widgets:
        try:
            if w.testAttribute(Qt.WidgetAttribute.WA_UnderMouse):
                w.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
                w.update()
        except Exception:
            _log.exception("silent exception in _clear_widget_hover")
            continue


class _PickShield(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("GgsPickShield")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setGeometry(parent.rect())
        self.show()
        self.raise_()

    def paintEvent(self, _e):
        pass


class _PickGrabber(QObject):

    def __init__(self, canvas, loop, snap=None, dpr=1.0):
        super().__init__(canvas)
        self._cv = canvas
        self._loop = loop
        self._snap = snap
        self._dpr = float(dpr or 1.0)
        self._hud = None
        self._win = None
        try:
            self._win = canvas.window()
        except Exception:
            _log.exception("silent exception in __init__")
            self._win = None
        if self._win is None:
            self._win = canvas
        self.color = QColor()
        self.picked = False
        self._shield = None
        try:
            self._shield = _PickShield(self._win)
        except Exception:
            _log.exception("silent exception in __init__")
            self._shield = None

    def _on_move(self, ev):
        if self._snap is None:
            return
        try:
            gp = ev.globalPosition().toPoint()
            lp = self._win.mapFromGlobal(gp)
        except Exception:
            _log.exception("silent exception in _on_move")
            return
        if not self._win.rect().contains(lp):
            if self._hud is not None:
                self._hud.hide()
            return
        try:
            if self._shield is not None:
                if self._shield.geometry() != self._win.rect():
                    self._shield.setGeometry(self._win.rect())
                self._shield.raise_()
        except Exception:
            _log.exception("silent exception in _on_move")
        color = _pixel_of(self._snap, lp, self._dpr)
        if not color.isValid():
            return
        try:
            if self._hud is None:
                self._hud = _PickerHUD()
            self._hud.set_color(color)
            self._hud.move(gp + QPoint(8, 10))
            if not self._hud.isVisible():
                self._hud.show()
        except Exception:
            _log.exception("silent exception in _on_move")
            self._hud = None

    def _finish(self, color=None):
        if color is not None and color.isValid():
            self.color = color
            self.picked = True
        try:
            if self._hud is not None:
                self._hud.close()
                self._hud = None
        except Exception:
            _log.exception("silent exception in _finish")
        try:
            if self._shield is not None:
                self._shield.hide()
                self._shield.deleteLater()
                self._shield = None
        except Exception:
            _log.exception("silent exception in _finish")
        try:
            self._loop.quit()
        except Exception:
            _log.exception("silent exception in _finish")

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t in _FROZEN_DURING_PICK:
            return True
        if t == QEvent.Type.KeyPress:
            if ev.key() == Qt.Key.Key_Escape:
                self._finish()
                return True
            return False
        if t == QEvent.Type.MouseMove:
            self._on_move(ev)
            return False
        if t != QEvent.Type.MouseButtonPress:
            return False
        if ev.button() != Qt.MouseButton.LeftButton:
            self._finish()
            return True
        w = self._win
        lp = None
        try:
            lp = w.mapFromGlobal(ev.globalPosition().toPoint())
        except Exception:
            _log.exception("silent exception in eventFilter")
            lp = None
        if lp is None or not w.rect().contains(lp):
            self._finish()
            return True
        self._finish(_pixel_of(self._snap, lp, self._dpr))
        return True


def pick_from_map(canvas, parent=None):
    if canvas is None:
        return QColor()
    if _modal_ancestor_blocking(parent, canvas) is not None:
        return None
    app = QApplication.instance()
    cur = picker_cursor()
    prev_cursor = None
    try:
        prev_cursor = canvas.cursor()
        canvas.setCursor(cur)
    except Exception:
        _log.exception("silent exception in pick_from_map")
        prev_cursor = None
    if app is not None:
        try:
            QApplication.setOverrideCursor(cur)
        except Exception:
            _log.exception("silent exception in pick_from_map")
    loop = QEventLoop()
    win = None
    try:
        win = canvas.window() or canvas
    except Exception:
        _log.exception("silent exception in pick_from_map")
        win = canvas
    _clear_widget_hover(win)
    snap, dpr = _grab_snapshot(win)
    grab = _PickGrabber(canvas, loop, snap, dpr)
    if app is not None:
        try:
            app.installEventFilter(grab)
        except Exception:
            _log.exception("silent exception in pick_from_map")
    try:
        if app is not None:
            try:
                app.processEvents()
            except Exception:
                _log.exception("silent exception in pick_from_map")
        loop.exec()
    finally:
        if app is not None:
            try:
                app.removeEventFilter(grab)
            except Exception:
                _log.exception("silent exception in pick_from_map")
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                _log.exception("silent exception in pick_from_map")
        try:
            if prev_cursor is not None:
                canvas.setCursor(prev_cursor)
        except Exception:
            _log.exception("silent exception in pick_from_map")
    return grab.color if grab.picked else QColor()

def _alpha_to_pct(a):
    try:
        return int(round((255 - max(0, min(255, int(a)))) / 255.0 * 100))
    except Exception:
        _log.exception("silent exception in _alpha_to_pct")
        return 0


def _pct_to_alpha(p):
    try:
        v = max(0, min(100, int(p)))
    except Exception:
        _log.exception("silent exception in _pct_to_alpha")
        return 255
    return int(round((100 - v) / 100.0 * 255))


def _paint_no_color(p, r):
    pen = QPen(QColor("#E5484D"))
    pen.setWidthF(1.5)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(r.left(), r.top()), QPointF(r.right(), r.bottom()))


class _ColorPreview(QWidget):

    def __init__(self, color="#FFFFFF", parent=None, size=None, shape="rect"):
        super().__init__(parent)
        self._color = QColor(color)
        self._shape = str(shape or "rect")
        if self._shape not in ("rect", "line", "dot"):
            self._shape = "rect"
        if size is not None:
            self.setFixedSize(QSize(int(size[0]), int(size[1])))
        else:
            self.setFixedHeight(24)
            self.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Fixed)

    def shape(self):
        return self._shape

    def setShape(self, shape):
        s = str(shape or "rect")
        if s in ("rect", "line", "dot"):
            self._shape = s
            self.update()

    def color(self):
        return QColor(self._color)

    def setColor(self, c):
        c = QColor(c)
        if c.isValid() and c != self._color:
            self._color = c
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
            if r.width() <= 0 or r.height() <= 0:
                return
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._shape == "line":
                y = r.center().y()
                pen = QPen(self._color, 3.0)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
                if self._color.alpha() == 0:
                    _paint_no_color(p, r)
                return
            if self._shape == "dot":
                d = max(4.0, min(r.width(), r.height()) * 0.72)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(contrast_halo_color(self._color)))
                p.drawEllipse(r.center(), d / 2.0, d / 2.0)
                p.setBrush(QBrush(self._color))
                p.drawEllipse(r.center(), max(1.5, d / 2.0 - 1.5),
                              max(1.5, d / 2.0 - 1.5))
                if self._color.alpha() == 0:
                    _paint_no_color(p, r)
                return
            paint_checkerboard(p, r, 3.0, 8)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(self._color))
            p.drawRoundedRect(r, 3.0, 3.0)
            if self._color.alpha() == 0:
                _paint_no_color(p, r)
        finally:
            p.end()


class GgsColorPopup(QFrame):

    colorPicked = Signal(object)

    def __init__(self, color=None, parent=None, with_alpha=True, shape="rect",
                 embedded=False):
        if embedded:
            super().__init__(parent)
        else:
            super().__init__(parent, Qt.WindowType.Popup)
        self._embedded = bool(embedded)
        self.setObjectName("GgsColorPopupEmbedded" if embedded
                            else "GgsColorPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._color = QColor(color) if QColor(color).isValid() else QColor("#FFFFFF")
        self._alpha = self._color.alpha()
        self._updating = False
        self._shape = str(shape or "rect")

        out = QVBoxLayout(self)
        out.setContentsMargins(10, 10, 10, 10)
        out.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.setAlignment(Qt.AlignmentFlag.AlignLeft
                         | Qt.AlignmentFlag.AlignVCenter)
        self.preview = _ColorPreview(self._color, self, size=(30, 24),
                                     shape=self._shape)
        top.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignLeft)
        self.ed_hex = GgsColorHex(self._color.name().upper())
        self.ed_hex.setMaxLength(7)
        self.ed_hex.setToolTip(_i18n.tr("十六进制颜色，如 #1E88E5"))
        self.ed_hex.editingFinished.connect(self._on_hex)
        top.addWidget(self.ed_hex)
        if with_alpha:
            self.alpha_row = GgsSliderSpin(self, 0, 100, " %")
            self.alpha_row.setValue(_alpha_to_pct(self._alpha))
            self.alpha_row.setToolTip(
                "")
            self.alpha_row.valueChanged.connect(self._on_alpha)
        else:
            self.alpha_row = None
        top.addStretch(1)
        out.addLayout(top)
        if self.alpha_row is not None:
            out.addWidget(self.alpha_row)

        self.cmb_palette = QComboBox()
        for title, _cols in PALETTES:
            self.cmb_palette.addItem(_i18n.tr(title))
        self.cmb_palette.currentIndexChanged.connect(self._refresh_palette)
        out.addWidget(self.cmb_palette)

        self.pal_holder = _PaletteHolder(self)
        self.grid = _PaletteGrid(PALETTES[0][1], cols=_PAL_COLS,
                                 cell=_PAL_CELL, parent=self.pal_holder)
        self.grid.picked.connect(self._on_picked)
        self.pal_holder.set_grid(self.grid)
        out.addWidget(self.pal_holder)

        self.lbl_recent = GgsDimLabel(_i18n.tr("最近使用"))
        out.addWidget(self.lbl_recent)
        self.recent_box = QWidget(self)
        self._recent_lay = QHBoxLayout(self.recent_box)
        self._recent_lay.setContentsMargins(0, 0, 0, 0)
        self._recent_lay.setSpacing(2)
        out.addWidget(self.recent_box)
        self._fill_recent()

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_more = QPushButton(_i18n.tr("更多颜色…"))
        self.btn_more.clicked.connect(self._open_dialog)
        row.addWidget(self.btn_more)
        out.addLayout(row)

    def color(self):
        return QColor(self._color)

    def setColor(self, c):
        c = QColor(c)
        if not c.isValid():
            return
        self._color = c
        self._alpha = c.alpha()
        self._updating = True
        try:
            self.preview.setColor(c)
            self.ed_hex.setText(c.name().upper())
            if self.alpha_row is not None:
                self.alpha_row.setValue(_alpha_to_pct(self._alpha))
        finally:
            self._updating = False

    def _on_hex(self):
        if self._updating:
            return
        c = QColor(str(self.ed_hex.text() or "").strip())
        if c.isValid():
            c.setAlpha(self._alpha)
            self.setColor(c)

    def _on_alpha(self, v):
        if self._updating:
            return
        c = QColor(self._color)
        c.setAlpha(_pct_to_alpha(v))
        self._color = c
        self._alpha = c.alpha()
        self.preview.setColor(c)
        self.colorPicked.emit(QColor(c))

    def _refresh_palette(self, idx):
        idx = max(0, min(len(PALETTES) - 1, int(idx)))
        new = _PaletteGrid(PALETTES[idx][1], cols=_PAL_COLS,
                           cell=_PAL_CELL, parent=self.pal_holder)
        new.picked.connect(self._on_picked)
        self.pal_holder.set_grid(new)
        self.grid = new

    def _fill_recent(self):
        while self._recent_lay.count():
            it = self._recent_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        colors = _recent.load_colors()
        for hexs in colors[:12]:
            c = _ColorCell(hexs, 16, self.recent_box)
            c.picked.connect(self._on_picked)
            self._recent_lay.addWidget(c)
        if not colors:
            tip = GgsDimLabel("—")
            self._recent_lay.addWidget(tip)
        self._recent_lay.addStretch(1)

    def _on_picked(self, c):
        c = QColor(c)
        c.setAlpha(self._alpha)
        self.setColor(c)
        _recent.add_color(c)
        self.colorPicked.emit(QColor(self._color))
        if not self._embedded:
            self.close()

    def _open_dialog(self):
        c = GgsColorDialog.getColor(self._color, self, with_alpha=True,
                                    shape=self._shape)
        if c.isValid():
            self.setColor(c)
            self.colorPicked.emit(QColor(c))
            self.close()


class GgsColorDialog(GgsDialog):

    def __init__(self, initial=None, parent=None, with_alpha=True,
                 title=None, shape="rect"):
        super().__init__(parent)
        self.setObjectName("GgsColorDialog")
        self.setWindowTitle(title or _i18n.tr("选择颜色"))
        self.resize(496, 400)
        c = QColor(initial) if QColor(initial).isValid() else QColor("#FFFFFF")
        self._color = c
        self._with_alpha = bool(with_alpha)
        self._updating = False

        out = QVBoxLayout(self)
        out.setContentsMargins(12, 10, 12, 10)
        out.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)
        out.addLayout(body, 1)

        left = QVBoxLayout()
        left.setSpacing(6)
        self.sv = _SVSquare(self)
        self.sv.svChanged.connect(self._on_sv)
        left.addWidget(self.sv)
        self.hue = _HueBar(self)
        self.hue.hueChanged.connect(self._on_hue)
        left.addWidget(self.hue)
        body.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(6)

        r1 = QHBoxLayout()
        r1.setSpacing(6)
        r1.setAlignment(Qt.AlignmentFlag.AlignLeft
                        | Qt.AlignmentFlag.AlignVCenter)
        self.preview = _ColorPreview(c, self, size=(34, 24), shape=shape)
        r1.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignLeft)
        self.ed_hex = GgsColorHex(c.name().upper())
        self.ed_hex.setMaxLength(7)
        self.ed_hex.setToolTip(_i18n.tr("十六进制颜色，如 #1E88E5"))
        self.ed_hex.editingFinished.connect(self._on_hex)
        r1.addWidget(self.ed_hex, 0, Qt.AlignmentFlag.AlignLeft)
        right.addLayout(r1)

        nums = QGridLayout()
        nums.setContentsMargins(0, 0, 0, 0)
        nums.setHorizontalSpacing(8)
        nums.setVerticalSpacing(2)
        self.spn = []
        for _c, (_head, _full) in enumerate(
                (("R", _i18n.tr("红色")), ("G", _i18n.tr("绿色")),
                 ("B", _i18n.tr("蓝色")))):
            nums.addWidget(self._head(_head, _full), 0, _c)
            s = GgsColorSpin()
            s.setRange(0, 255)
            s.setToolTip(_full)
            s.valueChanged.connect(self._on_rgb)
            self.spn.append(s)
            nums.addWidget(s, 1, _c, Qt.AlignmentFlag.AlignLeft)

        self.spn_h = QSpinBox()
        self.spn_s = QSpinBox()
        self.spn_v = QSpinBox()
        for _c, (_head, _full, spn, tip, rng, suf) in enumerate((
                ("H", _i18n.tr("色相"), self.spn_h,
                 _i18n.tr("色相（0–359°）"), 359, "°"),
                ("S", _i18n.tr("饱和度"), self.spn_s,
                 _i18n.tr("饱和度（0–100%）"), 100, "%"),
                ("V", _i18n.tr("明度"), self.spn_v,
                 _i18n.tr("明度（0–100%）"), 100, "%"))):
            spn.setRange(0, rng)
            spn.setSuffix(suf)
            spn.setToolTip(tip)
            spn.setObjectName("GgsColorSpin")
            spn.valueChanged.connect(self._on_hsv)
            nums.addWidget(self._head(_head, tip), 2, _c)
            nums.addWidget(spn, 3, _c, Qt.AlignmentFlag.AlignLeft)
        for _c in range(3):
            nums.setColumnStretch(_c, 1)
        right.addLayout(nums)

        if self._with_alpha:
            ar = QHBoxLayout()
            ar.setSpacing(6)
            _tip_a = _i18n.tr(""
                              ""
                              "")
            lbl_a = self._cap(_i18n.tr("透明度"))
            lbl_a.setToolTip(_tip_a)
            ar.addWidget(lbl_a)
            self.alpha_row = GgsSliderSpin(self, 0, 100, " %")
            self.alpha_row.setToolTip(_tip_a)
            self.alpha_row.valueChanged.connect(self._on_alpha)
            ar.addWidget(self.alpha_row, 1)
            right.addLayout(ar)
        else:
            self.alpha_row = None

        self.cmb_palette = QComboBox()
        for t, _cols in PALETTES:
            self.cmb_palette.addItem(_i18n.tr(t))
        self.cmb_palette.currentIndexChanged.connect(self._refresh_palette)
        right.addWidget(self.cmb_palette)

        self.pal_holder = _PaletteHolder(self)
        self.grid = _PaletteGrid(PALETTES[0][1], cols=_PAL_COLS,
                                 cell=_PAL_CELL, parent=self.pal_holder)
        self.grid.picked.connect(self._on_picked)
        self.pal_holder.set_grid(self.grid)
        right.addWidget(self.pal_holder)
        right.addStretch(1)
        body.addLayout(right, 2)

        out.addWidget(self._dim(_i18n.tr("最近使用")))
        self.recent_box = QWidget(self)
        self._recent_lay = QHBoxLayout(self.recent_box)
        self._recent_lay.setContentsMargins(0, 0, 0, 0)
        self._recent_lay.setSpacing(2)
        out.addWidget(self.recent_box)
        self._fill_recent()

        btns = QHBoxLayout()
        self.btn_pick = QPushButton(_i18n.tr("取色"))
        self.btn_pick.setIcon(icons.icon("eyedropper", size=14))
        self.btn_pick.setIconSize(QSize(14, 14))
        self.btn_pick.setToolTip(_i18n.tr(
            "点它之后对话框会收起，在窗口上点一下即取该处颜色（Esc 取消）"))
        self.btn_pick.clicked.connect(self._start_pick)
        self.btn_pick.setEnabled(_canvas_of(self) is not None)
        self._pick_canvas = None
        btns.addWidget(self.btn_pick)
        btns.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        btns.addWidget(bb)
        out.addLayout(btns)

        self._push_to_ui()

    @staticmethod
    def _dim(text):
        lab = GgsDimLabel(text)
        return lab

    @staticmethod
    def _head(letter, tip):
        lab = GgsColorHead(str(letter))
        lab.setAlignment(Qt.AlignmentFlag.AlignLeft
                         | Qt.AlignmentFlag.AlignVCenter)
        lab.setToolTip(str(tip))
        return lab

    @staticmethod
    def _cap(text):
        lab = GgsColorCap(str(text))
        lab.setAlignment(Qt.AlignmentFlag.AlignRight
                         | Qt.AlignmentFlag.AlignVCenter)
        return lab

    def color(self):
        return QColor(self._color)

    def _push_to_ui(self):
        c = self._color
        self._updating = True
        try:
            self.preview.setColor(c)
            self.ed_hex.setText(c.name().upper())
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            for s, v in zip(self.spn, (r, g, b)):
                s.setValue(v)
            if self.alpha_row is not None:
                self.alpha_row.setValue(_alpha_to_pct(a))
            h, s, v, _a = c.getHsv()
            self.hue.setHue(max(0, h))
            self.sv.setHue(max(0, h))
            self.sv.setSV(s, v)
            self.spn_h.setValue(max(0, h))
            self.spn_s.setValue(round(max(0, s) * 100 / 255.0))
            self.spn_v.setValue(round(max(0, v) * 100 / 255.0))
        finally:
            self._updating = False

    def _set_color(self, c):
        if self._updating:
            return
        c = QColor(c)
        if not c.isValid():
            return
        c.setAlpha(self._color.alpha() if self._with_alpha else 255)
        self._color = c
        self._push_to_ui()

    def _on_hex(self):
        if self._updating:
            return
        t = str(self.ed_hex.text() or "").strip()
        c = QColor(t)
        if c.isValid():
            self._set_color(c)
        else:
            self.ed_hex.setText(self._color.name().upper())

    def _on_rgb(self, *_a):
        if self._updating:
            return
        c = QColor(self.spn[0].value(), self.spn[1].value(),
                   self.spn[2].value())
        c.setAlpha(self._color.alpha())
        self._color = c
        self._push_to_ui()

    def _on_alpha(self, v):
        if self._updating:
            return
        c = QColor(self._color)
        c.setAlpha(_pct_to_alpha(v))
        self._color = c
        self._push_to_ui()

    def _on_hue(self, h):
        if self._updating:
            return
        _h, s, v, a = self._color.getHsv()
        c = QColor.fromHsv(int(h), max(0, s), max(0, v))
        c.setAlpha(a)
        self._color = c
        self._push_to_ui()

    def _on_sv(self, s, v):
        if self._updating:
            return
        h = self.hue.hue()
        c = QColor.fromHsv(int(h), int(s), int(v))
        c.setAlpha(self._color.alpha())
        self._color = c
        self._push_to_ui()

    def _on_hsv(self, *_a):
        if self._updating:
            return
        c = QColor.fromHsv(int(self.spn_h.value()),
                           round(self.spn_s.value() * 255 / 100.0),
                           round(self.spn_v.value() * 255 / 100.0))
        c.setAlpha(self._color.alpha())
        self._color = c
        self._push_to_ui()

    def _on_picked(self, c):
        self._set_color(c)

    def _refresh_palette(self, idx):
        idx = max(0, min(len(PALETTES) - 1, int(idx)))
        new = _PaletteGrid(PALETTES[idx][1], cols=_PAL_COLS,
                           cell=_PAL_CELL, parent=self.pal_holder)
        new.picked.connect(self._on_picked)
        self.pal_holder.set_grid(new)
        self.grid = new

    def _fill_recent(self):
        while self._recent_lay.count():
            it = self._recent_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
        colors = _recent.load_colors()
        for hexs in colors[:12]:
            cell = _ColorCell(hexs, 16, self.recent_box)
            cell.picked.connect(self._on_picked)
            self._recent_lay.addWidget(cell)
        if not colors:
            self._recent_lay.addWidget(self._dim("—"))
        self._recent_lay.addStretch(1)

    def _start_pick(self):
        cv = _canvas_of(self)
        if cv is None:
            return
        self._pick_canvas = cv
        self.done(_PICK_CODE)



    @staticmethod
    def getColor(initial=None, parent=None, with_alpha=True, title=None,
                 shape="rect"):
        dlg = GgsColorDialog(initial, parent, with_alpha=with_alpha,
                             title=title, shape=shape)
        code = 0
        while True:
            code = dlg.exec()
            if code != _PICK_CODE:
                break
            cv = getattr(dlg, "_pick_canvas", None)
            dlg._pick_canvas = None
            if cv is None:
                code = 0
                break
            picked = pick_from_map(cv, dlg)
            if picked is None:
                try:
                    from ggis.common.base.dialog import GgsMsgBox
                    GgsMsgBox.information(
                        dlg.parentWidget(),
                        _i18n.tr("取色"),
                        _i18n.tr("地图当前被一个模态对话框挡住，取不到颜色。"
                                 "请先关掉它，再回到这里取色。"))
                except Exception:
                    _log.exception("silent exception in getColor")
            elif picked.isValid():
                dlg._set_color(picked)
        if code:
            _col = dlg.color()
            if _col.alpha():
                _recent.add_color(_col)
            return _col
        return QColor()


def popup_color(anchor, color, on_pick, with_alpha=True, shape="rect"):
    try:
        pop = GgsColorPopup(color, anchor, with_alpha=with_alpha,
                            shape=shape)
        pop.colorPicked.connect(on_pick)
        pop.adjustSize()
        gp = anchor.mapToGlobal(QPoint(0, anchor.height() + 2))
        try:
            scr = anchor.screen()
            if scr is not None:
                avail = scr.availableGeometry()
                hint = pop.sizeHint()
                if gp.y() + hint.height() > avail.bottom():
                    gp.setY(anchor.mapToGlobal(QPoint(0, 0)).y()
                            - hint.height() - 2)
        except Exception:
            _log.exception("silent exception in popup_color")
        pop.move(gp)
        pop.show()
        return pop
    except Exception:
        _log.exception("silent exception in popup_color")
        return None


class GgsColorButton(QToolButton):

    colorChanged = Signal(object)

    def __init__(self, parent=None, color="#FFFFFF", shape="rect"):
        super().__init__(parent)
        self.setObjectName("GgsColorButton")
        self._color = QColor(color)
        self._shape = shape
        self.clicked.connect(self._pick)
        self._repaint_icon()

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        self._color = QColor(color)
        self._repaint_icon()
        self.colorChanged.emit(self.color())

    def _pick(self):
        popup_color(self, self._color, self.setColor, with_alpha=True,
                    shape=self._shape)

    def _repaint_icon(self):
        name = self._color.name()
        if self._shape == "line":
            self.setIcon(icons.colored_line(name, 16))
        elif self._shape == "dot":
            self.setIcon(icons.colored_dot(name, 16))
        else:
            self.setIcon(icons.colored_rect(name, 16))


class GgsColorCap(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsColorCap")
class GgsColorHead(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsColorHead")
class GgsColorHex(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsColorHex")
class GgsColorSpin(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsColorSpin")
