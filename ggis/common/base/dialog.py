# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QEvent, Qt, QSize
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ggis.common.styling import icons, themes
from ggis.core.app import i18n
from ggis.core.app import settings as _settings
from PySide6.QtWidgets import QToolButton

_TITLE_H = 32


_RESIZE_MARGIN = 6

_RS_CURSOR = {
    1: Qt.CursorShape.SizeHorCursor,
    4: Qt.CursorShape.SizeHorCursor,
    2: Qt.CursorShape.SizeVerCursor,
    8: Qt.CursorShape.SizeVerCursor,
    3: Qt.CursorShape.SizeFDiagCursor,
    9: Qt.CursorShape.SizeFDiagCursor,
    6: Qt.CursorShape.SizeBDiagCursor,
    12: Qt.CursorShape.SizeBDiagCursor,
}


class GgsDialogTitleBar(QWidget):

    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog
        self.setObjectName("GgsDialogTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(_TITLE_H)

        self.label = GgsDockTitleLabel(dialog.windowTitle() or "", self)
        try:
            dialog.windowTitleChanged.connect(
                lambda t: self.label.setText(t or ""))
        except Exception:
            exc_note("__init__ @ ggis/common/base/dialog.py:93")
            pass

        self.btn_close = GgsDockTitleBtn(self)
        self.btn_close.setAutoRaise(True)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip(i18n.tr("关闭"))
        try:
            from ggis.ui.framework.titlebar import win_glyph
            self.btn_close.setIcon(
                win_glyph("close", self.devicePixelRatioF(), 16))
        except Exception:
            exc_note("__init__ @ ggis/common/base/dialog.py:109")
            try:
                icons.bind(self.btn_close, "dock_close", size=14)
            except Exception:
                exc_note("__init__ @ ggis/common/base/dialog.py:112")
                self.btn_close.setText("✕")
        self.btn_close.setFixedSize(QSize(28, 26))
        self.btn_close.setIconSize(QSize(16, 16))
        self.btn_close.clicked.connect(dialog.reject)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(4)
        self.icon = QLabel(self)
        self.icon.setObjectName("GgsDialogTitleIcon")
        self.icon.setFixedSize(QSize(16, 16))
        self.icon.setVisible(False)
        self._sync_icon()
        try:
            dialog.windowIconChanged.connect(
                lambda *_: self._sync_icon())
        except Exception:
            exc_note("__init__ @ ggis/common/base/dialog.py:135")
            pass
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.label)
        lay.addStretch(1)
        lay.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignVCenter)

    def _sync_icon(self):
        try:
            ic = self.dialog.windowIcon()
            ok = ic is not None and not ic.isNull()
            if ok:
                self.icon.setPixmap(ic.pixmap(QSize(16, 16)))
            if self.icon.parent() is not None:
                self.icon.setVisible(bool(ok))
        except Exception:
            exc_note("_sync_icon @ ggis/common/base/dialog.py:154")
            self.icon.setVisible(False)

    def sizeHint(self):
        return QSize(self.width() or 200, _TITLE_H)

    def minimumSizeHint(self):
        return QSize(60, _TITLE_H)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            try:
                win = self.dialog.window().windowHandle()
                if win is not None:
                    win.startSystemMove()
                    e.accept()
                    return
            except Exception:
                exc_note("mousePressEvent @ ggis/common/base/dialog.py:172")
                pass
        super().mousePressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        try:
            pal = themes.theme_colors(_settings.get("theme"))
            p = QPainter(self)
            w = self.width()
            p.fillRect(0, self.height() - 1, w, 1,
                       QColor(pal.get("border_soft") or "#e3e5e8"))
            p.end()
        except Exception:
            exc_note("paintEvent @ ggis/common/base/dialog.py:188")
            pass


