# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QButtonGroup, QCheckBox,
                               QComboBox, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QRadioButton, QSpinBox,
                               QVBoxLayout, QWidget, QProgressBar,
                               QApplication)

from ggis.core.app import i18n
from ...core.analysis import (CAP_STYLES, JOIN_STYLES, OPS, AnalysisParams,
                              OP_BUFFER, OP_CENTROID, OP_DELETE_DUPLICATES,
                              OP_DENSIFY, OP_DISSOLVE, OP_ROUND_COORDINATES,
                              OP_SIMPLIFY, op_label)
from ...io.formats import VECTOR_WRITE_FORMATS as _VECTOR_ROWS
from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons as _icons
from ggis.common.styling import themes
from ggis.common.widgets.inputs import GgsLayerInputWidget, GgsLayerOutputWidget
from ggis.common.widgets.displays import GgsDimLabel
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr


def _make_checklist(options, checked_csv):
    box = QWidget()
    g = QGridLayout(box)
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(2)
    checked = {s.strip()
               for s in str(checked_csv or "").split(",") if s.strip()}
    boxes = []
    for k, opt in enumerate(options or []):
        val = str(opt[0])
        cb = QCheckBox(_tr(str(opt[1])))
        cb.setChecked(val in checked)
        g.addWidget(cb, k // 2, k % 2)
        boxes.append((val, cb))
    box.ggs_checklist = boxes
    return box


def _checklist_value(w):
    boxes = getattr(w, "ggs_checklist", None)
    if boxes is None:
        return None
    return ",".join(val for val, cb in boxes if cb.isChecked())

_ROLE_FROM_FILE = int(Qt.ItemDataRole.UserRole) + 1


_CREATION_OPTIONS = {
    "GPKG": [
        ("SPATIAL_INDEX", "空间索引", ["YES", "NO"], "YES", "layer"),
        ("IDENTIFIER", "标识符", [], "", "layer"),
    ],
    "ESRI Shapefile": [
        ("ENCODING", "字符编码",
         ["UTF-8", "GBK", "GB18030", "ISO-8859-1"], "UTF-8", "encoding"),
    ],
    "GeoJSON": [
        ("RFC7946", "严格 RFC 7946（WGS84）", ["NO", "YES"], "NO", "layer"),
        ("NATIVE_DATA", "保留原生属性类型", ["YES", "NO"], "YES", "layer"),
    ],
    "FlatGeobuf": [
        ("SPATIAL_INDEX", "空间索引", ["YES", "NO"], "YES", "dataset"),
    ],
    "GML": [
        ("FORMAT", "GML 版本", ["GML2", "GML3"], "GML3", "dataset"),
    ],
    "KML": [
        ("NameField", "名称字段", [], "", "layer"),
    ],
    "MapInfo File": [
        ("ENCODING", "字符编码", ["UTF-8", "GBK", "ISO-8859-1"], "UTF-8",
         "encoding"),
    ],
}

_OUT_FORMATS = [
    (drv, name, suffix, list(_CREATION_OPTIONS.get(drv) or []))
    for suffix, drv, name, _filt in _VECTOR_ROWS
]

_SUFFIX_DRIVER = [(suffix, drv) for suffix, drv, _n, _f in _VECTOR_ROWS]

_OUT_BY_DRIVER = {d: (d, lab, suf, opts) for d, lab, suf, opts in _OUT_FORMATS}


def _fmt_by_suffix(path):
    low = str(path or "").lower()
    for d, _lab, suf, _o in _OUT_FORMATS:
        if low.endswith(suf):
            return _OUT_BY_DRIVER[d]
    return None


class GgsAnalysisDialog(GgsDialog):

    def __init__(self, project, active_layer=None, parent=None,
                 dark_bg=True, op=None, allow_batch=True, lock_op=False):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._project = project
        self._dark = bool(dark_bg)
        self.setObjectName("GgsAnalysisDialog")
        self.setWindowTitle(_tr("空间分析"))
        self.resize(560, 520)
        self.overlay = None
        self._runner = None
        self._cancelled = False
        self._running = False
        self._task_token = None
        self._build()
        self._fill_layers(active_layer)
        try:
            self.w_in.layerPicked.connect(self._sync_selected_enabled)
        except Exception:
            _log.exception("silent exception in __init__")
        try:
            from ggis.core.model.selection import GgsSelection
            GgsSelection.instance().changed.connect(
                self._sync_selected_enabled)
        except Exception:
            _log.exception("silent exception in __init__")
        self._sync_selected_enabled()
        if op:
            i = self.cmb_op.findData(str(op))
            if i >= 0:
                self.cmb_op.setCurrentIndex(i)
        self._lock_op = bool(lock_op)
        if self._lock_op and op:
            self.gb_op.setVisible(False)
            self.setWindowTitle(_tr(op_label(str(op))))
        self._sync_op()
        self._sync_out()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        gb0 = QGroupBox(_tr("算法"))
        self.gb_op = gb0
        g0 = QFormLayout(gb0)
        g0.setContentsMargins(8, 8, 8, 8)
        self.cmb_op = QComboBox()
        for code, spec in OPS.items():
            self.cmb_op.addItem(_tr(spec["label"]), code)
        self.cmb_op.currentIndexChanged.connect(self._sync_op)
        g0.addRow(_tr("操作"), self.cmb_op)
        self.lbl_desc = QLabel()
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setEnabled(False)
        g0.addRow("", self.lbl_desc)
        lay.addWidget(gb0)

        gb1 = QGroupBox(_tr("输入"))
        self.gb_in = gb1
        g1 = QFormLayout(gb1)
        g1.setContentsMargins(8, 8, 8, 8)
        self.w_in = GgsLayerInputWidget(kind="vector", title=_tr("输入图层"))
        self.w_in.set_file_loader(True)
        self.w_in.filePicked.connect(
            lambda path: self._load_file_layer(path, self.w_in))
        g1.addRow(self.w_in)
        self.w_overlay = GgsLayerInputWidget(kind="vector",
                                             title=_tr("叠加图层"))
        self.w_overlay.set_file_loader(True)
        self.w_overlay.filePicked.connect(
            lambda path: self._load_file_layer(path, self.w_overlay))
        g1.addRow(self.w_overlay)
        self.chk_selected = QCheckBox(_tr("仅处理选中要素"))
        g1.addRow("", self.chk_selected)
        lay.addWidget(gb1)

        self.gb_param = QGroupBox(_tr("参数"))
        g2 = QFormLayout(self.gb_param)
        g2.setContentsMargins(8, 8, 8, 8)
        self._param_rows = {}
        self.spin_dist = QDoubleSpinBox()
        self.spin_dist.setRange(-1e9, 1e9)
        self.spin_dist.setDecimals(3)
        self.spin_dist.setValue(100.0)
        self.cmb_unit = QComboBox()
        self.cmb_unit.addItem(_tr("地图单位"), "map")
        self.cmb_unit.addItem(_tr("米（按椭球换算）"), "meters")
        row = QHBoxLayout()
        row.addWidget(self.spin_dist, 2)
        row.addWidget(self.cmb_unit, 1)
        self._w_dist = self._wrap(row)
        g2.addRow(_tr("缓冲距离"), self._w_dist)
        self._param_rows["distance"] = self._w_dist

        self.spin_seg = QSpinBox()
        self.spin_seg.setRange(1, 200)
        self.spin_seg.setValue(8)
        g2.addRow(_tr("圆弧分段（每 1/4 圆）"), self.spin_seg)
        self._param_rows["segments"] = self.spin_seg

        self.cmb_cap = QComboBox()
        for code, label in CAP_STYLES:
            self.cmb_cap.addItem(_tr(label), code)
        g2.addRow(_tr("线端头"), self.cmb_cap)
        self._param_rows["cap"] = self.cmb_cap
        self.cmb_join = QComboBox()
        for code, label in JOIN_STYLES:
            self.cmb_join.addItem(_tr(label), code)
        g2.addRow(_tr("拐角"), self.cmb_join)
        self._param_rows["join"] = self.cmb_join

        self.chk_dissolve = QCheckBox(_tr("合并为一个要素（融合）"))
        g2.addRow("", self.chk_dissolve)
        self._param_rows["dissolve"] = self.chk_dissolve
        self.cmb_field = QComboBox()
        self._lbl_field = g2.labelForField(self.cmb_field)
        g2.addRow(_tr("融合字段（分组）"), self.cmb_field)
        self._param_rows["field"] = self.cmb_field
        self.chk_inside = QCheckBox(_tr("质心落在面内（内部点）"))
        g2.addRow("", self.chk_inside)
        self._param_rows["inside"] = self.chk_inside

        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0.0, 1e9)
        self.spin_tol.setDecimals(3)
        self.spin_tol.setValue(1.0)
        self._lbl_tol = g2.labelForField(self.spin_tol)
        g2.addRow(_tr("容差 / 间距（地图单位）"), self.spin_tol)
        self._param_rows["tolerance"] = self.spin_tol

        self.spin_dec = QSpinBox()
        self.spin_dec.setRange(0, 12)
        self.spin_dec.setValue(6)
        self._lbl_dec = g2.labelForField(self.spin_dec)
        g2.addRow(_tr("小数位"), self.spin_dec)
        self._param_rows["decimals"] = self.spin_dec

        self._w_extra = QWidget()
        _ex_form = QFormLayout(self._w_extra)
        _ex_form.setContentsMargins(0, 0, 0, 0)
        g2.addRow(self._w_extra)
        self._param_rows["__extra__"] = self._w_extra
        self._extra_ctrls = {}
        self._extra_edited = False
        lay.addWidget(self.gb_param)

        gb3 = QGroupBox(_tr("输出"))
        self.gb_out = gb3
        g3 = QFormLayout(gb3)
        self._out_form = g3
        g3.setContentsMargins(8, 8, 8, 8)
        self.rad_layer = QRadioButton(_tr("写入内存"))
        self.rad_file = QRadioButton(_tr("写入文件"))
        self.rad_layer.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rad_layer)
        grp.addButton(self.rad_file)
        grp.buttonToggled.connect(lambda *_: self._sync_out())
        _out_mode = QWidget(self)
        _out_mode_lay = QHBoxLayout(_out_mode)
        _out_mode_lay.setContentsMargins(0, 0, 0, 0)
        _out_mode_lay.setSpacing(16)
        _out_mode_lay.addWidget(self.rad_layer)
        _out_mode_lay.addWidget(self.rad_file)
        _out_mode_lay.addStretch(1)
        g3.addRow(_out_mode)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText(_tr("留空自动命名"))
        g3.addRow(_tr("结果图层名"), self.edit_name)

        self.w_out = GgsLayerOutputWidget(kind="vector")
        self.w_out.set_options_provider(self._fill_out_opts)
        try:
            self.w_out.ed_file.textChanged.connect(self._on_out_file_typed)
        except Exception:
            _log.exception("silent exception in _build")
        g3.addRow(self.w_out)
        lay.addWidget(gb3)


        self.prog_box = QWidget()
        pv = QVBoxLayout(self.prog_box)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(4)
        self.lbl_stage = GgsDimLabel("")
        self.lbl_stage.setWordWrap(True)
        pv.addWidget(self.lbl_stage)
        self.bar = QProgressBar()
        self.bar.setObjectName("GgsProgressBar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFixedHeight(18)
        pv.addWidget(self.bar)

        lay.addStretch(1)
        lay.addWidget(self.prog_box)
        rowb = QHBoxLayout()
        rowb.setContentsMargins(0, 0, 0, 0)
        rowb.setSpacing(8)
        self.chk_add_to_map = QCheckBox(_tr("将结果加入到地图"))
        self.chk_add_to_map.setChecked(True)
        rowb.addWidget(self.chk_add_to_map)
        rowb.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        self._bb = bb
        self._set_action_face(False)
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(_tr("关闭"))
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        rowb.addWidget(bb)
        lay.addLayout(rowb)

    @staticmethod
    def _hrow(*widgets):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        for i, w in enumerate(widgets):
            row.addWidget(w, 1 if i == 0 else 0)
        return row

    @staticmethod
    def _wrap(inner):
        w = QWidget()
        inner.setContentsMargins(0, 0, 0, 0)
        w.setLayout(inner)
        return w

    def _vector_layers(self):
        out = []
        try:
            for l in self._project.layers():
                if l.is_vector() and l.is_valid():
                    out.append(l)
        except Exception:
            _log.exception("silent exception in _vector_layers")
        return out

    @staticmethod
    def _row_visible(fmt, widget, visible):
        widget.setVisible(visible)
        if fmt is None:
            return
        try:
            if hasattr(fmt, "setRowVisible"):
                fmt.setRowVisible(widget, visible)
            lab = fmt.labelForField(widget)
            if lab is not None:
                lab.setVisible(visible)
        except Exception:
            _log.exception("silent exception in _row_visible")

    def _set_in_row_visible(self, widget, visible):
        self._row_visible(getattr(self, "_in_form", None), widget, visible)

    def _load_file_layer(self, path, w):
        fname = str(path).replace("\\", "/").rsplit("/", 1)[-1]
        for i in range(w.cmb.count()):
            old = w.cmb.itemData(i)
            try:
                if old is not None and hasattr(old, "source") \
                        and str(old.source() or "") == path:
                    w.cmb.setCurrentIndex(i)
                    w.cmb.repaint()
                    self._reload_fields()
                    return
            except Exception:
                _log.exception("silent exception in _load_file_layer")
                continue
        lyr = None
        err = ""
        try:
            from ...io.vector_io import read_vector
            lyr = read_vector(path)
        except Exception as e:
            _log.exception("silent exception in _load_file_layer")
            err = str(e)
        if lyr is not None and hasattr(lyr, "on_done"):
            lyr.on_done(lambda ev: self._use_file_layer(
                ev.get("result"), w, fname, ""))
            lyr.on_fail(lambda ev: self._use_file_layer(
                None, w, fname, str(ev.get("error"))))
            return
        self._use_file_layer(lyr, w, fname, err)

    def _use_file_layer(self, lyr, w, fname, err=""):
        if lyr is None or not lyr.is_valid():
            msg = _tr("读不出这个矢量文件：{0}").format(fname)
            if err:
                msg += "\n" + err
            self._flash(msg)
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("选择矢量文件"), msg)
            except Exception:
                _log.exception("silent exception in _use_file_layer")
            return
        w.add_layer(lyr, "%s（文件）" % lyr.name())
        w.cmb.repaint()
        self._reload_fields()

    def _input_layer(self):
        v = self.w_in.value()
        return None if isinstance(v, str) else v

    def _sync_selected_enabled(self, *_a):
        chk = getattr(self, "chk_selected", None)
        if chk is None:
            return
        lyr = self._input_layer()
        has_sel = False
        if lyr is not None:
            try:
                from ggis.core.model.selection import GgsSelection
                has_sel = bool(GgsSelection.instance().fids(lyr))
            except Exception:
                _log.exception("silent exception in _sync_selected_enabled")
                has_sel = False
        chk.setEnabled(has_sel)
        if not has_sel:
            try:
                chk.setChecked(False)
            except Exception:
                _log.exception("silent exception in _sync_selected_enabled")

    def _fill_layers(self, active_layer=None):
        layers = self._vector_layers()
        items = [("%s (%d)" % (l.name(), l.feature_count()), l)
                 for l in layers]
        for w in (self.w_in, self.w_overlay):
            w.set_items(items)
        if layers:
            i = self.w_in.cmb.findData(active_layer) if active_layer else -1
            self.w_in.cmb.setCurrentIndex(max(1, i + 1))
            self.w_overlay.cmb.setCurrentIndex(1 if len(layers) == 1 else 2)
        self._reload_fields()

    def _reload_fields(self):
        self.cmb_field.clear()
        self.cmb_field.addItem(_tr("（不分组，全部融合）"), "")
        lyr = self._input_layer()
        try:
            for n, _t in (lyr.fields() if lyr is not None else []):
                self.cmb_field.addItem(str(n), str(n))
        except Exception:
            _log.exception("silent exception in _reload_fields")
        self._retitle_params(self._current_op(),
                             OPS.get(self._current_op(), {}))

    def _current_op(self):
        return str(self.cmb_op.currentData() or OP_BUFFER)

    def _sync_op(self, *_a):
        op = self._current_op()
        spec = OPS.get(op, {})
        need_ov = bool(spec.get("needs_overlay"))
        need_dist = bool(spec.get("needs_distance"))
        need_field = bool(spec.get("by_field"))
        self.w_overlay.setVisible(need_ov)
        for w in (self.spin_dist, self.cmb_unit, self.spin_seg,
                  self.cmb_cap, self.cmb_join):
            w.setEnabled(need_dist)
        self.chk_dissolve.setEnabled(bool(spec.get("dissolvable")))
        self.cmb_field.setEnabled(need_field)
        self.chk_inside.setEnabled(op == OP_CENTROID)
        self.spin_tol.setEnabled(bool(spec.get("needs_tolerance")))
        self.spin_dec.setEnabled(bool(spec.get("needs_decimals")))
        self._sync_param_rows(op, spec)
        self._rebuild_extra(op, spec)
        self._retitle_params(op, spec)
        self.lbl_desc.setText(self._describe(op, spec))

    def _visible_rows(self, op, spec):
        if spec.get("params"):
            return ["__extra__"]
        rows = ["dissolve"] if spec.get("dissolvable") else []
        if spec.get("needs_distance"):
            rows += ["distance", "segments", "cap", "join"]
        if op == OP_DISSOLVE:
            rows = ["field"]
        elif op == OP_DELETE_DUPLICATES:
            rows = ["field"]
        if op == OP_CENTROID:
            rows += ["inside"]
        if spec.get("needs_tolerance"):
            rows += ["tolerance"]
        if spec.get("needs_decimals"):
            rows += ["decimals"]
        if op == OP_DELETE_DUPLICATES:
            rows = ["field"]
        seen, out = set(), []
        for r in rows:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    def _sync_param_rows(self, op, spec):
        keep = set(self._visible_rows(op, spec))
        fmt = self.gb_param.layout()
        for key, w in (self._param_rows or {}).items():
            vis = key in keep
            try:
                w.setVisible(vis)
                if fmt is not None and hasattr(fmt, "setRowVisible"):
                    fmt.setRowVisible(w, vis)
                if fmt is not None:
                    lab = fmt.labelForField(w)
                    if lab is not None:
                        lab.setVisible(vis)
            except Exception:
                _log.exception("silent exception in _sync_param_rows")
        self.gb_param.setVisible(bool(keep))

    def _retitle_params(self, op, spec):
        if self._lbl_field is not None:
            self._lbl_field.setText(
                _tr("融合字段（分组）") if op == OP_DISSOLVE
                else _tr("去重字段（留空则按几何去重）"))
        if self.cmb_field.count():
            self.cmb_field.setItemText(
                0, _tr("（不分组，全部融合）") if op == OP_DISSOLVE
                else _tr("（按几何去重）"))
        if self._lbl_tol is not None:
            self._lbl_tol.setText(
                _tr("简化容差（地图单位）") if op == OP_SIMPLIFY
                else _tr("最大间距（地图单位）"))

    def _on_extra_edited(self, *_a):
        self._extra_edited = True

    def _rebuild_extra(self, op, spec):
        form = self._w_extra.layout()
        while form.count():
            item = form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._extra_ctrls = {}
        self._extra_edited = False
        for d in (spec.get("params") or []):
            key = str(d.get("key") or "")
            if not key:
                continue
            typ = str(d.get("type") or "number")
            label = _tr(str(d.get("label") or key))
            if typ == "text":
                w = QLineEdit()
                w.setText(str(d.get("default") or ""))
            elif typ == "checklist":
                w = _make_checklist(d.get("options") or [],
                                    str(d.get("default") or ""))
            elif typ == "choice":
                w = QComboBox()
                for val, name in (d.get("choices") or []):
                    w.addItem(_tr(str(name)), str(val))
                i = w.findData(str(d.get("default")))
                if i >= 0:
                    w.setCurrentIndex(i)
            elif typ == "int":
                w = QSpinBox()
                mn, mx = d.get("min"), d.get("max")
                w.setRange(int(mn) if mn is not None else -1000000,
                           int(mx) if mx is not None else 1000000)
                w.setValue(int(d.get("default") or 0))
            else:
                w = QDoubleSpinBox()
                mn, mx = d.get("min"), d.get("max")
                w.setRange(float(mn) if mn is not None else -1e9,
                           float(mx) if mx is not None else 1e9)
                w.setDecimals(6)
                w.setValue(float(d.get("default") or 0.0))
            try:
                if isinstance(w, QLineEdit):
                    w.textEdited.connect(self._on_extra_edited)
                elif isinstance(w, QComboBox):
                    w.currentIndexChanged.connect(self._on_extra_edited)
                elif isinstance(w, QCheckBox):
                    w.toggled.connect(self._on_extra_edited)
                elif not hasattr(w, "ggs_checklist"):
                    w.valueChanged.connect(self._on_extra_edited)
            except Exception:
                _log.exception("silent exception in _rebuild_extra")
            if typ == "checklist":
                form.addRow(label, w)
            else:
                form.addRow(label, w)
            self._extra_ctrls[key] = w
        if op == "clip_by_rect" and not self._extra_edited:
            self._prefill_clip_rect()

    def _prefill_clip_rect(self):
        lyr = self._input_layer()
        if lyr is None:
            return
        try:
            ext = lyr.extent()
            vals = (ext.xmin, ext.ymin, ext.xmax, ext.ymax)
        except Exception:
            _log.exception("silent exception in _prefill_clip_rect")
            return
        for key, val in zip(("minx", "miny", "maxx", "maxy"), vals):
            w = self._extra_ctrls.get(key)
            if isinstance(w, QDoubleSpinBox):
                w.setValue(float(val))

    def _extra_values(self):
        out = {}
        for key, w in (self._extra_ctrls or {}).items():
            try:
                cv = _checklist_value(w)
                if cv is not None:
                    out[key] = cv
                elif isinstance(w, QLineEdit):
                    out[key] = str(w.text())
                elif isinstance(w, QComboBox):
                    out[key] = w.currentData()
                elif isinstance(w, QSpinBox):
                    out[key] = int(w.value())
                elif isinstance(w, QDoubleSpinBox):
                    out[key] = float(w.value())
            except Exception:
                _log.exception("silent exception in _extra_values")
                continue
        return out

    @staticmethod
    def _describe(op, spec):
        return ""

    def _make_params(self):
        op = self._current_op()
        spec = OPS.get(op, {})
        to_file = bool(self.rad_file.isChecked())
        out_spec = self.w_out.spec() if to_file else {}
        p = AnalysisParams(
            op=op,
            input_layer=self._input_layer(),
            overlay_layer=(self.w_overlay.value()
                           if spec.get("needs_overlay") else None),
            distance=float(self.spin_dist.value()),
            segments=int(self.spin_seg.value()),
            cap_style=self.cmb_cap.currentData(),
            join_style=self.cmb_join.currentData(),
            dissolve=bool(self.chk_dissolve.isChecked()
                          and spec.get("dissolvable")),
            by_field=(str(self.cmb_field.currentData() or "")
                      if op == OP_DISSOLVE else ""),
            distance_unit=str(self.cmb_unit.currentData() or "map"),
            centroid_inside=bool(self.chk_inside.isChecked()),
            tolerance=float(self.spin_tol.value()),
            decimals=int(self.spin_dec.value()),
            extra=self._extra_values(),
            selected_only=bool(self.chk_selected.isChecked()),
            output_name=(str(out_spec.get("name") or "") if to_file
                         else str(self.edit_name.text() or "")),
            output_path=(str(out_spec.get("filename") or "") if to_file
                         else ""))
        if to_file and p.output_path:
            p.output_driver = (str(out_spec.get("driver") or "")
                               or self._driver_for(p.output_path))
        return p

    def _current_driver(self):
        return str(self.w_out.spec().get("driver") or "")

    def _current_fmt(self):
        drv = self._current_driver()
        for d, lab, suf, opts in _OUT_FORMATS:
            if d == drv:
                return d, lab, suf, opts
        return None

    def _create_options(self):
        ds, ly, enc = {}, {}, ""
        for key, w in (self._opt_widgets or {}).items():
            try:
                val = w.currentData() if isinstance(w, QComboBox) else w.text()
            except Exception:
                _log.exception("silent exception in _create_options")
                continue
            if not val:
                continue
            scope = (self._opt_scope or {}).get(key, "dataset")
            if scope == "encoding":
                enc = str(val)
            elif scope == "layer":
                ly[str(key)] = str(val)
            else:
                ds[str(key)] = str(val)
        return ds, ly, enc

    def creation_options(self):
        if not self.rad_file.isChecked():
            return {}
        ds, ly, enc = self._create_options()
        return {"dataset": ds, "layer": ly, "encoding": enc}

    def _fill_out_opts(self, form, drv):
        self._opt_widgets = {}
        self._opt_scope = {}
        opts = (_OUT_BY_DRIVER.get(drv) or ("", "", "", []))[3]
        for key, label, choices, default, scope in opts:
            if choices:
                w = QComboBox()
                for c in choices:
                    w.addItem(c, c)
                i = w.findData(default)
                if i >= 0:
                    w.setCurrentIndex(i)
            else:
                w = QLineEdit()
                w.setPlaceholderText(default or "")
            w.setObjectName("GgsAnalysisOpt_" + str(key))
            self._opt_widgets[key] = w
            self._opt_scope[key] = scope
            form.addRow(_tr(label), w)

    def _sync_out(self, *_a):
        to_file = bool(self.rad_file.isChecked())
        self._row_visible(self._out_form, self.edit_name, not to_file)
        if to_file:
            self.w_out._build_opts()
        self.w_out.setVisible(to_file)

    def _on_out_file_typed(self, text):
        if str(text or "").strip() and not self.rad_file.isChecked():
            self.rad_file.setChecked(True)

    @staticmethod
    def _driver_for(path):
        low = str(path).lower()
        for suffix, driver in _SUFFIX_DRIVER:
            if low.endswith(suffix):
                return driver
        fmt = _fmt_by_suffix(low)
        return fmt[0] if fmt else ""

    def params(self):
        return self._make_params()

    def add_to_map(self):
        return bool(self.chk_add_to_map.isChecked())

    def set_runner(self, fn):
        self._runner = fn

    def feed(self, frac, text=""):
        try:
            v = int(max(0.0, min(1.0, float(frac))) * 100)
            self.bar.setValue(v)
        except Exception:
            _log.exception("silent exception in feed")
        if text:
            try:
                self.lbl_stage.setText(_tr(str(text)))
            except Exception:
                _log.exception("silent exception in feed")

    def cancelled(self):
        return bool(getattr(self, "_cancelled", False))

    def _on_stop(self):
        t = getattr(self, "_pending_task", None)
        if t is not None:
            try:
                t.cancel()
            except Exception:
                _log.exception("silent exception in _on_stop")
        self._cancelled = True
        try:
            self.lbl_stage.setText(_tr("正在取消…"))
            self._set_progress_face(self._FACE_CANCEL)
        except Exception:
            _log.exception("silent exception in _on_stop")

    def _set_action_face(self, running):
        try:
            ok = self._bb.button(QDialogButtonBox.StandardButton.Ok)
        except Exception:
            _log.exception("silent exception in _set_action_face")
            return
        try:
            ok.setText(_tr("终止") if running else _tr("运行"))
            ok.setEnabled(True)
            ok.setObjectName("GgsToolActionButton")
            ok.setIcon(_icons.icon("stop" if running else "processing",
                                   size=16))
            ok.setIconSize(QSize(16, 16))
            ok.setStyleSheet("" if not running else
                             "QPushButton#GgsToolActionButton { color: %s; }"
                             % themes.ERR_COLOR)
        except Exception:
            _log.exception("silent exception in _set_action_face")

    _FACE_RUN = "run"
    _FACE_DONE = "done"
    _FACE_CANCEL = "cancel"
    _FACE_FAIL = "fail"

    def _set_progress_face(self, state):
        c = themes.progress_face_color(state)
        try:
            self.bar.setStyleSheet(
                "" if c is None else
                "QProgressBar#GgsProgressBar::chunk { background: %s; }" % c)
        except Exception:
            _log.exception("silent exception in _set_progress_face")
        try:
            self.lbl_stage.setStyleSheet(
                "" if c is None else
                "QLabel#GgsDimLabel { color: %s; }" % c)
        except Exception:
            _log.exception("silent exception in _set_progress_face")

    def _begin_busy(self):
        self._cancelled = False
        self._running = True
        try:
            self.bar.setValue(0)
            self.lbl_stage.setText(_tr("准备中…"))
            self.bar.setVisible(True)
            self.prog_box.setVisible(True)
            self._set_progress_face(self._FACE_RUN)
        except Exception:
            _log.exception("silent exception in _begin_busy")
        self._set_action_face(True)
        self._set_busy_controls(True)
        try:
            QApplication.processEvents()
        except Exception:
            _log.exception("silent exception in _begin_busy")

    def _set_busy_controls(self, busy):
        for w in (self.gb_op, self.gb_in, self.gb_param, self.gb_out):
            try:
                w.setEnabled(not busy)
            except Exception:
                _log.exception("silent exception in _set_busy_controls")
        try:
            self.chk_add_to_map.setEnabled(not busy)
        except Exception:
            _log.exception("silent exception in _set_busy_controls")

    def _end_busy(self):
        self._running = False
        self._set_action_face(False)
        self._set_busy_controls(False)
        try:
            self._sync_op()
            self._sync_out()
        except Exception:
            _log.exception("silent exception in _end_busy")

    def write_to_file(self):
        return bool(self.rad_file.isChecked()
                    and self.w_out.spec().get("filename"))

    def output_path(self):
        return str(self.w_out.spec().get("filename") or "")

    def _flash(self, text):
        self.lbl_desc.setText("⚠ " + text)

    def reject(self):
        if getattr(self, "_running", False):
            self.hide()
            return
        super().reject()

    def closeEvent(self, ev):
        if getattr(self, "_running", False):
            self.hide()
            ev.ignore()
            return
        super().closeEvent(ev)

    def _accept(self):
        if getattr(self, "_running", False):
            self._on_stop()
            return
        p = self._make_params()
        err = p.validate()
        if err:
            self._flash(err)
            return
        runner = getattr(self, "_runner", None)
        if runner is None:
            self.accept()
            return
        self._begin_busy()
        try:
            res = runner(p, self.feed, self.cancelled)
        except Exception as e:
            _log.exception("silent exception in _accept")
            self._end_busy()
            self._flash(_tr("执行失败：{0}").format(e))
            return
        if res is not None and hasattr(res, "on_done"):
            self._pending_task = res
            try:
                from ..panels import task_dock as _td
                _td.bind_window(getattr(res, "token", None), self)
            except Exception:
                _log.exception("silent exception in _accept")

            def _ok(_ev):
                self._pending_task = None
                self._end_busy()
                cancelled = bool((_ev or {}).get("cancelled", False))
                self._set_progress_face(self._FACE_CANCEL if cancelled
                                        else self._FACE_DONE)
                self._flash(_tr("已取消") if cancelled
                            else _tr("运行完成"))

            def _bad(ev):
                self._pending_task = None
                self._end_busy()
                self._set_progress_face(self._FACE_FAIL)
                self._flash(_tr("执行失败：{0}").format(ev.get("error")))

            res.on_done(_ok)
            res.on_fail(_bad)
            return
        self._end_busy()
        self.accept()


