# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QAbstractItemView, QLineEdit, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.widgets.itemviews import GgsTreeWidget
from ggis.common.styling import icons as _icons
from ggis.core.app import i18n
from ...core.analysis import (OPS, OP_BUFFER, OP_BOUNDING_BOX, OP_CENTROID,
                              OP_CLIP, OP_CONVEX_HULL, OP_DELETE_DUPLICATES,
                              OP_DENSIFY, OP_DIFFERENCE, OP_DISSOLVE,
                              OP_FIX_GEOMETRIES, OP_INTERSECT,
                              OP_MULTIPART_TO_SINGLE, OP_ROUND_COORDINATES,
                              OP_SIMPLIFY, OP_SYM_DIFFERENCE, OP_UNION)
from ggis.core.analysis.raster_ops import RASTER_OPS
from ggis.ui.framework.docks import GgsDockBody
from ggis.common.widgets.inputs import GgsSearchEdit
import logging
from PySide6.QtWidgets import QMenu
_log = logging.getLogger("gmagis")

_tr = i18n.tr

GROUPS = [
    ("提取范围",
     [(OP_INTERSECT, "intersect"),
      (OP_CLIP, "clip"),
      (OP_UNION, "union"),
      (OP_DIFFERENCE, "difference"),
      (OP_SYM_DIFFERENCE, "sym_difference")]),
    ("合并要素",
     [(OP_DISSOLVE, "dissolve")]),
    ("几何修正",
     [(OP_FIX_GEOMETRIES, "fix_geometry"),
      (OP_MULTIPART_TO_SINGLE, "multipart_single"),
      (OP_DELETE_DUPLICATES, "delete_duplicates"),
      (OP_SIMPLIFY, "simplify"),
      (OP_DENSIFY, "densify"),
      (OP_ROUND_COORDINATES, "round_coordinates")]),
    ("几何派生",
     [(OP_CENTROID, "centroid"),
      (OP_CONVEX_HULL, "convex_hull"),
      (OP_BOUNDING_BOX, "bounding_box")]),
    ("邻近分析",
     [(OP_BUFFER, "buffer")]),
]

_seen_ops = {_op for _g, _items in GROUPS for _op, _n in _items}
_new_groups = {}
for _op, _spec in OPS.items():
    _grp = _spec.get("group")
    if not _grp or _op in _seen_ops:
        continue
    _new_groups.setdefault(_grp, []).append((_op, _op))
for _grp, _items in _new_groups.items():
    for _i, (_gname, _old) in enumerate(GROUPS):
        if _gname == _grp:
            GROUPS[_i] = (_gname, _old + _items)
            break
    else:
        GROUPS.append((_grp, _items))
del _seen_ops, _new_groups, _op, _spec, _grp, _items, _i, _gname, _old

_seen_ops = {_op for _g, _items in GROUPS for _op, _n in _items}
_raster_groups = {}
for _op, _spec in RASTER_OPS.items():
    _grp = _spec.get("group")
    if not _grp or _op in _seen_ops:
        continue
    _raster_groups.setdefault(_grp, []).append((_op, _op))
for _grp, _items in _raster_groups.items():
    for _i, (_gname, _old) in enumerate(GROUPS):
        if _gname == _grp:
            GROUPS[_i] = (_gname, _old + _items)
            break
    else:
        GROUPS.append((_grp, _items))
del _seen_ops, _raster_groups, _op, _spec, _grp, _items, _i, _gname, _old

HINTS = {}


ROLE_ICON_NAME = int(Qt.ItemDataRole.UserRole) + 1
ROLE_GROUP_KEY = int(Qt.ItemDataRole.UserRole) + 2


