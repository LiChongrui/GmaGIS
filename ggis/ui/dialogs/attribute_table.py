# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import numpy as np
from PySide6.QtCore import (QAbstractTableModel, QItemSelection,
                            QItemSelectionModel, QModelIndex, QSize, Qt, Signal)
from PySide6.QtGui import QBrush, QColor, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                               QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QHBoxLayout, QHeaderView,
                               QInputDialog, QLabel, QLineEdit,
                               QListWidgetItem, QMenu, QSizePolicy,
                               QSpinBox, QTableWidget, QTableWidgetItem,
                               QTableView, QToolButton, QVBoxLayout,
                               QWidget, QTabWidget)

from ggis.core.app import i18n
from ggis.core.expr.expression import check_expression, compile_expression
from ggis.core.model.field import fields_from_layer, GgsField
from ggis.core.model.selection import GgsSelection
from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.base.dialog import GgsDialog, GgsMsgBox
from .field_calculator import GgsFieldCalculatorDialog
from ggis.ui.views.map.dialogs.select_by_expression import GgsSelectByExpressionDialog
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.widgets.itemviews import GgsTableWidget
from ggis.common.widgets.separators import GgsSepV
from ggis.common.styling import icons as _icons
import logging
from PySide6.QtWidgets import QListWidget
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_ATTR_PER_LAYER = True

PAGE_SIZES = [("全部（虚拟滚动）", 0), ("每页 200 行", 200),
              ("每页 1000 行", 1000), ("每页 5000 行", 5000)]

SEL_BG = QColor(255, 225, 77, 46)


def _haystack_of(n, attrs, names):
    out = []
    for i in range(n):
        a = attrs[i] if i < len(attrs) else None
        if isinstance(a, dict):
            parts = []
            for nm in names:
                v = a.get(nm)
                if v is not None and v != "":
                    parts.append(str(v))
            out.append("\n".join(parts).lower())
        else:
            out.append("")
    return out


def _numbers_of(n, attrs, name):
    arr = np.full(n, np.nan, dtype=np.float64)
    for i in range(min(n, len(attrs))):
        a = attrs[i]
        if not isinstance(a, dict):
            continue
        v = a.get(name)
        if v is None or isinstance(v, bool):
            continue
        try:
            arr[i] = float(v)
        except (TypeError, ValueError):
            exc_note("_numbers_of @ ggis/ui/dialogs/attribute_table.py:114")
            continue
    return arr


def _dense_mask(n, fids):
    if fids is None:
        return None
    out = np.zeros(n, dtype=bool)
    if len(fids) == 0:
        return out
    arr = np.fromiter((int(f) for f in fids), dtype=np.int64)
    arr = arr[(arr >= 0) & (arr < n)]
    out[arr] = True
    return out


def _text_mask_of(n, attrs, names, text, text_col, hay):
    needle = str(text or "").lower()
    if not needle:
        return None
    if 0 <= int(text_col) < len(names):
        name = names[int(text_col)]
        out = np.zeros(n, dtype=bool)
        for i in range(min(n, len(attrs))):
            a = attrs[i]
            if not isinstance(a, dict):
                continue
            v = a.get(name)
            if v is not None and needle in str(v).lower():
                out[i] = True
        return out
    if hay is None:
        hay = _haystack_of(n, attrs, names)
    return np.fromiter((needle in s for s in hay), dtype=bool, count=n)


def _rebuild_view(spec, hay=None, num=None):
    n = int(spec["n"])
    attrs = spec.get("attrs") or []
    names = list(spec.get("names") or [])
    mask = np.ones(n, dtype=bool)

    sub = _dense_mask(n, spec.get("subset"))
    if sub is not None:
        mask &= sub
    if spec.get("only_selected"):
        sel = _dense_mask(n, spec.get("selection") or [])
        if sel is not None:
            mask &= sel

    node = spec.get("expr_node")
    if node is not None:
        from ggis.core.expr.expression import select_mask
        mask &= select_mask(node, attrs)

    text = spec.get("text") or ""
    if text:
        text_col = int(spec.get("text_col", -1))
        if hay is None and not (0 <= text_col < len(names)):
            hay = _haystack_of(n, attrs, names)
        tm = _text_mask_of(n, attrs, names, text, text_col, hay)
        if tm is not None:
            mask &= tm

    idx = np.nonzero(mask)[0].astype(np.int64)

    col = int(spec.get("sort_col", -1))
    numeric = list(spec.get("numeric") or [])
    sort_cols = spec.get("sort_cols") or []
    if (sort_cols or (col >= 0)) and idx.size:
        if not sort_cols and col >= 0:
            sort_cols = [(col, bool(spec.get("sort_desc")))]
        for (scol, sdesc) in reversed(sort_cols):
            if not (0 <= int(scol) < len(numeric)):
                continue
            name = names[int(scol)] if int(scol) < len(names) else ""
            if numeric[int(scol)]:
                vals = None if num is None else num.get(int(scol))
                if vals is None:
                    vals = _numbers_of(n, attrs, name)
                    if num is None:
                        num = {}
                    num[int(scol)] = vals
                v = vals[idx]
                order = np.argsort(np.where(np.isfinite(v), v, np.inf),
                                   kind="stable")
            else:
                keys = []
                for i in idx:
                    a = attrs[int(i)] if int(i) < len(attrs) else None
                    v = a.get(name) if isinstance(a, dict) else None
                    keys.append((1, "") if v is None else (0, str(v)))
                order = np.asarray(sorted(range(len(keys)),
                                          key=lambda k: keys[k]),
                                   dtype=np.int64)
            if sdesc:
                order = order[::-1]
            idx = idx[order]
    return idx, hay, num


