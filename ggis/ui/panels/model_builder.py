# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import json
import logging
import time

from PySide6.QtCore import (QMimeData, QPointF, QRectF, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import (
                               QAbstractItemView,
                               QCheckBox,
                               QComboBox,
                               QDoubleSpinBox,
                               QFileDialog,
                               QFormLayout,
                               QFrame,
                               QGraphicsItem,
                               QGraphicsPathItem,
                               QGraphicsScene,
                               QGraphicsView,
                               QGridLayout,
                               QHBoxLayout,
                               QLabel,
                               QListWidgetItem,
                               QMainWindow,
                               QMessageBox,
                               QScrollArea,
                               QTreeWidgetItem,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n as _i18n
from ggis.core.model import model_builder as MB
from ...core.analysis import (
                              CAP_STYLES,
                              JOIN_STYLES,
                              OP_BUFFER,
                              OP_CENTROID,
                              OP_DISSOLVE,
                              OP_SIMPLIFY,
                              OPS,
                              op_label,
)
from ggis.common.styling import icons as _icons
from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.widgets.itemviews import GgsTreeWidget
from ggis.common.styling import themes as _themes
from ggis.common.base.dialog import GgsDialog
from ggis.common.widgets.displays import GgsDimLabel
from ggis.common.widgets.inputs import GgsSearchEdit
from PySide6.QtWidgets import QLineEdit, QProgressBar, QPushButton

_log = logging.getLogger("gmagis")

_tr = _i18n.tr

_MIME = "application/x-ggis-model-node"


def _tc(key, dark, fallback="#888888"):
    try:
        return QColor(_themes.theme_color(key, dark))
    except Exception:
        _log.exception("silent exception in _tc")
        return QColor(fallback)


def _icon(name, size=16):
    try:
        ic = _icons.icon(name, size=size)
        if ic is not None and not ic.pixmap(size, size).isNull():
            return ic
    except Exception:
        _log.exception("silent exception in _icon")
    try:
        return _icons.icon("processing", size=size)
    except Exception:
        _log.exception("silent exception in _icon")
        return None


def _row_icon(name):
    try:
        from .analysis import GgsToolboxPanel
        return GgsToolboxPanel.row_icon(name)
    except Exception:
        _log.exception("silent exception in _row_icon")
        return _icon(name)


def _op_hint(op):
    try:
        from .analysis import HINTS
        return str(HINTS.get(op, "") or "")
    except Exception:
        _log.exception("silent exception in _op_hint")
        return ""


def _op_icon(op):
    try:
        from .analysis import GROUPS
        for _gname, ops in GROUPS:
            for o, icon_name in ops:
                if o == op:
                    return str(icon_name)
    except Exception:
        _log.exception("silent exception in _op_icon")
    return "processing"


def _payload(kind, **kw):
    d = {"kind": kind}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def _parse_payload(text):
    try:
        d = json.loads(str(text))
        return d if isinstance(d, dict) else None
    except Exception:
        _log.exception("silent exception in _parse_payload")
        return None


ROLE_ICON_NAME = int(Qt.ItemDataRole.UserRole) + 1


class _NodeItem(QGraphicsItem):

    W = MB.NODE_W
    H = MB.NODE_H
    PORT = 10.0

    def __init__(self, panel, node):
        super().__init__()
        self._panel = panel
        self.node = node
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
                     True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10.0 if node.kind != MB.NODE_NOTE else 6.0)
        self.setToolTip(self._tip_of())
        self.setPos(QPointF(float(node.x), float(node.y)))

    def _tip_of(self):
        t = self.node.label()
        try:
            if self.node.kind == MB.NODE_NOTE:
                t = str(self.node.text or "").strip() or t
            if not getattr(self.node, "enabled", True):
                t = "%s —— %s" % (t, _tr("已禁用"))
        except Exception:
            _log.exception("silent exception in _tip_of")
        return t

    def n_in(self):
        if self.node.kind in (MB.NODE_INPUT, MB.NODE_NOTE):
            return 0
        if self.node.kind == MB.NODE_OUTPUT:
            return 1
        spec = OPS.get(self.node.op, {})
        return 2 if spec.get("needs_overlay") else 1

    def has_out(self):
        return self.node.kind not in (MB.NODE_OUTPUT, MB.NODE_NOTE)

    def in_pos(self, i):
        n = max(1, self.n_in())
        if n == 1:
            y = self.H * 0.5
        else:
            y = self.H * (0.30 if i == 0 else 0.70)
        return QPointF(0.0, y)

    def out_pos(self):
        return QPointF(self.W, self.H * 0.5)

    def scene_in(self, i):
        return self.mapToScene(self.in_pos(i))

    def scene_out(self):
        return self.mapToScene(self.out_pos())

    def port_at(self, pos):
        loc = self.mapFromScene(self._panel.view.mapToScene(pos))
        if (self.has_out() and
                QRectF(self.W - self.PORT, self.H * 0.5 - self.PORT * 0.7,
                       self.PORT * 2, self.PORT * 1.4).contains(loc)):
            return ("out", None)
        for i in range(self.n_in()):
            p = self.in_pos(i)
            if QRectF(-self.PORT, p.y() - self.PORT * 0.7,
                      self.PORT * 2, self.PORT * 1.4).contains(loc):
                return ("in", i)
        return None

    def boundingRect(self):
        pad = self.PORT + 2.0
        return QRectF(-pad, -pad, self.W + pad * 2, self.H + pad * 2)

    def _colors(self):
        dark = getattr(self._panel, "_dark", True)
        kind = self.node.kind
        if kind == MB.NODE_INPUT:
            fill = _tc("accent_soft", dark, "#243447")
            edge = _tc("accent", dark, "#4a90d9")
        elif kind == MB.NODE_OUTPUT:
            fill = _tc("group_bg", dark, "#22301f")
            edge = _tc("success", dark, "#4caf50")
        elif kind == MB.NODE_NOTE:
            fill = _tc("warn_soft", dark, "#3b3520")
            edge = _tc("warning", dark, "#d8b657")
        else:
            fill = _tc("panel_hi", dark, "#2a2f38")
            edge = _tc("border", dark, "#555b66")
        try:
            st = str((getattr(self._panel, "_run_states", None) or {})
                     .get(self.node.nid) or "")
        except Exception:
            _log.exception("silent exception in _colors")
            st = ""
        if st == "run":
            edge = _tc("accent", dark, "#4a90d9")
        elif st == "ok":
            edge = _tc("success", dark, "#4caf50")
        elif st == "fail":
            edge = _tc("error", dark, "#e5534b")
        elif st == "skip":
            edge = _tc("text_dim", dark, "#9aa0a8")
        return fill, edge, st

    def paint(self, painter, option, widget=None):
        fill, edge, st = self._colors()
        dark = getattr(self._panel, "_dark", True)
        txt = _tc("text", dark, "#e6e6e6")
        dim = _tc("text_dim", dark, "#9aa0a8")
        sel = self.isSelected() or (self.node.nid == self._panel._sel)
        off = not getattr(self.node, "enabled", True)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if off:
            painter.setOpacity(0.45)
        box = QRectF(0.0, 0.0, self.W, self.H)
        width = 2.0 if sel else 1.0
        if st == "run":
            width = 2.6
        painter.setPen(QPen(_tc("focus", dark, "#4a90d9") if sel else edge,
                            width))
        painter.setBrush(QBrush(fill))
        painter.drawRoundedRect(box, 6.0, 6.0)

        pcol = _tc("accent", dark, "#4a90d9") if self.node.kind != \
            MB.NODE_OUTPUT else _tc("success", dark, "#4caf50")
        painter.setPen(QPen(edge, 1.0))
        painter.setBrush(QBrush(pcol))
        if self.has_out():
            c = self.out_pos()
            painter.drawRoundedRect(QRectF(c.x() - self.PORT * 0.45,
                                           c.y() - self.PORT * 0.45,
                                           self.PORT * 0.9, self.PORT * 0.9),
                                    2.0, 2.0)
        for i in range(self.n_in()):
            c = self.in_pos(i)
            painter.drawRoundedRect(QRectF(c.x() - self.PORT * 0.45,
                                           c.y() - self.PORT * 0.45,
                                           self.PORT * 0.9, self.PORT * 0.9),
                                    2.0, 2.0)

        f = QFont(painter.font())
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QPen(txt))
        inner = box.adjusted(10.0, 6.0, -10.0, -6.0)
        if self.node.kind == MB.NODE_NOTE:
            fn = QFont(painter.font())
            fn.setBold(False)
            painter.setFont(fn)
            painter.drawText(
                inner, int(Qt.AlignmentFlag.AlignLeft |
                           Qt.AlignmentFlag.AlignTop |
                           Qt.TextFlag.TextWordWrap),
                str(self.node.text or "").strip() or self.node.label())
            if off:
                painter.setOpacity(1.0)
            return
        lab = self.node.label()
        if off:
            lab = "%s（%s）" % (lab, _tr("已禁用"))
        painter.drawText(
            inner, int(Qt.AlignmentFlag.AlignLeft |
                       Qt.AlignmentFlag.AlignVCenter),
            painter.fontMetrics().elidedText(
                lab, Qt.TextElideMode.ElideRight,
                int(self.W - 22)))
        sub = self.node.subtitle()
        if sub:
            f2 = QFont(painter.font())
            f2.setBold(False)
            f2.setPointSizeF(max(6.5, f2.pointSizeF() - 1.5))
            painter.setFont(f2)
            painter.setPen(QPen(dim))
            painter.drawText(
                QRectF(inner.left(), inner.center().y(), inner.width(),
                       inner.height() / 2.0),
                int(Qt.AlignmentFlag.AlignLeft |
                    Qt.AlignmentFlag.AlignVCenter),
                painter.fontMetrics().elidedText(
                    sub, Qt.TextElideMode.ElideRight, int(self.W - 22)))
        if off:
            painter.setOpacity(1.0)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            try:
                self.node.x = float(self.pos().x())
                self.node.y = float(self.pos().y())
                self._panel.on_node_moved(self)
            except Exception:
                _log.exception("模型：节点移动后的连线刷新失败")
        return super().itemChange(change, value)


class _EdgeItem(QGraphicsPathItem):

    def __init__(self, panel, src_item, dst_item, port=0):
        super().__init__()
        self._panel = panel
        self.src = src_item
        self.dst = dst_item
        self.port = max(0, int(port))
        self.setZValue(1.0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.refresh()

    def refresh(self):
        a = self.src.scene_out()
        b = self.dst.scene_in(min(self.port, max(0, self.dst.n_in() - 1)))
        dx = max(36.0, abs(b.x() - a.x()) * 0.45)
        path = QPainterPath(a)
        path.cubicTo(QPointF(a.x() + dx, a.y()),
                     QPointF(b.x() - dx, b.y()), b)
        self.setPath(path)
        dark = getattr(self._panel, "_dark", True)
        col = _tc("accent", dark, "#4a90d9")
        col.setAlpha(210)
        self.setPen(QPen(col, 2.0 if self.isSelected() else 1.4))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))


