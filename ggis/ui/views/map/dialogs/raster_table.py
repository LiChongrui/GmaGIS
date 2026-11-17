# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
                               QDialogButtonBox,
                               QHeaderView,
                               QTableWidget,
                               QTableWidgetItem,
                               QWidget,
                               QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.core.style import raster_display as rd
from ggis.common.base.dialog import GgsDialog
from ggis.common.widgets.itemviews import setup_table_ops
from ggis.common.widgets.itemviews import GgsTableWidget
from ggis.ui.framework.docks import GgsDockWidget
from PySide6.QtWidgets import QLabel

_log = logging.getLogger("gmagis")

_tr = i18n.tr

_COL_W = 120


def _raster_attr_header_text(layer, info):
    name = layer.name() if layer is not None else ""
    band = int(info.get("band") or 1)
    n = int(info.get("count") or 0)
    if info.get("kind") == "palette":
        return _tr("「{0}」第 {1} 波段：{2} 个类别值"
                   ).format(name, band, n)
    if info.get("kind") == "unique":
        return _tr("「{0}」第 {1} 波段：{2} 个离散取值"
                   ).format(name, band, n)
    return _tr("「{0}」第 {1} 波段：没有属性表").format(name, band)


def _build_raster_attr_table(rows, palette=False):
    if palette:
        heads = (_tr("值"), _tr("类别"), _tr("颜色"), _tr("像素数"))
    else:
        heads = (_tr("值"), _tr("像素数"))
    t = GgsTableWidget(len(rows), len(heads))
    t.setObjectName("GgsRasterAttributeTable")
    t.setHorizontalHeaderLabels(list(heads))
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)

    for i, row in enumerate(rows):
        val, cname, color, count = (list(row) + [None, None, None, None])[:4]
        t.setItem(i, 0, _num_item(val))
        if palette:
            t.setItem(i, 1, QTableWidgetItem(str(cname or "")))
            t.setItem(i, 2, _color_item(color))
            t.setItem(i, 3, _num_item(count, group=True))
        else:
            t.setItem(i, 1, _num_item(count, group=True))

    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    if palette:
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (0, 2, 3):
            t.setColumnWidth(c, _COL_W)
    else:
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        t.setColumnWidth(1, _COL_W)
    setup_table_ops(t)
    return t


def build_raster_attr_body(layer):
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(8)
    info = rd.raster_attribute_table(layer) if layer is not None else {
        "kind": "none", "rows": [], "reason": _tr("没有图层"),
        "band": 1, "count": 0}
    head = GgsRasterAttrHead(_raster_attr_header_text(layer, info))
    head.setWordWrap(True)
    lay.addWidget(head)
    rows = info.get("rows") or []
    kind = info.get("kind")
    if kind == "none" or not rows:
        note = GgsRasterAttrNote(info.get("reason")
                      or _tr("这个栅格没有属性表"))
        note.setWordWrap(True)
        lay.addWidget(note, 1)
    else:
        table = _build_raster_attr_table(rows, palette=(kind == "palette"))
        lay.addWidget(table, 1)
    return body


class GgsRasterAttributeDialog(GgsDialog):

    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self._layer = layer
        self.setObjectName("GgsRasterAttributeDialog")
        self.setWindowTitle(_tr("栅格属性表 — {0}").format(
            layer.name() if layer is not None else ""))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("table", size=16))
        self.resize(600, 460)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        body = build_raster_attr_body(self._layer)
        lay.addWidget(body, 1)
        bbox = QDialogButtonBox(self)
        bbox.addButton(_tr("关闭"), QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.accepted.connect(self.accept)
        lay.addWidget(bbox)


class GgsRasterAttrDock(GgsDockWidget):
    closed = Signal(str)

    def __init__(self, layer, parent=None):
        super().__init__(str(layer.name() or _tr("栅格属性表")), parent)
        self.setObjectName("GgsRasterAttrDock")
        self._layer = layer
        self._lid = layer.id()
        self.setWidget(build_raster_attr_body(layer))

    def layer(self):
        return self._layer

    def layer_id(self):
        return self._lid

    def closeEvent(self, ev):
        try:
            self.closed.emit(self._lid)
        except Exception:
            _log.exception("silent exception in closeEvent")
        try:
            super().closeEvent(ev)
        except Exception:
            _log.exception("silent exception in closeEvent")


def _num_item(v, group=False):
    it = QTableWidgetItem()
    it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter)
    if v is None:
        it.setText("-")
        return it
    try:
        f = float(v)
    except Exception:
        exc_note("_num_item @ ggis/ui/views/map/dialogs/raster_table.py:194")
        it.setText(str(v))
        return it
    if f == int(f) and abs(f) < 1e15:
        it.setText("{:,}".format(int(f)) if group else str(int(f)))
    else:
        it.setText("{:,.4f}".format(f) if group else ("%.4f" % f))
    return it


def _color_item(color):
    it = QTableWidgetItem()
    if not color:
        it.setText("-")
        return it
    try:
        r, g, b = int(color[0]), int(color[1]), int(color[2])
        a = int(color[3]) if len(color) > 3 else 255
        qc = QColor(r, g, b, a)
        it.setText(qc.name().upper())
        it.setBackground(qc if a >= 255 else QColor(r, g, b))
        it.setForeground(_readable_on(r, g, b))
    except Exception:
        exc_note("_color_item @ ggis/ui/views/map/dialogs/raster_table.py:221")
        it.setText(str(color))
    return it


def _readable_on(r, g, b):
    lum = (0.299 * r + 0.587 * g + 0.114 * b)
    return QColor("#101418") if lum > 150 else QColor("#F2F5F8")


class GgsRasterAttrHead(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRasterAttrHead")
class GgsRasterAttrNote(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRasterAttrNote")