class GgsFramelessMixin:

    def _setup_frameless(self):
        self.setObjectName("GgsDialog")
        self._title_installed = False
        self._title_bar = None
        self._pre_warmed = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,
                          True)
        try:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        except Exception:
            exc_note("_setup_frameless @ ggis/common/base/dialog.py:210")
            pass
        self._rs_edges = None
        self.setMouseTracking(True)
        self.installEventFilter(self)

    def setVisible(self, visible):
        placed = False
        if visible:
            self._install_title_bar()
            placed = self._pre_place_before_show()
            self._pre_warm_once()
        super().setVisible(visible)
        if placed:
            try:
                self.setAttribute(Qt.WidgetAttribute.WA_Moved, False)
            except Exception:
                exc_note("setVisible @ ggis/common/base/dialog.py:246")
                pass

    def _pre_place_before_show(self):
        try:
            if not self.testAttribute(Qt.WidgetAttribute.WA_Resized):
                self.adjustSize()
            if self.testAttribute(Qt.WidgetAttribute.WA_Moved):
                return False
            sz = self.size()
            parent = self.parentWidget()
            if parent is not None:
                c = parent.window().frameGeometry().center()
            else:
                c = QApplication.primaryScreen().availableGeometry().center()
            x = c.x() - sz.width() // 2
            y = c.y() - sz.height() // 2
            scr = QApplication.screenAt(c) or QApplication.primaryScreen()
            av = scr.availableGeometry()
            x = max(av.left(), min(x, av.left() + av.width() - sz.width()))
            y = max(av.top(), min(y, av.top() + av.height() - sz.height()))
            self.move(x, y)
            return True
        except Exception:
            exc_note("_pre_place_before_show @ ggis/common/base/dialog.py:300")
            return False

    def _pre_warm_once(self):
        if getattr(self, "_pre_warmed", False):
            return
        self._pre_warmed = True
        try:
            self.ensurePolished()
            lay = self.layout()
            if lay is not None:
                lay.activate()
            self.grab()
        except Exception:
            exc_note("_pre_warm_once @ ggis/common/base/dialog.py:330")
            pass

    def _install_title_bar(self):
        if self._title_installed:
            return
        self._title_installed = True
        self._title_bar = GgsDialogTitleBar(self)

        outer = QVBoxLayout()
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(self._title_bar)

        old = self.layout()
        if old is not None:
            body = QWidget()
            body.setObjectName("GgsDialogBody")
            body.setLayout(old)
            outer.addWidget(body, 1)
        self.setLayout(outer)

    def _rs_edges_at(self, pos):
        m = _RESIZE_MARGIN
        r = self.rect()
        e = 0
        if pos.x() <= m:
            e |= 1
        elif pos.x() >= r.width() - m:
            e |= 4
        if pos.y() <= m:
            e |= 2
        elif pos.y() >= r.height() - m:
            e |= 8
        return e or None

    def eventFilter(self, obj, ev):
        if obj is self and getattr(self, "_title_installed", False):
            try:
                t = ev.type()
                if t == QEvent.Type.MouseMove:
                    e = self._rs_edges_at(ev.position().toPoint())
                    self.setCursor(_RS_CURSOR.get(
                        e or 0, Qt.CursorShape.ArrowCursor))
                elif (t == QEvent.Type.MouseButtonPress
                        and ev.button() == Qt.MouseButton.LeftButton):
                    e = self._rs_edges_at(ev.position().toPoint())
                    if e is not None:
                        wh = self.windowHandle()
                        if wh is not None:
                            wh.startSystemResize(Qt.Edge(e))
                            return True
            except Exception:
                exc_note("eventFilter @ ggis/common/base/dialog.py:389")
                pass
        return super().eventFilter(obj, ev)

    def paintEvent(self, e):
        try:
            pal = themes.theme_colors(_settings.get("theme"))
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            path.addRoundedRect(
                QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0),
                6, 6)
            p.fillPath(path, QColor(pal["window"]))
            p.setPen(QColor(pal["border"]))
            p.drawPath(path)
            p.end()
        except Exception:
            exc_note("paintEvent @ ggis/common/base/dialog.py:409")
            pass


_STD_BUTTON_TEXTS = ("确定", "取消", "应用", "OK", "Ok", "Cancel", "Apply")


def _fallback_dialog_parent():
    try:
        from PySide6.QtWidgets import QMainWindow
        win = QApplication.activeWindow()
        if isinstance(win, QWidget):
            return win
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMainWindow) and w.isVisible():
                return w
    except Exception:
        exc_note("_fallback_dialog_parent @ ggis/common/base/dialog.py:439")
        pass
    return None


def _ensure_dialog_parent(args, kwargs):
    if kwargs.get("parent") is not None:
        return args, kwargs
    if args and isinstance(args[0], QWidget):
        return args, kwargs
    win = _fallback_dialog_parent()
    if not isinstance(win, QWidget):
        return args, kwargs
    if "parent" in kwargs:
        kwargs = dict(kwargs)
        kwargs["parent"] = win
        return args, kwargs
    if args and args[0] is None:
        return (win,) + tuple(args[1:]), kwargs
    if not args:
        return (win,), kwargs
    return args, kwargs


class GgsDialog(GgsFramelessMixin, QDialog):

    def __init__(self, *args, **kwargs):
        args, kwargs = _ensure_dialog_parent(args, kwargs)
        super().__init__(*args, **kwargs)
        self._setup_frameless()

    def showEvent(self, e):
        super().showEvent(e)
        try:
            self._strip_std_button_icons()
        except Exception:
            exc_note("showEvent @ ggis/common/base/dialog.py:497")
            pass

    def _strip_std_button_icons(self):
        for b in self.findChildren(QPushButton):
            try:
                if b.text().replace("&", "").strip() in _STD_BUTTON_TEXTS:
                    if not b.icon().isNull():
                        b.setIcon(QIcon())
            except Exception:
                exc_note("_strip_std_button_icons @ ggis/common/base/dialog.py:516")
                pass


