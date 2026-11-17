# -*- coding: utf-8 -*-

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QButtonGroup,
                               QCheckBox,
                               QDialogButtonBox,
                               QGridLayout,
                               QGroupBox,
                               QHBoxLayout,
                               QLabel,
                               QListWidgetItem,
                               QRadioButton,
                               QVBoxLayout,
)

from ggis.core.app import i18n
from ggis.core.app import settings as app_settings
from ggis.common.styling import icons
from ggis.core.model.field import fields_from_layer
from ...io.formats import (
    EIGHT_BIT_RASTER_DRIVERS,
)
from ggis.common.base.dialog import GgsDialog
from .tool_dialog import GgsToolDialog
from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.widgets.inputs import GgsComboBox
from ggis.common.widgets.inputs import GgsFileOutputWidget, GgsLayerOutputWidget
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
import logging
from PySide6.QtWidgets import QComboBox, QSpinBox
_log = logging.getLogger("gmagis")

_tr = i18n.tr


def _ensure_suffix(path, suffix):
    p = str(path or "")
    if not p:
        return p
    if os.path.splitext(p)[1]:
        return p
    return p + suffix




class GgsExportVectorDialog(GgsToolDialog):

    def __init__(self, layer, parent=None, start_dir="", n_selected=0):
        self._layer = layer
        self._start_dir = str(start_dir or "")
        self._n_selected = int(n_selected or 0)
        self._view = parent
        self.task_kind = "io"
        super().__init__(
            parent,
            title=_tr("导出矢量图层 — {0}").format(layer.name()),
            icon=icons.icon("export", size=16),
            buttons=(("导出", self._on_apply, "exec"),),
        )
        self.setObjectName("GgsExportVectorDialog")
        self.fit_to_content(560)

    def build_content(self):
        box_out, form_out = self.add_section(_tr("输出"))
        self.out = GgsLayerOutputWidget(self, kind="vector")
        form_out.addRow(self.out)

        box_scope, form_scope = self.add_section(_tr("导出要素"))
        self._scope_bg = QButtonGroup(self)
        self.rd_all = GgsExpVecScopeAll(_tr("全部要素"))
        self.rd_sel = GgsExpVecScopeSelected(_tr("选中要素"))
        self._scope_bg.addButton(self.rd_all)
        self._scope_bg.addButton(self.rd_sel)
        self.rd_all.setChecked(True)
        scope_row = QHBoxLayout()
        scope_row.setSpacing(16)
        scope_row.addWidget(self.rd_all)
        scope_row.addWidget(self.rd_sel)
        scope_row.addStretch(1)
        form_scope.addRow(scope_row)
        self.lbl_scope = GgsExpVecScope("")
        self.lbl_scope.setWordWrap(True)
        form_scope.addRow(self.lbl_scope)
        if self._n_selected <= 0:
            self.rd_sel.setEnabled(False)

        box_f, form_f = self.add_section(_tr("导出字段"))
        self.lst_fields = GgsListWidget()
        self.lst_fields.setObjectName("GgsExpVecFields")
        for f in fields_from_layer(self._layer):
            it = QListWidgetItem("%s (%s)" % (f.name, f.type))
            it.setData(Qt.ItemDataRole.UserRole, f.name)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            self.lst_fields.addItem(it)
        self.lst_fields.itemChanged.connect(
            lambda _it: self._update_field_count())
        form_f.addRow(self.lst_fields)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.btn_all_f = GgsSmallButtonStyle1("select", _tr("全选"),
                                       lambda: self._check_all(True))
        self.btn_none_f = GgsSmallButtonStyle1("deselect", _tr("全不选"),
                                        lambda: self._check_all(False))
        self.btn_all_f.setObjectName("GgsExpVecFieldsAll")
        self.btn_none_f.setObjectName("GgsExpVecFieldsNone")
        bar.addWidget(self.btn_all_f)
        bar.addWidget(self.btn_none_f)
        bar.addStretch(1)
        self.lbl_fields = GgsExpVecFieldsCount("")
        bar.addWidget(self.lbl_fields)
        form_f.addRow(bar)

        self.rd_all.toggled.connect(self._update_scope)
        self.rd_sel.toggled.connect(self._update_scope)
        self._update_field_count()
        self._update_scope()

    def collect_params(self):
        return self.params()

    def validate_params(self, params):
        if not params.get("path"):
            return _tr("请先选择输出文件")
        if params.get("only_selected") and not self._selected_fids():
            return _tr("没有选中的要素可导出")
        return ""

    def _selected_fids(self):
        try:
            return self._view._selected_fids_of(self._layer) or []
        except Exception:
            _log.exception("silent exception in _selected_fids")
            return []

    def _check_all(self, on):
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for i in range(self.lst_fields.count()):
            self.lst_fields.item(i).setCheckState(state)

    def _update_field_count(self):
        n = len(self.selected_fields())
        self.lbl_fields.setText(_tr("已选 {0} 个字段").format(n))

    def _update_scope(self, *_):
        if self.rd_sel.isChecked():
            self.lbl_scope.setText(
                _tr("将导出选中的 {0} 个要素").format(self._n_selected))
            return
        total = self._layer.feature_count()
        parts = [_tr("图层共 {0} 个要素").format(total)]
        if self._layer.is_filtered():
            parts.append(_tr("已过滤，只导出可见的 {0} 个").format(
                self._layer.visible_count()))
        self.lbl_scope.setText("；".join(parts))

    def suffix(self):
        return self.out.current_suffix() or ".gpkg"

    def driver(self):
        return self.out.current_driver() or "GPKG"

    def selected_fields(self):
        out = []
        for i in range(self.lst_fields.count()):
            it = self.lst_fields.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(str(it.data(Qt.ItemDataRole.UserRole)))
        return out

    def path(self):
        return _ensure_suffix(self.out.ed_file.text().strip(), self.suffix())

    def only_selected(self):
        return self.rd_sel.isChecked()

    def target_crs(self):
        return ""

    def params(self):
        return {
            "path": self.path(), "driver": self.driver(),
            "fields": self.selected_fields(),
            "only_selected": self.only_selected(),
            "target_crs": self.target_crs(),
            "add_to_map": self.add_to_map(),
        }




