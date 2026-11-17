# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import ctypes

TITLE_H = 32
WINCTL_W = 45

APP_NAME_PREFIX = "GmaGIS Desktop — "


_WIN_ICON_FAMILIES = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
_WIN_GLYPHS = {"min": "\ue921", "max": "\ue922",
               "restore": "\ue923", "close": "\ue8bb"}
_win_font_family = None


def _win_icon_family():
    global _win_font_family
    if _win_font_family is not None:
        return _win_font_family
    fam = ""
    try:
        from PySide6.QtGui import QFontDatabase
        have = set(QFontDatabase.families())
        for name in _WIN_ICON_FAMILIES:
            if name in have:
                fam = name
                break
    except Exception:
        exc_note("_win_icon_family @ ggis/ui/framework/titlebar.py:63")
        fam = ""
    _win_font_family = fam
    return fam


_GLYPH_TARGET_RATIO = 0.625
_glyph_scale_cache = {}


def _glyph_scale(family):
    key = str(family or "")
    if key in _glyph_scale_cache:
        return _glyph_scale_cache[key]
    ratio = 1.0
    try:
        probe = 64
        pm = QPixmap(probe * 2, probe * 2)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        f = QFont(key)
        f.setPixelSize(probe)
        p.setFont(f)
        p.setPen(QPen(QColor("#000000")))
        p.drawText(QRectF(0.0, 0.0, probe * 2.0, probe * 2.0),
                   int(Qt.AlignmentFlag.AlignCenter), _WIN_GLYPHS["max"])
        p.end()
        img = pm.toImage()
        top, bot = -1, -1
        for y in range(img.height()):
            hit = False
            for x in range(img.width()):
                if QColor(img.pixelColor(x, y)).alpha() > 8:
                    hit = True
                    break
            if hit:
                if top < 0:
                    top = y
                bot = y
        if top >= 0 and bot >= top:
            ratio = max(0.1, (bot - top + 1) / float(probe))
    except Exception:
        exc_note("_glyph_scale @ ggis/ui/framework/titlebar.py:119")
        ratio = 1.0
    _glyph_scale_cache[key] = _GLYPH_TARGET_RATIO / ratio
    return _glyph_scale_cache[key]


