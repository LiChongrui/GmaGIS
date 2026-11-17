# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QDialogButtonBox,
                               QFormLayout,
                               QHBoxLayout,
                               QHeaderView,
                               QTableWidget,
                               QTableWidgetItem,
                               QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.io import csv_io
from ggis.common.base.dialog import GgsDialog, GgsFileDialog
from ggis.common.widgets.itemviews import setup_table_ops
from ggis.common.widgets.itemviews import GgsTableWidget
from ggis.common.widgets.displays import GgsDimLabel
from PySide6.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton

_tr = i18n.tr

_CRS_CHOICES = (
    ("EPSG:4326 — WGS 84 经纬度", "EPSG:4326"),
    ("EPSG:4490 — CGCS2000 经纬度", "EPSG:4490"),
    ("EPSG:3857 — 伪墨卡托（Web 地图）", "EPSG:3857"),
)

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16", "latin-1")

_DELIMS = ((",", "逗号"), ("\t", "制表符"), (";", "分号"),
           ("|", "竖线"))

_PREVIEW_ROWS = 20


class GgsCsvImportDialog(GgsDialog):

    def __init__(self, parent=None, path="", force_xy_choice=False):
        super().__init__(parent)
        self._info = None
        self._force_xy = bool(force_xy_choice)
        self.setObjectName("GgsCsvImportDialog")
        self.setWindowTitle(_tr("导入分隔文本数据"))
        self.setMinimumWidth(680)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.ed_path = GgsCsvPath(str(path or ""))
        self.ed_path.setReadOnly(True)
        self.ed_path.setPlaceholderText(_tr("选择文件"))
        row.addWidget(self.ed_path, 1)
        b_browse = GgsCsvBrowse(_tr("浏览…"))
        b_browse.clicked.connect(self._browse)
        row.addWidget(b_browse)
        lay.addLayout(row)

        self.lab_info = GgsDimLabel()
        self.lab_info.setWordWrap(True)
        lay.addWidget(self.lab_info)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.cb_enc = GgsCsvEncoding()
        for e in _ENCODINGS:
            self.cb_enc.addItem(e, e)
        self.cb_enc.currentIndexChanged.connect(self._reload)
        form.addRow(_tr("编码"), self.cb_enc)

        self.cb_delim = GgsCsvDelimiter()
        for d, label in _DELIMS:
            self.cb_delim.addItem(label, d)
        self.cb_delim.currentIndexChanged.connect(self._reload)
        form.addRow(_tr("分隔符"), self.cb_delim)

        self.cb_x = GgsCsvXField()
        self.cb_x.currentIndexChanged.connect(self._reload)
        form.addRow(_tr("X / 经度列"), self.cb_x)

        self.cb_y = GgsCsvYField()
        self.cb_y.currentIndexChanged.connect(self._reload)
        form.addRow(_tr("Y / 纬度列"), self.cb_y)

        self.cb_crs = GgsCsvCrs()
        self.cb_crs.setEditable(True)
        for label, code in _CRS_CHOICES:
            self.cb_crs.addItem(label, code)
        form.addRow(_tr("坐标系"), self.cb_crs)

        self.ed_name = GgsCsvLayerName()
        self.ed_name.setPlaceholderText(_tr("留空则用文件名"))
        form.addRow(_tr("图层名"), self.ed_name)

        lay.addLayout(form)

        lab_prev = QLabel(_tr("数据预览"))
        lab_prev.setObjectName("GgsSectionLabel")
        lay.addWidget(lab_prev)

        self.table = GgsTableWidget(0, 0)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        setup_table_ops(self.table, row_height=22)
        lay.addWidget(self.table, 1)

        self.lab_warn = GgsCsvWarn()
        self.lab_warn.setWordWrap(True)
        lay.addWidget(self.lab_warn)

        self.box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("导入"))
        self.box.button(QDialogButtonBox.StandardButton.Cancel).setText(_tr("取消"))
        self.box.accepted.connect(self._accept)
        self.box.rejected.connect(self.reject)
        lay.addWidget(self.box)

        if path:
            self._reload()
        else:
            self._set_enabled(False)
            self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _set_enabled(self, on):
        for w in (self.cb_enc, self.cb_delim, self.cb_x, self.cb_y,
                  self.cb_crs, self.ed_name):
            w.setEnabled(on)

    def _browse(self):
        path, _ = GgsFileDialog.getOpenFileName(
            self, _tr("选择分隔文本数据"), self.ed_path.text(),
            _tr("分隔文本 (*.csv *.tsv *.txt);;所有文件 (*)"))
        if path:
            self.ed_path.setText(path)
            self._reload()

    def _current(self):
        return {
            "encoding": self.cb_enc.currentData(),
            "delimiter": self.cb_delim.currentData(),
        }

    def _sync_combos(self, encoding, delimiter):
        for cb, val in ((self.cb_enc, encoding), (self.cb_delim, delimiter)):
            cb.blockSignals(True)
            i = cb.findData(val)
            if i >= 0:
                cb.setCurrentIndex(i)
            else:
                cb.setEditable(True)
                cb.setEditText(str(val))
            cb.blockSignals(False)

    def _reload(self, *_a):
        path = self.ed_path.text().strip()
        if not path:
            return
        enc = self.cb_enc.currentData()
        delim = self.cb_delim.currentData()

        try:
            info = csv_io.sniff_table(path)
        except Exception as e:
            exc_note("_reload @ ggis/ui/views/map/dialogs/csv.py:205")
            self.lab_info.setText(_tr("读取失败：{}").format(e))
            self.lab_warn.setText("")
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            self._set_enabled(False)
            self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        self._sync_combos(info.encoding, info.delimiter)

        if (enc and enc != info.encoding) or (delim and delim != info.delimiter):
            try:
                info2 = csv_io.sniff_table(
                    path,
                    encoding=self.cb_enc.currentData(),
                    delimiter=self.cb_delim.currentData())
                info = info2
            except Exception as e:
                exc_note("_reload @ ggis/ui/views/map/dialogs/csv.py:225")
                self.lab_warn.setText(_tr("按所选编码 / 分隔符解析失败：{}")
                                      .format(e))
                self._set_enabled(True)
                self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
                return

        self._info = info
        self.lab_info.setText(_tr("已探测：{}").format(info.describe()))
        self.lab_warn.setText("")

        cur_x, cur_y = self.cb_x.currentText(), self.cb_y.currentText()
        gx, gy = csv_io.guess_xy_fields(info.headers)
        for cb, keep, guess in ((self.cb_x, cur_x, gx),
                                (self.cb_y, cur_y, gy)):
            cb.blockSignals(True)
            cb.clear()
            for h in info.headers:
                cb.addItem(h)
            want = keep if keep in info.headers else (guess or "")
            if want:
                cb.setCurrentIndex(info.headers.index(want))
            cb.blockSignals(False)

        self.ed_name.setPlaceholderText(
            _tr("留空则用文件名"))
        self._fill_preview(info)
        self._set_enabled(True)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _fill_preview(self, info):
        cols = info.headers
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        rows = info.rows[:_PREVIEW_ROWS]
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c in range(len(cols)):
                v = row[c] if c < len(row) else ""
                it = QTableWidgetItem(str(v))
                self.table.setItem(r, c, it)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        for c in range(len(cols)):
            if self.table.columnWidth(c) > 220:
                self.table.setColumnWidth(c, 220)

        x, y = self.cb_x.currentText(), self.cb_y.currentText()
        if x and y:
            r = csv_io.read_table_points(
                info.path, x, y, name="__probe__")
            if hasattr(r, "on_done"):
                r.on_done(lambda ev: self._show_probe(ev.get("result")))
                r.on_fail(lambda ev: self.lab_warn.setText(
                    _tr("⚠ {}").format(ev.get("error"))))
                return
            self._show_probe(r)

    def _show_probe(self, lyr):
        if lyr is None:
            return
        if not lyr.is_valid():
            self.lab_warn.setText(_tr("⚠ {}").format(lyr.error()))
        elif lyr.error():
            self.lab_warn.setText(
                _tr("⚠ {} 条记录可用，{}").format(
                    lyr.feature_count(), lyr.error()))
        else:
            self.lab_warn.setText(_tr("✓ {} 条记录可导入")
                                  .format(lyr.feature_count()))

    def _accept(self):
        if self.result_info() is None:
            return
        self.accept()

    def result_info(self):
        if self._info is None:
            return None
        x, y = self.cb_x.currentText(), self.cb_y.currentText()
        if not x or not y:
            return None
        if x == y:
            self.lab_warn.setText(_tr("⚠ X 列与 Y 列不能是同一列"))
            return None
        crs = self.cb_crs.currentData() or str(self.cb_crs.currentText()).strip()
        return {
            "path": self.ed_path.text().strip(),
            "x_field": x,
            "y_field": y,
            "crs": crs,
            "encoding": self.cb_enc.currentData(),
            "delimiter": self.cb_delim.currentData(),
            "name": self.ed_name.text().strip(),
        }


class GgsCsvBrowse(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvBrowse")
class GgsCsvCrs(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvCrs")
class GgsCsvDelimiter(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvDelimiter")
class GgsCsvEncoding(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvEncoding")
class GgsCsvLayerName(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvLayerName")
class GgsCsvPath(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvPath")
class GgsCsvWarn(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvWarn")
class GgsCsvXField(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvXField")
class GgsCsvYField(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCsvYField")
