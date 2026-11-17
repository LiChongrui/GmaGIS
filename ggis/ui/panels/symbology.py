# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDoubleSpinBox,
                               QFormLayout,
                               QFrame, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel,
                               QLineEdit, QPushButton, QScrollArea,
                               QSizePolicy, QSpinBox,
                               QStackedWidget, QStyledItemDelegate,
                               QTableWidget, QTableWidgetItem, QToolButton,
                               QToolTip,
                               QVBoxLayout, QWidget)

from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.widgets.inputs import GgsColorField, GgsColorRampField, GgsComboBox, GgsSliderSpin
from ggis.common.widgets.colors import GgsColorRampBar
from ggis.ui.dialogs.color import GgsColorButton
from ggis.ui.dialogs.symbol_preview import GgsSymbolGalleryDialog, GgsSymbolPreview
from ggis.core.app import i18n
from ggis.core.style import raster_display as rd
from ggis.core.model.field import fields_from_layer
from ggis.core.style.symbol_spec import (CAP_LABELS, FILL_STYLE_LABELS,
                                 JOIN_LABELS, LINE_STYLE_LABELS)
from ...render.renderers import (MODE_LABELS, MAX_CLASSES,
                                 GgsCategorizedRenderer,
                                 GgsGraduatedRenderer,
                                 GgsSingleSymbolRenderer,
                                 get_renderer, make_symbol,
                                 set_renderer,
                                 make_ramp, _default_sym)
from ...render.symbol import (color_field_for_kind, default_symbol,
                              set_symbol_color, symbol_color)
from ggis.common.widgets.itemviews import setup_table_ops
from ggis.common.widgets.itemviews import GgsTableWidget
from ggis.ui.framework.docks import GgsDockBody
from ggis.common.widgets.separators import GgsSepH
from ggis.ui.panels.labeling import GgsSymScroll

from ggis.core.style.symbol_spec import DASH_CUSTOM as _DASH_CUSTOM
_tr = i18n.tr

KIND_LABEL = {"point": "点", "line": "线", "polygon": "面"}

PAGE_RASTER = 3

_SYM_COLOR_BY_KIND = True


def _sym_is_line(layer):
    try:
        return bool(layer is not None and layer.base_kind() == "line")
    except Exception:
        exc_note("_sym_is_line @ ggis/ui/panels/symbology.py:84")
        return False


def _sym_color_attr(layer):
    if not _SYM_COLOR_BY_KIND:
        return "fill"
    return color_field_for_kind(_sym_kind_of(layer))


def _sym_kind_of(layer):
    try:
        return str(layer.base_kind() or "")
    except Exception:
        exc_note("_sym_kind_of @ ggis/ui/panels/symbology.py:104")
        return ""


def _sym_color(sym, layer):
    return symbol_color(sym, _sym_kind_of(layer))


def _sym_set_color(sym, layer, color):
    return set_symbol_color(sym, _sym_kind_of(layer), color)



def _apply_unit_spins(sp_size, sp_width, unit, extra=0.0):
    from ggis.core.crs.units import from_px
    u = str(unit or "pt")
    dec = 3 if u == "in" else 2
    step = 0.1 if u in ("mm", "pt") else (0.005 if u == "in" else 0.5)
    for sp, (a, b) in ((sp_size, (0.38, 227.0)), (sp_width, (0.19, 75.6))):
        lo, hi = round(from_px(a, u), 4), round(from_px(b, u), 4)
        if extra and float(extra) > hi:
            hi = float(extra)
        sp.setDecimals(dec)
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setSuffix(" " + u)


def _apply_pattern_spins(sp_spacing, sp_width, unit, extra=0.0):
    from ggis.core.crs.units import from_px
    u = str(unit or "pt")
    dec = 3 if u == "in" else 2
    step = 0.1 if u in ("mm", "pt") else (0.005 if u == "in" else 0.5)
    for sp, (a, b) in ((sp_spacing, (2.0, 114.0)), (sp_width, (0.19, 75.6))):
        lo, hi = round(from_px(a, u), 4), round(from_px(b, u), 4)
        if extra and float(extra) > hi:
            hi = float(extra)
        sp.setDecimals(dec)
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setSuffix(" " + u)


_LINE_STYLE_LABELS = LINE_STYLE_LABELS
_FILL_STYLE_LABELS = FILL_STYLE_LABELS
_CAP_LABELS = CAP_LABELS
_JOIN_LABELS = JOIN_LABELS


def _value_sort_key(key):
    try:
        return (0, float(key), "")
    except Exception:
        exc_note("_value_sort_key @ ggis/ui/panels/symbology.py:187")
        return (1, 0.0, str(key))


_STYLE_COL_W = 92
_TABLE_ROW_H = 34


def _swatch_icon(color, size=14):
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter, QPen
    p = QPainter(pm)
    try:
        c = QColor(color)
        p.setBrush(c)
        p.setPen(QPen(QColor("#3A4552"), 1))
        p.drawRect(0, 0, size - 1, size - 1)
    finally:
        p.end()
    return QIcon(pm)


class _VCenterDelegate(QStyledItemDelegate):

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        try:
            a = int(option.displayAlignment)
            _vmask = int(Qt.AlignmentFlag.AlignVertical_Mask)
            _vc = int(Qt.AlignmentFlag.AlignVCenter)
            if (a & _vmask) != _vc:
                option.displayAlignment = Qt.AlignmentFlag(
                    (a & ~_vmask) | _vc)
        except Exception:
            exc_note("initStyleOption @ ggis/ui/panels/symbology.py:241")
            pass


def _fmt_num(v):
    if v is None:
        return "-"
    try:
        f = float(v)
    except Exception:
        exc_note("_fmt_num @ ggis/ui/panels/symbology.py:251")
        return str(v)
    if f != f:
        return "nan"
    if f == 0:
        return "0"
    a = abs(f)
    if a >= 1e7 or a < 1e-3:
        return "%.4g" % f
    if a >= 1000:
        return "{:,.2f}".format(f)
    return ("%.4f" % f).rstrip("0").rstrip(".") or "0"


def _parse_num(text):
    t = str(text or "").strip()
    if not t:
        return None
    try:
        f = float(t)
    except Exception:
        exc_note("_parse_num @ ggis/ui/panels/symbology.py:272")
        return None
    return f if f == f else None


def _same_symbol(sym, item):
    try:
        from ggis.core.crs import units as U
        from ggis.core.style import style_library as lib
        u = lib.target_unit()
        if QColor(item.get("fill", "#000000")).name() != sym.fill.name():
            return False
        if QColor(item.get("stroke", "#000000")).name() != sym.stroke.name():
            return False
        if QColor(item.get("fill", "#000000")).alpha() \
                != QColor(sym.fill).alpha():
            return False
        if QColor(item.get("stroke", "#000000")).alpha() \
                != QColor(sym.stroke).alpha():
            return False
        if abs(float(item.get("fill_alpha", 1.0))
               - float(sym.fill_alpha)) > 1e-3:
            return False
        if abs(U.to_px(float(item.get("width", 1.0)), u)
               - sym.px_width()) > 0.08:
            return False
        if abs(U.to_px(float(item.get("size", 4.0)), u)
               - sym.px_size()) > 0.08:
            return False
        for _k, _d in (("line_style", "solid"), ("fill_style", "solid"),
                       ("cap", "flat"), ("join", "bevel")):
            if str(item.get(_k, _d) or _d) != str(getattr(sym, _k, _d) or _d):
                return False
        return True
    except Exception:
        exc_note("_same_symbol @ ggis/ui/panels/symbology.py:318")
        return False


class _ColorRow(QWidget):

    changed = Signal(str)

    def __init__(self, label, color="#4C9BE8", parent=None, shape="rect"):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.lbl = QLabel(_tr(label), self)
        self.lbl.setMinimumWidth(34)
        self.btn = GgsColorField(color, self, shape=shape)
        self.btn.colorChanged.connect(self._on_color)
        lay.addWidget(self.lbl)
        lay.addWidget(self.btn)
        lay.addStretch(1)

    def _on_color(self, c):
        try:
            col = QColor(c)
            self.changed.emit(col.name(QColor.NameFormat.HexArgb))
        except Exception:
            exc_note("_on_color @ ggis/ui/panels/symbology.py:384")
            pass

    def setShape(self, shape):
        try:
            self.btn.setShape(shape)
        except Exception:
            exc_note("setShape @ ggis/ui/panels/symbology.py:390")
            pass

    def color(self):
        return self.btn.color().name()

    def setColor(self, c):
        self.btn.blockSignals(True)
        self.btn.setColor(c)
        self.btn.blockSignals(False)


class GgsSymStack(QStackedWidget):

    def sizeHint(self):
        w = self.currentWidget()
        if w is not None:
            return w.sizeHint()
        return super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        if w is not None:
            return w.minimumSizeHint()
        return super().minimumSizeHint()