class GgsAttributeTableModel(QAbstractTableModel):

    countChanged = Signal()
    busyChanged = Signal(bool)

    def __init__(self, layer, parent=None):
        super().__init__(parent)
        self._layer = layer
        self._fields = fields_from_layer(layer)
        self._attrs = layer.attrs()
        self._n = max(layer.feature_count(), len(self._attrs))
        self._fids = layer.geoms()

        self._view = np.arange(self._n, dtype=np.int64)
        self._expr_node = None
        self._expr_text = ""
        self._text = ""
        self._text_col = -1
        self._text_node = None
        self._only_selected = False
        self._page = 0
        self._page_size = 0
        self._haystack = None
        self._num_cache = {}
        self._seq = 0
        self._pending = None
        self._busy = False
        self._editable = False
        self._cell_edit_cb = None
        self._sort_cols = []
        try:
            self._rebuild()
        except Exception:
            _log.exception("silent exception in __init__")

    def is_busy(self):
        return bool(self._busy)

    def layer(self):
        return self._layer

    def fields(self):
        return self._fields

    def total_rows(self):
        return self._n

    def visible_rows(self):
        return int(self._view.size)

    def fid_at(self, row):
        if 0 <= row < self._view.size:
            return int(self._view[row])
        return -1

    def row_at(self, fid):
        hit = np.nonzero(self._view == fid)[0]
        return int(hit[0]) if hit.size else -1

    def page(self):
        return self._page

    def page_count(self):
        if self._page_size <= 0:
            return 1
        return max(1, (int(self._view.size) + self._page_size - 1)
                   // self._page_size)

    def set_page(self, page):
        pc = self.page_count()
        page = max(0, min(int(page), pc - 1))
        if page == self._page:
            return
        self._page = page
        self._reset()

    def set_page_size(self, size):
        size = max(0, int(size))
        if size == self._page_size:
            return
        self._page_size = size
        self._page = 0
        self._reset()

    def page_size(self):
        return self._page_size

    def _page_slice(self):
        if self._page_size <= 0:
            return 0, int(self._view.size)
        start = self._page * self._page_size
        return start, min(start + self._page_size, int(self._view.size))

    def page_slice(self):
        return self._page_slice()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        start, stop = self._page_slice()
        return max(0, stop - start)

    def columnCount(self, parent=QModelIndex()):
        return len(self._fields)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                fid = self.fid_at(self._page_slice()[0] + section)
                return str(fid + 1) if fid >= 0 else ""
            if role == Qt.ItemDataRole.ToolTipRole:
                return _tr("要素 ID")
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._fields):
                return self._fields[section].name
            return ""
        if role == Qt.ItemDataRole.ToolTipRole:
            if 0 <= section < len(self._fields):
                f = self._fields[section]
                return "%s (%s)" % (f.name, i18n.tr(
                    _TYPE_LABELS_ZH.get(f.type, f.type)))
            return None
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._page_slice()[0] + index.row()
        col = index.column()
        if not (0 <= row < self._view.size) or not (0 <= col < len(self._fields)):
            return None
        fid = int(self._view[row])
        if role == Qt.ItemDataRole.DisplayRole:
            return self._value(fid, col)
        if role == Qt.ItemDataRole.EditRole:
            return self._raw_value(fid, col)
        if role == Qt.ItemDataRole.CheckStateRole:
            fld = self._fields[col]
            if fld.type == "bool":
                return (Qt.CheckState.Checked
                        if self._raw_value(fid, col) else Qt.CheckState.Unchecked)
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            return "%s = %s" % (self._fields[col].name,
                                self._value_full(fid, col))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            f = self._fields[col]
            if f.is_numeric():
                return int(Qt.AlignmentFlag.AlignRight |
                           Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft |
                       Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.BackgroundRole:
            if self._is_selected(fid):
                return QBrush(SEL_BG)
            return None
        if role == Qt.ItemDataRole.UserRole:
            return fid
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._editable and 0 <= index.column() < len(self._fields):
            f |= Qt.ItemFlag.ItemIsEditable
            if self._fields[index.column()].type == "bool":
                f |= Qt.ItemFlag.ItemIsUserCheckable
        return f

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        self.set_sort(column, order == Qt.SortOrder.DescendingOrder)

    def set_editable(self, on):
        on = bool(on)
        if on == self._editable:
            return
        self._editable = on
        self._reset()

    def is_editable(self):
        return self._editable

    def set_cell_edit_callback(self, cb):
        self._cell_edit_cb = cb

    def _raw_value(self, fid, col):
        a = self._attrs[fid] if fid < len(self._attrs) else None
        if not isinstance(a, dict):
            return None
        return a.get(self._fields[col].name)

    def _attrs_row(self, fid):
        return self._attrs[fid] if 0 <= fid < len(self._attrs) else {}

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        row = self._page_slice()[0] + index.row()
        col = index.column()
        if not (0 <= row < self._view.size) or not (0 <= col < len(self._fields)):
            return False
        fid = int(self._view[row])
        fld = self._fields[col]
        if role == Qt.ItemDataRole.CheckStateRole:
            new_val = (value == Qt.CheckState.Checked)
        elif role == Qt.ItemDataRole.EditRole:
            if isinstance(value, bool) or isinstance(value, str):
                new_val = fld.coerce(value)
            else:
                new_val = value
        else:
            return False
        if self._cell_edit_cb is not None:
            try:
                self._cell_edit_cb(fid, fld.name, new_val)
            except Exception:
                _log.exception("silent exception in setData")
                return False
        self.dataChanged.emit(
            index, index,
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole,
             Qt.ItemDataRole.CheckStateRole])
        return True

    def sort_column(self):
        return self._sort_cols[0][0] if self._sort_cols else -1

    def sort_descending(self):
        return bool(self._sort_cols[0][1]) if self._sort_cols else False

    def sort_levels(self):
        return list(self._sort_cols)

    def set_sort(self, column, descending=False):
        if column is not None and int(column) < 0:
            column = -1
        if column is None or int(column) < 0:
            self._sort_cols = []
        else:
            self._sort_cols = [(int(column), bool(descending))]
        self._rebuild()

    def add_sort_level(self, column, descending=False):
        column = int(column)
        if column < 0:
            return
        for i, (c, d) in enumerate(self._sort_cols):
            if c == column:
                self._sort_cols[i] = (c, not d)
                self._rebuild()
                return
        self._sort_cols.append((column, bool(descending)))
        self._rebuild()

    def clear_sort(self):
        self._sort_cols = []
        self._rebuild()

    def reload(self):
        self._fields = fields_from_layer(self._layer)
        self._attrs = self._layer.attrs()
        self._n = max(self._layer.feature_count(), len(self._attrs))
        self._fids = self._layer.geoms()
        self.invalidate_cache()
        self.beginResetModel()
        self._view = np.arange(self._n, dtype=np.int64)
        self.endResetModel()
        self._rebuild()
        self.countChanged.emit()

    def _value(self, fid, col):
        a = self._attrs[fid] if fid < len(self._attrs) else None
        if not isinstance(a, dict):
            return ""
        return self._fields[col].display(a.get(self._fields[col].name))

    def _value_full(self, fid, col):
        a = self._attrs[fid] if fid < len(self._attrs) else None
        if not isinstance(a, dict):
            return ""
        return self._fields[col].display_full(a.get(self._fields[col].name))

    def _is_selected(self, fid):
        try:
            return GgsSelection.instance().is_selected(self._layer, fid)
        except Exception:
            _log.exception("silent exception in _is_selected")
            return False

    def invalidate_cache(self):
        self._haystack = None
        self._num_cache.clear()

    def set_text_filter(self, text, column=-1):
        text = (text or "").strip()
        if text == self._text and int(column) == self._text_col:
            return
        self._text = text
        self._text_col = int(column)
        self._rebuild()

    def set_expression(self, text):
        text = (text or "").strip()
        node = None
        if text:
            err = check_expression(text, self._fields)
            if err:
                return err
            node = compile_expression(text, self._fields)
        self._expr_text = text
        self._expr_node = node
        self._rebuild()
        return None

    def expression_text(self):
        return self._expr_text

    def set_only_selected(self, on):
        on = bool(on)
        if on == self._only_selected:
            return
        self._only_selected = on
        self._rebuild()

    def only_selected(self):
        return self._only_selected

    def _reset(self):
        self.beginResetModel()
        self.endResetModel()
        self.countChanged.emit()

    def _snapshot(self):
        sub = None
        try:
            sub = self._layer.subset_fids()
        except Exception:
            _log.exception("silent exception in _snapshot")
            sub = None
        subset = None if sub is None else [int(f) for f in sub]
        sel = None
        if self._only_selected:
            try:
                sel = [int(f) for f in
                      GgsSelection.instance().fids(self._layer)]
            except Exception:
                _log.exception("silent exception in _snapshot")
                sel = []
        return {
            "n": int(self._n),
            "attrs": self._attrs,
            "names": [f.name for f in self._fields],
            "numeric": [bool(f.is_numeric()) for f in self._fields],
            "subset": subset,
            "only_selected": bool(self._only_selected),
            "selection": sel,
            "expr_node": self._expr_node,
            "text": self._text,
            "text_col": int(self._text_col),
            "sort_col": -1,
            "sort_desc": False,
            "sort_cols": [(int(c), bool(d)) for c, d in self._sort_cols],
        }

    def _rebuild(self):
        spec = self._snapshot()
        from ...exec import guard as _g
        if not (_g.ui_mode() and _g.on_ui_thread()):
            return self._apply_view(*_rebuild_view(
                spec, self._haystack, dict(self._num_cache)))
        return self._rebuild_async(spec)

    def _rebuild_async(self, spec):
        from ...exec import task as _et
        prev = getattr(self, "_pending", None)
        if prev is not None and not prev.done:
            prev.cancel()
        self._seq += 1
        token = self._seq
        self._set_busy(True)
        t = _et.submit(_rebuild_view, spec, self._haystack,
                       dict(self._num_cache), name=_tr("筛选中…"), kind="cpu")
        self._pending = t
        t.on_done(lambda ev: self._on_view_ready(ev, token))
        t.on_fail(lambda ev: self._on_view_failed(ev, token))
        return t

    def _on_view_ready(self, ev, token):
        if token != self._seq or ev.get("cancelled"):
            return
        res = ev.get("result")
        if res:
            self._apply_view(*res)
        self._set_busy(False)

    def _on_view_failed(self, ev, token):
        if token != self._seq:
            return
        self._set_busy(False)

    def _set_busy(self, on):
        on = bool(on)
        if on == self._busy:
            return
        self._busy = on
        try:
            self.busyChanged.emit(on)
        except Exception:
            _log.exception("silent exception in _set_busy")

    def _apply_view(self, idx, hay, num):
        if hay is not None:
            self._haystack = hay
        if num:
            if len(self._num_cache) > 64:
                self._num_cache.clear()
            self._num_cache.update(num)
        self.beginResetModel()
        self._view = idx
        self._page = min(self._page, self.page_count() - 1)
        self._page = max(0, self._page)
        self.endResetModel()
        self.countChanged.emit()

    def refresh_selection_marks(self):
        start, stop = self._page_slice()
        if stop <= start:
            return
        top = self.index(start, 0)
        bottom = self.index(stop - 1, max(0, len(self._fields) - 1))
        self.dataChanged.emit(top, bottom,
                              [Qt.ItemDataRole.BackgroundRole])

    def refilter_by_selection(self):
        prev = getattr(self, "_pending", None)
        if prev is not None and not getattr(prev, "done", True):
            try:
                prev.cancel()
            except Exception:
                _log.exception("silent exception in refilter_by_selection")
        self._seq += 1
        spec = self._snapshot()
        idx, hay, num = _rebuild_view(
            spec, self._haystack, dict(self._num_cache))
        self._apply_view(idx, hay, num)
        self._set_busy(False)

    def refresh_data(self):
        self._attrs = self._layer.attrs()
        self._n = max(self._layer.feature_count(), len(self._attrs))
        self.invalidate_cache()
        self._rebuild()


