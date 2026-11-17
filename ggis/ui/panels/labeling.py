# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QFormLayout, QFrame, QGroupBox, QHBoxLayout,
                               QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from ggis.core.app import i18n
from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.widgets.inputs import ggs_combo_value, ggs_font_combo, ggs_font_select, relax_wide_inputs
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.widgets.inputs import GgsColorField
from ggis.ui.dialogs.symbol_preview import GgsSymbolPreview
from ggis.ui.framework.docks import GgsDockBody
from ggis.common.widgets.separators import GgsSepH
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_PLACEMENTS = [
    ("自动", "auto"), ("右侧", "right"), ("上方", "top"),
    ("下方", "bottom"), ("左侧", "left"), ("居中", "center"),
]

_PRESET_FIELDS = ("font_size", "bold", "italic", "color", "halo_color",
                  "halo_width", "buffer", "font_family")

_PRESET_SIZE_FIELDS = ("halo_width", "buffer")

_UNIT_ALIGN_KEYS = frozenset(("halo_width", "buffer", "min_size_px",
                              "repeat_px", "unit"))

_SIZE_SPIN_PX = {"halo": (8.0, 0.2), "buffer": (40.0, 1.0),
                 "repeat": (500.0, 5.0), "minsize": (2000.0, 10.0)}


def _apply_unit_to_spin(sp, unit, px_max, px_step):
    from ggis.core.crs.units import from_px
    u = str(unit or "pt")
    sp.setSuffix(" " + u)
    sp.setDecimals(3 if u == "in" else 2)
    sp.setRange(0.0, max(1e-3, float(from_px(px_max, u))))
    sp.setSingleStep(max(1e-4, float(from_px(px_step, u))))

_SAMPLE = "示例文字 Aa 123"

def _default_label_font_family():
    try:
        return QFont("Microsoft YaHei").family() or "微软雅黑"
    except Exception:
        _log.exception("silent exception in _default_label_font_family")
        return "微软雅黑"


class _LabelPreview(GgsSymbolPreview):

    def __init__(self, parent=None, height=72, dark=True):
        super().__init__(parent, height=height, kind="polygon", dark=dark)
        self._style = None

    def style_obj(self):
        return self._style

    def setStyle(self, st):
        self._style = st
        self.update()

    def _paint_content(self, p, inner):
        st = self._style
        if st is None:
            return
        if inner.width() <= 4 or inner.height() <= 4:
            return
        font = QFont()
        try:
            size = max(4.0, float(st.font_size or 10.0))
        except Exception:
            _log.exception("silent exception in _paint_content")
            size = 10.0
        try:
            fam = str(getattr(st, "font_family", "") or "")
        except Exception:
            _log.exception("silent exception in _paint_content")
            fam = ""
        if not fam:
            fam = _default_label_font_family()
        font.setFamily(fam)
        font.setPointSizeF(max(1.0, size * float(self.zoom())))
        font.setBold(bool(getattr(st, "bold", False)))
        font.setItalic(bool(getattr(st, "italic", False)))
        p.setFont(font)
        fm = p.fontMetrics()
        text = _SAMPLE
        tw = fm.horizontalAdvance(text)
        th = fm.height()

        place = str(getattr(st, "placement", "auto") or "auto")
        try:
            buf = float(st.px_of("buffer"))
        except Exception:
            _log.exception("silent exception in _paint_content")
            buf = float(getattr(st, "buffer", 0.0) or 0.0)
        anchor = QPointF(inner.center()) + self._pan
        if place in ("left", "right"):
            tx = (anchor.x() - buf - tw) if place == "left" \
                else (anchor.x() + buf)
            ty = anchor.y() + th * 0.32
        elif place in ("top", "bottom"):
            tx = anchor.x() - tw / 2.0
            ty = (anchor.y() - buf) if place == "top" \
                else (anchor.y() + buf + th * 0.75)
        else:
            tx = anchor.x() - tw / 2.0
            ty = anchor.y() + th * 0.32

        p.setClipRect(inner)
        path = QPainterPath()
        path.addText(QPointF(tx, ty), p.font(), text)

        try:
            hw = float(st.px_of("halo_width"))
        except Exception:
            _log.exception("silent exception in _paint_content")
            hw = float(getattr(st, "halo_width", 0.0) or 0.0)
        if hw > 0.05:
            hp = QPen(QColor(getattr(st, "halo_color", "#FFFFFF")))
            hp.setWidthF(hw * 2.0 * float(self.zoom()))
            hp.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            hp.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(hp)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(getattr(st, "color", "#000000")))
        p.drawPath(path)