class _ModelView(QGraphicsView):

    def __init__(self, panel):
        super().__init__(panel.scene)
        self._panel = panel
        self.setObjectName("GgsModelView")
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self._drag_from = None
        self._ghost = None
        self._ghost_a = None
        self._zoom = 1.0

    def wheelEvent(self, e):
        try:
            steps = e.angleDelta().y() / 120.0
        except Exception:
            _log.exception("silent exception in wheelEvent")
            steps = 0.0
        if not steps:
            return super().wheelEvent(e)
        f = 1.15 ** steps
        new = self._zoom * f
        if new < 0.3 or new > 4.0:
            return
        self._zoom = new
        self.scale(f, f)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            hit = self._port_hit(e.position().toPoint())
            if hit is not None:
                item, side, idx = hit
                self._drag_from = (item, side, idx)
                try:
                    self._panel._select(item.node.nid)
                except Exception:
                    _log.exception("silent exception in mousePressEvent")
                self._start_ghost(item.scene_out() if side == "out"
                                  else item.scene_in(idx))
                return
            try:
                it = self.itemAt(e.position().toPoint())
                if isinstance(it, _NodeItem):
                    self._panel._push_undo("move:%s" % it.node.nid)
            except Exception:
                _log.exception("silent exception in mousePressEvent")
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        try:
            it = self.itemAt(e.position().toPoint())
        except Exception:
            _log.exception("silent exception in mouseDoubleClickEvent")
            it = None
        if isinstance(it, _NodeItem) and it.node.kind == MB.NODE_NOTE:
            self._panel.edit_note(it.node.nid)
            return
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_from is not None:
            self._move_ghost(self.mapToScene(e.position().toPoint()))
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drag_from is not None:
            item, side, _idx = self._drag_from
            self._drag_from = None
            self._clear_ghost()
            tgt = self._port_hit(e.position().toPoint())
            if tgt is not None:
                other, oside, _ = tgt
                if side == "out" and oside == "in":
                    self._panel.connect_items(item, other)
                elif side == "in" and oside == "out":
                    self._panel.connect_items(other, item)
            super().mouseReleaseEvent(e)
            return
        super().mouseReleaseEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(_MIME):
            e.acceptProposedAction()
            return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(_MIME):
            e.acceptProposedAction()
            return
        super().dragMoveEvent(e)

    def dropEvent(self, e):
        if not e.mimeData().hasFormat(_MIME):
            return super().dropEvent(e)
        raw = bytes(e.mimeData().data(_MIME)).decode("utf-8", "ignore")
        d = _parse_payload(raw)
        if not d:
            return
        try:
            pos = e.position().toPoint()
        except Exception:
            _log.exception("silent exception in dropEvent")
            pos = e.pos()
        self._panel.add_from_payload(d, self.mapToScene(pos))
        e.acceptProposedAction()

    def keyPressEvent(self, e):
        try:
            mod = e.modifiers()
            ctrl = bool(int(mod) & int(Qt.KeyboardModifier.ControlModifier))
            k = int(e.key())
        except Exception:
            _log.exception("silent exception in keyPressEvent")
            ctrl, k = False, -1
        if ctrl:
            if k == int(Qt.Key.Key_Z):
                if bool(int(mod)
                        & int(Qt.KeyboardModifier.ShiftModifier)):
                    self._panel.redo()
                else:
                    self._panel.undo()
                return
            if k == int(Qt.Key.Key_Y):
                self._panel.redo()
                return
            if k == int(Qt.Key.Key_A):
                self._panel.select_all()
                return
            if k == int(Qt.Key.Key_C):
                self._panel.copy_selected()
                return
            if k == int(Qt.Key.Key_V):
                self._panel.paste_clip()
                return
            if k == int(Qt.Key.Key_D):
                self._panel.duplicate_selected()
                return
        if e.key() in (int(Qt.Key.Key_Delete), int(Qt.Key.Key_Backspace)):
            if self._panel.remove_selected():
                return
        if e.key() == int(Qt.Key.Key_F2):
            self._panel.fit_view()
            return
        super().keyPressEvent(e)

    def _port_hit(self, view_pos):
        for it in self.scene().items():
            if isinstance(it, _NodeItem):
                hit = it.port_at(view_pos)
                if hit is not None:
                    return (it, hit[0], hit[1])
        return None

    def _start_ghost(self, scene_pos):
        self._clear_ghost()
        self._ghost = QGraphicsPathItem()
        dark = getattr(self._panel, "_dark", True)
        col = _tc("accent", dark, "#4a90d9")
        col.setAlpha(160)
        pen = QPen(col, 1.4)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._ghost.setPen(pen)
        self._ghost.setZValue(0.5)
        self.scene().addItem(self._ghost)
        self._ghost_a = scene_pos
        self._ghost_path(scene_pos, scene_pos)

    def _move_ghost(self, scene_pos):
        if self._ghost is None:
            return
        self._ghost_path(self._ghost_a, scene_pos)

    def _ghost_path(self, a, b):
        if a is None:
            a = b
        self._ghost_a = a
        path = QPainterPath(a)
        dx = max(36.0, abs(b.x() - a.x()) * 0.45)
        path.cubicTo(QPointF(a.x() + dx, a.y()),
                     QPointF(b.x() - dx, b.y()), b)
        self._ghost.setPath(path)

    def _clear_ghost(self):
        if self._ghost is not None:
            try:
                self.scene().removeItem(self._ghost)
            except Exception:
                _log.exception("silent exception in _clear_ghost")
            self._ghost = None


class _PaletteList(GgsListWidget):

    def mimeData(self, items):
        md = QMimeData()
        for it in items:
            raw = it.data(Qt.ItemDataRole.UserRole)
            if raw:
                md.setData(_MIME, str(raw).encode("utf-8"))
                break
        return md


class _PaletteTree(GgsTreeWidget):

    def mimeData(self, items):
        md = QMimeData()
        for it in items:
            try:
                raw = it.data(0, Qt.ItemDataRole.UserRole)
            except Exception:
                _log.exception("silent exception in mimeData")
                raw = None
            if raw:
                md.setData(_MIME, str(raw).encode("utf-8"))
                break
        return md


