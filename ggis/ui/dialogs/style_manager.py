# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import os

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
                               QApplication,
                               QFileDialog,
                               QFormLayout,
                               QFrame,
                               QHBoxLayout,
                               QLabel,
                               QListWidget,
                               QListWidgetItem,
                               QMessageBox,
                               QSplitter,
                               QStyle,
                               QStyledItemDelegate,
                               QStyleOptionViewItem,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n
from ggis.core.style import style_library as lib
from ggis.core.style import user_ramps as _user_ramps
from ggis.common.widgets.inputs import GgsComboBox, ggs_combo_value
from ggis.common.widgets.buttons import GgsStandardButton
from ggis.common.base.dialog import GgsDialog
from .style_preview import _preview_pixmap
from .style_widgets import (_category_word, _color_row, _field_title,
                            _form_label, _left_row, _make_editor,
                            _preview_title)
import logging
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QScrollArea
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_KIND_FILTERS = [("全部", ""), ("点", "point"), ("线", "line"),
                 ("面", "polygon")]

_BIG = QSize(260, 72)
_CARD = 48
_CELL = QSize(_CARD + 64, _CARD + 20)

MODE_GRID, MODE_LIST = "grid", "list"
_DISPLAY_MODES = (MODE_GRID, MODE_LIST)
_MODE_ICON = {MODE_GRID: _CARD, MODE_LIST: 24}
_MODE_CELL = {MODE_GRID: _CELL}
_MODE_ICON_RAMP = {MODE_GRID: QSize(96, 26), MODE_LIST: QSize(80, 20)}
_VIEW_CHOICES = ((MODE_GRID, "大图标"), (MODE_LIST, "列表"))


class GgsStyleWall(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleItems")


class _CardWall(GgsStyleWall):

    picked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setWordWrap(False)
        self.setSpacing(2)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._rows = []
        self._mode = MODE_GRID
        self.currentRowChanged.connect(self._on_row)

    def set_display_mode(self, mode):
        if mode in _DISPLAY_MODES:
            self._mode = mode

    def display_mode(self):
        return self._mode

    def _icon_size(self, category):
        if str(category or "") == "ramp":
            return QSize(_MODE_ICON_RAMP.get(self._mode)
                         or _MODE_ICON_RAMP[MODE_GRID])
        n = int(_MODE_ICON.get(self._mode, _CARD))
        return QSize(n, n)

    def fill(self, items, category, dark):
        self.blockSignals(True)
        try:
            self.clear()
            self._rows = list(items)
            as_list = self._mode == MODE_LIST
            sz = self._icon_size(category)
            wide = str(category or "") == "ramp"
            self.setIconSize(sz)
            if as_list:
                self.setViewMode(QListWidget.ViewMode.ListMode)
                self.setSpacing(0)
                self.setGridSize(QSize())
            else:
                self.setViewMode(QListWidget.ViewMode.IconMode)
                self.setSpacing(2)
                self.setGridSize(_MODE_CELL.get(self._mode, _CELL))
            for it in self._rows:
                row = QListWidgetItem(_preview_title(it))
                if wide:
                    pm = _preview_pixmap(category, it, dark,
                                         sz.width(), sz.height())
                else:
                    pm = _preview_pixmap(category, it, dark, sz.width())
                row.setIcon(QIcon(pm))
                row.setToolTip(_tr("内置预设（只读）") if it.get("builtin")
                               else _tr("自定义预设"))
                if as_list:
                    row.setTextAlignment(Qt.AlignmentFlag.AlignLeft
                                         | Qt.AlignmentFlag.AlignVCenter)
                else:
                    row.setTextAlignment(Qt.AlignmentFlag.AlignHCenter
                                         | Qt.AlignmentFlag.AlignTop)
                    row.setSizeHint(_MODE_CELL.get(self._mode, _CELL))
                self.addItem(row)
            self.setCurrentRow(-1)
        finally:
            self.blockSignals(False)

    def pick_key(self, key):
        for r, it in enumerate(self._rows):
            if it["key"] == key:
                self.setCurrentRow(r)
                return True
        return False

    def unselect(self):
        self.blockSignals(True)
        try:
            self.setCurrentRow(-1)
        finally:
            self.blockSignals(False)

    def item_at(self, row):
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _on_row(self, row):
        self.picked.emit(self.item_at(row))


class GgsStyleCatDelegate(QStyledItemDelegate):

    def paint(self, p, opt, idx):
        o = QStyleOptionViewItem(opt)
        self.initStyleOption(o, idx)
        o.text = ""
        w = o.widget
        style = w.style() if w is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, o, p, w)
        r = opt.rect.adjusted(7, 0, -7, 0)
        base = opt.palette.color(QPalette.ColorRole.Text)
        x = r.left()
        ic = idx.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(ic, QIcon) and not ic.isNull():
            ic.paint(p, QRect(x, r.center().y() - 7, 14, 14))
            x += 20
        fm = QFontMetrics(opt.font)
        cnt = str(idx.data(Qt.ItemDataRole.UserRole + 1) or "")
        cw = fm.horizontalAdvance(cnt) if cnt else 0
        if cnt:
            dim = QColor(base)
            dim.setAlpha(140)
            p.setPen(dim)
            p.drawText(QRect(r.right() - cw, r.top(), cw, r.height()),
                       int(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignVCenter), cnt)
        p.setPen(base)
        p.drawText(QRect(x, r.top(), max(0, r.right() - cw - 6 - x),
                         r.height()),
                   int(Qt.AlignmentFlag.AlignLeft
                       | Qt.AlignmentFlag.AlignVCenter),
                   str(idx.data(Qt.ItemDataRole.DisplayRole) or ""))


