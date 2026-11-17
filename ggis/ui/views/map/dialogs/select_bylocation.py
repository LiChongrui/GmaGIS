# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtWidgets import (QButtonGroup, QDialogButtonBox, QGroupBox,
                              QHBoxLayout, QLabel, QVBoxLayout)

from ggis.core.app import i18n
from ggis.core.model.layer import GgsVectorLayer
from ggis.core.expr.query import PREDICATE_LABELS, SPATIAL_PREDICATES
from ggis.core.model.selection import GgsSelection
from ggis.common.base.dialog import GgsDialog
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QRadioButton

_tr = i18n.tr

MODE_REPLACE = "replace"
MODE_ADD = "add"
MODE_SUBTRACT = "subtract"
MODE_INTERSECT = "intersect"

_MODE_LABELS = (
    (MODE_REPLACE, "替换当前选择"),
    (MODE_ADD, "加入当前选择"),
    (MODE_SUBTRACT, "从当前选择中减去"),
    (MODE_INTERSECT, "与当前选择求交"),
)


def _hits_of(layer, geoms, pred, dist):
    from ggis.core.expr.query import features_by_predicate
    hit = set()
    for g in geoms:
        for fid in features_by_predicate(layer, g, pred, dist):
            hit.add(fid)
    return sorted(hit)


