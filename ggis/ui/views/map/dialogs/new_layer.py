# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QDialogButtonBox, QFormLayout,
                               QFrame, QHBoxLayout, QRadioButton, QScrollArea,
                               QVBoxLayout, QWidget)

from ggis.core.app import i18n
from ggis.io.vector_io import OGR_GEOMETRY_TYPES
from ggis.common.base.dialog import GgsDialog
from ggis.common.widgets.inputs import GgsCrsSelector, GgsComboBox, GgsLineEdit
from ggis.common.widgets.inputs import GgsLayerOutputWidget
from ggis.common.widgets.buttons import GgsButtonBox, GgsSmallButtonStyle1
from ggis.common.widgets.displays import GgsDimLabel

_tr = i18n.tr

KIND_CHOICES = (
    ("point", "点", "Point"),
    ("line", "线", "LineString"),
    ("polygon", "面", "Polygon"),
)

FIELD_TYPE_CHOICES = (
    ("文本", "str"),
    ("整数", "int64"),
    ("小数", "float64"),
    ("日期", "datetime64[ns]"),
)



class GgsNewLayerDialog(GgsDialog):

    def __init__(self, parent=None, title="", kind="point", crs="",
                 name="", show_name=True,
                 show_format=False, show_create_type=False,
                 show_fields=False, create_type="file", fmt=".gpkg"):
        _real_parent = parent
        try:
            from PySide6.QtWidgets import QWidget, QApplication
            if isinstance(parent, QWidget):
                _w = parent.window()
                if _w is not None:
                    _real_parent = _w
            if _real_parent is None:
                _real_parent = QApplication.activeWindow()
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/new_layer.py:75")
            _real_parent = parent
        super().__init__(_real_parent)
        self.setObjectName("GgsNewLayerDialog")
        self.setWindowTitle(_tr(title or "新建矢量图层"))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("new_shape", size=16))
        self.setMinimumWidth(420)

        self._show_format = show_format
        self._show_create_type = show_create_type
        self._show_fields = show_fields

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)

        self.w_out = None
        self.ed_name = None
        self._lab_name = None

        if show_format:
            self.rad_file = QRadioButton(_tr("文件"), self)
            self.rad_memory = QRadioButton(_tr("内存图层"), self)
            self.rad_file.setChecked(create_type != "memory")
            self.rad_memory.setChecked(create_type == "memory")
            _bg = QButtonGroup(self)
            _bg.addButton(self.rad_file)
            _bg.addButton(self.rad_memory)
            _bg.buttonToggled.connect(lambda *_a: self._sync_out())
            _mode = QWidget(self)
            _mode_lay = QHBoxLayout(_mode)
            _mode_lay.setContentsMargins(0, 0, 0, 0)
            _mode_lay.setSpacing(16)
            _mode_lay.addWidget(self.rad_file)
            _mode_lay.addWidget(self.rad_memory)
            _mode_lay.addStretch(1)
            if show_create_type:
                form.addRow(_mode)
            self.w_out = GgsLayerOutputWidget(self, kind="vector")
            form.addRow(self.w_out)
            self.ed_name = GgsLineEdit(str(name or ""), self)
            self.ed_name.setObjectName("GgsNewLayerName")
            self.ed_name.setPlaceholderText(_tr("留空自动命名"))
            form.addRow(_tr("图层名"), self.ed_name)
            self._lab_name = form.labelForField(self.ed_name)
        else:
            self.ed_name = GgsLineEdit(str(name or ""), self)
            self.ed_name.setObjectName("GgsNewLayerName")
            self.ed_name.setPlaceholderText(_tr("留空则用文件名"))
            form.addRow(_tr("图层名"), self.ed_name)
            self._lab_name = form.labelForField(self.ed_name)
            self.ed_name.setVisible(bool(show_name))

        self.cmb_kind = GgsComboBox(self)
        self.cmb_kind.setObjectName("GgsNewLayerKind")
        for k, label, _ogr in KIND_CHOICES:
            self.cmb_kind.addItem(_tr(label), k)
        ki = self.cmb_kind.findData(kind)
        if ki >= 0:
            self.cmb_kind.setCurrentIndex(ki)
        form.addRow(_tr("几何类型"), self.cmb_kind)
        self.crs_sel = GgsCrsSelector(self, crs=crs)
        form.addRow(_tr("坐标系"), self.crs_sel)

        lay.addLayout(form)

        if show_fields:
            _fld_title = GgsDimLabel(self)
            _fld_title.setText(_tr("字段"))
            lay.addWidget(_fld_title)
        self.fld_box = self._build_fields_area()
        self.fld_box.setVisible(show_fields)
        lay.addWidget(self.fld_box)

        self.lab_hint = GgsDimLabel(self)
        self.lab_hint.setWordWrap(True)
        lay.addWidget(self.lab_hint)

        self.box = GgsButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        self.box.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("创建"))
        self.box.button(QDialogButtonBox.StandardButton.Cancel).setText(_tr("取消"))
        self.box.accepted.connect(self.accept)
        self.box.rejected.connect(self.reject)
        lay.addWidget(self.box)

        self._sync_out()

    def _build_fields_area(self):
        self._fld_widgets = []
        box = QWidget(self)
        box.setObjectName("GgsNewLayerFieldsBox")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(6)

        frame = QFrame(self)
        frame.setObjectName("GgsNewLayerFieldsFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(8, 8, 8, 8)
        fl.setSpacing(6)

        scroll = QScrollArea(self)
        scroll.setObjectName("GgsNewLayerFieldsScroll")
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFixedHeight(180)
        inner = QWidget(self)
        inner.setObjectName("GgsNewLayerFieldsInner")
        vl = QVBoxLayout(inner)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(4)
        self._fld_rows = QVBoxLayout()
        self._fld_rows.setSpacing(4)
        vl.addLayout(self._fld_rows)
        self._fld_empty = GgsDimLabel(self)
        self._fld_empty.setText(_tr("默认无字段，点击下方「添加字段」增加"))
        self._fld_empty.setWordWrap(True)
        vl.addWidget(self._fld_empty)
        scroll.setWidget(inner)
        fl.addWidget(scroll)
        bl.addWidget(frame)

        btn_row = QWidget(self)
        brl = QHBoxLayout(btn_row)
        brl.setContentsMargins(0, 0, 0, 0)
        brl.addStretch(1)
        btn_add = GgsSmallButtonStyle1(
            "add", _tr("添加字段"),
            lambda: self._add_field_row(), 16, self)
        btn_add.setObjectName("GgsNewLayerAddField")
        brl.addWidget(btn_add)
        bl.addWidget(btn_row)
        return box

    def _add_field_row(self, name="", ftype="str"):
        row = QWidget()
        row.setObjectName("GgsFieldRow")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        le = GgsLineEdit(str(name or ""), self)
        le.setObjectName("GgsFieldName")
        le.setPlaceholderText(_tr("字段名"))
        cb = GgsComboBox(self)
        for label, t in FIELD_TYPE_CHOICES:
            cb.addItem(_tr(label), t)
        j = cb.findData(ftype)
        if j >= 0:
            cb.setCurrentIndex(j)
        btn = GgsSmallButtonStyle1(
            "delete", _tr("删除该字段"),
            lambda _c=False, w=row: self._remove_field_row(w), 16, self)
        rl.addWidget(le, 2)
        rl.addWidget(cb, 1)
        rl.addWidget(btn, 0)
        self._fld_rows.addWidget(row)
        self._fld_widgets.append(row)
        if self._fld_empty is not None:
            self._fld_empty.setVisible(False)
        return row

    def _remove_field_row(self, row):
        if row in self._fld_widgets:
            self._fld_widgets.remove(row)
        self._fld_rows.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        if not self._fld_widgets and self._fld_empty is not None:
            self._fld_empty.setVisible(True)

    def _collect_fields(self):
        out = []
        for i in range(self._fld_rows.count()):
            item = self._fld_rows.itemAt(i)
            row = item.widget() if item is not None else None
            if row is None:
                continue
            le = row.findChild(GgsLineEdit)
            cb = row.findChild(GgsComboBox)
            nm = le.text().strip() if le is not None else ""
            tp = cb.itemData(cb.currentIndex()) if cb is not None else "str"
            if not nm:
                continue
            out.append((str(nm), str(tp or "str")))
        return out

    def _sync_out(self, *_a):
        is_memory = self.create_type() == "memory"
        if self.w_out is not None:
            self.w_out.setVisible(not is_memory)
        if self.ed_name is not None and self._show_format:
            self.ed_name.setVisible(is_memory)
            if self._lab_name is not None:
                self._lab_name.setVisible(is_memory)

    def set_hint(self, text):
        self.lab_hint.setText(_tr(str(text or "")))

    def kind(self):
        data = self.cmb_kind.itemData(self.cmb_kind.currentIndex())
        return str(data or "point")

    def geometry_type(self):
        k = self.kind()
        for key, _label, ogr in KIND_CHOICES:
            if key == k:
                return ogr
        return OGR_GEOMETRY_TYPES[0]

    def crs(self):
        return self.crs_sel.crs()

    def layer_name(self):
        if (self._show_format and self.w_out is not None
                and self.create_type() == "file"):
            return self.w_out.ed_name.text().strip()
        return self.ed_name.text().strip() if self.ed_name is not None else ""

    def create_type(self):
        return ("memory" if (getattr(self, "rad_memory", None) is not None
                             and self.rad_memory.isChecked()) else "file")

    def format_info(self):
        if self.w_out is not None and self._show_format:
            return (self.w_out.current_suffix(), self.w_out.current_driver())
        return (".gpkg", "GPKG")

    def fields(self):
        return self._collect_fields()

    def result(self):
        suffix, driver = self.format_info()
        filename = ""
        if (self.w_out is not None and self._show_format
                and self.create_type() == "file"):
            filename = self.w_out.ed_file.text().strip()
        return {"kind": self.kind(),
                "geometry_type": self.geometry_type(),
                "crs": self.crs(),
                "name": self.layer_name(),
                "format": suffix,
                "driver": driver,
                "create_type": self.create_type(),
                "fields": self.fields(),
                "filename": filename}
