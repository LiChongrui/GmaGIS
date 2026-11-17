# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QRadioButton, QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.common.base.dialog import GgsDialog, GgsMsgBox
from ggis.common.widgets.inputs import GgsComboBox, GgsCrsSelector
from ggis.io.csv_io import guess_xy_fields
from ggis.io.table_io import table_to_layer
from ggis.core.model.field import fields_from_layer

_tr = i18n.tr


class GgsTableToLayerDialog(GgsDialog):

    def __init__(self, layer, parent=None, host=None):
        super().__init__(parent)
        self._layer = layer
        self._host = host
        self.result_layer = None
        self.setObjectName("GgsTableToLayerDialog")
        self.setWindowTitle(_tr("表转矢量 — {0}").format(layer.name()))
        self.resize(420, 220)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        fields = fields_from_layer(self._layer)
        headers = [f.name for f in fields]
        num_fields = [f.name for f in fields if f.is_numeric()]
        str_fields = [f.name for f in fields if f.type == "string"]
        if not num_fields:
            num_fields = headers
        if not str_fields:
            str_fields = headers

        self._bg = QButtonGroup(self)
        self.rd_xy = QRadioButton(_tr("XY表转点"))
        self.rd_wkt = QRadioButton(_tr("WKT转几何"))
        self.rd_xy.setChecked(True)
        self._bg.addButton(self.rd_xy)
        self._bg.addButton(self.rd_wkt)
        row_mode = QHBoxLayout()
        row_mode.setContentsMargins(0, 0, 0, 0)
        row_mode.addWidget(self.rd_xy)
        row_mode.addWidget(self.rd_wkt)
        row_mode.addStretch(1)
        lay.addLayout(row_mode)

        gb_xy, form_xy = self._section()
        self.cmb_x = GgsComboBox(self)
        self.cmb_y = GgsComboBox(self)
        self.cmb_x.addItems(num_fields)
        self.cmb_y.addItems(num_fields)
        x_hint, y_hint = guess_xy_fields(headers)
        if x_hint and x_hint in num_fields:
            self.cmb_x.setCurrentText(x_hint)
        if y_hint and y_hint in num_fields:
            self.cmb_y.setCurrentText(y_hint)
        form_xy.addRow(QLabel(_tr("X")), self.cmb_x)
        form_xy.addRow(QLabel(_tr("Y")), self.cmb_y)
        self._gb_xy = gb_xy

        gb_w, form_w = self._section()
        self.cmb_wkt = GgsComboBox(self)
        self.cmb_wkt.addItems(str_fields)
        form_w.addRow(QLabel(_tr("WKT")), self.cmb_wkt)
        self._gb_w = gb_w

        gb_c, form_c = self._section()
        default_crs = ""
        try:
            c = self._layer.crs()
            if c is not None and c.is_valid():
                default_crs = c.authid() or ""
        except Exception:
            default_crs = ""
        if not default_crs:
            default_crs = "EPSG:4326"
        self.crs_sel = GgsCrsSelector(
            self, crs=default_crs, label=_tr("坐标系"))
        form_c.addRow(self.crs_sel)

        lay.addWidget(gb_xy)
        lay.addWidget(gb_w)
        lay.addWidget(gb_c)
        lay.addStretch(1)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        bbox.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("确定"))
        bbox.button(QDialogButtonBox.StandardButton.Cancel).setText(
            _tr("取消"))
        bbox.accepted.connect(self._on_accept)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)

        self.rd_xy.toggled.connect(self._sync_mode)
        self.rd_wkt.toggled.connect(self._sync_mode)
        self._sync_mode()

    def _section(self):
        gb = QGroupBox()
        form = QFormLayout(gb)
        form.setContentsMargins(8, 8, 8, 8)
        return gb, form

    def _sync_mode(self, *_):
        xy = self.rd_xy.isChecked()
        self._gb_xy.setVisible(xy)
        self._gb_w.setVisible(not xy)

    def _on_accept(self):
        if self.rd_xy.isChecked():
            lyr = table_to_layer(
                self._layer, "xy",
                x_field=self.cmb_x.currentText(),
                y_field=self.cmb_y.currentText(),
                crs=self.crs_sel.crs())
        else:
            lyr = table_to_layer(
                self._layer, "wkt",
                wkt_field=self.cmb_wkt.currentText(),
                crs=self.crs_sel.crs())
        if lyr is None or not lyr.is_valid():
            GgsMsgBox.warning(
                self, _tr("无法转换"),
                _tr(str(lyr.error() if lyr is not None else "未知错误")))
            return
        self.result_layer = lyr
        self.accept()
