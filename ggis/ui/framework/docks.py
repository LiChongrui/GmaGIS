# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QEvent, QObject, QSize, Signal
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QCursor
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ggis.common.styling import icons, themes
from ggis.core.app import i18n
from ggis.core.app import settings as _settings
from ggis.common.base.dialog import GgsDockTitleBtn
from ggis.common.base.dialog import GgsDockTitleLabel


def _norm_uri_path(p):
    import os as _os
    try:
        return _os.path.normcase(_os.path.abspath(str(p or "")))
    except Exception:
        exc_note("_norm_uri_path @ ggis/ui/framework/docks.py:42")
        return str(p or "")

_TITLE_MIN_H = 28


def title_bar_height(widget):
    try:
        fm = int(widget.fontMetrics().height())
    except Exception:
        exc_note("title_bar_height @ ggis/ui/framework/docks.py:62")
        fm = 16
    return max(int(_TITLE_MIN_H), fm + 16)


def sync_title_bar_height(obj, attr="_fixed_h", extra=0):
    h = int(title_bar_height(obj)) + int(extra)
    if int(getattr(obj, attr, -1)) == h:
        return False
    setattr(obj, attr, h)
    try:
        obj.setFixedHeight(h)
        obj.updateGeometry()
    except Exception:
        exc_note("sync_title_bar_height @ ggis/ui/framework/docks.py:88")
        pass
    return True
_BAR_FALLBACK = "#8a929e"


def _bar_color():
    try:
        c = QColor(themes.text_dim(_settings.get("theme")))
        if c.isValid():
            return c
    except Exception:
        exc_note("_bar_color @ ggis/ui/framework/docks.py:102")
        pass
    return QColor(_BAR_FALLBACK)