class GgsAnalysisProgress(GgsDialog):

    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setObjectName("GgsAnalysisProgress")
        self.setWindowTitle(title or _tr("正在运行"))
        self.setModal(True)
        self.setFixedWidth(340)
        self._cancelled = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)
        self.lbl_title = GgsProgressTitle(title or _tr("正在运行"))
        self.lbl_title.setWordWrap(True)
        lay.addWidget(self.lbl_title)
        self.lbl_stage = GgsDimLabel(_tr("准备中…"))
        self.lbl_stage.setWordWrap(True)
        lay.addWidget(self.lbl_stage)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton(_tr("取消"))
        self.btn_cancel.clicked.connect(self._on_cancel)
        row.addWidget(self.btn_cancel)
        lay.addLayout(row)

    def feed(self, frac, text=""):
        try:
            self.bar.setValue(int(max(0.0, min(1.0, float(frac))) * 100))
        except Exception:
            _log.exception("silent exception in feed")
        if text:
            try:
                self.lbl_stage.setText(_tr(str(text)))
            except Exception:
                _log.exception("silent exception in feed")

    def cancelled(self):
        return bool(self._cancelled)

    def _on_cancel(self):
        self._cancelled = True
        try:
            self.btn_cancel.setEnabled(False)
            self.lbl_stage.setText(_tr("正在取消…"))
        except Exception:
            _log.exception("silent exception in _on_cancel")
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
        except Exception:
            _log.exception("silent exception in _on_cancel")


class GgsProgressTitle(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsProgressTitle")