_TYPE_LABELS_ZH = {
    "integer": "整数", "real": "浮点", "string": "文本", "date": "日期",
    "datetime": "时间", "bool": "布尔", "binary": "二进制",
    "unknown": "未知",
}


class GgsAttributeTableView(QTableView):

    zoomToFeature = Signal(int)
    headerMenuRequested = Signal(object, int)
    cellMenuRequested = Signal(object, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsAttributeTable")
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.AnyKeyPressed |
            QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setSortingEnabled(False)
        self.setWordWrap(False)
        self.setShowGrid(True)
        self.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel)
        vh = self.verticalHeader()
        vh.setDefaultSectionSize(22)
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setHighlightSections(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hh.setStretchLastSection(False)
        hh.setSectionsClickable(True)
        hh.setSectionsMovable(True)
        hh.setSortIndicatorShown(True)
        hh.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._on_header_menu)
        self.doubleClicked.connect(self._on_double)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_cell_menu)
        vh.sectionDoubleClicked.connect(self._on_row_double)

    def _on_double(self, index):
        if not index.isValid():
            return
        m = self.model()
        if m is None:
            return
        if not (m.flags(index) & Qt.ItemFlag.ItemIsEditable):
            return

    def _on_row_double(self, row):
        m = self.model()
        if m is None:
            return
        fid = m.data(m.index(row, 0), Qt.ItemDataRole.UserRole)
        if fid is not None and int(fid) >= 0:
            self.zoomToFeature.emit(int(fid))

    def _on_cell_menu(self, pos):
        idx = self.indexAt(pos)
        if not idx.isValid():
            return
        self.cellMenuRequested.emit(self.viewport().mapToGlobal(pos),
                                    idx.row(), idx.column())

    def _on_header_menu(self, pos):
        hh = self.horizontalHeader()
        col = hh.logicalIndexAt(pos)
        if col < 0:
            return
        self.headerMenuRequested.emit(hh.mapToGlobal(pos), col)

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            return
        super().keyPressEvent(e)

    def copy_selection(self):
        sm = self.selectionModel()
        if sm is None:
            return
        rows = sorted({i.row() for i in sm.selectedIndexes()})
        cols = sorted({i.column() for i in sm.selectedIndexes()})
        m = self.model()
        if not rows or m is None:
            return
        lines = []
        for r in rows:
            lines.append("\t".join(
                str(m.data(m.index(r, c), Qt.ItemDataRole.DisplayRole) or "")
                for c in cols))
        QApplication.clipboard().setText("\n".join(lines))


_OPEN_TABLES = {}
_AUTOSIZE_ROWS = 200


