# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QButtonGroup,
                               QComboBox,
                               QDialogButtonBox,
                               QDoubleSpinBox,
                               QFormLayout,
                               QHBoxLayout,
                               QLineEdit,
                               QRadioButton,
                               QVBoxLayout,
                               QWidget,
)

from ggis.common.base.dialog import GgsDialog
from ggis.core.model.layout_model import (DEFAULT_PAGE, ORIENTATION_LANDSCAPE,
                           ORIENTATION_PORTRAIT, PAGE_SIZES, Layout,
                           unit_factor)
from ggis.ui.views.layout.page_units import DEFAULT_UNIT, PAGE_UNIT_ITEMS, unit_name
from ggis.core.app import i18n
from ggis.common.widgets.displays import GgsDimLabel

_tr = i18n.tr

_CUSTOM = "__custom__"

_DECIMALS = {"mm": 1, "cm": 2, "in": 2}


def _paper_names():
    try:
        from ggis.ui.views.layout.workspace import PAGE_ORDER
        names = [n for n in PAGE_ORDER if n in PAGE_SIZES]
        if names:
            return names
    except Exception:
        exc_note("_paper_names @ ggis/ui/views/layout/new_layout.py:73")
        pass
    return list(PAGE_SIZES)


class GgsNewLayoutDialog(GgsDialog):

    def __init__(self, parent=None, unit=DEFAULT_UNIT, name=None):
        super().__init__(parent)
        self.setObjectName("GgsNewLayoutDialog")
        self.setWindowTitle(_tr("新建布局"))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("layout", size=16))
        self.setMinimumWidth(440)

        self._mm = list(PAGE_SIZES.get(DEFAULT_PAGE, (210.0, 297.0)))
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 12, 18, 14)
        root.setSpacing(10)

        body = QWidget(self)
        form = QFormLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        self.ed_name = QLineEdit(name or _tr("布局"))
        self.ed_name.setPlaceholderText(_tr("布局名称"))
        self.ed_name.selectAll()
        form.addRow(_tr("名称"), self.ed_name)

        self.cmb_page = QComboBox()
        for name in _paper_names():
            self.cmb_page.addItem(str(name), str(name))
        self.cmb_page.addItem(_tr("自定义…"), _CUSTOM)
        self.cmb_page.currentIndexChanged.connect(self._on_paper_changed)
        form.addRow(_tr("纸张"), self.cmb_page)

        self.spn_w = QDoubleSpinBox()
        self.spn_h = QDoubleSpinBox()
        for sp in (self.spn_w, self.spn_h):
            sp.setRange(0.1, 3000.0)
            sp.setDecimals(2)
            sp.setSingleStep(1.0)
            sp.setMinimumWidth(96)
            sp.valueChanged.connect(self._on_size_edited)
        row = QWidget()
        hz = QHBoxLayout(row)
        hz.setContentsMargins(0, 0, 0, 0)
        hz.setSpacing(6)
        hz.addWidget(self.spn_w, 1)
        lb_x = GgsDimLabel("×")
        hz.addWidget(lb_x, 0)
        hz.addWidget(self.spn_h, 1)
        form.addRow(_tr("宽度 × 高度"), row)

        self.cmb_unit = QComboBox()
        for code, label in PAGE_UNIT_ITEMS:
            self.cmb_unit.addItem(str(label), str(code))
        k = self.cmb_unit.findData(str(unit or DEFAULT_UNIT))
        self.cmb_unit.setCurrentIndex(max(0, k))
        self.cmb_unit.currentIndexChanged.connect(self._on_unit_changed)
        form.addRow(_tr("单位"), self.cmb_unit)

        self.rb_port = QRadioButton(_tr("纵向"))
        self.rb_land = QRadioButton(_tr("横向"))
        self.rb_land.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rb_port)
        grp.addButton(self.rb_land)
        self.rb_port.toggled.connect(self._on_orient_changed)
        row2 = QWidget()
        hz2 = QHBoxLayout(row2)
        hz2.setContentsMargins(0, 0, 0, 0)
        hz2.setSpacing(16)
        hz2.addWidget(self.rb_port)
        hz2.addWidget(self.rb_land)
        hz2.addStretch(1)
        form.addRow(_tr("方向"), row2)

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

        self._mm = self._preset_mm(DEFAULT_PAGE, ORIENTATION_LANDSCAPE)
        self._sync_from_mm()
        try:
            self.ed_name.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            exc_note("__init__ @ ggis/ui/views/layout/new_layout.py:193")
            pass

    def _unit(self):
        try:
            return str(self.cmb_unit.currentData() or DEFAULT_UNIT)
        except Exception:
            exc_note("_unit @ ggis/ui/views/layout/new_layout.py:202")
            return DEFAULT_UNIT

    def _orient(self):
        return (ORIENTATION_PORTRAIT if self.rb_port.isChecked()
                else ORIENTATION_LANDSCAPE)

    @staticmethod
    def _preset_mm(name, orient):
        a, b = PAGE_SIZES.get(str(name), PAGE_SIZES[DEFAULT_PAGE])
        if str(orient) == ORIENTATION_PORTRAIT:
            return [min(a, b), max(a, b)]
        return [max(a, b), min(a, b)]

    def _match_paper(self):
        orient = self._orient()
        for name in PAGE_SIZES:
            ww, hh = self._preset_mm(name, orient)
            if abs(ww - self._mm[0]) < 0.05 and abs(hh - self._mm[1]) < 0.05:
                return str(name)
        return ""

    def _sync_from_mm(self):
        code = self._unit()
        f = unit_factor(code) or 1.0
        dec = int(_DECIMALS.get(code, 1))
        self._syncing = True
        try:
            for sp, v in ((self.spn_w, self._mm[0]), (self.spn_h, self._mm[1])):
                sp.setDecimals(dec)
                sp.setSuffix(" " + unit_name(code))
                sp.setValue(float(v) / f)
            hit = self._match_paper()
            i = self.cmb_page.findData(str(hit)) if hit else -1
            if i < 0:
                i = self.cmb_page.findData(_CUSTOM)
            if i >= 0:
                self.cmb_page.setCurrentIndex(i)
        finally:
            self._syncing = False

    def _read_mm(self):
        f = unit_factor(self._unit()) or 1.0
        return [float(self.spn_w.value()) * f, float(self.spn_h.value()) * f]

    def _on_unit_changed(self, *_):
        if self._syncing:
            return
        self._sync_from_mm()

    def _on_size_edited(self, *_):
        if self._syncing:
            return
        self._mm = self._read_mm()
        self._syncing = True
        try:
            hit = self._match_paper()
            i = (self.cmb_page.findData(str(hit)) if hit
                 else self.cmb_page.findData(_CUSTOM))
            if i >= 0:
                self.cmb_page.setCurrentIndex(i)
        finally:
            self._syncing = False

    def _on_paper_changed(self, *_):
        if self._syncing:
            return
        data = str(self.cmb_page.currentData() or "")
        if not data or data == _CUSTOM or data not in PAGE_SIZES:
            return
        self._mm = self._preset_mm(data, self._orient())
        self._sync_from_mm()

    def _on_orient_changed(self, *_):
        if self._syncing:
            return
        self._mm = [self._mm[1], self._mm[0]]
        self._sync_from_mm()

    def make_layout(self):
        try:
            name = str(self.ed_name.text() or "").strip() or _tr("布局")
        except Exception:
            exc_note("make_layout @ ggis/ui/views/layout/new_layout.py:316")
            name = _tr("布局")
        self._mm = self._read_mm()
        orient = self._orient()
        hit = self._match_paper()
        if hit:
            page = str(hit)
        else:
            page = "%gx%g" % (round(self._mm[0], 2), round(self._mm[1], 2))
        return Layout(name=name, page=page, orientation=orient,
                      margins_mm=(10.0, 10.0, 10.0, 10.0), dpi=300.0,
                      unit=self._unit())