class GgsExportTableDialog(GgsToolDialog):

    def __init__(self, layer, parent=None, start_dir=""):
        self._layer = layer
        self._start_dir = str(start_dir or "")
        self._view = parent
        self.task_kind = "io"
        super().__init__(
            parent,
            title=_tr("导出表格 — {0}").format(layer.name()),
            icon=icons.icon("export", size=16),
            buttons=(("导出", self._on_apply, "exec"),),
        )
        self.setObjectName("GgsExportTableDialog")
        self.chk_add_to_map.setVisible(False)
        self.fit_to_content(560)

    def build_content(self):
        box_out, form_out = self.add_section(_tr("输出"))
        self.out = GgsLayerOutputWidget(self, kind="table")
        form_out.addRow(self.out)

        box_f, form_f = self.add_section(_tr("导出字段"))
        self.lst_fields = GgsListWidget()
        self.lst_fields.setObjectName("GgsExpTableFields")
        for f in fields_from_layer(self._layer):
            it = QListWidgetItem("%s (%s)" % (f.name, f.type))
            it.setData(Qt.ItemDataRole.UserRole, f.name)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            self.lst_fields.addItem(it)
        self.lst_fields.itemChanged.connect(
            lambda _it: self._update_field_count())
        form_f.addRow(self.lst_fields)
        bar = QHBoxLayout()
        bar.setSpacing(6)
        self.btn_all_f = GgsSmallButtonStyle1(
            "select", _tr("全选"), lambda: self._check_all(True))
        self.btn_none_f = GgsSmallButtonStyle1(
            "deselect", _tr("全不选"), lambda: self._check_all(False))
        self.btn_all_f.setObjectName("GgsExpTableFieldsAll")
        self.btn_none_f.setObjectName("GgsExpTableFieldsNone")
        bar.addWidget(self.btn_all_f)
        bar.addWidget(self.btn_none_f)
        bar.addStretch(1)
        self.lbl_fields = GgsExpTableFieldsCount("")
        bar.addWidget(self.lbl_fields)
        form_f.addRow(bar)
        self._update_field_count()

    def collect_params(self):
        return self.params()

    def validate_params(self, params):
        if not params.get("path"):
            return _tr("请先选择输出文件")
        return ""

    def _check_all(self, on):
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for i in range(self.lst_fields.count()):
            self.lst_fields.item(i).setCheckState(state)

    def _update_field_count(self):
        n = len(self.selected_fields())
        self.lbl_fields.setText(_tr("已选 {0} 个字段").format(n))

    def suffix(self):
        return self.out.current_suffix() or ".csv"

    def driver(self):
        return self.out.current_driver() or "CSV"

    def selected_fields(self):
        out = []
        for i in range(self.lst_fields.count()):
            it = self.lst_fields.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(str(it.data(Qt.ItemDataRole.UserRole)))
        return out

    def path(self):
        return _ensure_suffix(self.out.ed_file.text().strip(), self.suffix())

    def params(self):
        return {
            "path": self.path(), "driver": self.driver(),
            "fields": self.selected_fields(),
        }