class GgsSelectByLocationDialog(GgsDialog):

    def __init__(self, layer, project=None, canvas=None, parent=None):
        super().__init__(parent)
        self._layer = layer
        self._project = project
        self._canvas = canvas
        self._result_fids = []
        self.setObjectName("GgsSelectByLocationDialog")
        self.setWindowTitle(_tr("按位置选择 — {0}").format(layer.name()))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("sel_bylocation", size=16))
        self.resize(560, 460)
        self._build()

    def _vector_layers(self):
        out = []
        if self._project is None:
            return out
        for l in self._project.layers():
            if not isinstance(l, GgsVectorLayer):
                continue
            if not l.is_valid():
                continue
            if l is self._layer:
                continue
            out.append(l)
        return out

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        head = QLabel(_tr("选择「{0}」中满足下列空间关系的要素").format(
            self._layer.name()))
        head.setWordWrap(True)
        lay.addWidget(head)

        box_ref = QGroupBox(_tr("参考几何"), self)
        rl = QVBoxLayout(box_ref)
        rl.setContentsMargins(10, 10, 10, 10)
        rl.setSpacing(6)

        row_layer = QHBoxLayout()
        row_layer.setSpacing(6)
        self.rb_layer = GgsSblRefLayer(_tr("来自图层："))
        row_layer.addWidget(self.rb_layer)
        self.cmb_layer = GgsSblLayerCombo()
        for l in self._vector_layers():
            self.cmb_layer.addItem(l.name(), l)
        row_layer.addWidget(self.cmb_layer, 1)
        rl.addLayout(row_layer)

        indent = QHBoxLayout()
        indent.setSpacing(6)
        indent.addSpacing(20)
        self.chk_selected = GgsSblOnlySelected(
            _tr("只用该图层中已选中的要素作为参考"))
        indent.addWidget(self.chk_selected)
        rl.addLayout(indent)

        self.rb_extent = GgsSblRefExtent(_tr("当前地图视图范围"))
        rl.addWidget(self.rb_extent)

        if self.cmb_layer.count():
            self.rb_layer.setChecked(True)
        else:
            self.rb_extent.setChecked(True)
            self.rb_layer.setEnabled(False)
            self.cmb_layer.setEnabled(False)
            self.chk_selected.setEnabled(False)
        lay.addWidget(box_ref)

        box_rel = QGroupBox(_tr("空间关系"), self)
        rl2 = QVBoxLayout(box_rel)
        rl2.setContentsMargins(10, 10, 10, 10)
        rl2.setSpacing(6)

        row = QHBoxLayout()
        self.cmb_pred = GgsSblPredicate()
        for p in SPATIAL_PREDICATES:
            self.cmb_pred.addItem(_tr(PREDICATE_LABELS.get(p, p)), p)
        row.addWidget(QLabel(_tr("关系")))
        row.addWidget(self.cmb_pred, 1)
        rl2.addLayout(row)

        self.sp_dist = GgsSblDistance()
        self.sp_dist.setDecimals(4)
        self.sp_dist.setRange(0.0, 1e9)
        self.sp_dist.setValue(100.0)
        self.sp_dist.setSuffix(_tr(" 地图单位"))
        drow = QHBoxLayout()
        self.lbl_dist = QLabel(_tr("距离"))
        drow.addWidget(self.lbl_dist)
        drow.addWidget(self.sp_dist, 1)
        rl2.addLayout(drow)
        lay.addWidget(box_rel)

        box_mode = QGroupBox(_tr("结果"), self)
        ml = QVBoxLayout(box_mode)
        ml.setContentsMargins(10, 10, 10, 10)
        ml.setSpacing(6)
        self._mode_buttons = []
        self._mode_group = QButtonGroup(box_mode)
        for key, label in _MODE_LABELS:
            rb = GgsSblMode(_tr(label))
            rb.setProperty("mode", key)
            ml.addWidget(rb)
            self._mode_group.addButton(rb)
            self._mode_buttons.append(rb)
        self._mode_buttons[0].setChecked(True)
        lay.addWidget(box_mode)

        lay.addStretch(1)

        bbox = QDialogButtonBox(self)
        self.btn_ok = bbox.addButton(_tr("选择"),
                                     QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.addButton(_tr("取消"),
                       QDialogButtonBox.ButtonRole.RejectRole)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)

        self.cmb_pred.currentIndexChanged.connect(self._on_pred_changed)
        self.rb_layer.toggled.connect(self._on_ref_changed)
        self.rb_extent.toggled.connect(self._on_ref_changed)
        self._on_pred_changed()

    def _on_pred_changed(self, *_):
        is_dist = self.predicate() == "distance"
        self.sp_dist.setEnabled(is_dist)
        self.lbl_dist.setEnabled(is_dist)

    def _on_ref_changed(self, *_):
        use_layer = self.rb_layer.isChecked()
        self.cmb_layer.setEnabled(use_layer)
        self.chk_selected.setEnabled(use_layer)

    def predicate(self):
        d = self.cmb_pred.currentData()
        return str(d) if d else "intersects"

    def distance(self):
        return float(self.sp_dist.value())

    def mode(self):
        for rb in self._mode_buttons:
            if rb.isChecked():
                return str(rb.property("mode") or MODE_REPLACE)
        return MODE_REPLACE

    def result_fids(self):
        return list(self._result_fids)

    def _reference_geoms(self):
        self._err = ""
        if self.rb_extent.isChecked():
            if self._canvas is None:
                self._err = _tr("没有地图视图，无法取当前范围")
                return []
            try:
                ext = self._canvas.extent()
            except Exception:
                exc_note("_reference_geoms @ ggis/ui/views/map/dialogs/select_bylocation.py:245")
                ext = None
            if ext is None or ext.is_empty():
                self._err = _tr("当前地图视图没有有效范围")
                return []
            from shapely.geometry import box
            return self._to_target_crs(
                [box(ext.xmin, ext.ymin, ext.xmax, ext.ymax)], self._canvas)

        ref = self.cmb_layer.currentData()
        if ref is None:
            self._err = _tr("没有可用的参考图层")
            return []
        fids = None
        if self.chk_selected.isChecked():
            try:
                fids = sorted(GgsSelection.instance().fids(ref))
            except Exception:
                exc_note("_reference_geoms @ ggis/ui/views/map/dialogs/select_bylocation.py:263")
                fids = []
            if not fids:
                self._err = _tr("参考图层里没有选中的要素")
                return []
        geoms = []
        if fids is None:
            for _f, _a, g in ref.features():
                if g is not None and not getattr(g, "is_empty", True):
                    geoms.append(g)
        else:
            for fid in fids:
                _a, g = ref.feature(fid)
                if g is not None and not getattr(g, "is_empty", True):
                    geoms.append(g)
        if not geoms:
            self._err = _tr("参考图层里没有可用几何")
        try:
            src = ref.crs()
        except Exception:
            exc_note("_reference_geoms @ ggis/ui/views/map/dialogs/select_bylocation.py:282")
            src = None
        return self._to_target_crs(geoms, src)

    def _to_target_crs(self, geoms, source):
        if self._layer is None or source is None or not geoms:
            return geoms
        try:
            from ggis.core.expr.query import to_layer_geometry
        except Exception:
            exc_note("_to_target_crs @ ggis/ui/views/map/dialogs/select_bylocation.py:302")
            return geoms
        out = []
        for g in geoms:
            try:
                out.append(to_layer_geometry(self._layer, g, source))
            except Exception:
                exc_note("_to_target_crs @ ggis/ui/views/map/dialogs/select_bylocation.py:308")
                out.append(g)
        return out

    def _compute(self):
        geoms = self._reference_geoms()
        if not geoms:
            self._result_fids = []
            return []
        fids = _hits_of(self._layer, geoms, self.predicate(), self.distance())
        self._result_fids = list(fids or [])
        return fids

    def apply_to_selection(self):
        geoms = self._reference_geoms()
        if not geoms:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, _tr("按位置选择"),
                self._err or _tr("参考几何为空"))
            return 0
        fids = _hits_of(self._layer, geoms, self.predicate(), self.distance())
        self._result_fids = list(fids or [])
        sel = GgsSelection.instance()
        layer = self._layer
        hit = set(self._result_fids)
        mode = self.mode()
        if mode == MODE_REPLACE:
            sel.set_fids(layer, sorted(hit))
        elif mode == MODE_ADD:
            sel.add_fids(layer, sorted(hit))
        elif mode == MODE_SUBTRACT:
            sel.remove_fids(layer, sorted(hit))
        elif mode == MODE_INTERSECT:
            try:
                cur = set(sel.fids(layer))
            except Exception:
                exc_note("apply_to_selection @ ggis/ui/views/map/dialogs/select_bylocation.py:360")
                cur = set()
            sel.set_fids(layer, sorted(cur & hit))
        return sel.count(layer)


class GgsSblDistance(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblDistance")
class GgsSblLayerCombo(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblLayerCombo")
class GgsSblOnlySelected(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblOnlySelected")
class GgsSblPredicate(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblPredicate")
class GgsSblRefExtent(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblRefExtent")
class GgsSblRefLayer(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblRefLayer")


from PySide6.QtWidgets import QRadioButton



class GgsSblMode(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSblMode")