def _font_glyph(kind, dpr, size, color):
    fam = _win_icon_family()
    code = _WIN_GLYPHS.get(kind)
    if not fam or not code:
        return None
    try:
        dpr = float(dpr) or 1.0
    except Exception:
        exc_note("_font_glyph @ ggis/ui/framework/titlebar.py:133")
        dpr = 1.0
    try:
        pm = QPixmap(max(1, round(size * dpr)), max(1, round(size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        f = QFont(fam)
        try:
            scale = float(_glyph_scale(fam))
        except Exception:
            exc_note("_font_glyph @ ggis/ui/framework/titlebar.py:147")
            scale = 1.0
        f.setPixelSize(max(5, int(round(float(size) * scale))))
        p.setFont(f)
        p.setPen(QPen(color))
        p.drawText(QRectF(0.0, 0.0, float(size), float(size)),
                   int(Qt.AlignmentFlag.AlignCenter), code)
        p.end()
        return QIcon(pm)
    except Exception:
        exc_note("_font_glyph @ ggis/ui/framework/titlebar.py:156")
        return None


from PySide6.QtCore import (Qt, QSize, QEvent, QObject,
                              QRectF, QPointF)
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPen, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QWidget, QToolButton, QLabel, QSizePolicy, QHBoxLayout, QMenu,
)

from ggis.common.styling.icons import app_icon
from ggis.common.styling import themes
from ggis.core.app import i18n
from ggis.core.app import settings as _settings

_tr = i18n.tr


class _TitleDragMixin:

    _DRAG_THRESHOLD = 8

    def _drag_init(self):
        self._press = None
        self._last_click = None

    def _is_double_click(self, ts, pos):
        last = self._last_click
        if last is None:
            return False
        try:
            sh = QApplication.styleHints()
            interval = sh.mouseDoubleClickInterval()
            dist = max(12, sh.mouseDoubleClickDistance() * 2)
        except Exception:
            exc_note("_is_double_click @ ggis/ui/framework/titlebar.py:203")
            interval, dist = 400, 12
        elapsed = ts - last[0]
        return 0 <= elapsed <= interval and \
            (pos - last[1]).manhattanLength() <= dist

    def _handle_press(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            self._press = None
            return False
        pos = e.position().toPoint()
        if self.childAt(pos) is not None:
            self._press = None
            self._last_click = None
            return False
        if self._is_double_click(e.timestamp(), pos):
            self._last_click = None
            self._press = None
            self._toggle_max()
            return True
        self._last_click = (e.timestamp(), pos)
        self._press = pos
        return False

    def _handle_move(self, e):
        if (self._press is not None
                and e.buttons() & Qt.MouseButton.LeftButton):
            d = e.position().toPoint() - self._press
            if d.manhattanLength() >= self._DRAG_THRESHOLD:
                self._press = None
                self._last_click = None
                h = self.mainwin.windowHandle()
                if h is not None:
                    h.startSystemMove()

    def _handle_release(self, e):
        self._press = None


class _DragHost(_TitleDragMixin, QWidget):

    def __init__(self, titlebar):
        super().__init__(titlebar)
        self._tb = titlebar
        self._drag_init()

    @property
    def mainwin(self):
        return self._tb.mainwin

    def _toggle_max(self):
        self._tb._toggle_max()

    def mousePressEvent(self, e):
        self._handle_press(e)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        self._handle_move(e)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._handle_release(e)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._press = None
        self._last_click = None
        if self.childAt(e.position().toPoint()) is None:
            self._tb._toggle_max()
        super().mouseDoubleClickEvent(e)


class EdgeGrip(QWidget):

    _CURSOR = {
        Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
        Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
        Qt.Edge.LeftEdge | Qt.Edge.TopEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.RightEdge | Qt.Edge.BottomEdge: Qt.CursorShape.SizeFDiagCursor,
        Qt.Edge.TopEdge | Qt.Edge.RightEdge: Qt.CursorShape.SizeBDiagCursor,
        Qt.Edge.BottomEdge | Qt.Edge.LeftEdge: Qt.CursorShape.SizeBDiagCursor,
    }

    def __init__(self, edges, mainwin):
        super().__init__(mainwin)
        self._edges = edges
        self._win = mainwin
        try:
            self.setCursor(self._CURSOR[edges])
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/titlebar.py:304")
            self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            h = self._win.windowHandle()
            if h is not None:
                h.startSystemResize(self._edges)
        super().mousePressEvent(e)


class _GripRaiseFilter(QObject):

    def __init__(self, win):
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t in (QEvent.Type.Show, QEvent.Type.ZOrderChange):
                from PySide6.QtWidgets import QDockWidget
                if isinstance(obj, QDockWidget):
                    _dr = getattr(self._win, "dock_region", None)
                    if _dr is not None:
                        _dr._name_dock_tabbars()
                        _dr._raise_grips()
                        try:
                            _dr._layout_separators()
                        except Exception:
                            exc_note("eventFilter @ ggis/ui/framework/titlebar.py:349")
                            pass
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/titlebar.py:351")
            pass
        return False


class _DockActiveFilter(QObject):

    def __init__(self, win):
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t in (QEvent.Type.MouseButtonPress,
                     QEvent.Type.MouseButtonDblClick):
                if (t == QEvent.Type.MouseButtonPress
                        and ev.button() == Qt.MouseButton.LeftButton
                        and isinstance(obj, QWidget)
                        and obj.window() is self._win):
                    try:
                        _gp = ev.globalPosition().toPoint()
                        if self._win.ctx.region("dock")._sep_drag_begin(
                                self._win.mapFromGlobal(_gp)):
                            return False
                    except Exception:
                        exc_note("eventFilter @ ggis/ui/framework/titlebar.py:400")
                        pass
                from ggis.ui.framework.docks import GgsDockWidget
                w = obj
                while (isinstance(w, QWidget)
                       and not isinstance(w, GgsDockWidget)):
                    w = w.parentWidget()
                if w is None or isinstance(w, GgsDockWidget):
                    self._win.ctx.region("dock")._set_active_dock(w)
            elif t == QEvent.Type.MouseMove:
                try:
                    gp = ev.globalPosition().toPoint()
                except Exception:
                    exc_note("eventFilter @ ggis/ui/framework/titlebar.py:410")
                    gp = None
                if gp is not None:
                    if getattr(self._win, "_sep_dragging", None) is not None:
                        try:
                            self._win.ctx.region("dock")._sep_drag_move(
                                self._win.mapFromGlobal(gp))
                        except Exception:
                            exc_note("eventFilter @ ggis/ui/framework/titlebar.py:417")
                            pass
                    else:
                        try:
                            self._win.ctx.region("dock")._sep_hover(gp)
                        except Exception:
                            exc_note("eventFilter @ ggis/ui/framework/titlebar.py:432")
                            pass
            elif t == QEvent.Type.MouseButtonRelease:
                if getattr(self._win, "_sep_dragging", None) is not None:
                    try:
                        self._win.ctx.region("dock")._sep_drag_end()
                    except Exception:
                        exc_note("eventFilter @ ggis/ui/framework/titlebar.py:425")
                        pass
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/titlebar.py:427")
            pass
        return False


def win_glyph(kind, dpr=1.0, size=16, color=None):
    if color:
        qc = QColor(color)
    else:
        qc = None
        try:
            qc = QColor(themes.theme_colors(
                _settings.get("theme")).get("text"))
        except Exception:
            exc_note("win_glyph @ ggis/ui/framework/titlebar.py:476")
            qc = None
        if qc is None or not qc.isValid():
            try:
                qc = QColor("#1a2230" if _settings.get("theme") == "light"
                            else "#f0f2f5")
            except Exception:
                exc_note("win_glyph @ ggis/ui/framework/titlebar.py:483")
                qc = QColor("#19232D")
    if not qc.isValid():
        qc = QColor("#19232D")

    by_font = _font_glyph(kind, dpr, size, qc)
    if by_font is not None:
        return by_font

    try:
        dpr = float(dpr) or 1.0
    except Exception:
        exc_note("win_glyph @ ggis/ui/framework/titlebar.py:496")
        dpr = 1.0
    pm = QPixmap(max(1, round(size * dpr)), max(1, round(size * dpr)))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    u = 10.0
    x0 = (size - u) / 2.0
    y0 = (size - u) / 2.0
    p.setPen(QPen(qc, 1.0))
    p.setRenderHint(QPainter.RenderHint.Antialiasing, kind == "close")
    if kind == "min":
        p.drawLine(QPointF(x0, size - 4.5), QPointF(x0 + u, size - 4.5))
    elif kind == "max":
        p.drawRect(QRectF(x0 + 0.5, y0 + 0.5, u - 1, u - 1))
    elif kind == "restore":
        p.drawRect(QRectF(x0 + 0.5, y0 + 3.5, 6.0, 6.0))
        p.drawLine(QPointF(x0 + 3.5, y0 + 0.5), QPointF(x0 + u + 0.5,
                                                        y0 + 0.5))
        p.drawLine(QPointF(x0 + u + 0.5, y0 + 0.5),
                   QPointF(x0 + u + 0.5, y0 + 7.5))
    elif kind == "close":
        p.drawLine(QPointF(x0 + 0.5, y0 + 0.5), QPointF(x0 + u - 0.5,
                                                        y0 + u - 0.5))
        p.drawLine(QPointF(x0 + u - 0.5, y0 + 0.5), QPointF(x0 + 0.5,
                                                            y0 + u - 0.5))
    p.end()
    return QIcon(pm)


class _WinCloseButton(QToolButton):

    def __init__(self, bar):
        super().__init__()
        self._bar = bar

    def repaint_glyph(self):
        try:
            self.setIcon(self._bar._glyph(
                "close", color="#ffffff" if self.underMouse() else None))
        except Exception:
            exc_note("repaint_glyph @ ggis/ui/framework/titlebar.py:554")
            pass

    def enterEvent(self, e):
        self.repaint_glyph()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.repaint_glyph()
        super().leaveEvent(e)


class TitleBar(_TitleDragMixin, QWidget):

    def __init__(self, mainwin, search=None):
        super().__init__(mainwin)
        self.setObjectName("GgsTitleBar")
        self.mainwin = mainwin
        self.setFixedHeight(TITLE_H)
        self._drag_init()

        left = _DragHost(self)
        left.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        left.setMinimumWidth(280)
        lh = QHBoxLayout(left)
        lh.setContentsMargins(15, 0, 0, 0)
        lh.setSpacing(4)
        self._icon = QLabel()
        _pm = app_icon().pixmap(256, 256)
        _pm.setDevicePixelRatio(256 / 18.0)
        self._icon.setPixmap(_pm)
        self._icon.setFixedSize(24, 24)
        lh.addWidget(self._icon)
        from ggis.common.widgets.buttons import GgsSwitch
        auto_host = QWidget(left)
        auto_host.setObjectName("GgsAutoSaveHost")
        ah = QHBoxLayout(auto_host)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(5)
        auto_lbl = QLabel(_tr("自动保存"), auto_host)
        auto_lbl.setObjectName("GgsAutoSaveLabel")
        _f = auto_lbl.font()
        _f.setPointSizeF(9.0)
        auto_lbl.setFont(_f)
        ah.addWidget(auto_lbl)
        _auto_act = mainwin.ctx.svc("actions").get("auto_save_toggle")
        self._auto_save_switch = GgsSwitch(
            checked=bool(_auto_act.isChecked()), parent=auto_host,
            on_toggle=self._on_auto_save_switch_toggled)
        self._auto_save_switch.setFixedSize(30, 16)
        self._auto_save_switch.setToolTip(
            _tr("自动保存"))
        ah.addWidget(self._auto_save_switch)
        self._auto_save_host = auto_host
        lh.addWidget(auto_host)

        self._qat_buttons = []
        for n in ("save_project", "undo_layer", "redo_layer", "reset_window"):
            b = GgsTitleBtn()
            b.setDefaultAction(mainwin.ctx.svc("actions").get(n))
            b.setAutoRaise(True)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            b.setContentsMargins(0, 0, 0, 0)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setFixedSize(32, TITLE_H - 8)
            b.setIconSize(QSize(18, 18))
            self._qat_buttons.append(b)
            lh.addWidget(b)
        self._title = GgsProjectBtn()
        _title_text = mainwin.windowTitle() or _tr("未命名工程")
        if _title_text.startswith(APP_NAME_PREFIX):
            _title_text = _title_text[len(APP_NAME_PREFIX):]
        self._title.setText(_title_text)
        self._title.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self._title.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._title.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._title.setToolTip(_tr("当前工程"))
        self._title.setFixedHeight(TITLE_H - 8)
        self._set_project_chevron()
        lh.addSpacing(4)
        f = self._title.font()
        f.setPointSizeF(max(f.pointSizeF(), 9.5))
        f.setBold(True)
        self._title.setFont(f)
        lh.addWidget(self._title)
        lh.addStretch(1)

        self._search = search

        right = _DragHost(self)
        rh = QHBoxLayout(right)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(0)
        _WINCTL_W = WINCTL_W
        self._min = GgsWinBtn()
        self._min.setIcon(self._glyph("min"))
        self._min.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._min.setFixedSize(_WINCTL_W, TITLE_H)
        self._min.setToolTip(_tr("最小化"))
        self._min.clicked.connect(mainwin.showMinimized)
        self._max = GgsWinBtn()
        self._max.setIcon(self._glyph("max"))
        self._max.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._max.setFixedSize(_WINCTL_W, TITLE_H)
        self._max.setToolTip(_tr("最大化"))
        self._max.clicked.connect(self._toggle_max)
        self._max.setProperty("hot", False)
        self._close = _WinCloseButton(self)
        self._close.setObjectName("GgsWinClose")
        self._close.setIcon(self._glyph("close"))
        self._close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close.setFixedSize(_WINCTL_W, TITLE_H)
        self._close.setToolTip(_tr("关闭"))
        self._close.clicked.connect(mainwin.close)
        rh.addWidget(self._min)
        rh.addWidget(self._max)
        rh.addWidget(self._close)

        body = QHBoxLayout(self)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(left, 1)
        if self._search is not None:
            self._search.setParent(self)
            body.addWidget(self._search, 0, Qt.AlignmentFlag.AlignVCenter)
        gap = _DragHost(self)
        gap.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        body.addWidget(gap, 1)
        body.addWidget(right)
        self._left, self._right = left, right

    def resizeEvent(self, e):
        super().resizeEvent(e)
        try:
            sw = self._search.width() if self._search is not None else 0
            self._left.setFixedWidth(max(280, (self.width() - sw) // 2))
        except Exception:
            exc_note("resizeEvent @ ggis/ui/framework/titlebar.py:753")
            pass

    def set_project_menu(self, menu):
        self._title.setMenu(menu)

    def _on_auto_save_switch_toggled(self, on):
        try:
            from ggis.core.app import settings as _st
            _st.set("auto_save_enabled", bool(on))
            a = self.mainwin.ctx.svc("actions").get("auto_save_toggle")
            if a.isChecked() != bool(on):
                a.setChecked(bool(on))
        except Exception:
            import logging
            logging.getLogger("gmagis").exception(
                "silent exception in _on_auto_save_switch_toggled")

    def _set_project_chevron(self):
        try:
            self._title.setIcon(QIcon())
        except Exception:
            exc_note("_set_project_chevron @ ggis/ui/framework/titlebar.py:790")
            pass

    def _glyph(self, kind, color=None):
        try:
            dpr = float(self.devicePixelRatioF()) or 1.0
        except Exception:
            exc_note("_glyph @ ggis/ui/framework/titlebar.py:809")
            dpr = 1.0
        return win_glyph(kind, dpr, 16, color)

    def retheme(self):
        self.refresh_icons()

    def refresh_icons(self):
        self._min.setIcon(self._glyph("min"))
        kind = "restore" if self.mainwin.isMaximized() else "max"
        self._max.setIcon(self._glyph(kind))
        self._max.setToolTip(_tr("向下还原") if self.mainwin.isMaximized()
                             else _tr("最大化"))
        self._close.repaint_glyph()
        self._set_project_chevron()

    def mousePressEvent(self, e):
        if self._handle_press(e):
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        self._handle_move(e)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._handle_release(e)
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._press = None
        self._last_click = None
        if self.childAt(e.position().toPoint()) is None:
            self._toggle_max()
        super().mouseDoubleClickEvent(e)

    def _toggle_max(self):
        mw = self.mainwin
        if mw.isMaximized():
            mw.showNormal()
            self._max.setIcon(self._glyph("max"))
            self._max.setToolTip(_tr("最大化"))
        else:
            mw.showMaximized()
            self._max.setIcon(self._glyph("restore"))
            self._max.setToolTip(_tr("向下还原"))



class _PopupRoundFilter(QObject):

    def eventFilter(self, obj, ev):
        try:
            t = ev.type()
            if t not in (QEvent.Type.Polish, QEvent.Type.Show):
                return False
            cls = obj.metaObject().className()
            if cls == "QComboBoxPrivateContainer":
                self._translucent(obj)
                if t == QEvent.Type.Show:
                    self._disable_sys_round(obj)
            elif cls == "QTipLabel":
                self._translucent(obj)
            elif isinstance(obj, QMenu):
                self._translucent(obj)
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/titlebar.py:891")
            pass
        return False

    @staticmethod
    def _translucent(w):
        if not w.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground):
            w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    @staticmethod
    def _disable_sys_round(w):
        hwnd = int(w.winId())
        pref = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 33,
            ctypes.byref(pref), ctypes.sizeof(pref))


class GgsProjectBtn(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsProjectBtn")
class GgsTitleBtn(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsTitleBtn")
class GgsWinBtn(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsWinBtn")
