# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox,
                               QComboBox, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QProgressBar, QPushButton, QRadioButton,
                               QSpinBox, QVBoxLayout, QWidget)

from ggis.core.app import i18n
from ggis.core.analysis.raster_ops import RASTER_OPS, raster_op_label
from ggis.common.base.dialog import GgsDialog
from ggis.common.styling import icons as _icons
from ggis.common.styling import themes
from ggis.common.widgets.inputs import GgsExtentPicker
from ggis.common.widgets.inputs import (GgsLayerInputWidget,
    GgsLayerOutputWidget, GgsMultiLayerInputWidget)
from ggis.common.widgets.displays import GgsDimLabel
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr


class GgsRasterAnalysisDialog(GgsDialog):

    def __init__(self, project, active_layer=None, parent=None,
                 dark_bg=True, op=None, lock_op=False):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._project = project
        self._dark = bool(dark_bg)
        self.setObjectName("GgsRasterAnalysisDialog")
        self.setWindowTitle(_tr("栅格分析"))
        self.setFixedSize(560, 580)
        self.overlay = None
        self._runner = None
        self._cancelled = False
        self._running = False
        self._task_token = None
        self._pending_task = None
        self._extra_ctrls = {}
        self._extra_edited = False
        self._build()
        self._fill_layers(active_layer)
        try:
            self.w_in.layerPicked.connect(self._sync_extent_reference)
        except Exception:
            _log.exception("silent exception in __init__")
        if op:
            i = self.cmb_op.findData(str(op))
            if i >= 0:
                self.cmb_op.setCurrentIndex(i)
        self._lock_op = bool(lock_op)
        if self._lock_op and op:
            self.gb_op.setVisible(False)
            self.setWindowTitle(_tr(raster_op_label(str(op))))
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
        for code, spec in RASTER_OPS.items():
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
        self.w_in = GgsLayerInputWidget(kind="raster", title=_tr("输入图层"))
        self.w_in.set_file_loader(True)
        self.w_in.filePicked.connect(
            lambda path: self._load_raster_file(path))
        g1.addRow(self.w_in)
        self.w_mask = GgsLayerInputWidget(kind="vector",
                                          title=_tr("裁剪掩模（矢量，可选）"))
        self.w_mask.set_file_loader(True)
        self.w_mask.filePicked.connect(
            lambda path: self._load_vector_file(path))
        g1.addRow(self.w_mask)
        self.w_layers = GgsMultiLayerInputWidget(
            kind="raster", title=_tr("输入栅格（勾选多个）"))
        g1.addRow(self.w_layers)
        lay.addWidget(gb1)

        self.gb_param = QGroupBox(_tr("参数"))
        g2 = QFormLayout(self.gb_param)
        g2.setContentsMargins(8, 8, 8, 8)
        self.w_extent = GgsExtentPicker(modes=("layer", "custom"))
        g2.addRow(self.w_extent)
        self._w_extra = QWidget()
        _ex_form = QFormLayout(self._w_extra)
        _ex_form.setContentsMargins(0, 0, 0, 0)
        g2.addRow(self._w_extra)
        lay.addWidget(self.gb_param)

        gb3 = QGroupBox(_tr("输出"))
        self.gb_out = gb3
        g3 = QFormLayout(gb3)
        self._out_form = g3
        g3.setContentsMargins(8, 8, 8, 8)
        self.rad_memory = QRadioButton(_tr("写入内存"))
        self.rad_file = QRadioButton(_tr("写入文件"))
        self.rad_memory.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.rad_memory)
        grp.addButton(self.rad_file)
        grp.buttonToggled.connect(lambda *_: self._sync_out())
        _out_mode = QWidget(self)
        _out_mode_lay = QHBoxLayout(_out_mode)
        _out_mode_lay.setContentsMargins(0, 0, 0, 0)
        _out_mode_lay.setSpacing(16)
        _out_mode_lay.addWidget(self.rad_memory)
        _out_mode_lay.addWidget(self.rad_file)
        _out_mode_lay.addStretch(1)
        g3.addRow(_out_mode)

        self.w_out_raster = GgsLayerOutputWidget(kind="raster")
        try:
            self.w_out_raster.ed_file.textChanged.connect(
                self._on_out_file_typed)
        except Exception:
            _log.exception("silent exception in _build")
        g3.addRow(self.w_out_raster)
        self.w_out_vector = GgsLayerOutputWidget(kind="vector")
        try:
            self.w_out_vector.ed_file.textChanged.connect(
                self._on_out_file_typed)
        except Exception:
            _log.exception("silent exception in _build")
        g3.addRow(self.w_out_vector)
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
        _ph = self.prog_box.sizeHint().height()
        self.bar.setVisible(False)
        self.prog_box.setFixedHeight(max(_ph, 40))

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

    def _load_raster_file(self, path):
        fname = str(path).replace("\\", "/").rsplit("/", 1)[-1]
        try:
            from ...io.raster_io import read_raster
            lyr = read_raster(path)
        except Exception as e:
            self._flash(_tr("读不出这个栅格文件：{0}").format(fname))
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("选择栅格文件"),
                                  _tr("读不出这个栅格文件：{0}").format(fname)
                                  + "\n" + str(e))
            except Exception:
                _log.exception("silent exception in _load_raster_file")
            return
        if lyr is None or not lyr.is_valid():
            msg = _tr("读不出这个栅格文件：{0}").format(fname)
            self._flash(msg)
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("选择栅格文件"), msg)
            except Exception:
                _log.exception("silent exception in _load_raster_file")
            return
        self.w_in.add_layer(lyr, "%s（文件）" % lyr.name())
        self.w_in.cmb.repaint()
        self._sync_extent_reference()
        self.w_layers.add_layer(lyr, "%s（文件）" % lyr.name())

    def _load_vector_file(self, path):
        fname = str(path).replace("\\", "/").rsplit("/", 1)[-1]
        try:
            from ...io.vector_io import read_vector
            lyr = read_vector(path)
        except Exception as e:
            self._flash(_tr("读不出这个矢量文件：{0}").format(fname))
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("选择矢量文件"),
                                  _tr("读不出这个矢量文件：{0}").format(fname)
                                  + "\n" + str(e))
            except Exception:
                _log.exception("silent exception in _load_vector_file")
            return
        if lyr is None or not lyr.is_valid():
            msg = _tr("读不出这个矢量文件：{0}").format(fname)
            self._flash(msg)
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("选择矢量文件"), msg)
            except Exception:
                _log.exception("silent exception in _load_vector_file")
            return
        self.w_mask.add_layer(lyr, "%s（文件）" % lyr.name())
        self.w_mask.cmb.repaint()

    def _raster_layers(self):
        out = []
        try:
            for l in self._project.layers():
                if getattr(l, "is_raster", lambda: False)() and \
                        getattr(l, "is_valid", lambda: False)():
                    out.append(l)
        except Exception:
            _log.exception("silent exception in _raster_layers")
        return out

    def _vector_layers(self):
        out = []
        try:
            for l in self._project.layers():
                if getattr(l, "is_vector", lambda: False)() and \
                        getattr(l, "is_valid", lambda: False)():
                    out.append(l)
        except Exception:
            _log.exception("silent exception in _vector_layers")
        return out

    def _fill_layers(self, active_layer=None):
        raster_items = [("%s" % l.name(), l) for l in self._raster_layers()]
        self.w_in.set_items(raster_items)
        i = self.w_in.cmb.findData(active_layer) if active_layer else -1
        if raster_items:
            self.w_in.cmb.setCurrentIndex(i if i >= 1 else 1)
        vector_items = [("%s" % l.name(), l) for l in self._vector_layers()]
        self.w_mask.set_items(vector_items)
        self.w_layers.set_layers(self._raster_layers(), prefer=active_layer)

    def _checked_layers(self):
        return self.w_layers.checked_layers()

    def _input_layer(self):
        v = self.w_in.value()
        return None if isinstance(v, str) else v

    def _mask_layer(self):
        v = self.w_mask.value()
        return None if isinstance(v, str) else v

    def _current_op(self):
        return str(self.cmb_op.currentData() or "")

    def _current_spec(self):
        return RASTER_OPS.get(self._current_op(), {})

    def _current_out_kind(self):
        return self._current_spec().get("out_kind", "raster")

    def _sync_op(self, *_a):
        op = self._current_op()
        spec = self._current_spec()
        self.w_mask.setVisible(bool(spec.get("needs_mask")))
        needs_ext = bool(spec.get("needs_extent"))
        self.w_extent.setVisible(needs_ext)
        if needs_ext:
            self._sync_extent_reference()
        self.w_layers.setVisible(bool(spec.get("needs_layers")))
        self._rebuild_extra(op, spec)
        self.lbl_desc.setText(self._describe(op, spec))
        self.gb_param.setVisible(bool(spec.get("params")) or needs_ext)
        self._sync_out()

    def _sync_extent_reference(self, *_a):
        if not bool(self._current_spec().get("needs_extent")):
            return
        lyr = self._input_layer()
        if lyr is None:
            return
        try:
            ext = lyr.extent()
        except Exception:
            _log.exception("silent exception in _sync_extent_reference")
            return
        if ext is not None and not ext.is_empty():
            self.w_extent.set_reference_extent(ext)

    def _describe(self, op, spec):
        return ""

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
                else:
                    w.valueChanged.connect(self._on_extra_edited)
            except Exception:
                _log.exception("silent exception in _rebuild_extra")
            form.addRow(label, w)
            self._extra_ctrls[key] = w

    def _extra_values(self):
        out = {}
        for key, w in (self._extra_ctrls or {}).items():
            try:
                if isinstance(w, QLineEdit):
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

    def _active_out_widget(self):
        return (self.w_out_vector if self._current_out_kind() == "vector"
                else self.w_out_raster)

    def _sync_out(self, *_a):
        to_file = bool(self.rad_file.isChecked())
        kind = self._current_out_kind()
        self.w_out_raster.setVisible(to_file and kind == "raster")
        self.w_out_vector.setVisible(to_file and kind == "vector")

    def _on_out_file_typed(self, text):
        if str(text or "").strip() and not self.rad_file.isChecked():
            self.rad_file.setChecked(True)

    def _output_spec(self):
        return self._active_out_widget().spec()

    def _make_params(self):
        op = self._current_op()
        to_file = bool(self.rad_file.isChecked())
        out_spec = self._output_spec() if to_file else {}
        needs_ext = bool(self._current_spec().get("needs_extent"))
        needs_layers = bool(self._current_spec().get("needs_layers"))
        params = {
            "input": self._input_layer(),
            "mask": self._mask_layer() if self._current_spec().get("needs_mask")
            else None,
            "extent": self.w_extent.extent() if needs_ext else None,
            "layers": self._checked_layers() if needs_layers else [],
            "values": self._extra_values(),
        }
        return op, params, to_file, out_spec

    def params(self):
        op, params, _to_file, _spec = self._make_params()
        return op, params

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
            ok.setIcon(_icons.icon("stop" if running else "processing", size=16))
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
        op, params, to_file, out_spec = self._make_params()
        if params.get("input") is None \
                and not self._current_spec().get("needs_layers"):
            self._flash(_tr("请先选择输入栅格图层"))
            return
        if self._current_spec().get("needs_layers") \
                and not params.get("layers"):
            self._flash(_tr("请至少勾选一个输入栅格图层"))
            return
        if self._current_spec().get("needs_mask") and params.get("mask") is None \
                and params.get("extent") is None:
            self._flash(_tr("请先设置裁剪范围或选择掩模图层"))
            return
        if to_file and not out_spec.get("filename"):
            self._flash(_tr("请先填写输出文件"))
            return
        runner = getattr(self, "_runner", None)
        if runner is None:
            self.accept()
            return
        self._begin_busy()
        try:
            res = runner(op, params, out_spec, self.feed, self.cancelled)
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
                self._flash(_tr("已取消") if cancelled else _tr("运行完成"))

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
