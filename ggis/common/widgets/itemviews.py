# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QRegion
from PySide6.QtWidgets import (QFrame, QTreeView, QTreeWidget,
                               QListWidget, QTableWidget, QHeaderView)

TREE_INDENT = 16
TREE_ICON = 16
TREE_ROW_H = 24

CHECK_PX = 14
CHECK_OUTER_PX = 16


def _ggs_rounded_region(r, rad):
    from PySide6.QtCore import QRect
    x, y, w, h = r.x(), r.y(), r.width(), r.height()
    reg = QRegion(QRect(x, y + rad, w, h - 2 * rad))
    reg += QRegion(QRect(x + rad, y, w - 2 * rad, h))
    d = 2 * rad
    reg += QRegion(QRect(x, y, d, d), QRegion.RegionType.Ellipse)
    reg += QRegion(QRect(x + w - d, y, d, d), QRegion.RegionType.Ellipse)
    reg += QRegion(QRect(x, y + h - d, d, d), QRegion.RegionType.Ellipse)
    reg += QRegion(QRect(x + w - d, y + h - d, d, d), QRegion.RegionType.Ellipse)
    return reg


class GgsTreeMixin:

    def _apply_tree_common(self):
        try:
            self.setIndentation(TREE_INDENT)
            self.setIconSize(QSize(TREE_ICON, TREE_ICON))
            self.setAnimated(False)
            self.setFrameShape(QFrame.Shape.NoFrame)
            self.setUniformRowHeights(False)
            self.setProperty("ggsStdTree", True)
        except Exception:
            exc_note("_apply_tree_common @ ggis/common/widgets/treeview.py:131")
            pass
        return self

    def _ggs_repaint_rows(self, *indexes):
        try:
            pass
        except Exception:
            exc_note("_ggs_repaint_rows @ ggis/common/widgets/treeview.py:154")
            return
        box = None
        for idx in indexes:
            if idx is None:
                continue
            try:
                if not idx.isValid():
                    continue
                rr = self.visualRect(idx)
            except Exception:
                exc_note("_ggs_repaint_rows @ ggis/common/widgets/treeview.py:164")
                continue
            try:
                rr = rr.adjusted(0, -1, 0, 1)
                rr.setLeft(0)
                rr.setRight(max(rr.right(), self.viewport().width()))
            except Exception:
                exc_note("_ggs_repaint_rows @ ggis/common/widgets/treeview.py:177")
                pass
            box = rr if box is None else box.united(rr)
        if box is not None and not box.isNull():
            try:
                self.viewport().update(box)
            except Exception:
                exc_note("_ggs_repaint_rows @ ggis/common/widgets/treeview.py:183")
                pass

    def _ggs_note_hover(self, pos):
        try:
            idx = self.indexAt(pos)
        except Exception:
            exc_note("_ggs_note_hover @ ggis/common/widgets/treeview.py:190")
            return
        prev = getattr(self, "_ggs_hover_idx", None)
        if prev == idx:
            return
        self._ggs_hover_idx = idx
        self._ggs_repaint_rows(prev, idx)

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)
        try:
            self._ggs_note_hover(ev.position().toPoint())
        except Exception:
            exc_note("mouseMoveEvent @ ggis/common/widgets/treeview.py:202")
            pass

    def leaveEvent(self, ev):
        prev = getattr(self, "_ggs_hover_idx", None)
        self._ggs_hover_idx = None
        super().leaveEvent(ev)
        self._ggs_repaint_rows(prev, None)

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        try:
            idx = self.indexAt(ev.position().toPoint())
            if idx.isValid():
                self._ggs_repaint_rows(idx, getattr(self, "_ggs_hover_idx", None))
        except Exception:
            exc_note("mousePressEvent @ ggis/common/widgets/treeview.py:219")
            pass

    def currentChanged(self, current, previous):
        super().currentChanged(current, previous)
        try:
            self._ggs_repaint_rows(previous, current)
        except Exception:
            exc_note("currentChanged @ ggis/common/widgets/treeview.py:228")
            pass

    def resizeEvent(self, ev):
        super().resizeEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)