_MSGBTN_TEXT = {
    QMessageBox.StandardButton.Ok: "确定",
    QMessageBox.StandardButton.Save: "保存",
    QMessageBox.StandardButton.Discard: "放弃",
    QMessageBox.StandardButton.Cancel: "取消",
    QMessageBox.StandardButton.Yes: "是",
    QMessageBox.StandardButton.No: "否",
    QMessageBox.StandardButton.Close: "关闭",
}


class GgsMsgBox(GgsDialog):

    _DEFAULT_BTNS = {
        "information": QMessageBox.StandardButton.Ok,
        "warning": QMessageBox.StandardButton.Ok,
        "critical": QMessageBox.StandardButton.Ok,
        "question": (QMessageBox.StandardButton.Yes
                     | QMessageBox.StandardButton.No),
    }

    StandardButton = QMessageBox.StandardButton

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setMinimumWidth(380)
        self._ret = QMessageBox.StandardButton.NoButton
        self._buttons = []

    def _build(self, text, buttons, default_btn):
        self._ret = QMessageBox.StandardButton.NoButton
        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 14)
        body.setSpacing(14)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setMaximumWidth(520)
        body.addWidget(lab)
        row = QHBoxLayout()
        row.addStretch(1)
        for b in _MSGBTN_TEXT:
            if b in buttons:
                pb = QPushButton(i18n.tr(_MSGBTN_TEXT[b]))
                pb.setMinimumWidth(72)
                if b == default_btn:
                    pb.setDefault(True)
                pb.clicked.connect(
                    lambda checked=False, sb=b: self._finish(sb))
                row.addWidget(pb)
                self._buttons.append(pb)
        body.addLayout(row)
        w = QWidget()
        w.setLayout(body)
        self.setLayout(w.layout())

    def _finish(self, sb):
        self._ret = sb
        try:
            self.done(int(sb) or 1)
        except Exception:
            exc_note("_finish @ ggis/common/base/dialog.py:598")
            self.done(1)

    def reject(self):
        if self._ret == QMessageBox.StandardButton.NoButton:
            if QMessageBox.StandardButton.Cancel in _MSGBTN_TEXT and \
                    getattr(self, "_has_cancel", False):
                self._ret = QMessageBox.StandardButton.Cancel
            else:
                self._ret = QMessageBox.StandardButton.No
        super().reject()

    @staticmethod
    def _show(parent, title, text, buttons, default, level):
        box = GgsMsgBox(parent)
        box.setWindowTitle(i18n.tr(title) if title else "")
        if buttons is None:
            buttons = GgsMsgBox._DEFAULT_BTNS[level]
        box._has_cancel = bool(buttons & QMessageBox.StandardButton.Cancel)
        if default is None:
            names = sorted(b.name for b in _MSGBTN_TEXT if b in buttons)
            default = next((b for b in _MSGBTN_TEXT if b.name in names),
                           QMessageBox.StandardButton.Ok)
        box._build(text, buttons, default)
        box.exec()
        return box._ret

    @staticmethod
    def information(parent, title, text,
                    buttons=None, default=None, **_):
        return GgsMsgBox._show(parent, title, text, buttons, default,
                               "information")

    @staticmethod
    def warning(parent, title, text,
                buttons=None, default=None, **_):
        return GgsMsgBox._show(parent, title, text, buttons, default,
                               "warning")

    warn = warning

    @staticmethod
    def critical(parent, title, text,
                 buttons=None, default=None, **_):
        return GgsMsgBox._show(parent, title, text, buttons, default,
                               "critical")

    @staticmethod
    def question(parent, title, text,
                 buttons=None, default=None, **_):
        return GgsMsgBox._show(parent, title, text, buttons, default,
                               "question")


