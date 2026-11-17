# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox,
                               QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QSpinBox,
                               QVBoxLayout)

from ggis.core.app import i18n
from ggis.ui.dialogs.color import GgsColorButton
from ...render.labeling import LabelStyle, suggest_label_field
from ggis.common.base.dialog import GgsDialog
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_PLACEMENTS = [
    ("自动", "auto"), ("右侧", "right"), ("上方", "top"),
    ("下方", "bottom"), ("左侧", "left"), ("居中", "center"),
]


class GgsLabelDialog(GgsDialog):

    def __init__(self, layer, style=None, parent=None, dark_bg=True):
        super().__init__(parent)
        self._layer = layer
        self._style = (style or LabelStyle()).clone()
        self._dark = bool(dark_bg)
        self.setObjectName("GgsLabelDialog")
        self.setWindowTitle(_tr("标注设置 — {0}").format(layer.name()))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("label", size=16))
        self.resize(460, 520)
        self._build()
        self._load()

    @property
    def style_obj(self):
        return self._style

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        self.chk_enabled = QCheckBox(_tr("显示标注"))
        lay.addWidget(self.chk_enabled)

        gb1 = QGroupBox(_tr("内容"))
        f1 = QFormLayout(gb1)
        f1.setContentsMargins(8, 8, 8, 8)
        self.cmb_field = QComboBox()
        for name, typ in self._fields():
            self.cmb_field.addItem("%s (%s)" % (name, typ), str(name))
        f1.addRow(_tr("标注字段"), self.cmb_field)
        self.ed_expr = QLineEdit()
        self.ed_expr.setPlaceholderText(
            "")
        f1.addRow(_tr("表达式（可选）"), self.ed_expr)
        self.spin_max = QSpinBox()
        self.spin_max.setRange(0, 1000000)
        self.spin_max.setSpecialValueText(_tr("不限"))
        f1.addRow(_tr("每层上限"), self.spin_max)
        lay.addWidget(gb1)

        gb2 = QGroupBox(_tr("字体与配色"))
        f2 = QFormLayout(gb2)
        f2.setContentsMargins(8, 8, 8, 8)
        self.spin_size = QDoubleSpinBox()
        self.spin_size.setRange(4.0, 72.0)
        self.spin_size.setDecimals(1)
        self.spin_size.setSingleStep(0.5)
        f2.addRow(_tr("字号 (pt)"), self.spin_size)
        row = QHBoxLayout()
        self.chk_bold = QCheckBox(_tr("粗体"))
        self.chk_italic = QCheckBox(_tr("斜体"))
        row.addWidget(self.chk_bold)
        row.addWidget(self.chk_italic)
        row.addStretch(1)
        f2.addRow(_tr("样式"), self._wrap(row))
        self.btn_color = GgsColorButton()
        f2.addRow(_tr("文字颜色"), self.btn_color)
        self.btn_halo = GgsColorButton()
        f2.addRow(_tr("描边颜色"), self.btn_halo)
        self.spin_halo = QDoubleSpinBox()
        self.spin_halo.setRange(0.0, 8.0)
        self.spin_halo.setDecimals(1)
        self.spin_halo.setSingleStep(0.2)
        self.spin_halo.setSpecialValueText(_tr("无"))
        f2.addRow(_tr("描边宽度 (px)"), self.spin_halo)
        lay.addWidget(gb2)

        gb3 = QGroupBox(_tr("位置"))
        f3 = QFormLayout(gb3)
        f3.setContentsMargins(8, 8, 8, 8)
        self.cmb_pos = QComboBox()
        for label, val in _PLACEMENTS:
            self.cmb_pos.addItem(_tr(label), val)
        f3.addRow(_tr("候选位置"), self.cmb_pos)
        self.spin_buffer = QDoubleSpinBox()
        self.spin_buffer.setRange(0.0, 40.0)
        self.spin_buffer.setDecimals(1)
        f3.addRow(_tr("与锚点间距 (px)"), self.spin_buffer)
        self.spin_repeat = QDoubleSpinBox()
        self.spin_repeat.setRange(0.0, 500.0)
        self.spin_repeat.setDecimals(1)
        self.spin_repeat.setSpecialValueText(_tr("仅中点/内部点"))
        f3.addRow(_tr("沿线重复距离 (px)"), self.spin_repeat)
        lay.addWidget(gb3)

        gb4 = QGroupBox(_tr("显示范围"))
        f4 = QFormLayout(gb4)
        f4.setContentsMargins(8, 8, 8, 8)
        self.spin_minscale = QDoubleSpinBox()
        self.spin_minscale.setRange(0.0, 5e7)
        self.spin_minscale.setDecimals(0)
        self.spin_minscale.setSpecialValueText(_tr("不限"))
        f4.addRow(_tr("最小比例尺 1:"), self.spin_minscale)
        self.spin_maxscale = QDoubleSpinBox()
        self.spin_maxscale.setRange(0.0, 5e7)
        self.spin_maxscale.setDecimals(0)
        self.spin_maxscale.setSpecialValueText(_tr("不限"))
        f4.addRow(_tr("最大比例尺 1:"), self.spin_maxscale)
        self.spin_minsize = QDoubleSpinBox()
        self.spin_minsize.setRange(0.0, 2000.0)
        self.spin_minsize.setDecimals(1)
        self.spin_minsize.setSpecialValueText(_tr("不限"))
        f4.addRow(_tr("最小要素尺寸 (px)"), self.spin_minsize)
        lay.addWidget(gb4)

        lay.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(_tr("确定"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(_tr("取消"))
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    @staticmethod
    def _wrap(inner):
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        inner.setContentsMargins(0, 0, 0, 0)
        w.setLayout(inner)
        return w

    def _fields(self):
        try:
            return [(str(n), str(t)) for n, t in self._layer.fields()]
        except Exception:
            _log.exception("silent exception in _fields")
            return []

    def _load(self):
        s = self._style
        self.chk_enabled.setChecked(bool(s.enabled))
        if s.field and "[" in s.field:
            self.ed_expr.setText(s.field)
        else:
            name = s.field or suggest_label_field(self._layer)
            i = self.cmb_field.findData(name)
            if i < 0 and self.cmb_field.count():
                i = 0
            if i >= 0:
                self.cmb_field.setCurrentIndex(i)
        self.spin_size.setValue(s.font_size)
        self.chk_bold.setChecked(bool(s.bold))
        self.chk_italic.setChecked(bool(s.italic))
        self.btn_color.setColor(QColor(s.color))
        self.btn_halo.setColor(QColor(s.halo_color))
        self.spin_halo.setValue(s.halo_width)
        self.spin_buffer.setValue(s.buffer)
        self.spin_max.setValue(int(s.max_labels))
        self.spin_repeat.setValue(s.repeat_px)
        self.spin_minscale.setValue(s.min_scale)
        self.spin_maxscale.setValue(s.max_scale)
        self.spin_minsize.setValue(s.min_size_px)
        j = self.cmb_pos.findData(s.placement or "auto")
        self.cmb_pos.setCurrentIndex(max(0, j))

    def _accept(self):
        s = self._style
        s.enabled = bool(self.chk_enabled.isChecked())
        expr = self.ed_expr.text().strip()
        if expr:
            s.field = expr
        else:
            s.field = str(self.cmb_field.currentData() or "")
        s.font_size = float(self.spin_size.value())
        s.bold = bool(self.chk_bold.isChecked())
        s.italic = bool(self.chk_italic.isChecked())
        s.color = self.btn_color.color().name()
        s.halo_color = self.btn_halo.color().name()
        s.halo_width = float(self.spin_halo.value())
        s.buffer = float(self.spin_buffer.value())
        s.max_labels = int(self.spin_max.value())
        s.repeat_px = float(self.spin_repeat.value())
        s.min_scale = float(self.spin_minscale.value())
        s.max_scale = float(self.spin_maxscale.value())
        s.min_size_px = float(self.spin_minsize.value())
        s.placement = str(self.cmb_pos.currentData() or "auto")
        s._font_key = None
        s._font = None
        self.accept()
