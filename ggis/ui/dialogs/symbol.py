# -*- coding: utf-8 -*-

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialogButtonBox, QDoubleSpinBox,
                              QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                              QLineEdit, QVBoxLayout, QWidget)

from ggis.common.widgets.inputs import GgsColorField
from ggis.ui.dialogs.symbol_preview import GgsSymbolPreview
from ggis.core.app import i18n
from ggis.core.style import style_library as _lib
from ggis.core.style.symbol_spec import (CAP_LABELS, CAPS, FILL_STYLE_LABELS,
                                 FILL_STYLES, JOIN_LABELS, JOINS,
                                 LINE_STYLE_LABELS, LINE_STYLES)
from ...render.symbol import (set_symbol_color,
                              symbol_color)
from ggis.common.base.dialog import GgsDialog
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr


def symbol_items_for_kind(kind):
    k = str(kind or "")
    out = []
    try:
        pool = (list(_lib.builtin_items("symbol"))
                + list(_lib.user_items("symbol")))
    except Exception:
        _log.exception("silent exception in symbol_items_for_kind")
        return []
    for it in pool:
        if str(it.get("kind") or "") == k:
            out.append(it)
    return out


def _combo(pairs, value):
    cb = QComboBox()
    for key in pairs:
        cb.addItem(_tr(key[1]), key[0])
    i = cb.findData(value)
    cb.setCurrentIndex(i if i >= 0 else 0)
    return cb


