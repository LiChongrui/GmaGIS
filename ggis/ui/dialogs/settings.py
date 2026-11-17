# -*- coding: utf-8 -*-

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QWidget,
)

from ggis.core.app import i18n
from ggis.core.analysis import resampling as _resampling
from ggis.core.crs.units import SELECTABLE_UNITS
from ggis.common.styling import themes
from ggis.common.widgets.inputs import GgsColorField, GgsCrsSelector
from ggis.common.widgets.buttons import GgsSmallButtonStyle1, GgsStandardButton
from .app import _NavDialog
from ggis.core.app import settings as app_settings
from ggis.app import log_file
from ...io.formats import VECTOR_WRITE_FORMATS, RASTER_WRITE_FORMATS
import logging
_log = logging.getLogger("gmagis")

_PG_GENERAL, _PG_MAP = 0, 1
_PG_SELECT, _PG_EDIT, _PG_RENDER = 2, 3, 4

_PAGE_TITLES = {
    _PG_GENERAL: i18n.tr("应用程序选项"),
    _PG_MAP: i18n.tr("地图显示选项"),
    _PG_SELECT: i18n.tr("选择选项"),
    _PG_EDIT: i18n.tr("编辑选项"),
    _PG_RENDER: i18n.tr("渲染选项"),
}


_RESTART_KEYS = ("language",)

_RESTART_HINT = {
    "language": i18n.tr("语言更改需要重启程序才完全生效。"),
}
_RESTART_NAME = {
    "language": i18n.tr("语言"),
}

_RESTART_HINT_ANY = i18n.tr("更改需要重启程序才完全生效。")

_AUTO_SEL_WIDTH = 0.0


def _aa_ss(combo):
    try:
        v = combo.currentData()
        ss = int(round(float(v))) if v is not None else 2
    except Exception:
        _log.exception("silent exception in _aa_ss")
        ss = 2
    return max(1, min(4, ss))


def _aa_default_ss(D):
    try:
        raw = D.get("vector_antialias_ss", None)
        if raw is None:
            raw = 2 if D.get("render_antialias", True) else 1
        return max(1, min(4, int(round(float(raw)))))
    except Exception:
        _log.exception("silent exception in _aa_default_ss")
        return 2