class GgsAttributeTableWidget(QWidget):

    zoomToFeature = Signal(object, int)

    def __init__(self, layer, parent=None, canvas=None, host=None,
                 session_provider=None):
        super().__init__(parent)
        self._layer = layer
        self._canvas = canvas
        self._host = host
        self._session_provider = session_provider or (lambda: None)
        self._connected_session = None
        self._syncing = False
        self.setObjectName("GgsAttributeTableBody")
        self.model_ = GgsAttributeTableModel(layer, self)
        self.model_.set_cell_edit_callback(self._apply_cell_edit)
        self._build_ui()
        self._wire()
        self._ensure_session()
        self._sync_edit_state()
        self._refresh_status()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 4)
        lay.setSpacing(6)

        act = QHBoxLayout()
        act.setSpacing(4)

        def _vsep():
            return GgsSepV(self)

        self.btn_calc = GgsSmallButtonStyle1(
            "calc", _tr("字段计算器：用表达式批量计算字段值"), None, 16)
        act.addWidget(self.btn_calc)

        self.btn_fields = GgsSmallButtonStyle1(
            "new_attr", _tr("字段管理"), None, 16)
        act.addWidget(self.btn_fields)

        act.addWidget(_vsep())

        self.btn_autosize = GgsSmallButtonStyle1(
            "ruler", _tr("自动列宽"), None, 16)
        act.addWidget(self.btn_autosize)

        self.btn_clear_sort = GgsSmallButtonStyle1(
            "refresh", _tr("清除排序"), None, 16)
        act.addWidget(self.btn_clear_sort)

        act.addWidget(_vsep())

        self.btn_sel_attr = GgsSmallButtonStyle1(
            "select_attr", _tr("按属性选择：用表达式选择要素"), None, 16)
        act.addWidget(self.btn_sel_attr)

        act.addWidget(_vsep())

        self.btn_sel_all = GgsSmallButtonStyle1(
            "checkbox_on", _tr("全选"), None, 16)
        act.addWidget(self.btn_sel_all)

        self.btn_sel_inv = GgsSmallButtonStyle1(
            "invert_sel", _tr("反选"), None, 16)
        act.addWidget(self.btn_sel_inv)

        self.btn_sel_clear = GgsSmallButtonStyle1(
            "deselect", _tr("清除选择"), None, 16)
        act.addWidget(self.btn_sel_clear)

        act.addWidget(_vsep())

        self.btn_zoom_sel = GgsSmallButtonStyle1(
            "zoom_full", _tr("缩放到选中要素"), None, 16)
        act.addWidget(self.btn_zoom_sel)

        act.addStretch(1)
        lay.addLayout(act)

        tbl = QHBoxLayout()
        tbl.setSpacing(0)
        tbl.setContentsMargins(0, 0, 0, 0)
        self.view = GgsAttributeTableView(self)
        self.view.setObjectName("GgsAttributeTableView")
        self.view.setModel(self.model_)
        self.view.zoomToFeature.connect(self._on_zoom)
        self.frozen = GgsAttributeTableView(self)
        self.frozen.setObjectName("GgsAttributeTableViewFrozen")
        self._init_frozen_view()
        self.frozen.hide()
        tbl.addWidget(self.frozen, 0)
        tbl.addWidget(self.view, 1)
        lay.addLayout(tbl)

        foot = QHBoxLayout()
        foot.setSpacing(6)
        foot.setContentsMargins(0, 2, 0, 0)

        self._btn_show_all = GgsSmallButtonStyle1(
            "table", _tr("全部要素：显示该图层所有要素"), None, 16)
        self._btn_show_sel = GgsSmallButtonStyle1(
            "select_attr", _tr("所选要素：仅显示被选中的要素"), None, 16)
        self._show_grp = QButtonGroup(self)
        self._show_grp.setExclusive(True)
        self._show_grp.addButton(self._btn_show_all)
        self._show_grp.addButton(self._btn_show_sel)
        if self.model_.only_selected():
            self._btn_show_sel.setChecked(True)
        else:
            self._btn_show_all.setChecked(True)
        foot.addWidget(self._btn_show_all)
        foot.addWidget(self._btn_show_sel)
        foot.addWidget(_vsep())

        foot.addStretch(1)
        self.lbl_status = GgsAttrStatus("", self)
        foot.addWidget(self.lbl_status)
        lay.addLayout(foot)

        self._autosize_pending = True

    def _wire(self):
        self._show_grp.buttonClicked.connect(self._on_show_toggle)
        self.model_.countChanged.connect(self._refresh_status)
        self.model_.busyChanged.connect(self._refresh_status)
        self.view.horizontalHeader().sectionClicked.connect(
            self._on_header_clicked)
        self.view.headerMenuRequested.connect(self._on_header_menu)
        self.view.cellMenuRequested.connect(self._on_cell_menu)
        self.btn_calc.clicked.connect(self._open_field_calculator)
        self.btn_fields.clicked.connect(self._open_field_manager)
        self.btn_sel_all.clicked.connect(self._select_all)
        self.btn_sel_inv.clicked.connect(self._invert_selection)
        self.btn_sel_clear.clicked.connect(self._clear_selection)
        self.btn_zoom_sel.clicked.connect(self._zoom_to_selected)
        self.btn_sel_attr.clicked.connect(self._open_select_by_attr)
        self.btn_autosize.clicked.connect(self._autosize)
        self.btn_clear_sort.clicked.connect(self._on_clear_sort)
        self.view.selectionModel().selectionChanged.connect(
            self._on_table_selection)
        try:
            GgsSelection.instance().layerSelectionChanged.connect(
                self._on_map_selection)
        except Exception:
            _log.exception("silent exception in _wire")

    def showEvent(self, e):
        super().showEvent(e)
        if getattr(self, "_autosize_pending", False):
            self._autosize_pending = False
            self._autosize()

    def _on_show_toggle(self, btn):
        only = (btn is self._btn_show_sel)
        self.model_.set_only_selected(only)
        self._sync_show_state()
        self._refresh_status()

    def _sync_show_state(self):
        on_sel = self.model_.only_selected()
        self._btn_show_sel.setChecked(on_sel)
        self._btn_show_all.setChecked(not on_sel)

    def _autosize(self):
        try:
            rows = int(self.model_.rowCount())
            cols = int(self.model_.columnCount())
        except Exception:
            _log.exception("silent exception in _autosize")
            return
        n = min(rows, _AUTOSIZE_ROWS)
        try:
            hh = self.view.horizontalHeader()
            fm = self.view.fontMetrics()
        except Exception:
            _log.exception("silent exception in _autosize")
            return
        for c in range(cols):
            w = 0
            try:
                head = self.model_.headerData(
                    c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
                if head is not None:
                    w = fm.horizontalAdvance(str(head))
            except Exception:
                _log.exception("silent exception in _autosize")
            for r in range(n):
                try:
                    v = self.model_.data(self.model_.index(r, c),
                                         Qt.ItemDataRole.DisplayRole)
                except Exception:
                    _log.exception("silent exception in _autosize")
                    continue
                if v is None:
                    continue
                tw = fm.horizontalAdvance(str(v))
                if tw > w:
                    w = tw
            try:
                hh.resizeSection(c, max(70, min(w + 24, 320)))
            except Exception:
                _log.exception("silent exception in _autosize")

    def closeEvent(self, e):
        _OPEN_TABLES.pop(self._layer.id(), None)
        super().closeEvent(e)

    def _ensure_session(self):
        if self._connected_session is not None:
            return self._connected_session
        try:
            s = self._session_provider()
        except Exception:
            _log.exception("silent exception in _ensure_session")
            s = None
        if s is None:
            return None
        self._connected_session = s
        try:
            s.structureChanged.connect(self._on_session_structure)
            s.dirtyChanged.connect(self._on_session_dirty)
        except Exception:
            _log.exception("silent exception in _ensure_session")
        try:
            if not s.is_active():
                s.start()
        except Exception:
            _log.exception("silent exception in _ensure_session")
        self._sync_edit_state()
        return s

    def _session(self):
        if self._connected_session is None:
            self._ensure_session()
        return self._connected_session

    def _on_session_structure(self):
        try:
            self.model_.reload()
        except Exception:
            _log.exception("silent exception in _on_session_structure")
        self._refresh_status()

    def _on_session_dirty(self, dirty):
        self._sync_edit_state()

    def _sync_edit_state(self):
        s = self._session()
        active = bool(s is not None and s.is_active())
        self.model_.set_editable(active)
        self.btn_calc.setEnabled(True)
        self.btn_fields.setEnabled(True)
        self._refresh_status()

    def _apply_cell_edit(self, fid, name, value):
        s = self._session()
        if s is None or not s.is_active():
            self._host_msg(_tr("本图层当前不可编辑，无法执行该操作"))
            return False
        try:
            s.set_attribute(int(fid), str(name), value)
        except Exception as e:
            _log.exception("silent exception in _apply_cell_edit")
            self._host_msg(_tr("写入失败：{0}").format(e))
            return False
        return True

    def _on_header_clicked(self, col):
        if col < 0:
            return
        from PySide6.QtGui import QGuiApplication
        mods = QGuiApplication.keyboardModifiers()
        levels = self.model_.sort_levels()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            desc = False
            for c, d in levels:
                if c == col:
                    desc = not d
                    break
            self.model_.add_sort_level(col, desc)
        else:
            if len(levels) == 1 and levels[0][0] == col:
                self.model_.add_sort_level(col, not levels[0][1])
            else:
                self.model_.set_sort(col, False)
        self._sync_sort_indicator()
        self._refresh_status()

    def _sync_sort_indicator(self):
        try:
            hh = self.view.horizontalHeader()
            levels = self.model_.sort_levels()
            if not levels:
                hh.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
                return
            col, desc = levels[0]
            hh.setSortIndicator(
                col, Qt.SortOrder.DescendingOrder if desc
                else Qt.SortOrder.AscendingOrder)
        except Exception:
            _log.exception("silent exception in _sync_sort_indicator")

    def _on_clear_sort(self):
        self.model_.clear_sort()
        self._sync_sort_indicator()
        self._refresh_status()

    def _header_sort(self, col, desc):
        self.model_.set_sort(col, desc)
        self._sync_sort_indicator()
        self._refresh_status()

    def _on_header_menu(self, pos, col):
        if col < 0:
            return
        try:
            name = self.model_.fields()[col].name
        except Exception:
            _log.exception("silent exception in _on_header_menu")
            name = ""
        menu = QMenu(self)
        menu.addAction(_tr("升序排列"), lambda: self._header_sort(col, False))
        menu.addAction(_tr("降序排列"), lambda: self._header_sort(col, True))
        menu.addAction(_tr("清除排序"), self._on_clear_sort)
        menu.addSeparator()
        menu.addAction(_tr("隐藏此列"), lambda: self._hide_column(col, True))
        menu.addAction(_tr("显示所有列"), lambda: self._hide_column(col, False))
        fcols = getattr(self, "_frozen_cols", []) or []
        if col in fcols:
            menu.addAction(_tr("取消冻结"),
                           lambda: self._toggle_freeze(col))
        else:
            menu.addAction(_tr("冻结到左侧"),
                           lambda: self._toggle_freeze(col))
        menu.addSeparator()
        menu.addAction(_tr("列统计"), lambda: self._show_column_stats(col))
        menu.addAction(_tr("自动列宽"), self._autosize)
        menu.addSeparator()
        menu.addAction(_tr("管理列…"), self._show_columns_dialog)
        menu.exec(pos)

    def _on_cell_menu(self, pos, row, col):
        m = self.model_
        if row < 0 or row >= m.rowCount():
            return
        menu = QMenu(self)
        fid = m.data(m.index(row, 0), Qt.ItemDataRole.UserRole)
        if fid is not None and int(fid) >= 0:
            menu.addAction(_tr("缩放到要素"),
                           lambda: self._on_zoom(int(fid)))
        sel = GgsSelection.instance()
        menu.addAction(_tr("选中此要素"),
                       lambda: sel.add_fids(self._layer, [int(fid)]))
        menu.addAction(_tr("取消选中此要素"),
                       lambda: sel.remove_fids(self._layer, [int(fid)]))
        menu.addSeparator()
        menu.addAction(_tr("复制单元格"),
                       lambda: self._copy_cell(row, col))
        menu.addAction(_tr("复制整行"),
                       lambda: self._copy_row(row))
        menu.addSeparator()
        menu.addAction(_tr("全选"), self._select_all)
        menu.addAction(_tr("反选"), self._invert_selection)
        if self._layer is not None and self._layer.is_table():
            menu.addSeparator()
            menu.addAction(_tr("表转矢量"), self._on_table_to_layer)
        menu.exec(pos)

    def _copy_cell(self, row, col):
        m = self.model_
        v = m.data(m.index(row, col), Qt.ItemDataRole.DisplayRole)
        QApplication.clipboard().setText("" if v is None else str(v))

    def _copy_row(self, row):
        m = self.model_
        ncols = max(0, m.columnCount())
        vals = ["" if m.data(m.index(row, c), Qt.ItemDataRole.DisplayRole) is None
                else str(m.data(m.index(row, c), Qt.ItemDataRole.DisplayRole))
                for c in range(ncols)]
        QApplication.clipboard().setText("\t".join(vals))

    def _on_table_to_layer(self):
        from ggis.ui.dialogs.table_to_layer import GgsTableToLayerDialog
        dlg = GgsTableToLayerDialog(self._layer, self, host=self._host)
        dlg.setModal(True)
        if dlg.exec() == GgsDialog.Accepted:
            lyr = dlg.result_layer
            if lyr is not None and self._host is not None:
                host = self._host
                ctx = getattr(host, "ctx", None)
                if ctx is None:
                    ctx = getattr(getattr(host, "_host", None), "ctx", None)
                if ctx is not None:
                    ctx.svc("views")._on_view_method("_adopt_layer", lyr)

    def _hide_column(self, col, hide):
        if not hasattr(self, "_hidden_cols"):
            self._hidden_cols = set()
        if hide:
            self._hidden_cols.add(col)
        else:
            self._hidden_cols.discard(col)
        self._apply_col_visibility()

    def set_column_visible(self, col, visible):
        if not hasattr(self, "_hidden_cols"):
            self._hidden_cols = set()
        if visible:
            self._hidden_cols.discard(col)
        else:
            self._hidden_cols.add(col)
        self._apply_col_visibility()

    def set_frozen(self, col, frozen):
        if not hasattr(self, "_frozen_cols"):
            self._frozen_cols = []
        s = set(self._frozen_cols)
        if frozen:
            s.add(col)
        else:
            s.discard(col)
        self._frozen_cols = list(s)
        self._rebuild_frozen()

    def set_column_order(self, order):
        try:
            hh = self.view.horizontalHeader()
            for target, model_col in enumerate(order):
                cur = hh.visualIndex(model_col)
                if cur != target:
                    hh.moveSection(cur, target)
        except Exception:
            _log.exception("silent exception in set_column_order")

    def _init_frozen_view(self):
        fv = self.frozen
        try:
            fv.setModel(self.model_)
            fv.setSelectionModel(self.view.selectionModel())
            fv.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows)
            fv.setSelectionMode(
                QAbstractItemView.SelectionMode.ExtendedSelection)
            fv.setEditTriggers(self.view.editTriggers())
            fv.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            fv.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            fv.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            fv.setSortingEnabled(False)
            fv.setWordWrap(False)
            fv.setShowGrid(True)
            vh = fv.verticalHeader()
            vh.setDefaultSectionSize(22)
            vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
            vh.setHighlightSections(False)
            vh.setVisible(False)
            fh = fv.horizontalHeader()
            fh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            fh.setSectionsClickable(False)
            fh.setSectionsMovable(False)
            fh.setVisible(True)
            fv.setHorizontalScrollMode(
                QAbstractItemView.ScrollMode.ScrollPerPixel)
            fv.setVerticalScrollMode(
                QAbstractItemView.ScrollMode.ScrollPerPixel)
            fv.zoomToFeature.connect(self._on_zoom)
            fv.cellMenuRequested.connect(self._on_cell_menu)
        except Exception:
            _log.exception("silent exception in _init_frozen_view")
        self._frozen_cols = []
        self._hidden_cols = set()
        self._frozen_scrolling = False
        try:
            self.view.verticalScrollBar().valueChanged.connect(
                lambda v: self._sync_frozen_scroll(v, "main"))
            fv.verticalScrollBar().valueChanged.connect(
                lambda v: self._sync_frozen_scroll(v, "frozen"))
        except Exception:
            _log.exception("silent exception in _init_frozen_view")

    def _rebuild_frozen(self):
        try:
            fcols = set(getattr(self, "_frozen_cols", []) or [])
            hh = self.view.horizontalHeader()
            fh = self.frozen.horizontalHeader()
            n = self.model_.columnCount()
            if not fcols:
                self._apply_col_visibility()
                self.frozen.hide()
                return
            width = 0
            for c in range(n):
                is_f = c in fcols
                hh.setSectionHidden(c, is_f)
                fh.setSectionHidden(c, not is_f)
                if is_f:
                    w = hh.sectionSize(c)
                    if w <= 0:
                        w = 110
                    fh.resizeSection(c, w)
                    width += w
            self.frozen.setFixedWidth(min(max(width + 4, 60), 640))
            self.frozen.show()
        except Exception:
            _log.exception("silent exception in _rebuild_frozen")

    def _apply_col_visibility(self):
        try:
            hh = self.view.horizontalHeader()
            n = self.model_.columnCount()
            fcols = set(getattr(self, "_frozen_cols", []) or [])
            hidden = set(getattr(self, "_hidden_cols", set()) or set())
            for c in range(n):
                hh.setSectionHidden(c, (c in hidden) and (c not in fcols))
        except Exception:
            _log.exception("silent exception in _apply_col_visibility")

    def _sync_frozen_scroll(self, value, src):
        if self._frozen_scrolling:
            return
        self._frozen_scrolling = True
        try:
            if src == "main":
                self.frozen.verticalScrollBar().setValue(value)
            else:
                self.view.verticalScrollBar().setValue(value)
        except Exception:
            _log.exception("silent exception in _sync_frozen_scroll")
        finally:
            self._frozen_scrolling = False

    def _toggle_freeze(self, col):
        if col < 0:
            return
        if not hasattr(self, "_frozen_cols"):
            self._frozen_cols = []
        if col in self._frozen_cols:
            self._frozen_cols.remove(col)
        else:
            self._frozen_cols.append(col)
        self._rebuild_frozen()

    def _select_all(self):
        sm = self.view.selectionModel()
        if sm is None:
            return
        m = self.model_
        if m.rowCount() <= 0:
            return
        ncols = max(0, m.columnCount() - 1)
        sel = QItemSelection(m.index(0, 0), m.index(m.rowCount() - 1, ncols))
        sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect
                  | QItemSelectionModel.SelectionFlag.Rows)

    def _invert_selection(self):
        sm = self.view.selectionModel()
        if sm is None:
            return
        m = self.model_
        nrows = m.rowCount()
        if nrows <= 0:
            return
        ncols = max(0, m.columnCount() - 1)
        all_sel = QItemSelection(m.index(0, 0),
                                 m.index(nrows - 1, ncols))
        cur = sm.selection()
        sm.select(all_sel,
                  QItemSelectionModel.SelectionFlag.Select
                  | QItemSelectionModel.SelectionFlag.Rows)
        sm.select(cur,
                  QItemSelectionModel.SelectionFlag.Deselect
                  | QItemSelectionModel.SelectionFlag.Rows)

    def _clear_selection(self):
        try:
            GgsSelection.instance().clear(self._layer)
        except Exception:
            _log.exception("silent exception in _clear_selection")
        cv = self._canvas
        if cv is not None and hasattr(cv, "refresh_selection"):
            try:
                cv.refresh_selection()
            except Exception:
                _log.exception("silent exception in _clear_selection")
        try:
            self.model_.refresh_selection_marks()
        except Exception:
            _log.exception("silent exception in _clear_selection")
        self._syncing = True
        try:
            self._select_rows_of_selection()
        finally:
            self._syncing = False
        self._refresh_status()

    def _zoom_to_selected(self):
        sel = GgsSelection.instance().fids(self._layer)
        if not sel:
            self._host_msg(_tr("没有选中的要素"))
            return
        geoms = self._layer.geoms()
        xmin = ymin = xmax = ymax = None
        for fid in sel:
            fid = int(fid)
            if 0 <= fid < len(geoms):
                g = geoms[fid]
                if g is None or getattr(g, "is_empty", True):
                    continue
                try:
                    b = g.bounds
                except Exception:
                    _log.exception("silent exception in _zoom_to_selected")
                    continue
                if xmin is None:
                    xmin, ymin, xmax, ymax = b
                else:
                    xmin = min(xmin, b[0]); ymin = min(ymin, b[1])
                    xmax = max(xmax, b[2]); ymax = max(ymax, b[3])
        if xmin is None:
            self._host_msg(_tr("选中要素没有可缩放的几何"))
            return
        from ggis.core.crs.extent import GgsRectangle
        rect = GgsRectangle(xmin, ymin, xmax, ymax)
        cv = self._canvas
        if cv is not None and hasattr(cv, "zoomToExtent"):
            try:
                cv.zoomToExtent(rect, 1.35)
            except Exception:
                _log.exception("silent exception in _zoom_to_selected")
        elif self._host is not None and hasattr(self._host, "ctx"):
            try:
                self._host._forward_to_map_view("_zoom_rect", rect)
            except Exception:
                _log.exception("silent exception in _zoom_to_selected")

    def _open_select_by_attr(self):
        try:
            dlg = GgsSelectByExpressionDialog(
                self._layer, self, apply_cb=self._on_select_by_attr_applied)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                fids = dlg.result_fids()
                try:
                    GgsSelection.instance().set_fids(
                        self._layer, fids or [])
                except Exception:
                    _log.exception("silent exception in _open_select_by_attr")
                self._on_select_by_attr_applied()
        except Exception as e:
            _log.exception("silent exception in _open_select_by_attr")
            self._host_msg(_tr("打开按属性选择失败：{0}").format(e))

    def _on_select_by_attr_applied(self):
        cv = self._canvas
        if cv is not None and hasattr(cv, "refresh_selection"):
            try:
                cv.refresh_selection()
            except Exception:
                _log.exception("silent exception in _on_select_by_attr_applied")
        try:
            self.model_.refresh_selection_marks()
        except Exception:
            _log.exception("silent exception in _on_select_by_attr_applied")

    def _host_msg(self, text, warn=False):
        if self._host is not None and hasattr(self._host, "show_message"):
            try:
                self._host.show_message(text)
                return
            except Exception:
                _log.exception("silent exception in _host_msg")
        try:
            self.lbl_status.setText(text)
        except Exception:
            _log.exception("silent exception in _host_msg")

    def _show_columns_dialog(self):
        try:
            dlg = GgsColumnOrganizeDialog(self, self)
            dlg.exec()
        except Exception as e:
            _log.exception("silent exception in _show_columns_dialog")
            self._host_msg(_tr("打开列管理失败：{0}").format(e))

    def _show_column_stats(self, col):
        try:
            field = self.model_.fields()[col]
        except Exception:
            _log.exception("silent exception in _show_column_stats")
            return
        name = field.name
        attrs = self._layer.attrs()
        n = len(attrs)
        vals = []
        nulls = 0
        for a in attrs:
            if isinstance(a, dict):
                v = a.get(name)
            else:
                v = None
            if v is None or v == "":
                nulls += 1
                continue
            vals.append(v)
        uniq = len(set(map(str, vals)))
        rows = [
            (_tr("字段"), name),
            (_tr("类型"), _TYPE_LABELS_ZH.get(field.type, field.type)),
            (_tr("要素总数"), str(n)),
            (_tr("空值"), str(nulls)),
            (_tr("非空"), str(len(vals))),
            (_tr("唯一值"), str(uniq)),
        ]
        if field.is_numeric():
            nums = [v for v in vals
                    if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if nums:
                try:
                    rows.append((_tr("最小值"), "%.6g" % min(nums)))
                    rows.append((_tr("最大值"), "%.6g" % max(nums)))
                    rows.append((_tr("总和"), "%.6g" % sum(nums)))
                    rows.append((_tr("平均值"),
                                 "%.6g" % (sum(nums) / len(nums))))
                except Exception:
                    _log.exception("silent exception in _show_column_stats")
        else:
            lens = [len(str(v)) for v in vals]
            if lens:
                rows.append((_tr("最短文本"), str(min(lens))))
                rows.append((_tr("最长文本"), str(max(lens))))
        try:
            dlg = GgsColumnStatsDialog(self, name, rows)
            dlg.exec()
        except Exception as e:
            _log.exception("silent exception in _show_column_stats")
            self._host_msg(_tr("统计失败：{0}").format(e))

    def _open_field_calculator(self):
        try:
            dlg = GgsFieldCalculatorDialog(self, self)
            dlg.exec()
        except Exception as e:
            _log.exception("silent exception in _open_field_calculator")
            self._host_msg(_tr("打开字段计算器失败：{0}").format(e))

    def _open_field_manager(self):
        try:
            dlg = GgsFieldManagerDialog(self, self)
            dlg.exec()
        except Exception as e:
            _log.exception("silent exception in _open_field_manager")
            self._host_msg(_tr("打开字段管理失败：{0}").format(e))

    def _on_zoom(self, fid):
        self.zoomToFeature.emit(self._layer, int(fid))

    def _on_table_selection(self, *_):
        if self._syncing:
            return
        sm = self.view.selectionModel()
        if sm is None:
            return
        m = self.model_
        fids = []
        for idx in sm.selectedRows():
            fid = m.data(idx, Qt.ItemDataRole.UserRole)
            if fid is not None and int(fid) >= 0:
                fids.append(int(fid))
        self._syncing = True
        try:
            GgsSelection.instance().set_fids(self._layer, fids)
        finally:
            self._syncing = False
        self._refresh_status()

    def _on_map_selection(self, layer_id=None):
        if layer_id is not None and layer_id != self._layer.id():
            return
        if self.model_.only_selected():
            try:
                self.model_.refilter_by_selection()
            except Exception:
                _log.exception("silent exception in _on_map_selection")
        self.model_.refresh_selection_marks()
        self._syncing = True
        try:
            self._select_rows_of_selection()
        finally:
            self._syncing = False
        self._refresh_status()

    def _select_rows_of_selection(self):
        sel = GgsSelection.instance()
        fids = sel.fids(self._layer)
        sm = self.view.selectionModel()
        if sm is None:
            return
        m = self.model_
        sel_range = QItemSelection()
        if fids:
            start = m.page_slice()[0]
            ncols = max(0, m.columnCount() - 1)
            for r in sorted(m.row_at(f) for f in fids):
                r -= start
                if 0 <= r < m.rowCount():
                    sel_range.select(m.index(r, 0), m.index(r, ncols))
        sm.select(sel_range,
                  QItemSelectionModel.SelectionFlag.ClearAndSelect |
                  QItemSelectionModel.SelectionFlag.Rows)

    def _refresh_status(self):
        m = self.model_
        total = m.total_rows()
        sel = GgsSelection.instance().count(self._layer)
        self.lbl_status.setText(_tr("全部 {0}　|　选中 {1}").format(total, sel))

    def refresh(self):
        try:
            self.model_.reload()
        except Exception:
            _log.exception("silent exception in refresh")
            try:
                self.model_.refresh()
            except Exception:
                _log.exception("silent exception in refresh")
        try:
            self.view.viewport().update()
        except Exception:
            _log.exception("silent exception in refresh")
        self._refresh_status()


class GgsColumnStatsDialog(GgsDialog):

    def __init__(self, parent, name, rows):
        super().__init__(parent)
        self.setObjectName("GgsColumnStatsDialog")
        self.setWindowTitle(_tr("列统计 — {0}").format(name))
        self.resize(360, 320)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        tbl = GgsTableWidget(len(rows), 2, self)
        tbl.setHorizontalHeaderLabels([_tr("项目"), _tr("值")])
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.horizontalHeader().setStretchLastSection(True)
        for i, (k, v) in enumerate(rows):
            tbl.setItem(i, 0, QTableWidgetItem(str(k)))
            it = QTableWidgetItem(str(v))
            it.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
            tbl.setItem(i, 1, it)
        tbl.resizeColumnsToContents()
        lay.addWidget(tbl, 1)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)