class GgsInputDialog(GgsDialog):

    _W = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self._ok = False

    def _build(self, title, label_widget, value_widget):
        self.setWindowTitle(i18n.tr(title) if title else "")
        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 14)
        body.setSpacing(12)
        body.addWidget(label_widget)
        body.addWidget(value_widget)
        row = QHBoxLayout()
        row.addStretch(1)
        for text, accept in ((i18n.tr("确定"), True),
                             (i18n.tr("取消"), False)):
            pb = QPushButton(text)
            pb.setMinimumWidth(72)
            if accept:
                pb.setDefault(True)
                pb.clicked.connect(self.accept)
            else:
                pb.clicked.connect(self.reject)
            row.addWidget(pb)
        body.addLayout(row)
        w = QWidget()
        w.setLayout(body)
        self.setLayout(w.layout())
        self.setFixedWidth(self._W)

    def accept(self):
        self._ok = True
        super().accept()

    def reject(self):
        self._ok = False
        super().reject()

    @staticmethod
    def _label(text):
        lab = QLabel(i18n.tr(text))
        lab.setWordWrap(True)
        return lab

    @staticmethod
    def getText(parent, title, label, echo=QLineEdit.EchoMode.Normal,
                text="", flags=None, **_):
        dlg = GgsInputDialog(parent)
        ed = QLineEdit(text)
        ed.setEchoMode(echo)
        ed.returnPressed.connect(dlg.accept)
        dlg._build(title, GgsInputDialog._label(label), ed)
        dlg.exec()
        return ed.text(), dlg._ok

    @staticmethod
    def getMultiLineText(parent, title, label, text="", flags=None, **_):
        dlg = GgsInputDialog(parent)
        ed = QTextEdit()
        ed.setPlainText(text or "")
        dlg._build(title, GgsInputDialog._label(label), ed)
        dlg.resize(GgsInputDialog._W, 220)
        dlg.exec()
        return ed.toPlainText(), dlg._ok

    @staticmethod
    def getDouble(parent, title, label, value=0.0, minValue=-2147483647.0,
                  maxValue=2147483647.0, decimals=1, step=1.0, flags=None,
                  **_):
        dlg = GgsInputDialog(parent)
        sp = QDoubleSpinBox()
        sp.setDecimals(decimals)
        sp.setRange(minValue, maxValue)
        sp.setSingleStep(step)
        sp.setValue(value)
        sp.setAlignment(Qt.AlignmentFlag.AlignRight)
        sp.returnPressed.connect(dlg.accept)
        dlg._build(title, GgsInputDialog._label(label), sp)
        dlg.exec()
        return sp.value(), dlg._ok

    @staticmethod
    def getItem(parent, title, label, items=None, current=0,
                editable=True, flags=None, **_):
        dlg = GgsInputDialog(parent)
        cb = QComboBox()
        if editable:
            cb.setEditable(True)
            cb.lineEdit().returnPressed.connect(dlg.accept)
        for it in (items or []):
            cb.addItem(str(it))
        cb.setCurrentIndex(max(0, min(int(current or 0),
                                      cb.count() - 1)))
        dlg._build(title, GgsInputDialog._label(label), cb)
        dlg.exec()
        return cb.currentText(), dlg._ok


class GgsFileDialog(GgsFramelessMixin, QFileDialog):

    def __init__(self, parent=None, caption="", directory="", flt=""):
        super().__init__(parent, caption, directory, flt)
        self._setup_frameless()
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.resize(780, 520)

    @staticmethod
    def _prep(mode, initial_filter=None, options=None):
        pass

    @staticmethod
    def getOpenFileName(parent=None, caption="", directory="",
                        flt="", initial_filter="", options=None):
        dlg = GgsFileDialog(parent, caption, directory, flt)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
        if initial_filter:
            dlg.selectNameFilter(initial_filter)
        if options:
            dlg.setOptions(dlg.options() | options)
        if dlg.exec():
            return dlg.selectedFiles()[0], dlg.selectedNameFilter()
        return "", ""

    @staticmethod
    def getOpenFileNames(parent=None, caption="", directory="",
                         flt="", initial_filter="", options=None):
        dlg = GgsFileDialog(parent, caption, directory, flt)
        dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if initial_filter:
            dlg.selectNameFilter(initial_filter)
        if options:
            dlg.setOptions(dlg.options() | options)
        if dlg.exec():
            return dlg.selectedFiles(), dlg.selectedNameFilter()
        return [], ""

    @staticmethod
    def getSaveFileName(parent=None, caption="", directory="",
                        flt="", initial_filter="", options=None):
        dlg = GgsFileDialog(parent, caption, directory, flt)
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setFileMode(QFileDialog.FileMode.AnyFile)
        if initial_filter:
            dlg.selectNameFilter(initial_filter)
        if options:
            dlg.setOptions(dlg.options() | options)
        if dlg.exec():
            return dlg.selectedFiles()[0], dlg.selectedNameFilter()
        return "", ""

    @staticmethod
    def getExistingDirectory(parent=None, caption="", directory="",
                             options=None):
        dlg = GgsFileDialog(parent, caption, directory, "")
        dlg.setFileMode(QFileDialog.FileMode.Directory)
        dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
        if options:
            dlg.setOptions(dlg.options() | options)
        if dlg.exec():
            return dlg.selectedFiles()[0]
        return ""


class GgsDockTitleBtn(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsDockTitleBtn")
class GgsDockTitleLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsDockTitleLabel")