class GgsExportRasterDialog(GgsToolDialog):

    def __init__(self, layer, parent=None, canvas=None, start_dir=""):
        self._layer = layer
        self._canvas = canvas
        self._start_dir = str(start_dir or "")
        self._view = parent
        self.task_kind = "io"
        super().__init__(
            parent,
            title=_tr("导出栅格图层 — {0}").format(layer.name()),
            icon=icons.icon("export", size=16),
            buttons=(("导出", self._on_apply, "exec"),),
        )
        self.setObjectName("GgsExportRasterDialog")
        self.fit_to_content(560)

    def build_content(self):
        box, form = self.add_section(_tr("输出"))
        self.out = GgsLayerOutputWidget(self, kind="raster")
        _want_r = str(app_settings.get("temp_raster_format") or "GTiff")
        for _i in range(self.out.cmb_fmt.count()):
            if self.out.cmb_fmt.itemData(_i) == _want_r:
                self.out.cmb_fmt.setCurrentIndex(_i)
                break
        form.addRow(self.out)

        box_ext, form_ext = self.add_section(_tr("范围"))
        self._ext_bg = QButtonGroup(self)
        self.rb_full = GgsExpRasFull(_tr("整个图层"))
        self.rb_view = GgsExpRasView(_tr("仅当前地图视图范围"))
        self._ext_bg.addButton(self.rb_full)
        self._ext_bg.addButton(self.rb_view)
        self.rb_full.setChecked(True)
        if self._canvas is None:
            self.rb_view.setEnabled(False)
        form_ext.addRow(self.rb_full)
        form_ext.addRow(self.rb_view)

        box_b, form_b = self.add_section(_tr("波段"))
        self.cmb_bands = GgsExpRasBands()
        n = 1
        try:
            n = max(1, int(layer_band_count(self._layer)))
        except Exception:
            _log.exception("silent exception in build_content")
            n = 1
        self.cmb_bands.addItem(_tr("全部波段（{0} 个）").format(n), None)
        for b in range(1, n + 1):
            self.cmb_bands.addItem(_tr("仅第 {0} 波段").format(b), b)
        form_b.addRow(QLabel(_tr("波段")), self.cmb_bands)

        self.cmb_comp = GgsExpRasCompress()
        self.cmb_comp.addItem(_tr("无"), None)
        self.cmb_comp.addItem("DEFLATE", "DEFLATE")
        self.cmb_comp.addItem("LZW", "LZW")
        self.cmb_comp.addItem("ZSTD", "ZSTD")
        self.cmb_comp.setCurrentIndex(1)
        form_b.addRow(QLabel(_tr("压缩")), self.cmb_comp)

        self.lbl_info = GgsExpRasInfo("")
        self.lbl_info.setWordWrap(True)
        self.add_widget(self.lbl_info)

        self.out.cmb_fmt.currentIndexChanged.connect(self._on_format_changed)
        self._on_format_changed()

    def collect_params(self):
        return self.params()

    def validate_params(self, params):
        if not params.get("path"):
            return _tr("请先选择输出文件")
        return ""

    def _on_format_changed(self, *_):
        info = []
        try:
            info.append(_tr("尺寸：{0} × {1}").format(
                self._layer.width(), self._layer.height()))
            info.append(_tr("波段：{0}").format(self._layer.band_count()))
            info.append(_tr("类型：{0}").format(self._layer.dtype() or "-"))
        except Exception:
            _log.exception("silent exception in _on_format_changed")
        if self.driver() == "VRT":
            pass
        elif self.driver() in EIGHT_BIT_RASTER_DRIVERS:
            try:
                dt = str(self._layer.dtype() or "").lower()
            except Exception:
                _log.exception("silent exception in _on_format_changed")
                dt = ""
            if dt and not dt.startswith("uint8"):
                info.append(_tr("该格式只支持 8 位整型（当前 {0}）").format(dt))
        self.lbl_info.setText("；".join([s for s in info if s]))

    def suffix(self):
        return self.out.current_suffix() or ".tif"

    def driver(self):
        return self.out.current_driver() or "GTiff"

    def path(self):
        return _ensure_suffix(self.out.ed_file.text().strip(), self.suffix())

    def clip_to_view(self):
        return self.rb_view.isChecked()

    def extent(self):
        if not self.clip_to_view() or self._canvas is None:
            return None
        try:
            ext = self._canvas.extent()
        except Exception:
            _log.exception("silent exception in extent")
            return None
        if ext is None or ext.is_empty():
            return None
        return ext

    def bands(self):
        return self.cmb_bands.currentData()

    def compression(self):
        return self.cmb_comp.currentData()

    def params(self):
        return {
            "path": self.path(), "driver": self.driver(),
            "extent": self.extent(), "bands": self.bands(),
            "compression": self.compression(),
            "add_to_map": self.add_to_map(),
        }