def _category_icon(category, items, dark, size):
    if not items:
        return None
    try:
        return QIcon(_preview_pixmap(category, items[0], dark, size, size))
    except Exception:
        _log.exception("silent exception in _category_icon")
        return None


class GgsStyleManagerDialog(GgsDialog):

    def __init__(self, parent=None, dark_bg=True):
        super().__init__(parent)
        self._dark = bool(dark_bg)
        self._category = lib.CATEGORIES[0]
        self._item = None
        self._editors = {}
        self._dirty = False
        self._loading = False
        self._walls = []
        self.setObjectName("GgsStyleManagerDialog")
        self.setWindowTitle(_tr("样式管理器"))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("color_swatch", size=16))
        self.resize(920, 620)
        self._build()
        self._load_categories()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self._build_header(root)
        self._build_nav(root)
        self._build_status(root)
        self._build_footer(root)
        self._refresh_buttons()

    def _build_header(self, root):
        self.lbl_hint = GgsStyleHint("")
        self.lbl_hint.setWordWrap(False)
        root.addWidget(self.lbl_hint)

    def _build_nav(self, root):
        split = QSplitter(Qt.Orientation.Horizontal, self)

        self.lst_cat = GgsStyleCats()
        self.lst_cat.setItemDelegate(GgsStyleCatDelegate(self.lst_cat))
        self.lst_cat.currentRowChanged.connect(self._on_category_changed)
        split.addWidget(self.lst_cat)

        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(4)
        ml.addLayout(self._build_preset_toolbar())
        for _builtin in (True, False):
            lab = GgsStyleGroup(mid)
            _lf = lab.font()
            _lf.setBold(True)
            lab.setFont(_lf)
            ml.addWidget(lab)
            wall = _CardWall(mid)
            wall.setObjectName("GgsStyleItems")
            wall.picked.connect(
                lambda _it, _w=wall: self._on_item_picked(_w, _it))
            ml.addWidget(wall, 1)
            self._walls.append((_builtin, lab, wall))
        split.addWidget(mid)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        rl.addWidget(QLabel(_tr("预览")))
        self.lbl_preview = GgsStylePreview()
        self.lbl_preview.setMinimumHeight(_BIG.height() + 8)
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rl.addWidget(self.lbl_preview)

        rl.addWidget(QLabel(_tr("名称")))
        self.ed_title = GgsStyleTitle()
        self.ed_title.textChanged.connect(self._on_title_changed)
        rl.addWidget(self.ed_title)

        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(4)
        rl.addWidget(self.form_host)
        self._build_detail_actions(rl)
        rl.addStretch(1)
        scroll = GgsStyleScroll()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(right)
        split.addWidget(scroll)
        split.setSizes([150, 380, 370])
        root.addWidget(split, 1)

    def _build_preset_toolbar(self):
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(4)
        self.cmb_kind_filter = GgsStyleKindFilter()
        self.cmb_kind_filter.blockSignals(True)
        for label, key in _KIND_FILTERS:
            self.cmb_kind_filter.addItem(_tr(label), key)
        self.cmb_kind_filter.blockSignals(False)
        self.cmb_kind_filter.currentIndexChanged.connect(
            lambda _i: self._load_items())
        bar.addWidget(self.cmb_kind_filter)

        self.ed_search = GgsStyleSearch()
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.setPlaceholderText(_tr("搜索名称…"))
        self.ed_search.textChanged.connect(lambda _t: self._load_items())
        bar.addWidget(self.ed_search, 1)

        self.cmb_view = GgsStyleViewMode()
        self.cmb_view.blockSignals(True)
        for key, label in _VIEW_CHOICES:
            self.cmb_view.addItem(_tr(label), key)
        self.cmb_view.blockSignals(False)
        self.cmb_view.setToolTip(_tr("预设的显示方式"))
        self.cmb_view.currentIndexChanged.connect(self._on_view_mode)
        bar.addWidget(self.cmb_view)
        return bar

    def _on_view_mode(self, *_a):
        key = (self._item or {}).get("key")
        mode = self.cmb_view.currentData() or MODE_GRID
        for _b, _lab, wall in self._walls:
            wall.set_display_mode(mode)
        self._load_items()
        if key:
            self._select_visible(key)

    def _build_status(self, root):
        self.lbl_status = GgsStyleStatus("")
        self.lbl_status.setWordWrap(False)
        self.lbl_status.setVisible(False)
        root.addWidget(self.lbl_status)

    def _build_footer(self, root):
        foot = QHBoxLayout()
        foot.setSpacing(6)
        self.btn_new = GgsStandardButton(
            "new", _tr("新建"), slot=self._on_new)
        self.btn_copy = GgsStandardButton(
            "copy_features", _tr("复制为自定义"), slot=self._on_copy)
        foot.addWidget(self.btn_new)
        foot.addWidget(self.btn_copy)
        foot.addStretch(1)
        self.btn_import = GgsStandardButton(
            "open", _tr("导入…"), slot=self._on_import)
        self.btn_export = GgsStandardButton(
            "export", _tr("导出…"), slot=self._on_export)
        self.btn_close = GgsStandardButton(
            "dock_close", _tr("关闭"), slot=self.reject)
        foot.addWidget(self.btn_import)
        foot.addWidget(self.btn_export)
        foot.addSpacing(12)
        foot.addWidget(self.btn_close)
        root.addLayout(foot)

    def _build_detail_actions(self, root):
        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_ramp = GgsStyleEditRamp(_tr("编辑色带…"))
        self.btn_ramp.clicked.connect(self._on_edit_ramp)
        row.addWidget(self.btn_ramp)
        self.btn_save = GgsStandardButton(
            "save", _tr("保存"), slot=self._on_save)
        row.addWidget(self.btn_save)
        self.btn_del = GgsStandardButton(
            "delete", _tr("删除"), slot=self._on_delete)
        row.addWidget(self.btn_del)
        row.addStretch(1)
        root.addLayout(row)
        self._refresh_buttons()

    def _load_categories(self):
        want = self._category
        self._loading = True
        self.lst_cat.clear()
        row = 0
        for i, c in enumerate(lib.CATEGORIES):
            its = lib.items(c)
            it = QListWidgetItem(_tr(lib.CATEGORY_TITLES[c]))
            it.setData(Qt.ItemDataRole.UserRole, c)
            it.setData(Qt.ItemDataRole.UserRole + 1, len(its))
            ic = _category_icon(c, its, self._dark, 14)
            if ic is not None:
                it.setIcon(ic)
            self.lst_cat.addItem(it)
            if c == want:
                row = i
        self.lst_cat.setCurrentRow(row)
        self._category = lib.CATEGORIES[row]
        self._loading = False
        self.cmb_kind_filter.setEnabled(self._category == "symbol")
        self._load_items()

    def _on_category_changed(self, row):
        if getattr(self, "_loading", False) or row < 0:
            return
        it = self.lst_cat.item(row)
        if it is None:
            return
        self._category = it.data(Qt.ItemDataRole.UserRole)
        self.cmb_kind_filter.setEnabled(self._category == "symbol")
        self._load_items()

    def _kind_filter(self):
        if self._category != "symbol":
            return ""
        return self.cmb_kind_filter.currentData() or ""

    def _search_text(self):
        return (self.ed_search.text() or "").strip().casefold()

    def _load_items(self):
        want = self._kind_filter()
        query = self._search_text()
        rows = []
        for it in lib.items(self._category):
            if want and self._category == "symbol" and it.get("kind") != want:
                continue
            if query and query not in _preview_title(it).casefold():
                continue
            rows.append(it)
        self._item = None
        first = None
        for builtin, lab, wall in self._walls:
            part = [x for x in rows if bool(x.get("builtin")) is builtin]
            wall.fill(part, self._category, self._dark)
            name = _tr("内置样式") if builtin else _tr("我的样式")
            lab.setText(_tr("{0}（{1}）").format(name, len(part)))
            show = bool(part)
            lab.setVisible(show)
            wall.setVisible(show)
            if first is None and part:
                first = part[0]
        if first is not None:
            self._select_visible(first["key"])
        else:
            self._fill_detail(None)
            self._refresh_buttons()

    def _on_item_picked(self, wall, item):
        for _b, _lab, w in self._walls:
            if w is not wall:
                w.unselect()
        self._item = item
        self._fill_detail(item)

    def _fill_detail(self, item):
        self._loading = True
        try:
            self._fill_detail_body(item)
        finally:
            self._loading = False

    def _fill_detail_body(self, item):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._editors = {}
        self._item = item
        if item is None:
            self.ed_title.setText("")
            self.ed_title.setEnabled(False)
            self.lbl_preview.setPixmap(QPixmap())
            self._dirty = False
            self._ramp_stops = None
            self._ramp_kind = None
            self.lbl_ramp_stops = None
            self._refresh_buttons()
            return
        editable = not item.get("builtin")
        self.ed_title.setEnabled(editable)
        self.ed_title.setText(_tr(item.get("title", item["key"])))
        for name, spec in lib.schema(self._category).items():
            w = _make_editor(name, spec, item.get(name), self._on_edit)
            w.setEnabled(editable)
            self._editors[name] = w
            if spec["type"] == "color":
                field = _color_row(w)
            else:
                field = _left_row(w)
            self.form.addRow(_form_label(_field_title(name)), field)
        if self._category == "ramp":
            self._ramp_stops = None
            self._ramp_kind = None
            self.lbl_ramp_stops = QLabel("")
            self.lbl_ramp_stops.setWordWrap(True)
            self._refresh_ramp_label()
            self.form.addRow(_form_label(_tr("色标")), self.lbl_ramp_stops)
        else:
            self._ramp_stops = None
            self._ramp_kind = None
            self.lbl_ramp_stops = None
        self._dirty = False
        self._refresh_preview()
        self._refresh_buttons()

    def _values(self):
        out = {}
        for name, spec in lib.schema(self._category).items():
            w = self._editors.get(name)
            if w is None:
                continue
            t = spec["type"]
            if t == "color":
                out[name] = w.color()
            elif t == "bool":
                out[name] = w.isChecked()
            elif t in ("float", "int"):
                out[name] = w.value()
            elif t == "choice":
                out[name] = w.currentData()
            elif isinstance(w, GgsComboBox):
                out[name] = ggs_combo_value(w)
            else:
                out[name] = w.text()
        return out

    def _on_edit(self, *_a):
        if self._loading:
            return
        self._dirty = True
        self._refresh_preview()
        self._refresh_buttons()

    def _on_title_changed(self, _t):
        if self._loading:
            return
        self._dirty = True
        self._refresh_buttons()

    def _live_item(self):
        if self._item is None:
            return None
        d = dict(self._item)
        d.update(self._values())
        d["title"] = self.ed_title.text()
        if self._category == "ramp" and getattr(self, "_ramp_stops", None):
            d["stops"] = [(float(p), str(c)) for p, c in self._ramp_stops]
        return d

    def _refresh_preview(self):
        d = self._live_item()
        if d is None:
            self.lbl_preview.setPixmap(QPixmap())
            return
        self.lbl_preview.setPixmap(_preview_pixmap(
            self._category, d, self._dark, _BIG.width(), _BIG.height()))

    def _refresh_buttons(self):
        for _name in ("btn_new", "btn_copy", "btn_save", "btn_del", "btn_ramp"):
            if not hasattr(self, _name):
                return
        item = self._item
        user = bool(item and not item.get("builtin"))
        self.btn_copy.setEnabled(bool(item and item.get("builtin")))
        self.btn_save.setEnabled(bool(user and self._dirty))
        self.btn_del.setEnabled(bool(user))
        self.btn_new.setEnabled(True)
        self.btn_ramp.setVisible(self._category == "ramp"
                                 and item is not None)
        self.btn_ramp.setEnabled(bool(user))
        self._update_hint()

    def _update_hint(self):
        if self._category == "ramp":
            text = ""
        else:
            text = _tr("内置预设只读")
        self.lbl_hint.setText(text)
        self.lbl_hint.setToolTip(text)

    @staticmethod
    def _as_stop_pairs(stops):
        out = []
        try:
            items = list(stops or [])
        except TypeError:
            exc_note("_as_stop_pairs @ ggis/ui/dialogs/style_manager.py:861")
            return out
        for i, st in enumerate(items):
            try:
                if isinstance(st, (tuple, list)) and len(st) >= 2:
                    pos = max(0.0, min(1.0, float(st[0])))
                    out.append((pos, str(st[1])))
                else:
                    n = len(items)
                    out.append(((i / (n - 1)) if n > 1 else 0.5, str(st)))
            except (TypeError, ValueError):
                exc_note("_as_stop_pairs @ ggis/ui/dialogs/style_manager.py:871")
                continue
        return out

    def _ramp_saved(self, item):
        code = str((item or {}).get("key") or "")
        if _user_ramps.is_user(code):
            st = _user_ramps.stops_of(code)
            if st:
                return self._as_stop_pairs(st)
        return self._as_stop_pairs(lib.ramp_stops(code))

    def _ramp_current(self):
        if getattr(self, "_ramp_stops", None):
            return list(self._ramp_stops)
        return self._ramp_saved(self._item)

    def _ramp_current_kind(self):
        if getattr(self, "_ramp_kind", None):
            return self._ramp_kind
        code = str((self._item or {}).get("key") or "")
        if _user_ramps.is_user(code):
            return _user_ramps.kind_of(code)
        return _user_ramps.KIND_CONTINUOUS

    def _refresh_ramp_label(self):
        lbl = getattr(self, "lbl_ramp_stops", None)
        if lbl is None:
            return
        try:
            stops = self._ramp_current()
            pairs = self._as_stop_pairs(stops)
            txt = " ".join(c for _p, c in pairs)
            dirty = bool(getattr(self, "_ramp_stops", None))
            lbl.setText(txt)
            lbl.setToolTip(_tr("共 {0} 个色标").format(len(pairs)))
            _f = lbl.font()
            _f.setItalic(dirty)
            lbl.setFont(_f)
        except RuntimeError:
            exc_note("_refresh_ramp_label @ ggis/ui/dialogs/style_manager.py:925")
            self.lbl_ramp_stops = None

    def _on_edit_ramp(self):
        if self._item is None or self._item.get("builtin"):
            return
        try:
            from .color_ramp import GgsColorRampDialog
        except Exception:
            _log.exception("silent exception in _on_edit_ramp")
            self.show_hint(_tr("色带编辑器不可用"))
            return
        dlg = GgsColorRampDialog(
            stops=self._ramp_current(),
            name=self.ed_title.text().strip() or self._item.get("key", ""),
            parent=self, kind=self._ramp_current_kind())
        if dlg.exec() != int(GgsDialog.DialogCode.Accepted):
            return
        stops = self._as_stop_pairs(dlg.stops())
        if len(stops) < 2:
            self.show_hint(_tr("色标至少要有两个"))
            return
        self._ramp_stops = stops
        self._ramp_kind = dlg.ramp_kind()
        _nm = str(dlg.ramp_name() or "").strip()
        if _nm:
            self.ed_title.setText(_nm)
        self._dirty = True
        self._refresh_ramp_label()
        self._refresh_preview()
        self._refresh_buttons()
        self.show_hint(_tr("色标已改"))

    def _unique_ramp_name(self, base):
        used = {str(i.get("title") or "") for i in lib.items("ramp")}
        n = 1
        while _tr(base).format(n) in used:
            n += 1
        return _tr(base).format(n)

    def _add_ramp(self, title, stops, kind, hint):
        code = _user_ramps.save(title, stops, kind)
        if not code:
            self.show_hint(_tr("色带保存失败"))
            return
        lib.add("ramp", {"key": code, "title": title})
        self._reload(select_key=code)
        self.show_hint(hint.format(title))

    def _new_ramp(self):
        title = self._unique_ramp_name("我的色带 {0}")
        keys = lib.ramp_keys()
        stops = list(lib.ramp_stops(keys[0])) if keys else []
        self._add_ramp(title, stops, _user_ramps.KIND_CONTINUOUS,
                       _tr("已新建：{0}"))

    def _copy_ramp(self, item):
        title = _tr("{0} 副本").format(item.get("title", ""))
        self._add_ramp(title, self._ramp_saved(item),
                       self._ramp_current_kind(), _tr("已复制：{0}"))

    def _save_ramp(self):
        title = (self.ed_title.text().strip()
                 or str(self._item.get("title") or "").strip())
        stops = self._ramp_current()
        if not title or len(stops) < 2:
            self.show_hint(_tr("色带保存失败"))
            return
        old = str(self._item.get("key") or "")
        code = _user_ramps.save(title, stops, self._ramp_current_kind())
        if not code:
            self.show_hint(_tr("色带保存失败"))
            return
        if _user_ramps.is_user(old) and old != code:
            try:
                _user_ramps.remove(old)
            except Exception:
                _log.exception("silent exception in _save_ramp")
            lib.remove("ramp", old)
        lib.add("ramp", {"key": code, "title": title})
        self._ramp_stops = None
        self._ramp_kind = None
        self._reload(select_key=code)
        self.show_hint(_tr("已保存：{0}").format(title))

    def _new_kind(self):
        want = self._kind_filter()
        if want in lib.schema("symbol")["kind"]["options"]:
            return want
        return lib.schema("symbol")["kind"]["default"]

    def _on_new(self):
        if self._category == "ramp":
            self._new_ramp()
            return
        values = {}
        for name, spec in lib.schema(self._category).items():
            values[name] = spec["default"]
        if self._category == "symbol":
            values["kind"] = self._new_kind()
        n = 1
        used = {i["title"] for i in lib.items(self._category)}
        while _tr("我的{0} {1}").format(
                _tr(_category_word(self._category)), n) in used:
            n += 1
        item = lib.make(self._category, title=_tr("我的{0} {1}").format(
            _tr(_category_word(self._category)), n), **values)
        lib.add(self._category, item)
        self._reload(select_key=item["key"])

    def _on_copy(self):
        if self._item is None:
            return
        if self._category == "ramp":
            self._copy_ramp(self._item)
            return
        d = dict(self._live_item())
        d["key"] = ""
        d["title"] = _tr("{0} 副本").format(d.get("title", ""))
        item = lib.make(self._category, title=d["title"],
                        **{k: v for k, v in d.items()
                           if k in lib.schema(self._category)})
        lib.add(self._category, item)
        self._reload(select_key=item["key"])

    def _on_save(self):
        if self._item is None or self._item.get("builtin"):
            return
        if self._category == "ramp":
            self._save_ramp()
            return
        d = dict(self._item)
        d.update(self._values())
        d["title"] = self.ed_title.text().strip() or d["key"]
        lib.add(self._category, d)
        self._reload(select_key=d["key"])
        self.show_hint(_tr("已保存：{0}").format(d["title"]))

    def _on_delete(self):
        if self._item is None or self._item.get("builtin"):
            return
        title = self._item.get("title", "")
        if QMessageBox.question(
                self, _tr("删除样式"),
                _tr("确定删除自定义样式「{0}」？").format(title)) \
                != QMessageBox.StandardButton.Yes:
            return
        if self._category == "ramp":
            try:
                _user_ramps.remove(self._item["key"])
            except Exception:
                _log.exception("silent exception in _on_delete")
        lib.remove(self._category, self._item["key"])
        self._reload()

    def _reload(self, select_key=None):
        self._load_categories()
        if select_key is not None:
            self.select_key(select_key)

    def select_key(self, key):
        if self._select_visible(key):
            return True
        if self._category == "symbol" and self._kind_filter():
            for i in range(self.cmb_kind_filter.count()):
                if self.cmb_kind_filter.itemData(i) == "":
                    if self.cmb_kind_filter.currentIndex() != i:
                        self.cmb_kind_filter.setCurrentIndex(i)
                    break
            if self._select_visible(key):
                return True
        if self._search_text():
            self.ed_search.clear()
            return self._select_visible(key)
        return False

    def _select_visible(self, key):
        for _b, _lab, wall in getattr(self, "_walls", []):
            if wall.pick_key(key):
                return True
        return False

    def show_hint(self, text):
        text = str(text or "")
        self.lbl_status.setText(text)
        self.lbl_status.setToolTip(text)
        self.lbl_status.setVisible(bool(text))

    def _on_export(self):
        path, _f = QFileDialog.getSaveFileName(
            self, _tr("导出样式库"), "gmagis_styles.json",
            _tr("JSON 文件 (*.json)"))
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(lib.export_json(include_builtin=True))
        except Exception as e:
            QMessageBox.warning(self, _tr("导出失败"), str(e))
            return
        self.show_hint(_tr("已导出样式库：{0}").format(
            os.path.basename(path)))

    def _on_import(self):
        path, _f = QFileDialog.getOpenFileName(
            self, _tr("导入样式库"), "", _tr("JSON 文件 (*.json)"))
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                n = lib.import_json(f.read())
        except Exception as e:
            QMessageBox.warning(self, _tr("导入失败"), str(e))
            return
        self._reload()
        self.show_hint(_tr("已导入 {0} 条样式").format(n))



class GgsStyleCats(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleCats")
class GgsStyleEditRamp(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleEditRamp")
class GgsStyleGroup(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleGroup")
class GgsStyleHint(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleHint")
class GgsStyleKindFilter(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleKindFilter")
class GgsStylePreview(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStylePreview")
class GgsStyleScroll(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleScroll")
class GgsStyleSearch(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleSearch")
class GgsStyleStatus(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleStatus")
class GgsStyleTitle(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleTitle")
class GgsStyleViewMode(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStyleViewMode")