class GgsToolboxPanel(GgsDockWidget):

    algorithmTriggered = Signal(str)

    def __init__(self, parent=None):
        super().__init__(_tr("处理工具箱"), parent)
        self.setObjectName("GgsToolboxDock")
        self._items = []
        body = GgsDockBody(self)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 4, 6, 2)
        lay.setSpacing(4)

        self.edit_search = GgsSearchEdit()
        self.edit_search.setPlaceholderText(_tr("搜索算法…"))
        self.edit_search.setClearButtonEnabled(True)
        try:
            self.edit_search.addAction(
                _icons.icon("search", size=16),
                QLineEdit.ActionPosition.LeadingPosition)
        except Exception:
            _log.exception("silent exception in __init__")
        self.edit_search.textChanged.connect(self._filter)
        lay.addWidget(self.edit_search)

        self.tree = GgsTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(False)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemActivated.connect(self._on_double)
        self.tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._popup_menu)
        lay.addWidget(self.tree, 1)

        self.setWidget(body)
        self._populate()

    def _popup_menu(self, pos):
        it = self.tree.itemAt(pos)
        op = self._op_of(it)
        menu = GgsToolboxMenu(self)
        if op:
            a = menu.addAction(_icons.icon("tool", size=16), _tr("运行算法…"))
            a.triggered.connect(lambda _c=False, o=op: self._run_op(o))
            menu.addSeparator()
            c = menu.addAction(_icons.icon("info", size=16), _tr("算法说明"))
            c.triggered.connect(lambda _c=False, o=op: self._show_hint(o))
        else:
            b = menu.addAction(_icons.icon("expand_all", size=16),
                               _tr("展开全部"))
            b.triggered.connect(self.tree.expandAll)
            c = menu.addAction(_icons.icon("collapse_all", size=16),
                               _tr("折叠全部"))
            c.triggered.connect(self.tree.collapseAll)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    @staticmethod
    def _op_of(item):
        if item is None:
            return ""
        return item.data(0, Qt.ItemDataRole.UserRole) or ""

    def _run_op(self, op):
        if op:
            self.algorithmTriggered.emit(op)

    def _show_hint(self, op):
        from PySide6.QtWidgets import QMessageBox
        spec = OPS.get(op, RASTER_OPS.get(op, {}))
        QMessageBox.information(
            self, _tr(spec.get("label", op)),
            _tr(HINTS.get(op, "")) or "")

    FALLBACK_ICON = "processing"

    @staticmethod
    def row_icon(name):
        ic = None
        try:
            ic = _icons.icon(name, size=16) if name else None
        except Exception:
            _log.exception("silent exception in row_icon")
            ic = None
        try:
            if ic is None or ic.pixmap(16, 16).isNull():
                ic = _icons.icon(GgsToolboxPanel.FALLBACK_ICON, size=16)
        except Exception:
            _log.exception("silent exception in row_icon")
        return ic

    def _group_font(self):
        f = QFont(self.tree.font())
        f.setBold(True)
        return f

    def _populate(self):
        self.tree.clear()
        self._items = []
        gfont = self._group_font()
        for gname, ops in GROUPS:
            group = QTreeWidgetItem([_tr(gname)])
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            group.setFont(0, gfont)
            group.setIcon(0, self.row_icon("folder"))
            group.setData(0, ROLE_ICON_NAME, "folder")
            group.setData(0, ROLE_GROUP_KEY, str(gname))
            group.setToolTip(0, _tr("算法分类"))
            self.tree.addTopLevelItem(group)
            for op, icon_name in ops:
                spec = OPS.get(op, RASTER_OPS.get(op, {}))
                it = QTreeWidgetItem([_tr(spec.get("label", op))])
                it.setIcon(0, self.row_icon(icon_name))
                it.setData(0, ROLE_ICON_NAME, icon_name)
                it.setToolTip(0, _tr(HINTS.get(op, "")))
                it.setData(0, Qt.ItemDataRole.UserRole, op)
                group.addChild(it)
                self._items.append((it, op))
            group.setExpanded(False)

    def retheme(self):
        try:
            count = self.tree.topLevelItemCount()
        except Exception:
            _log.exception("silent exception in retheme")
            return
        for i in range(count):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            self._reset_icon(group)
            for j in range(group.childCount()):
                self._reset_icon(group.child(j))

    def _reset_icon(self, item):
        try:
            name = item.data(0, ROLE_ICON_NAME)
        except Exception:
            _log.exception("silent exception in _reset_icon")
            return
        if not name:
            return
        try:
            item.setIcon(0, self.row_icon(name))
        except Exception:
            _log.exception("silent exception in _reset_icon")

    def session_state(self):
        out = [str(self.tree.topLevelItem(i).data(0, ROLE_GROUP_KEY) or "")
               for i in range(self.tree.topLevelItemCount())
               if self.tree.topLevelItem(i).isExpanded()]
        out = [k for k in out if k]
        return {"expanded": out} if out else None

    def restore_session(self, state):
        paths = (state or {}).get("expanded") \
            if isinstance(state, dict) else None
        if not isinstance(paths, (list, tuple)):
            return
        want = {str(x) for x in paths if x}
        if not want:
            return
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if str(it.data(0, ROLE_GROUP_KEY) or "") in want:
                it.setExpanded(True)

    def _filter(self, text):
        text = str(text or "").strip().lower()
        for group in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(group)
            shown = 0
            for i in range(g.childCount()):
                it = g.child(i)
                op = str(it.data(0, Qt.ItemDataRole.UserRole) or "")
                spec = OPS.get(op, RASTER_OPS.get(op, {}))
                hay = (_tr(spec.get("label", op)) + " " + op + " "
                       + _tr(HINTS.get(op, ""))).lower()
                hit = (not text) or (text in hay)
                it.setHidden(not hit)
                shown += 1 if hit else 0
            g.setHidden(shown == 0)
            if text and shown:
                g.setExpanded(True)

    def selected_op(self):
        it = self.tree.currentItem()
        if it is None:
            return ""
        return str(it.data(0, Qt.ItemDataRole.UserRole) or "")

    def _on_double(self, item, _col=0):
        op = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
        if op:
            self.algorithmTriggered.emit(op)

    def _on_run(self):
        op = self.selected_op()
        if op:
            self.algorithmTriggered.emit(op)

    def visible_ops(self):
        out = []
        for group in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(group)
            if g.isHidden():
                continue
            for i in range(g.childCount()):
                it = g.child(i)
                if not it.isHidden():
                    out.append(str(it.data(0, Qt.ItemDataRole.UserRole)))
        return out

    def algorithms(self):
        out = []
        for group in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(group)
            for i in range(g.childCount()):
                it = g.child(i)
                out.append((g.text(0), str(it.data(0, Qt.ItemDataRole.UserRole)),
                            it.text(0)))
        return out


class GgsToolboxMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsToolboxMenu")