class GgsExportMapImageDialog(GgsDialog):

    def __init__(self, canvas, parent=None, start_dir=""):
        super().__init__(parent)
        self._canvas = canvas
        self._start_dir = str(start_dir or "")
        self.setObjectName("GgsExportMapImageDialog")
        self.setWindowTitle(_tr("导出地图图片"))
        self.resize(520, 400)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        box = QGroupBox(_tr("输出文件"), self)
        g = QGridLayout(box)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)
        g.addWidget(QLabel(_tr("格式")), 0, 0)
        self.cmb_fmt = GgsComboBox(self)
        self.cmb_fmt.setObjectName("GgsExpImgFormat")
        self.cmb_fmt.addItem("PNG (*.png)", ".png")
        self.cmb_fmt.addItem("JPEG (*.jpg)", ".jpg")
        g.addWidget(self.cmb_fmt, 0, 1, 1, 2)
        g.addWidget(QLabel(_tr("路径")), 1, 0)
        self.out = GgsFileOutputWidget(self, kind="vector", title="")
        self.out.set_suffix(self.suffix())
        self.out.set_filters("PNG (*.png)")
        g.addWidget(self.out, 1, 1, 1, 2)
        g.setColumnStretch(1, 1)
        lay.addWidget(box)

        box_s = QGroupBox(_tr("图片尺寸"), self)
        sg = QGridLayout(box_s)
        sg.setHorizontalSpacing(8)
        sg.setVerticalSpacing(6)
        w, h = self._canvas_size()
        self.sp_w = GgsExpImgWidth()
        self.sp_w.setRange(64, 20000)
        self.sp_w.setValue(w)
        self.sp_h = GgsExpImgHeight()
        self.sp_h.setRange(64, 20000)
        self.sp_h.setValue(h)
        sg.addWidget(QLabel(_tr("宽度 (px)")), 0, 0)
        sg.addWidget(self.sp_w, 0, 1)
        sg.addWidget(QLabel(_tr("高度 (px)")), 1, 0)
        sg.addWidget(self.sp_h, 1, 1)
        sg.addWidget(QLabel(_tr("DPI")), 2, 0)
        self.sp_dpi = GgsExpImgDpi()
        self.sp_dpi.setRange(36, 1200)
        self.sp_dpi.setValue(300)
        sg.addWidget(self.sp_dpi, 2, 1)
        sg.setColumnStretch(1, 1)

        self.chk_ratio = GgsExpImgRatio(_tr("锁定宽高比"))
        self.chk_ratio.setChecked(True)
        sg.addWidget(self.chk_ratio, 3, 0, 1, 2)
        self.chk_labels = GgsExpImgLabels(_tr("包含标注"))
        self.chk_labels.setChecked(True)
        sg.addWidget(self.chk_labels, 4, 0, 1, 2)
        self.chk_sel = GgsExpImgSelection(_tr("包含选择集高亮"))
        self.chk_sel.setChecked(True)
        sg.addWidget(self.chk_sel, 5, 0, 1, 2)

        self.lbl_info = GgsExpImgInfo("")
        self.lbl_info.setWordWrap(True)
        sg.addWidget(self.lbl_info, 6, 0, 1, 2)
        lay.addWidget(box_s)
        lay.addStretch(1)

        bbox = QDialogButtonBox(self)
        bbox.addButton(_tr("导出"),
                       QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.addButton(_tr("取消"),
                       QDialogButtonBox.ButtonRole.RejectRole)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)

        self._ratio = (w / float(h)) if h else 1.0
        self.cmb_fmt.currentIndexChanged.connect(self._on_format_changed)
        self.sp_w.valueChanged.connect(self._on_w)
        self.sp_h.valueChanged.connect(self._on_h)
        self.sp_dpi.valueChanged.connect(self._update_info)
        self._update_info()

    def _canvas_size(self):
        try:
            return (max(64, int(self._canvas.width())),
                    max(64, int(self._canvas.height())))
        except Exception:
            _log.exception("silent exception in _canvas_size")
            return (1200, 800)

    def _on_format_changed(self, *_):
        suffix = self.suffix()
        self.out.set_suffix(suffix)
        self.out.set_filters(
            "PNG (*.png)" if suffix == ".png" else "JPEG (*.jpg)")
        cur = self.out.value()
        if cur:
            self.out.set_path(os.path.splitext(cur)[0] + suffix)
        self._update_info()

    def _on_w(self, v):
        if self.chk_ratio.isChecked() and self._ratio > 0:
            self.sp_h.blockSignals(True)
            self.sp_h.setValue(max(64, int(round(v / self._ratio))))
            self.sp_h.blockSignals(False)
        self._update_info()

    def _on_h(self, v):
        if self.chk_ratio.isChecked() and self._ratio > 0:
            self.sp_w.blockSignals(True)
            self.sp_w.setValue(max(64, int(round(v * self._ratio))))
            self.sp_w.blockSignals(False)
        self._update_info()

    def _update_info(self, *_):
        w, h = self.sp_w.value(), self.sp_h.value()
        dpi = max(1, self.sp_dpi.value())
        cm_w = w / dpi * 2.54
        cm_h = h / dpi * 2.54
        self.lbl_info.setText(
            _tr("输出 {0} × {1} px；按 {2} DPI 打印约 {3:.1f} × {4:.1f} cm")
            .format(w, h, dpi, cm_w, cm_h))

    def suffix(self):
        return str(self.cmb_fmt.currentData() or ".png")

    def path(self):
        return _ensure_suffix(self.out.value(), self.suffix())

    def params(self):
        return {
            "path": self.path(), "width": self.sp_w.value(),
            "height": self.sp_h.value(), "dpi": self.sp_dpi.value(),
            "with_labels": self.chk_labels.isChecked(),
            "with_selection": self.chk_sel.isChecked(),
        }


def layer_band_count(layer):
    return int(layer.band_count() or 1)


def _crs_label(layer):
    try:
        c = layer.crs()
        if c is None or not c.is_valid():
            return _tr("未定义")
        return c.display_name() or _tr("未定义")
    except Exception:
        _log.exception("silent exception in _crs_label")
        return _tr("未定义")


class GgsExpImgDpi(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgDpi")
class GgsExpImgHeight(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgHeight")
class GgsExpImgInfo(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgInfo")
class GgsExpImgLabels(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgLabels")
class GgsExpImgRatio(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgRatio")
class GgsExpImgSelection(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgSelection")
class GgsExpImgWidth(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpImgWidth")
class GgsExpRasBands(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpRasBands")
class GgsExpRasCompress(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpRasCompress")
class GgsExpRasFull(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpRasFull")
class GgsExpRasInfo(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpRasInfo")
class GgsExpRasView(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpRasView")
class GgsExpVecFieldsCount(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpVecFieldsCount")
class GgsExpVecScope(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpVecScope")
class GgsExpVecScopeAll(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpVecScopeAll")
class GgsExpVecScopeSelected(QRadioButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpVecScopeSelected")
class GgsExpTableFieldsCount(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsExpTableFieldsCount")