class GgsSymbologyPanel(GgsDockWidget):

    styleChanged = Signal(object)
    activated = Signal()

    def __init__(self, title=None, parent=None):
        super().__init__(title or _tr("符号系统"), parent)
        self.setObjectName("GgsSymbologyDock")
        self._layer = None
        self._loading = False
        self._warned_class_n = 0
        self._is_raster = False
        self._ras_dirty = False
        self._ras_disp = None
        self._ras_uniq = {}
        self._ras_pal_ovr = {}
        self._ras_uniq_band = None
        self._ras_last_range = None
        self._ras_class_colors = []
        self._ras_class_breaks = []
        self._pending_single = {}
        self._pending_all = {}
        self._pending_kind = None
        self._pending_cat_color = {}
        self._pending_cat_sym = {}
        self._pending_grad_sym = {}
        self._grad_def_dirty = False
        self._cat_def_dirty = False
        self._grad_order = None
        self._cat_order = None
        self._pending_others = None
        self._pending_grad_color = {}
        self._pending_grad_break = {}
        self._grad_ovr = None
        self._grad_cnt_key = None
        self._grad_cnt = None
        self._build()
        self._refresh_layers()
        self._clear_all()
        try:
            from ggis.core.style import style_library as _lib
            _lib.on_changed(self._on_style_library_changed)
        except Exception:
            exc_note("__init__ @ ggis/ui/panels/symbology.py:523")
            pass

    def _on_style_library_changed(self):
        try:
            self._sync_style_button(self._base_symbol())
        except Exception:
            exc_note("_on_style_library_changed @ ggis/ui/panels/symbology.py:534")
            pass

    def showEvent(self, e):
        super().showEvent(e)
        try:
            self.activated.emit()
        except Exception:
            exc_note("showEvent @ ggis/ui/panels/symbology.py:542")
            pass
        try:
            QTimer.singleShot(0, self._relax_wide_inputs)
        except Exception:
            exc_note("showEvent @ ggis/ui/panels/symbology.py:556")
            pass

    def _build(self):
        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 6, 8, 2)
        lay.setSpacing(6)

        self.row_kind = QWidget()
        hk = QHBoxLayout(self.row_kind)
        hk.setContentsMargins(0, 0, 0, 0)
        hk.setSpacing(6)
        self.lbl_kind = QLabel(_tr("符号化"))
        hk.addWidget(self.lbl_kind)
        self.cmb_kind = GgsComboBox()
        self.cmb_kind.setObjectName("GgsSymKind")
        self.cmb_kind.addItem(_tr("单一符号"), "single")
        self.cmb_kind.addItem(_tr("唯一值"), "categorized")
        self.cmb_kind.addItem(_tr("分级色彩"), "graduated")
        self.cmb_kind.currentIndexChanged.connect(self._on_kind_changed)
        hk.addWidget(self.cmb_kind, 1)

        self.ras_mode = GgsComboBox()
        self.ras_mode.setObjectName("GgsSymRasMode")
        for _code, _label in rd.RENDER_MODES:
            self.ras_mode.addItem(_tr(_label), _code)
        self.ras_mode.currentIndexChanged.connect(self._on_raster_mode_changed)
        self.ras_mode.setVisible(False)
        hk.addWidget(self.ras_mode, 1)
        lay.addWidget(self.row_kind)

        self.row_sep = GgsSepH()
        self.row_sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(self.row_sep)

        self.stack = GgsSymStack()
        self.stack.addWidget(self._build_single())
        self.stack.addWidget(self._build_categorized())
        self.stack.addWidget(self._build_graduated())
        self.stack.addWidget(self._build_raster())
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.stack)
        self.scroll = GgsSymScroll()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(holder)
        lay.addWidget(self.scroll, 1)
        self.bottom_row = QWidget()
        hb = QVBoxLayout(self.bottom_row)
        hb.setContentsMargins(0, 4, 0, 0)
        hb.setSpacing(0)
        self.preview = GgsSymbolPreview(self, height=72, dark=self._dark)
        hb.addWidget(self.preview)
        lay.addWidget(self.bottom_row)
        foot = QHBoxLayout()
        foot.setSpacing(6)
        self.btn_import = GgsStyleImportButton(self, tip=_tr("导入符号系统"))
        self.btn_import.set_layer_source(self._import_layer_choices)
        self.btn_import.pickFromLibrary.connect(self._import_from_library)
        self.btn_import.pickFromLayer.connect(self._import_from_layer)
        foot.addWidget(self.btn_import)
        self.btn_apply = GgsSymApply(_tr("应用"))
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self._on_apply)
        self.lbl_cat_count = GgsSymCount("")
        self.lbl_cat_count.setVisible(False)
        foot.addStretch(1)
        foot.addWidget(self.lbl_cat_count)
        foot.addWidget(self.btn_apply)
        lay.addLayout(foot)
        self.setWidget(body)
        self._relax_wide_inputs()

    def _relax_wide_inputs(self, limit=96):
        from ggis.common.widgets.inputs import relax_wide_inputs
        relax_wide_inputs(self, limit=limit)

    def _build_single(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        from ggis.common.styling import icons as _icons
        try:
            self._dark = bool(_icons.is_dark())
        except Exception:
            exc_note("_build_single @ ggis/ui/panels/symbology.py:759")
            self._dark = True

        from ...render.symbol import (CAPS, FILL_STYLES, JOINS, LINE_STYLES,
                                      current_unit)
        _u0 = current_unit()

        self.grp_fill = QGroupBox(_tr("填充"))
        self.form_fill = QFormLayout(self.grp_fill)
        self.form_fill.setContentsMargins(8, 8, 8, 8)
        self.form_fill.setSpacing(4)
        self.lbl_fill = QLabel(_tr("填充"))
        self.fld_fill = GgsColorField("#4C9BE8", self, shape="rect")
        self.fld_fill.colorChanged.connect(
            lambda c: self._edit_single("fill", c))
        self.form_fill.addRow(self.lbl_fill, self.fld_fill)
        self.cmb_fill_style = GgsComboBox()
        for _k in FILL_STYLES:
            self.cmb_fill_style.addItem(_tr(_FILL_STYLE_LABELS.get(_k, _k)), _k)
        self.cmb_fill_style.currentIndexChanged.connect(self._on_fill_style)
        self.form_fill.addRow(_tr("样式"), self.cmb_fill_style)
        self.sp_fill_spacing = QDoubleSpinBox()
        self.sp_fill_width = QDoubleSpinBox()
        _apply_pattern_spins(self.sp_fill_spacing, self.sp_fill_width, _u0)
        self.sp_fill_spacing.valueChanged.connect(
            lambda v: self._edit_single("fill_spacing", v))
        self.sp_fill_width.valueChanged.connect(
            lambda v: self._edit_single("fill_width", v))
        self.lbl_fill_spacing = QLabel(_tr("间距"))
        self.lbl_fill_width = QLabel(_tr("图案线宽"))
        self.form_fill.addRow(self.lbl_fill_spacing, self.sp_fill_spacing)
        self.form_fill.addRow(self.lbl_fill_width, self.sp_fill_width)
        lay.addWidget(self.grp_fill)

        self.grp_stroke = QGroupBox(_tr("描边"))
        self.form_stroke = QFormLayout(self.grp_stroke)
        self.form_stroke.setContentsMargins(8, 8, 8, 8)
        self.form_stroke.setSpacing(4)
        self.lbl_stroke = QLabel(_tr("描边"))
        self.fld_stroke = GgsColorField("#1B2430", self, shape="line")
        self.fld_stroke.colorChanged.connect(
            lambda c: self._edit_single("stroke", c))
        self.form_stroke.addRow(self.lbl_stroke, self.fld_stroke)
        self.sp_width = QDoubleSpinBox()
        self.sp_width.setDecimals(2)
        self.sp_width.valueChanged.connect(
            lambda v: self._edit_single("width", v))
        self.lbl_width = QLabel(_tr("线宽"))
        self.form_stroke.addRow(self.lbl_width, self.sp_width)
        self.cmb_line_style = GgsComboBox()
        for _k in LINE_STYLES:
            self.cmb_line_style.addItem(_tr(_LINE_STYLE_LABELS.get(_k, _k)), _k)
        self.cmb_line_style.addItem(_tr("自定义…"), _DASH_CUSTOM)
        self.cmb_line_style.currentIndexChanged.connect(self._on_line_style)
        self.form_stroke.addRow(_tr("样式"), self.cmb_line_style)
        self.lbl_dash_pattern = QLabel(_tr("虚线图案（线宽倍数）"))
        self.ed_dash_pattern = QLineEdit()
        self.ed_dash_pattern.setPlaceholderText(
            "")
        self.ed_dash_pattern.editingFinished.connect(self._on_dash_pattern)
        self.form_stroke.addRow(self.lbl_dash_pattern, self.ed_dash_pattern)
        self.lbl_dash_pattern.setVisible(False)
        self.ed_dash_pattern.setVisible(False)
        self.cmb_cap = GgsComboBox()
        for _k in CAPS:
            self.cmb_cap.addItem(_tr(_CAP_LABELS.get(_k, _k)), _k)
        self.cmb_cap.currentIndexChanged.connect(self._on_cap)
        self.lbl_cap = QLabel(_tr("端头"))
        self.form_stroke.addRow(self.lbl_cap, self.cmb_cap)
        self.cmb_join = GgsComboBox()
        for _k in JOINS:
            self.cmb_join.addItem(_tr(_JOIN_LABELS.get(_k, _k)), _k)
        self.cmb_join.currentIndexChanged.connect(self._on_join)
        self.lbl_join = QLabel(_tr("连接"))
        self.form_stroke.addRow(self.lbl_join, self.cmb_join)
        lay.addWidget(self.grp_stroke)

        self.sp_size = QDoubleSpinBox()
        self.sp_size.setDecimals(2)
        self.sp_size.valueChanged.connect(
            lambda v: self._edit_single("size", v))
        _apply_unit_spins(self.sp_size, self.sp_width, _u0)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        self.lbl_size = QLabel(_tr("符号大小"))
        form.addRow(self.lbl_size, self.sp_size)

        lay.addLayout(form)
        lay.addStretch(1)
        self._sync_pattern_rows()
        return w

    def _on_fill_style(self, *a):
        self._sync_pattern_rows()
        try:
            k = str(self.cmb_fill_style.currentData() or "solid")
        except Exception:
            exc_note("_on_fill_style @ ggis/ui/panels/symbology.py:920")
            k = "solid"
        self._edit_single("fill_style", k)

    def _on_line_style(self, *a):
        try:
            k = str(self.cmb_line_style.currentData() or "solid")
        except Exception:
            exc_note("_on_line_style @ ggis/ui/panels/symbology.py:927")
            k = "solid"
        self._sync_dash_row()
        self._edit_single("line_style", k)

    def _on_dash_pattern(self):
        try:
            txt = str(self.ed_dash_pattern.text() or "")
            vals = tuple(float(v) for v in txt.replace("，", ",").split(",")
                         if v.strip())
        except Exception:
            exc_note("_on_dash_pattern @ ggis/ui/panels/symbology.py:942")
            return
        self._edit_single("dash_custom", tuple(v for v in vals if v > 0))

    def _sync_dash_row(self):
        try:
            on = str(self.cmb_line_style.currentData() or "solid") == "custom"
        except Exception:
            exc_note("_sync_dash_row @ ggis/ui/panels/symbology.py:950")
            on = False
        self.lbl_dash_pattern.setVisible(on)
        self.ed_dash_pattern.setVisible(on)

    def _on_cap(self, *a):
        try:
            k = str(self.cmb_cap.currentData() or "flat")
        except Exception:
            exc_note("_on_cap @ ggis/ui/panels/symbology.py:959")
            k = "flat"
        self._edit_single("cap", k)

    def _on_join(self, *a):
        try:
            k = str(self.cmb_join.currentData() or "bevel")
        except Exception:
            exc_note("_on_join @ ggis/ui/panels/symbology.py:967")
            k = "bevel"
        self._edit_single("join", k)

    def _sync_pattern_rows(self):
        try:
            on = str(self.cmb_fill_style.currentData() or "solid") != "solid"
        except Exception:
            exc_note("_sync_pattern_rows @ ggis/ui/panels/symbology.py:980")
            on = False
        for wdg in (self.lbl_fill_spacing, self.sp_fill_spacing,
                    self.lbl_fill_width, self.sp_fill_width):
            try:
                wdg.setVisible(bool(on))
            except Exception:
                exc_note("_sync_pattern_rows @ ggis/ui/panels/symbology.py:986")
                pass

    def _build_categorized(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        gb_cat = QGroupBox(_tr("分类"))
        gb_cat_lay = QVBoxLayout(gb_cat)
        gb_cat_lay.setContentsMargins(8, 8, 8, 8)
        gb_cat_lay.setSpacing(6)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.lbl_cat_field = QLabel(_tr("字段"))
        row.addWidget(self.lbl_cat_field)
        self.cat_field = GgsComboBox()
        self.cat_field.currentIndexChanged.connect(self._on_cat_field)
        self._relax_width(self.cat_field, 96)
        row.addWidget(self.cat_field, 1)
        self.btn_cat_build = QPushButton(_tr("分类"))
        self.btn_cat_build.clicked.connect(self._on_cat_rebuild)
        row.addWidget(self.btn_cat_build)
        gb_cat_lay.addLayout(row)

        row_r = QHBoxLayout()
        row_r.setContentsMargins(0, 0, 0, 0)
        row_r.setSpacing(6)
        self.lbl_cat_ramp = QLabel(_tr("色带"))
        row_r.addWidget(self.lbl_cat_ramp)
        self.cat_ramp = GgsColorRampField(self, with_invert=False)
        self.cat_ramp.setItemsProvider(self._ramp_items)
        self.cat_ramp.setItems(self._ramp_items(), "spectral")
        self.cat_ramp.rampChanged.connect(
            lambda _c: self._apply_ramp_to("categorized"))
        self._relax_width(self.cat_ramp, 120)
        row_r.addWidget(self.cat_ramp, 1)
        gb_cat_lay.addLayout(row_r)
        lay.addWidget(gb_cat)

        self.tbl_cat = GgsTableWidget(0, 3)
        self.tbl_cat.setHorizontalHeaderLabels(
            [_tr("值"), _tr("样式"), _tr("标签")])
        self.tbl_cat.verticalHeader().setVisible(False)
        setup_table_ops(self.tbl_cat, sortable=False, keep_widths=True,
                        row_height=_TABLE_ROW_H)
        self.tbl_cat.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        hh = self.tbl_cat.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        hh.resizeSection(0, 92)
        hh.resizeSection(1, _STYLE_COL_W)
        hh.setSortIndicatorShown(False)
        hh.sectionClicked.connect(self._on_cat_sort)
        self._tune_table(self.tbl_cat)
        self.tbl_cat.itemChanged.connect(self._on_cat_label)
        self.tbl_cat.cellDoubleClicked.connect(self._on_cat_double)

        act = QHBoxLayout()
        act.setContentsMargins(0, 0, 0, 0)
        act.setSpacing(4)
        self.btn_cat_add = self._icon_button(
            "add_feature", _tr("新增值（从未添加的值里挑一个）"),
            self._on_cat_add_value)
        act.addWidget(self.btn_cat_add)
        self.btn_cat_del = self._icon_button(
            "delete", _tr("删除值（删除当前行）"), self._on_cat_del_value)
        act.addWidget(self.btn_cat_del)
        self.btn_cat_add_all = self._icon_button(
            "new", _tr("新增所有值"),
            self._on_cat_add_all)
        act.addWidget(self.btn_cat_add_all)
        act.addStretch(1)
        lay.addLayout(act)
        lay.addWidget(self.tbl_cat, 1)
        self.tbl_cat.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_cat.customContextMenuRequested.connect(self._on_cat_menu)
        self.cat_others = _ColorRow("其他值", "#9C9C9C", w)
        self.cat_others.setVisible(False)
        return w

    def _build_graduated(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        gb_grad = QGroupBox(_tr("分级"))
        form = QFormLayout(gb_grad)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(4)
        self.grad_field = GgsComboBox()
        self.grad_field.currentIndexChanged.connect(self._on_grad_change)
        self._relax_width(self.grad_field, 96)
        form.addRow(_tr("字段"), self.grad_field)

        self.grad_mode = GgsComboBox()
        for m in ("equal", "quantile", "jenks", "stddev"):
            self.grad_mode.addItem(_tr(MODE_LABELS[m]), m)
        self.grad_mode.currentIndexChanged.connect(self._on_grad_change)
        form.addRow(_tr("方法"), self.grad_mode)

        self.grad_n = QSpinBox()
        self.grad_n.setRange(2, MAX_CLASSES)
        self.grad_n.setValue(5)
        self.grad_n.valueChanged.connect(self._on_grad_change)
        form.addRow(_tr("类数"), self.grad_n)

        self.grad_ramp = GgsColorRampField(self, with_invert=False)
        self.grad_ramp.setItemsProvider(self._ramp_items)
        self.grad_ramp.setItems(self._ramp_items(), "spectral")
        self.grad_ramp.rampChanged.connect(self._on_grad_ramp)
        self._relax_width(self.grad_ramp, 120)
        form.addRow(_tr("色带"), self.grad_ramp)
        lay.addWidget(gb_grad)

        self.tbl_grad = GgsTableWidget(0, 3)
        self.tbl_grad.setHorizontalHeaderLabels(
            [_tr("样式"), _tr("下限"), _tr("上限")])
        self.tbl_grad.verticalHeader().setVisible(False)
        setup_table_ops(self.tbl_grad, sortable=False, keep_widths=True,
                        row_height=_TABLE_ROW_H)
        self.tbl_grad.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.tbl_grad.setToolTip("")
        self.tbl_grad.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        hh = self.tbl_grad.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(True)
        hh.resizeSection(0, _STYLE_COL_W)
        hh.resizeSection(1, 92)
        hh.setSortIndicatorShown(False)
        hh.sectionClicked.connect(self._on_grad_sort)
        self.tbl_grad.itemChanged.connect(self._on_grad_break)
        self.tbl_grad.cellDoubleClicked.connect(self._on_grad_double)
        self._tune_table(self.tbl_grad)
        act = QHBoxLayout()
        act.setContentsMargins(0, 0, 0, 0)
        act.setSpacing(4)
        self.btn_grad_add = self._icon_button(
            "add_feature", _tr("新建分级"),
            self._on_grad_add_class)
        act.addWidget(self.btn_grad_add)
        self.btn_grad_del = self._icon_button(
            "delete", _tr("删除分级（区间并入相邻档）"),
            self._on_grad_del_class)
        act.addWidget(self.btn_grad_del)
        act.addStretch(1)
        lay.addLayout(act)
        lay.addWidget(self.tbl_grad, 1)
        self.tbl_grad.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl_grad.customContextMenuRequested.connect(self._on_grad_menu)
        return w

    def _build_raster(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        def _group(title):
            grp = QGroupBox(_tr(title))
            f = QFormLayout(grp)
            f.setContentsMargins(8, 8, 8, 8)
            f.setSpacing(4)
            lay.addWidget(grp)
            return grp, f

        self.grp_ras_data, form = _group("数据")

        self.ras_band = GgsComboBox()
        self.ras_band.setObjectName("GgsSymRasBand")
        self.ras_band.currentIndexChanged.connect(self._edit_raster)
        self.ras_band.currentIndexChanged.connect(self._on_raster_band_changed)
        self._row_data_band = QWidget()
        _hdb = QHBoxLayout(self._row_data_band)
        _hdb.setContentsMargins(0, 0, 0, 0)
        _hdb.setSpacing(0)
        _hdb.addWidget(self.ras_band)
        form.addRow(_tr("波段"), self._row_data_band)
        self._lbl_data_band = form.labelForField(self._row_data_band)

        self.ras_rgb = []
        self._rows_rgb = []
        for _txt in ("红波段 (R)", "绿波段 (G)", "蓝波段 (B)"):
            _cb = GgsComboBox()
            _cb.setObjectName("GgsSymRasRgb")
            _cb.currentIndexChanged.connect(self._edit_raster)
            _w = QWidget()
            _h = QHBoxLayout(_w)
            _h.setContentsMargins(0, 0, 0, 0)
            _h.setSpacing(0)
            _h.addWidget(_cb)
            form.addRow(_tr(_txt), _w)
            self.ras_rgb.append((_cb, _w, form.labelForField(_w)))
        self.ras_alpha = GgsComboBox()
        self.ras_alpha.setObjectName("GgsSymRasAlphaband")
        self.ras_alpha.currentIndexChanged.connect(self._edit_raster)
        self._row_ras_alpha = QWidget()
        _ha = QHBoxLayout(self._row_ras_alpha)
        _ha.setContentsMargins(0, 0, 0, 0)
        _ha.setSpacing(0)
        _ha.addWidget(self.ras_alpha)
        form.addRow(_tr("透明度波段"), self._row_ras_alpha)
        self._lbl_ras_alpha = form.labelForField(self._row_ras_alpha)

        self.ras_ramp = GgsColorRampField(self)
        self.ras_ramp.setItemsProvider(self._raster_ramp_items)
        self.ras_ramp.setItems(self._raster_ramp_items(),
                               current=rd.RAMP_NONE)
        self.ras_ramp.rampChanged.connect(self._on_ras_ramp_changed)
        self.ras_ramp.invertChanged.connect(self._edit_raster)
        self.ras_palette_bar = GgsColorRampBar()
        self.ras_palette_bar.setToolTip(
            _tr("数据源调色板"))
        from ggis.common.styling import icons as _icons
        self.btn_palette_reset = GgsSymRasPalReset()
        self.btn_palette_reset.setToolTip(_tr("恢复为数据源自带的配色"))
        try:
            _icons.bind(self.btn_palette_reset, "refresh", size=16)
            self.btn_palette_reset.setIconSize(QSize(16, 16))
        except Exception:
            exc_note("_build_raster @ ggis/ui/panels/symbology.py:1386")
            pass
        self.btn_palette_reset.setAutoRaise(True)
        self.btn_palette_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_palette_reset.clicked.connect(lambda *_: self._reset_palette())

        self.grp_ras_class, form_c = _group("分类")
        self.ras_class_n = GgsSymRasClassN()
        self.ras_class_n.setRange(2, MAX_CLASSES)
        self.ras_class_n.setValue(5)
        self.ras_class_n.setToolTip(
            _tr("改段数会重新计算断点"))
        self.ras_class_n.valueChanged.connect(self._on_ras_class_n)
        form_c.addRow(_tr("类数"), self.ras_class_n)
        self.ras_class_mode = GgsComboBox()
        self.ras_class_mode.setObjectName("GgsSymRasClassMode")
        for _code, _label in rd.CLASS_MODES:
            self.ras_class_mode.addItem(_tr(_label), _code)
        self._select_data(self.ras_class_mode, rd.DEFAULT_CLASS_MODE)
        self.ras_class_mode.currentIndexChanged.connect(
            self._on_ras_class_mode)
        form_c.addRow(_tr("方法"), self.ras_class_mode)
        self.tbl_ras_class = GgsTableWidget(0, 3)
        self.tbl_ras_class.setHorizontalHeaderLabels(
            [_tr("样式"), _tr("下限"), _tr("上限")])
        self.tbl_ras_class.verticalHeader().setVisible(False)
        setup_table_ops(self.tbl_ras_class, sortable=False, keep_widths=True,
                        row_height=_TABLE_ROW_H)
        self.tbl_ras_class.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        _hc = self.tbl_ras_class.horizontalHeader()
        _hc.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        _hc.setStretchLastSection(True)
        _hc.resizeSection(0, _STYLE_COL_W)
        self._tune_table(self.tbl_ras_class)
        self.tbl_ras_class.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.tbl_ras_class.itemChanged.connect(self._on_ras_class_break)
        form_c.addRow(self.tbl_ras_class)

        self._box_ras_uniq = QWidget()
        _vb = QVBoxLayout(self._box_ras_uniq)
        _vb.setContentsMargins(0, 0, 0, 0)
        _vb.setSpacing(4)
        self.tbl_ras_uniq = GgsTableWidget(0, 2)
        self.tbl_ras_uniq.setHorizontalHeaderLabels([_tr("值"), _tr("颜色")])
        self.tbl_ras_uniq.verticalHeader().setVisible(False)
        setup_table_ops(self.tbl_ras_uniq, sortable=False, keep_widths=True,
                        row_height=_TABLE_ROW_H)
        self.tbl_ras_uniq.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_ras_uniq.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        _hh = self.tbl_ras_uniq.horizontalHeader()
        _hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        _hh.setStretchLastSection(True)
        _hh.resizeSection(0, 92)
        _hh.resizeSection(1, _STYLE_COL_W)
        self._tune_table(self.tbl_ras_uniq)
        self.btn_ras_uniq_calc = QPushButton(_tr("分类"))
        self.btn_ras_uniq_calc.setToolTip(
            _tr("计算当前波段的全部唯一值并加入下表"))
        self.btn_ras_uniq_calc.clicked.connect(self._on_ras_uniq_calc)
        _hrow_uniq = QHBoxLayout()
        _hrow_uniq.setContentsMargins(0, 0, 0, 0)
        _hrow_uniq.setSpacing(4)
        _hrow_uniq.addWidget(self.btn_ras_uniq_calc)
        _hrow_uniq.addStretch(1)
        _vb.addLayout(_hrow_uniq)
        _vb.addWidget(self.tbl_ras_uniq)
        self._row_ras_uniq = self._box_ras_uniq
        self._lbl_ras_uniq = None
        lay.addWidget(self._box_ras_uniq)

        self.grp_ras_color, form = _group("着色")

        self.ras_ramp.invertChanged.connect(self._edit_raster)




        self.ras_opacity = GgsSliderSpin(self, 0, 100, " %")
        self.ras_opacity.setToolTip(
            "")
        self.ras_opacity.valueChanged.connect(self._edit_raster)

        self.lbl_ramp = QLabel(_tr("色带"))
        self.cell_ramp = QStackedWidget()
        _pg_ramp = QWidget()
        _l1 = QHBoxLayout(_pg_ramp)
        _l1.setContentsMargins(0, 0, 0, 0)
        _l1.addWidget(self.ras_ramp)
        _pg_pal = QWidget()
        _l2 = QHBoxLayout(_pg_pal)
        _l2.setContentsMargins(0, 0, 0, 0)
        _l2.setSpacing(6)
        _pal_bar_h = int(getattr(self.ras_ramp, "_h", 16) or 16) + 10
        try:
            self.ras_palette_bar.setFixedHeight(_pal_bar_h)
        except Exception:
            exc_note("_build_raster @ ggis/ui/panels/symbology.py:1575")
            pass
        _l2.addWidget(self.ras_palette_bar, 1,
                      Qt.AlignmentFlag.AlignVCenter)
        _l2.addWidget(self.btn_palette_reset, 0,
                      Qt.AlignmentFlag.AlignVCenter)
        self.cell_ramp.addWidget(_pg_ramp)
        self.cell_ramp.addWidget(_pg_pal)
        self._lbl_ramp_wrap = QWidget()
        _vl_ramp = QVBoxLayout(self._lbl_ramp_wrap)
        _vl_ramp.setContentsMargins(0, 0, 0, 0)
        _vl_ramp.addStretch(1)
        _vl_ramp.addWidget(self.lbl_ramp)
        _vl_ramp.addStretch(1)
        form.addRow(self._lbl_ramp_wrap, self.cell_ramp)


        form.addRow(_tr("透明度"), self.ras_opacity)

        self.grp_ras_mask, form_mask = _group("掩膜")
        self.ras_nodata_color = GgsColorField("#00000000", self, shape="rect")
        self.ras_nodata_color.setObjectName("GgsSymRasNodataColor")
        self.ras_nodata_color.colorChanged.connect(self._edit_raster)
        form_mask.addRow(_tr("无数据值"), self.ras_nodata_color)
        self.ras_bg_chk = GgsSymRasBgChk(_tr("掩膜背景"))
        self.ras_bg_chk.setChecked(False)
        self.ras_bg_chk.toggled.connect(self._on_ras_bg_toggled)
        form_mask.addRow(self.ras_bg_chk)
        self.ras_bg_value = GgsSymRasBgValue()
        self.ras_bg_value.setRange(-1e12, 1e12)
        self.ras_bg_value.setDecimals(4)
        self.ras_bg_value.setSingleStep(1.0)
        self.ras_bg_value.valueChanged.connect(self._edit_raster)
        self.ras_bg_color = GgsColorField("#00000000", self, shape="rect")
        self.ras_bg_color.setObjectName("GgsSymRasBgColor")
        self.ras_bg_color.colorChanged.connect(self._edit_raster)
        self._row_ras_bg_valuecolor = QWidget()
        _hbv = QHBoxLayout(self._row_ras_bg_valuecolor)
        _hbv.setContentsMargins(0, 0, 0, 0)
        _hbv.setSpacing(6)
        _hbv.addWidget(QLabel(_tr("值")))
        _hbv.addWidget(self.ras_bg_value)
        _hbv.addWidget(QLabel(_tr("颜色")))
        _hbv.addWidget(self.ras_bg_color)
        form_mask.addRow(self._row_ras_bg_valuecolor)
        self._on_ras_bg_toggled(False)

        self.grp_ras_stretch, form = _group("拉伸设置")
        self.ras_stretch = GgsComboBox()
        self.ras_stretch.setObjectName("GgsSymRasStretch")
        for code, label in rd.STRETCHES:
            self.ras_stretch.addItem(_tr(label), code)
        self.ras_stretch.currentIndexChanged.connect(self._on_stretch_type)
        form.addRow(_tr("类型"), self.ras_stretch)
        self.ras_ref_band = GgsComboBox()
        self.ras_ref_band.setObjectName("GgsSymRasRefBand")
        self.ras_ref_band.currentIndexChanged.connect(self._edit_raster)
        self._row_ras_ref = QWidget()
        _hrf = QHBoxLayout(self._row_ras_ref)
        _hrf.setContentsMargins(0, 0, 0, 0)
        _hrf.setSpacing(0)
        _hrf.addWidget(self.ras_ref_band)
        form.addRow(_tr("参考波段"), self._row_ras_ref)
        self._lbl_ras_ref = form.labelForField(self._row_ras_ref)

        self.ras_low = QDoubleSpinBox()
        self.ras_low.setRange(0.0, 100.0)
        self.ras_low.setDecimals(1)
        self.ras_low.setSingleStep(0.5)
        self.ras_low.setSuffix(" %")
        self.ras_low.valueChanged.connect(self._edit_raster)
        self.ras_high = QDoubleSpinBox()
        self.ras_high.setRange(0.0, 100.0)
        self.ras_high.setDecimals(1)
        self.ras_high.setSingleStep(0.5)
        self.ras_high.setSuffix(" %")
        self.ras_high.valueChanged.connect(self._edit_raster)
        self._row_pct = self._pair_row(self.ras_low, self.ras_high)
        form.addRow(_tr("百分位"), self._row_pct)
        self._lbl_pct = form.labelForField(self._row_pct)

        self.lbl_ras_vmax = GgsSymRasValue("—")
        self.lbl_ras_vmax.setToolTip(_tr("当前生效拉伸区间的上界（只读）"))
        self.lbl_ras_vmin = GgsSymRasValue("—")
        self.lbl_ras_vmin.setToolTip(_tr("当前生效拉伸区间的下界（只读）"))
        self._row_rng = QWidget()
        _hr = QHBoxLayout(self._row_rng)
        _hr.setContentsMargins(0, 0, 0, 0)
        _hr.setSpacing(4)
        _hr.addWidget(self.lbl_ras_vmax, 1)
        _hr.addWidget(self.lbl_ras_vmin, 1)
        form.addRow(_tr("值"), self._row_rng)
        self._lbl_rng = form.labelForField(self._row_rng)

        self.ed_ras_anno_max = GgsSymRasAnno()
        self.ed_ras_anno_max.setToolTip(_tr(
            "图例中「最大」那个标注的文字（不影响渲染）；留空 = 用上面的值"))
        self.ed_ras_anno_max.textEdited.connect(self._on_anno_edited)
        self.ed_ras_anno_min = GgsSymRasAnno()
        self.ed_ras_anno_min.setToolTip(_tr(
            "图例中「最小」那个标注的文字（不影响渲染）；留空 = 用上面的值"))
        self.ed_ras_anno_min.textEdited.connect(self._on_anno_edited)
        self._row_anno = QWidget()
        _ha = QHBoxLayout(self._row_anno)
        _ha.setContentsMargins(0, 0, 0, 0)
        _ha.setSpacing(4)
        _ha.addWidget(self.ed_ras_anno_max, 1)
        _ha.addWidget(self.ed_ras_anno_min, 1)
        form.addRow(_tr("标注"), self._row_anno)
        self._lbl_anno = form.labelForField(self._row_anno)

        self.ras_gamma = QDoubleSpinBox()
        self.ras_gamma.setRange(0.10, 5.00)
        self.ras_gamma.setSingleStep(0.05)
        self.ras_gamma.setDecimals(2)
        self.ras_gamma.setToolTip("")
        self.ras_gamma.valueChanged.connect(self._edit_raster)
        form.addRow(_tr("伽马"), self.ras_gamma)
        self.ras_stddev = QDoubleSpinBox()
        self.ras_stddev.setRange(0.5, 5.0)
        self.ras_stddev.setDecimals(1)
        self.ras_stddev.setSingleStep(0.5)
        self.ras_stddev.setValue(2.0)
        self.ras_stddev.setSuffix(" σ")
        self.ras_stddev.setToolTip(
            "")
        self.ras_stddev.valueChanged.connect(self._edit_raster)
        self._row_std = QWidget()
        _hs = QHBoxLayout(self._row_std)
        _hs.setContentsMargins(0, 0, 0, 0)
        _hs.setSpacing(0)
        _hs.addWidget(self.ras_stddev)
        form.addRow(_tr("标准差"), self._row_std)
        self._lbl_std = form.labelForField(self._row_std)



        for _i in range(lay.count() - 1, -1, -1):
            _it = lay.itemAt(_i)
            if _it is not None and _it.spacerItem() is not None:
                lay.takeAt(_i)
        for _w in (getattr(self, "grp_ras_data", None),
                   getattr(self, "grp_ras_color", None),
                   getattr(self, "grp_ras_stretch", None),
                   getattr(self, "grp_ras_class", None),
                   getattr(self, "_box_ras_uniq", None),
                   getattr(self, "grp_ras_mask", None)):
            if _w is None:
                continue
            try:
                lay.removeWidget(_w)
                lay.addWidget(_w)
            except Exception:
                exc_note("_build_raster @ ggis/ui/panels/symbology.py:1865")
                pass
        for _w in (getattr(self, "ras_band", None),
                   getattr(self, "ras_class_n", None),
                   getattr(self, "ras_class_mode", None),
                   getattr(self, "ras_stretch", None),
                   getattr(self, "ras_gamma", None),
                   getattr(self, "ras_opacity", None)):
            if _w is None:
                continue
            try:
                _sp = _w.sizePolicy()
                _sp.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
                _w.setSizePolicy(_sp)
            except Exception:
                exc_note("_build_raster @ ggis/ui/panels/symbology.py:1886")
                pass
        lay.addStretch(1)
        return w

    def _warn_many_classes(self, n):
        try:
            from ggis.core.app import settings as _st
            if not bool(_st.get("class_warn_enabled", True)):
                return
            thr = int(_st.get("class_warn_threshold", 50) or 0)
        except Exception:
            exc_note("_warn_many_classes @ ggis/ui/panels/symbology.py:1920")
            return
        try:
            n = int(n)
        except Exception:
            exc_note("_warn_many_classes @ ggis/ui/panels/symbology.py:1924")
            return
        if thr <= 0 or n <= thr:
            self._warned_class_n = 0
            return
        try:
            if n <= int(getattr(self, "_warned_class_n", 0) or 0):
                return
        except Exception:
            exc_note("_warn_many_classes @ ggis/ui/panels/symbology.py:1932")
            pass
        self._warned_class_n = n
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.warning(
                self.window(),
                _tr("分类数较多（{0} 个）").format(n),
                _tr("分类 / 分级数超过 {0} 个以后，符号与图例的生成、以及每次"
                    "重绘都会明显变慢；分位数 / 自然断点这类算法在类数很多时"
                    "会额外耗时。\n\n"
                    "可以继续使用；如果只是想要好看的渐变色，建议改用「拉伸」。\n\n"
                    "（这条提醒的开关与阈值，可在「选项 → 渲染」里调整。）")
                .format(thr))
        except Exception:
            exc_note("_warn_many_classes @ ggis/ui/panels/symbology.py:1946")
            pass

    @staticmethod
    def _tune_table(tbl, min_w=170):
        try:
            tbl.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows)
            tbl.setSelectionMode(
                QAbstractItemView.SelectionMode.SingleSelection)
        except Exception:
            exc_note("_tune_table @ ggis/ui/panels/symbology.py:1990")
            pass
        try:
            sp = tbl.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            tbl.setSizePolicy(sp)
        except Exception:
            exc_note("_tune_table @ ggis/ui/panels/symbology.py:1996")
            pass
        try:
            tbl.setMinimumWidth(int(min_w))
        except Exception:
            exc_note("_tune_table @ ggis/ui/panels/symbology.py:2000")
            pass
        try:
            tbl.setItemDelegate(_VCenterDelegate(tbl))
        except Exception:
            exc_note("_tune_table @ ggis/ui/panels/symbology.py:2008")
            pass
        try:
            tbl.setWordWrap(False)
        except Exception:
            exc_note("_tune_table @ ggis/ui/panels/symbology.py:2013")
            pass

    @staticmethod
    def _icon_button(icon_name, tip, slot, size=16):
        from ggis.common.widgets.buttons import GgsSmallButtonStyle1
        return GgsSmallButtonStyle1(icon_name, tip, slot, size)

    @staticmethod
    def _relax_width(w, min_w=96):
        try:
            sp = w.sizePolicy()
            sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            w.setSizePolicy(sp)
        except Exception:
            exc_note("_relax_width @ ggis/ui/panels/symbology.py:2054")
            pass
        try:
            w.setMinimumWidth(int(min_w))
        except Exception:
            exc_note("_relax_width @ ggis/ui/panels/symbology.py:2058")
            pass

    @staticmethod
    def _pair_row(a, b, min_w=56):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        for x in (a, b):
            try:
                sp = x.sizePolicy()
                sp.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                x.setSizePolicy(sp)
            except Exception:
                exc_note("_pair_row @ ggis/ui/panels/symbology.py:2086")
                pass
            try:
                x.setMinimumWidth(int(min_w))
            except Exception:
                exc_note("_pair_row @ ggis/ui/panels/symbology.py:2090")
                pass
        h.addWidget(a, 1)
        dash = QLabel("—")
        h.addWidget(dash)
        h.addWidget(b, 1)
        return w

    def _load_raster(self, layer):
        d = rd.get_display(layer).copy()
        self._ras_disp = d
        self.ras_band.clear()
        try:
            n = max(1, int(layer.band_count() or 1))
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2106")
            n = 1
        self._band_n = n
        if n >= 3:
            self.ras_band.addItem(_tr("自动（三波段彩色）"), 0)
        for b in range(1, n + 1):
            self.ras_band.addItem(_tr("波段 {0}").format(b), b)
        try:
            self.ras_ref_band.clear()
            self.ras_ref_band.addItem(_tr("无"), 0)
            for b in range(1, n + 1):
                self.ras_ref_band.addItem(_tr("波段 {0}").format(b), b)
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2121")
            pass
        for _cb, _w, _l in (getattr(self, "ras_rgb", None) or []):
            _cb.clear()
            _cb.addItem(_tr("自动"), 0)
            for b in range(1, n + 1):
                _cb.addItem(_tr("波段 {0}").format(b), b)
        try:
            self.ras_alpha.clear()
            self.ras_alpha.addItem(_tr("无"), 0)
            for b in range(1, n + 1):
                self.ras_alpha.addItem(_tr("波段 {0}").format(b), b)
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2135")
            pass
        self._rebuild_ras_modes(layer, d)
        self._select_data(self.ras_mode, rd.render_mode(d))
        self._select_data(self.ras_band, int(d.band or 0))
        self.ras_ramp.setRamp(d.ramp or rd.RAMP_NONE)
        self._select_data(self.ras_stretch, d.stretch)
        try:
            self._select_data(self.ras_ref_band,
                              int(d.stretch_ref_band or 0))
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2156")
            pass
        self.ras_ramp.setInvert(bool(d.invert_ramp))
        self.ras_low.setValue(float(d.low))
        self.ras_high.setValue(float(d.high))
        try:
            self.ras_stddev.setValue(float(getattr(d, "stddev_k", 2.0) or 2.0))
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2167")
            pass
        for _w, _v in ((self.lbl_ras_vmax, d.vmax),
                       (self.lbl_ras_vmin, d.vmin)):
            try:
                _w.setText("—" if _v is None else _fmt_num(float(_v)))
            except Exception:
                exc_note("_load_raster @ ggis/ui/panels/symbology.py:2176")
                pass
        try:
            self._ras_anno_edited = bool(d.anno_max or d.anno_min)
            self.ed_ras_anno_max.setText(str(d.anno_max or ""))
            self.ed_ras_anno_min.setText(str(d.anno_min or ""))
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2186")
            pass
        self.ras_gamma.setValue(float(d.gamma or 1.0))
        try:
            self.ras_class_n.setValue(int(d.class_n) if int(d.class_n) >= 2 else 5)
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2195")
            pass
        self.ras_opacity.setValue(
            int(round((1.0 - float(d.opacity)) * 100)))
        try:
            rb = d.rgb_bands or rd.default_rgb_bands(n) or (0, 0, 0)
            for i, (cb, _w, _l) in enumerate(self.ras_rgb):
                self._select_data(cb, int(rb[i]) if i < len(rb) else 0)
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2209")
            pass
        try:
            self._select_data(self.ras_alpha, int(d.alpha_band or 0))
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2214")
            pass
        try:
            self.ras_bg_chk.setChecked(bool(getattr(d, "bg_enabled", False)))
            _bv = getattr(d, "bg_value", None)
            self.ras_bg_value.setValue(float(_bv) if _bv is not None else 0.0)
            _bc = getattr(d, "bg_color", "") or ""
            self.ras_bg_color.setColor(QColor(_bc) if _bc else QColor(0, 0, 0, 0))
            _nc = getattr(d, "nodata_color", "") or ""
            self.ras_nodata_color.setColor(QColor(_nc) if _nc else QColor(0, 0, 0, 0))
            self._on_ras_bg_toggled(self.ras_bg_chk.isChecked())
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2231")
            pass
        _cm = dict(d.color_map or {})
        if rd.render_mode(d) == rd.MODE_COLORMAP:
            self._ras_pal_ovr = _cm
            self._ras_uniq = {}
            self._ras_uniq_band = None
        else:
            self._ras_uniq = _cm
            self._ras_pal_ovr = {}
            self._ras_uniq_band = int(d.band or 0) or None
        self._ras_class_colors = list(d.class_colors or [])
        self._ras_class_breaks = list(d.class_breaks or [])
        try:
            _cm = rd.class_mode_of(d)
            self._select_data(self.ras_class_mode, _cm)
            if _cm != rd.CLASS_CUSTOM and not self._ras_class_breaks:
                self._apply_class_mode()
        except Exception:
            exc_note("_load_raster @ ggis/ui/panels/symbology.py:2260")
            pass
        self._fill_ras_uniq_table()
        self._sync_class_table_editable()
        self._fill_ras_class_table()
        self._sync_raster_enabled()
        self._ras_last_range = None
        self._refresh_range()

    def _rebuild_ras_modes(self, layer, d):
        cb = getattr(self, "ras_mode", None)
        if cb is None or layer is None:
            return
        cur = str(cb.currentData() or "")
        try:
            has_map = bool(rd.palette(layer))
        except Exception:
            exc_note("_rebuild_ras_modes @ ggis/ui/panels/symbology.py:2298")
            has_map = False
        _is_int = rd.band_is_integer(layer, int(getattr(d, "band", 0) or 0))
        want = []
        want.append(rd.MODE_RGB)
        want.append(rd.MODE_PSEUDO)
        want.append(rd.MODE_CLASSIFY)
        if has_map:
            want.append(rd.MODE_COLORMAP)
        if _is_int:
            want.append(rd.MODE_UNIQUE)
        cur = cur or rd.render_mode(d)
        if cur not in want:
            if cur == rd.MODE_UNIQUE and not _is_int:
                cur = rd.MODE_PSEUDO
            if cur not in want:
                want.append(cur)
        if [cb.itemData(i) for i in range(cb.count())] == want:
            return
        cb.blockSignals(True)
        try:
            cb.clear()
            for code in want:
                cb.addItem(_tr(rd.RENDER_MODE_LABELS.get(code, code)), code)
        finally:
            cb.blockSignals(False)

    def _sync_raster_enabled(self):
        try:
            if getattr(self, "ras_stretch", None) is None:
                return
            st = self.ras_stretch.currentData()
            active = (st != rd.STRETCH_NONE)
            for _w in (getattr(self, "_row_pct", None),
                       getattr(self, "_lbl_pct", None)):
                if _w is not None:
                    _w.setVisible(st == rd.STRETCH_PERCENTILE)
            for _w in (getattr(self, "_row_std", None),
                       getattr(self, "_lbl_std", None)):
                if _w is not None:
                    _w.setVisible(st == rd.STRETCH_STDDEV)
            for _w in (getattr(self, "_row_rng", None),
                       getattr(self, "_lbl_rng", None),
                       getattr(self, "_row_anno", None),
                       getattr(self, "_lbl_anno", None)):
                if _w is not None:
                    _w.setVisible(bool(active))
            if getattr(self, "ras_gamma", None) is not None:
                self.ras_gamma.setEnabled(bool(active))
            mode = str(self.ras_mode.currentData() or rd.MODE_RGB)
            self.ras_band.setEnabled(mode != rd.MODE_RGB)
            self.ras_ramp.setEnabled(
                mode in (rd.MODE_PSEUDO, rd.MODE_CLASSIFY, rd.MODE_UNIQUE))
            for _w, _on in (
                    (getattr(self, "grp_ras_stretch", None),
                     mode == rd.MODE_PSEUDO),
                    (getattr(self, "grp_ras_class", None),
                     mode == rd.MODE_CLASSIFY),
                    (getattr(self, "_box_ras_uniq", None),
                     mode in (rd.MODE_UNIQUE, rd.MODE_COLORMAP))):
                if _w is not None:
                    _w.setVisible(bool(_on))
            _ramp_on = mode in (rd.MODE_PSEUDO, rd.MODE_CLASSIFY,
                                rd.MODE_COLORMAP, rd.MODE_UNIQUE)
            for _w in (getattr(self, "_lbl_ramp_wrap", None),
                       getattr(self, "lbl_ramp", None),
                       getattr(self, "cell_ramp", None)):
                if _w is not None:
                    _w.setVisible(bool(_ramp_on))
            if _ramp_on:
                _pal = (mode == rd.MODE_COLORMAP)
                try:
                    self.lbl_ramp.setText(_tr("调色板") if _pal
                                          else _tr("色带"))
                    self.cell_ramp.setCurrentIndex(1 if _pal else 0)
                except Exception:
                    exc_note("_sync_raster_enabled @ ggis/ui/panels/symbology.py:2431")
                    pass
            for _w in (getattr(self, "_row_data_band", None),
                       getattr(self, "_lbl_data_band", None)):
                if _w is not None:
                    _w.setVisible(mode != rd.MODE_RGB)
            for _cb, _w, _l in (getattr(self, "ras_rgb", None) or []):
                _w.setVisible(mode == rd.MODE_RGB)
                if _l is not None:
                    _l.setVisible(mode == rd.MODE_RGB)
            for _w in (getattr(self, "_row_ras_alpha", None),
                       getattr(self, "_lbl_ras_alpha", None)):
                if _w is not None:
                    _w.setVisible(mode == rd.MODE_RGB)
            try:
                _st = str(self.ras_stretch.currentData() or "")
            except Exception:
                exc_note("_sync_raster_enabled @ ggis/ui/panels/symbology.py:2460")
                _st = ""
            _ref_on = (_st == rd.STRETCH_HIST_MATCH
                       and int(getattr(self, "_band_n", 0) or 0) >= 2)
            for _w in (getattr(self, "_row_ras_ref", None),
                       getattr(self, "_lbl_ras_ref", None)):
                if _w is not None:
                    _w.setVisible(_ref_on)
            try:
                if mode == rd.MODE_COLORMAP:
                    self._refresh_palette_row()
                _bc = getattr(self, "btn_ras_uniq_calc", None)
                if _bc is not None:
                    _bc.setVisible(mode == rd.MODE_UNIQUE)
            except Exception:
                exc_note("_sync_raster_enabled @ ggis/ui/panels/symbology.py:2482")
                pass
        except Exception:
            exc_note("_sync_raster_enabled @ ggis/ui/panels/symbology.py:2484")
            pass

    def _fit_ras_uniq_height(self):
        tbl = getattr(self, "tbl_ras_uniq", None)
        if tbl is None:
            return
        hh = tbl.horizontalHeader()
        h = hh.height() if (hh is not None and hh.isVisible()) else 0
        for i in range(tbl.rowCount()):
            h += tbl.rowHeight(i)
        tbl.setFixedHeight(max(h, 1))

    def _fill_ras_uniq_table(self):
        tbl = getattr(self, "tbl_ras_uniq", None)
        if tbl is None:
            return
        try:
            mode = str(self.ras_mode.currentData() or "")
        except Exception:
            exc_note("_fill_ras_uniq_table @ ggis/ui/panels/symbology.py:2519")
            mode = ""
        cm = {}
        if mode == rd.MODE_COLORMAP:
            try:
                _d = (self._ras_disp.copy() if self._ras_disp is not None
                      else rd.GgsRasterDisplay())
                _d.use_colormap = True
                _d.color_map = dict(getattr(self, "_ras_pal_ovr", None) or {})
            except Exception:
                exc_note("_fill_ras_uniq_table @ ggis/ui/panels/symbology.py:2528")
                _d = None
            try:
                _, cm = rd.legend_palette(self._layer, _d, limit=None)
            except Exception:
                exc_note("_fill_ras_uniq_table @ ggis/ui/panels/symbology.py:2539")
                cm = {}
        else:
            cm = dict(getattr(self, "_ras_uniq", None) or {})
        out = {}
        for k, v in cm.items():
            try:
                if isinstance(v, str):
                    out["%d" % int(float(k))] = v
                else:
                    out["%d" % int(float(k))] = "#%02X%02X%02X" % (
                        int(v[0]), int(v[1]), int(v[2]))
            except Exception:
                exc_note("_fill_ras_uniq_table @ ggis/ui/panels/symbology.py:2552")
                continue
        tbl.blockSignals(True)
        try:
            keys = sorted(out, key=_value_sort_key)
            tbl.setRowCount(len(keys))
            for i, k in enumerate(keys):
                it = QTableWidgetItem(str(k))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled
                            | Qt.ItemFlag.ItemIsSelectable)
                tbl.setItem(i, 0, it)
                btn = GgsColorField(str(out[k]), tbl, shape="rect",
                                    width=_STYLE_COL_W - 8,
                                    height=_TABLE_ROW_H - 8)
                btn.colorChanged.connect(
                    lambda c, key=k, row=i: (tbl.selectRow(row),
                                             self._on_ras_uniq_color(key, c)))
                tbl.setCellWidget(i, 1, btn)
        finally:
            tbl.blockSignals(False)
        self._fit_ras_uniq_height()
        self._refresh_palette_row()

    def _refresh_palette_row(self):
        bar = getattr(self, "ras_palette_bar", None)
        if bar is not None:
            cols = []
            try:
                _d = (self._ras_disp.copy() if self._ras_disp is not None
                      else rd.GgsRasterDisplay())
                _d.use_colormap = True
                _d.color_map = dict(getattr(self, "_ras_pal_ovr", None) or {})
                cm = rd.render_palette(self._layer, _d) or {}
                for k in sorted(cm)[:64]:
                    v = cm[k]
                    cols.append("#%02X%02X%02X" % (int(v[0]), int(v[1]),
                                                   int(v[2])))
            except Exception:
                exc_note("_refresh_palette_row @ ggis/ui/panels/symbology.py:2603")
                cols = []
            try:
                bar.setColors(cols)
            except Exception:
                exc_note("_refresh_palette_row @ ggis/ui/panels/symbology.py:2607")
                pass
        btn = getattr(self, "btn_palette_reset", None)
        if btn is not None:
            try:
                btn.setEnabled(bool(getattr(self, "_ras_pal_ovr", None)))
            except Exception:
                exc_note("_refresh_palette_row @ ggis/ui/panels/symbology.py:2613")
                pass

    def _reset_palette(self):
        if self._loading or self._layer is None:
            return
        self._ras_pal_ovr = {}
        self._fill_ras_uniq_table()
        self._edit_raster()

    def _on_ras_uniq_color(self, key, color):
        if self._loading:
            return
        try:
            hexs = QColor(color).name().upper()
        except Exception:
            exc_note("_on_ras_uniq_color @ ggis/ui/panels/symbology.py:2634")
            return
        try:
            mode = str(self.ras_mode.currentData() or "")
        except Exception:
            exc_note("_on_ras_uniq_color @ ggis/ui/panels/symbology.py:2638")
            mode = ""
        if mode == rd.MODE_COLORMAP:
            ovr = dict(getattr(self, "_ras_pal_ovr", None) or {})
            ovr[str(key)] = hexs
            self._ras_pal_ovr = ovr
        else:
            self._ras_uniq[str(key)] = hexs
        self._edit_raster()

    def _ras_ramp_code(self):
        try:
            return str(self.ras_ramp.ramp() or rd.RAMP_NONE)
        except Exception:
            exc_note("_ras_ramp_code @ ggis/ui/panels/symbology.py:2657")
            return rd.RAMP_NONE

    def _on_ras_uniq_calc(self, *_a):
        if self._loading or self._layer is None or not self._is_raster:
            return
        from ..dialogs import busy as _busy
        _busy.show_busy_delayed(
            self.window(), _tr("计算唯一值"),
            _tr("正在统计当前波段的全部取值…"))
        try:
            self._fill_ras_uniq()
        finally:
            _busy.hide_busy()
        if not (self._ras_uniq or {}):
            try:
                QToolTip.showText(
                    QCursor.pos(),
                    _tr("当前波段取值过于连续（不同值超过 256 个），"
                        "无法按唯一值渲染；请改用拉伸 / 分类。"))
            except Exception:
                exc_note("_on_ras_uniq_calc @ ggis/ui/panels/symbology.py:2689")
                pass

    def _on_ras_ramp_changed(self, *_a):
        if getattr(self, "_loading", False):
            return
        try:
            _m = str(self.ras_mode.currentData() or "")
            if _m == rd.MODE_UNIQUE and (self._ras_uniq or {}):
                self._fill_ras_uniq()
                return
            if _m == rd.MODE_CLASSIFY:
                self._ras_class_colors = []
                self._fill_ras_class_table()
        except Exception:
            exc_note("_on_ras_ramp_changed @ ggis/ui/panels/symbology.py:2715")
            pass
        self._edit_raster()

    def _class_default_breaks(self, d, n):
        lo, hi = 0.0, 255.0
        try:
            lim = rd.layer_limits(self._layer, d, band=int(d.band or 0))
            if lim:
                lo, hi = float(lim[0]), float(lim[1])
        except Exception:
            exc_note("_class_default_breaks @ ggis/ui/panels/symbology.py:2727")
            pass
        if not (hi > lo):
            hi = lo + 1.0
        return [lo + (hi - lo) * i / n for i in range(n + 1)]

    def _fill_ras_class_table(self):
        tbl = getattr(self, "tbl_ras_class", None)
        if tbl is None or self._layer is None:
            return
        try:
            d = self._collect_raster()
            n = int(rd.class_steps(d) or 0)
        except Exception:
            exc_note("_fill_ras_class_table @ ggis/ui/panels/symbology.py:2745")
            return
        tbl.blockSignals(True)
        try:
            if n < 2:
                tbl.setRowCount(0)
                self._fit_ras_class_height(tbl, 0)
                return
            cols = rd.class_color_list(d)
            bk = rd.class_breaks_of(d) or self._class_default_breaks(d, n)
            tbl.setRowCount(n)
            for i in range(n):
                hexs = ("#%02X%02X%02X" % tuple(cols[i])
                        if i < len(cols) else "#808080")
                btn = GgsColorField(hexs, tbl, shape="rect",
                                    width=_STYLE_COL_W - 8,
                                    height=_TABLE_ROW_H - 8)
                btn.colorChanged.connect(
                    lambda c, r=i: (tbl.selectRow(r),
                                    self._on_ras_class_color(r, c)))
                tbl.setCellWidget(i, 0, btn)
                for j, v in ((1, bk[i]), (2, bk[i + 1])):
                    it = QTableWidgetItem(_fmt_num(v))
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled
                                | Qt.ItemFlag.ItemIsSelectable
                                | Qt.ItemFlag.ItemIsEditable)
                    tbl.setItem(i, j, it)
            self._fit_ras_class_height(tbl, n)
        finally:
            tbl.blockSignals(False)

    def _fit_ras_class_height(self, tbl, n):
        _hh = tbl.horizontalHeader()
        _h = max(int(_hh.height()), 24)
        tbl.setFixedHeight(_h + max(0, int(n)) * _TABLE_ROW_H + 4)

    def _on_stretch_type(self, _i=None):
        self._sync_raster_enabled()
        self._edit_raster()

    def _sync_class_table_editable(self):
        tbl = getattr(self, "tbl_ras_class", None)
        if tbl is None:
            return
        try:
            custom = (str(self.ras_class_mode.currentData() or "")
                      == rd.CLASS_CUSTOM)
        except Exception:
            exc_note("_sync_class_table_editable @ ggis/ui/panels/symbology.py:2814")
            custom = False
        try:
            tbl.setEditTriggers(
                (QAbstractItemView.EditTrigger.DoubleClicked
                 | QAbstractItemView.EditTrigger.EditKeyPressed) if custom
                else QAbstractItemView.EditTrigger.NoEditTriggers)
        except Exception:
            exc_note("_sync_class_table_editable @ ggis/ui/panels/symbology.py:2821")
            pass

    def _apply_class_mode(self):
        try:
            mode = str(self.ras_class_mode.currentData()
                       or rd.DEFAULT_CLASS_MODE)
        except Exception:
            exc_note("_apply_class_mode @ ggis/ui/panels/symbology.py:2836")
            return
        if mode == rd.CLASS_CUSTOM:
            return
        n = 0
        try:
            n = int(self.ras_class_n.value())
        except Exception:
            exc_note("_apply_class_mode @ ggis/ui/panels/symbology.py:2843")
            n = 0
        lim = None
        band = 0
        try:
            d = self._collect_raster()
            band = int(getattr(d, "band", 0) or 0)
            lim = rd.layer_limits(self._layer, d, band=band)
        except Exception:
            exc_note("_apply_class_mode @ ggis/ui/panels/symbology.py:2851")
            lim = None
        self._ras_class_breaks = list(
            rd.classify_breaks(self._layer, band, mode, n, limits=lim) or [])

    def _on_ras_class_mode(self, _v=None):
        if self._loading:
            return
        self._apply_class_mode()
        self._sync_class_table_editable()
        self._fill_ras_class_table()
        self._edit_raster()

    def _on_ras_class_n(self, _v=None):
        if self._loading:
            return
        try:
            self._warn_many_classes(int(self.ras_class_n.value()))
        except Exception:
            exc_note("_on_ras_class_n @ ggis/ui/panels/symbology.py:2879")
            pass
        self._ras_class_breaks = []
        self._apply_class_mode()
        self._fill_ras_class_table()
        self._edit_raster()

    def _on_ras_class_break(self, item):
        if self._loading or self._layer is None or item is None:
            return
        col = int(item.column())
        row = int(item.row())
        if col not in (1, 2):
            return
        try:
            if str(self.ras_class_mode.currentData() or "") != rd.CLASS_CUSTOM:
                self.ras_class_mode.blockSignals(True)
                self._select_data(self.ras_class_mode, rd.CLASS_CUSTOM)
                self.ras_class_mode.blockSignals(False)
                self._sync_class_table_editable()
        except Exception:
            exc_note("_on_ras_class_break @ ggis/ui/panels/symbology.py:2909")
            pass
        try:
            d = self._collect_raster()
            n = int(rd.class_steps(d) or 0)
        except Exception:
            exc_note("_on_ras_class_break @ ggis/ui/panels/symbology.py:2914")
            return
        if not (0 <= row < n):
            return
        try:
            v = float(str(item.text()).strip())
        except Exception:
            exc_note("_on_ras_class_break @ ggis/ui/panels/symbology.py:2920")
            self._fill_ras_class_table()
            return
        bk = list(rd.class_breaks_of(d) or self._class_default_breaks(d, n))
        if len(bk) != n + 1:
            self._fill_ras_class_table()
            return
        if col == 1:
            bk[row] = v
        else:
            bk[row + 1] = v
        for i in range(1, len(bk)):
            if not (bk[i] > bk[i - 1]):
                self._fill_ras_class_table()
                return
        self._ras_class_breaks = bk
        self._fill_ras_class_table()
        self._edit_raster()

    def _on_ras_class_color(self, row, color):
        if self._loading or self._layer is None:
            return
        try:
            hexs = QColor(color).name().upper()
            r = int(row)
        except Exception:
            exc_note("_on_ras_class_color @ ggis/ui/panels/symbology.py:2946")
            return
        try:
            d = self._collect_raster()
            n = int(rd.class_steps(d) or 0)
        except Exception:
            exc_note("_on_ras_class_color @ ggis/ui/panels/symbology.py:2951")
            return
        if not (0 <= r < n):
            return
        cols = ["#%02X%02X%02X" % tuple(t) for t in rd.class_color_list(d)]
        cs = list(getattr(self, "_ras_class_colors", None) or [])
        if len(cs) < n:
            cs = list(cols) + [""] * max(0, n - len(cs))
        cs[r] = hexs
        self._ras_class_colors = cs[:n]
        self._edit_raster()

    def _fill_ras_uniq(self):
        if self._layer is None:
            return
        cm = {}
        _band = 0
        try:
            _band = int(getattr(self, "ras_band", None) is not None
                        and (self.ras_band.currentData() or 0) or 0)
            cm = rd.auto_color_map(self._layer, band=_band,
                                   ramp=self._ras_ramp_code())
        except Exception:
            exc_note("_fill_ras_uniq @ ggis/ui/panels/symbology.py:2988")
            cm = {}
        self._ras_uniq_band = _band if cm else None
        self._ras_uniq = dict(cm)
        self._fill_ras_uniq_table()
        self._edit_raster()

    def _refresh_range(self, force=False):
        w_max = getattr(self, "lbl_ras_vmax", None)
        w_min = getattr(self, "lbl_ras_vmin", None)
        if w_max is None or w_min is None:
            return
        d = getattr(self, "_ras_disp", None)
        if d is None or self._layer is None or not self._is_raster:
            return
        try:
            d = self._collect_raster()
        except Exception:
            exc_note("_refresh_range @ ggis/ui/panels/symbology.py:3015")
            return
        if d is None:
            return
        st = str(d.stretch or "")
        lo = hi = None
        if st == rd.STRETCH_CUSTOM and d.vmin is not None and d.vmax is not None:
            lo, hi = float(d.vmin), float(d.vmax)
        if lo is None or hi is None:
            try:
                lim = rd.layer_limits(self._layer, d, band=int(d.band or 0))
                if lim:
                    lo, hi = float(lim[0]), float(lim[1])
            except Exception:
                exc_note("_refresh_range @ ggis/ui/panels/symbology.py:3028")
                lo = hi = None
        if lo is None or hi is None:
            try:
                s = rd.stats_for(self._layer, d, band=int(d.band or 0)) or {}
                lo, hi = s.get("min"), s.get("max")
            except Exception:
                exc_note("_refresh_range @ ggis/ui/panels/symbology.py:3034")
                lo = hi = None
        if lo is None or hi is None:
            return
        for _w, _v in ((w_max, hi), (w_min, lo)):
            try:
                _w.setText(_fmt_num(float(_v)))
            except Exception:
                exc_note("_refresh_range @ ggis/ui/panels/symbology.py:3041")
                pass
        _cur = (float(hi), float(lo))
        _prev = getattr(self, "_ras_last_range", None)
        self._ras_last_range = _cur
        _range_changed = (_prev is not None and _prev != _cur)
        if _range_changed:
            self._ras_anno_edited = False
        if _range_changed or not bool(getattr(self, "_ras_anno_edited", False)):
            for _w, _v in ((self.ed_ras_anno_max, hi),
                           (self.ed_ras_anno_min, lo)):
                try:
                    _w.setText(_fmt_num(float(_v)))
                except Exception:
                    exc_note("_refresh_range @ ggis/ui/panels/symbology.py:3071")
                    pass

    def _collect_raster(self):
        d = (self._ras_disp.copy() if self._ras_disp is not None
             else rd.GgsRasterDisplay())
        st = self.ras_stretch.currentData() or rd.STRETCH_PERCENTILE
        d.stretch = st
        d.band = int(self.ras_band.currentData() or 0)
        d.gamma = float(self.ras_gamma.value())
        d.opacity = 1.0 - self.ras_opacity.value() / 100.0
        d.bg_enabled = bool(self.ras_bg_chk.isChecked())
        d.bg_value = None
        d.bg_color = ""
        if d.bg_enabled:
            try:
                d.bg_value = float(self.ras_bg_value.value())
            except Exception:
                exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3092")
                d.bg_value = None
            d.bg_color = self.ras_bg_color.color().name(QColor.NameFormat.HexArgb)
        d.use_nodata = True
        d.nodata = None
        d.nodata_color = self.ras_nodata_color.color().name(QColor.NameFormat.HexArgb)
        d.low = float(self.ras_low.value())
        d.high = float(self.ras_high.value())
        d.stddev_k = float(self.ras_stddev.value())
        if st == rd.STRETCH_CUSTOM:
            try:
                if (d.vmin is not None and d.vmax is not None
                        and float(d.vmin) > float(d.vmax)):
                    d.vmin, d.vmax = d.vmax, d.vmin
            except Exception:
                exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3116")
                pass
        else:
            d.vmin = d.vmax = None
        try:
            d.class_n = int(self.ras_class_n.value())
        except Exception:
            exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3129")
            d.class_n = 0
        if getattr(self, "_ras_class_colors", None):
            d.class_colors = list(self._ras_class_colors)
        d.class_breaks = list(getattr(self, "_ras_class_breaks", None) or [])
        try:
            d.class_mode = str(self.ras_class_mode.currentData()
                               or rd.DEFAULT_CLASS_MODE)
        except Exception:
            exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3142")
            d.class_mode = rd.DEFAULT_CLASS_MODE
        d.ramp = self.ras_ramp.ramp() or rd.RAMP_NONE
        d.invert_ramp = bool(self.ras_ramp.invert())
        try:
            d.anno_max = str(self.ed_ras_anno_max.text() or "").strip()
            d.anno_min = str(self.ed_ras_anno_min.text() or "").strip()
        except Exception:
            exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3152")
            d.anno_max = d.anno_min = ""
        try:
            vals = [int(cb.currentData() or 0)
                    for cb, _w, _l in (self.ras_rgb or [])]
            d.rgb_bands = tuple(vals) if (len(vals) == 3
                                          and all(v > 0 for v in vals)) else None
        except Exception:
            exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3160")
            d.rgb_bands = None
        try:
            d.alpha_band = max(0, int(self.ras_alpha.currentData() or 0))
        except Exception:
            exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3165")
            d.alpha_band = 0
        try:
            d.stretch_ref_band = max(0,
                                     int(self.ras_ref_band.currentData() or 0))
        except Exception:
            exc_note("_collect_raster @ ggis/ui/panels/symbology.py:3171")
            d.stretch_ref_band = 0
        _mode0 = str(self.ras_mode.currentData() or rd.MODE_RGB)
        if _mode0 == rd.MODE_COLORMAP:
            d.color_map = dict(getattr(self, "_ras_pal_ovr", None) or {})
        else:
            d.color_map = dict(getattr(self, "_ras_uniq", None) or {})
        rd.set_render_mode(d, _mode0, ramp=self.ras_ramp.ramp())
        if d.low > d.high:
            d.low, d.high = d.high, d.low
        return d

    def _on_raster_mode_changed(self, *_a):
        if self._loading:
            return
        try:
            mode = str(self.ras_mode.currentData() or rd.MODE_RGB)
            if mode != rd.MODE_RGB:
                if int(self.ras_band.currentData() or 0) == 0:
                    i = self.ras_band.findData(1)
                    if i >= 0:
                        self.ras_band.setCurrentIndex(i)
            if mode in (rd.MODE_CLASSIFY, rd.MODE_UNIQUE):
                try:
                    if (str(self.ras_ramp.ramp() or rd.RAMP_NONE)
                            == rd.RAMP_NONE):
                        self.ras_ramp.setRamp("spectral")
                except Exception:
                    exc_note("_on_raster_mode_changed @ ggis/ui/panels/symbology.py:3224")
                    pass
            try:
                self._fill_ras_uniq_table()
                self._fill_ras_class_table()
            except Exception:
                exc_note("_on_raster_mode_changed @ ggis/ui/panels/symbology.py:3232")
                pass
        except Exception:
            exc_note("_on_raster_mode_changed @ ggis/ui/panels/symbology.py:3240")
            pass
        self._edit_raster()

    def _on_raster_band_changed(self, *_a):
        if self._loading or self._layer is None or not self._is_raster:
            return
        try:
            if str(self.ras_mode.currentData() or rd.MODE_RGB) != rd.MODE_UNIQUE:
                return
            _band = int(getattr(self, "ras_band", None) is not None
                        and (self.ras_band.currentData() or 0) or 0)
            if _band == self._ras_uniq_band:
                return
            if not (self._ras_uniq or {}):
                return
            self._fill_ras_uniq()
        except Exception:
            exc_note("_on_raster_band_changed @ ggis/ui/panels/symbology.py:3267")
            pass

    def _on_anno_edited(self, *_a):
        self._ras_anno_edited = True
        self._edit_raster()
        self._push_anno_now()

    def _push_anno_now(self):
        if self._loading or self._layer is None or not self._is_raster:
            return
        try:
            d = rd.get_display(self._layer)
            if d is None:
                return
            d.anno_max = str(self.ed_ras_anno_max.text() or "").strip()
            d.anno_min = str(self.ed_ras_anno_min.text() or "").strip()
            rd.set_display(self._layer, d)
        except Exception:
            exc_note("_push_anno_now @ ggis/ui/panels/symbology.py:3304")
            return
        self._commit()

    def _edit_raster(self, *_a):
        self._sync_raster_enabled()
        if self._loading or self._layer is None:
            return
        if not self._is_raster:
            return
        self._ras_dirty = True
        self._mark_dirty()
        self._refresh_range()

    def _on_ras_bg_toggled(self, checked):
        _on = bool(checked)
        self._row_ras_bg_valuecolor.setEnabled(_on)
        if not self._loading:
            self._edit_raster()

    def set_project(self, project):
        old = getattr(self, "_project", None)
        if old is not None and old is not project:
            try:
                old.layersChanged.disconnect(self._refresh_layers)
            except Exception:
                exc_note("set_project @ ggis/ui/panels/symbology.py:3344")
                pass
        self._project = project
        if project is not None:
            try:
                project.layersChanged.connect(self._refresh_layers)
            except Exception:
                exc_note("set_project @ ggis/ui/panels/symbology.py:3350")
                pass
        self._refresh_layers()

    def _refresh_layers(self):
        proj = getattr(self, "_project", None)
        cur = self._layer
        alive = False
        if cur is not None and proj is not None:
            try:
                for lyr in proj.layers():
                    if lyr is cur:
                        alive = True
                        break
            except Exception:
                exc_note("_refresh_layers @ ggis/ui/panels/symbology.py:3370")
                alive = False
        if alive:
            self._load(cur)
            return
        self._layer = None
        self._clear_all()

    def set_layer(self, layer):
        if layer is None:
            if self._layer is None:
                return
            self._reset_pending()
            self._layer = None
            self._clear_all()
            return
        if layer is self._layer:
            return
        self._reset_pending()
        self._layer = layer
        self._load(layer)

    def reload_from_layer(self, layer):
        if layer is None or self._layer is None or layer is not self._layer:
            return
        try:
            if self.btn_apply.isEnabled():
                return
        except Exception:
            exc_note("reload_from_layer @ ggis/ui/panels/symbology.py:3425")
            pass
        try:
            self._load(layer)
        except Exception:
            exc_note("reload_from_layer @ ggis/ui/panels/symbology.py:3429")
            pass

    def _reset_pending(self):
        self._pending_kind = None
        self._pending_single = {}
        self._pending_all = {}
        self._pending_cat_color = {}
        self._ras_last_range = None
        self._pending_cat_sym = {}
        self._pending_others = None
        self._pending_others_show = None
        self._pending_grad_sym = {}
        self._pending_grad_color = {}
        self._pending_grad_break = {}
        self._grad_def_dirty = False
        self._cat_def_dirty = False
        self._cat_ovr = None
        self._cat_miss_key = None
        self._grad_ovr = None
        self._grad_cnt_key = None
        self._grad_cnt = None
        self._grad_order = None
        self._cat_order = None

    def current_layer(self):
        return self._layer

    def _clear_all(self):
        self._loading = True
        try:
            self.tbl_cat.setRowCount(0)
            self.tbl_grad.setRowCount(0)
            self._sync_size_row(None)
            self.btn_apply.setEnabled(False)
            self._set_content_visible(False)
            self.bottom_row.setVisible(False)
            try:
                self.btn_import.setVisible(False)
            except Exception:
                exc_note("_clear_all @ ggis/ui/panels/symbology.py:3495")
                pass
            self._reset_pending()
        finally:
            self._loading = False
        self._is_raster = False
        self._ras_dirty = False
        self._update_title()

    def _set_content_visible(self, on):
        on = bool(on)
        for wdg in (getattr(self, "row_kind", None),
                    getattr(self, "row_sep", None),
                    getattr(self, "scroll", None),
                    getattr(self, "btn_apply", None)):
            if wdg is None:
                continue
            try:
                wdg.setVisible(on)
            except Exception:
                exc_note("_set_content_visible @ ggis/ui/panels/symbology.py:3520")
                pass

    def _update_title(self):
        name = ""
        try:
            if self._layer is not None:
                name = str(self._layer.name() or "")
        except Exception:
            exc_note("_update_title @ ggis/ui/panels/symbology.py:3533")
            name = ""
        text = (_tr("符号系统 — {0}").format(name) if name
                else _tr("符号系统"))
        try:
            self.set_title_label(text)
        except Exception:
            exc_note("_update_title @ ggis/ui/panels/symbology.py:3539")
            pass

    def _load(self, layer):
        self._loading = True
        try:
            self._ras_dirty = False
            self._grad_def_dirty = False
            self._cat_def_dirty = False
            self._grad_order = None
            self._cat_order = None
            self._is_raster = bool(layer is not None and layer.is_raster())
            self.btn_apply.setEnabled(False)
            if layer is None:
                self._clear_all()
                return
            if self._is_raster:
                self._set_content_visible(True)
                try:
                    self.cmb_kind.setVisible(False)
                    self.ras_mode.setVisible(True)
                except Exception:
                    exc_note("_load @ ggis/ui/panels/symbology.py:3564")
                    pass
                self.stack.setEnabled(True)
                self._load_raster(layer)
                self.stack.setCurrentIndex(PAGE_RASTER)
                return

            if not layer.is_vector():
                self._layer = None
                self._clear_all()
                return

            self._set_content_visible(True)
            try:
                self.ras_mode.setVisible(False)
                self.cmb_kind.setVisible(True)
            except Exception:
                exc_note("_load @ ggis/ui/panels/symbology.py:3589")
                pass
            fields = fields_from_layer(layer)

            for cmb, numeric_only in ((self.cat_field, False),
                                      (self.grad_field, True)):
                cmb.clear()
                for f in fields:
                    if numeric_only and not f.is_numeric():
                        continue
                    cmb.addItem("%s (%s)" % (f.name,
                                             KIND_LABEL.get(f.type, f.type)),
                                f.name)

            r = get_renderer(layer)
            tname = getattr(r, "type_name", "single")
            self.cmb_kind.setCurrentIndex(
                {"single": 0, "categorized": 1,
                 "graduated": 2}.get(tname, 0))
            self.stack.setCurrentIndex(self.cmb_kind.currentIndex())

            if isinstance(r, GgsCategorizedRenderer):
                self._select_field(self.cat_field, r.field)
                self._fill_cat_table(r)
                self.cat_others.setColor(
                    _sym_color(r.others_symbol, self._layer) if r.others_symbol
                    else "#9C9C9C")
            elif isinstance(r, GgsGraduatedRenderer):
                self._select_field(self.grad_field, r.field)
                self._select_data(self.grad_mode, r.mode)
                self.grad_n.setValue(max(2, min(r.n_classes,
                                                self.grad_n.maximum())))
                self.grad_ramp.setRamp(r.ramp)
                self._fill_grad_table(r)
            else:
                self._fill_single(r.symbol)

            self._sync_size_row(layer)
        finally:
            self._loading = False
            self._update_title()
            self._sync_bottom_row()
            self._relax_wide_inputs()

    @staticmethod
    def _select_data(cmb, value):
        for i in range(cmb.count()):
            if cmb.itemData(i) == value:
                cmb.setCurrentIndex(i)
                return

    def _select_field(self, cmb, name):
        self._select_data(cmb, name)

    @staticmethod
    def _icon_shape(kind):
        return "line" if str(kind or "") == "line" else "rect"

    def _sync_bottom_row(self):
        try:
            on = (self._layer is not None) and (not self._is_raster) \
                and int(self.stack.currentIndex()) == 0
            self.bottom_row.setVisible(bool(on))
        except Exception:
            exc_note("_sync_bottom_row @ ggis/ui/panels/symbology.py:3677")
            pass
        self._sync_import_button()

    def _sync_import_button(self):
        try:
            self.btn_import.setVisible(self._layer is not None)
        except Exception:
            exc_note("_sync_import_button @ ggis/ui/panels/symbology.py:3689")
            pass


    def _sync_size_row(self, layer):
        try:
            kind = layer.base_kind() if layer is not None else ""
        except Exception:
            exc_note("_sync_size_row @ ggis/ui/panels/symbology.py:3706")
            kind = ""
        is_point = (kind == "point")
        is_line = bool(_SYM_COLOR_BY_KIND and kind == "line")
        self.lbl_size.setVisible(is_point)
        self.sp_size.setVisible(is_point)
        try:
            self.grp_fill.setTitle(_tr("填充") if not is_line else _tr("颜色"))
            self.grp_fill.setVisible(not is_line)
            self.grp_stroke.setTitle(_tr("线条") if is_line else _tr("描边"))
            self.grp_stroke.setVisible(True)
            self.lbl_cap.setVisible(bool(is_line))
            self.cmb_cap.setVisible(bool(is_line))
            self.lbl_join.setVisible(True)
            self.cmb_join.setVisible(True)
            self.lbl_width.setText(_tr("线宽"))
            self._sync_pattern_rows()
            self.lbl_fill.setText(_tr("填充") if not is_line
                                  else _tr("颜色"))
            self.lbl_stroke.setText(_tr("颜色") if is_line
                                    else _tr("描边"))
            self.fld_fill.setShape(self._icon_shape(kind))
            self.fld_stroke.setShape("line")
            self.cat_others.setShape(self._icon_shape(kind))
        except Exception:
            exc_note("_sync_size_row @ ggis/ui/panels/symbology.py:3749")
            pass

    def _fill_single(self, sym):
        try:
            from ggis.common.styling import icons as _icons2
            self._dark = bool(_icons2.is_dark())
        except Exception:
            exc_note("_fill_single @ ggis/ui/panels/symbology.py:3758")
            pass
        self.fld_fill.setColor(QColor(sym.fill))
        self.fld_stroke.setColor(QColor(sym.stroke))
        from ...render.symbol import current_unit
        _u = str(getattr(sym, "unit", None) or "") or current_unit()
        _apply_unit_spins(self.sp_size, self.sp_width, _u,
                          extra=max(float(sym.size), float(sym.width)))
        self.sp_size.setValue(round(float(sym.size), 4))
        self.sp_width.setValue(round(float(sym.width), 4))
        _apply_pattern_spins(
            self.sp_fill_spacing, self.sp_fill_width, _u,
            extra=max(float(getattr(sym, "fill_spacing", 0.0) or 0.0),
                      float(getattr(sym, "fill_width", 0.0) or 0.0)))
        self._select_data(self.cmb_fill_style,
                          str(getattr(sym, "fill_style", "solid") or "solid"))
        self._select_data(self.cmb_line_style,
                          str(getattr(sym, "line_style", "solid") or "solid"))
        self.ed_dash_pattern.setText(
            ", ".join(str(float(v)) for v in
                      (getattr(sym, "dash_custom", ()) or ())))
        self._sync_dash_row()
        self._select_data(self.cmb_cap,
                          str(getattr(sym, "cap", "flat") or "flat"))
        self._select_data(self.cmb_join,
                          str(getattr(sym, "join", "bevel") or "bevel"))
        self.sp_fill_spacing.setValue(
            round(float(getattr(sym, "fill_spacing", 0.0) or 0.0), 4))
        self.sp_fill_width.setValue(
            round(float(getattr(sym, "fill_width", 0.0) or 0.0), 4))
        self._sync_pattern_rows()
        self.preview.setSymbol(sym, self._cur_kind(), self._dark)
        self._sync_style_button(sym)

    def _style_items(self, layer):
        from ..dialogs.symbol import symbol_items_for_kind
        try:
            kind = str(layer.base_kind()) if layer is not None else ""
        except Exception:
            exc_note("_style_items @ ggis/ui/panels/symbology.py:3819")
            kind = ""
        return symbol_items_for_kind(kind)

    def _cur_kind(self):
        try:
            return str(self._layer.base_kind()) if self._layer else "polygon"
        except Exception:
            exc_note("_cur_kind @ ggis/ui/panels/symbology.py:3828")
            return "polygon"

    def _base_symbol(self):
        if self._layer is None:
            return None
        try:
            syms = get_renderer(self._layer).symbols()
            return syms[0] if syms else None
        except Exception:
            exc_note("_base_symbol @ ggis/ui/panels/symbology.py:3841")
            return None

    def _compose_preview_symbol(self):
        base = self._base_symbol()
        if base is None:
            return None
        try:
            sym = base.clone()
        except Exception:
            exc_note("_compose_preview_symbol @ ggis/ui/panels/symbology.py:3856")
            return None
        pend = dict(getattr(self, "_pending_single", {}) or {})
        try:
            if "fill" in pend:
                sym.fill = QColor(pend["fill"])
            if "stroke" in pend:
                sym.stroke = QColor(pend["stroke"])
            if "size" in pend:
                sym.size = float(pend["size"])
            if "width" in pend:
                sym.width = float(pend["width"])
            if "opacity" in pend:
                sym.opacity = float(pend["opacity"])
            if "fill_alpha" in pend:
                sym.fill_alpha = float(pend["fill_alpha"])
            if "line_style" in pend:
                sym.line_style = str(pend["line_style"])
            if "dash_custom" in pend:
                sym.dash_custom = tuple(pend["dash_custom"] or ())
            if "cap" in pend:
                sym.cap = str(pend["cap"])
            if "join" in pend:
                sym.join = str(pend["join"])
            if "fill_style" in pend:
                sym.fill_style = str(pend["fill_style"])
            if "fill_spacing" in pend:
                sym.fill_spacing = float(pend["fill_spacing"])
            if "fill_width" in pend:
                sym.fill_width = float(pend["fill_width"])
        except Exception:
            exc_note("_compose_preview_symbol @ ggis/ui/panels/symbology.py:3888")
            pass
        return sym

    def _preview_refresh(self):
        sym = self._compose_preview_symbol()
        if sym is not None:
            self.preview.setSymbol(sym, self._cur_kind(), self._dark)

    def _sync_style_button(self, sym):
        self._sync_import_button()

    def _renderer_is_single(self):
        if self._layer is None:
            return True
        try:
            return isinstance(get_renderer(self._layer),
                              GgsSingleSymbolRenderer)
        except Exception:
            exc_note("_renderer_is_single @ ggis/ui/panels/symbology.py:3919")
            return True

    def _mode_is_single_for_import(self):
        pend = str(getattr(self, "_pending_kind", None) or "")
        if pend:
            return pend == "single"
        return self._renderer_is_single()

    def _import_render_mode(self, src_layer):
        if self._layer is None or self._is_raster:
            return
        try:
            want = str(getattr(get_renderer(src_layer), "type_name", "")
                       or "")
        except Exception:
            exc_note("_import_render_mode @ ggis/ui/panels/symbology.py:3957")
            return
        if want not in ("single", "categorized", "graduated"):
            return
        cmb = getattr(self, "cmb_kind", None)
        if cmb is None:
            return
        idx = -1
        for i in range(cmb.count()):
            if cmb.itemData(i) == want:
                idx = i
                break
        if idx < 0:
            return
        cur = ""
        try:
            cur = str(getattr(get_renderer(self._layer), "type_name", "")
                      or "")
        except Exception:
            exc_note("_import_render_mode @ ggis/ui/panels/symbology.py:3975")
            cur = ""
        if want == (str(getattr(self, "_pending_kind", None) or "") or cur):
            return
        try:
            cmb.blockSignals(True)
            cmb.setCurrentIndex(idx)
        finally:
            try:
                cmb.blockSignals(False)
            except Exception:
                exc_note("_import_render_mode @ ggis/ui/panels/symbology.py:3989")
                pass
        self.stack.setCurrentIndex(idx)
        self._sync_bottom_row()
        self._fill_tables_for(self._make_renderer(want))
        self._refresh_count_label()
        self._pending_kind = want
        self._mark_dirty()

    def _apply_item_to_all_symbols(self, renderer, item):
        try:
            from ggis.core.crs import units as U
            from ggis.core.style.style_library import target_unit
        except Exception:
            exc_note("_apply_item_to_all_symbols @ ggis/ui/panels/symbology.py:4013")
            return
        src = target_unit()
        try:
            syms = list(renderer.symbols() or [])
        except Exception:
            exc_note("_apply_item_to_all_symbols @ ggis/ui/panels/symbology.py:4018")
            syms = []
        for sym in syms:
            try:
                dst = str(getattr(sym, "unit", "") or "") or src
                if dst != src:
                    def conv(v, _s=src, _d=dst):
                        return U.convert(float(v), _s, _d)
                else:
                    def conv(v):
                        return float(v)
                sym.fill = QColor(item.get("fill", "#4C9BE8"))
                sym.stroke = QColor(item.get("stroke", "#1B2430"))
                sym.width = conv(item.get("width", 1.0))
                sym.size = conv(item.get("size", 4.0))
                sym.fill_alpha = float(item.get("fill_alpha", 1.0))
                sym.line_style = str(item.get("line_style", "solid"))
                sym.fill_style = str(item.get("fill_style", "solid"))
                sym.cap = str(item.get("cap", "flat"))
                sym.join = str(item.get("join", "bevel"))
            except Exception:
                exc_note("_apply_item_to_all_symbols @ ggis/ui/panels/symbology.py:4040")
                continue
        try:
            renderer.invalidate()
        except Exception:
            exc_note("_apply_item_to_all_symbols @ ggis/ui/panels/symbology.py:4044")
            pass

    def _on_style_picked(self, item):
        if self._loading or self._layer is None or not item:
            return
        if not self._mode_is_single_for_import():
            self._pending_all = dict(item)
            self._mark_dirty()
            return
        try:
            from ggis.core.crs import units as U
            from ggis.core.style.style_library import target_unit
            src = target_unit()
            base = self._base_symbol()
            dst = str(getattr(base, "unit", None) or "") or src
            if dst != src:
                conv = lambda v: U.convert(float(v), src, dst)
            else:
                conv = lambda v: float(v)
            self._pending_single.update({
                "fill": item.get("fill", "#4C9BE8"),
                "stroke": item.get("stroke", "#1B2430"),
                "width": conv(item.get("width", 1.0)),
                "size": conv(item.get("size", 4.0)),
                "fill_alpha": float(item.get("fill_alpha", 1.0)),
                "line_style": str(item.get("line_style", "solid")),
                "fill_style": str(item.get("fill_style", "solid")),
                "cap": str(item.get("cap", "flat")),
                "join": str(item.get("join", "bevel")),
            })
        except Exception:
            exc_note("_on_style_picked @ ggis/ui/panels/symbology.py:4094")
            return
        self._mark_dirty()
        self._loading = True
        try:
            sym = self._compose_preview_symbol()
            if sym is not None:
                self._fill_single(sym)
        finally:
            self._loading = False

    def _other_vector_layers(self):
        proj = getattr(self, "_project", None)
        rows = []
        try:
            layers = list(proj.layers()) if proj is not None else []
        except Exception:
            exc_note("_other_vector_layers @ ggis/ui/panels/symbology.py:4124")
            layers = []
        for lyr in layers:
            if lyr is self._layer:
                continue
            try:
                if not lyr.is_vector():
                    continue
                name = str(lyr.name() or "")
            except Exception:
                exc_note("_other_vector_layers @ ggis/ui/panels/symbology.py:4133")
                continue
            rows.append((name or _tr("未命名图层"), lyr))
        return rows

    def _import_layer_choices(self):
        if self._is_raster:
            return self._other_layers_of("raster")
        return self._other_vector_layers()

    def _other_layers_of(self, kind):
        proj = getattr(self, "_project", None)
        rows = []
        try:
            layers = list(proj.layers()) if proj is not None else []
        except Exception:
            exc_note("_other_layers_of @ ggis/ui/panels/symbology.py:4154")
            layers = []
        want_raster = (str(kind) == "raster")
        for lyr in layers:
            if lyr is self._layer:
                continue
            try:
                if bool(lyr.is_raster()) != want_raster:
                    continue
                if not want_raster and not lyr.is_vector():
                    continue
                name = str(lyr.name() or "")
            except Exception:
                exc_note("_other_layers_of @ ggis/ui/panels/symbology.py:4166")
                continue
            rows.append((name or _tr("未命名图层"), lyr))
        return rows

    def _import_from_library(self):
        if self._is_raster:
            self._import_raster_from_library()
            return
        items = self._style_items(self._layer)
        if not items:
            return
        try:
            item = GgsSymbolGalleryDialog.getItem(
                items, self._cur_kind(), self._dark,
                current_key=None, parent=self, category="symbol")
        except Exception:
            exc_note("_import_from_library @ ggis/ui/panels/symbology.py:4188")
            item = None
        if item:
            self._on_style_picked(item)

    def _import_raster_from_library(self):
        try:
            from ggis.core.style import style_library as _lib
            items = list(_lib.items("ramp"))
        except Exception:
            exc_note("_import_raster_from_library @ ggis/ui/panels/symbology.py:4198")
            items = []
        if not items:
            return
        cur = ""
        try:
            cur = str(self.ras_ramp.ramp() or "")
        except Exception:
            exc_note("_import_raster_from_library @ ggis/ui/panels/symbology.py:4205")
            cur = ""
        try:
            item = GgsSymbolGalleryDialog.getItem(
                items, "polygon", self._dark,
                current_key=cur or None, parent=self, category="ramp")
        except Exception:
            exc_note("_import_raster_from_library @ ggis/ui/panels/symbology.py:4211")
            item = None
        if item:
            self._apply_raster_import({"ramp": str(item.get("key") or "")})

    def _import_raster_from_layer(self, layer):
        try:
            from ggis.core.style import raster_display as rd
            src = rd.get_display(layer)
        except Exception:
            exc_note("_import_raster_from_layer @ ggis/ui/panels/symbology.py:4226")
            return
        if src is None:
            return
        item = {
            "ramp": str(getattr(src, "ramp", "") or ""),
            "invert_ramp": bool(getattr(src, "invert_ramp", False)),
            "stretch": str(getattr(src, "stretch", "")
                           or rd.STRETCH_PERCENTILE),
            "low": float(getattr(src, "low", 2.0)),
            "high": float(getattr(src, "high", 98.0)),
            "stddev_k": float(getattr(src, "stddev_k", 2.0)),
            "gamma": float(getattr(src, "gamma", 1.0)),
            "opacity": 1.0 - float(getattr(src, "opacity", 1.0)),
        }
        self._apply_raster_import(item)

    def _apply_raster_import(self, item):
        if not item or self._layer is None or not self._is_raster:
            return
        self._loading = True
        try:
            code = str(item.get("ramp") or "")
            if code:
                self.ras_ramp.setRamp(code)
            if "invert_ramp" in item:
                try:
                    self.ras_ramp.setInvert(bool(item["invert_ramp"]))
                except Exception:
                    exc_note("_apply_raster_import @ ggis/ui/panels/symbology.py:4263")
                    pass
            val = str(item.get("stretch") or "")
            if val:
                self._select_data(self.ras_stretch, val)
            for key, setter in (("low", self.ras_low),
                                ("high", self.ras_high),
                                ("stddev_k", self.ras_stddev),
                                ("gamma", self.ras_gamma)):
                if key in item:
                    try:
                        setter.setValue(float(item[key]))
                    except Exception:
                        exc_note("_apply_raster_import @ ggis/ui/panels/symbology.py:4275")
                        pass
            if "opacity" in item:
                try:
                    self.ras_opacity.setValue(
                        max(0.0, min(100.0, float(item["opacity"]) * 100.0)))
                except Exception:
                    exc_note("_apply_raster_import @ ggis/ui/panels/symbology.py:4281")
                    pass
        finally:
            self._loading = False
        self._ras_dirty = True
        self._sync_raster_enabled()
        self._refresh_range()
        self._mark_dirty()

    def _import_from_layer(self, layer):
        if self._is_raster:
            self._import_raster_from_layer(layer)
            return
        self._import_render_mode(layer)
        try:
            from ...render.renderers import get_renderer
            syms = get_renderer(layer).symbols()
            sym = syms[0] if syms else None
        except Exception:
            exc_note("_import_from_layer @ ggis/ui/panels/symbology.py:4312")
            sym = None
        if sym is None:
            return
        item = {}
        for k in ("fill", "stroke", "width", "size", "fill_alpha",
                  "fill_style", "line_style", "cap", "join"):
            try:
                v = getattr(sym, k)
            except Exception:
                exc_note("_import_from_layer @ ggis/ui/panels/symbology.py:4321")
                continue
            if k in ("fill", "stroke"):
                try:
                    v = QColor(v).name(QColor.NameFormat.HexArgb)
                except Exception:
                    exc_note("_import_from_layer @ ggis/ui/panels/symbology.py:4327")
                    continue
            item[k] = v
        try:
            from ggis.core.crs import units as U
            from ggis.core.style.style_library import target_unit
            tu = target_unit()
            su = str(getattr(sym, "unit", "") or "") or tu
            for k in ("width", "size"):
                if k in item:
                    item[k] = U.convert(float(item[k]), su, tu)
        except Exception:
            exc_note("_import_from_layer @ ggis/ui/panels/symbology.py:4338")
            pass
        self._on_style_picked(item)

    def _view_order(self, key, n):
        order = getattr(self, key, None)
        try:
            if order is None or len(order) != int(n):
                order = list(range(int(n)))
                setattr(self, key, order)
            return order
        except Exception:
            exc_note("_view_order @ ggis/ui/panels/symbology.py:4350")
            return list(range(int(n)))

    def _model_row(self, key, n, disp):
        try:
            order = self._view_order(key, n)
            d = int(disp)
            if 0 <= d < len(order):
                return int(order[d])
        except Exception:
            exc_note("_model_row @ ggis/ui/panels/symbology.py:4360")
            pass
        return int(disp)

    def _fill_cat_table(self, r):
        ents = (list(self._cat_ovr) if getattr(self, "_cat_ovr", None) is not None
                else list(getattr(r, "entries", []) or []))
        n = len(ents)
        order = self._view_order("_cat_order", n)
        self.tbl_cat.blockSignals(True)
        try:
            self.tbl_cat.setRowCount(n)
            for disp, mi in enumerate(order):
                v, sym = ents[mi]
                it = QTableWidgetItem("" if v is None else str(v))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled
                            | Qt.ItemFlag.ItemIsSelectable)
                it.setToolTip("" if v is None else str(v))
                self.tbl_cat.setItem(disp, 0, it)
                _sym = (getattr(self, "_pending_cat_sym", {}).get(mi) or sym)
                _col = getattr(self, "_pending_cat_color", {}).get(mi)
                if _col:
                    try:
                        _sym = _sym.clone()
                        _sym_set_color(_sym, self._layer, _col)
                    except Exception:
                        exc_note("_fill_cat_table @ ggis/ui/panels/symbology.py:4393")
                        pass
                btn = GgsSymbolCellButton(
                    _sym, self._cur_kind(), self._dark, self.tbl_cat,
                    tip=_tr("点击配置这个样式"))
                btn.clicked.connect(
                    lambda _c=False, row=disp: self._edit_class_symbol(row))
                self.tbl_cat.setCellWidget(disp, 1, btn)
                lab = QTableWidgetItem("" if v is None else str(v))
                self.tbl_cat.setItem(disp, 2, lab)
        finally:
            self.tbl_cat.blockSignals(False)
        self._sync_cat_others()

    def _on_cat_double(self, row, col):
        if int(col) != 1 or self._layer is None:
            return
        self._edit_class_symbol(int(row))

    def _on_grad_double(self, row, col):
        if int(col) != 0 or self._layer is None:
            return
        self._edit_grad_symbol(int(row))

    def _fallback_class_symbol(self, r, row):
        try:
            n = max(1, len(getattr(r, "entries", None)
                           or getattr(r, "symbols_", None) or []))
            cols = make_ramp(getattr(r, "ramp", "spectral"), n)
            i = int(row) % len(cols)
            return _default_sym(r.geometry_kind, int(row), fill=cols[i])
        except Exception:
            exc_note("_fallback_class_symbol @ ggis/ui/panels/symbology.py:4445")
            try:
                return _default_sym(r.geometry_kind, int(row))
            except Exception:
                exc_note("_fallback_class_symbol @ ggis/ui/panels/symbology.py:4448")
                return None

    def _warn_dialog_fail(self, err):
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.warn(self, _tr("无法打开样式配置窗口"),
                           _tr("原因：{0}").format(err))
        except Exception:
            exc_note("_warn_dialog_fail @ ggis/ui/panels/symbology.py:4462")
            pass

    def _edit_class_symbol(self, row):
        try:
            if self._layer is None:
                return
            disp = int(row)
            try:
                self.tbl_cat.selectRow(disp)
            except Exception:
                exc_note("_edit_class_symbol @ ggis/ui/panels/symbology.py:4486")
                pass
            r = get_renderer(self._layer)
            if not isinstance(r, GgsCategorizedRenderer):
                r = None
            n = max(0, self.tbl_cat.rowCount())
            mi = self._model_row("_cat_order",
                                 len(r.entries) if r is not None else n, disp)
            pend = getattr(self, "_pending_cat_sym", None)
            if pend is None:
                pend = self._pending_cat_sym = {}
            cur = pend.get(mi)
            value = None
            if cur is None:
                try:
                    value = self.tbl_cat.item(disp, 0).text()
                except Exception:
                    exc_note("_edit_class_symbol @ ggis/ui/panels/symbology.py:4504")
                    value = None
                btn = self.tbl_cat.cellWidget(disp, 1)
                try:
                    cur = btn.symbol() if btn is not None else None
                except Exception:
                    exc_note("_edit_class_symbol @ ggis/ui/panels/symbology.py:4509")
                    cur = None
            if cur is None and r is not None and 0 <= mi < len(r.entries):
                value, sym = r.entries[mi]
                cur = sym
            if cur is None:
                cur = (self._fallback_class_symbol(r, mi) if r is not None
                       else default_symbol(self._cur_kind(), 0))
            from ..dialogs.symbol import GgsSymbolDialog
            new = GgsSymbolDialog.edit(
                cur, kind=self._cur_kind(), dark=self._dark,
                title=_tr("分类符号：{0}").format(
                    "" if value is None else value),
                parent=self)
            if new is None:
                return
            pend[mi] = new
            if r is not None:
                self._fill_cat_table(r)
            else:
                btn = self.tbl_cat.cellWidget(disp, 1)
                if btn is not None:
                    btn.setSymbol(new, self._cur_kind(), self._dark)
            self._mark_dirty()
        except Exception as e:
            exc_note("_edit_class_symbol @ ggis/ui/panels/symbology.py:4535")
            self._warn_dialog_fail(e)

    def _fill_grad_table(self, r):
        bk, syms = self._grad_now(r)
        n = max(0, len(bk) - 1)
        order = self._grad_rows(r, n)
        pend = getattr(self, "_pending_grad_sym", {})
        self.tbl_grad.blockSignals(True)
        try:
            self.tbl_grad.setRowCount(len(order))
            for disp, mi in enumerate(order):
                _sym = pend.get(mi) or (syms[mi] if mi < len(syms) else None)
                color = getattr(self, "_pending_grad_color", {}).get(mi)
                if color and _sym is not None:
                    try:
                        _sym = _sym.clone()
                        _sym_set_color(_sym, self._layer, color)
                    except Exception:
                        exc_note("_fill_grad_table @ ggis/ui/panels/symbology.py:4559")
                        pass
                btn = GgsSymbolCellButton(
                    _sym, self._cur_kind(), self._dark, self.tbl_grad,
                    tip=_tr("点击配置这个样式"))
                btn.clicked.connect(
                    lambda _c=False, row=disp: self._edit_grad_symbol(row))
                self.tbl_grad.setCellWidget(disp, 0, btn)
                lo = bk[mi]
                hi = bk[mi + 1]
                it_lo = QTableWidgetItem("%.6g" % lo)
                it_hi = QTableWidgetItem("%.6g" % hi)
                it_lo.setTextAlignment(int(Qt.AlignmentFlag.AlignRight |
                                           Qt.AlignmentFlag.AlignVCenter))
                it_hi.setTextAlignment(int(Qt.AlignmentFlag.AlignRight |
                                           Qt.AlignmentFlag.AlignVCenter))
                self.tbl_grad.setItem(disp, 1, it_lo)
                self.tbl_grad.setItem(disp, 2, it_hi)
        finally:
            self.tbl_grad.blockSignals(False)
        self._sync_grad_buttons(r, n)

    def _on_grad_break(self, item):
        if self._loading or self._layer is None:
            return
        try:
            col = int(item.column())
        except Exception:
            exc_note("_on_grad_break @ ggis/ui/panels/symbology.py:4608")
            return
        if col not in (1, 2):
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsGraduatedRenderer):
            return
        _bk, _syms = self._grad_now(r)
        n = max(0, len(_bk) - 1)
        mi = self._grad_model_row(r, n, int(item.row()))
        bi = mi + (0 if col == 1 else 1)
        try:
            val = float(str(item.text()).strip())
        except Exception:
            exc_note("_on_grad_break @ ggis/ui/panels/symbology.py:4623")
            self._fill_grad_table(r)
            return
        if bi < 0 or bi >= len(_bk):
            self._fill_grad_table(r)
            return
        pend = getattr(self, "_pending_grad_break", None)
        if pend is None:
            pend = self._pending_grad_break = {}
        pend[int(bi)] = val
        self._mark_dirty()

    def _grad_cell_range(self, disp):
        out = []
        for col in (1, 2):
            try:
                out.append(float(self.tbl_grad.item(int(disp), col).text()))
            except Exception:
                exc_note("_grad_cell_range @ ggis/ui/panels/symbology.py:4641")
                out.append(None)
        return out[0], out[1]

    def _edit_grad_symbol(self, row):
        try:
            if self._layer is None:
                return
            disp = int(row)
            try:
                self.tbl_grad.selectRow(disp)
            except Exception:
                exc_note("_edit_grad_symbol @ ggis/ui/panels/symbology.py:4675")
                pass
            r = get_renderer(self._layer)
            if not isinstance(r, GgsGraduatedRenderer):
                r = None
            _bk, _all = self._grad_now(r) if r is not None else ([], [])
            syms = _all
            _nm = max(0, len(_bk) - 1)
            mi = self._grad_model_row(r, _nm, disp) if r is not None else disp
            pend = getattr(self, "_pending_grad_sym", None)
            if pend is None:
                pend = self._pending_grad_sym = {}
            cur = pend.get(mi)
            if cur is None:
                btn = self.tbl_grad.cellWidget(disp, 0)
                try:
                    cur = btn.symbol() if btn is not None else None
                except Exception:
                    exc_note("_edit_grad_symbol @ ggis/ui/panels/symbology.py:4696")
                    cur = None
            if cur is None and r is not None and 0 <= mi < len(syms):
                cur = syms[mi]
            if cur is None:
                cur = (self._fallback_class_symbol(r, mi) if r is not None
                       else default_symbol(self._cur_kind(), 0))
            title = _tr("分级符号")
            try:
                if r is not None:
                    lo, hi = _bk[mi], _bk[mi + 1]
                else:
                    lo, hi = self._grad_cell_range(disp)
                title = _tr("分级符号：{0} – {1}").format("%.6g" % lo,
                                                         "%.6g" % hi)
            except Exception:
                exc_note("_edit_grad_symbol @ ggis/ui/panels/symbology.py:4713")
                pass
            from ..dialogs.symbol import GgsSymbolDialog
            new = GgsSymbolDialog.edit(cur, kind=self._cur_kind(),
                                       dark=self._dark,
                                       title=title, parent=self)
            if new is None:
                return
            pend[mi] = new
            if r is not None:
                self._fill_grad_table(r)
            else:
                btn = self.tbl_grad.cellWidget(disp, 0)
                if btn is not None:
                    btn.setSymbol(new, self._cur_kind(), self._dark)
            self._mark_dirty()
        except Exception as e:
            exc_note("_edit_grad_symbol @ ggis/ui/panels/symbology.py:4731")
            self._warn_dialog_fail(e)

    def _commit(self):
        if self._layer is None:
            return
        try:
            from ...render.renderers import _bump_render_version
            _bump_render_version(self._layer)
        except Exception:
            exc_note("_commit @ ggis/ui/panels/symbology.py:4743")
            pass
        self.styleChanged.emit(self._layer)

    def _mark_dirty(self):
        try:
            self.btn_apply.setEnabled(True)
        except Exception:
            exc_note("_mark_dirty @ ggis/ui/panels/symbology.py:4752")
            pass

    def _on_apply(self):
        if self._layer is None:
            return
        if self._is_raster:
            if not self._ras_dirty:
                return
            try:
                rd.set_display(self._layer, self._collect_raster())
            except Exception:
                exc_note("_on_apply @ ggis/ui/panels/symbology.py:4766")
                pass
            self._ras_dirty = False
            self.btn_apply.setEnabled(False)
            self._commit()
            return
        want = getattr(self, "_pending_kind", None)
        if want:
            self._pending_kind = None
            keep = dict(getattr(self, "_pending_single", {}) or {})
            if want != "single":
                keep = {}
            try:
                self._switch_renderer(want)
            except Exception:
                exc_note("_on_apply @ ggis/ui/panels/symbology.py:4784")
                return
            self._pending_single = keep
        did = False
        r0 = get_renderer(self._layer)
        if getattr(self, "_grad_def_dirty", False):
            self._grad_def_dirty = False
            if isinstance(r0, GgsGraduatedRenderer):
                did = True
                r0.field = self.grad_field.currentData() or ""
                r0.mode = self.grad_mode.currentData() or "equal"
                r0.n_classes = int(self.grad_n.value())
                r0.ramp = self._grad_ramp_code()
                if r0.field:
                    from ..dialogs import busy as _busy
                    _busy.show_busy_delayed(
                        self.window(), _tr("重建分级"),
                        _tr("正在按字段重新计算断点…"))
                    try:
                        r0.rebuild(self._layer)
                    finally:
                        _busy.hide_busy()
                self._grad_order = None
        _grad_ovr_used = getattr(self, "_grad_ovr", None) is not None
        if _grad_ovr_used:
            r2 = get_renderer(self._layer)
            if isinstance(r2, GgsGraduatedRenderer):
                did = True
                try:
                    _bk, _sy = self._grad_ovr
                    r2.breaks = [float(v) for v in _bk]
                    _n_have = max(0, len(r2.breaks) - 1)
                    _syms = list(_sy)[:_n_have]
                    while len(_syms) < _n_have:
                        _syms.append(None)
                    r2.symbols_ = _syms
                    r2.n_classes = _n_have
                    r2.invalidate()
                    try:
                        self.grad_n.blockSignals(True)
                        self.grad_n.setValue(
                            max(2, min(int(MAX_CLASSES), int(_n_have))))
                    finally:
                        try:
                            self.grad_n.blockSignals(False)
                        except Exception:
                            exc_note("_on_apply @ ggis/ui/panels/symbology.py:4844")
                            pass
                except Exception:
                    exc_note("_on_apply @ ggis/ui/panels/symbology.py:4846")
                    pass
        self._grad_ovr = None
        self._grad_cnt_key = None
        self._grad_cnt = None
        if getattr(self, "_cat_def_dirty", False):
            self._cat_def_dirty = False
            if isinstance(r0, GgsCategorizedRenderer):
                did = True
                r0.field = self.cat_field.currentData() or ""
                if r0.field:
                    from ..dialogs import busy as _busy
                    _busy.show_busy_delayed(
                        self.window(), _tr("重建分类"),
                        _tr("正在按字段重新分类…"))
                    try:
                        r0.rebuild(self._layer)
                    finally:
                        _busy.hide_busy()
                self._cat_order = None
        if getattr(self, "_cat_ovr", None) is not None:
            r1 = get_renderer(self._layer)
            if isinstance(r1, GgsCategorizedRenderer):
                did = True
                try:
                    r1.entries = [tuple(e) for e in self._cat_ovr]
                except Exception:
                    exc_note("_on_apply @ ggis/ui/panels/symbology.py:4877")
                    pass
        self._cat_ovr = None
        pend = getattr(self, "_pending_single", None)
        if pend:
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsSingleSymbolRenderer):
                sym = r.symbol
                if "fill" in pend:
                    sym.fill = QColor(pend["fill"])
                if "stroke" in pend:
                    sym.stroke = QColor(pend["stroke"])
                if "size" in pend:
                    sym.size = float(pend["size"])
                if "width" in pend:
                    sym.width = float(pend["width"])
                if "opacity" in pend:
                    sym.opacity = float(pend["opacity"])
                if "fill_alpha" in pend:
                    sym.fill_alpha = float(pend["fill_alpha"])
                if "line_style" in pend:
                    sym.line_style = str(pend["line_style"])
                if "dash_custom" in pend:
                    sym.dash_custom = tuple(pend["dash_custom"] or ())
                if "cap" in pend:
                    sym.cap = str(pend["cap"])
                if "join" in pend:
                    sym.join = str(pend["join"])
                if "fill_style" in pend:
                    sym.fill_style = str(pend["fill_style"])
                if "fill_spacing" in pend:
                    sym.fill_spacing = float(pend["fill_spacing"])
                if "fill_width" in pend:
                    sym.fill_width = float(pend["fill_width"])
            self._pending_single = {}
        pall = getattr(self, "_pending_all", None)
        if pall:
            self._pending_all = {}
            try:
                r = get_renderer(self._layer)
            except Exception:
                exc_note("_on_apply @ ggis/ui/panels/symbology.py:4934")
                r = None
            if r is not None and not isinstance(
                    r, GgsSingleSymbolRenderer):
                did = True
                self._apply_item_to_all_symbols(r, pall)
        for row, sym in sorted(getattr(self, "_pending_cat_sym", {}).items()):
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsCategorizedRenderer) and 0 <= row < len(r.entries):
                try:
                    v = r.entries[row][0]
                    r.entries[row] = (v, sym)
                    r.invalidate()
                except Exception:
                    exc_note("_on_apply @ ggis/ui/panels/symbology.py:4952")
                    pass
        for row, c in sorted(getattr(self, "_pending_cat_color", {}).items()):
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsCategorizedRenderer) and 0 <= row < len(r.entries):
                _sym_set_color(r.entries[row][1], self._layer, c)
                r.invalidate()
        oc = getattr(self, "_pending_others", None)
        if oc is not None:
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsCategorizedRenderer):
                if r.others_symbol is None:
                    r.others_symbol = make_symbol(r.geometry_kind, 0, fill=oc)
                else:
                    _sym_set_color(r.others_symbol, self._layer, oc)
                r.invalidate()
        ov = getattr(self, "_pending_others_show", None)
        if ov is not None:
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsCategorizedRenderer):
                r.others_visible = bool(ov)
                r.invalidate()
        pend_b = getattr(self, "_pending_grad_break", None)
        if pend_b:
            rb = get_renderer(self._layer)
            if isinstance(rb, GgsGraduatedRenderer) and len(rb.breaks) >= 2:
                new = [float(x) for x in rb.breaks]
                for bi, val in sorted(pend_b.items()):
                    try:
                        i = int(bi)
                    except Exception:
                        exc_note("_on_apply @ ggis/ui/panels/symbology.py:4998")
                        continue
                    if 0 <= i < len(new):
                        new[i] = float(val)
                bad = False
                for i in range(len(new) - 1):
                    if not (new[i] < new[i + 1]):
                        bad = True
                        break
                if bad:
                    try:
                        from ggis.common.base.dialog import GgsMsgBox
                        GgsMsgBox.warn(
                            self, _tr("分级区间无效"),
                            _tr("上下限必须严格递增（每一档的下限小于上限，"
                                "且相邻两档的断点不能相等）；已忽略这次修改。"))
                    except Exception:
                        exc_note("_on_apply @ ggis/ui/panels/symbology.py:5017")
                        pass
                else:
                    did = True
                    rb.breaks = new
                    rb.invalidate()
        self._pending_grad_break = {}
        for row, sym in sorted(getattr(self, "_pending_grad_sym", {}).items()):
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsGraduatedRenderer):
                try:
                    n_have = max(0, len(r.breaks) - 1)
                    while len(r.symbols_) < n_have:
                        r.symbols_.append(None)
                    if 0 <= int(row) < len(r.symbols_):
                        r.symbols_[int(row)] = sym
                        r.invalidate()
                except Exception:
                    exc_note("_on_apply @ ggis/ui/panels/symbology.py:5038")
                    pass
        for row, c in sorted(getattr(self, "_pending_grad_color", {}).items()):
            did = True
            r = get_renderer(self._layer)
            if isinstance(r, GgsGraduatedRenderer):
                syms = r.symbols_
                if 0 <= row < len(syms):
                    _sym_set_color(syms[row], self._layer, c)
                    r.invalidate()
        self._pending_cat_color = {}
        self._pending_cat_sym = {}
        self._pending_grad_sym = {}
        self._pending_others = None
        self._pending_others_show = None
        self._pending_grad_color = {}
        self.btn_apply.setEnabled(False)
        if pend_b or _grad_ovr_used:
            try:
                self._fill_tables_for(get_renderer(self._layer))
            except Exception:
                exc_note("_on_apply @ ggis/ui/panels/symbology.py:5061")
                pass
        if did:
            self._commit()

    def _edit_single(self, attr, value):
        if self._loading or self._layer is None:
            return
        if not hasattr(self, "_pending_single"):
            self._pending_single = {}
        self._pending_single[attr] = value
        self._mark_dirty()
        self._preview_refresh()

    def _on_kind_changed(self, idx):
        self.stack.setCurrentIndex(idx)
        self._sync_bottom_row()
        self._refresh_count_label()
        if self._loading or self._layer is None:
            return
        want = str(self.cmb_kind.currentData() or "")
        cur_t = str(getattr(get_renderer(self._layer), "type_name", "") or "")
        if want == cur_t:
            self._pending_kind = None
            self._fill_tables_for(get_renderer(self._layer))
            return
        self._pending_kind = want
        self._mark_dirty()
        self._fill_tables_for(self._make_renderer(want))

    def _ramp_items(self, n=32):
        try:
            from ...render.renderers import RAMP_NAMES, make_ramp
            from ggis.core.style.style_library import ramp_title
            from ggis.core.style import user_ramps
            items = [(nm, _tr(ramp_title(nm)), make_ramp(nm, n))
                     for nm in RAMP_NAMES]
            for code, name, _stops in user_ramps.entries():
                items.append((code, name, user_ramps.hex_stops(code, n)))
            return items
        except Exception:
            exc_note("_ramp_items @ ggis/ui/panels/symbology.py:5134")
            return []

    def _raster_ramp_items(self, n=32):
        try:
            from ggis.core.style import user_ramps
            items = [(code, _tr(label), rd.ramp_hex_stops(code, n))
                     for code, label, _pts in rd.RAMPS]
            for code, name, _stops in user_ramps.entries():
                items.append((code, name, user_ramps.hex_stops(code, n)))
            return items
        except Exception:
            exc_note("_raster_ramp_items @ ggis/ui/panels/symbology.py:5155")
            return []

    def _cat_count(self):
        try:
            if self._layer is None:
                return 0
            kind = str(self.cmb_kind.currentData() or "")
            if kind != "categorized":
                return 0
            tbl = getattr(self, "tbl_cat", None)
            if tbl is not None:
                return tbl.rowCount()
        except Exception:
            exc_note("_cat_count @ ggis/ui/panels/symbology.py:5175")
            pass
        return 0

    def _sync_cat_others(self):
        try:
            has_miss = bool(self._cat_missing())
        except Exception:
            exc_note("_sync_cat_others @ ggis/ui/panels/symbology.py:5195")
            has_miss = False
        for _w in (getattr(self, "btn_cat_add", None),
                   getattr(self, "btn_cat_add_all", None)):
            if _w is None:
                continue
            try:
                _w.setEnabled(has_miss)
            except Exception:
                exc_note("_sync_cat_others @ ggis/ui/panels/symbology.py:5203")
                pass
        self._refresh_count_label()

    def _refresh_count_label(self):
        lbl = getattr(self, "lbl_cat_count", None)
        if lbl is None:
            return
        try:
            kind = str(self.cmb_kind.currentData() or "")
        except Exception:
            exc_note("_refresh_count_label @ ggis/ui/panels/symbology.py:5219")
            kind = ""
        if kind != "categorized" or self._layer is None:
            lbl.setText("")
            lbl.setVisible(False)
            return
        n = self._cat_count()
        lbl.setText(_tr("共 {0} 个分类值").format(n))
        lbl.setVisible(True)

    def _on_others_show(self, checked):
        if self._loading:
            return
        self._pending_others_show = bool(checked)
        row = getattr(self, "cat_others", None)
        if row is not None:
            row.setVisible(bool(checked))
        self._mark_dirty()

    def _grad_now(self, r):
        ovr = getattr(self, "_grad_ovr", None)
        if ovr is not None:
            try:
                return list(ovr[0]), list(ovr[1])
            except Exception:
                exc_note("_grad_now @ ggis/ui/panels/symbology.py:5261")
                pass
        if r is None:
            return [], []
        return (list(getattr(r, "breaks", None) or []),
                self._grad_symbols(r))

    def _grad_counts(self, r, n):
        arr = self._grad_cache_arr(r)
        if arr is None or not n:
            return []
        try:
            key = (id(self._layer), str(getattr(r, "field", "") or ""),
                   tuple(float(v) for v in (r.breaks or [])), int(n))
        except Exception:
            exc_note("_grad_counts @ ggis/ui/panels/symbology.py:5285")
            key = None
        if (key is not None and key == getattr(self, "_grad_cnt_key", None)
                and getattr(self, "_grad_cnt", None) is not None):
            return list(self._grad_cnt)
        out = []
        try:
            import numpy as np
            b = np.bincount(np.asarray(arr).astype(np.int64, copy=False),
                            minlength=int(n) + 2)
            out = [int(b[i + 1]) for i in range(int(n))]
        except Exception:
            exc_note("_grad_counts @ ggis/ui/panels/symbology.py:5296")
            out = []
        self._grad_cnt_key = key
        self._grad_cnt = list(out)
        return out

    def _grad_cache_arr(self, r):
        if r is None:
            return None
        try:
            ck = getattr(r, "_cache_key", None)
            arr = getattr(r, "_cache", None)
            if ck is None or arr is None:
                return None
            want = (id(self._layer), str(getattr(r, "field", "") or ""),
                    tuple(float(v) for v in (r.breaks or [])),
                    bool(getattr(r, "others_symbol", None)))
            got = (ck[0], str(ck[2]), tuple(float(v) for v in ck[3]),
                   bool(ck[4]))
            return arr if got == want else None
        except Exception:
            exc_note("_grad_cache_arr @ ggis/ui/panels/symbology.py:5324")
            return None

    def _grad_rows(self, r, n):
        order = self._view_order("_grad_order", n)
        if getattr(self, "_grad_ovr", None) is not None:
            return list(order)
        cnt = self._grad_counts(r, n)
        if not cnt or len(cnt) != int(n):
            return list(order)
        keep = [mi for mi in order if 0 <= mi < int(n) and cnt[mi] > 0]
        return keep or list(order)

    def _grad_model_row(self, r, n, disp):
        try:
            rows = self._grad_rows(r, n)
            d = int(disp)
            if 0 <= d < len(rows):
                return int(rows[d])
        except Exception:
            exc_note("_grad_model_row @ ggis/ui/panels/symbology.py:5354")
            pass
        return int(disp)

    def _sync_grad_buttons(self, r, n):
        for _w, _on in ((getattr(self, "btn_grad_add", None), int(n) >= 1),
                        (getattr(self, "btn_grad_del", None), int(n) > 1)):
            if _w is None:
                continue
            try:
                _w.setEnabled(bool(_on))
            except Exception:
                exc_note("_sync_grad_buttons @ ggis/ui/panels/symbology.py:5366")
                pass

    def _grad_set_ovr(self, breaks, syms):
        self._grad_ovr = (list(breaks), list(syms))
        self._pending_grad_sym = {}
        self._pending_grad_color = {}
        self._pending_grad_break = {}
        self._grad_order = None
        self._grad_sort = None
        self._grad_cnt_key = None
        self._grad_cnt = None
        self._mark_dirty()

    def _on_grad_add_class(self, *_a):
        if self._layer is None or self._loading:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsGraduatedRenderer):
            return
        bk, syms = self._grad_now(r)
        n = max(0, len(bk) - 1)
        if n < 1:
            return
        row = int(self.tbl_grad.currentRow())
        mi = (self._grad_model_row(r, n, row) if row >= 0 else -1)
        if not (0 <= mi < n):
            cnt = self._grad_counts(r, n)
            mi = (max(range(n), key=lambda i: cnt[i])
                  if (cnt and len(cnt) == n) else n - 1)
        lo, hi = float(bk[mi]), float(bk[mi + 1])
        cut = lo + (hi - lo) / 2.0
        if not (lo < cut < hi):
            return
        bk.insert(mi + 1, cut)
        sym = syms[mi] if 0 <= mi < len(syms) else None
        try:
            syms.insert(mi + 1, sym.clone() if sym is not None else None)
        except Exception:
            exc_note("_on_grad_add_class @ ggis/ui/panels/symbology.py:5421")
            syms.insert(mi + 1, sym)
        self._grad_set_ovr(bk, syms)
        self._fill_grad_table(r)

    def _on_grad_del_class(self, *_a):
        if self._layer is None or self._loading:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsGraduatedRenderer):
            return
        bk, syms = self._grad_now(r)
        n = max(0, len(bk) - 1)
        if n < 2:
            return
        row = int(self.tbl_grad.currentRow())
        if row < 0:
            return
        mi = self._grad_model_row(r, n, row)
        if not (0 <= mi < n):
            return
        bk = list(bk)
        syms = list(syms)
        if mi < n - 1:
            del bk[mi + 1]
        else:
            del bk[mi]
        if 0 <= mi < len(syms):
            del syms[mi]
        self._grad_set_ovr(bk, syms)
        self._fill_grad_table(r)

    def _on_grad_menu(self, pos):
        try:
            from PySide6.QtWidgets import QMenu
        except Exception:
            exc_note("_on_grad_menu @ ggis/ui/panels/symbology.py:5467")
            return
        row = -1
        try:
            idx = self.tbl_grad.indexAt(pos)
            row = int(idx.row()) if idx.isValid() else -1
        except Exception:
            exc_note("_on_grad_menu @ ggis/ui/panels/symbology.py:5473")
            row = -1
        if row >= 0:
            try:
                self.tbl_grad.selectRow(row)
            except Exception:
                exc_note("_on_grad_menu @ ggis/ui/panels/symbology.py:5478")
                pass
        try:
            _r = get_renderer(self._layer)
            n = max(0, len(self._grad_now(_r)[0]) - 1)
        except Exception:
            exc_note("_on_grad_menu @ ggis/ui/panels/symbology.py:5485")
            n = max(0, int(self.tbl_grad.rowCount()))
        try:
            m = QMenu(self)
            a_add = m.addAction(_tr("新建分级"))
            a_add.triggered.connect(lambda *_: self._on_grad_add_class())
            m.addSeparator()
            a_edit = m.addAction(_tr("编辑样式…"))
            a_edit.triggered.connect(
                lambda *_, _r=row: self._edit_grad_symbol(_r))
            a_edit.setEnabled(row >= 0)
            a_del = m.addAction(_tr("删除分级"))
            a_del.triggered.connect(lambda *_: self._on_grad_del_class())
            a_del.setEnabled(row >= 0 and n > 1)
            m.exec(self.tbl_grad.viewport().mapToGlobal(pos))
        except Exception:
            exc_note("_on_grad_menu @ ggis/ui/panels/symbology.py:5500")
            pass

    def _grad_symbols(self, r):
        n = max(0, len(r.breaks) - 1)
        syms = list(getattr(r, "symbols_", None) or [])
        if n and len(syms) < n:
            colors = make_ramp(r.ramp, n)
            syms = [_default_sym(r.geometry_kind, i, fill=colors[i])
                    for i in range(n)]
        return syms

    def _toggle_sort(self, key, hh, col, n, keyfunc):
        st = getattr(self, key, None)
        try:
            desc = (isinstance(st, tuple) and int(st[0]) == int(col)
                    and not bool(st[1]))
        except Exception:
            exc_note("_toggle_sort @ ggis/ui/panels/symbology.py:5537")
            desc = False
        order = sorted(range(int(n)), key=keyfunc, reverse=bool(desc))
        setattr(self, key, (int(col), bool(desc)))
        try:
            hh.setSortIndicatorShown(True)
            hh.setSortIndicator(int(col),
                                Qt.SortOrder.DescendingOrder if desc
                                else Qt.SortOrder.AscendingOrder)
        except Exception:
            exc_note("_toggle_sort @ ggis/ui/panels/symbology.py:5546")
            pass
        return order

    def _on_grad_sort(self, col):
        if self._layer is None or int(col) not in (1, 2):
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsGraduatedRenderer):
            return
        _bk, _syms = self._grad_now(r)
        n = max(0, len(_bk) - 1)
        if n <= 1:
            return
        self._grad_order = self._toggle_sort(
            "_grad_sort", self.tbl_grad.horizontalHeader(), col, n,
            lambda i: float(_bk[i]))
        self._fill_grad_table(r)

    def _on_grad_ramp(self, _code):
        if self._loading or self._layer is None:
            return
        self._on_grad_change()

    def _apply_ramp_to(self, kind, preview=None):
        if self._layer is None or kind != "categorized":
            return
        fld = getattr(self, "cat_ramp", None)
        if fld is None:
            return
        try:
            from ...render.renderers import make_ramp
            tbl = self.tbl_cat
            n = max(1, int(tbl.rowCount()))
            cols = make_ramp(fld.ramp(), n)
        except Exception:
            exc_note("_apply_ramp_to @ ggis/ui/panels/symbology.py:5601")
            return
        if not hasattr(self, "_pending_cat_color"):
            self._pending_cat_color = {}
        for i, c in enumerate(cols):
            self._pending_cat_color[i] = c
        self._mark_dirty()
        self._fill_tables_for(preview if preview is not None
                              else self._make_renderer(kind))

    def _grad_ramp_code(self):
        try:
            f = getattr(self, "grad_ramp", None)
            if f is None:
                return "spectral"
            if hasattr(f, "ramp"):
                return str(f.ramp() or "spectral")
            return str(f.currentData() or "spectral")
        except Exception:
            exc_note("_grad_ramp_code @ ggis/ui/panels/symbology.py:5622")
            return "spectral"

    def _make_renderer(self, want):
        lyr = self._layer
        if lyr is None:
            return None
        kind = lyr.base_kind()
        try:
            if want == "categorized":
                field = self.cat_field.currentData() or ""
                if not field:
                    fields = fields_from_layer(lyr)
                    field = fields[0].name if fields else ""
                r = GgsCategorizedRenderer(field, geometry_kind=kind)
                if field:
                    r.rebuild(lyr)
            elif want == "graduated":
                field = self.grad_field.currentData() or ""
                if not field:
                    fields = [f for f in fields_from_layer(lyr)
                              if f.is_numeric()]
                    field = fields[0].name if fields else ""
                r = GgsGraduatedRenderer(
                    field, self.grad_mode.currentData() or "equal",
                    self.grad_n.value(), self._grad_ramp_code(),
                    geometry_kind=kind)
                if field:
                    r.rebuild(lyr)
            else:
                old = get_renderer(lyr)
                sym = None
                try:
                    syms = old.symbols()
                    sym = syms[0] if syms else None
                except Exception:
                    exc_note("_make_renderer @ ggis/ui/panels/symbology.py:5666")
                    sym = None
                r = GgsSingleSymbolRenderer(
                    sym or default_symbol(kind, 0), kind)
        except Exception:
            exc_note("_make_renderer @ ggis/ui/panels/symbology.py:5670")
            return None
        return r

    def _fill_tables_for(self, r):
        if r is None:
            return
        self._loading = True
        try:
            if isinstance(r, GgsCategorizedRenderer):
                self._fill_cat_table(r)
            elif isinstance(r, GgsGraduatedRenderer):
                self._fill_grad_table(r)
        except Exception:
            exc_note("_fill_tables_for @ ggis/ui/panels/symbology.py:5688")
            pass
        finally:
            self._loading = False

    def _switch_renderer(self, want):
        r = self._make_renderer(want)
        if r is None:
            return
        set_renderer(self._layer, r)
        self._load(self._layer)
        self._commit()

    def _on_cat_field(self, _i):
        if self._loading or self._layer is None:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsCategorizedRenderer):
            return
        self._cat_def_dirty = True
        self._pending_cat_sym = {}
        self._pending_cat_color = {}
        self._cat_order = None
        self._cat_ovr = None
        self._cat_miss_key = None
        preview = self._make_renderer("categorized")
        if preview is not None:
            self._fill_tables_for(preview)
        self._apply_ramp_to("categorized", preview)
        self._mark_dirty()

    def _cat_entries_now(self):
        ovr = getattr(self, "_cat_ovr", None)
        if ovr is not None:
            return [tuple(e) for e in ovr]
        try:
            r = get_renderer(self._layer)
            if isinstance(r, GgsCategorizedRenderer):
                return [tuple(e) for e in r.entries]
        except Exception:
            exc_note("_cat_entries_now @ ggis/ui/panels/symbology.py:5738")
            pass
        return []

    def _cat_all_values(self):
        try:
            pv = self._make_renderer("categorized")
            if pv is not None:
                return [e[0] for e in (getattr(pv, "entries", []) or [])]
        except Exception:
            exc_note("_cat_all_values @ ggis/ui/panels/symbology.py:5749")
            pass
        return []

    def _cat_missing(self):
        key = (id(self._layer), str(self.cat_field.currentData() or ""))
        if getattr(self, "_cat_miss_key", None) != key:
            have = {str(e[0]) for e in self._cat_entries_now()}
            self._cat_miss = [v for v in self._cat_all_values()
                              if str(v) not in have]
            self._cat_miss_key = key
        return list(getattr(self, "_cat_miss", []) or [])

    def _cat_apply_ovr(self, ents):
        self._cat_ovr = [tuple(e) for e in ents]
        self._cat_def_dirty = True
        self._pending_cat_sym = {}
        self._pending_cat_color = {}
        self._cat_order = None
        self._cat_miss_key = None
        try:
            self._fill_cat_table(None)
        except Exception:
            exc_note("_cat_apply_ovr @ ggis/ui/panels/symbology.py:5778")
            pass
        self._mark_dirty()
        self._sync_cat_others()

    def _cat_new_symbol(self, idx, n):
        sym = None
        try:
            r = get_renderer(self._layer)
            if isinstance(r, GgsCategorizedRenderer):
                sym = r.others_symbol
                if sym is None and r.entries:
                    sym = r.entries[-1][1]
        except Exception:
            exc_note("_cat_new_symbol @ ggis/ui/panels/symbology.py:5796")
            sym = None
        try:
            sym = sym.clone() if sym is not None else None
        except Exception:
            exc_note("_cat_new_symbol @ ggis/ui/panels/symbology.py:5800")
            sym = None
        if sym is None:
            try:
                from ...render.renderers import default_symbol
                sym = default_symbol(self._layer.base_kind(), idx)
            except Exception:
                exc_note("_cat_new_symbol @ ggis/ui/panels/symbology.py:5806")
                return None
        try:
            from ...render.renderers import make_ramp
            cols = make_ramp(self.cat_ramp.ramp(), max(1, int(n)))
            c = cols[min(max(0, int(idx)), len(cols) - 1)]
            _sym_set_color(sym, self._layer, c)
        except Exception:
            exc_note("_cat_new_symbol @ ggis/ui/panels/symbology.py:5813")
            pass
        return sym

    def _on_cat_add_value(self):
        if self._layer is None or self._loading:
            return
        miss = self._cat_missing()
        if not miss:
            return
        pick = None
        try:
            from ggis.common.base.dialog import GgsInputDialog
            items = [str(v) for v in miss]
            res = GgsInputDialog.getItem(
                self, _tr("新增值"), _tr("选择要添加的值"), items, 0, False)
            if isinstance(res, tuple):
                txt = res[0] if res else ""
                ok = bool(res[1]) if len(res) > 1 else bool(txt)
            else:
                txt, ok = res, bool(res)
            if ok and txt:
                pick = miss[items.index(str(txt))]
        except Exception:
            exc_note("_on_cat_add_value @ ggis/ui/panels/symbology.py:5842")
            pick = None
        if pick is None:
            return
        ents = self._cat_entries_now()
        sym = self._cat_new_symbol(len(ents), len(ents) + 1)
        ents.append((pick, sym))
        self._cat_apply_ovr(ents)

    def _on_cat_del_value(self):
        if self._layer is None or self._loading:
            return
        ents = self._cat_entries_now()
        if not ents:
            return
        row = int(self.tbl_cat.currentRow())
        if row < 0:
            return
        mi = self._model_row("_cat_order", len(ents), row)
        if not (0 <= mi < len(ents)):
            return
        ents.pop(mi)
        self._cat_apply_ovr(ents)

    def _on_cat_add_all(self):
        if self._layer is None or self._loading:
            return
        self._cat_ovr = None
        self._cat_miss_key = None
        self._on_cat_rebuild()

    def _on_cat_menu(self, pos):
        try:
            from PySide6.QtWidgets import QMenu
        except Exception:
            exc_note("_on_cat_menu @ ggis/ui/panels/symbology.py:5888")
            return
        row = -1
        try:
            idx = self.tbl_cat.indexAt(pos)
            row = int(idx.row()) if idx.isValid() else -1
        except Exception:
            exc_note("_on_cat_menu @ ggis/ui/panels/symbology.py:5894")
            row = -1
        if row >= 0:
            try:
                self.tbl_cat.selectRow(row)
            except Exception:
                exc_note("_on_cat_menu @ ggis/ui/panels/symbology.py:5899")
                pass
        has_miss = bool(self._cat_missing())
        try:
            m = QMenu(self)
            a_pick = m.addAction(_tr("新增值…"))
            a_pick.triggered.connect(lambda *_: self._on_cat_add_value())
            a_pick.setEnabled(has_miss)
            a_all = m.addAction(_tr("新增所有值"))
            a_all.triggered.connect(lambda *_: self._on_cat_add_all())
            a_all.setEnabled(has_miss)
            m.addSeparator()
            a_del = m.addAction(_tr("删除值"))
            a_del.triggered.connect(lambda *_: self._on_cat_del_value())
            a_del.setEnabled(row >= 0)
            m.exec(self.tbl_cat.viewport().mapToGlobal(pos))
        except Exception:
            exc_note("_on_cat_menu @ ggis/ui/panels/symbology.py:5915")
            pass

    def _on_cat_rebuild(self):
        self._on_cat_field(0)

    def _on_cat_sort(self, col):
        if self._layer is None or int(col) not in (0, 2):
            return
        r = get_renderer(self._layer)
        ents = self._cat_entries_now()
        if not isinstance(r, GgsCategorizedRenderer) or len(ents) <= 1:
            return
        n = len(ents)
        self._cat_order = self._toggle_sort(
            "_cat_sort", self.tbl_cat.horizontalHeader(), col, n,
            lambda i: _value_sort_key(ents[i][0]))
        self._fill_cat_table(r)

    def _on_cat_row_color(self, row, color):
        if self._layer is None:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsCategorizedRenderer):
            return
        row = self._model_row("_cat_order", len(r.entries), row)
        if 0 <= row < len(r.entries):
            if not hasattr(self, "_pending_cat_color"):
                self._pending_cat_color = {}
            self._pending_cat_color[row] = color
            self._mark_dirty()

    def _on_cat_color(self, row, col):
        if col > 1:
            return
        w = self.tbl_cat.cellWidget(row, 1)
        if isinstance(w, GgsColorButton):
            w._pick()

    def _on_cat_label(self, item):
        if self._loading or self._layer is None or item.column() != 2:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsCategorizedRenderer):
            return
        _ = item.text()

    def _on_others_color(self, color):
        if self._loading or self._layer is None:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsCategorizedRenderer):
            return
        self._pending_others = color
        self._mark_dirty()

    def _on_grad_change(self, *_):
        if self._loading or self._layer is None:
            return
        try:
            self._warn_many_classes(int(self.grad_n.value()))
        except Exception:
            exc_note("_on_grad_change @ ggis/ui/panels/symbology.py:5991")
            pass
        r = get_renderer(self._layer)
        if not isinstance(r, GgsGraduatedRenderer):
            return
        self._grad_def_dirty = True
        self._pending_grad_sym = {}
        self._pending_grad_color = {}
        self._grad_ovr = None
        self._grad_cnt_key = None
        self._grad_cnt = None
        self._grad_order = None
        preview = self._make_renderer("graduated")
        if preview is not None:
            self._fill_tables_for(preview)
        self._mark_dirty()

    def _on_grad_color(self, row, col):
        if col != 0 or self._layer is None:
            return
        r = get_renderer(self._layer)
        if not isinstance(r, GgsGraduatedRenderer):
            return
        syms = r.symbols_
        if not (0 <= row < len(syms)):
            return
        from ..dialogs.color import popup_color
        popup_color(
            self, QColor(_sym_color(syms[row], self._layer)),
            lambda c, _r=row: self._apply_grad_color(_r, c))

    def _apply_grad_color(self, row, c):
        c = QColor(c)
        if not c.isValid():
            return
        try:
            _r = get_renderer(self._layer)
            _n = max(0, len(self._grad_now(_r)[0]) - 1)
        except Exception:
            exc_note("_apply_grad_color @ ggis/ui/panels/symbology.py:6051")
            _r, _n = None, 0
        row = self._grad_model_row(_r, _n, row)
        if not hasattr(self, "_pending_grad_color"):
            self._pending_grad_color = {}
        self._pending_grad_color[row] = c
        self._mark_dirty()