class SettingsDialog(_NavDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(_dialog_icon("mActionOptions.svg", "settings"))
        self.setWindowTitle(i18n.tr("选项"))
        self._mw = parent
        self._picked_color = app_settings.get("canvas_color") or ""

        self._add_page(_dialog_icon("mActionOptions.svg", "settings"),
                       i18n.tr("常规"), self._page_general(),
                       _PAGE_TITLES[_PG_GENERAL])
        self._add_page(_dialog_icon("mActionMapSettings.svg", "overview"),
                       i18n.tr("地图"), self._page_map(),
                       _PAGE_TITLES[_PG_MAP])
        self._add_page(_dialog_icon("mActionSelectRectangle.svg", "select"),
                       i18n.tr("选择"), self._page_select(),
                       _PAGE_TITLES[_PG_SELECT])
        self._add_page(_dialog_icon("mActionToggleEditing.svg", "edit"),
                       i18n.tr("编辑"), self._page_edit(),
                       _PAGE_TITLES[_PG_EDIT])
        self._add_page(_dialog_icon("mActionRender.svg", "render"),
                       i18n.tr("渲染"), self._page_render(),
                       _PAGE_TITLES[_PG_RENDER])
        self.finish()


        self.lbl_restart = QLabel("")
        self.lbl_restart.setStyleSheet("color:{}".format(themes.accent()))
        btn_reset = QPushButton(i18n.tr("恢复默认"))
        btn_reset.clicked.connect(self._reset_defaults)
        self.btn_left.addWidget(btn_reset)
        self.btn_left.addWidget(self.lbl_restart)

        self._initial = self._collect()
        self._clear_cache_wanted = False
        for _w in (getattr(self, "cmb_lang", None),):
            try:
                _w.currentIndexChanged.connect(self._update_restart_hint)
            except Exception:
                _log.exception("silent exception in __init__")
        self._update_restart_hint()

    def _page_general(self):
        w, group = self._grouped_page()
        form = group(i18n.tr("外观"), "color_swatch")

        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem(i18n.tr("跟随系统"), "system")
        self.cmb_theme.addItem(i18n.tr("深色"), "dark")
        self.cmb_theme.addItem(i18n.tr("浅色"), "light")
        self._select_combo(self.cmb_theme, app_settings.get_raw("theme"))
        form.addRow(i18n.tr("主题"), self.cmb_theme)

        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem(i18n.tr("跟随系统"), "system")
        self.cmb_lang.addItem(i18n.tr("简体中文"), "zh_CN")
        self.cmb_lang.addItem(i18n.tr("English"), "en_US")
        self._select_combo(self.cmb_lang, app_settings.get("language"))
        form.addRow(i18n.tr("语言"), self.cmb_lang)

        form = group(i18n.tr("消息"), "message")
        self.chk_show_info = QCheckBox(i18n.tr("正常"))
        self.chk_show_info.setChecked(
            bool(app_settings.get("show_info_messages", False)))
        self.chk_show_success = QCheckBox(i18n.tr("成功"))
        self.chk_show_success.setChecked(
            bool(app_settings.get("show_success_messages", False)))
        self.chk_show_warning = QCheckBox(i18n.tr("警告"))
        self.chk_show_warning.setChecked(
            bool(app_settings.get("show_warning_messages", True)))
        self.chk_show_error = QCheckBox(i18n.tr("错误"))
        self.chk_show_error.setChecked(
            bool(app_settings.get("show_critical_messages", True)))
        self.chk_show_other = QCheckBox(i18n.tr("其他"))
        self.chk_show_other.setChecked(
            bool(app_settings.get("show_other_messages", True)))
        _msg_row = QWidget()
        _mh = QHBoxLayout(_msg_row)
        _mh.setContentsMargins(0, 0, 0, 0)
        _mh.setSpacing(10)
        for _cb in (self.chk_show_info, self.chk_show_success,
                    self.chk_show_warning, self.chk_show_error,
                    self.chk_show_other):
            _mh.addWidget(_cb)
        _mh.addStretch(1)
        form.addRow(i18n.tr("显示消息"), _msg_row)

        form = group(i18n.tr("临时文件"), "save")
        self.cmb_temp_fmt = QComboBox()
        for _s, _drv, _name, _filt in VECTOR_WRITE_FORMATS:
            self.cmb_temp_fmt.addItem(i18n.tr(_filt), _drv)
        self._select_combo(self.cmb_temp_fmt,
                           str(app_settings.get("temp_layer_format")
                               or "GPKG"))
        form.addRow(i18n.tr("临时矢量格式"), self.cmb_temp_fmt)

        self.cmb_temp_ras_fmt = QComboBox()
        for _s, _drv, _name, _filt, _e in RASTER_WRITE_FORMATS:
            self.cmb_temp_ras_fmt.addItem(i18n.tr(_filt), _drv)
        self._select_combo(self.cmb_temp_ras_fmt,
                           str(app_settings.get("temp_raster_format")
                               or "GTiff"))
        form.addRow(i18n.tr("临时栅格格式"), self.cmb_temp_ras_fmt)

        form = group(i18n.tr("自动保存"), "save")
        self.spn_auto_save_min = QSpinBox()
        self.spn_auto_save_min.setRange(1, 120)
        self.spn_auto_save_min.setSuffix(i18n.tr(" 分钟"))
        try:
            self.spn_auto_save_min.setValue(max(1, min(120, int(
                app_settings.get("auto_save_interval_min", 1) or 1))))
        except Exception:
            _log.exception("silent exception in _page_general")
            self.spn_auto_save_min.setValue(1)
        form.addRow(i18n.tr("保存间隔"), self.spn_auto_save_min)

        form = group(i18n.tr("存储位置"), "database")
        row = QHBoxLayout()
        row.setSpacing(6)
        self.ed_cache_root = QLineEdit()
        self.ed_cache_root.setToolTip(i18n.tr(
            "在线瓦片与显示金字塔的存放位置，可再生，可随手删。"
            "留空则使用用户目录下与日志文件同级的默认位置。"
            "也可填绝对路径，如 D:/GmaGIS-cache"))
        try:
            from ... import app_paths as _app_paths
            self.ed_cache_root.setText(str(_app_paths.cache_dir()))
        except Exception:
            _log.exception("silent exception in _page_general")
            self.ed_cache_root.setText(
                str(app_settings.get("cache_root") or ""))
        self._cache_root_initial = self.ed_cache_root.text()
        row.addWidget(self.ed_cache_root, 1)
        self.btn_clear_cache = GgsSmallButtonStyle1(
            "broom", i18n.tr("清空渲染缓存"), self._request_clear_cache, 16)
        row.addWidget(self.btn_clear_cache)
        self.btn_cache_root = GgsSmallButtonStyle1(
            "folder", i18n.tr("选择缓存目录"), self._pick_cache_root, 16)
        row.addWidget(self.btn_cache_root)
        form.addRow(i18n.tr("栅格缓存"), row)

        try:
            _log_path = log_file()
        except Exception:
            _log_path = ""
        row_log = QHBoxLayout()
        row_log.setSpacing(6)
        self.ed_log_file = QLineEdit()
        self.ed_log_file.setText(str(app_settings.get("log_file") or _log_path))
        self.ed_log_file.setPlaceholderText(_log_path)
        self.ed_log_file.setToolTip(i18n.tr(
            "日志写入的文件路径；留空使用默认位置（%APPDATA%/GmaGIS/logs）。"))
        self._log_file_initial = self.ed_log_file.text().strip()
        row_log.addWidget(self.ed_log_file, 1)
        self.btn_log_file = GgsSmallButtonStyle1(
            "folder", i18n.tr("选择日志文件"), self._pick_log_file, 16)
        row_log.addWidget(self.btn_log_file)
        form.addRow(i18n.tr("日志文件"), row_log)

        form = group(i18n.tr("文件关联"), "link")
        if sys.platform == "win32":
            self.btn_reassoc = GgsStandardButton(
                "link", i18n.tr("重置文件关联"),
                tip="", slot=self._reset_file_assoc, size=16, parent=self)
            form.addRow("", self.btn_reassoc)

        return w

    def _page_map(self):
        w, group = self._grouped_page()
        form = group(i18n.tr("画布"), "basemap_main")
        h = QHBoxLayout()
        h.setSpacing(6)
        self.chk_canvas_theme = QCheckBox(i18n.tr("跟随主题"))
        self.chk_canvas_theme.setChecked(not self._picked_color)
        self.color_field = GgsColorField(
            self._picked_color or themes.canvas_color(
                app_settings.get("theme")), self)
        self.color_field.setEnabled(bool(self._picked_color))
        self.color_field.colorChanged.connect(self._set_picked_color)
        self.chk_canvas_theme.toggled.connect(self._on_theme_color_toggled)
        h.addWidget(self.chk_canvas_theme)
        h.addWidget(self.color_field)
        h.addStretch(1)
        form.addRow(i18n.tr("背景色"), h)

        self.crs_sel = GgsCrsSelector(self, crs=app_settings.get(
            "default_crs") or "")
        self.crs_sel.setToolTip(i18n.tr(
            "新建地图视图时采用的默认坐标系。留空则按首个数据图层的坐标系自动推导。仅作为初值，每视图的坐标系可在视图内单独设定，不影响已打开的视图。"))
        form.addRow(i18n.tr("默认坐标系"), self.crs_sel)

        return w

    def _page_select(self):
        w, group = self._grouped_page()

        form = group(i18n.tr("填充"), "select")
        self.btn_sel_fill = self._mk_color_btn(QColor(
            app_settings.get("selection_fill_color", "#4DFFE14D")))
        form.addRow(i18n.tr("填充颜色"), self.btn_sel_fill)

        form_l = group(i18n.tr("线条"), "select")
        self.btn_sel_stroke = self._mk_color_btn(
            app_settings.get("selection_line_color", "#FFE14D"),
            shape="line")
        form_l.addRow(i18n.tr("线条颜色"), self.btn_sel_stroke)
        self.spn_sel_width = QDoubleSpinBox()
        self.spn_sel_width.setDecimals(2)
        self.spn_sel_width.setRange(0.0, 99.99)
        self.spn_sel_width.setSingleStep(0.5)
        self.spn_sel_width.setSuffix(" px")
        self.spn_sel_width.setToolTip(i18n.tr(
            "选中要素的线条宽度，单位为屏幕像素。"
            "填0 表示跟随图层符号自身的线宽。"))
        w0 = float(app_settings.get("selection_line_width",
                                   _AUTO_SEL_WIDTH) or 0.0)
        self.spn_sel_width.setValue(max(0.0, min(99.99, w0)))
        form_l.addRow(i18n.tr("线宽"), self.spn_sel_width)

        form2 = group(i18n.tr("容差"), "identify")
        self.spn_id_tol = QSpinBox()
        self.spn_id_tol.setRange(1, 30)
        self.spn_id_tol.setSuffix(" px")
        try:
            self.spn_id_tol.setValue(
                int(app_settings.get("identify_tolerance_px", 5)))
        except Exception:
            _log.exception("silent exception in _page_select")
            self.spn_id_tol.setValue(5)
        form2.addRow(i18n.tr("点选容差"), self.spn_id_tol)

        _sel_color_btns = {self.btn_sel_fill, self.btn_sel_stroke}
        _a_left = (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for _card in (form, form_l, form2):
            for _r in range(_card.grid.rowCount()):
                _it0 = _card.grid.itemAtPosition(_r, 0)
                if _it0 is not None:
                    _wl = _it0.widget()
                    if isinstance(_wl, QLabel):
                        _wl.setAlignment(_a_left)
                        _card.grid.setAlignment(_wl, _a_left)
                _it1 = _card.grid.itemAtPosition(_r, 1)
                if _it1 is not None:
                    _wf = _it1.widget()
                    if _wf is not None and _wf in _sel_color_btns:
                        _card.grid.setAlignment(_wf, _a_left)

        return w

    def _page_edit(self):
        w, group = self._grouped_page()
        form = group(i18n.tr("捕捉"), "snap_midpoint")
        self.spn_snap_tol = QSpinBox()
        self.spn_snap_tol.setRange(1, 50)
        self.spn_snap_tol.setSuffix(" px")
        try:
            self.spn_snap_tol.setValue(
                int(app_settings.get("snap_tolerance_px", 8)))
        except Exception:
            _log.exception("silent exception in _page_edit")
            self.spn_snap_tol.setValue(8)
        form.addRow(i18n.tr("捕捉容差"), self.spn_snap_tol)
        return w

    def _page_render(self):
        w, group = self._grouped_page()


        form_ras = group(i18n.tr("栅格重采样"), "stretch")
        _tip = i18n.tr("分类 / 离散值用最近邻；连续影像放大可用双三次 / Lanczos。"
                       "缩小时用「平均值」等比最近邻更干净（代价是细节变软）。")
        self.cmb_rsample_in = QComboBox()
        for _c in _resampling.options(is_zoom_in=True):
            self.cmb_rsample_in.addItem(i18n.tr(_resampling.label(_c)), _c)
        self.cmb_rsample_in.setToolTip(_tip)
        self._select_combo(self.cmb_rsample_in,
                           str(app_settings.get("raster_resample_in")
                               or _resampling.NEAREST))
        form_ras.addRow(i18n.tr("放大时"), self.cmb_rsample_in)

        self.cmb_rsample_out = QComboBox()
        for _c in _resampling.options(is_zoom_in=False):
            self.cmb_rsample_out.addItem(i18n.tr(_resampling.label(_c)), _c)
        self.cmb_rsample_out.setToolTip(_tip)
        self._select_combo(self.cmb_rsample_out,
                           str(app_settings.get("raster_resample_out")
                               or _resampling.NEAREST))
        form_ras.addRow(i18n.tr("缩小时"), self.cmb_rsample_out)


        form_vec = group(i18n.tr("矢量增强"), "polygon_layer")
        _antialias_ss0 = 2
        try:
            _raw = app_settings.get("vector_antialias_ss", None)
            if _raw is None:
                _raw = (2 if app_settings.get("render_antialias", True)
                        else 1)
            _antialias_ss0 = max(1, min(4, int(round(float(_raw)))))
        except Exception:
            _log.exception("silent exception in _page_render")
            _antialias_ss0 = 2
        self.cmb_antialias = QComboBox()
        for _v, _lab in ((1, i18n.tr("1×")),
                         (2, i18n.tr("2×")),
                         (3, i18n.tr("3×")),
                         (4, i18n.tr("4×"))):
            self.cmb_antialias.addItem(_lab, _v)
        self.cmb_antialias.setToolTip(i18n.tr(
            "矢量线与面的抗锯齿超采样倍率。倍率越高边缘越细腻，"
            "但渲染开销按倍率的平方增长。1× 为关闭，2× 为推荐值，"
            "4× 最平滑也最慢。"))
        self._select_combo(self.cmb_antialias, _antialias_ss0)
        form_vec.addRow(i18n.tr("矢量抗锯齿"), self.cmb_antialias)

        self.chk_lod = QCheckBox(i18n.tr("简化复杂几何"))
        self.chk_lod.setToolTip(i18n.tr(
            "按当前比例尺抽稀矢量几何，可提速，"
            "但可能吃掉细小的多边形。底图与选中高亮使用同一份简化结果，"
            "所以两者的轮廓始终重合。"))
        self.chk_lod.setChecked(
            bool(app_settings.get("vector_lod_simplify", False)))
        form_vec.addRow("", self.chk_lod)

        self.spn_lod_tol = QSpinBox()
        self.spn_lod_tol.setRange(1, 20)
        self.spn_lod_tol.setSuffix(" px")
        self.spn_lod_tol.setToolTip(i18n.tr(
            "抽稀容差，以屏幕像素计：1 像素最精细也最慢，"
            "数值越大越快，但小于容差的细小多边形可能被整个吃掉。"
            "QGIS 的默认值是 1.2 像素。"))
        try:
            _lt = float(app_settings.get("vector_lod_tolerance_px", 1.2))
        except Exception:
            _log.exception("silent exception in _page_render")
            _lt = 1.2
        try:
            self.spn_lod_tol.setValue(max(1, min(20, int(round(_lt)))))
        except Exception:
            _log.exception("silent exception in _page_render")
            self.spn_lod_tol.setValue(1)
        self.spn_lod_tol.setEnabled(self.chk_lod.isChecked())
        self.chk_lod.toggled.connect(
            lambda on: self.spn_lod_tol.setEnabled(on))
        form_vec.addRow(i18n.tr("简化容差"), self.spn_lod_tol)

        form = group(i18n.tr("通用"), "settings")

        self.cmb_unit = QComboBox()
        for _u in SELECTABLE_UNITS:
            self.cmb_unit.addItem(_u, _u)
        self.cmb_unit.setToolTip(i18n.tr(
            "新建符号的尺寸与线宽用哪个单位保存。"
            "已有符号仍按各自保存的单位显示。"))
        try:
            self._select_combo(self.cmb_unit,
                               str(app_settings.get("symbol_unit") or "pt"))
        except Exception:
            _log.exception("silent exception in _page_render")
        form.addRow(i18n.tr("默认尺寸单位"), self.cmb_unit)
        self.chk_class_warn = QCheckBox(
            i18n.tr("分类/分级数过多时提醒"))
        self.chk_class_warn.setChecked(
            bool(app_settings.get("class_warn_enabled", True)))
        form.addRow("", self.chk_class_warn)

        self.spn_class_warn = QSpinBox()
        self.spn_class_warn.setRange(2, 1024)
        self.spn_class_warn.setValue(
            int(app_settings.get("class_warn_threshold", 50) or 50))
        self.spn_class_warn.setSuffix(i18n.tr(" 个"))
        form.addRow(i18n.tr("提醒阈值"), self.spn_class_warn)

        self.spn_class_warn.setEnabled(self.chk_class_warn.isChecked())
        self.chk_class_warn.toggled.connect(
            lambda on: self.spn_class_warn.setEnabled(on))

        return w

    @staticmethod
    def _ro(text):
        ed = QLineEdit(str(text or ""))
        ed.setReadOnly(True)
        return ed

    @staticmethod
    def _dim(text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:{}".format(themes.text_dim()))
        return lbl

    def _mk_color_btn(self, color_text, shape="rect"):
        return GgsColorField(color_text, self, shape=shape)

    def _cache_root_for_save(self):
        try:
            cur = self.ed_cache_root.text().strip()
            if cur == str(getattr(self, "_cache_root_initial", "") or ""):
                return str(app_settings.get("cache_root") or "").strip()
            return cur
        except Exception:
            _log.exception("silent exception in _cache_root_for_save")
            try:
                return self.ed_cache_root.text().strip()
            except Exception:
                _log.exception("silent exception in _cache_root_for_save")
                return ""

    def _pick_cache_root(self):
        from PySide6.QtWidgets import QFileDialog

        try:
            start = self.ed_cache_root.text().strip()
        except Exception:
            _log.exception("silent exception in _pick_cache_root")
            start = ""
        d = QFileDialog.getExistingDirectory(
            self, i18n.tr("选择缓存目录"), start)
        if d:
            self.ed_cache_root.setText(d)

    def _pick_log_file(self):
        from PySide6.QtWidgets import QFileDialog

        try:
            start = self.ed_log_file.text().strip()
        except Exception:
            _log.exception("silent exception in _pick_log_file")
            start = ""
        p, _ = QFileDialog.getSaveFileName(
            self, i18n.tr("选择日志文件"), start,
            i18n.tr("日志文件 (*.log);;所有文件 (*)"))
        if p:
            self.ed_log_file.setText(p)

    def _reset_file_assoc(self):
        from ggis.common.base.dialog import GgsMsgBox
        try:
            from ggis.core.app.file_assoc import associate_ggs
            _ok, _msg = associate_ggs(True)
        except Exception as e:
            _log.exception("silent exception in _reset_file_assoc")
            _ok, _msg = False, i18n.tr("文件关联失败：{}").format(e)
        _msg = i18n.tr(_msg)
        try:
            if _ok:
                GgsMsgBox.information(self, i18n.tr("文件关联"), _msg)
            else:
                GgsMsgBox.warning(self, i18n.tr("文件关联"), _msg)
        except Exception:
            _log.exception("silent exception in _reset_file_assoc")

    def _request_clear_cache(self):
        self._clear_cache_wanted = True
        self.btn_clear_cache.setEnabled(False)
        self.btn_clear_cache.setToolTip("")

    def cache_clear_requested(self):
        v = bool(getattr(self, "_clear_cache_wanted", False))
        self._clear_cache_wanted = False
        return v

    def log_file_requested(self):
        v = self.ed_log_file.text().strip()
        return v if v and v != self._log_file_initial else None

    def _select_combo(self, combo, value):
        idx = combo.findData(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_theme_color_toggled(self, follow):
        self.color_field.setEnabled(not follow)
        if follow:
            self._picked_color = ""

    def _set_picked_color(self, c):
        c = QColor(c)
        if not c.isValid():
            return
        self._picked_color = c.name()
        if self.chk_canvas_theme.isChecked():
            self.chk_canvas_theme.setChecked(False)
        else:
            self.color_field.setEnabled(True)

    def _reset_defaults(self):
        D = app_settings.DEFAULTS
        self._select_combo(self.cmb_theme, D["theme"])
        self._select_combo(self.cmb_lang, D["language"])
        self._select_combo(self.cmb_unit, D.get("symbol_unit", "pt"))
        self._picked_color = D["canvas_color"]
        self.chk_canvas_theme.setChecked(True)
        self.color_field.setColor(QColor(themes.canvas_color(
            app_settings.get("theme"))))
        try:
            self.crs_sel.setCrs("", emit=False)
        except Exception:
            _log.exception("silent exception in _reset_defaults")
        self.chk_show_info.setChecked(
            bool(D.get("show_info_messages", False)))
        self.chk_show_success.setChecked(
            bool(D.get("show_success_messages", False)))
        self.chk_show_warning.setChecked(
            bool(D.get("show_warning_messages", True)))
        self.chk_show_error.setChecked(
            bool(D.get("show_critical_messages", True)))
        self.chk_show_other.setChecked(
            bool(D.get("show_other_messages", True)))
        self.spn_auto_save_min.setValue(
            max(1, min(120, int(D.get("auto_save_interval_min", 1) or 1))))
        self._select_combo(self.cmb_temp_fmt, D.get("temp_layer_format",
                                                    "GPKG"))
        self._select_combo(self.cmb_temp_ras_fmt,
                           D.get("temp_raster_format", "GTiff"))
        self.btn_sel_fill.setColor(QColor(
            D.get("selection_fill_color", "#4DFFE14D")))
        self.btn_sel_stroke.setColor(QColor(
            D.get("selection_line_color", "#FFE14D")))
        self.spn_sel_width.setValue(max(
            0.0, min(99.99, float(
                D.get("selection_line_width", _AUTO_SEL_WIDTH)
                or _AUTO_SEL_WIDTH))))
        self.spn_id_tol.setValue(int(D.get("identify_tolerance_px", 5)))
        self.spn_snap_tol.setValue(int(D.get("snap_tolerance_px", 8)))
        self._select_combo(self.cmb_rsample_in,
                           D.get("raster_resample_in", _resampling.NEAREST))
        self._select_combo(self.cmb_rsample_out,
                           D.get("raster_resample_out", _resampling.NEAREST))
        self._select_combo(self.cmb_antialias, _aa_default_ss(D))
        self.chk_lod.setChecked(bool(D.get("vector_lod_simplify", False)))
        try:
            self.spn_lod_tol.setValue(max(1, min(20, int(round(
                float(D.get("vector_lod_tolerance_px", 1.2)))))))
        except Exception:
            _log.exception("silent exception in _reset_defaults")
            self.spn_lod_tol.setValue(1)
        self.spn_lod_tol.setEnabled(self.chk_lod.isChecked())
        self.chk_class_warn.setChecked(
            bool(D.get("class_warn_enabled", True)))
        self.spn_class_warn.setEnabled(self.chk_class_warn.isChecked())
        self.spn_class_warn.setValue(
            int(D.get("class_warn_threshold", 50) or 50))
        try:
            from ... import app_paths as _ap
            self.ed_cache_root.setText(str(_ap.cache_dir()))
        except Exception:
            _log.exception("silent exception in _reset_defaults")
            self.ed_cache_root.setText(str(D.get("cache_root", "") or ""))
        self.ed_log_file.setText(log_file())
        self._update_restart_hint()

    def _collect(self):
        sel_w = float(self.spn_sel_width.value())
        _fc = self.btn_sel_fill.color()
        return {
            "theme": self.cmb_theme.currentData(),
            "language": self.cmb_lang.currentData(),
            "show_info_messages": bool(self.chk_show_info.isChecked()),
            "show_success_messages": bool(self.chk_show_success.isChecked()),
            "show_warning_messages": bool(self.chk_show_warning.isChecked()),
            "show_critical_messages": bool(self.chk_show_error.isChecked()),
            "show_other_messages": bool(self.chk_show_other.isChecked()),
            "auto_save_interval_min": int(self.spn_auto_save_min.value()),
            "temp_layer_format": self.cmb_temp_fmt.currentData() or "GPKG",
            "temp_raster_format":
                self.cmb_temp_ras_fmt.currentData() or "GTiff",
            "canvas_color": ("" if self.chk_canvas_theme.isChecked()
                             else self._picked_color),
            "default_crs": self.crs_sel.crs(),
            "selection_fill_color": "#%02X%02X%02X%02X" % (
                _fc.alpha(), _fc.red(), _fc.green(), _fc.blue()),
            "selection_line_color": self.btn_sel_stroke.color().name(),
            "selection_line_width": sel_w,
            "identify_tolerance_px": self.spn_id_tol.value(),
            "snap_tolerance_px": self.spn_snap_tol.value(),
            "raster_resample_in": (self.cmb_rsample_in.currentData()
                                   or _resampling.NEAREST),
            "raster_resample_out": (self.cmb_rsample_out.currentData()
                                    or _resampling.NEAREST),
            "vector_antialias_ss": _aa_ss(self.cmb_antialias),
            "render_antialias": bool(_aa_ss(self.cmb_antialias) >= 2),
            "vector_lod_simplify": bool(self.chk_lod.isChecked()),
            "vector_lod_tolerance_px": int(self.spn_lod_tol.value()),
            "class_warn_enabled": bool(self.chk_class_warn.isChecked()),
            "class_warn_threshold": int(self.spn_class_warn.value()),
            "symbol_unit": str(self.cmb_unit.currentData() or "pt"),
            "cache_root": self._cache_root_for_save(),
            "log_file": self.ed_log_file.text().strip(),
        }

    def changed(self):
        return self._collect() != self._initial

    def changed_keys(self):
        try:
            was = dict(self._initial)
            now = self._collect()
        except Exception:
            _log.exception("silent exception in changed_keys")
            return set()
        return {k for k in set(was) | set(now)
                if was.get(k) != now.get(k)}

    def _restart_pending(self):
        try:
            was = getattr(self, "_initial", None)
            now = self._collect()
        except Exception:
            _log.exception("silent exception in _restart_pending")
            return []
        if not isinstance(was, dict):
            return []
        return [k for k in _RESTART_KEYS if was.get(k) != now.get(k)]

    def restart_pending_labels(self):
        return [_RESTART_NAME.get(k, k) for k in self._restart_pending()]

    def _update_restart_hint(self, *_a):
        try:
            pend = self._restart_pending()
            if not pend:
                self.lbl_restart.setText("")
            elif len(pend) == 1 and pend[0] in _RESTART_HINT:
                self.lbl_restart.setText(_RESTART_HINT[pend[0]])
            else:
                self.lbl_restart.setText(_RESTART_HINT_ANY)
        except Exception:
            _log.exception("silent exception in _update_restart_hint")

    def render_changed(self):
        try:
            was = dict(self._initial)
            now = self._collect()
            keys = ("vector_antialias_ss", "vector_lod_simplify",
                    "vector_lod_tolerance_px",
                    "raster_resample_in", "raster_resample_out")
            return any(was.get(k) != now.get(k) for k in keys)
        except Exception:
            _log.exception("silent exception in render_changed")
            return False

    def canvas_color_changed(self):
        try:
            return (self._collect().get("canvas_color")
                    != self._initial.get("canvas_color"))
        except Exception:
            _log.exception("silent exception in canvas_color_changed")
            return False

    def selection_style_changed(self):
        was = dict(self._initial)
        now = self._collect()
        keys = ("selection_fill_color",
                "selection_line_color", "selection_line_width")
        return any(was.get(k) != now.get(k) for k in keys)


def _theme_icon(name):
    from .app import _theme_icon as _ti
    return _ti(name)


def _dialog_icon(qgis_path, app_name):
    from .app import _dialog_icon as _di
    return _di(qgis_path, app_name)
