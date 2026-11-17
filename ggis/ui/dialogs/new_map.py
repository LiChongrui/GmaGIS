# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtWidgets import (QDialogButtonBox, QFormLayout, QLineEdit,
                               QVBoxLayout, QWidget)

from ggis.common.widgets.inputs import GgsCrsSelector
from ggis.common.base.dialog import GgsDialog
from ggis.core.app import i18n
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr


class GgsNewMapDialog(GgsDialog):

    def __init__(self, parent=None, name="", crs=""):
        super().__init__(parent)
        self.setObjectName("GgsNewMapDialog")
        self.setWindowTitle(_tr("新建地图"))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("map_street", size=16))
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 14)
        root.setSpacing(10)

        body = QWidget(self)
        form = QFormLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        # 视图名创建后即固定（用户数据），不走翻译。
        self.ed_name = QLineEdit(name or "地图")
        self.ed_name.setPlaceholderText(_tr("地图名称"))
        self.ed_name.selectAll()
        form.addRow(_tr("名称"), self.ed_name)

        self.crs_ctl = GgsCrsSelector(self, crs=crs)
        form.addRow(_tr("坐标系"), self.crs_ctl)

        root.addWidget(body)
        root.addStretch(1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel, self)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("确定"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(_tr("取消"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        try:
            self.ed_name.setFocus()
        except Exception:
            _log.exception("silent exception in __init__")

    def map_name(self):
        return str(self.ed_name.text() or "").strip() or "地图"

    def crs(self):
        return self.crs_ctl.crs()