class GgsTreeWidget(GgsTreeMixin, QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsTree")
        self.setHeaderHidden(True)
        self.setExpandsOnDoubleClick(False)
        self._apply_tree_common()


class GgsTreeView(GgsTreeMixin, QTreeView):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsTree")
        self.setHeaderHidden(True)
        self.setExpandsOnDoubleClick(False)
        self._apply_tree_common()


LIST_ICON = 16
LIST_ROW_H = 24


class GgsListMixin:

    def _apply_list_common(self):
        try:
            self.setIconSize(QSize(LIST_ICON, LIST_ICON))
            self.setUniformItemSizes(True)
            self.setFrameShape(QFrame.Shape.NoFrame)
            self.setProperty("ggsStdList", True)
        except Exception:
            exc_note("_apply_list_common @ ggis/common/widgets/listview.py:63")
            pass
        return self

    def _ggs_repaint_rows(self, *indexes):
        box = None
        for idx in indexes:
            if idx is None:
                continue
            try:
                if not idx.isValid():
                    continue
                rr = self.visualRect(idx)
            except Exception:
                exc_note("_ggs_repaint_rows @ ggis/common/widgets/listview.py:87")
                continue
            try:
                rr = rr.adjusted(0, -1, 0, 1)
                rr.setLeft(0)
                rr.setRight(max(rr.right(), self.viewport().width()))
            except Exception:
                exc_note("_ggs_repaint_rows @ ggis/common/widgets/listview.py:93")
                pass
            box = rr if box is None else box.united(rr)
        if box is not None and not box.isNull():
            try:
                self.viewport().update(box)
            except Exception:
                exc_note("_ggs_repaint_rows @ ggis/common/widgets/listview.py:99")
                pass

    def _ggs_note_hover(self, pos):
        try:
            idx = self.indexAt(pos)
        except Exception:
            exc_note("_ggs_note_hover @ ggis/common/widgets/listview.py:106")
            return
        prev = getattr(self, "_ggs_hover_idx", None)
        if prev == idx:
            return
        self._ggs_hover_idx = idx
        self._ggs_repaint_rows(prev, idx)

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)
        try:
            self._ggs_note_hover(ev.position().toPoint())
        except Exception:
            exc_note("mouseMoveEvent @ ggis/common/widgets/listview.py:118")
            pass

    def leaveEvent(self, ev):
        prev = getattr(self, "_ggs_hover_idx", None)
        self._ggs_hover_idx = None
        super().leaveEvent(ev)
        self._ggs_repaint_rows(prev, None)

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        try:
            idx = self.indexAt(ev.position().toPoint())
            if idx.isValid():
                self._ggs_repaint_rows(idx, getattr(self, "_ggs_hover_idx", None))
        except Exception:
            exc_note("mousePressEvent @ ggis/common/widgets/listview.py:133")
            pass

    def currentChanged(self, current, previous):
        super().currentChanged(current, previous)
        try:
            self._ggs_repaint_rows(previous, current)
        except Exception:
            exc_note("currentChanged @ ggis/common/widgets/listview.py:141")
            pass

    def resizeEvent(self, ev):
        super().resizeEvent(ev)

    def showEvent(self, ev):
        super().showEvent(ev)



class GgsListWidget(GgsListMixin, QListWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsList")
        self._apply_list_common()


from PySide6.QtWidgets import QTableWidget

__all__ = ["GgsTableWidget"]


class GgsTableWidget(QTableWidget):

    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__(rows, cols, parent)
        self.setObjectName("GgsTable")
        self.verticalHeader().setVisible(False)


def setup_table_ops(table, sortable=True, keep_widths=False, row_height=None):
    if table is None:
        return table
    try:
        from PySide6.QtWidgets import QHeaderView
    except Exception:
        exc_note("setup_table_ops @ ggis/common/widgets/standard.py:5053")
        return table
    try:
        hh = table.horizontalHeader()
    except Exception:
        exc_note("setup_table_ops @ ggis/common/widgets/standard.py:5057")
        hh = None
    if hh is not None:
        try:
            hh.setSectionsClickable(True)
            hh.setSectionsMovable(True)
            hh.setHighlightSections(False)
            if not keep_widths:
                hh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            if sortable:
                table.setSortingEnabled(True)
                hh.setSortIndicatorShown(True)
        except Exception:
            exc_note("setup_table_ops @ ggis/common/widgets/standard.py:5069")
            pass
    try:
        vh = table.verticalHeader()
    except Exception:
        exc_note("setup_table_ops @ ggis/common/widgets/standard.py:5073")
        vh = None
    if vh is not None:
        try:
            vh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            if row_height:
                vh.setDefaultSectionSize(int(row_height))
        except Exception:
            exc_note("setup_table_ops @ ggis/common/widgets/standard.py:5082")
            pass
    return table



