# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
                               QAbstractItemView,
                               QHBoxLayout,
                               QLabel,
                               QMenu,
                               QTreeWidgetItem,
                               QVBoxLayout,
                               QWidget,
)

from ggis.ui.framework.docks import GgsDockWidget
from ggis.core.app import i18n
from ggis.common.widgets.inputs import GgsComboBox
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.widgets.itemviews import GgsTreeWidget
from ggis.ui.framework.docks import GgsDockBody
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

try:
    from ggis.core.style.raster_display import _fmt_value
except Exception:
    _log.exception("silent exception")
    def _fmt_value(v):
        return str(v)

_GROUP = 0
_HEADER = 1
_FIELD = 2


def _fmt_coord(v):
    try:
        s = "%.6f" % float(v)
    except Exception:
        _log.exception("silent exception in _fmt_coord")
        return str(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


class GgsIdentifyPanel(GgsDockWidget):

    zoomRequested = Signal(object, int)
    modeChanged = Signal(str)
    pickToggled = Signal(bool)

    def __init__(self, title=None, parent=None):
        super().__init__(title or _tr("识别"), parent)
        self.setObjectName("GgsIdentifyDock")
        self._hits = []
        self._mode = "visible"
        self._point = None
        self._filling = False
        self._build()

    def _build(self):
        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 4, 6, 2)
        lay.setSpacing(4)

        top = GgsIdentifyTopBar()
        _hl = QHBoxLayout(top)
        _hl.setContentsMargins(0, 0, 0, 0)
        _hl.setSpacing(6)
        _hl.addWidget(QLabel(_tr("识别范围")))
        self.mode_combo = GgsComboBox()
        self.mode_combo.addItems([
            _tr("可见图层"), _tr("全部图层"), _tr("顶部图层")])
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip(_tr(
            "识别时查哪些图层：可见图层 / 全部图层（含隐藏）/ 顶部图层"
            "（图层树最上方一个）"))
        self.mode_combo.currentIndexChanged.connect(self._on_mode_picked)
        _hl.addWidget(self.mode_combo, 1)
        lay.addWidget(top)

        self.lbl_coord = GgsIdentifyCoord(_tr("（尚未点击地图）"))
        self.lbl_coord.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.lbl_coord)

        self.tree = GgsTreeWidget()
        self.tree.setObjectName("GgsIdentifyTree")
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(self._on_double)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_menu)
        lay.addWidget(self.tree, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.btn_pick = GgsSmallButtonStyle1(
            "select", _tr("地图取点"), self._on_toggle_pick)
        self.btn_pick.setChecked(False)
        btn_row.addWidget(self.btn_pick)
        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        self.setWidget(body)

    def _on_toggle_pick(self, on):
        self.pickToggled.emit(bool(on))

    def set_pick_checked(self, on):
        self.btn_pick.blockSignals(True)
        try:
            self.btn_pick.setChecked(bool(on))
        finally:
            self.btn_pick.blockSignals(False)

    def set_results(self, hits, point=None):
        self._hits = list(hits or [])
        if point is not None:
            self._point = point
        self._show_point()

        self._filling = True
        try:
            self.tree.clear()
        finally:
            self._filling = False

        if not self._hits:
            return

        by_layer = {}
        order = []
        for h in self._hits:
            k = _layer_key_of(h)
            if k not in by_layer:
                by_layer[k] = []
                order.append(k)
            by_layer[k].append(h)

        self._filling = True
        try:
            for k in order:
                items = by_layer[k]
                first = items[0]
                layer_name = _layer_name_of(first)
                if getattr(first, "kind", "") == "raster":
                    px = (getattr(first, "attrs", {}) or {}).get("pixel")
                    if px:
                        try:
                            layer_text = _tr("{0}（列 {1}, 行 {2}）").format(
                                layer_name, int(px[0]), int(px[1]))
                        except Exception:
                            _log.exception("silent exception in set_results")
                            layer_text = layer_name
                    else:
                        layer_text = layer_name
                else:
                    layer_text = "%s（%d）" % (layer_name, len(items))
                lit = QTreeWidgetItem([layer_text])
                lit.setData(0, Qt.ItemDataRole.UserRole, "layer")
                lit.setData(0, Qt.ItemDataRole.UserRole + 1, k)
                lit.setToolTip(0, layer_name)
                lkey = "L::%s" % k
                lit.setData(0, Qt.ItemDataRole.UserRole + 3, lkey)
                for h in items:
                    for _n in self._hit_node(h, k, len(items)):
                        lit.addChild(_n)
                self.tree.addTopLevelItem(lit)
            self.tree.expandAll()
        finally:
            self._filling = False

    def _show_point(self):
        try:
            if self._point is None:
                self.lbl_coord.setText(_tr("（尚未点击地图）"))
                return
            self.lbl_coord.setText(_tr("位置：{0}, {1}").format(
                _fmt_coord(self._point[0]), _fmt_coord(self._point[1])))
        except Exception:
            _log.exception("silent exception in _show_point")

    def _hit_node(self, h, key, n_in_layer=1):
        nodes = []
        if getattr(h, "kind", "") == "raster":
            attrs = getattr(h, "attrs", {}) or {}
            bands = list(attrs.get("bands") or [])
            values = list(attrs.get("values") or [])
            for i, b in enumerate(bands):
                v = values[i] if i < len(values) else None
                txt = _tr("（无数据）") if v is None else _fmt_value(v)
                node = QTreeWidgetItem(
                    [_tr("波段 {0}: {1}").format(b, txt)])
                node.setData(0, Qt.ItemDataRole.UserRole, "field")
                nodes.append(node)
            if not nodes:
                enode = QTreeWidgetItem([_tr("（读不到像素值）")])
                enode.setData(0, Qt.ItemDataRole.UserRole, "field")
                nodes.append(enode)
        elif getattr(h, "kind", "") == "tile":
            attrs = getattr(h, "attrs", {}) or {}
            r = attrs.get("r")
            g = attrs.get("g")
            b = attrs.get("b")
            if r is not None and g is not None and b is not None:
                txt = _tr("RGB: {0}, {1}, {2}").format(r, g, b)
            else:
                txt = _tr("（瓦片未缓存）")
            node = QTreeWidgetItem([txt])
            node.setData(0, Qt.ItemDataRole.UserRole, "field")
            node.setToolTip(
                0, _tr("瓦片层级 z={0}（{1}, {2}）").format(
                    attrs.get("z"), attrs.get("tx"), attrs.get("ty")))
            nodes.append(node)
        else:
            node = QTreeWidgetItem([_tr("要素: {0}").format(h.fid)])
            node.setData(0, Qt.ItemDataRole.UserRole, "feature")
            node.setData(0, Qt.ItemDataRole.UserRole + 1, h.fid)
            node.setData(0, Qt.ItemDataRole.UserRole + 2, key)
            node.setToolTip(0, _tr("要素 ID：{0}　双击缩放").format(h.fid))
            layer = h.layer
            for k2, v in _ordered_items(
                    h.attrs, layer.fields() if layer else []):
                child = QTreeWidgetItem(["%s: %s" % (k2, v)])
                child.setData(0, Qt.ItemDataRole.UserRole, "field")
                node.addChild(child)
            nodes.append(node)
        return nodes

    def clear(self):
        self.set_results([])

    def count(self):
        return len(self._hits)

    def _current_feature(self):
        it = self.tree.currentItem()
        while it is not None:
            if it.data(0, Qt.ItemDataRole.UserRole) == "feature":
                return (it.data(0, Qt.ItemDataRole.UserRole + 2),
                        it.data(0, Qt.ItemDataRole.UserRole + 1))
            it = it.parent()
        return None, None

    def _zoom_current(self):
        lid, fid = self._current_feature()
        if fid is None:
            return
        for h in self._hits:
            if _layer_key_of(h) == lid and getattr(h, "fid", None) == fid:
                if h.layer is not None:
                    self.zoomRequested.emit(h.layer, int(fid))
                return

    def _on_double(self, item, _col):
        self._zoom_current()

    def _on_mode_picked(self, idx):
        modes = ("visible", "all", "top")
        self._mode = modes[idx] if 0 <= idx < len(modes) else "visible"
        self.modeChanged.emit(self._mode)

    def _format_hit(self, h):
        lines = []
        if getattr(h, "kind", "") == "raster":
            attrs = getattr(h, "attrs", {}) or {}
            px = attrs.get("pixel")
            if px:
                try:
                    lines.append(_tr("像素（列, 行） = {0}, {1}").format(
                        int(px[0]), int(px[1])))
                except Exception:
                    _log.exception("silent exception in _format_hit")
            bands = list(attrs.get("bands") or [])
            values = list(attrs.get("values") or [])
            for i, b in enumerate(bands):
                v = values[i] if i < len(values) else None
                txt = _tr("（无数据）") if v is None else _fmt_value(v)
                lines.append(_tr("波段 {0}: {1}").format(b, txt))
        else:
            lines.append(_tr("要素: {0}").format(h.fid))
            layer = h.layer
            for k2, v in _ordered_items(
                    h.attrs, layer.fields() if layer else []):
                lines.append("%s: %s" % (k2, v))
        return lines

    def _on_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self.tree)
        act = menu.addAction(_tr("复制"))
        text = item.text(0)
        act.triggered.connect(
            lambda *a: QGuiApplication.clipboard().setText(text))
        menu.exec(self.tree.viewport().mapToGlobal(pos))


def _layer_key_of(hit):
    layer = getattr(hit, "layer", None)
    if layer is not None:
        try:
            lid = layer.id()
        except Exception:
            _log.exception("silent exception in _layer_key_of")
            lid = None
        if lid:
            return "id:%s" % lid
    return "name:%s" % _layer_name_of(hit)


def _layer_name_of(hit):
    layer = getattr(hit, "layer", None)
    if layer is not None:
        try:
            nm = layer.name()
        except Exception:
            _log.exception("silent exception in _layer_name_of")
            nm = None
        if nm:
            return nm
    try:
        nm = hit.layer_name()
    except Exception:
        _log.exception("silent exception in _layer_name_of")
        nm = None
    return nm or _tr("图层")


def _ordered_items(attrs, fields):
    names = []
    for f in (fields or []):
        nm = f[0] if isinstance(f, (tuple, list)) else str(f)
        if nm not in names:
            names.append(nm)
    for k in (attrs or {}):
        if k not in names:
            names.append(k)
    out = []
    for nm in names:
        v = (attrs or {}).get(nm)
        out.append((nm, "" if v is None else str(v)))
    return out


class GgsIdentifyCoord(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsIdentifyCoord")
class GgsIdentifyTopBar(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsIdentifyTopBar")