class GgsColumnOrganizeDialog(GgsDialog):

    def __init__(self, parent, widget):
        super().__init__(parent)
        self.setObjectName("GgsColumnOrganizeDialog")
        self._widget = widget
        self.setWindowTitle(_tr("管理列"))
        self.resize(360, 440)
        m = widget.model_
        fields = m.fields()
        hh = widget.view.horizontalHeader()
        fcols = set(getattr(widget, "_frozen_cols", []) or [])
        hidden = set(getattr(widget, "_hidden_cols", set()) or set())
        self._order = sorted(range(len(fields)),
                             key=lambda c: (hh.visualIndex(c)
                                            if hh.visualIndex(c) >= 0 else c))
        self._visible = {c: (c not in hidden) for c in range(len(fields))}
        self._frozen = {c: (c in fcols) for c in range(len(fields))}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.lst = GgsColumnList(self)
        lay.addWidget(self.lst, 1)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_up = QToolButton(self); self.btn_up.setText(_tr("上移"))
        self.btn_down = QToolButton(self); self.btn_down.setText(_tr("下移"))
        self.btn_all = QToolButton(self); self.btn_all.setText(_tr("全部显示"))
        self.btn_none = QToolButton(self); self.btn_none.setText(_tr("全部隐藏"))
        row.addWidget(self.btn_up); row.addWidget(self.btn_down)
        row.addStretch(1)
        row.addWidget(self.btn_all); row.addWidget(self.btn_none)
        lay.addLayout(row)
        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel, self)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        lay.addWidget(bbox)
        self._fill()
        self.lst.currentRowChanged.connect(self._on_current)
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down.clicked.connect(lambda: self._move(1))
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none.clicked.connect(lambda: self._set_all(False))

    def _fill(self):
        self.lst.blockSignals(True)
        self.lst.clear()
        for c in self._order:
            f = self._widget.model_.fields()[c]
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, c)
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(4, 3, 4, 3)
            cbv = QCheckBox(_tr("显示"), w)
            cbf = QCheckBox(_tr("冻结"), w)
            cbv.setChecked(self._visible[c])
            cbf.setChecked(self._frozen[c])
            cbv.toggled.connect(
                lambda on, col=c: self._on_visible(col, on))
            cbf.toggled.connect(
                lambda on, col=c: self._on_frozen(col, on))
            lab = GgsColumnName(f.name, w)
            lab.setSizePolicy(QSizePolicy.Policy.Ignored,
                              QSizePolicy.Policy.Preferred)
            hl.addWidget(lab, 1)
            hl.addWidget(cbv)
            hl.addWidget(cbf)
            item.setSizeHint(QSize(w.sizeHint().width(), 28))
            self.lst.addItem(item)
            self.lst.setItemWidget(item, w)
        self.lst.blockSignals(False)

    def _on_visible(self, col, on):
        self._visible[col] = on

    def _on_frozen(self, col, on):
        self._frozen[col] = on
        if on:
            self._visible[col] = True

    def _on_current(self, _row):
        pass

    def _move(self, delta):
        r = self.lst.currentRow()
        if r < 0 or r + delta < 0 or r + delta >= len(self._order):
            return
        self._order[r], self._order[r + delta] = \
            self._order[r + delta], self._order[r]
        self._fill()
        self.lst.setCurrentRow(r + delta)

    def _set_all(self, on):
        for c in self._visible:
            self._visible[c] = on
        self._fill()

    def accept(self):
        w = self._widget
        try:
            w.set_column_order(self._order)
            for c in range(len(w.model_.fields())):
                w.set_column_visible(c, self._visible[c])
                w.set_frozen(c, self._frozen[c])
        except Exception as e:
            if w._host is not None and hasattr(w._host, "show_message"):
                try:
                    w._host.show_message(
                        _tr("应用列设置失败：{0}").format(e))
                except Exception:
                    _log.exception("silent exception in accept")
        super().accept()


