# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QAbstractItemView,
                               QDialogButtonBox,
                               QHBoxLayout,
                               QListWidgetItem,
                               QVBoxLayout,
)

from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons as _icons
from ggis.core.app import i18n
from ggis.common.widgets.displays import GgsDimLabel
from ggis.common.base.dialog import GgsDockTitleLabel
from ggis.common.widgets.buttons import GgsSmallButtonStyle1, GgsStandardButton

_tr = i18n.tr


class GgsLayerPickDialog(GgsDialog):

    def __init__(self, layers, path="", parent=None):
        super().__init__(parent)
        self.setObjectName("GgsLayerPickDialog")
        self.setWindowTitle(_tr("添加图层"))
        try:
            self.setWindowIcon(_icons.icon("add_vector", size=16))
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/layer_pick.py:63")
            pass
        self.setMinimumSize(420, 380)
        self._layers = [(str(n), str(g or "")) for n, g in (layers or [])]
        self._src_path = str(path or "")
        self._group_name = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        name = os.path.basename(str(path or "")) or str(path or "")
        top = QHBoxLayout()
        top.setSpacing(6)
        self.lbl_file = GgsDockTitleLabel(name)
        self.lbl_file.setToolTip(str(path or ""))
        top.addWidget(self.lbl_file)
        top.addStretch(1)
        self.lbl_count = GgsDimLabel("")
        top.addWidget(self.lbl_count)
        root.addLayout(top)

        self.lst = GgsListWidget()
        self.lst.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection)
        for lname, gtype in self._layers:
            it = QListWidgetItem(_short_geom_name(gtype, lname))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            if gtype:
                it.setToolTip(lname)
            self.lst.addItem(it)
        self.lst.itemChanged.connect(lambda _i: self._update_count())
        root.addWidget(self.lst, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_all = GgsSmallButtonStyle1(
            "select", _tr("全选"), lambda: self._set_all(True), 16, self)
        row.addWidget(self.btn_all)
        self.btn_none = GgsSmallButtonStyle1(
            "deselect", _tr("全不选"), lambda: self._set_all(False), 16, self)
        row.addWidget(self.btn_none)
        self.btn_group = GgsStandardButton(
            "folder", _tr("按文件名建分组添加"),
            slot=lambda: self._accept_grouped(), parent=self)
        row.addWidget(self.btn_group)
        row.addStretch(1)
        root.addLayout(row)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        try:
            bok = box.button(QDialogButtonBox.StandardButton.Ok)
            if bok is not None:
                bok.setIcon(_icons.icon("confirm", size=16))
            bc = box.button(QDialogButtonBox.StandardButton.Cancel)
            if bc is not None:
                bc.setIcon(_icons.icon("clear", size=16))
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/layer_pick.py:134")
            pass
        root.addWidget(box)
        self._update_count()

    def _set_all(self, on):
        self.lst.blockSignals(True)
        try:
            for i in range(self.lst.count()):
                self.lst.item(i).setCheckState(
                    Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        finally:
            self.lst.blockSignals(False)
        self._update_count()

    def _update_count(self):
        n = len(self.picked_names())
        try:
            self.lbl_count.setText(
                _tr("已选 {0} / {1}").format(n, len(self._layers)))
        except Exception:
            exc_note("_update_count @ ggis/ui/views/map/dialogs/layer_pick.py:155")
            pass

    def picked_names(self):
        out = []
        for i in range(self.lst.count()):
            it = self.lst.item(i)
            if it is not None and it.checkState() == Qt.CheckState.Checked:
                if 0 <= i < len(self._layers):
                    out.append(self._layers[i][0])
        return out

    def group_name(self):
        return self._group_name

    def _accept_grouped(self):
        import os as _os
        base = _os.path.splitext(_os.path.basename(self._src_path))[0]
        self._group_name = base or _tr("图层组")
        self.accept()


_GEOM_NAMES = (("Point", "点"), ("LineString", "线"), ("Polygon", "面"),
               ("Multi", "多部件"), ("GeometryCollection", "集合"))


def _short_geom_name(gtype, lname):
    s = str(gtype or "")
    for key, label in _GEOM_NAMES:
        if key in s:
            return "%s  （%s）" % (lname, _tr(label))
    return str(lname)
