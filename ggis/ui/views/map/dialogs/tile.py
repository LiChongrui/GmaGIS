# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QComboBox,
                               QDialogButtonBox,
                               QFormLayout,
                               QLineEdit,
                               QSpinBox,
                               QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.core.analysis.tile import (LONGLAT, WEBMERCATOR, GgsTileSource,
                          missing_placeholders)
from ggis.common.base.dialog import GgsDialog
from PySide6.QtWidgets import QLabel

_tr = i18n.tr

_CRS_CHOICES = (
    ("Web 墨卡托 (EPSG:3857)", WEBMERCATOR),
    ("经纬度 (EPSG:4326)", LONGLAT),
)


class GgsTileLayerDialog(GgsDialog):

    def __init__(self, parent=None, url="", name=""):
        super().__init__(parent)
        self._source = None
        self.setObjectName("GgsTileLayerDialog")
        self.setWindowTitle(_tr("在线瓦片"))
        self.setMinimumWidth(520)
        self._build(url, name)

    def _build(self, url, name):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter)

        self.ed_url = QLineEdit(str(url or ""))
        self.ed_url.setPlaceholderText(
            _tr("如 https://…/{z}/{x}/{y}.png"))
        form.addRow(_tr("URL 模板："), self.ed_url)

        self.ed_name = QLineEdit(str(name or ""))
        self.ed_name.setPlaceholderText(_tr("留空则按 URL 自动取名"))
        form.addRow(_tr("图层名称："), self.ed_name)

        self.cmb_crs = QComboBox()
        for label, authid in _CRS_CHOICES:
            self.cmb_crs.addItem(_tr(label), authid)
        form.addRow(_tr("坐标系："), self.cmb_crs)

        self.sp_max_zoom = QSpinBox()
        self.sp_max_zoom.setRange(0, 24)
        self.sp_max_zoom.setValue(19)
        self.sp_max_zoom.setSpecialValueText(_tr("不限制"))
        self.sp_max_zoom.setToolTip(_tr("瓦片最大缩放级别，0 = 不限制"))
        form.addRow(_tr("最大层级："), self.sp_max_zoom)

        lay.addLayout(form)

        self.lb_hint = GgsTileDialogHint("")
        self.lb_hint.setWordWrap(True)
        lay.addWidget(self.lb_hint)

        lay.addStretch(1)

        bbox = QDialogButtonBox(self)
        bbox.addButton(_tr("取消"), QDialogButtonBox.ButtonRole.RejectRole)
        bbox.addButton(_tr("确定"), QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)

    def source(self):
        return self._source

    def accept(self):
        text = str(self.ed_url.text() or "").strip()
        gap = missing_placeholders(text)
        if gap:
            self.lb_hint.setText(_tr("URL 模板必须包含 {x} {y} {z} 占位符（TMS 服务的行号也可写成 {-y}）"))
            self.ed_url.setFocus()
            return
        src = GgsTileSource(
            url=text,
            name=str(self.ed_name.text() or "").strip(),
            crs=self.cmb_crs.currentData() or WEBMERCATOR,
            max_zoom=int(self.sp_max_zoom.value()))
        if not src.is_valid():
            self.lb_hint.setText(_tr("URL 模板必须包含 {x} {y} {z} 占位符（TMS 服务的行号也可写成 {-y}）"))
            return
        if not src.name:
            src.name = _auto_name(text)
        self._source = src
        super().accept()


def _auto_name(url):
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        host = (u.hostname or "").replace("www.", "")
        seg = [s for s in (u.path or "").split("/") if s]
        if seg:
            return "%s/%s" % (host, seg[-1])
        return host or url
    except Exception:
        exc_note("_auto_name @ ggis/ui/views/map/dialogs/tile.py:140")
        return url


class GgsTileDialogHint(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsTileDialogHint")