class GgsFieldManagerDialog(GgsDialog):

    TYPE_CHOICES = [("integer", _tr("整数")), ("real", _tr("浮点")),
                    ("string", _tr("文本")), ("date", _tr("日期")),
                    ("datetime", _tr("日期时间")), ("bool", _tr("布尔")),
                    ("binary", _tr("二进制"))]

    _NULL_ROWS = 5000

    def __init__(self, parent, widget):
        super().__init__(parent)
        self.setObjectName("GgsFieldManagerDialog")
        self._widget = widget
        self.setWindowTitle(
            _tr("字段管理 — {0}").format(self._layer_name()))
        self.setWindowIcon(_icons.icon("new_attr", size=16))
        self.resize(620, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.tbl = GgsTableWidget(0, 5, self)
        self.tbl.setHorizontalHeaderLabels(
            [_tr("字段名"), _tr("类型"), _tr("长度"), _tr("精度"),
             _tr("空值数")])
        self.tbl.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        hh = self.tbl.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hit = self.tbl.horizontalHeaderItem(4)
        if hit is not None:
            hit.setToolTip(
                _tr("空值数（前 {0} 行）").format(self._NULL_ROWS))
        self.tbl.itemDoubleClicked.connect(self._on_double)
        self.tbl.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tbl.customContextMenuRequested.connect(self._on_menu)
        lay.addWidget(self.tbl, 1)

        nr = QHBoxLayout()
        nr.setSpacing(6)
        self.ed_new = QLineEdit(self)
        self.ed_new.setPlaceholderText(_tr("字段名"))
        self.ed_new.returnPressed.connect(self._apply_new)
        nr.addWidget(self.ed_new, 1)
        nr.addWidget(QLabel(_tr("类型")))
        self.cmb_type = QComboBox(self)
        for t, lab in self.TYPE_CHOICES:
            self.cmb_type.addItem(lab, t)
        nr.addWidget(self.cmb_type)
        nr.addWidget(QLabel(_tr("宽度")))
        self.spn_w = QSpinBox(self)
        self.spn_w.setRange(0, 254); self.spn_w.setValue(0)
        nr.addWidget(self.spn_w)
        nr.addWidget(QLabel(_tr("精度")))
        self.spn_p = QSpinBox(self)
        self.spn_p.setRange(0, 16); self.spn_p.setValue(0)
        nr.addWidget(self.spn_p)
        lay.addLayout(nr)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.btn_add = GgsSmallButtonStyle1(
            "add", _tr("新建字段"), self._apply_new, 16, self)
        self.btn_del = GgsSmallButtonStyle1(
            "delete", _tr("删除所选"), self._del, 16, self)
        self.btn_ren = GgsSmallButtonStyle1(
            "edit", _tr("重命名所选"), self._ren, 16, self)
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_del)
        row.addWidget(self.btn_ren)
        row.addStretch(1)
        bbox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        bbox.rejected.connect(self.reject)
        row.addWidget(bbox)
        lay.addLayout(row)

        self._fill()

    def _layer_name(self):
        try:
            return self._widget._layer.name()
        except Exception:
            _log.exception("silent exception in _layer_name")
            return ""

    def _fill(self):
        fields = self._widget.model_.fields()
        nulls = self._null_counts(fields)
        self.tbl.blockSignals(True)
        self.tbl.setRowCount(0)
        for i, ff in enumerate(fields):
            self.tbl.insertRow(i)
            vals = [ff.name, _TYPE_LABELS_ZH.get(ff.type, ff.type),
                    str(ff.width), str(ff.precision),
                    "" if nulls is None else str(nulls[i])]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c in (2, 3, 4):
                    it.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter)
                self.tbl.setItem(i, c, it)
        self.tbl.blockSignals(False)

    def _null_counts(self, fields):
        try:
            attrs = self._widget._layer.attrs() or []
        except Exception:
            _log.exception("silent exception in _null_counts")
            return None
        names = [f.name for f in fields]
        counts = [0] * len(names)
        for n, a in enumerate(attrs):
            if n >= self._NULL_ROWS:
                break
            if not isinstance(a, dict):
                continue
            for i, nm in enumerate(names):
                if a.get(nm) is None:
                    counts[i] += 1
        return counts

    def _session_or_err(self):
        s = self._widget._session()
        if s is None or not s.is_active():
            self._alert(_tr("本图层当前不可编辑，无法执行该操作"))
            return None
        return s

    def _alert(self, text):
        GgsMsgBox.warning(self, _tr("字段管理"), text)

    def _apply_new(self):
        s = self._session_or_err()
        if s is None:
            return
        name = self.ed_new.text().strip()
        if not name:
            self._alert(_tr("请填写字段名称"))
            return
        field = GgsField(name, self.cmb_type.currentData(),
                         self.spn_w.value(), self.spn_p.value())
        try:
            s.add_field(field)
        except Exception as e:
            _log.exception("silent exception in _apply_new")
            self._alert(_tr("新增字段失败：{0}").format(e))
            return
        self._fill()
        self.ed_new.clear()
        self.ed_new.setFocus()

    def _del(self):
        s = self._session_or_err()
        if s is None:
            return
        fields = self._widget.model_.fields()
        row = self.tbl.currentRow()
        if row < 0 or row >= len(fields):
            self._alert(_tr("请选择一个字段"))
            return
        name = fields[row].name
        try:
            s.delete_field(name)
        except Exception as e:
            _log.exception("silent exception in _del")
            self._alert(_tr("删除字段失败：{0}").format(e))
            return
        self._fill()

    def _ren(self):
        s = self._session_or_err()
        if s is None:
            return
        fields = self._widget.model_.fields()
        row = self.tbl.currentRow()
        if row < 0 or row >= len(fields):
            self._alert(_tr("请选择一个字段"))
            return
        old = fields[row].name
        new, ok = QInputDialog.getText(self, _tr("重命名字段"),
                                       _tr("新名称："), text=old)
        if not ok or not new.strip():
            return
        try:
            s.rename_field(old, new.strip())
        except Exception as e:
            _log.exception("silent exception in _ren")
            self._alert(_tr("重命名字段失败：{0}").format(e))
            return
        self._fill()

    def _on_double(self, item):
        if item.column() != 0:
            return
        if not (0 <= item.row() < len(self._widget.model_.fields())):
            return
        self._ren()

    def _on_menu(self, pos):
        it = self.tbl.itemAt(pos)
        if it is not None:
            r = it.row()
            sm = self.tbl.selectionModel()
            sel = {ix.row() for ix in sm.selectedRows()} if sm else set()
            if r not in sel:
                self.tbl.selectRow(r)
        m = QMenu(self)
        m.addAction(_tr("重命名所选"), self._ren)
        m.addAction(_tr("删除所选"), self._del)
        m.addSeparator()
        m.addAction(_tr("新建字段"), self._apply_new)
        m.exec(self.tbl.viewport().mapToGlobal(pos))

    def closeEvent(self, e):
        try:
            self._widget._refresh_status()
        except Exception:
            _log.exception("silent exception in closeEvent")
        super().closeEvent(e)