class GgsSymApply(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymApply")
class GgsSymCount(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymCount")
class GgsSymRasAnno(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymRasAnno")
class GgsSymRasBgChk(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymRasBgChk")
class GgsSymRasBgValue(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymRasBgValue")
class GgsSymRasClassN(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymRasClassN")
class GgsSymRasPalReset(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymRasPalReset")
class GgsSymRasValue(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymRasValue")



from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QMenu
from ggis.common.widgets.buttons import SmallDropButton
from ggis.core.app import i18n
_tr = i18n.tr


class GgsSymbolCellButton(QToolButton):

    THUMB = QSize(84, 28)
    SIZE = QSize(88, 32)

    def __init__(self, sym, kind="polygon", dark=True, parent=None, tip=""):
        super().__init__(parent)
        self.setObjectName("GgsSymbolCellButton")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._kind = str(kind or "polygon")
        self._dark = bool(dark)
        self._pm = None
        self.setToolTip(str(tip or "") or _tr("点击配置这个样式"))
        self.setSymbol(sym, self._kind, self._dark)

    def setSymbol(self, sym, kind=None, dark=None):
        if kind is not None:
            self._kind = str(kind or "polygon")
        if dark is not None:
            self._dark = bool(dark)
        self._sym = sym
        if sym is None:
            self._pm = None
            self.update()
            return
        try:
            from ggis.common.styling.symbol_sample import sample_pixmap
            self._pm = sample_pixmap(sym, self._kind, self.THUMB,
                                     self._dark, border=False, fill=True)
        except Exception:
            exc_note("setSymbol @ ggis/common/widgets/buttons.py:638")
            self._pm = None
        self.update()

    def symbol(self):
        return getattr(self, "_sym", None)

    def sizeHint(self):
        return self.SIZE

    def minimumSizeHint(self):
        return self.SIZE

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            pm = getattr(self, "_pm", None)
            if pm is None or pm.isNull():
                return
            if not self.isEnabled():
                p.setOpacity(0.35)
            elif self.isDown():
                p.setOpacity(0.70)
            elif self.underMouse():
                p.setOpacity(0.85)
            try:
                dpr = float(pm.devicePixelRatio() or 1.0) or 1.0
            except Exception:
                exc_note("paintEvent @ ggis/common/widgets/buttons.py:685")
                dpr = 1.0
            lw = int(round(pm.width() / dpr))
            lh = int(round(pm.height() / dpr))
            r = self.rect()
            x = r.x() + (r.width() - lw) // 2
            y = r.y() + (r.height() - lh) // 2
            p.drawPixmap(x, y, lw, lh, pm)
        except Exception:
            exc_note("paintEvent @ ggis/common/widgets/symbol_preview.py:594")
            pass
        finally:
            p.end()
class GgsStyleImportButton(SmallDropButton):

    pickFromLibrary = Signal()
    pickFromLayer = Signal(object)

    ICON = 16
    HEIGHT = 28

    def __init__(self, parent=None, tip="", layer_source=None):
        super().__init__(parent)
        self.setObjectName("GgsImportStyleBtn")
        from ggis.ui.framework import ribbon as _ribbon
        self._layer_source = layer_source
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setText(_tr("导入样式"))
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setProperty("dropSmall", True)
        try:
            from ggis.common.styling import icons as _icons
            _icons.bind(self, "style_library", size=self.ICON)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/symbol_preview.py:752")
            pass
        try:
            _ic = int(getattr(_ribbon, "SMALL_ICON", 0) or self.ICON)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/symbol_preview.py:762")
            _ic = self.ICON
        self.setIconSize(QSize(_ic, _ic))
        try:
            _w = (self.fontMetrics().horizontalAdvance(self.text())
                  + _ic + 10 + 9)
            self.setMinimumWidth(max(int(getattr(_ribbon, "SMALL_MIN_W", 64)), _w))
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/symbol_preview.py:773")
            pass
        self.setToolTip(str(tip or "") or _tr("导入样式"))
        m = QMenu(self)
        act = m.addAction(_tr("从样式库选择"))
        act.triggered.connect(self.pickFromLibrary.emit)
        self._sub = m.addMenu(_tr("从图层应用"))
        self._sub.aboutToShow.connect(self._fill_layers)
        self.setMenu(m)

    def set_layer_source(self, fn):
        self._layer_source = fn

    def _fill_layers(self):
        self._sub.clear()
        rows = []
        try:
            if callable(self._layer_source):
                rows = list(self._layer_source() or [])
        except Exception:
            exc_note("_fill_layers @ ggis/common/widgets/symbol_preview.py:794")
            rows = []
        for name, lyr in rows:
            act = self._sub.addAction(str(name or ""))
            act.triggered.connect(
                lambda _checked=False, _l=lyr: self.pickFromLayer.emit(_l))
        if not rows:
            act = self._sub.addAction(_tr("没有可导入的图层"))
            act.setEnabled(False)
