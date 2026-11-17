# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QVBoxLayout, QWidget)

from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons as _icons
from ggis.core.app import i18n
from ggis.common.widgets.displays import GgsDimLabel
from ggis.common.base.dialog import GgsDockTitleLabel
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_KIND_NAMES = {
    "map": _tr("地图"),
    "layout": _tr("布局"),
    "model": _tr("模型"),
}


class GgsViewPropsDialog(GgsDialog):

    def __init__(self, title, kind="", view_id="", icon_name="", parent=None):
        super().__init__(parent)
        self.setObjectName("GgsViewPropsDialog")
        self.setWindowTitle(_tr("视图属性"))
        if icon_name:
            try:
                self.setWindowIcon(_icons.icon(icon_name, size=16))
            except Exception:
                _log.exception("silent exception in __init__")
        self.setFixedWidth(400)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(6)
        self._kind = str(kind or "")
        ic_name = str(icon_name or "")
        if ic_name:
            try:
                _ic = _icons.icon(ic_name, size=16)
                if _ic is not None and not _ic.isNull():
                    lb_ic = QLabel()
                    lb_ic.setPixmap(_ic.pixmap(16, 16))
                    top.addWidget(lb_ic)
            except Exception:
                _log.exception("silent exception in __init__")
        lb_kind = GgsDockTitleLabel(_KIND_NAMES.get(self._kind, self._kind or _tr("视图")))
        top.addWidget(lb_kind)
        top.addStretch(1)
        root.addLayout(top)

        body = QWidget(self)
        form = QFormLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self.ed_name = QLineEdit(str(title or ""))
        self.ed_name.setPlaceholderText(_tr("视图名称"))
        self.ed_name.selectAll()
        form.addRow(_tr("名称"), self.ed_name)

        lb_kind2 = GgsDimLabel(_KIND_NAMES.get(self._kind, self._kind or "—"))
        form.addRow(_tr("类型"), lb_kind2)

        lb_id = GgsDimLabel(str(view_id or "—"))
        lb_id.setToolTip(_tr("视图标识（不可修改）"))
        form.addRow(_tr("标识"), lb_id)
        root.addWidget(body)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel, self)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("确定"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(_tr("取消"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        try:
            self.ed_name.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            _log.exception("silent exception in __init__")

    def name(self):
        try:
            return str(self.ed_name.text() or "").strip()
        except Exception:
            _log.exception("silent exception in name")
            return ""