class GgsAttributeTableDialog(GgsDialog):

    zoomToFeature = Signal(object, int)

    @staticmethod
    def open_for(layer, parent=None, canvas=None):
        if layer is None or not layer.is_vector():
            return None
        key = layer.id()
        dlg = _OPEN_TABLES.get(key)
        if dlg is not None and isinstance(dlg, GgsAttributeTableDialog):
            try:
                dlg.show()
                dlg.raise_()
                dlg.activateWindow()
                return dlg
            except RuntimeError:
                exc_note("open_for @ ggis/ui/dialogs/attribute_table.py:2297")
                _OPEN_TABLES.pop(key, None)
        host = parent
        sp = (lambda: host._session_for(layer)) if (
            host is not None and hasattr(host, "_session_for")) else None
        dlg = GgsAttributeTableDialog(layer, parent, canvas,
                                     host=host, session_provider=sp)
        _OPEN_TABLES[key] = dlg
        dlg.show()
        return dlg

    def __init__(self, layer, parent=None, canvas=None, host=None,
                 session_provider=None):
        super().__init__(parent)
        self._layer = layer
        self.setWindowTitle(_tr("属性表 — {0}").format(layer.name()))
        self.resize(940, 620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.body = GgsAttributeTableWidget(
            layer, self, canvas, host=host,
            session_provider=session_provider)
        lay.addWidget(self.body)
        self.body.zoomToFeature.connect(self.zoomToFeature)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        _OPEN_TABLES.pop(self._layer.id(), None)
        try:
            self.body.deleteLater()
        except Exception:
            _log.exception("silent exception in closeEvent")
        super().closeEvent(e)


class GgsAttributeTableDock(GgsDockWidget):

    zoomToFeature = Signal(object, int)

    def __init__(self, parent=None):
        super().__init__(_tr("属性表"), parent)
        self.setObjectName("GgsAttributeTableDock")
        self._layer = None
        self._table = None
        self._tabs = {}
        host = QWidget()
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.tabs = GgsAttrTabs(host)
        self.tabs.setTabsClosable(True)
        self.tabs.setDocumentMode(False)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        _bar = self.tabs.tabBar()
        _bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        _bar.customContextMenuRequested.connect(self._on_tab_menu)
        lay.addWidget(self.tabs, 1)
        self._empty = self._build_empty_hint()
        lay.addWidget(self._empty, 1)
        self.setWidget(host)
        self._sync_empty()

    def _build_empty_hint(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lab = GgsAttrEmptyHint(_tr("选择或双击一个矢量图层以查看属性表"))
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setWordWrap(True)
        lay.addWidget(lab)
        return w

    def _sync_empty(self):
        empty = (self.tabs.count() <= 0)
        try:
            self.tabs.setVisible(not empty)
            self._empty.setVisible(empty)
        except Exception:
            _log.exception("silent exception in _sync_empty")

    def layer(self):
        return self._layer

    def has_layer(self, layer):
        try:
            return layer is not None and layer.id() in self._tabs
        except Exception:
            _log.exception("silent exception in has_layer")
            return False

    def show_layer(self, layer, canvas=None, reload=False):
        if layer is None or not layer.is_vector():
            return None
        key = layer.id()
        got = self._tabs.get(key)
        if got is not None and reload:
            self._remove_tab(key)
            got = None
        if got is not None:
            _lyr, w = got
            try:
                self.tabs.setCurrentWidget(w)
            except Exception:
                _log.exception("silent exception in show_layer")
            self._layer = _lyr
            self._table = w
            self._sync_empty()
            return w
        host = self.parent()
        sp = (lambda: host._session_for(layer)) if (
            host is not None and hasattr(host, "_session_for")) else None
        table = GgsAttributeTableWidget(
            layer, self, canvas, host=host, session_provider=sp)
        table.zoomToFeature.connect(self.zoomToFeature)
        self._tabs[key] = (layer, table)
        try:
            idx = self.tabs.addTab(table, str(layer.name() or ""))
            self.tabs.setCurrentIndex(idx)
            self.tabs.setTabToolTip(idx, str(layer.name() or ""))
        except Exception:
            _log.exception("silent exception in show_layer")
        self._layer = layer
        self._table = table
        self._sync_empty()
        return table

    def _remove_tab(self, key):
        got = self._tabs.pop(key, None)
        if got is None:
            return
        _lyr, w = got
        try:
            i = self.tabs.indexOf(w)
            if i >= 0:
                self.tabs.removeTab(i)
        except Exception:
            _log.exception("silent exception in _remove_tab")
        try:
            w.deleteLater()
        except Exception:
            _log.exception("silent exception in _remove_tab")
        if self._table is w:
            self._table = None
            self._layer = None

    def _on_tab_close(self, idx):
        w = self.tabs.widget(idx)
        for key, (_lyr, tw) in list(self._tabs.items()):
            if tw is w:
                self._remove_tab(key)
                break
        self._sync_empty()
        self._on_tab_changed(self.tabs.currentIndex())

    def _on_tab_changed(self, _idx):
        cur = self.tabs.currentWidget()
        self._table = cur
        self._layer = None
        for _key, (_lyr, tw) in self._tabs.items():
            if tw is cur:
                self._layer = _lyr
                break

    def _on_tab_menu(self, pos):
        bar = self.tabs.tabBar()
        idx = bar.tabAt(pos)
        if idx < 0:
            return
        try:
            if self.tabs.widget(idx) is None:
                return
        except Exception:
            _log.exception("silent exception in _on_tab_menu")
            return
        menu = QMenu(self)
        menu.addAction(_tr("关闭"), lambda: self._on_tab_close(idx))
        menu.addAction(_tr("关闭其它页签"), lambda: self._close_others(idx))
        menu.addAction(_tr("关闭全部页签"), self.close_all_tabs)
        try:
            menu.exec(bar.mapToGlobal(pos))
        except Exception:
            _log.exception("silent exception in _on_tab_menu")

    def _close_others(self, keep_idx):
        keep = self.tabs.widget(keep_idx)
        for key, (_lyr, tw) in list(self._tabs.items()):
            if tw is keep:
                continue
            self._remove_tab(key)
        self._sync_empty()
        self._on_tab_changed(self.tabs.currentIndex())

    def close_all_tabs(self):
        for key in list(self._tabs.keys()):
            self._remove_tab(key)
        self._layer = None
        self._table = None
        self._sync_empty()

    def close_layer_tab(self, layer_id):
        if not layer_id or layer_id not in self._tabs:
            return False
        self._remove_tab(layer_id)
        self._sync_empty()
        self._on_tab_changed(self.tabs.currentIndex())
        return True

    def refresh(self):
        if self._table is not None:
            try:
                self._table.refresh()
            except Exception:
                _log.exception("silent exception in refresh")

    def content(self):
        return self._table


class GgsLayerAttributeDock(GgsDockWidget):

    zoomToFeature = Signal(object, int)
    closed = Signal(str)

    def __init__(self, layer, canvas=None, host=None, parent=None):
        super().__init__(str(layer.name() or _tr("属性表")), parent)
        self.setObjectName("GgsLayerAttributeDock")
        self._layer = layer
        self._lid = layer.id()
        self._host_ref = host
        self._view_ref = parent
        self._table = self._make_widget(layer, canvas, host)
        self.setWidget(self._table)

    def _make_widget(self, layer, canvas, host):
        sp = self._session_provider(layer, host)
        table = GgsAttributeTableWidget(
            layer, self, canvas, host=host, session_provider=sp)
        table.zoomToFeature.connect(self.zoomToFeature)
        return table

    def _session_provider(self, layer, host):
        view = getattr(self, "_view_ref", None)
        for cand in (view, host):
            if cand is not None and hasattr(cand, "_session_for"):
                return (lambda _c=cand: _c._session_for(layer))
        return None

    def layer(self):
        return self._layer

    def layer_id(self):
        return self._lid

    def content(self):
        return self._table

    def refresh(self):
        if self._table is not None:
            try:
                self._table.refresh()
            except Exception:
                _log.exception("silent exception in refresh")

    def reload(self, canvas=None):
        old_body = getattr(self, "_body", None)
        old = self._table
        self._table = self._make_widget(self._layer, canvas, self._host_ref)
        self.setWidget(self._table)
        if old is not None:
            try:
                old.deleteLater()
            except Exception:
                _log.exception("silent exception in reload")
        _new_body = getattr(self, "_body", None)
        if old_body is not None and old_body is not _new_body:
            try:
                old_body.deleteLater()
            except Exception:
                _log.exception("silent exception in reload")

    def closeEvent(self, ev):
        try:
            self.closed.emit(self._lid)
        except Exception:
            _log.exception("silent exception in closeEvent")
        try:
            super().closeEvent(ev)
        except Exception:
            _log.exception("silent exception in closeEvent")


class GgsAttrEmptyHint(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAttrEmptyHint")
class GgsAttrHint(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAttrHint")
class GgsAttrStatus(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAttrStatus")
class GgsAttrTabs(QTabWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAttrTabs")
class GgsColumnList(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsColumnList")
class GgsColumnName(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsColumnName")