class GgsModelBuilderWorkspace(QWidget):

    activated = Signal()

    def __init__(self, title=None, parent=None, embedded=False, window=None,
                 ribbon=None, tab_tag=None, model_id=None, view_id=None):
        super().__init__(parent)
        self.ctx = getattr(window, "ctx", None) or getattr(parent, "ctx", None)
        self._embedded = bool(embedded)
        self.model_id = model_id
        self.setObjectName("GgsModelBuilderWindow")
        if not self._embedded:
            self.setWindowTitle(title or _tr("模型构建器"))
        self._win = window if window is not None else parent
        self._ribbon_host = ribbon
        self._tab_tag = tab_tag or ("model:%d" % id(self))
        self._view_id = view_id
        self._model = MB.Model()
        self._items = {}
        self._edge_items = []
        self._sel = ""
        self._loading = False
        self._rebuilding = False
        self._syncing = False
        self._editing = None
        self._queue = []
        self._ctx = {}
        self._run_i = 0
        self._cancelled = False
        self._fitted = False
        self._undo = []
        self._redo = []
        self._undo_max = 60
        self._undo_tag = ""
        self._undo_at = 0.0
        self._clip = None
        self._run_states = {}
        self._run_log = []
        try:
            self._dark = bool(_icons.is_dark())
        except Exception:
            _log.exception("silent exception in __init__")
            self._dark = True
        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(
            QGraphicsScene.ItemIndexMethod.NoIndex)
        self._build()
        self.reload_layers()
        self.load_from_project()
        if not self._embedded:
            try:
                self.resize(1080, 720)
                self.setMinimumSize(760, 460)
            except Exception:
                _log.exception("silent exception in __init__")

    def _build(self):
        self.status_row_w = self._status_row()

        center = self._center()

        self._panel_ops = self._ops_panel()
        self._panel_layers = self._layers_panel()
        self._panel_props = self._right()

        self.shell = None
        self.dock_ops = None
        self.dock_layers = None
        self.dock_props = None
        if self._embedded and self.attach_to_main_docks():
            central = center
        else:
            self.shell = QMainWindow()
            self.shell.setObjectName("GgsModelShell")
            self.shell.setCentralWidget(center)
            central = self.shell
            self.dock_ops = self._make_dock(
                "GgsModelOpsDock", _tr("算法"), self._panel_ops,
                Qt.DockWidgetArea.LeftDockWidgetArea)
            self.dock_layers = self._make_dock(
                "GgsModelLayersDock", _tr("数据"), self._panel_layers,
                Qt.DockWidgetArea.LeftDockWidgetArea)
            try:
                self.shell.tabifyDockWidget(self.dock_ops, self.dock_layers)
                self.dock_ops.raise_()
            except Exception:
                _log.exception("silent exception in _build")
            self.dock_props = self._make_dock(
                "GgsModelPropsDock", _tr("节点参数"), self._panel_props,
                Qt.DockWidgetArea.RightDockWidgetArea)
            try:
                self.shell.resizeDocks(
                    [self.dock_ops, self.dock_layers, self.dock_props],
                    [180, 180, 250], Qt.Orientation.Horizontal)
            except Exception:
                _log.exception("silent exception in _build")

        outer = QVBoxLayout(self)
        if self._embedded:
            outer.setContentsMargins(0, 0, 0, 0)
        else:
            outer.setContentsMargins(8, 6, 8, 8)
        outer.setSpacing(0)
        if self._embedded and self._ribbon_host is not None:
            self._ribbon_bar(self._ribbon_host, tag=self._tab_tag)
        else:
            outer.addWidget(self._ribbon_bar())
        if self._embedded:
            self.status_row_w.hide()
        else:
            outer.addWidget(self.status_row_w)
        outer.addWidget(central, 1)

    def _make_dock(self, obj_name, title, widget, area):
        from ggis.ui.framework.docks import GgsDockWidget
        d = GgsDockWidget(_tr(title), self.shell)
        d.setObjectName(obj_name)
        d.setWidget(widget)
        d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.shell.addDockWidget(area, d)
        return d

    def _ribbon_bar(self, rb=None, tag=None):
        from ggis.common.styling import icons as _icons
        from ggis.ui.framework.ribbon import BIG_ICON, GgsRibbon, RibbonGroup

        if rb is None:
            rb = GgsRibbon()
            rb.setObjectName("GgsModelRibbon")
        else:
            self._tab_tag = tag
        self.rb = rb
        try:
            rb.app_button.setVisible(bool(self._embedded))
        except Exception:
            _log.exception("silent exception in _ribbon_bar")

        pg = rb.add_tab(_tr("模型"))

        g = RibbonGroup(_tr("运行"))
        self.act_run = self._rib_action(
            _icons.icon("processing", size=BIG_ICON), _tr("运行"),
            _tr("按连线顺序执行整条处理链"), self.run_model)
        g.add_action(self.act_run, big=True,
                     variant="GgsBigButtonStyle1")
        self.act_stop = self._rib_action(
            _icons.icon("cancel", size=BIG_ICON), _tr("取消"),
            _tr("中断正在运行的模型"), self.cancel_run)
        self.act_stop.setEnabled(False)
        g.add_action(self.act_stop, big=True,
                     variant="GgsBigButtonStyle1")
        pg.add_group(g)

        g = RibbonGroup(_tr("编辑"))
        self.act_undo = self._rib_action(
            _icons.icon("undo", size=BIG_ICON), _tr("撤销"),
            _tr("撤销上一步改动（Ctrl+Z）"), self.undo)
        self.act_undo.setEnabled(False)
        g.add_action(self.act_undo, big=True,
                     variant="GgsBigButtonStyle1")
        self.act_redo = self._rib_action(
            _icons.icon("redo", size=BIG_ICON), _tr("重做"),
            _tr("重做"), self.redo)
        self.act_redo.setEnabled(False)
        g.add_action(self.act_redo, big=True,
                     variant="GgsBigButtonStyle1")
        for icon_name, label, tip, slot in (
                ("label", _tr("添加注释"),
                 _tr("添加注释"), self.add_note),
                ("delete", _tr("删除选中"),
                 _tr("删除选中的节点或连线"), self.remove_selected),
                ("clear", _tr("清空"),
                 _tr("清空整张模型（不影响已产出的图层）"), self.clear_model)):
            a = self._rib_action(_icons.icon(icon_name, size=BIG_ICON),
                                 label, tip, slot)
            g.add_action(a, big=True,
                         variant="GgsBigButtonStyle1")
        pg.add_group(g)

        g = RibbonGroup(_tr("模型"))
        for icon_name, label, tip, slot in (
                ("open", _tr("导入"),
                 _tr("导入模型"), self.import_model),
                ("save", _tr("导出"),
                 _tr("导出模型"), self.export_model)):
            a = self._rib_action(_icons.icon(icon_name, size=BIG_ICON),
                                 label, tip, slot)
            g.add_action(a, big=True,
                         variant="GgsBigButtonStyle1")
        pg.add_group(g)

        g = RibbonGroup(_tr("视图"))
        for icon_name, label, tip, slot in (
                ("zoom_in", _tr("放大"), _tr("放大节点图"), self.zoom_in),
                ("zoom_out", _tr("缩小"), _tr("缩小节点图"), self.zoom_out),
                ("zoom_full", _tr("适应窗口"), _tr("把所有节点缩进视野"),
                 self.fit_view),
                ("align", _tr("整理排列"),
                 _tr("重新排布"),
                 self.auto_layout)):
            a = self._rib_action(_icons.icon(icon_name, size=BIG_ICON),
                                 label, tip, slot)
            g.add_action(a, big=True,
                         variant="GgsBigButtonStyle1")
        pg.add_group(g)
        if tag is not None:
            self._tag_ribbon_tab(rb, tag)
        return rb

    def _tag_ribbon_tab(self, rb, tag):
        try:
            i = int(getattr(rb, "_main_count", 0)) - 1
        except Exception:
            _log.exception("silent exception in _tag_ribbon_tab")
            i = -1
        if i < 0 or i >= rb.tabs.count():
            return None
        try:
            rb.tabs.setTabData(i, tag)
        except Exception:
            _log.exception("silent exception in _tag_ribbon_tab")
        idx = getattr(self, "_ribbon_indexes", None)
        if idx is None:
            idx = self._ribbon_indexes = []
        idx.append(i)
        return i

    def attach_to_main_docks(self):
        win = self._win
        if win is None or not self._embedded:
            return False
        vid = self._view_id
        if not vid:
            return False
        if win._view_docks.get(str(vid), []):
            return True
        names = (("GgsModelOpsDock", "_panel_ops", _tr("算法"),
                  Qt.DockWidgetArea.LeftDockWidgetArea),
                 ("GgsModelLayersDock", "_panel_layers", _tr("数据"),
                  Qt.DockWidgetArea.LeftDockWidgetArea),
                 ("GgsModelPropsDock", "_panel_props", _tr("节点参数"),
                  Qt.DockWidgetArea.RightDockWidgetArea))
        docks = []
        left = None
        for obj_name, panel_attr, title, area in names:
            panel = getattr(self, panel_attr, None)
            if panel is None:
                return False
            try:
                from ggis.ui.framework.docks import GgsDockWidget
            except Exception:
                _log.exception("silent exception in attach_to_main_docks")
                return False
            d = GgsDockWidget(title, win)
            d.setObjectName(obj_name)
            try:
                d.setWidget(panel)
            except Exception:
                _log.exception("silent exception in attach_to_main_docks")
            try:
                win.addDockWidget(area, d)
                d.setFloating(False)
                d.hide()
            except Exception:
                _log.exception("silent exception in attach_to_main_docks")
            docks.append(d)
            if area == Qt.DockWidgetArea.LeftDockWidgetArea and left is None:
                left = d
        if len(docks) >= 2 and docks[0] is not None and docks[1] is not None:
            try:
                win.tabifyDockWidget(docks[0], docks[1])
                docks[0].raise_()
            except Exception:
                _log.exception("silent exception in attach_to_main_docks")
        try:
            from ggis.main_window import DOCK_W
        except Exception:
            _log.exception("silent exception in attach_to_main_docks")
            DOCK_W = 300
        for d in docks:
            try:
                d.setMinimumWidth(int(d.minimumSizeHint().width() or 0))
                d.setMaximumWidth(16777215)
                win.resizeDocks([d], [int(DOCK_W)], Qt.Orientation.Horizontal)
            except Exception:
                _log.exception("silent exception in attach_to_main_docks")
        self.dock_ops = docks[0] if len(docks) > 0 else None
        self.dock_layers = docks[1] if len(docks) > 1 else None
        self.dock_props = docks[2] if len(docks) > 2 else None
        win.ctx.region("dock")._register_view_docks(vid, docks)
        return True

    def detach_from_main_docks(self):
        win = self._win
        if win is None or not self._view_id:
            return
        try:
            win._unregister_view_docks(self._view_id)
        except Exception:
            _log.exception("silent exception in detach_from_main_docks")

    def _rib_action(self, icon, text, tip, slot):
        a = QAction(icon, str(text), self)
        a.setToolTip(str(tip))
        a.triggered.connect(lambda _c=False, sl=slot: sl())
        if not hasattr(self, "_rib_actions"):
            self._rib_actions = []
        self._rib_actions.append(a)
        return a

    def _status_row(self):
        from ggis.ui.framework.statusbar import STATUS_CTRL_H, STATUS_H

        w = GgsModelStatusRow()
        row = QHBoxLayout(w)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(6)
        self.bar = GgsModelBar()
        self.bar.setRange(0, 100)
        self.bar.setVisible(False)
        self.bar.setMaximumWidth(180)
        row.addWidget(self.bar)
        self.lbl_stage = GgsDimLabel("")
        row.addWidget(self.lbl_stage, 1)
        try:
            w.setFixedHeight(STATUS_H + 2)
            self.bar.setFixedHeight(STATUS_CTRL_H)
            self.lbl_stage.setFixedHeight(STATUS_CTRL_H)
        except Exception:
            _log.exception("silent exception in _status_row")
        self.status_row_w = w
        return w

    def _make_list(self):
        lw = _PaletteList()
        lw.setDragEnabled(True)
        lw.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        lw.setDefaultDropAction(Qt.DropAction.CopyAction)
        lw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        lw.setIconSize(QSize(16, 16))
        lw.setUniformItemSizes(True)
        lw.setWordWrap(False)
        lw.setMinimumWidth(140)
        return lw

    @staticmethod
    def _setup_tree(tree):
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(True)
        tree.setIndentation(16)
        tree.setUniformRowHeights(True)
        tree.setAnimated(False)
        tree.setIconSize(QSize(16, 16))
        tree.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        tree.setDragEnabled(True)
        tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        tree.setDefaultDropAction(Qt.DropAction.CopyAction)
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.setMinimumWidth(140)
        return tree

    def _ops_panel(self):
        w = GgsModelOpsPanel()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.edit_ops = GgsSearchEdit()
        self.edit_ops.setPlaceholderText(_tr("搜索算法…"))
        self.edit_ops.setClearButtonEnabled(True)
        self.edit_ops.textChanged.connect(self._filter_ops)
        v.addWidget(self.edit_ops)
        self.lst_ops = self._setup_tree(_PaletteTree())
        self.lst_ops.setToolTip(_tr("把算法拖到画布上；双击也可以添加"))
        self.lst_ops.itemDoubleClicked.connect(self._on_palette_dbl)
        self.lst_ops.customContextMenuRequested.connect(self._on_ops_menu)
        v.addWidget(self.lst_ops, 1)
        self._fill_palette_ops()
        return w

    def _layers_panel(self):
        w = GgsModelLayersPanel()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        self.lst_layers = self._make_list()
        self.lst_layers.setToolTip("")
        self.lst_layers.itemDoubleClicked.connect(self._on_palette_dbl)
        v.addWidget(self.lst_layers, 1)
        return w

    def _center(self):
        self.view = _ModelView(self)
        self.scene.selectionChanged.connect(self._on_scene_sel)
        self._context_menu()
        return self.view

    def _right(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        area = GgsModelParamArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        self._param_host = GgsModelParam()
        self._param_lay = QVBoxLayout(self._param_host)
        self._param_lay.setContentsMargins(2, 2, 2, 2)
        self._param_lay.setSpacing(6)
        area.setWidget(self._param_host)
        v.addWidget(area, 1)
        self.lbl_hint = GgsDimLabel("")
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setVisible(False)
        v.addWidget(self.lbl_hint)
        return w

    def _context_menu(self):
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_canvas_menu)

    def _on_canvas_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        item = None
        try:
            vp_pos = self.view.viewport().mapFrom(self.view, pos)
            item = self.view.itemAt(vp_pos)
        except Exception:
            _log.exception("silent exception in _on_canvas_menu")
            item = None
        m = QMenu(self.view)
        if isinstance(item, _NodeItem):
            node = item.node
            try:
                self.scene.clearSelection()
                item.setSelected(True)
                self._sel = node.nid
                self._rebuild_params()
            except Exception:
                _log.exception("silent exception in _on_canvas_menu")
            a = QAction(_tr("删除节点"), m)
            a.triggered.connect(lambda _c=False, it=item:
                                self._remove_node_item(it))
            m.addAction(a)
            a = QAction(_tr("复制"), m)
            a.triggered.connect(lambda _c=False: self.copy_selected())
            m.addAction(a)
            if node.kind == MB.NODE_OP:
                lab = (_tr("禁用此节点") if getattr(node, "enabled", True)
                       else _tr("启用此节点"))
                a = QAction(lab, m)
                a.triggered.connect(
                    lambda _c=False: self.toggle_enabled_selected())
                m.addAction(a)
            if node.kind == MB.NODE_NOTE:
                a = QAction(_tr("编辑注释…"), m)
                a.triggered.connect(lambda _c=False, n=node.nid:
                                    self.edit_note(n))
                m.addAction(a)
            if node.kind == MB.NODE_INPUT:
                a2 = QAction(_tr("设为活动数据"), m)
                a2.triggered.connect(lambda _c=False, n=node:
                                     self._select(n.nid))
                m.addAction(a2)
            m.addSeparator()
        a = QAction(_tr("粘贴"), m)
        a.setEnabled(bool(self._clip))
        a.triggered.connect(lambda _c=False: self.paste_clip())
        m.addAction(a)
        try:
            sp = self.view.mapToScene(pos)
        except Exception:
            _log.exception("silent exception in _on_canvas_menu")
            sp = None
        a = QAction(_tr("添加注释"), m)
        a.triggered.connect(lambda _c=False, p=sp: self.add_note(p))
        m.addAction(a)
        a = QAction(_tr("整理排列"), m)
        a.triggered.connect(lambda _c=False: self.auto_layout())
        m.addAction(a)
        a = QAction(_tr("适应窗口"), m)
        a.triggered.connect(self.fit_view)
        m.addAction(a)
        m.exec(self.view.mapToGlobal(pos))

    def _remove_node_item(self, item):
        self._push_undo()
        self._model.remove_node(item.node.nid)
        if self._sel == item.node.nid:
            self._sel = ""
        self._rebuild()
        self._mark_dirty()

    def _group_font(self):
        f = QFont(self.lst_ops.font())
        f.setBold(True)
        return f

    def _fill_palette_ops(self):
        try:
            from .analysis import GROUPS
        except Exception:
            _log.exception("silent exception in _fill_palette_ops")
            GROUPS = []
        self.lst_ops.clear()
        self._op_items = []
        for gname, ops in GROUPS:
            grp = QTreeWidgetItem([_tr(gname)])
            grp.setFlags(Qt.ItemFlag.ItemIsEnabled)
            grp.setFont(0, self._group_font())
            grp.setIcon(0, _row_icon("folder"))
            grp.setData(0, ROLE_ICON_NAME, "folder")
            grp.setToolTip(0, _tr("算法分类"))
            self.lst_ops.addTopLevelItem(grp)
            for op, icon_name in ops:
                it = QTreeWidgetItem([_tr(op_label(op))])
                it.setIcon(0, _row_icon(icon_name))
                it.setData(0, ROLE_ICON_NAME, icon_name)
                hint = _op_hint(op)
                it.setToolTip(0, ("%s\n%s" % (op_label(op), _tr(hint))).strip()
                              if hint else _tr(op_label(op)))
                it.setData(0, Qt.ItemDataRole.UserRole,
                           _payload("op", op=op, label=op_label(op)))
                grp.addChild(it)
                self._op_items.append((it, op))
            grp.setExpanded(True)

        grp = QTreeWidgetItem([_tr("输出")])
        grp.setFlags(Qt.ItemFlag.ItemIsEnabled)
        grp.setFont(0, self._group_font())
        grp.setIcon(0, _row_icon("folder"))
        grp.setData(0, ROLE_ICON_NAME, "folder")
        grp.setToolTip(0, _tr("算法分类"))
        self.lst_ops.addTopLevelItem(grp)
        it = QTreeWidgetItem([_tr("结果")])
        it.setIcon(0, _row_icon("layer"))
        it.setData(0, ROLE_ICON_NAME, "layer")
        it.setToolTip(0, "")
        it.setData(0, Qt.ItemDataRole.UserRole,
                   _payload("output", label=_tr("结果")))
        grp.addChild(it)
        grp.setExpanded(True)

    def _filter_ops(self, text):
        text = str(text or "").strip().lower()
        for i in range(self.lst_ops.topLevelItemCount()):
            grp = self.lst_ops.topLevelItem(i)
            shown = 0
            for j in range(grp.childCount()):
                it = grp.child(j)
                d = _parse_payload(self._raw_of(it)) or {}
                op = str(d.get("op") or "")
                hay = "%s %s %s" % (it.text(0), op, _tr(_op_hint(op)))
                hit = (not text) or (text in hay.lower())
                it.setHidden(not hit)
                shown += 1 if hit else 0
            grp.setHidden(shown == 0)
            if text and shown:
                grp.setExpanded(True)

    def _on_ops_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        it = self.lst_ops.itemAt(pos)
        d = _parse_payload(self._raw_of(it)) if it is not None else None
        m = QMenu(self.lst_ops)
        if d:
            op = str(d.get("op") or "")
            a = QAction(_icon("plus"), _tr("添加到画布"), m)
            a.triggered.connect(lambda _c=False, p=dict(d):
                                self.add_from_payload(p, self._next_drop_pos()))
            m.addAction(a)
            if op:
                m.addSeparator()
                b = QAction(_icon("info"), _tr("算法说明"), m)
                b.triggered.connect(lambda _c=False, o=op:
                                    self._show_op_hint(o))
                m.addAction(b)
        else:
            a = QAction(_icon("expand_all"), _tr("展开全部"), m)
            a.triggered.connect(self.lst_ops.expandAll)
            m.addAction(a)
            b = QAction(_icon("collapse_all"), _tr("折叠全部"), m)
            b.triggered.connect(self.lst_ops.collapseAll)
            m.addAction(b)
        m.exec(self.lst_ops.viewport().mapToGlobal(pos))

    def _show_op_hint(self, op):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, _tr(OPS.get(op, {}).get("label", op)),
            _tr(_op_hint(op)) or "")

    @staticmethod
    def _raw_of(item):
        if item is None:
            return ""
        try:
            if isinstance(item, QTreeWidgetItem):
                return item.data(0, Qt.ItemDataRole.UserRole) or ""
            return item.data(Qt.ItemDataRole.UserRole) or ""
        except Exception:
            _log.exception("silent exception in _raw_of")
            return ""

    def retheme(self):
        try:
            for i in range(self.lst_ops.topLevelItemCount()):
                grp = self.lst_ops.topLevelItem(i)
                if grp is None:
                    continue
                self._reset_row_icon(grp)
                for j in range(grp.childCount()):
                    self._reset_row_icon(grp.child(j))
        except Exception:
            _log.exception("silent exception in retheme")
        lst = getattr(self, "lst_layers", None)
        if lst is None:
            return
        try:
            for i in range(lst.count()):
                self._reset_row_icon(lst.item(i))
        except Exception:
            _log.exception("silent exception in retheme")

    @staticmethod
    def _reset_row_icon(item):
        if item is None:
            return
        try:
            name = item.data(ROLE_ICON_NAME)
            if not name:
                name = item.data(0, ROLE_ICON_NAME)
        except Exception:
            _log.exception("silent exception in _reset_row_icon")
            return
        if not name:
            return
        try:
            if isinstance(item, QTreeWidgetItem):
                item.setIcon(0, _row_icon(name))
            else:
                item.setIcon(_row_icon(name))
        except Exception:
            _log.exception("silent exception in _reset_row_icon")

    def reload_layers(self):
        self.lst_layers.clear()
        for lyr in self._project_layers():
            try:
                if not lyr.is_vector():
                    continue
                name = str(lyr.name() or "")
            except Exception:
                _log.exception("silent exception in reload_layers")
                continue
            it = QListWidgetItem(name or _tr("（未命名图层）"))
            it.setIcon(_icon("layer"))
            it.setData(ROLE_ICON_NAME, "layer")
            it.setToolTip(name)
            it.setData(Qt.ItemDataRole.UserRole,
                       _payload("input", layer_id=str(_lid(lyr)),
                                label=name))
            self.lst_layers.addItem(it)

    def _on_palette_dbl(self, item, _col=0):
        raw = self._raw_of(item)
        if not raw:
            return
        d = _parse_payload(raw)
        if not d:
            return
        self.add_from_payload(d, self._next_drop_pos())

    def _next_drop_pos(self):
        try:
            c = self.view.mapToScene(self.view.viewport().rect().center())
        except Exception:
            _log.exception("silent exception in _next_drop_pos")
            c = QPointF(0.0, 0.0)
        n = len(self._model.nodes)
        off = float((n % 5) * 24)
        return QPointF(c.x() - _NodeItem.W / 2.0 + off,
                       c.y() - _NodeItem.H / 2.0 + off)

    def _project(self):
        try:
            return self._win._project()
        except Exception:
            _log.exception("silent exception in _project")
            from ggis.core.model.project import GgsProject
            return GgsProject.instance()

    def _project_layers(self):
        try:
            return list(self._project().layers())
        except Exception:
            _log.exception("silent exception in _project_layers")
            return []

    def _layer_ids(self):
        return {str(_lid(l)) for l in self._project_layers()}

    def _find_layer(self, lid):
        lid = str(lid or "")
        if not lid:
            return None
        for l in self._project_layers():
            if str(_lid(l)) == lid:
                return l
        return None

    def _rebuild(self):
        self._rebuilding = True
        try:
            self.scene.clear()
            self._items = {}
            self._edge_items = []
            for n in self._model.nodes.values():
                it = _NodeItem(self, n)
                self.scene.addItem(it)
                self._items[n.nid] = it
            _seen_in = {}
            for s, d in self._model.edges:
                a, b = self._items.get(s), self._items.get(d)
                if a is None or b is None or not b.n_in():
                    continue
                port = _seen_in.get(d, 0)
                _seen_in[d] = port + 1
                e = _EdgeItem(self, a, b, port)
                self.scene.addItem(e)
                self._edge_items.append(e)
            self._refresh_edges(exact=True)
            self._sel = "" if self._sel not in self._items else self._sel
            self._rebuild_params()
            it = self._items.get(self._sel)
            if it is not None:
                it.setSelected(True)
        finally:
            self._rebuilding = False
        self._auto_fit_once()

    def _refresh_edges(self, exact=False):
        for e in self._edge_items:
            try:
                e.refresh()
            except Exception:
                _log.exception("silent exception in _refresh_edges")
        self._sync_scene_rect(exact)

    def _sync_scene_rect(self, exact=False):
        try:
            r = self.scene.itemsBoundingRect()
        except Exception:
            _log.exception("silent exception in _sync_scene_rect")
            return
        if r.isEmpty():
            return
        want = r.adjusted(-400.0, -300.0, 400.0, 300.0)
        try:
            cur = self.scene.sceneRect()
        except Exception:
            _log.exception("silent exception in _sync_scene_rect")
            cur = None
        if not exact and cur is not None:
            if cur.contains(r):
                return
            want = cur.united(want)
        try:
            self.scene.setSceneRect(want)
        except Exception:
            _log.exception("silent exception in _sync_scene_rect")

    def on_node_moved(self, item):
        if self._loading or self._rebuilding or self._syncing:
            return
        self._syncing = True
        try:
            self._refresh_edges()
            self._mark_dirty()
        finally:
            self._syncing = False

    def add_from_payload(self, d, scene_pos):
        kind = str(d.get("kind") or "")
        node = None
        if kind == "input":
            node = MB.ModelNode(MB.NODE_INPUT,
                                title=str(d.get("label") or _tr("数据")),
                                layer_id=str(d.get("layer_id") or ""),
                                layer_name=str(d.get("label") or ""))
        elif kind == "output":
            node = MB.ModelNode(MB.NODE_OUTPUT, title=_tr("结果"),
                                output_name=self._suggest_output_name())
        elif kind == "op":
            op = str(d.get("op") or "")
            if op not in OPS:
                return
            node = MB.ModelNode(MB.NODE_OP, op=op)
        if node is None:
            return
        node.x = float(scene_pos.x())
        node.y = float(scene_pos.y())
        self._push_undo()
        self._model.add_node(node)
        self._rebuild()
        self._select(node.nid)
        self._mark_dirty()

    def _suggest_output_name(self):
        base = _tr("结果")
        names = set()
        try:
            names = {str(l.name()) for l in self._project_layers()}
        except Exception:
            _log.exception("silent exception in _suggest_output_name")
        name = base
        i = 1
        while name in names:
            i += 1
            name = "%s_%d" % (base, i)
        return name

    def connect_items(self, src_item, dst_item):
        self._push_undo()
        try:
            self._model.connect(src_item.node.nid, dst_item.node.nid)
        except Exception as e:
            msg = str(e) or _tr("这条连线不成立")
            self.lbl_stage.setText(msg)
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("无法连接"), msg)
            except Exception:
                _log.exception("silent exception in connect_items")
            return
        self._rebuild()
        self._mark_dirty()

    def remove_selected(self):
        nids = [nid for nid, it in self._items.items() if it.isSelected()]
        sel_edges = [e for e in self._edge_items if e.isSelected()]
        if not nids and not sel_edges:
            return False
        self._push_undo()
        if not nids:
            n = 0
            for e in list(self._edge_items):
                if e.isSelected():
                    s = e.src.node.nid
                    d = e.dst.node.nid
                    if self._model.disconnect(s, d):
                        n += 1
            if not n:
                return False
            self._rebuild()
            self._mark_dirty()
            return True
        for nid in nids:
            self._model.remove_node(nid)
            if self._sel == nid:
                self._sel = ""
        self._rebuild()
        self._mark_dirty()
        return True

    def _push_undo(self, tag=""):
        if self._loading or self._rebuilding:
            return
        now = time.monotonic()
        if tag and self._undo_tag == tag and (now - float(self._undo_at)) < 0.9:
            self._undo_at = now
            return
        try:
            snap = self._model.to_dict()
        except Exception:
            _log.exception("模型：撤销快照失败")
            return
        self._undo.append(snap)
        if len(self._undo) > int(self._undo_max):
            del self._undo[0]
        self._redo = []
        self._undo_tag = str(tag or "")
        self._undo_at = now
        self._sync_edit_actions()

    def _restore(self, snap):
        self._loading = True
        try:
            self._model = MB.Model.from_dict(snap)
        finally:
            self._loading = False
        self._sel = "" if self._sel not in self._model.nodes else self._sel
        self._undo_tag = ""
        self._rebuild()
        self._mark_dirty()

    def undo(self):
        if not self._undo:
            self.lbl_stage.setText(_tr("没有可撤销的操作"))
            return False
        try:
            self._redo.append(self._model.to_dict())
        except Exception:
            _log.exception("silent exception in undo")
        self._restore(self._undo.pop())
        self.lbl_stage.setText(_tr("已撤销"))
        self._sync_edit_actions()
        return True

    def redo(self):
        if not self._redo:
            self.lbl_stage.setText(_tr("没有可重做的操作"))
            return False
        try:
            self._undo.append(self._model.to_dict())
        except Exception:
            _log.exception("silent exception in redo")
        self._restore(self._redo.pop())
        self.lbl_stage.setText(_tr("已重做"))
        self._sync_edit_actions()
        return True

    def _selected_nids(self):
        return [nid for nid, it in self._items.items() if it.isSelected()]

    def select_all(self):
        for it in self._items.values():
            it.setSelected(True)
        return bool(self._items)

    def copy_selected(self):
        nids = self._selected_nids()
        if not nids and self._sel:
            nids = [self._sel]
        if not nids:
            return False
        nodes, edges = self._model.copy_fragment(nids)
        if not nodes:
            return False
        self._clip = (nodes, edges)
        self.lbl_stage.setText(
            _tr("已复制 {0} 个节点").format(len(nodes)))
        return True

    def paste_clip(self):
        if not self._clip:
            return False
        nodes, edges = self._clip
        self._push_undo()
        new, _n = self._model.paste_fragment(nodes, edges, dx=24.0, dy=24.0)
        if not new:
            return False
        self._rebuild()
        self._select(new[0])
        self._mark_dirty()
        self.lbl_stage.setText(_tr("已粘贴 {0} 个节点").format(len(new)))
        return True

    def duplicate_selected(self):
        if not self.copy_selected():
            return False
        return self.paste_clip()

    def toggle_enabled_selected(self):
        nids = self._selected_nids() or ([self._sel] if self._sel else [])
        nids = [n for n in nids
                if self._model.node(n) is not None
                and self._model.node(n).kind == MB.NODE_OP]
        if not nids:
            return False
        self._push_undo()
        for nid in nids:
            n = self._model.node(nid)
            n.enabled = not bool(n.enabled)
        self._rebuild()
        self._mark_dirty()
        self.lbl_stage.setText(
            _tr("已切换 {0} 个节点的启用状态").format(len(nids)))
        return True

    def add_note(self, scene_pos=None):
        self._push_undo()
        pos = scene_pos if scene_pos is not None else self._next_drop_pos()
        node = MB.ModelNode(MB.NODE_NOTE, title=_tr("注释"))
        node.x = float(pos.x())
        node.y = float(pos.y())
        self._model.add_node(node)
        self._rebuild()
        self._select(node.nid)
        self._mark_dirty()
        self.edit_note(node.nid)
        return True

    def edit_note(self, nid):
        n = self._model.node(str(nid or ""))
        if n is None or n.kind != MB.NODE_NOTE:
            return False
        try:
            from PySide6.QtWidgets import QInputDialog
            txt, ok = QInputDialog.getMultiLineText(
                self, _tr("注释"), _tr("写点说明（会显示在画布上）："),
                str(n.text or ""))
        except Exception:
            _log.exception("模型：注释编辑失败")
            return False
        if not ok:
            return False
        self._push_undo()
        n.text = str(txt or "")
        self._rebuild()
        self._mark_dirty()
        return True

    def auto_layout(self):
        if self._model.is_empty():
            return False
        self._push_undo()
        pos = self._model.auto_layout() or {}
        if not pos:
            return False
        for nid, xy in pos.items():
            n = self._model.node(nid)
            if n is None:
                continue
            n.x, n.y = float(xy[0]), float(xy[1])
        self._rebuild()
        self._mark_dirty()
        self.fit_view()
        self.lbl_stage.setText(_tr("已按依赖关系整理"))
        return True

    def zoom_in(self):
        self.zoom_by(1.25)

    def zoom_out(self):
        self.zoom_by(1.0 / 1.25)

    def _sync_edit_actions(self):
        try:
            self.act_undo.setEnabled(bool(self._undo))
        except Exception:
            _log.exception("silent exception in _sync_edit_actions")
        try:
            self.act_redo.setEnabled(bool(self._redo))
        except Exception:
            _log.exception("silent exception in _sync_edit_actions")

    def zoom_by(self, factor):
        try:
            new = float(self.view._zoom) * float(factor)
        except Exception:
            _log.exception("silent exception in zoom_by")
            new = 1.0
        new = max(0.3, min(4.0, new))
        try:
            self.view.scale(new / float(self.view._zoom),
                            new / float(self.view._zoom))
            self.view._zoom = new
        except Exception:
            _log.exception("silent exception in zoom_by")

    def zoom_reset(self):
        try:
            self.view.resetTransform()
            self.view._zoom = 1.0
        except Exception:
            _log.exception("silent exception in zoom_reset")

    def export_model(self):
        if self._model.is_empty():
            return False
        path, _f = QFileDialog.getSaveFileName(
            self, _tr("导出模型"), "",
            _tr("模型文件 (*.ggismodel);;JSON 文件 (*.json)"))
        if not path:
            return False
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self._model.to_dict(), fh, ensure_ascii=False,
                          indent=1)
        except Exception as e:
            _log.exception("模型：导出失败")
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("导出失败"), str(e))
            except Exception:
                _log.exception("silent exception in export_model")
            return False
        self.lbl_stage.setText(_tr("已导出模型"))
        return True

    def import_model(self):
        path, _f = QFileDialog.getOpenFileName(
            self, _tr("导入模型"), "",
            _tr("模型文件 (*.ggismodel);;JSON 文件 (*.json);;所有文件 (*)"))
        if not path:
            return False
        try:
            with open(path, "r", encoding="utf-8") as fh:
                d = json.load(fh)
            model = MB.Model.from_dict(d)
        except Exception as e:
            _log.exception("模型：导入失败")
            try:
                from ggis.common.base.dialog import GgsMsgBox
                GgsMsgBox.warning(self, _tr("导入失败"), str(e))
            except Exception:
                _log.exception("silent exception in import_model")
            return False
        self._push_undo()
        self._model = model
        self._sel = ""
        self._rebuild()
        self._mark_dirty()
        self._auto_fit_once()
        self.lbl_stage.setText(_tr("已导入模型"))
        return True

    def clear_model(self):
        if self._model.is_empty():
            return
        self._push_undo()
        self._model.clear()
        self._sel = ""
        self._rebuild()
        self._mark_dirty()

    def fit_view(self):
        try:
            r = self.scene.itemsBoundingRect()
            if r.isEmpty():
                return
            self.view.fitInView(r.adjusted(-24, -24, 24, 24),
                                Qt.AspectRatioMode.KeepAspectRatio)
            m = float(self.view.transform().m11() or 0.0)
            if m <= 0.0 or m > 1.0:
                self.view.resetTransform()
                self.view._zoom = 1.0
                self.view.centerOn(r.center())
            else:
                self.view._zoom = m
        except Exception:
            _log.exception("silent exception in fit_view")

    def _auto_fit_once(self):
        if self._fitted or not self._model.nodes:
            return
        try:
            if (self.view.viewport().width() < 50
                    or not self.view.isVisible()):
                return
        except Exception:
            _log.exception("silent exception in _auto_fit_once")
            return
        self._fitted = True
        self.fit_view()

    def _select(self, nid):
        self._sel = str(nid or "")
        it = self._items.get(self._sel)
        if it is not None:
            try:
                self.scene.clearSelection()
                it.setSelected(True)
            except Exception:
                _log.exception("silent exception in _select")
        self._rebuild_params()

    def _on_scene_sel(self):
        if getattr(self, "_rebuilding", False):
            return
        sel = [it for it in self.scene.selectedItems()
               if isinstance(it, _NodeItem)]
        self._sel = sel[0].node.nid if sel else ""
        self._rebuild_params()

    def _clear_params(self):
        while self._param_lay.count():
            self._drop_param_item(self._param_lay.takeAt(0))

    def _drop_param_item(self, item):
        try:
            w = item.widget()
        except Exception:
            _log.exception("silent exception in _drop_param_item")
            w = None
        if w is not None:
            try:
                w.hide()
            except Exception:
                _log.exception("silent exception in _drop_param_item")
            w.setParent(None)
            w.deleteLater()
            return
        try:
            lay = item.layout()
        except Exception:
            _log.exception("silent exception in _drop_param_item")
            lay = None
        if lay is None:
            return
        while lay.count():
            self._drop_param_item(lay.takeAt(0))
        try:
            lay.deleteLater()
        except Exception:
            _log.exception("silent exception in _drop_param_item")

    def _hint(self, text):
        text = str(text or "")
        try:
            self.lbl_hint.setText(text)
            self.lbl_hint.setVisible(bool(text.strip()))
        except Exception:
            _log.exception("silent exception in _hint")

    def _sect(self, title):
        lab = GgsModelSect(_tr(title))
        self._param_lay.addWidget(lab)

    def _dim(self, text, wrap=True):
        lab = GgsModelSub(str(text))
        lab.setWordWrap(bool(wrap))
        return lab

    @staticmethod
    def _form():
        f = QFormLayout()
        f.setContentsMargins(0, 0, 0, 0)
        f.setSpacing(6)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter)
        f.setFormAlignment(Qt.AlignmentFlag.AlignLeft
                           | Qt.AlignmentFlag.AlignTop)
        f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        f.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return f

    def _rebuild_params(self):
        self._clear_params()
        node = self._model.node(self._sel)
        if node is None:
            self._empty_block()
            self._hint("")
            self._relax_param_widths()
            return
        self._hint("")
        self._head_block(node)
        if node.kind == MB.NODE_INPUT:
            self._param_input(node)
        elif node.kind == MB.NODE_OUTPUT:
            self._param_output(node)
        elif node.kind == MB.NODE_NOTE:
            self._param_note(node)
        else:
            self._param_op(node)
        self._conn_block(node)
        self._param_lay.addStretch(1)
        self._relax_param_widths()

    def _relax_param_widths(self):
        try:
            from ggis.common.widgets.inputs import relax_wide_inputs
            relax_wide_inputs(self._param_host, limit=96)
        except Exception:
            _log.exception("silent exception in _relax_param_widths")

    def _param_note(self, node):
        self._sect(_tr("注释"))
        form = self._form()
        txt = str(node.text or "").strip() or ""
        lab = self._dim(txt)
        form.addRow(lab)
        btn = GgsModelBtn(_tr("编辑注释…"))
        btn.clicked.connect(lambda _c=False, n=node.nid: self.edit_note(n))
        form.addRow(btn)
        self._param_lay.addLayout(form)

    def _empty_block(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(8, 28, 8, 8)
        v.setSpacing(6)
        ic = QLabel()
        ic.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        try:
            ic.setPixmap(_icon("model", size=32).pixmap(32, 32))
        except Exception:
            _log.exception("silent exception in _empty_block")
        v.addWidget(ic)
        title = GgsModelEmpty(_tr("未选中节点"))
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(title)
        sub = GgsModelSub("")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sub.setWordWrap(True)
        v.addWidget(sub)
        v.addStretch(1)
        self._param_lay.addWidget(box)

    def _head_block(self, node):
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        ic = QLabel()
        try:
            ic.setPixmap(_icon(self._head_icon(node), size=20).pixmap(20, 20))
        except Exception:
            _log.exception("silent exception in _head_block")
        h.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        if node.kind == MB.NODE_OP:
            t = GgsModelCap(node.label())
            t.setWordWrap(True)
            col.addWidget(t)
        else:
            ed = GgsModelLine(str(node.title or ""))
            ed.setPlaceholderText(
                _tr("注释") if node.kind == MB.NODE_NOTE
                else ((node.layer_name or _tr("数据"))
                      if node.kind == MB.NODE_INPUT
                      else (node.output_name or _tr("结果"))))
            ed.setToolTip("")
            ed.textChanged.connect(lambda s, n=node: self._set_title(n, s))
            col.addWidget(ed)
        sub = GgsModelSub(self._head_sub(node))
        sub.setWordWrap(True)
        col.addWidget(sub)
        h.addLayout(col, 1)
        self._param_lay.addWidget(box)

    @staticmethod
    def _head_icon(node):
        if node.kind == MB.NODE_OP:
            return _op_icon(node.op)
        if node.kind == MB.NODE_NOTE:
            return "label"
        return "layer"

    def _head_sub(self, node):
        if node.kind == MB.NODE_NOTE:
            return _tr("注释 · 双击画布上的便签改内容")
        if node.kind == MB.NODE_INPUT:
            lyr = self._find_layer(node.layer_id)
            name = ""
            try:
                name = str(lyr.name() or "") if lyr is not None else ""
            except Exception:
                _log.exception("silent exception in _head_sub")
                name = ""
            return _tr("数据 · {0}").format(
                name or str(node.layer_name or "") or _tr("未选择图层"))
        if node.kind == MB.NODE_OUTPUT:
            return _tr("结果 · {0}").format(
                str(node.output_name or "") or _tr("未命名"))
        return _tr("算子 · {0}").format(self._op_desc(node.op))

    @staticmethod
    def _op_desc(op):
        try:
            from ..dialogs.analysis import GgsAnalysisDialog
            txt = str(GgsAnalysisDialog._describe(op, OPS.get(op, {})) or "")
            if txt:
                return _tr(txt)
        except Exception:
            _log.exception("silent exception in _op_desc")
        return _tr(_op_hint(op))

    def _conn_block(self, node):
        if node.kind == MB.NODE_NOTE:
            return
        self._sect(_tr("连接"))
        form = self._form()
        srcs = self._model.inputs_of(node.nid)
        if node.kind != MB.NODE_INPUT:
            n_in = 1
            if node.kind == MB.NODE_OP and OPS.get(node.op, {}).get(
                    "needs_overlay"):
                n_in = 2
            for i in range(n_in):
                has = i < len(srcs)
                lab = (_tr("输入") if n_in == 1
                       else _tr("输入{0}").format("①②③④"[i]))
                if has:
                    form.addRow(lab, self._conn_value(
                        self._conn_label(srcs[i]), True))
                else:
                    form.addRow(lab, self._conn_value(
                        _tr("（未连接）"), False))
        outs = self._model.outputs_of(node.nid)
        if outs:
            names = [self._conn_label(nid) for nid in outs]
            txt = "、".join(names[:3]) + ("…" if len(names) > 3 else "")
        else:
            txt = _tr("（未连接）")
        form.addRow(_tr("输出"), self._conn_value(txt, bool(outs)))
        self._param_lay.addLayout(form)

    @staticmethod
    def _conn_value(text, real):
        lab = QLabel(str(text))
        lab.setObjectName("GgsModelVal" if real else "GgsModelSub")
        lab.setWordWrap(True)
        lab.setToolTip(str(text))
        return lab

    def _conn_label(self, nid):
        n = self._model.node(nid)
        if n is None:
            return _tr("（节点已删除）")
        if n.kind == MB.NODE_INPUT:
            lyr = self._find_layer(n.layer_id)
            name = ""
            try:
                name = str(lyr.name() or "") if lyr is not None else ""
            except Exception:
                _log.exception("silent exception in _conn_label")
                name = ""
            return _tr("{0}（{1}）").format(
                n.label(), name or str(n.layer_name or "")
                or _tr("图层已不在工程中"))
        return n.label()

    def _param_input(self, node):
        self._sect(_tr("数据"))
        form = self._form()
        cmb = GgsModelCmb()
        cmb.addItem(_tr("（请选择图层）"), "")
        cur = 0
        for lyr in self._project_layers():
            try:
                if not lyr.is_vector():
                    continue
                name = str(lyr.name() or "")
            except Exception:
                _log.exception("silent exception in _param_input")
                continue
            cmb.addItem(name, str(_lid(lyr)))
            if str(_lid(lyr)) == str(node.layer_id):
                cur = cmb.count() - 1
        cmb.setCurrentIndex(cur)
        cmb.setToolTip(_tr("这个节点读取工程里的哪一份矢量图层"))

        def _on(idx, n=node, c=cmb):
            n.layer_id = str(c.currentData() or "")
            n.layer_name = str(c.currentText() or "")
            ok = self._find_layer(n.layer_id) is not None
            self._hint("" if ok else _tr("这个图层已不在工程中，请重新选择"))
            if self._items.get(n.nid) is not None:
                self._items[n.nid].update()
            self._mark_dirty()

        cmb.currentIndexChanged.connect(_on)
        form.addRow(_tr("图层"), cmb)
        self._param_lay.addLayout(form)

    def _param_output(self, node):
        self._sect(_tr("输出"))
        form = self._form()
        ed = GgsModelLine(str(node.output_name or ""))
        ed.setPlaceholderText(_tr("结果图层名"))
        ed.setToolTip(_tr("跑完之后结果图层用什么名字"))
        ed.textChanged.connect(lambda t, n=node: self._set_output_name(n, t))
        form.addRow(_tr("结果图层名"), ed)

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        pe = GgsModelLine(str(node.output_path or ""))
        pe.setPlaceholderText(_tr("留空 = 只放工程里，不写文件"))
        pe.textChanged.connect(lambda t, n=node: self._set_out_path(n, t))
        h.addWidget(pe, 1)
        btn = GgsModelTool("…")
        btn.setMaximumWidth(28)
        btn.setToolTip(_tr("选择要写出的文件"))
        btn.clicked.connect(lambda _c=False, e=pe: self._pick_out_file(e))
        h.addWidget(btn)
        form.addRow(_tr("输出文件"), row)
        self._add_check(form, node, "add_to_map", _tr("添加到地图"))
        self._param_lay.addLayout(form)

    def _param_op(self, node):
        spec = OPS.get(node.op, {})
        form = self._form()

        if spec.get("needs_distance"):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            sp = GgsModelSpin()
            sp.setRange(-1e9, 1e9)
            sp.setDecimals(3)
            sp.setValue(_num(node.params.get("distance"), 0.0))
            sp.setToolTip(_tr("负数为收缩（腐蚀）"))
            sp.valueChanged.connect(
                lambda v, n=node: self._set_param(n, "distance", float(v)))
            h.addWidget(sp, 2)
            cmb = GgsModelCmb()
            for code, label in (("map", _tr("地图单位")),
                                ("meters", _tr("米（按椭球换算）"))):
                cmb.addItem(label, code)
            _sel_data(cmb, node.params.get("distance_unit"), "map")
            cmb.currentIndexChanged.connect(
                lambda _i, n=node, c=cmb:
                self._set_param(n, "distance_unit", str(c.currentData())))
            h.addWidget(cmb, 1)
            form.addRow(_tr("缓冲距离"), row)

            seg = GgsModelSpin()
            seg.setRange(1, 200)
            seg.setValue(int(_num(node.params.get("segments"), 8)))
            seg.valueChanged.connect(
                lambda v, n=node: self._set_param(n, "segments", int(v)))
            form.addRow(_tr("圆弧分段（每 1/4 圆）"), seg)

            for key, styles, label in (("cap_style", CAP_STYLES, _tr("线端头")),
                                       ("join_style", JOIN_STYLES, _tr("拐角"))):
                c2 = GgsModelCmb()
                for code, lab in styles:
                    c2.addItem(_tr(lab), code)
                _sel_data(c2, node.params.get(key), styles[0][0])
                c2.currentIndexChanged.connect(
                    lambda _i, n=node, c=c2, k=key:
                    self._set_param(n, k, str(c.currentData())))
                form.addRow(label, c2)

        if node.op == OP_BUFFER:
            self._add_check(form, node, "dissolve",
                            _tr("合并为一个要素（融合）"))
        if spec.get("by_field"):
            self._param_field(form, node)
        if node.op == OP_CENTROID:
            self._add_check(form, node, "centroid_inside",
                            _tr("质心落在面内（内部点）"))
        if spec.get("needs_tolerance"):
            sp = GgsModelSpin()
            sp.setRange(0.0, 1e9)
            sp.setDecimals(3)
            sp.setValue(_num(node.params.get("tolerance"), 0.0))
            sp.valueChanged.connect(
                lambda v, n=node: self._set_param(n, "tolerance", float(v)))
            lab = (_tr("简化容差（地图单位）") if node.op == OP_SIMPLIFY
                   else _tr("最大间距（地图单位）"))
            form.addRow(lab, sp)
        if spec.get("needs_decimals"):
            sp = GgsModelSpin()
            sp.setRange(0, 12)
            sp.setValue(int(_num(node.params.get("decimals"), 6)))
            sp.valueChanged.connect(
                lambda v, n=node: self._set_param(n, "decimals", int(v)))
            form.addRow(_tr("小数位"), sp)

        for d in (spec.get("params") or []):
            self._param_extra_row(form, node, d)

        self._sect(_tr("参数"))
        if form.rowCount():
            self._param_lay.addLayout(form)
        else:
            self._param_lay.addWidget(self._dim(_tr("这个算法没有可调参数")))

    def _param_field(self, form, node):
        is_dis = (node.op == OP_DISSOLVE)
        cmb = GgsModelCmb()
        cmb.addItem(_tr("（不分组，全部融合）") if is_dis
                    else _tr("（按几何去重）"), "")
        for name in self._upstream_fields(node):
            cmb.addItem(str(name), str(name))
        _sel_data(cmb, node.params.get("by_field"), "")
        cmb.currentIndexChanged.connect(
            lambda _i, n=node, c=cmb:
            self._set_param(n, "by_field", str(c.currentData() or "")))
        if is_dis:
            cmb.setToolTip(_tr("留空 = 全部融成一个要素"))
            form.addRow(_tr("分组字段"), cmb)
        else:
            cmb.setToolTip("")
            form.addRow(_tr("去重字段"), cmb)

    def _overlay_hint(self, node):
        srcs = self._model.inputs_of(node.nid)
        if len(srcs) < 2:
            return ""
        src = self._model.node(srcs[1])
        if src is None:
            return _tr("（未连接）")
        if src.kind == MB.NODE_INPUT:
            lyr = self._find_layer(src.layer_id)
            if lyr is not None:
                try:
                    return str(lyr.name() or "")
                except Exception:
                    _log.exception("silent exception in _overlay_hint")
            return str(src.layer_name or _tr("（图层已不在工程中）"))
        return src.label()

    def _add_check(self, form, node, key, label):
        chk = GgsModelChk(label)
        if key == "add_to_map":
            chk.setChecked(bool(node.add_to_map))
        else:
            chk.setChecked(bool(node.params.get(key)))

        def _on(v, n=node, k=key):
            if k == "add_to_map":
                self._push_undo("addproj:%s" % n.nid)
                n.add_to_map = bool(v)
                self._mark_dirty()
            else:
                self._set_param(n, k, bool(v))

        chk.toggled.connect(_on)
        form.addRow(chk)

    def _upstream_fields(self, node):
        out = []
        for s in self._model.inputs_of(node.nid):
            src = self._model.node(s)
            if src is None:
                continue
            if src.kind == MB.NODE_OP:
                out.extend(self._upstream_fields(src))
            elif src.kind == MB.NODE_INPUT:
                lyr = self._find_layer(src.layer_id)
                try:
                    out.extend([str(x) for x in (lyr.fields() or [])])
                except Exception:
                    _log.exception("silent exception in _upstream_fields")
            if out:
                break
        seen = []
        for n in out:
            if n not in seen:
                seen.append(n)
        return seen

    def _set_title(self, node, text):
        self._push_undo("title:%s" % node.nid)
        node.title = str(text or "")
        it = self._items.get(node.nid)
        if it is not None:
            it.setToolTip(it._tip_of())
            it.update()
        self._mark_dirty()

    def _set_output_name(self, node, text):
        self._push_undo("outname:%s" % node.nid)
        node.output_name = str(text or "")
        it = self._items.get(node.nid)
        if it is not None:
            it.update()
        self._mark_dirty()

    def _set_out_path(self, node, text):
        self._push_undo("outpath:%s" % node.nid)
        node.output_path = str(text or "")
        self._mark_dirty()

    def _set_param(self, node, key, value):
        self._push_undo("param:%s:%s" % (node.nid, key))
        node.params[key] = value
        self._mark_dirty()

    def _set_extra_param(self, node, key, value):
        ex = dict(node.params.get("extra") or {})
        ex[str(key)] = value
        self._set_param(node, "extra", ex)

    def _param_extra_row(self, form, node, d):
        key = str(d.get("key") or "")
        if not key:
            return
        typ = str(d.get("type") or "number")
        label = _tr(str(d.get("label") or key))
        cur = (node.params.get("extra") or {}).get(key, d.get("default"))
        if typ == "text":
            ed = GgsModelLine("" if cur is None else str(cur))
            ed.textChanged.connect(
                lambda t, n=node, k=key: self._set_extra_param(n, k, str(t)))
            form.addRow(label, ed)
            return
        if typ == "choice":
            cmb = GgsModelCmb()
            for val, name in (d.get("choices") or []):
                cmb.addItem(_tr(str(name)), str(val))
            _sel_data(cmb, cur, str(d.get("default")))
            cmb.currentIndexChanged.connect(
                lambda _i, n=node, c=cmb, k=key:
                self._set_extra_param(n, k, str(c.currentData())))
            form.addRow(label, cmb)
            return
        if typ == "checklist":
            box = QWidget()
            g = QGridLayout(box)
            g.setContentsMargins(0, 0, 0, 0)
            g.setHorizontalSpacing(12)
            g.setVerticalSpacing(2)
            checked = {s.strip() for s in str(cur or "").split(",")
                       if s.strip()}
            boxes = []
            for k_i, opt in enumerate(d.get("options") or []):
                val = str(opt[0])
                cb = QCheckBox(_tr(str(opt[1])))
                cb.setChecked(val in checked)
                cb.toggled.connect(
                    lambda _c, n=node, k=key, b=boxes:
                    self._set_extra_param(
                        n, k, ",".join(v for v, c2 in b if c2.isChecked())))
                g.addWidget(cb, k_i // 2, k_i % 2)
                boxes.append((val, cb))
            form.addRow(label, box)
            return
        sp = GgsModelSpin()
        mn, mx = d.get("min"), d.get("max")
        sp.setRange(float(mn) if mn is not None else -1e9,
                    float(mx) if mx is not None else 1e9)
        sp.setDecimals(0 if typ == "int" else 6)
        try:
            sp.setValue(float(cur if cur is not None
                              else d.get("default")))
        except (TypeError, ValueError):
            exc_note("_param_extra_row @ ggis/ui/panels/model_builder.py:3126")
            sp.setValue(0.0)
        sp.valueChanged.connect(
            lambda v, n=node, k=key, t=typ:
            self._set_extra_param(n, k, int(v) if t == "int" else float(v)))
        form.addRow(label, sp)

    def _pick_out_file(self, edit):
        try:
            path, _f = QFileDialog.getSaveFileName(
                self, _tr("选择输出文件"), "",
                "GeoPackage (*.gpkg);;Shapefile (*.shp);;GeoJSON (*.geojson)")
        except Exception:
            _log.exception("silent exception in _pick_out_file")
            return
        if path:
            edit.setText(path)

    def load_from_project(self):
        self._loading = True
        try:
            raw = None
            try:
                raw = self._project().model_graph(self.model_id)
            except Exception:
                _log.exception("silent exception in load_from_project")
                raw = None
            self._model = MB.Model.from_dict(raw or {})
            self._sel = ""
            self._rebuild()
        finally:
            self._loading = False

    def save_to_project(self):
        try:
            self._project().set_model_graph(self.model_id, self._model.to_dict())
        except Exception:
            _log.exception("silent exception in save_to_project")

    def _mark_dirty(self):
        if self._loading:
            return
        self.save_to_project()
        try:
            self._project().set_dirty(True)
        except Exception:
            _log.exception("silent exception in _mark_dirty")

    def status_texts(self):
        stage = ""
        try:
            stage = str(self.lbl_stage.text() or "")
        except Exception:
            _log.exception("silent exception in status_texts")
            stage = ""
        val, vis = 0, False
        try:
            val = int(self.bar.value())
            vis = bool(self.bar.isVisible())
        except Exception:
            _log.exception("silent exception in status_texts")
            val, vis = 0, False
        return (stage, val, vis)

    def cancel_run(self):
        self._cancelled = True
        self.lbl_stage.setText(_tr("正在取消…"))

    def run_model(self):
        ids = self._layer_ids()
        probs = self._model.problems(ids)
        if probs:
            self._warn(_tr("模型还不能运行"), probs)
            return
        warns = self._model.warnings(ids)
        if warns:
            if not self.ctx.region("dock")._confirm(_tr("有需要确认的地方"),
                                 warns + [("确认后开始运行", ())]):
                return
        self._ctx = {}
        for n in self._model.nodes.values():
            if n.kind == MB.NODE_INPUT:
                lyr = self._find_layer(n.layer_id)
                if lyr is not None:
                    self._ctx[n.nid] = lyr
        try:
            self._queue = self._model.topo_order()
        except Exception as e:
            _log.exception("silent exception in run_model")
            self._warn(_tr("模型还不能运行"), [(str(e), ())])
            return
        self._run_i = 0
        self._cancelled = False
        self._run_states = {}
        self._run_log = []
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self._step()

    def _step(self):
        if self._cancelled:
            self._finish(_tr("已取消"))
            return
        while self._run_i < len(self._queue):
            node = self._model.node(self._queue[self._run_i])
            self._run_i += 1
            if node is None:
                continue
            if node.kind == MB.NODE_OUTPUT:
                continue
            if node.kind == MB.NODE_OP and not getattr(node, "enabled", True):
                srcs = self._model.inputs_of(node.nid)
                self._ctx[node.nid] = (self._ctx.get(srcs[0])
                                       if srcs else None)
                self._set_run_state(node.nid, "skip")
                self._run_log.append(
                    "%s：%s" % (node.label(), _tr("已跳过（节点被禁用）")))
                continue
            self._run_one(node)
            return
        self._finish(_tr("完成"))

    def _set_run_state(self, nid, st):
        self._run_states[str(nid)] = str(st or "")
        it = self._items.get(str(nid))
        if it is not None:
            it.update()

    def _deliver_of(self, nid):
        for d in self._model.outputs_of(nid):
            n = self._model.node(d)
            if n is not None and n.kind == MB.NODE_OUTPUT:
                return n
        return None

    def _run_one(self, node):
        from ...core.analysis import AnalysisParams
        srcs = self._model.inputs_of(node.nid)
        main_l = self._ctx.get(srcs[0]) if srcs else None
        over_l = self._ctx.get(srcs[1]) if len(srcs) > 1 else None
        if main_l is None:
            self._finish(_tr("「{0}」拿不到输入图层").format(node.label()))
            return
        spec = OPS.get(node.op, {})
        p = AnalysisParams(
            op=node.op,
            input_layer=main_l,
            overlay_layer=(over_l if spec.get("needs_overlay") else None),
            distance=_num(node.params.get("distance"), 0.0),
            segments=int(_num(node.params.get("segments"), 8)),
            cap_style=str(node.params.get("cap_style") or "round"),
            join_style=str(node.params.get("join_style") or "round"),
            dissolve=bool(node.params.get("dissolve")
                          and spec.get("dissolvable")),
            by_field=(str(node.params.get("by_field") or "")
                      if spec.get("by_field") else ""),
            distance_unit=str(node.params.get("distance_unit") or "map"),
            centroid_inside=bool(node.params.get("centroid_inside")),
            tolerance=_num(node.params.get("tolerance"), 0.0),
            decimals=int(_num(node.params.get("decimals"), 6)),
            extra=dict(node.params.get("extra") or {}))

        out = self._deliver_of(node.nid)
        to_file = False
        path = ""
        add = False
        if out is not None:
            add = bool(out.add_to_map)
            path = str(out.output_path or "")
            if path:
                to_file = True
                p.output_path = path
                p.output_driver = self._driver_for(path)
            if add or path:
                p.output_name = str(out.output_name or "")
        self._editing = node
        self._set_run_state(node.nid, "run")
        self.lbl_stage.setText(_tr("正在运行「{0}」…").format(node.label()))
        self._run_log.append("%s：%s" % (node.label(), _tr("运行中")))
        try:
            self._win.run_analysis(
                p, to_file=to_file, path=path, add_to_map=add,
                progress=self._feed, cancel=self._is_cancelled,
                on_done=self._on_node_done)
        except Exception as e:
            _log.exception("silent exception in _run_one")
            self._set_run_state(node.nid, "fail")
            self._finish(_tr("「{0}」失败：{1}").format(node.label(), e))
            return

    def _driver_for(self, path):
        try:
            from ..dialogs.analysis import GgsAnalysisDialog
            return str(GgsAnalysisDialog._driver_for(path) or "")
        except Exception:
            _log.exception("silent exception in _driver_for")
            return ""

    def _on_node_done(self, lyr):
        node = self._editing
        self._editing = None
        if node is None:
            return
        if lyr is None:
            self._set_run_state(node.nid, "fail")
            self._finish(_tr("「{0}」没有产出结果").format(node.label()))
            return
        self._ctx[node.nid] = lyr
        self._set_run_state(node.nid, "ok")
        try:
            nm = str(lyr.name() or "")
        except Exception:
            _log.exception("silent exception in _on_node_done")
            nm = ""
        if self._run_log:
            self._run_log[-1] = "%s：%s%s" % (
                node.label(), _tr("完成"), ("（%s）" % nm) if nm else "")
        else:
            self._run_log.append("%s：%s" % (node.label(), _tr("完成")))
        total = max(1, len(self._queue))
        self.bar.setValue(int((self._run_i / float(total)) * 100))
        self._step()

    def _feed(self, frac, text=""):
        try:
            self.bar.setValue(int(max(0.0, min(1.0, float(frac))) * 100))
        except Exception:
            _log.exception("silent exception in _feed")
        if text:
            self.lbl_stage.setText(_tr(str(text)))

    def _is_cancelled(self):
        return bool(self._cancelled)

    def _finish(self, text):
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
        self.bar.setVisible(False)
        self._queue = []
        self._ctx = {}
        self._run_i = 0
        self._editing = None
        for nid, st in list(self._run_states.items()):
            if st == "run":
                self._set_run_state(nid, "fail")
        self.lbl_stage.setText(str(text or ""))
        try:
            self._win.canvas.refresh()
        except Exception:
            _log.exception("silent exception in _finish")
        try:
            self.reload_layers()
        except Exception:
            _log.exception("silent exception in _finish")
        self._show_run_summary(text)

    def _show_run_summary(self, text):
        if not self._run_log:
            return
        lines = list(self._run_log)[:12]
        if len(self._run_log) > len(lines):
            lines.append("…")
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.information(self, str(text or _tr("运行结束")),
                                  "\n".join(lines))
        except Exception:
            _log.exception("silent exception in _show_run_summary")
            self.lbl_stage.setText(str(text or ""))

    def _warn(self, title, items):
        text = self._fmt(items)
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.warning(self, title, text)
        except Exception:
            _log.exception("silent exception in _warn")
            self.lbl_stage.setText(text.replace("\n", "  "))

    def _confirm(self, title, items):
        text = self._fmt(items)
        try:
            from ggis.common.base.dialog import GgsMsgBox
            btns = (QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No)
            ret = GgsMsgBox.question(self, title, "", buttons=btns,
                                     default=QMessageBox.StandardButton.Yes)
            return ret == QMessageBox.StandardButton.Yes
        except Exception:
            _log.exception("silent exception in _confirm")
            return True

    @staticmethod
    def _fmt(items):
        lines = []
        for k, a in items:
            try:
                lines.append("· " + _tr(k).format(*a))
            except Exception:
                _log.exception("silent exception in _fmt")
                lines.append("· " + str(k))
        return "\n".join(lines)

    def showEvent(self, e):
        super().showEvent(e)
        try:
            self.activated.emit()
        except Exception:
            _log.exception("silent exception in showEvent")
        try:
            self.reload_layers()
        except Exception:
            _log.exception("silent exception in showEvent")
        try:
            QTimer.singleShot(0, self._auto_fit_once)
        except Exception:
            _log.exception("silent exception in showEvent")


def _lid(lyr):
    try:
        return str(lyr.id())
    except Exception:
        _log.exception("silent exception in _lid")
        return ""


def _num(v, fallback):
    try:
        return float(v)
    except Exception:
        _log.exception("silent exception in _num")
        return float(fallback)


def _sel_data(cmb, value, fallback):
    want = str(value if value not in (None, "") else fallback)
    for i in range(cmb.count()):
        if str(cmb.itemData(i)) == want:
            cmb.setCurrentIndex(i)
            return
    cmb.setCurrentIndex(0)


class GgsModelBuilderWindow(GgsDialog):

    activated = Signal()

    def __init__(self, title=None, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsModelBuilderWindowShell")
        if title:
            self.setWindowTitle(str(title))
        self.workspace = GgsModelBuilderWorkspace(
            title, self, embedded=False, window=parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(0)
        lay.addWidget(self.workspace, 1)
        try:
            self.workspace.activated.connect(self.activated)
        except Exception:
            _log.exception("silent exception in __init__")

    def __getattr__(self, name):
        ws = self.__dict__.get("workspace")
        if ws is not None:
            try:
                return getattr(ws, name)
            except AttributeError:
                exc_note("__getattr__ @ ggis/ui/panels/model_builder.py:3560")
                pass
        raise AttributeError(name)


__all__ = ["GgsModelBuilderWindow", "GgsModelBuilderWorkspace"]


class GgsModelBar(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelBar")
class GgsModelBtn(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelBtn")
class GgsModelCap(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelCap")
class GgsModelChk(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelChk")
class GgsModelCmb(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelCmb")
class GgsModelEmpty(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelEmpty")
class GgsModelLayersPanel(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelLayersPanel")
class GgsModelLine(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelLine")
class GgsModelOpsPanel(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelOpsPanel")
class GgsModelParam(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelParam")
class GgsModelParamArea(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelParamArea")
class GgsModelSect(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelSect")
class GgsModelSpin(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelSpin")
class GgsModelStatusRow(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelStatusRow")
class GgsModelSub(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelSub")
class GgsModelTool(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsModelTool")
