# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math
import os

from PySide6.QtWidgets import QLabel, QSpinBox


from ggis.core.app import i18n
from ggis.core.crs import GgsCrs, crs_transformer
from ggis.core.crs.extent import GgsRectangle
from ggis.io import tile_export
from ggis.io.formats import EIGHT_BIT_RASTER_DRIVERS
from ggis.ui.dialogs.tool_dialog import GgsToolDialog
from ggis.common.styling import icons
from ggis.common.widgets.displays import GgsDimLabel
from ggis.common.widgets.inputs import GgsExtentPicker
from ggis.common.widgets.inputs import GgsLayerOutputWidget

_tr = i18n.tr


def _ensure_suffix(path, suffix):
    p = str(path or "")
    if not p:
        return p
    if os.path.splitext(p)[1]:
        return p
    return p + suffix


class GgsExportTileDialog(GgsToolDialog):

    def __init__(self, layer, parent=None, canvas=None, start_dir=""):
        self._layer = layer
        self._canvas = canvas
        self._start_dir = str(start_dir or "")
        self.task_kind = "io"
        self._over = False
        src = layer.tile_source()
        super().__init__(
            parent,
            title=_tr("导出瓦片图层 — {0}").format(layer.name()),
            icon=icons.icon("export", size=16),
            buttons=(("下载", self._on_apply, "exec"),),
        )
        self.setObjectName("GgsExportTileDialog")
        self.fit_to_content(560)

    def build_content(self):
        src = self._layer.tile_source()

        box_out, form_out = self.add_section(_tr("输出"))
        self.out = GgsLayerOutputWidget(self, kind="raster")
        form_out.addRow(self.out)

        self.box_ext, form_ext = self.add_section(_tr("范围"))
        self.picker = GgsExtentPicker(self, modes=("view", "custom"))
        self.picker.set_canvas(self._canvas)
        world = src.matrix().world()
        self.picker.set_reference_extent(GgsRectangle(
            float(world.xmin), float(world.ymin),
            float(world.xmax), float(world.ymax)))
        try:
            tile_crs = GgsCrs.from_user_input(src.crs)
            self.picker.set_view_sync(
                lambda ext, _dst=None: self._reproject_rect(
                    ext, self._map_crs(), tile_crs))
        except Exception:
            exc_note("build_content @ ggis/ui/views/map/dialogs/export_tile.py:101")
            self.picker.set_view_sync(None)
        form_ext.addRow(self.picker)

        box_res, form_res = self.add_section(_tr("瓦片层级"))
        self.sp_zoom = QSpinBox()
        self.sp_zoom.setRange(int(src.min_zoom), int(src.max_zoom))
        self.sp_zoom.setValue(self._suggest_zoom())
        form_res.addRow(QLabel(_tr("层级")), self.sp_zoom)
        self.lbl_resinfo = GgsDimLabel("")
        self.lbl_resinfo.setWordWrap(True)
        form_res.addRow(self.lbl_resinfo)

        self.lbl_est = GgsDimLabel("")
        self.lbl_est.setWordWrap(True)
        form_res.addRow(self.lbl_est)

        self.lbl_info = GgsDimLabel("")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setVisible(False)
        self.add_widget(self.lbl_info)

        self.picker.modeChanged.connect(self._on_ext_mode_changed)
        self.picker.extentChanged.connect(self._update_estimate)
        self.sp_zoom.valueChanged.connect(self._update_estimate)
        self.out.cmb_fmt.currentIndexChanged.connect(self._update_format_info)
        self._on_ext_mode_changed(self.picker.mode())
        self._update_format_info()
        self._update_estimate()

    def _reproject_rect(self, rect, from_crs, to_crs):
        if rect is None or rect.is_empty():
            return None
        tf = crs_transformer(from_crs, to_crs)
        if tf is None:
            return None
        try:
            xs = [rect.xmin, rect.xmax, rect.xmax, rect.xmin]
            ys = [rect.ymax, rect.ymax, rect.ymin, rect.ymin]
            px, py = tf.transform(xs, ys)
        except Exception:
            exc_note("_reproject_rect @ ggis/ui/views/map/dialogs/export_tile.py:153")
            return None
        fx, fy = [], []
        for _x, _y in zip(px, py):
            try:
                if math.isfinite(float(_x)) and math.isfinite(float(_y)):
                    fx.append(float(_x)); fy.append(float(_y))
            except Exception:
                exc_note("_reproject_rect @ ggis/ui/views/map/dialogs/export_tile.py:160")
                pass
        if not fx:
            return None
        return GgsRectangle(min(fx), min(fy), max(fx), max(fy))

    def _map_crs(self):
        try:
            return self._canvas.map_settings().destination_crs()
        except Exception:
            exc_note("_map_crs @ ggis/ui/views/map/dialogs/export_tile.py:169")
            return None

    def _compute_extent(self):
        ext = self.picker.extent()
        if ext is None or ext.is_empty():
            return None
        return ext

    def _suggest_zoom(self):
        src = self._layer.tile_source()
        m = src.matrix()
        if self._canvas is not None:
            try:
                ext = self._canvas.extent()
                dst = self._map_crs()
                tile_crs = GgsCrs.from_user_input(src.crs)
                ext_src = self._reproject_rect(ext, dst, tile_crs)
                if ext_src is not None and not ext_src.is_empty():
                    px = max(1, int(self._canvas.width()))
                    return m.zoom_for_resolution(
                        ext_src.width() / px, src.min_zoom, src.max_zoom)
            except Exception:
                exc_note("_suggest_zoom @ ggis/ui/views/map/dialogs/export_tile.py:198")
                pass
        return int(src.min_zoom)

    def _zoom_res_text(self, z):
        try:
            m = self._layer.tile_source().matrix()
            res = float(m.units_per_pixel(z)) * float(m.unit_to_meters())
        except Exception:
            exc_note("_zoom_res_text @ ggis/ui/views/map/dialogs/export_tile.py:207")
            return "?"
        return ("%.2f" % res) if abs(res) >= 1 else ("%.4f" % res)

    def _on_ext_mode_changed(self, *_):
        try:
            self.box_ext.setTitle(_tr("范围（当前：{0}）").format(
                _tr("地图视图") if self.picker.mode() == "view"
                else _tr("自定义")))
        except Exception:
            exc_note("_on_ext_mode_changed @ ggis/ui/views/map/dialogs/export_tile.py:220")
            pass
        self._update_estimate()

    def _update_format_info(self, *_):
        self.lbl_info.setText("")
        self.lbl_info.setVisible(False)

    def _update_estimate(self, *_):
        try:
            ext = self._compute_extent()
        except Exception:
            exc_note("_update_estimate @ ggis/ui/views/map/dialogs/export_tile.py:240")
            ext = None
        if ext is None or ext.is_empty():
            self.lbl_est.setText(_tr("请先确定导出范围"))
            self._over = True
            return
        z = int(self.sp_zoom.value())
        n, w, h, over = tile_export.estimate(
            self._layer.tile_source(), ext, z)
        sug = self._suggest_zoom()
        self.lbl_resinfo.setText(
            _tr("分辨率 ≈ {0} 米/像素").format(self._zoom_res_text(z)))
        if over:
            self.lbl_est.setText(
                _tr("预计 {0} 张瓦片 / {1} × {2} 像元 —— "
                    "超出上限，请缩小范围或降低层级").format(n, w, h))
            self._over = True
        else:
            self.lbl_est.setText(
                _tr("预计下载 {0} 张瓦片，拼接成 {1} × {2} 像元"
                    "（当前视图约第 {3} 级）").format(n, w, h, sug))
            self._over = False

    def driver(self):
        return self.out.current_driver() or "GTiff"

    def suffix(self):
        return self.out.current_suffix() or ".tif"

    def path(self):
        spec = self.out.spec()
        return _ensure_suffix((spec.get("filename") or "").strip(),
                              self.suffix())

    def collect_params(self):
        return self.params()

    def validate_params(self, params):
        if not params.get("path"):
            return _tr("请先选择输出文件")
        ext = params.get("extent")
        if ext is None or ext.is_empty():
            return _tr("自定义范围无效（请检查经纬度）")
        if self._over:
            return _tr("瓦片数量或尺寸超出上限，请缩小范围或降低层级")
        return ""

    def params(self):
        return {
            "path": self.path(),
            "driver": self.driver(),
            "zoom": int(self.sp_zoom.value()),
            "extent": self._compute_extent(),
            "add_to_map": self.add_to_map(),
        }
