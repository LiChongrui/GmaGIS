# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QWidget,
                               QVBoxLayout,
                               QHBoxLayout,
                               QSizePolicy,
                               QFrame,
)

from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.styling import icons as _icons
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.core.app import i18n
from ggis.common.widgets.displays import GgsDimLabel
from ggis.ui.framework.docks import GgsDockBody
from ggis.ui.panels.layertree import GgsDockToolbar
import logging
from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QScrollArea, QTextEdit
_log = logging.getLogger("gmagis")


class GgsPlaceholderDock(GgsDockWidget):

    def __init__(self, title, hint="", icon_name=None, parent=None):
        super().__init__(title, parent)
        self.setObjectName("GgsPlaceholderDock")

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        center = QWidget()
        center.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cl = QVBoxLayout(center)
        cl.setContentsMargins(16, 24, 16, 24)
        cl.setSpacing(10)
        cl.addStretch(1)

        if icon_name:
            ic = GgsPlaceholderIcon()
            try:
                pm = _icons.icon(icon_name, size=48).pixmap(48, 48)
                ic.setPixmap(pm)
            except Exception:
                _log.exception("silent exception in __init__")
            ic.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            cl.addWidget(ic, 0, Qt.AlignmentFlag.AlignHCenter)

        tx = GgsPlaceholderText(hint or title)
        tx.setWordWrap(True)
        tx.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cl.addWidget(tx, 0, Qt.AlignmentFlag.AlignHCenter)

        cl.addStretch(1)
        lay.addWidget(center)
        body.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setWidget(body)


class GgsLogDock(GgsDockWidget):

    _RANK = {"Info": 0, "Success": 0, "Warning": 1, "Error": 2}

    _FILTERS = (("全部消息", -1), ("仅警告及以上", 1), ("仅错误", 2))

    def __init__(self, title="日志", parent=None):
        super().__init__(title, parent)
        self.setObjectName("GgsLogDock")

        from PySide6.QtWidgets import QTextEdit
        from PySide6.QtGui import QFont

        self._entries = []
        self._filter_rank = -1
        self._auto_scroll = True

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = GgsDockToolbar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        bl.setSpacing(2)

        def _btn(icon_name, tip, cb):
            b = GgsSmallButtonStyle1(icon_name, i18n.tr(tip), cb)
            bl.addWidget(b)
            return b

        self.btn_clear = _btn("log_clear", "清空日志", self.clear)
        self.btn_copy = _btn("copy_features", "复制全部日志到剪贴板",
                             self.copy_all)
        self.btn_save = _btn("export", "把日志保存为文本文件…",
                             self.save_to_file)

        bl.addSpacing(6)
        self.cmb_filter = GgsLogFilter()
        self.cmb_filter.setToolTip(i18n.tr("只显示指定级别以上的日志"))
        for label, rank in self._FILTERS:
            self.cmb_filter.addItem(i18n.tr(label), rank)
        self.cmb_filter.currentIndexChanged.connect(
            lambda _i: self.set_filter(self.cmb_filter.currentData()))
        bl.addWidget(self.cmb_filter)

        self.chk_scroll = GgsLogAutoScroll(i18n.tr("自动滚动"))
        self.chk_scroll.setChecked(True)
        self.chk_scroll.setToolTip(
            i18n.tr("新日志到来时自动滚到最后一行"))
        self.chk_scroll.toggled.connect(self._on_autoscroll)
        bl.addWidget(self.chk_scroll)

        for _w in (self.cmb_filter, self.chk_scroll):
            try:
                _w.setFixedHeight(22)
            except Exception:
                _log.exception("silent exception in __init__")

        bl.addStretch(1)
        self.lbl_count = GgsDimLabel("")
        bl.addWidget(self.lbl_count)
        lay.addWidget(bar)

        self.text = GgsLogView()
        self.text.setReadOnly(True)
        try:
            f = QFont("Consolas")
            f.setPointSize(9)
            self.text.setFont(f)
        except Exception:
            _log.exception("silent exception in __init__")
        lay.addWidget(self.text, 1)

        scroll = GgsLogScroll()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        self.setWidget(scroll)
        self._update_count()

    def append(self, line, level=None):
        lv = str(level or "Info")
        text = str(line)
        self._entries.append((lv, text))
        self._update_count()
        if self._passes(lv):
            self._append_view(text)

    def _append_view(self, text):
        try:
            from shiboken6 import isValid as _valid
            if not _valid(self.text):
                return
            self.text.append(text)
        except Exception:
            _log.exception("silent exception in _append_view")
            return
        if not self._auto_scroll:
            return
        try:
            sb = self.text.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            _log.exception("silent exception in _append_view")

    def _passes(self, level):
        if self._filter_rank < 0:
            return True
        return self._RANK.get(str(level or "Info"), 0) >= self._filter_rank

    def set_filter(self, rank):
        try:
            self._filter_rank = int(rank)
        except Exception:
            _log.exception("silent exception in set_filter")
            self._filter_rank = -1
        self._rebuild_view()

    def _rebuild_view(self):
        try:
            self.text.clear()
        except Exception:
            _log.exception("silent exception in _rebuild_view")
        for lv, text in self._entries:
            if self._passes(lv):
                self._append_view(text)

    def _on_autoscroll(self, on):
        self._auto_scroll = bool(on)
        if self._auto_scroll:
            try:
                sb = self.text.verticalScrollBar()
                sb.setValue(sb.maximum())
            except Exception:
                _log.exception("silent exception in _on_autoscroll")

    def copy_all(self):
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.text.toPlainText())
            return True
        except Exception:
            _log.exception("silent exception in copy_all")
            return False

    def save_to_file(self):
        try:
            import os
            import datetime
            from ggis.common.base.dialog import GgsFileDialog
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            default = os.path.join(os.path.expanduser("~"),
                                   "gmagis-log-%s.txt" % stamp)
            path, _f = GgsFileDialog.getSaveFileName(
                self, i18n.tr("保存日志"), default,
                i18n.tr("文本文件 (*.txt *.log);;所有文件 (*)"))
            if not path:
                return False
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.text.toPlainText())
            return True
        except Exception:
            _log.exception("silent exception in save_to_file")
            return False

    def _update_count(self):
        try:
            from shiboken6 import isValid as _valid
            if not _valid(self.lbl_count):
                return
            self.lbl_count.setText(
                i18n.tr("{0} 条").format(len(self._entries)))
        except Exception:
            _log.exception("silent exception in _update_count")

    def clear(self):
        try:
            self._entries = []
            self.text.clear()
            self._update_count()
        except Exception:
            _log.exception("silent exception in clear")


class GgsLogAutoScroll(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLogAutoScroll")
class GgsLogFilter(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLogFilter")
        self.setProperty("compact", "true")
class GgsLogScroll(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLogScroll")
class GgsLogView(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLogView")
class GgsPlaceholderIcon(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPlaceholderIcon")
class GgsPlaceholderText(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsPlaceholderText")