class GgsSymbolDialog(GgsDialog):

    def __init__(self, sym, kind="polygon", dark=True, title="",
                 parent=None):
        super().__init__(parent)
        self.setObjectName("GgsSymbolDialog")
        self.setWindowTitle(_tr(title or "单一符号"))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("styling", size=16))
        self.resize(420, 470)
        try:
            self._sym = sym.clone()
        except Exception:
            _log.exception("silent exception in __init__")
            self._sym = sym
        self._kind = str(kind or "polygon")
        self._dark = bool(dark)
        self._loading = False
        self._build()

    def _build(self):
        self._loading = True
        out = QVBoxLayout(self)
        out.setContentsMargins(12, 10, 12, 10)
        out.setSpacing(8)

        is_line = self._kind.startswith("line")
        is_point = self._kind.startswith("point")
        fill_shape = "line" if is_line else "rect"
        stroke_shape = "line"

        self.grp_fill = QGroupBox(_tr("填充"), self)
        form_fill = QFormLayout(self.grp_fill)
        form_fill.setContentsMargins(8, 8, 8, 8)
        form_fill.setSpacing(4)
        self._form = form_fill

        self.fld_color = GgsColorField(
            symbol_color(self._sym, self._kind), self, shape=fill_shape)
        self.fld_color.colorChanged.connect(self._on_color)
        if not is_line:
            form_fill.addRow(_tr("填充颜色"), self.fld_color)

        if not is_line:
            self.cmb_fill = _combo(
                [(k, FILL_STYLE_LABELS.get(k, k)) for k in FILL_STYLES],
                str(getattr(self._sym, "fill_style", "solid") or "solid"))
            self.cmb_fill.currentIndexChanged.connect(self._on_fill_style)
            form_fill.addRow(_tr("填充图案"), self.cmb_fill)
            self.sp_spacing = QDoubleSpinBox()
            self.sp_width2 = QDoubleSpinBox()
            try:
                self.sp_spacing.setValue(float(self._sym.fill_spacing))
                self.sp_width2.setValue(float(self._sym.fill_width))
            except Exception:
                _log.exception("silent exception in _build")
            from ..panels.symbology import (_apply_pattern_spins,
                                            _apply_unit_spins)
            _apply_pattern_spins(
                self.sp_spacing, self.sp_width2,
                str(getattr(self._sym, "unit", "") or "pt"))
            self.sp_spacing.valueChanged.connect(self._on_pattern_param)
            self.sp_width2.valueChanged.connect(self._on_pattern_param)
            self._w_pattern = QWidget(self)
            hb = QHBoxLayout(self._w_pattern)
            hb.setContentsMargins(0, 0, 0, 0)
            hb.setSpacing(4)
            hb.addWidget(self.sp_spacing, 1)
            hb.addWidget(QLabel("—"))
            hb.addWidget(self.sp_width2, 1)
            form_fill.addRow(_tr("图案间距"), self._w_pattern)
        out.addWidget(self.grp_fill)
        self.grp_fill.setVisible(not is_line)

        self.grp_stroke = QGroupBox(_tr("线条") if is_line else _tr("描边"), self)
        form_stroke = QFormLayout(self.grp_stroke)
        form_stroke.setContentsMargins(8, 8, 8, 8)
        form_stroke.setSpacing(4)
        if is_line:
            form_stroke.addRow(_tr("颜色"), self.fld_color)
        if not is_line:
            self.fld_stroke = GgsColorField(
                self._sym.stroke or "#2A2A2A", self, shape=stroke_shape)
            self.fld_stroke.colorChanged.connect(self._on_stroke)
            form_stroke.addRow(_tr("描边颜色"), self.fld_stroke)

        from ..panels.symbology import _apply_unit_spins
        u = str(getattr(self._sym, "unit", "") or "pt")
        self.sp_size = QDoubleSpinBox()
        self.sp_size.setValue(float(getattr(self._sym, "size", 0.0) or 0.0))
        self.sp_size.valueChanged.connect(self._on_size)
        self.sp_width = QDoubleSpinBox()
        self.sp_width.setValue(float(self._sym.width))
        self.sp_width.valueChanged.connect(self._on_width)
        _apply_unit_spins(self.sp_size, self.sp_width, u,
                          extra=max(float(getattr(self._sym, "size", 0.0)),
                                    float(self._sym.width)))
        form_stroke.addRow(_tr("线宽"), self.sp_width)

        _line_items = [(k, LINE_STYLE_LABELS.get(k, k)) for k in LINE_STYLES]
        _line_items.append(("custom", _tr("自定义…")))
        self.cmb_line = _combo(
            _line_items,
            str(getattr(self._sym, "line_style", "solid") or "solid"))
        self.cmb_line.currentIndexChanged.connect(self._on_line_style)
        form_stroke.addRow(_tr("线样式"), self.cmb_line)

        self.lbl_dash_pattern = QLabel(_tr("虚线图案（线宽倍数）"))
        self.ed_dash_pattern = QLineEdit()
        self.ed_dash_pattern.setPlaceholderText(
            "")
        self.ed_dash_pattern.editingFinished.connect(self._on_dash_pattern)
        _dc = getattr(self._sym, "dash_custom", ()) or ()
        self.ed_dash_pattern.setText(", ".join(str(v) for v in _dc))
        form_stroke.addRow(self.lbl_dash_pattern, self.ed_dash_pattern)
        self.lbl_dash_pattern.setVisible(False)
        self.ed_dash_pattern.setVisible(False)

        self.cmb_cap = _combo([(k, CAP_LABELS.get(k, k)) for k in CAPS],
                              str(getattr(self._sym, "cap", "flat") or "flat"))
        self.cmb_cap.currentIndexChanged.connect(self._on_cap)
        form_stroke.addRow(_tr("端头"), self.cmb_cap)
        self.cmb_join = _combo([(k, JOIN_LABELS.get(k, k)) for k in JOINS],
                               str(getattr(self._sym, "join", "bevel")
                                   or "bevel"))
        self.cmb_join.currentIndexChanged.connect(self._on_join)
        form_stroke.addRow(_tr("连接"), self.cmb_join)
        out.addWidget(self.grp_stroke)

        if is_point:
            form_size = QFormLayout()
            form_size.setContentsMargins(0, 0, 0, 0)
            form_size.setSpacing(4)
            form_size.addRow(_tr("符号大小"), self.sp_size)
            out.addLayout(form_size)

        out.addStretch(1)
        self.preview = GgsSymbolPreview(self, height=72, kind=self._kind,
                                        dark=self._dark)
        out.addWidget(self.preview)
        foot = QHBoxLayout()
        foot.setSpacing(6)
        self.btn_lib = GgsSymbolButton(self, kind=self._kind, dark=self._dark,
                                       tip=_tr("从样式库选择"))
        self.btn_lib.setItems(symbol_items_for_kind(self._kind),
                              kind=self._kind, dark=self._dark,
                              sym=self._sym)
        self.btn_lib.picked.connect(self._on_preset)
        foot.addWidget(self.btn_lib)
        foot.addStretch(1)
        bb = QDialogButtonBox(self)
        bb.addButton(_tr("确定"), QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton(_tr("取消"), QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        foot.addWidget(bb)
        out.addLayout(foot)

        self._loading = False
        self._sync_dash_row()
        self._sync_pattern()
        self._refresh_preview()

    def _refresh_preview(self):
        try:
            self.preview.setSymbol(self._sym, self._kind, self._dark)
        except Exception:
            _log.exception("silent exception in _refresh_preview")

    def _changed(self, *_a):
        if self._loading:
            return
        self._sync_pattern()
        self._refresh_preview()

    def _sync_pattern(self):
        w = getattr(self, "_w_pattern", None)
        if w is None:
            return
        try:
            on = str(self.cmb_fill.currentData() or "solid") != "solid"
        except Exception:
            _log.exception("silent exception in _sync_pattern")
            on = False
        w.setVisible(bool(on))
        lbl = self._form.labelForField(w)
        if lbl is not None:
            lbl.setVisible(bool(on))

    def _on_color(self, c):
        if self._loading:
            return
        set_symbol_color(self._sym, self._kind, c)
        self._changed()

    def _on_stroke(self, c):
        if self._loading:
            return
        try:
            self._sym.stroke = c
        except Exception:
            _log.exception("silent exception in _on_stroke")
        self._changed()

    def _on_size(self, v):
        if self._loading:
            return
        self._sym.size = float(v)
        self._changed()

    def _on_width(self, v):
        if self._loading:
            return
        self._sym.width = float(v)
        self._changed()

    def _on_line_style(self, *_a):
        if self._loading:
            return
        self._sym.line_style = str(self.cmb_line.currentData() or "solid")
        self._sync_dash_row()
        self._changed()

    def _on_dash_pattern(self):
        if self._loading:
            return
        try:
            txt = str(self.ed_dash_pattern.text() or "")
            vals = tuple(float(v) for v in txt.replace("，", ",").split(",")
                         if v.strip())
        except Exception:
            _log.exception("silent exception in _on_dash_pattern")
            return
        self._sym.dash_custom = tuple(v for v in vals if v > 0)
        self._changed()

    def _sync_dash_row(self):
        try:
            on = str(self.cmb_line.currentData() or "solid") == "custom"
        except Exception:
            _log.exception("silent exception in _sync_dash_row")
            on = False
        self.lbl_dash_pattern.setVisible(on)
        self.ed_dash_pattern.setVisible(on)

    def _on_fill_style(self, *_a):
        if self._loading:
            return
        self._sym.fill_style = str(self.cmb_fill.currentData() or "solid")
        self._changed()

    def _on_pattern_param(self, *_a):
        if self._loading:
            return
        try:
            self._sym.fill_spacing = float(self.sp_spacing.value())
            self._sym.fill_width = float(self.sp_width2.value())
        except Exception:
            _log.exception("silent exception in _on_pattern_param")
        self._changed()

    def _on_cap(self, *_a):
        if self._loading:
            return
        self._sym.cap = str(self.cmb_cap.currentData() or "flat")
        self._changed()

    def _on_join(self, *_a):
        if self._loading:
            return
        self._sym.join = str(self.cmb_join.currentData() or "bevel")
        self._changed()

    def _on_preset(self, item):
        if not item:
            return
        try:
            from ...render.style_apply import symbol_from_item
            new = symbol_from_item(item, self._kind, self._dark)
        except Exception:
            _log.exception("silent exception in _on_preset")
            return
        if new is None:
            return
        self._sym = new
        self._loading = True
        try:
            self.fld_color.setColor(QColor(symbol_color(self._sym,
                                                        self._kind)))
            if hasattr(self, "fld_stroke"):
                self.fld_stroke.setColor(self._sym.stroke or "#2A2A2A")
            self.sp_width.setValue(float(self._sym.width))
            if hasattr(self, "sp_size"):
                self.sp_size.setValue(float(self._sym.size))
            self.cmb_line.setCurrentIndex(max(
                0, self.cmb_line.findData(
                    str(getattr(self._sym, "line_style", "solid")))))
            self.ed_dash_pattern.setText(", ".join(
                str(v) for v in (getattr(self._sym, "dash_custom", ()) or ())))
            self._sync_dash_row()
            if hasattr(self, "cmb_fill"):
                self.cmb_fill.setCurrentIndex(max(
                    0, self.cmb_fill.findData(
                        str(getattr(self._sym, "fill_style", "solid")))))
                self._sync_pattern()
            self.cmb_cap.setCurrentIndex(max(
                0, self.cmb_cap.findData(str(getattr(self._sym, "cap",
                                                     "flat")))))
            self.cmb_join.setCurrentIndex(max(
                0, self.cmb_join.findData(str(getattr(self._sym, "join",
                                                      "bevel")))))
        except Exception:
            _log.exception("silent exception in _on_preset")
        finally:
            self._loading = False
        self._refresh_preview()

    def symbol(self):
        return self._sym

    @staticmethod
    def edit(sym, kind="polygon", dark=True, title="", parent=None):
        if sym is None:
            return None
        dlg = GgsSymbolDialog(sym, kind=kind, dark=dark, title=title,
                              parent=parent)
        if dlg.exec():
            return dlg.symbol()
        return None


from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QToolButton
from ggis.common.widgets.buttons import exc_note
from ggis.core.app import i18n
_tr = i18n.tr


class GgsSymbolButton(QToolButton):

    picked = Signal(object)

    MIN_WIDTH = 88
    HEIGHT = 28
    LABEL_MAX = 6
    ICON = 16

    def __init__(self, parent=None, kind="polygon", dark=True, tip="",
                 category="symbol"):
        super().__init__(parent)
        self.setObjectName("GgsSymbolButton")
        self._tip = str(tip or "") or _tr("从样式库选择")
        self.setIconSize(QSize(self.ICON, self.ICON))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setArrowType(Qt.ArrowType.NoArrow)
        self.setMinimumWidth(int(self.MIN_WIDTH))
        self.setFixedHeight(int(self.HEIGHT))
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Fixed)
        self.setAutoRaise(False)
        self._items = []
        self._kind = str(kind or "polygon")
        self._dark = bool(dark)
        self._category = str(category or "symbol")
        self._current = None
        self._sym = None
        self.clicked.connect(self._choose)
        try:
            from ggis.common.styling import icons as _icons
            _icons.bind(self, "style_library", size=self.ICON)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/symbol_preview.py:926")
            pass
        self._refresh()

    def setItems(self, items, kind=None, dark=None, current=None, sym=None,
                 category=None):
        self._items = list(items or [])
        if kind is not None:
            self._kind = str(kind or "polygon")
        if dark is not None:
            self._dark = bool(dark)
        if category is not None:
            self._category = str(category or "symbol")
        self._current = current
        self._sym = sym
        self._refresh()

    def current(self):
        return self._current

    def _refresh(self):
        sym = None
        if self._current:
            try:
                from ggis.render.style_apply import symbol_from_item
                sym = symbol_from_item(self._current, self._kind, self._dark)
            except Exception:
                exc_note("_refresh @ ggis/common/widgets/symbol_preview.py:959")
                sym = None
        if sym is None:
            sym = self._sym
        name = ""
        try:
            if self._current:
                name = str(self._current.get("title") or "").strip()
        except Exception:
            exc_note("_refresh @ ggis/common/widgets/symbol_preview.py:976")
            name = ""
        short = name
        if len(short) > self.LABEL_MAX:
            short = short[:self.LABEL_MAX] + "…"
        self.setText(_tr("从样式库选择"))
        tip = self._tip
        if name:
            tip = _tr("当前样式：{0}").format(name) + "\n" + self._tip
        self.setToolTip(tip)


    def _choose(self):
        if not self._items:
            return
        from ggis.ui.dialogs.symbol_preview import GgsSymbolGalleryDialog
        item = GgsSymbolGalleryDialog.getItem(
            self._items, self._kind, self._dark,
            current_key=(self._current or {}).get("key"), parent=self,
            category=self._category)
        if item is None or item == self._current:
            return
        self._current = item
        self._refresh()
        self.picked.emit(item)