class GgsLabelingPanel(GgsDockWidget):

    labelChanged = Signal(object)
    activated = Signal()

    def __init__(self, title=None, parent=None):
        super().__init__(title or _tr("标注设置"), parent)
        self.setObjectName("GgsLabelingDock")
        self._project = None
        self._layer = None
        self._loading = False
        self._style = None
        self._pending = {}
        self._expr_text = ""
        self._dirty = False
        self._build()
        self._clear_all()
        try:
            from ggis.core.style import style_library as _lib
            _lib.on_changed(self._on_style_library_changed)
        except Exception:
            _log.exception("silent exception in __init__")

    def _build(self):
        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 6, 8, 2)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        self.chk_enabled = QCheckBox(_tr("显示标注"))
        self.chk_enabled.toggled.connect(
            lambda on: self._edit("enabled", bool(on)))
        head.addWidget(self.chk_enabled)
        head.addStretch(1)
        lay.addLayout(head)

        self.row_sep = GgsSepH()
        self.row_sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(self.row_sep)

        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(8)
        iv.addWidget(self._build_content())
        iv.addWidget(self._build_font())
        iv.addWidget(self._build_pos())
        iv.addWidget(self._build_scale())
        iv.addStretch(1)
        self.scroll = GgsSymScroll()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(inner)
        lay.addWidget(self.scroll, 1)

        self.bottom_row = QWidget()
        hb = QVBoxLayout(self.bottom_row)
        hb.setContentsMargins(0, 4, 0, 0)
        hb.setSpacing(0)
        self.preview = _LabelPreview(self, height=72,
                                     dark=self._is_dark())
        hb.addWidget(self.preview)
        lay.addWidget(self.bottom_row)

        self.btn_apply = GgsApplyBtn(_tr("应用"))
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._on_apply)
        self.btn_import = self._make_import_button()
        foot = QHBoxLayout()
        foot.setSpacing(6)
        foot.addWidget(self.btn_import)
        foot.addStretch(1)
        foot.addWidget(self.btn_apply)
        lay.addLayout(foot)

        self.setWidget(body)
        relax_wide_inputs(self, limit=96)

    def _build_content(self):
        gb = QGroupBox(_tr("内容"))
        f = QFormLayout(gb)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(4)
        self.cmb_field = QComboBox()
        self.cmb_field.currentIndexChanged.connect(self._on_field_picked)
        self.btn_expr = GgsSmallButtonStyle1(
            "expression", _tr("标注表达式"),
            self._open_expr_dialog)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self.cmb_field, 1)
        row.addWidget(self.btn_expr)
        f.addRow(_tr("字段"), self._wrap(row))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(0, 1000000)
        self.spin_max.setSpecialValueText(_tr("不限"))
        self.spin_max.valueChanged.connect(
            lambda v: self._edit("max_labels", int(v)))
        f.addRow(_tr("每层上限"), self.spin_max)
        return gb

    def _build_font(self):
        gb = QGroupBox(_tr("字体与配色"))
        f = QFormLayout(gb)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(4)
        self.cmb_family = ggs_font_combo(self)
        self.cmb_family.currentIndexChanged.connect(self._on_family_picked)
        f.addRow(_tr("字体"), self.cmb_family)

        self.spin_font = QDoubleSpinBox()
        self.spin_font.setRange(4.0, 72.0)
        self.spin_font.setDecimals(1)
        self.spin_font.setSingleStep(0.5)
        self.spin_font.setSuffix(" pt")
        self.spin_font.valueChanged.connect(
            lambda v: self._edit("font_size", float(v)))
        f.addRow(_tr("字号"), self.spin_font)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.chk_bold = QCheckBox(_tr("粗体"))
        self.chk_bold.toggled.connect(lambda on: self._edit("bold", bool(on)))
        self.chk_italic = QCheckBox(_tr("斜体"))
        self.chk_italic.toggled.connect(
            lambda on: self._edit("italic", bool(on)))
        row.addWidget(self.chk_bold)
        row.addWidget(self.chk_italic)
        row.addStretch(1)
        f.addRow(_tr("样式"), self._wrap(row))

        self.btn_color = GgsColorField("#FFFFFF", self, shape="rect")
        self.btn_color.colorChanged.connect(
            lambda c: self._edit("color", QColor(c)))
        f.addRow(_tr("文字颜色"), self.btn_color)
        self.btn_halo = GgsColorField("#000000", self, shape="line")
        self.btn_halo.colorChanged.connect(
            lambda c: self._edit("halo_color", QColor(c)))
        f.addRow(_tr("描边颜色"), self.btn_halo)

        self.spin_halo = QDoubleSpinBox()
        self.spin_halo.setRange(0.0, 8.0)
        self.spin_halo.setDecimals(1)
        self.spin_halo.setSingleStep(0.2)
        self.spin_halo.setSpecialValueText(_tr("无"))
        self.spin_halo.valueChanged.connect(
            lambda v: self._edit("halo_width", float(v)))
        f.addRow(_tr("描边宽度"), self.spin_halo)
        return gb

    def _on_family_picked(self, idx):
        if self._loading or int(idx) < 0:
            return
        self._edit("font_family", ggs_combo_value(self.cmb_family))

    def _select_family(self, family):
        if not family:
            family = _default_label_font_family()
        ggs_font_select(self.cmb_family, str(family))

    def _build_pos(self):
        gb = QGroupBox(_tr("位置"))
        f = QFormLayout(gb)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(4)
        self.cmb_pos = QComboBox()
        for label, val in _PLACEMENTS:
            self.cmb_pos.addItem(_tr(label), val)
        self.cmb_pos.currentIndexChanged.connect(
            lambda _i: self._edit("placement",
                                  str(self.cmb_pos.currentData() or "auto")))
        f.addRow(_tr("候选位置"), self.cmb_pos)
        self.spin_buffer = QDoubleSpinBox()
        self.spin_buffer.setRange(0.0, 40.0)
        self.spin_buffer.setDecimals(1)
        self.spin_buffer.valueChanged.connect(
            lambda v: self._edit("buffer", float(v)))
        f.addRow(_tr("与锚点间距"), self.spin_buffer)
        self.spin_repeat = QDoubleSpinBox()
        self.spin_repeat.setRange(0.0, 500.0)
        self.spin_repeat.setDecimals(1)
        self.spin_repeat.setSpecialValueText(_tr("仅中点/内部点"))
        self.spin_repeat.valueChanged.connect(
            lambda v: self._edit("repeat_px", float(v)))
        f.addRow(_tr("沿线重复距离"), self.spin_repeat)
        return gb

    def _build_scale(self):
        gb = QGroupBox(_tr("显示范围"))
        f = QFormLayout(gb)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(4)
        self.spin_minscale = QDoubleSpinBox()
        self.spin_minscale.setRange(0.0, 5e7)
        self.spin_minscale.setDecimals(0)
        self.spin_minscale.setSpecialValueText(_tr("不限"))
        self.spin_minscale.valueChanged.connect(
            lambda v: self._edit("min_scale", float(v)))
        f.addRow(_tr("最小比例尺 1:"), self.spin_minscale)
        self.spin_maxscale = QDoubleSpinBox()
        self.spin_maxscale.setRange(0.0, 5e7)
        self.spin_maxscale.setDecimals(0)
        self.spin_maxscale.setSpecialValueText(_tr("不限"))
        self.spin_maxscale.valueChanged.connect(
            lambda v: self._edit("max_scale", float(v)))
        f.addRow(_tr("最大比例尺 1:"), self.spin_maxscale)
        self.spin_minsize = QDoubleSpinBox()
        self.spin_minsize.setRange(0.0, 2000.0)
        self.spin_minsize.setDecimals(1)
        self.spin_minsize.setSpecialValueText(_tr("不限"))
        self.spin_minsize.valueChanged.connect(
            lambda v: self._edit("min_size_px", float(v)))
        f.addRow(_tr("最小要素尺寸"), self.spin_minsize)
        gb.setToolTip("")
        return gb

    @staticmethod
    def _wrap(inner):
        w = QWidget()
        inner.setContentsMargins(0, 0, 0, 0)
        w.setLayout(inner)
        return w

    def current_layer(self):
        return self._layer

    def set_layer(self, layer):
        if layer is self._layer:
            return
        if layer is None:
            self._reset_pending()
            self._layer = None
            self._clear_all()
            return
        try:
            if not layer.is_vector():
                self._reset_pending()
                self._layer = None
                self._clear_all()
                return
        except Exception:
            _log.exception("silent exception in set_layer")
        from ...render.labeling import get_label_style
        self._layer = layer
        try:
            self._style = get_label_style(layer).clone()
        except Exception:
            _log.exception("silent exception in set_layer")
            from ...render.labeling import LabelStyle
            self._style = LabelStyle()
        self._reset_pending()
        self._load()
        self._update_title()

    def _fields(self):
        try:
            return [(str(n), str(t)) for n, t in self._layer.fields()]
        except Exception:
            _log.exception("silent exception in _fields")
            return []

    def _style_unit(self):
        try:
            return str(getattr(self._style, "unit", "") or "pt")
        except Exception:
            _log.exception("silent exception in _style_unit")
            return "pt"

    def _sync_size_units(self):
        u = self._style_unit()
        _apply_unit_to_spin(self.spin_halo, u, *_SIZE_SPIN_PX["halo"])
        _apply_unit_to_spin(self.spin_buffer, u, *_SIZE_SPIN_PX["buffer"])
        _apply_unit_to_spin(self.spin_repeat, u, *_SIZE_SPIN_PX["repeat"])
        _apply_unit_to_spin(self.spin_minsize, u, *_SIZE_SPIN_PX["minsize"])

    def _align_unit(self):
        st = self._style
        if st is None:
            return
        try:
            from ggis.core.crs.units import convert, default_unit, is_known
            cur = str(getattr(st, "unit", "") or "")
            want = str(default_unit())
        except Exception:
            _log.exception("silent exception in _align_unit")
            return
        if (not is_known(cur)) or cur == want:
            return
        try:
            names = tuple(st.size_fields())
        except Exception:
            _log.exception("silent exception in _align_unit")
            names = ("halo_width", "buffer", "min_size_px", "repeat_px")
        for k in names:
            try:
                v = float(convert(float(getattr(st, k) or 0.0), cur, want))
            except Exception:
                _log.exception("silent exception in _align_unit")
                continue
            setattr(st, k, v)
            self._pending[k] = v
        st.unit = want
        self._pending["unit"] = want
        self._mark_dirty()

    def _load(self):
        st = self._style
        if st is None:
            return
        self._align_unit()
        self._sync_size_units()
        self._loading = True
        try:
            from ...render.labeling import suggest_label_field
            self.cmb_field.clear()
            for name, typ in self._fields():
                self.cmb_field.addItem(str(name), str(name))
                self.cmb_field.setItemData(
                    self.cmb_field.count() - 1, "%s (%s)" % (name, typ),
                    Qt.ItemDataRole.ToolTipRole)
            self.cmb_field.addItem(_tr("自定义"), "")
            self.chk_enabled.setChecked(bool(st.enabled))
            expr = str(getattr(st, "field", "") or "")
            if not expr:
                try:
                    expr = str(suggest_label_field(self._layer) or "")
                except Exception:
                    _log.exception("silent exception in _load")
                    expr = ""
            self._show_field_value(expr)
            self.spin_max.setValue(int(getattr(st, "max_labels", 0) or 0))
            self._select_family(str(getattr(st, "font_family", "") or ""))
            self.spin_font.setValue(float(getattr(st, "font_size", 10.0)))
            self.chk_bold.setChecked(bool(getattr(st, "bold", False)))
            self.chk_italic.setChecked(bool(getattr(st, "italic", False)))
            self.btn_color.setColor(QColor(getattr(st, "color", "#FFFFFF")))
            self.btn_halo.setColor(
                QColor(getattr(st, "halo_color", "#000000")))
            self.spin_halo.setValue(float(getattr(st, "halo_width", 0.0)))
            self.spin_buffer.setValue(float(getattr(st, "buffer", 0.0)))
            self.spin_repeat.setValue(float(getattr(st, "repeat_px", 0.0)))
            self.spin_minscale.setValue(float(getattr(st, "min_scale", 0.0)))
            self.spin_maxscale.setValue(float(getattr(st, "max_scale", 0.0)))
            self.spin_minsize.setValue(float(getattr(st, "min_size_px", 0.0)))
            j = self.cmb_pos.findData(str(getattr(st, "placement", "auto")
                                          or "auto"))
            self.cmb_pos.setCurrentIndex(max(0, j))
        finally:
            self._loading = False
        self._apply_first_time_default()
        self.preview.setStyle(self._eff_style())
        self._set_content_visible(True)
        self._sync_style_button()

    def _apply_first_time_default(self):
        st = self._style
        if st is None:
            return
        if any(k not in _UNIT_ALIGN_KEYS for k in self._pending):
            return
        if bool(getattr(st, "enabled", False)):
            return
        if str(getattr(st, "field", "") or "").strip():
            return
        if self.chk_enabled.isChecked():
            return
        self._loading = True
        try:
            self.chk_enabled.setChecked(True)
        finally:
            self._loading = False
        self._pending["enabled"] = True
        self._mark_dirty()

    @staticmethod
    def _is_dark():
        try:
            from ggis.common.styling import icons
            return bool(icons.is_dark())
        except Exception:
            _log.exception("silent exception in _is_dark")
            return True

    def _style_items(self):
        try:
            from ggis.core.style import style_library as lib
            return list(lib.items("text"))
        except Exception:
            _log.exception("silent exception in _style_items")
            return []

    def _same_text_style(self, st, item):
        if st is None or not item:
            return False
        for k in _PRESET_FIELDS:
            if k not in item:
                continue
            try:
                a = getattr(st, k)
            except Exception:
                _log.exception("silent exception in _same_text_style")
                continue
            b = item.get(k)
            if b is None:
                continue
            if k in ("color", "halo_color"):
                try:
                    if (QColor(a).name().lower()
                            != QColor(str(b)).name().lower()):
                        return False
                except Exception:
                    _log.exception("silent exception in _same_text_style")
                    return False
            elif isinstance(b, bool):
                if bool(a) != bool(b):
                    return False
            elif isinstance(b, (int, float)):
                try:
                    a_v = float(a)
                    if k in _PRESET_SIZE_FIELDS:
                        try:
                            a_v = float(st.px_of(k))
                        except Exception:
                            _log.exception("silent exception in _same_text_style")
                    if abs(a_v - float(b)) > 1e-3:
                        return False
                except Exception:
                    _log.exception("silent exception in _same_text_style")
                    return False
            else:
                if str(a or "") != str(b or ""):
                    return False
        return True

    def _make_import_button(self):
        from ggis.ui.panels.symbology import GgsStyleImportButton
        btn = GgsStyleImportButton(self, tip=_tr("导入标注设置"))
        btn.set_layer_source(self._labelled_layers)
        btn.pickFromLibrary.connect(self._import_from_library)
        btn.pickFromLayer.connect(self._import_from_layer)
        return btn

    def set_project(self, project):
        self._project = project

    def _import_from_library(self):
        items = self._style_items()
        if not items:
            return
        try:
            from ggis.ui.dialogs.symbol_preview import GgsSymbolGalleryDialog
            item = GgsSymbolGalleryDialog.getItem(
                items, "polygon", self._is_dark(),
                current_key=None, parent=self, category="text")
        except Exception:
            _log.exception("silent exception in _import_from_library")
            item = None
        if item:
            self._on_style_picked(item)

    def _labelled_layers(self):
        proj = getattr(self, "_project", None)
        rows = []
        try:
            layers = list(proj.layers()) if proj is not None else []
        except Exception:
            _log.exception("silent exception in _labelled_layers")
            layers = []
        for lyr in layers:
            if lyr is self._layer:
                continue
            try:
                from ...render.labeling import get_label_style
                st = get_label_style(lyr)
            except Exception:
                _log.exception("silent exception in _labelled_layers")
                st = None
            if st is None or not bool(getattr(st, "enabled", False)):
                continue
            try:
                name = str(lyr.name() or "")
            except Exception:
                _log.exception("silent exception in _labelled_layers")
                name = ""
            rows.append((name or _tr("未命名图层"), lyr))
        return rows

    def _import_from_layer(self, layer):
        try:
            from ...render.labeling import get_label_style
            st = get_label_style(layer)
        except Exception:
            _log.exception("silent exception in _import_from_layer")
            st = None
        if st is None:
            return
        item = {}
        for k in _PRESET_FIELDS:
            try:
                v = getattr(st, k)
            except Exception:
                _log.exception("silent exception in _import_from_layer")
                continue
            if k in _PRESET_SIZE_FIELDS:
                try:
                    v = float(st.px_of(k))
                except Exception:
                    _log.exception("silent exception in _import_from_layer")
            item[k] = v
        if item:
            self._on_style_picked(item)

    def _sync_style_button(self):
        try:
            self.btn_import.setEnabled(self._layer is not None)
        except Exception:
            _log.exception("silent exception in _sync_style_button")

    def _on_style_library_changed(self):
        try:
            self._sync_style_button()
        except Exception:
            _log.exception("silent exception in _on_style_library_changed")

    def _on_style_picked(self, item):
        if self._loading or self._style is None or not item:
            return
        _u = self._style_unit()
        for k in _PRESET_FIELDS:
            if k not in item:
                continue
            v = item.get(k)
            if k in ("color", "halo_color"):
                v = QColor(str(v))
            elif k in _PRESET_SIZE_FIELDS:
                try:
                    from ggis.core.crs.units import from_px
                    v = float(from_px(float(v), _u))
                except Exception:
                    _log.exception("silent exception in _on_style_picked")
            self._pending[k] = v
            self._load_preset_field(k, v)
        self._mark_dirty()
        self.preview.setStyle(self._eff_style())
        self._sync_style_button()

    def _load_preset_field(self, key, value):
        self._loading = True
        try:
            if key == "font_size":
                self.spin_font.setValue(float(value))
            elif key == "bold":
                self.chk_bold.setChecked(bool(value))
            elif key == "italic":
                self.chk_italic.setChecked(bool(value))
            elif key == "color":
                self.btn_color.setColor(value)
            elif key == "halo_color":
                self.btn_halo.setColor(value)
            elif key == "halo_width":
                self.spin_halo.setValue(float(value))
            elif key == "buffer":
                self.spin_buffer.setValue(float(value))
            elif key == "font_family":
                self._select_family(str(value or ""))
        finally:
            self._loading = False

    def _show_field_value(self, expr):
        expr = str(expr or "")
        i = self.cmb_field.findData(expr) if expr else -1
        if i < 0:
            i = self.cmb_field.findData("")
        self.cmb_field.setCurrentIndex(max(0, i))
        if i == self.cmb_field.findData("") and expr:
            self.btn_expr.setToolTip(_tr("当前表达式：{0}").format(expr))
        else:
            self._reset_expr_tip()
        self._expr_text = expr

    def _reset_expr_tip(self):
        try:
            self.btn_expr.setToolTip(_tr("标注表达式"))
        except Exception:
            _log.exception("silent exception in _reset_expr_tip")

    def _on_field_picked(self, _idx):
        if self._loading:
            return
        data = self.cmb_field.currentData()
        if data:
            self._edit("field", str(data))
            self._expr_text = str(data)
            self._reset_expr_tip()

    def _open_expr_dialog(self):
        if self._loading or self._style is None:
            return
        try:
            from ..dialogs.label_expression import (
                GgsLabelExpressionDialog)
        except Exception:
            _log.exception("silent exception in _open_expr_dialog")
            return
        cur = (str(self._pending.get("field", ""))
               or str(getattr(self._style, "field", "") or ""))
        try:
            dlg = GgsLabelExpressionDialog(self._layer, cur, self)
        except Exception:
            _log.exception("silent exception in _open_expr_dialog")
            return
        from PySide6.QtWidgets import QDialog
        if int(dlg.exec()) != int(QDialog.DialogCode.Accepted):
            return
        expr = dlg.expression()
        expr = self._as_bare_field(expr)
        self._edit("field", expr)
        self._show_field_value(expr)
        self.preview.setStyle(self._eff_style())

    def _as_bare_field(self, expr):
        t = str(expr or "").strip()
        if not (t.startswith("[") and t.endswith("]")) or t.count("[") != 1:
            return t
        name = t[1:-1].strip()
        try:
            if name in {str(n) for n, _typ in self._fields()}:
                return name
        except Exception:
            _log.exception("silent exception in _as_bare_field")
        return t

    def _eff_style(self):
        st = self._style
        if st is None:
            return None
        try:
            st = st.clone()
        except Exception:
            _log.exception("silent exception in _eff_style")
        for k, v in self._pending.items():
            try:
                setattr(st, k, v)
            except Exception:
                _log.exception("silent exception in _eff_style")
        return st

    def _edit(self, key, value):
        if self._loading or self._style is None:
            return
        self._pending[str(key)] = value
        self._mark_dirty()
        self.preview.setStyle(self._eff_style())

    def _mark_dirty(self):
        try:
            self.btn_apply.setEnabled(bool(self._pending))
        except Exception:
            _log.exception("silent exception in _mark_dirty")

    def _reset_pending(self):
        self._pending = {}
        self._dirty = False
        try:
            self.btn_apply.setEnabled(False)
        except Exception:
            _log.exception("silent exception in _reset_pending")

    def _on_apply(self):
        lyr, st = self._layer, self._style
        if lyr is None or st is None:
            return
        for k, v in self._pending.items():
            try:
                setattr(st, k, v)
            except Exception:
                _log.exception("silent exception in _on_apply")
        if not str(getattr(st, "field", "") or "").strip():
            try:
                f = str(self.cmb_field.currentData()
                        or getattr(self, "_expr_text", "") or "")
            except Exception:
                _log.exception("silent exception in _on_apply")
                f = ""
            if f:
                try:
                    st.field = f
                except Exception:
                    _log.exception("silent exception in _on_apply")
        if not str(getattr(st, "font_family", "") or "").strip():
            try:
                ff = ggs_combo_value(self.cmb_family)
                if ff:
                    st.font_family = ff
            except Exception:
                _log.exception("silent exception in _on_apply")
        try:
            st._font_key = None
            st._font = None
        except Exception:
            _log.exception("silent exception in _on_apply")
        try:
            from ...render.labeling import set_label_style
            set_label_style(lyr, st)
        except Exception:
            _log.exception("silent exception in _on_apply")
        self._reset_pending()
        self._load()
        self.labelChanged.emit(lyr)

    def _clear_all(self):
        self._set_content_visible(False)
        self._update_title()

    def _update_title(self):
        name = ""
        try:
            if self._layer is not None:
                name = str(self._layer.name() or "")
        except Exception:
            _log.exception("silent exception in _update_title")
            name = ""
        text = (_tr("标注设置 — {0}").format(name) if name else
                _tr("标注设置"))
        try:
            self.set_title_label(text)
        except Exception:
            _log.exception("silent exception in _update_title")

    def _set_content_visible(self, on):
        on = bool(on) and (self._layer is not None)
        for w in (self.chk_enabled, self.row_sep, self.scroll,
                  self.bottom_row, self.btn_import):
            try:
                w.setVisible(on)
            except Exception:
                _log.exception("silent exception in _set_content_visible")
        try:
            self.btn_apply.setVisible(on)
        except Exception:
            _log.exception("silent exception in _set_content_visible")

    def showEvent(self, e):
        super().showEvent(e)
        try:
            self.activated.emit()
        except Exception:
            _log.exception("silent exception in showEvent")


class GgsApplyBtn(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsApplyBtn")
class GgsSymScroll(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSymScroll")
