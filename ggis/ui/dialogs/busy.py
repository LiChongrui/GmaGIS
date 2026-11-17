# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtWidgets import (
                               QApplication,
                               QHBoxLayout,
                               QProgressBar,
                               QPushButton,
                               QVBoxLayout,
)

from ggis.common.base.dialog import GgsDialog
from ggis.common.widgets.displays import GgsSpinner
from ggis.core.app import i18n
import logging
from PySide6.QtWidgets import QLabel
_log = logging.getLogger("gmagis")

_tr = i18n.tr


class GgsBusyCard(GgsDialog):

    def __init__(self, parent=None, title="", text="", diameter=30,
                 cancellable=False):
        super().__init__(parent)
        self.setWindowTitle(title or _tr("读取中"))
        self.setModal(False)
        self.setMinimumWidth(320)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.spinner = GgsSpinner(self, diameter=int(diameter))
        row.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl = GgsBusyText(text or _tr("正在读取…"))
        self.lbl.setWordWrap(True)
        row.addWidget(self.lbl, 1)
        lay.addLayout(row)
        self.bar = QProgressBar(self)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        self.btn_cancel = QPushButton(_tr("取消"), self)
        self.btn_cancel.setVisible(bool(cancellable))
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        self._cancel = False
        cancel_row = QHBoxLayout()
        cancel_row.addStretch(1)
        cancel_row.addWidget(self.btn_cancel)
        lay.addLayout(cancel_row)
        self._progress_shown = False
        self._center_on_parent()
        self.spinner.start()
        _win = self.window()
        if _win is not None and _win is not self:
            try:
                _win.installEventFilter(self)
            except Exception:
                _log.exception("silent exception in __init__")

    def set_text(self, text):
        try:
            self.lbl.setText(str(text or ""))
        except Exception:
            _log.exception("silent exception in set_text")

    def set_progress(self, frac, text="", cancellable=True):
        try:
            was_hidden = not self.bar.isVisible()
            self.bar.setVisible(True)
            self.btn_cancel.setVisible(bool(cancellable))
            self.bar.setValue(int(max(0, min(100, float(frac) * 100))))
            if was_hidden and not self._progress_shown:
                self._progress_shown = True
                self.adjustSize()
                self._center_on_parent()
        except Exception:
            _log.exception("silent exception in set_progress")
        if text:
            self.set_text(text)

    def clear_progress(self):
        try:
            self.bar.setVisible(False)
            self.btn_cancel.setVisible(False)
            self.bar.setValue(0)
            self._cancel = False
        except Exception:
            _log.exception("silent exception in clear_progress")

    def _on_cancel_clicked(self):
        global _BUSY_CANCEL
        _BUSY_CANCEL = True
        self._cancel = True
        cb = _CANCEL_CB
        if cb is not None:
            try:
                cb()
            except Exception:
                _log.exception("silent exception in _on_cancel_clicked")
        try:
            self.btn_cancel.setEnabled(False)
            self.set_text(_tr("正在取消…"))
        except Exception:
            _log.exception("silent exception in _on_cancel_clicked")

    def _center_on_parent(self):
        p = self.parentWidget()
        if p is None:
            self._center_on_screen()
            return
        try:
            self.adjustSize()
            c = p.mapToGlobal(p.rect().center())
            self.move(int(c.x() - self.width() / 2),
                      int(c.y() - self.height() / 2))
        except Exception:
            _log.exception("silent exception in _center_on_parent")

    def _center_on_screen(self):
        try:
            app = QApplication.instance()
            if app is None:
                return
            scr = app.primaryScreen()
            r = scr.availableGeometry() if scr is not None \
                else app.desktop().availableGeometry()
            self.adjustSize()
            self.move(int(r.center().x() - self.width() / 2),
                      int(r.center().y() - self.height() / 2))
        except Exception:
            _log.exception("silent exception in _center_on_screen")

    def showEvent(self, e):
        super().showEvent(e)
        self._center_on_parent()

    def closeEvent(self, e):
        _win = self.window()
        if _win is not None and _win is not self:
            try:
                _win.removeEventFilter(self)
            except Exception:
                _log.exception("silent exception in closeEvent")
        super().closeEvent(e)

    def eventFilter(self, obj, ev):
        try:
            if ev.type() in (QEvent.Type.Move, QEvent.Type.Resize) \
                    and obj is self.window():
                self._center_on_parent()
        except Exception:
            _log.exception("silent exception in eventFilter")
        return super().eventFilter(obj, ev)


_CARD = None
_OWNER = None
_PENDING = None
_BUSY_CANCEL = False
_CANCEL_CB = None
_PENDING_CB = None


def set_cancel_callback(cb):
    global _CANCEL_CB
    _CANCEL_CB = cb


def show_busy(parent, title="", text="", owner=None, cancellable=False):
    global _CARD, _OWNER, _CANCEL_CB
    hide_busy(owner=_OWNER)
    try:
        _CARD = GgsBusyCard(parent, title=title, text=text,
                            cancellable=bool(cancellable))
        _CARD.show()
        _CARD.raise_()
        QApplication.processEvents()
        _OWNER = owner
        if not cancellable:
            _CANCEL_CB = None
    except Exception:
        _log.exception("silent exception in show_busy")
        _CARD = None
        _OWNER = None
        _CANCEL_CB = None
    return _CARD


def update_busy(text):
    card = _CARD
    if card is not None:
        card.set_text(text)


def is_busy():
    return _CARD is not None


def pump():
    if _CARD is None:
        return False
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return False
        app.processEvents()
        return True
    except Exception:
        _log.exception("silent exception in pump")
        return False


def show_busy_delayed(parent, title="", text="", delay_ms=300,
                      cancellable=False, cancel_cb=None):
    global _PENDING, _CANCEL_CB, _PENDING_CB
    hide_busy()
    if cancellable:
        _PENDING_CB = cancel_cb
    else:
        _CANCEL_CB = None
        _PENDING_CB = None
    try:
        t = QTimer()
        t.setSingleShot(True)
        t.timeout.connect(
            lambda: _fire_busy(parent, title, text, cancellable))
        t.start(max(0, int(delay_ms)))
        _PENDING = t
    except Exception:
        _log.exception("silent exception in show_busy_delayed")
        _PENDING = None
    return None


def _fire_busy(parent, title, text, cancellable=False):
    global _PENDING, _CANCEL_CB, _PENDING_CB
    if _PENDING is None:
        return
    _PENDING = None
    show_busy(parent, title, text, cancellable=bool(cancellable))
    if cancellable:
        _CANCEL_CB = _PENDING_CB
    _PENDING_CB = None


def hide_busy(owner=None):
    global _CARD, _PENDING, _OWNER, _PENDING_CB
    pend = _PENDING
    _PENDING = None
    _PENDING_CB = None
    if pend is not None:
        try:
            pend.stop()
        except Exception:
            _log.exception("silent exception in hide_busy")
    if _OWNER is not None and owner != _OWNER:
        return
    card = _CARD
    _CARD = None
    _OWNER = None
    global _CANCEL_CB
    _CANCEL_CB = None
    if card is None:
        return
    try:
        card.spinner.stop()
    except Exception:
        _log.exception("silent exception in hide_busy")
    try:
        card.close()
        card.deleteLater()
    except Exception:
        _log.exception("silent exception in hide_busy")


def update_busy_progress(frac, text="", cancellable=True):
    card = _CARD
    if card is not None:
        try:
            card.set_progress(frac, text, cancellable=cancellable)
        except Exception:
            _log.exception("silent exception in update_busy_progress")


class GgsBusyText(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsBusyText")
