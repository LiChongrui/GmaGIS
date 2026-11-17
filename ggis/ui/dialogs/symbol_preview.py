# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note
from ggis.common.styling.symbol_sample import (
    _ZOOM_MAX, _ZOOM_MIN, _ZOOM_STEP,
    _category_pixmap, _preview_scale, _theme,
    paint_symbol_sample, sample_pixmap)
from ggis.core.app import i18n
from ggis.render.style_apply import symbol_from_item
from ggis.common.base.dialog import GgsDialog
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, Signal
from PySide6.QtGui import QIcon, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QDialogButtonBox, QListWidget, QListWidgetItem, QSizePolicy,
                               QVBoxLayout, QWidget)

_tr = i18n.tr


class GgsSymbolPreview(QWidget):

    def __init__(self, parent=None, height=54, kind="polygon", dark=True,
                 width=None):
        super().__init__(parent)
        self.setObjectName("GgsSymbolPreview")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFixedHeight(int(height))
        if width:
            self.setFixedWidth(int(width))
        else:
            self.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Fixed)
        self._sym = None
        self._kind = str(kind or "polygon")
        self._dark = bool(dark)
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._drag_from = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("")

    def zoom(self):
        return float(self._zoom)

    def setZoom(self, z):
        try:
            z = float(z)
        except Exception:
            exc_note("setZoom @ ggis/ui/dialogs/symbol_preview.py:366")
            return
        self._zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, z))
        self.update()

    def wheelEvent(self, e):
        try:
            dy = float(e.angleDelta().y())
        except Exception:
            exc_note("wheelEvent @ ggis/ui/dialogs/symbol_preview.py:375")
            dy = 0.0
        if dy == 0.0:
            return super().wheelEvent(e)
        self.setZoom(self._zoom * (_ZOOM_STEP if dy > 0 else 1.0 / _ZOOM_STEP))
        e.accept()

    def mouseDoubleClickEvent(self, e):
        self.setZoom(1.0)
        self._pan = QPointF(0.0, 0.0)
        self.update()
        e.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_from = QPointF(e.position())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_from is None:
            return super().mouseMoveEvent(e)
        now = QPointF(e.position())
        self._pan += now - self._drag_from
        self._drag_from = now
        self.update()
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._drag_from is not None:
            self._drag_from = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def reset_view(self):
        self.setZoom(1.0)
        self._pan = QPointF(0.0, 0.0)
        self.update()

    def setSymbol(self, sym, kind=None, dark=None):
        if kind is not None:
            self._kind = str(kind or "polygon")
        if dark is not None:
            self._dark = bool(dark)
        self._sym = sym
        self.update()

    def symbol(self):
        return self._sym

    def _paint_content(self, painter, inner):
        if self._sym is None:
            return
        base = _preview_scale(max(1.0, inner.width() - 12.0),
                              max(1.0, inner.height() - 12.0))
        painter.setClipRect(inner)
        paint_symbol_sample(painter, QRectF(inner).translated(self._pan),
                            self._sym, self._kind,
                            scale=base * self._zoom)

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            inner = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(QPen(_theme("border", self._dark), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(inner, 4.0, 4.0)
            self._paint_content(p, QRectF(self.rect()))
        finally:
            p.end()


class GgsSymbolGallery(QListWidget):

    picked = Signal(object)
    THUMB = QSize(62, 38)

    def __init__(self, parent=None, kind="polygon", dark=True, rows=2,
                 category="symbol"):
        super().__init__(parent)
        self.setObjectName("GgsSymbolGallery")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(self.THUMB)
        self.setGridSize(QSize(self.THUMB.width() + 18,
                               self.THUMB.height() + 26))
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setSpacing(2)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        if rows:
            self.setFixedHeight(max(1, int(rows))
                                * (self.gridSize().height() + 4) + 6)
        else:
            self.setMinimumHeight(2 * (self.gridSize().height() + 4) + 6)
            self.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Expanding)
        self._kind = str(kind or "polygon")
        self._dark = bool(dark)
        self._category = str(category or "symbol")
        self._loading = False
        self.itemSelectionChanged.connect(self._on_sel)

    def setItems(self, items, kind=None, dark=None, selected_key=None,
                 category=None):
        if kind is not None:
            self._kind = str(kind or "polygon")
        if dark is not None:
            self._dark = bool(dark)
        if category is not None:
            self._category = str(category or "symbol")
        self._loading = True
        try:
            self.clear()
            for it in list(items or []):
                title = _tr(it.get("title") or it.get("key") or "")
                if self._category == "symbol":
                    sym = symbol_from_item(it, self._kind, self._dark)
                    pm = sample_pixmap(sym, self._kind, self.THUMB,
                                       self._dark)
                else:
                    pm = _category_pixmap(self._category, it, self._dark,
                                          self.THUMB)
                cell = QListWidgetItem(QIcon(pm), title)
                cell.setData(Qt.ItemDataRole.UserRole, it)
                cell.setToolTip(title)
                cell.setSizeHint(self.gridSize())
                self.addItem(cell)
            self._select_key(selected_key)
        finally:
            self._loading = False

    def _select_key(self, key):
        self.clearSelection()
        if not key:
            self.setCurrentItem(None)
            return
        for i in range(self.count()):
            d = self.item(i).data(Qt.ItemDataRole.UserRole) or {}
            if str(d.get("key") or "") == str(key):
                self.setCurrentRow(i)
                return

    def current_item(self):
        items = self.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _on_sel(self):
        if self._loading:
            return
        self.picked.emit(self.current_item())


class GgsSymbolGalleryDialog(GgsDialog):

    def __init__(self, items, kind="polygon", dark=True,
                 current_key=None, parent=None, category="symbol"):
        super().__init__(parent)
        self.setObjectName("GgsSymbolGalleryDialog")
        self.setWindowTitle(_tr("样式"))
        self.resize(560, 420)
        out = QVBoxLayout(self)
        out.setContentsMargins(12, 10, 12, 10)
        out.setSpacing(8)
        self.gallery = GgsSymbolGallery(self, kind=kind, dark=dark, rows=None,
                                        category=category)
        self.gallery.setItems(items, kind=kind, dark=dark,
                              selected_key=current_key, category=category)
        self.gallery.itemDoubleClicked.connect(lambda *_: self.accept())
        out.addWidget(self.gallery, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        out.addWidget(bb)

    def item(self):
        return self.gallery.current_item()

    @staticmethod
    def getItem(items, kind="polygon", dark=True, current_key=None,
                parent=None, category="symbol"):
        if not items:
            return None
        dlg = GgsSymbolGalleryDialog(items, kind, dark, current_key, parent,
                                     category=category)
        if dlg.exec():
            return dlg.item()
        return None