class GgsDockTitleBar(QWidget):

    def __init__(self, dock):
        super().__init__(dock)
        self.dock = dock
        self.setObjectName("GgsDockTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._fixed_h = int(title_bar_height(dock))
        self.setFixedHeight(self._fixed_h)

        self.label = GgsDockTitleLabel(dock.windowTitle() or "")

        self.btn_float = GgsDockTitleBtn()
        self.btn_float.setAutoRaise(True)
        self.btn_float.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_float.setToolTip(i18n.tr("浮动 / 取消浮动"))
        try:
            icons.bind(self.btn_float, "fullscreen", size=14)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/docks.py:147")
            self.btn_float.setText("▢")
        self.btn_float.clicked.connect(self._toggle_float)

        self.btn_close = GgsDockTitleBtn()
        self.btn_close.setAutoRaise(True)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip(i18n.tr("关闭面板"))
        try:
            icons.bind(self.btn_close, "dock_close", size=14)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/docks.py:161")
            self.btn_close.setText("✕")
        self.btn_close.clicked.connect(dock.close)

        for b in (self.btn_float, self.btn_close):
            b.setFixedSize(QSize(20, 20))
        b.setIconSize(QSize(14, 14))

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 6, 0)
        lay.setSpacing(4)
        lay.addWidget(self.label)
        lay.addStretch(1)
        lay.addWidget(self.btn_float, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignVCenter)

    def _sync_height(self):
        try:
            sync_title_bar_height(self, "_fixed_h")
        except Exception:
            exc_note("_sync_height @ ggis/ui/framework/docks.py:193")
            pass

    def changeEvent(self, e):
        try:
            if e.type() in (QEvent.Type.FontChange,
                            QEvent.Type.ApplicationFontChange):
                self._sync_height()
        except Exception:
            exc_note("changeEvent @ ggis/ui/framework/docks.py:202")
            pass
        super().changeEvent(e)

    def showEvent(self, e):
        try:
            self._sync_height()
        except Exception:
            exc_note("showEvent @ ggis/ui/framework/docks.py:210")
            pass
        super().showEvent(e)

    def set_title_text(self, text):
        try:
            self.label.setText(text or "")
        except Exception:
            exc_note("set_title_text @ ggis/ui/framework/docks.py:219")
            pass

    def set_title(self, title):
        self.label.setText(title or "")

    def sizeHint(self):
        return QSize(self.width() or 100, self._fixed_h)

    def minimumSizeHint(self):
        return QSize(60, self._fixed_h)

    def _toggle_float(self):
        try:
            self.dock.setFloating(not self.dock.isFloating())
        except Exception:
            exc_note("_toggle_float @ ggis/ui/framework/docks.py:242")
            pass

    def paintEvent(self, e):
        super().paintEvent(e)
        try:
            pal = themes.theme_colors(_settings.get("theme"))
            p = QPainter(self)
            c = _bar_color()
            h = self.height()
            p.fillRect(6, max(2, (h - 12) // 2), 3, min(12, h - 4), c)
            sep = QColor(pal.get("border_soft") or "#e3e5e8")
            w = self.width()
            p.fillRect(2, h - 1, max(0, w - 4), 1, sep)
            p.end()
        except Exception:
            exc_note("paintEvent @ ggis/ui/framework/docks.py:274")
            pass

    def contextMenuEvent(self, e):
        e.accept()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._toggle_float()
            e.accept()
            return
        super().mouseDoubleClickEvent(e)


class GgsDockWidget(QDockWidget):

    frontChanged = Signal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._body = None
        self._wrapped = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._main_win = self.parentWidget()
        try:
            self.topLevelChanged.connect(self._on_top_level_changed)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/docks.py:326")
            pass
        try:
            self._title_widget = GgsDockTitleBar(self)
            self.setTitleBarWidget(self._title_widget)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/docks.py:332")
            self._title_widget = None

    def _on_top_level_changed(self, floating):
        try:
            if floating:
                self.raise_()
                try:
                    self.activateWindow()
                except Exception:
                    exc_note("_on_top_level_changed @ ggis/ui/framework/docks.py:352")
                    pass
                return
            mw = getattr(self, "_main_win", None)
            if not self.isHidden():
                return
            if mw is None or not mw.isVisible():
                return
            if not getattr(mw, "_layout_restored", False):
                return
            self.show()
        except Exception:
            exc_note("_on_top_level_changed @ ggis/ui/framework/docks.py:363")
            pass

    def _is_active(self):
        mw = getattr(self, "_main_win", None)
        if mw is not None and hasattr(mw, "_active_dock"):
            return mw._active_dock is self
        return False

    def set_short_title(self, short):
        full = self.windowTitle()
        self.setWindowTitle(i18n.tr(short))
        tw = getattr(self, "_title_widget", None)
        if tw is not None:
            try:
                tw.set_title_text(full)
            except Exception:
                exc_note("set_short_title @ ggis/ui/framework/docks.py:389")
                pass
        self._full_title = full

    def full_title(self):
        return getattr(self, "_full_title", None) or self.windowTitle()

    def set_title_label(self, text):
        tw = getattr(self, "_title_widget", None)
        if tw is not None:
            try:
                tw.set_title_text(text)
            except Exception:
                exc_note("set_title_label @ ggis/ui/framework/docks.py:411")
                pass
        self._full_title = text

    def _card_path(self, rect, r):
        p = QPainterPath()
        p.addRoundedRect(rect, r, r)
        return p

    def paintEvent(self, e):
        try:
            pal = themes.theme_colors(_settings.get("theme"))
            if self._is_active():
                border = pal.get("dock_active") or pal.get("focus") \
                    or pal["border"]
            elif self.underMouse():
                border = pal.get("dock_hover") or pal["border"]
            else:
                border = pal["border"]
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = self._card_path(
                QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0), 6)
            p.fillPath(path, QColor(pal["panel"]))
            p.setPen(QColor(border))
            p.drawPath(path)
            p.end()
        except Exception:
            exc_note("paintEvent @ ggis/ui/framework/docks.py:463")
            pass

    def setWidget(self, widget):
        self._wrapped = widget
        body = GgsDockBody(self)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(2, 0, 2, 3)
        lay.setSpacing(0)
        if widget is not None:
            lay.addWidget(widget)
        self._body = body
        super().setWidget(body)

    def widget(self):
        return self._wrapped

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        tb = getattr(self, "_title_widget", None)
        if tb is not None:
            try:
                tb.set_title(title)
            except Exception:
                exc_note("setWindowTitle @ ggis/ui/framework/docks.py:507")
                pass


class UriDropFilter(QObject):

    def __init__(self, window):
        super().__init__(window)
        self.win = window

    def eventFilter(self, obj, e):
        t = e.type()
        if t not in (QEvent.Type.DragEnter, QEvent.Type.DragMove,
                     QEvent.Type.Drop):
            return False
        try:
            src = e.source()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/docks.py:535")
            src = None
        if src is not None:
            try:
                from ggis.ui.panels.layertree import GgsLayerTreeView
                if isinstance(src, GgsLayerTreeView):
                    return False
            except Exception:
                exc_note("eventFilter @ ggis/ui/framework/docks.py:543")
                pass
        try:
            mime = e.mimeData()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/docks.py:547")
            return False

        try:
            had_layers = bool(self.win.has_layers())
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/docks.py:556")
            had_layers = True

        try:
            has_files = mime.hasUrls()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/docks.py:561")
            has_files = False
        if not has_files:
            return False
        if t != QEvent.Type.Drop:
            e.acceptProposedAction()
            return True
        try:
            urls = list(mime.urls())
            paths = [(u.toLocalFile() or u.toString()) for u in urls]
            view = None
            local = None
            try:
                _vv = self.win.layer_dock.view
                local = _vv.viewport().mapFromGlobal(QCursor.pos())
                if _vv.viewport().rect().contains(local):
                    view = _vv
            except Exception:
                exc_note("eventFilter @ ggis/ui/framework/docks.py:582")
                view = None
            slot = None
            if view is not None:
                try:
                    slot = view.drop_slot_at(local)
                except Exception:
                    exc_note("eventFilter @ ggis/ui/framework/docks.py:588")
                    slot = None
            try:
                self.win.layer_dock.set_pending_drop(
                    paths,
                    slot[0] if slot else None,
                    slot[1] if slot else 0)
            except Exception:
                exc_note("eventFilter @ ggis/ui/framework/docks.py:595")
                pass
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/docks.py:597")
            pass
        try:
            _urls = list(mime.urls())
            _local = [u.toLocalFile() or u.toString() for u in _urls]
            _line_paths = set()
            _lines = []
            try:
                _raw = mime.data("application/x-ggis-uri")
                if _raw is not None and _raw.data():
                    for _ln in bytes(_raw.data()).decode(
                            "utf-8", "replace").splitlines():
                        _ln = _ln.strip()
                        if not _ln:
                            continue
                        _lines.append(_ln)
                        try:
                            _line_paths.add(_norm_uri_path(
                                _ln.split("|", 1)[0]))
                        except Exception:
                            exc_note("eventFilter @ ggis/ui/framework/docks.py:625")
                            pass
            except Exception:
                exc_note("eventFilter @ ggis/ui/framework/docks.py:627")
                _lines = []
            _single = (len([p for p in _local
                            if p and _norm_uri_path(p) not in _line_paths])
                       + len(_lines)) == 1
            added = 0
            for ln in reversed(_lines):
                try:
                    p, name = ln.split("|", 1)
                except ValueError:
                    exc_note("eventFilter @ ggis/ui/framework/docks.py:636")
                    continue
                if p and self.win.ctx.svc("views")._on_view_method(
                        "add_uri_layer_from_db", p, name, _single):
                    added += 1
            for path in reversed(_local):
                if not path or "|" in path:
                    continue
                try:
                    if _norm_uri_path(path) in _line_paths:
                        continue
                except Exception:
                    exc_note("eventFilter @ ggis/ui/framework/docks.py:647")
                    pass
                if self.win.ctx.svc("views")._on_view_method(
                        "add_uri_layer", path, _single):
                    added += 1
            if added:
                if not had_layers:
                    self.win._forward_to_map_view("zoom_full")
                self.win.show_message(
                    i18n.tr("已拖入 {} 个图层").format(added),
                    self.win.LEVEL_SUCCESS)
            e.acceptProposedAction()
        except Exception as err:
            exc_note("eventFilter @ ggis/ui/framework/docks.py:659")
            self.win.log("[错误] 拖放添加数据失败：{}".format(err))
        return True


class GgsDockBody(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsDockBody")
