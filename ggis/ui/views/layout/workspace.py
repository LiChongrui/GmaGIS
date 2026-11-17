# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging

from PySide6.QtCore import (QMarginsF, QPoint, QRectF, QSize, QSizeF, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QAction, QBrush, QColor, QPageLayout, QPageSize
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox,
                               QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QFrame, QGridLayout,
                               QGroupBox,                                QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem,                                QMainWindow,
                               QScrollArea, QSizePolicy, QSpinBox,
                               QStackedWidget, QTextEdit, QTreeWidgetItem,
                               QVBoxLayout, QWidget,
                               QMenu)

from ggis.core.app import i18n
from ggis.ui.views.layout import exporter as EX
from ggis.core.model import layout_items as LI
from ggis.common.styling import icons as _icons
from ggis.core.model.layout_model import (DEFAULT_PAGE, DEFAULT_UNIT,
                           ORIENTATION_LANDSCAPE, ORIENTATION_PORTRAIT,
                           PAGE_SIZES, Layout, LayoutError)
from ggis.ui.views.layout.canvas import LayoutView
from ggis.ui.views.layout.page_units import fmt_len
from ggis.common.base.dialog import GgsDialog, GgsFileDialog, GgsMsgBox
from ggis.common.widgets.inputs import GgsColorField, GgsComboBox, ggs_combo_value, ggs_font_combo, ggs_font_select
from ggis.common.widgets.buttons import GgsSmallButtonStyle1, GgsStandardButton
from ggis.common.widgets.itemviews import GgsTreeWidget
try:
    import shiboken6
except Exception:
    exc_note("<module> @ ggis/ui/views/layout/workspace.py:shiboken6")
    shiboken6 = None


def _alive(qobj):
    if qobj is None:
        return False
    if shiboken6 is None:
        return True
    return shiboken6.isValid(qobj)
from ggis.ui.framework.docks import GgsDockBody
from ggis.ui.panels.layertree import GgsDockToolbar
from ggis.common.widgets.separators import GgsSepH
from PySide6.QtWidgets import QPushButton

_tr = i18n.tr

_log = logging.getLogger("gmagis")

PAGE_ORDER = ["A0", "A1", "A2", "A3", "A4", "A5", "Letter", "Legal",
              "B5", "B4", "B3"]

DPI_CHOICES = [("72 dpi（屏幕）", 72), ("150 dpi（草稿）", 150),
               ("300 dpi（印刷）", 300), ("600 dpi（高清）", 600),
               ("1200 dpi（超清）", 1200)]

LAYOUT_RIBBON_TAG = "layout:__shared__"

ADD_BUTTONS = [
    ("map_frame", "地图框", "layout_map"),
    ("legend", "图例", "layout_legend"),
    ("scale_bar", "比例尺", "layout_scale"),
    ("north_arrow", "指北针", "layout_north"),
    ("grid", "格网", "layout_grid"),
    ("text", "文字", "layout_text"),
    ("image", "图片", "layout_image"),
]

INSERT_GROUPS = (
    ("插入", ("map_frame", "grid", "legend", "scale_bar", "north_arrow",
              "text", "image")),
)

LINK_SEL = "sel"
LINK_SEL2 = "sel2"
LINK_CLIP = "clip"
LINK_ITEMS = "items"
LINK_MAP = "map"
LINK_PREV = "prev"
LINK_NEXT = "next"
LINK_GUIDES = "guides"
LINK_FRAME = "frame"
LINK_MAPVIEW = "mapview"

FRAME_BOUND_ITEMS = ("grid", "legend", "scale_bar", "north_arrow")

ELEMENT_ICONS = {t: ic for t, _label, ic in ADD_BUTTONS}

ROLE_ELEM_ID = int(Qt.ItemDataRole.UserRole) + 1
ROLE_ICON_NAME = int(Qt.ItemDataRole.UserRole) + 2


def _elem_set_drop(item, enabled):
    try:
        f = item.flags()
        if enabled:
            f |= Qt.ItemFlag.ItemIsDropEnabled
        else:
            f &= ~Qt.ItemFlag.ItemIsDropEnabled
        item.setFlags(f)
    except Exception:
        exc_note("_elem_set_drop @ ggis/ui/views/layout/workspace.py:152")
        pass


class _LayoutItemsTree(GgsTreeWidget):

    rowsReordered = Signal()

    def dropEvent(self, e):
        accepted = False
        try:
            super().dropEvent(e)
            accepted = bool(e.isAccepted())
        except Exception:
            exc_note("dropEvent @ ggis/ui/views/layout/workspace.py:175")
            pass
        if accepted:
            try:
                self.rowsReordered.emit()
            except Exception:
                exc_note("dropEvent @ ggis/ui/views/layout/workspace.py:180")
                pass


class GgsLayoutWorkspace(QWidget):

    exported = Signal(object)
    closeRequested = Signal()
    layoutDuplicated = Signal(object)

    def __init__(self, project, layout=None, parent=None, dark_bg=True,
                 map_extent=None, map_crs=None, default_dpi=300,
                 embedded=False, ribbon=None, window=None, view_id=None):
        super().__init__(parent)
        self.ctx = getattr(window, "ctx", None) or getattr(parent, "ctx", None)
        self._embedded = bool(embedded)
        self._ribbon_host = ribbon
        self._win = window
        self._tab_tag = LAYOUT_RIBBON_TAG
        self._view_id = view_id
        self._project = project
        self._dark = bool(dark_bg)
        self._map_extent = map_extent
        self._map_crs = map_crs
        self._clip = []
        self._syncing = False
        self.lay = layout
        if self.lay is None:
            # 不允许无布局构造（旧 _new_layout 自动创建兜底已废除——
            # 那是往工程里塞空布局的根源）。
            raise ValueError(_tr("布局视图必须指定布局对象"))
        if self.lay not in (project.layouts() if project else []):
            try:
                project.add_layout(self.lay)
            except Exception:
                exc_note("__init__ @ ggis/ui/views/layout/workspace.py:261")
                pass
        self.setObjectName("GgsLayoutDialog")
        if not self._embedded:
            self.setWindowTitle(_tr("打印布局设计器") + " — " + self.lay.name)
            self.resize(1180, 760)
            self.setMinimumSize(900, 600)
        self._build()
        self._reload_all()
        self._select_index(0)

    def reject(self):
        w = None
        try:
            w = self.window()
        except Exception:
            exc_note("reject @ ggis/ui/views/layout/workspace.py:307")
            w = None
        if w is not None and w is not self and isinstance(w, QDialog):
            try:
                w.reject()
                return
            except Exception:
                exc_note("reject @ ggis/ui/views/layout/workspace.py:315")
                pass
        try:
            self.closeRequested.emit()
        except Exception:
            exc_note("reject @ ggis/ui/views/layout/workspace.py:319")
            pass

    def _build(self):
        outer = QVBoxLayout(self)
        if self._embedded:
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(0)
        else:
            outer.setContentsMargins(10, 8, 10, 10)
            outer.setSpacing(8)

        center = self._center_panel()
        if self._embedded:
            win = self._win
            if win is None or not getattr(win, "_shared_layout_delegate", None):
                self._ribbon_bar(self._ribbon_host, tag=self._tab_tag)
                if win is not None:
                    win._shared_layout_delegate = self
                self._add_dock_view_group()
            else:
                self._adopt_shared_controls(win._shared_layout_delegate)
        else:
            outer.addWidget(self._ribbon_bar())
            self._add_dock_view_group()

        panel_left = self._left_panel()
        panel_right = self._right_panel()
        self._panel_left = panel_left
        self._panel_right = panel_right
        self._shell = None
        if self.attach_to_main_docks():
            outer.addWidget(center, 1)
        else:
            self._shell = QMainWindow()
            self._shell.setObjectName("GgsLayoutShell")
            self._shell.setCentralWidget(center)
            self.dock_items = self._make_dock(
                "GgsLayoutItemsDock", _tr("元素清单"), panel_left,
                Qt.DockWidgetArea.LeftDockWidgetArea)
            self.dock_props = self._make_dock(
                "GgsLayoutPropsDock", _tr("元素设置"), panel_right,
                Qt.DockWidgetArea.RightDockWidgetArea)
            outer.addWidget(self._shell, 1)


        QTimer.singleShot(0, self.ctx.region("dock")._apply_dock_widths)

        self._install_bottom_bar(outer)
        self._pump()

    @staticmethod
    def _pump():
        try:
            from ggis.ui.dialogs.busy import pump as _pump
            _pump()
        except Exception:
            exc_note("_pump @ ggis/ui/views/layout/workspace.py:451")
            pass

    def _apply_dock_widths(self):
        try:
            from ggis.main_window import DOCK_W
        except Exception:
            exc_note("_apply_dock_widths @ ggis/ui/views/layout/workspace.py:472")
            DOCK_W = 300
        docks = [d for d in (getattr(self, "dock_items", None),
                             getattr(self, "dock_props", None)) if d is not None]
        if not docks:
            return
        if getattr(self, "_shell", None) is None:
            return
        try:
            min_w = int(docks[0].minimumSizeHint().width() or 0)
        except Exception:
            exc_note("_apply_dock_widths @ ggis/ui/views/layout/workspace.py:487")
            min_w = 0
        for d in docks:
            try:
                d.setMinimumWidth(int(min_w))
                d.setMaximumWidth(16777215)
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/views/layout/workspace.py:494")
                pass
            try:
                if int(d.width()) != int(DOCK_W):
                    d.resize(int(DOCK_W), int(d.height()))
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/views/layout/workspace.py:500")
                pass
        try:
            self._shell.resizeDocks(docks, [int(DOCK_W)] * len(docks),
                                    Qt.Orientation.Horizontal)
        except Exception:
            exc_note("_apply_dock_widths @ ggis/ui/views/layout/workspace.py:505")
            pass

    def _add_dock_view_group(self):
        pg = getattr(self, "_pg_start", None)
        if pg is None:
            return
        from ggis.ui.framework.ribbon import BIG_ICON, RibbonGroup
        win = getattr(self, "_win", None)
        shared = bool(getattr(self, "_embedded", False)) and win is not None \
            and getattr(win, "_shared_layout_delegate", None) is self
        try:
            g = RibbonGroup(_tr("视图"))
            if shared:
                self.act_dock_items = QAction(
                    _icons.icon("layer", size=BIG_ICON), _tr("元素清单"), self)
                self.act_dock_items.setCheckable(True)
                self.act_dock_items.setToolTip(_tr("显示 / 隐藏") + _tr("元素清单"))
                self._keep_action(self.act_dock_items)
                self.act_dock_items.toggled.connect(
                    self._on_dock_items_toggled)
                g.add_action(self.act_dock_items, big=True,
                             variant="GgsBigCheckButtonStyle1")
                self.act_dock_props = QAction(
                    _icons.icon("settings", size=BIG_ICON), _tr("元素设置"), self)
                self.act_dock_props.setCheckable(True)
                self.act_dock_props.setToolTip(_tr("显示 / 隐藏") + _tr("元素设置"))
                self._keep_action(self.act_dock_props)
                self.act_dock_props.toggled.connect(
                    self._on_dock_props_toggled)
                g.add_action(self.act_dock_props, big=True,
                             variant="GgsBigCheckButtonStyle1")
                self._sync_dock_toggle_states()
            else:
                for dock, label, icon_name in (
                        (getattr(self, "dock_items", None), "元素清单", "layer"),
                        (getattr(self, "dock_props", None), "元素设置", "settings")):
                    if dock is None:
                        continue
                    a = dock.toggleViewAction()
                    a.setText(_tr(label))
                    a.setToolTip(_tr("显示 / 隐藏") + _tr(label))
                    try:
                        a.setIcon(_icons.icon(icon_name, size=BIG_ICON))
                    except Exception:
                        exc_note("_add_dock_view_group @ ggis/ui/views/layout/workspace.py:572")
                        pass
                    self._keep_action(a)
                    g.add_action(a, big=True, variant="GgsBigCheckButtonStyle1")
            pg.add_group(g)
        except Exception:
            _log.exception("布局：往「开始」页添加「视图」组失败")

    def _make_dock(self, obj_name, title, widget, area):
        from ggis.ui.framework.docks import GgsDockWidget
        d = GgsDockWidget(_tr(title), self._shell)
        d.setObjectName(obj_name)
        d.setWidget(widget)
        d.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self._shell.addDockWidget(area, d)
        return d

    _SHARED_ATTRS = (
        "rb", "_pg_start", "_ribbon_indexes",
        "cmb_page", "cmb_orient", "cmb_dpi", "spn_margins",
        "act_dup", "act_size", "m_size", "act_orient", "m_orient",
        "act_paste", "m_paste", "act_pan", "act_select", "m_select",
        "chk_ruler", "chk_guides", "chk_margin",
        "act_guide_h", "act_guide_v", "act_guide_clear",
        "act_activate",
        "act_mapframe", "m_mapframe", "act_mapframe_btn",
        "_ins_actions",
        "act_dock_items", "act_dock_props",
    )

    def _adopt_shared_controls(self, delegate):
        if delegate is None or delegate is self:
            return
        for k in self._SHARED_ATTRS:
            v = getattr(delegate, k, None)
            if v is not None:
                setattr(self, k, v)
        try:
            self._delegate = delegate
        except Exception:
            exc_note("_adopt_shared_controls @ ggis/ui/views/layout/workspace.py:638")
            pass

    def _relink_to(self, ws):
        if ws is None:
            return
        self.lay = ws.lay
        self.view = ws.view
        self.lst = ws.lst
        self.dock_items = ws.dock_items
        self.dock_props = ws.dock_props
        self._project = ws._project
        self._map_extent = ws._map_extent
        self._map_crs = getattr(ws, "_map_crs", None)
        try:
            self._reload_all()
        except Exception:
            _log.exception("布局：切换布局重载共享功能区失败")
        try:
            self._sync_dock_toggle_states()
        except Exception:
            exc_note("_relink_to @ ggis/ui/views/layout/workspace.py:672")
            pass

    def _on_dock_items_toggled(self, on):
        d = getattr(self, "dock_items", None)
        if d is not None:
            try:
                d.setVisible(bool(on))
            except Exception:
                exc_note("_on_dock_items_toggled @ ggis/ui/views/layout/workspace.py:681")
                pass

    def _on_dock_props_toggled(self, on):
        d = getattr(self, "dock_props", None)
        if d is not None:
            try:
                d.setVisible(bool(on))
            except Exception:
                exc_note("_on_dock_props_toggled @ ggis/ui/views/layout/workspace.py:690")
                pass

    def _sync_dock_toggle_states(self):
        di = getattr(self, "act_dock_items", None)
        if di is not None:
            d = getattr(self, "dock_items", None)
            try:
                di.setChecked(bool(d is not None and d.isVisible()))
            except Exception:
                exc_note("_sync_dock_toggle_states @ ggis/ui/views/layout/workspace.py:705")
                pass
        dp = getattr(self, "act_dock_props", None)
        if dp is not None:
            d = getattr(self, "dock_props", None)
            try:
                dp.setChecked(bool(d is not None and d.isVisible()))
            except Exception:
                exc_note("_sync_dock_toggle_states @ ggis/ui/views/layout/workspace.py:712")
                pass

    def attach_to_main_docks(self):
        win = self._win
        if win is None or not self._embedded:
            return False
        vid = self._view_id
        if not vid:
            return False
        if win._view_docks.get(str(vid), []):
            return True
        left = getattr(self, "_panel_left", None)
        right = getattr(self, "_panel_right", None)
        if left is None or right is None:
            return False
        try:
            from ggis.ui.framework.docks import GgsDockWidget
        except Exception:
            exc_note("attach_to_main_docks @ ggis/ui/views/layout/workspace.py:751")
            return False
        d_items = GgsDockWidget(_tr("元素清单"), win)
        d_items.setObjectName("GgsLayoutItemsDock")
        d_props = GgsDockWidget(_tr("元素设置"), win)
        d_props.setObjectName("GgsLayoutPropsDock")
        try:
            d_items.setWidget(left)
            d_props.setWidget(right)
        except Exception:
            _log.exception("布局：元素面板装入主窗口 DOCK 失败")
            return False
        try:
            if getattr(self, "_shell", None) is None:
                try:
                    from ggis.main_window import DOCK_W
                except Exception:
                    exc_note("attach_to_main_docks @ ggis/ui/views/layout/workspace.py:769")
                    DOCK_W = 300
                for _d in (d_items, d_props):
                    try:
                        _d.setMinimumWidth(int(_d.minimumSizeHint().width() or 0))
                        _d.setMaximumWidth(16777215)
                        win.resizeDocks([_d], [int(DOCK_W)],
                                        Qt.Orientation.Horizontal)
                    except Exception:
                        exc_note("attach_to_main_docks @ ggis/ui/views/layout/workspace.py:777")
                        pass
            win.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, d_items)
            win.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d_props)
            d_items.setFloating(False)
            d_props.setFloating(False)
            d_items.hide()
            d_props.hide()
        except Exception:
            exc_note("attach_to_main_docks @ ggis/ui/views/layout/workspace.py:786")
            return False
        self.dock_items = d_items
        self.dock_props = d_props
        win.ctx.region("dock")._register_view_docks(vid, [d_items, d_props])
        return True

    def detach_from_main_docks(self):
        win = self._win
        if win is None or not self._view_id:
            return
        try:
            win._unregister_view_docks(self._view_id)
        except Exception:
            exc_note("detach_from_main_docks @ ggis/ui/views/layout/workspace.py:808")
            pass

    def _install_bottom_bar(self, outer):
        self.bottom = self._bottom_bar()
        if self._embedded:
            self.bottom.hide()
        else:
            outer.addWidget(self.bottom)

    def _tag_ribbon_tab(self, rb, tag):
        try:
            i = int(getattr(rb, "_main_count", 0)) - 1
        except Exception:
            exc_note("_tag_ribbon_tab @ ggis/ui/views/layout/workspace.py:851")
            i = -1
        if i < 0 or i >= rb.tabs.count():
            return None
        try:
            rb.tabs.setTabData(i, tag)
        except Exception:
            exc_note("_tag_ribbon_tab @ ggis/ui/views/layout/workspace.py:857")
            pass
        idx = getattr(self, "_ribbon_indexes", None)
        if idx is None:
            idx = self._ribbon_indexes = []
        idx.append(i)
        return i

    def _ribbon_bar(self, rb=None, tag=None):
        from ggis.ui.framework.ribbon import BIG_ICON, GgsRibbon, RibbonGroup

        mine = rb is None
        if rb is None:
            rb = GgsRibbon()
            rb.setObjectName("GgsLayoutRibbon")
        self.rb = rb
        if mine:
            try:
                rb.app_button.setVisible(bool(self._embedded))
            except Exception:
                exc_note("_ribbon_bar @ ggis/ui/views/layout/workspace.py:912")
                pass

        pg = rb.add_tab(_tr("开始"))
        self._tag_ribbon_tab(rb, getattr(self, "_tab_tag", None) or tag)
        self._pg_start = pg

        pg2 = rb.add_tab(_tr("页面"))
        self._tag_ribbon_tab(rb, getattr(self, "_tab_tag", None) or tag)


        self.cmb_page = QComboBox()
        for name in PAGE_ORDER:
            if name in PAGE_SIZES:
                self.cmb_page.addItem(self._page_label(name), name)
        self.cmb_page.currentIndexChanged.connect(self._on_page_changed)
        self.cmb_orient = QComboBox()
        self.cmb_orient.addItem(_tr("横向"), ORIENTATION_LANDSCAPE)
        self.cmb_orient.addItem(_tr("纵向"), ORIENTATION_PORTRAIT)
        self.cmb_orient.currentIndexChanged.connect(self._on_page_changed)
        self.cmb_dpi = QComboBox()
        for label, dpi in DPI_CHOICES:
            self.cmb_dpi.addItem(label, dpi)
        k = self.cmb_dpi.findData(int(self.lay.dpi or 300))
        self.cmb_dpi.setCurrentIndex(max(0, k))

        g = RibbonGroup(_tr("页面设置"))
        self.act_dup = QAction(_icons.icon("layout", size=BIG_ICON),
                               _tr("复制布局"), self)
        self.act_dup.setToolTip(_tr("复制布局"))
        self.act_dup.triggered.connect(
            lambda _c=False: self.duplicate_layout())
        self._keep_action(self.act_dup)
        g.add_action(self.act_dup, big=True, variant="GgsBigButtonStyle1")

        self.act_size = QAction(_icons.icon("page_setup", size=16),
                                _tr("大小"), self)
        self.act_size.setToolTip(_tr("纸张大小"))
        m_size = QMenu(self)
        for name in PAGE_ORDER:
            if name not in PAGE_SIZES:
                continue
            a = m_size.addAction(self._page_label(name))
            a.setCheckable(True)
            a.setData(str(name))
            a.triggered.connect(
                lambda _c=False, n=name: self._pick_page_size(n))
        self.m_size = m_size
        self._keep_action(self.act_size)
        col = g.small_column()
        g.add_dropdown(self.act_size, m_size, big=False, col=col,
                       tip=_tr("纸张大小"))

        self.act_orient = QAction(_icons.icon("page_orient", size=16),
                                  _tr("方向"), self)
        self.act_orient.setToolTip(_tr("纸张方向"))
        m_orient = QMenu(self)
        for label, code in ((_tr("横向"), ORIENTATION_LANDSCAPE),
                            (_tr("纵向"), ORIENTATION_PORTRAIT)):
            a = m_orient.addAction(label)
            a.setCheckable(True)
            a.setData(str(code))
            a.triggered.connect(
                lambda _c=False, v=code: self._pick_orient(v))
        self.m_orient = m_orient
        self._keep_action(self.act_orient)
        g.add_dropdown(self.act_orient, m_orient, big=False, col=col,
                       tip=_tr("纸张方向"))

        col2 = g.small_column()
        for label, icon_name, slot, tip in (
                (_tr("页面设置…"), "settings", self._open_page_setup,
                 _tr("纸张 / 方向 / 边距 / 分辨率")),):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(lambda _c=False, sl=slot: sl())
            self._keep_action(a)
            g.add_action(a, big=False, col=col2)
        pg2.add_group(g)

        self.spn_margins = []
        cells = QWidget(self)
        grid = QGridLayout(cells)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(3)
        for col, side in enumerate(("左", "上", "右", "下")):
            lb = GgsRibbonMini(_tr(side))
            lb.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(lb, 0, col)
            sp = QDoubleSpinBox()
            sp.setRange(0.0, 60.0)
            sp.setDecimals(1)
            sp.setSingleStep(1.0)
            sp.setSuffix(" mm")
            sp.setFixedWidth(70)
            sp.setFixedHeight(22)
            sp.valueChanged.connect(self._on_margins_changed)
            self.spn_margins.append(sp)
            grid.addWidget(sp, 1, col)

        g = RibbonGroup(_tr("排列"))
        for label, icon_name, slot, tip in (
                (_tr("上移一层"), "arrange_up",
                 lambda: self.move_item(1), _tr("提高绘制顺序")),
                (_tr("下移一层"), "arrange_down",
                 lambda: self.move_item(-1), _tr("降低绘制顺序")),
                (_tr("删除"), "delete", self.remove_current,
                 _tr("删除选中元素"))):
            a = QAction(_icons.icon(icon_name, size=BIG_ICON), label, self)
            a.setToolTip(tip)
            a.triggered.connect(lambda _c=False, sl=slot: sl())
            self._keep_action(a)
            self._link(a, LINK_SEL)
            g.add_action(a, big=True, variant="GgsBigButtonStyle1")
        col = g.small_column()
        for label, icon_name, top, tip in (
                (_tr("置于顶层"), "arrow_up", True, _tr("移到所有元素之上")),
                (_tr("置于底层"), "arrow_down", False, _tr("移到所有元素之下"))):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(lambda _c=False, t=top: self.move_item_to(t))
            self._keep_action(a)
            self._link(a, LINK_SEL)
            g.add_action(a, big=False, col=col)
        m_align = GgsLayoutAlignMenu(self)
        for label, code in ((_tr("左对齐"), "left"),
                            (_tr("水平居中"), "hcenter"),
                            (_tr("右对齐"), "right"),
                            (_tr("顶端对齐"), "top"),
                            (_tr("垂直居中"), "vcenter"),
                            (_tr("底端对齐"), "bottom")):
            a = m_align.addAction(label)
            a.setData(code)
            a.triggered.connect(
                lambda _c=False, e=code: self._align_item(e))
        act_align = QAction(_icons.icon("align", size=BIG_ICON),
                            _tr("对齐"), self)
        act_align.setToolTip(_tr("按页面对齐选中元素"))
        self._keep_action(act_align)
        self._link(act_align, LINK_SEL2)
        g.add_dropdown(act_align, m_align, tip=_tr("按页面对齐选中元素"))
        m_dist = GgsLayoutDistMenu(self)
        for label, code in ((_tr("横向分布"), "h"),
                            (_tr("纵向分布"), "v")):
            a = m_dist.addAction(label)
            a.setData(code)
            a.triggered.connect(
                lambda _c=False, k=code: self._distribute(k))
        act_dist = QAction(_icons.icon("distribute", size=BIG_ICON),
                           _tr("分布"), self)
        act_dist.setToolTip(_tr("等间距分布"))
        self._keep_action(act_dist)
        self._link(act_dist, LINK_SEL2)
        g.add_dropdown(act_dist, m_dist,
                       tip=_tr("等间距分布"))
        pg2.add_group(g)


        g = RibbonGroup(_tr("剪贴板"))
        self.act_paste = QAction(
            _icons.icon("paste_features", size=BIG_ICON), _tr("粘贴"), self)
        self.act_paste.setToolTip(_tr("把剪贴板里的元素粘贴到页面"))
        self.act_paste.triggered.connect(
            lambda _c=False: self.paste_items(False))
        self.m_paste = QMenu(self)
        a = self.m_paste.addAction(_tr("粘贴"))
        a.triggered.connect(lambda _c=False: self.paste_items(False))
        a = self.m_paste.addAction(_tr("粘贴到原位置"))
        a.triggered.connect(lambda _c=False: self.paste_items(True))
        self._keep_action(self.act_paste)
        self._link(self.act_paste, LINK_CLIP)
        g.add_dropdown(self.act_paste, self.m_paste, tip=_tr("粘贴"))
        col = g.small_column()
        for label, icon_name, slot, tip in (
                (_tr("剪切"), "cut_features", self.cut_selected,
                 _tr("剪切选中的元素")),
                (_tr("复制"), "copy_features", self.copy_selected,
                 _tr("复制选中的元素"))):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(lambda _c=False, sl=slot: sl())
            self._keep_action(a)
            self._link(a, LINK_SEL)
            g.add_action(a, big=False, col=col)
        pg.add_group(g)

        self._add_insert_groups(pg)

        g = RibbonGroup(_tr("导航"))
        self.act_pan = QAction(_icons.icon("pan", size=BIG_ICON),
                               _tr("导航"), self)
        self.act_pan.setToolTip(_tr("导航：拖动页面平移（再点一次退出）"))
        self.act_pan.setCheckable(True)
        self.act_pan.toggled.connect(self._on_pan_toggled)
        self._keep_action(self.act_pan)
        g.add_action(self.act_pan, variant="GgsBigCheckButtonStyle1")

        c1 = g.small_column()
        for label, icon_name, meth, tip in (
                (_tr("缩放到 100%"), "zoom_100", "zoom_actual",
                 _tr("按屏幕实际尺寸显示（1:1）")),
                (_tr("适应页面"), "zoom_full", "fit_page",
                 _tr("适应页面"))):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(
                lambda _c=False, m=meth:
                getattr(self.view, m)() if self.view is not None else None)
            self._keep_action(a)
            g.add_action(a, big=False, col=c1, icon_only=True)
        c2 = g.small_column()
        for label, icon_name, meth, tip in (
                (_tr("放大"), "zoom_in", "zoom_in", _tr("放大")),
                (_tr("缩小"), "zoom_out", "zoom_out", _tr("缩小"))):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(
                lambda _c=False, m=meth:
                getattr(self.view, m)() if self.view is not None else None)
            self._keep_action(a)
            g.add_action(a, big=False, col=c2, icon_only=True)
        a = QAction(_icons.icon("refresh", size=16), _tr("刷新预览"), self)
        a.setToolTip(_tr("重新渲染底图"))
        a.triggered.connect(lambda _c=False: self._refresh_view(True))
        self._keep_action(a)
        g.add_action(a, big=False, col=c1, icon_only=True)
        pg.add_group(g)

        g = RibbonGroup(_tr("选择"))
        self.act_select = QAction(_icons.icon("select", size=BIG_ICON),
                                  _tr("选择"), self)
        self.act_select.setToolTip(_tr("选择元素"))
        self.act_select.triggered.connect(
            lambda _c=False: self._set_select_mode("rect"))
        self.m_select = QMenu(self)
        for label, code, icon_name, tip in (
                (_tr("矩形"), "rect", "sel_rect", _tr("拖框选择元素")),
                (_tr("多边形"), "poly", "sel_poly",
                 ""),
                (_tr("套索"), "lasso", "sel_lasso", _tr("按住左键自由描圈选择")),
                (_tr("圆"), "circle", "sel_circle", _tr("按住拖出圆（内切椭圆）选择")),
                (_tr("线"), "line", "sel_line",
                 _tr("拖一条线，选中与它相交的元素"))):
            a = self.m_select.addAction(_icons.icon(icon_name, size=16), label)
            a.setCheckable(True)
            a.setData(code)
            a.setToolTip(tip)
            a.triggered.connect(
                lambda _c=False, v=code: self._set_select_mode(v))
        try:
            self.m_select.actions()[0].setChecked(True)
        except Exception:
            exc_note("_ribbon_bar @ ggis/ui/views/layout/workspace.py:1283")
            pass
        self._keep_action(self.act_select)
        g.add_dropdown(self.act_select, self.m_select, style2=True,
                       variant="GgsBigMenuButtonStyle4", tip=_tr("选择方式"))
        col = g.small_column()
        for label, icon_name, slot, tip, link in (
                (_tr("按属性选择"), "select_attr", self._pick_select_by_type,
                 "", LINK_ITEMS),
                (_tr("按位置选择"), "sel_bylocation",
                 self._select_by_location,
                 _tr("选中与当前选中元素相交的元素"), LINK_SEL)):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(lambda _c=False, sl=slot: sl())
            self._keep_action(a)
            self._link(a, link)
            g.add_action(a, big=False, col=col)
        col2 = g.small_column()
        a = QAction(_icons.icon("deselect", size=16), _tr("清除"), self)
        a.setToolTip(_tr("取消全部选中"))
        a.triggered.connect(lambda _c=False: self.view.clear_selection())
        self._keep_action(a)
        self._link(a, LINK_SEL)
        g.add_action(a, big=False, col=col2)
        pg.add_group(g)

        g = RibbonGroup(_tr("显示"))
        box = QWidget()
        vb = QVBoxLayout(box)
        vb.setContentsMargins(2, 0, 2, 0)
        vb.setSpacing(1)
        self.chk_ruler = QCheckBox(_tr("标尺"))
        self.chk_ruler.setToolTip(_tr("标尺"))
        self.chk_ruler.toggled.connect(self._on_ruler_toggled)
        self.chk_guides = QCheckBox(_tr("参考线"))
        self.chk_guides.setToolTip(_tr(""
                                       ""))
        self.chk_guides.toggled.connect(self._on_guides_toggled)
        self.chk_margin = QCheckBox(_tr("边距"))
        self.chk_margin.setToolTip(_tr("页边距"))
        self.chk_margin.toggled.connect(self._on_margin_toggled)
        for c in (self.chk_ruler, self.chk_guides, self.chk_margin):
            c.setFixedHeight(20)
            vb.addWidget(c)
        self.chk_ruler.setChecked(True)
        g.add_widget(box)
        self.act_guide_h = QAction(_icons.icon("guide", size=16),
                                   _tr("添加水平参考线"), self)
        self.act_guide_h.setToolTip(_tr("在右键的位置添加一条水平参考线"))
        self.act_guide_h.triggered.connect(
            lambda _c=False: self.add_guide_at_cursor(True))
        self.act_guide_v = QAction(_icons.icon("guide", size=16),
                                   _tr("添加垂直参考线"), self)
        self.act_guide_v.setToolTip(_tr("在右键的位置添加一条垂直参考线"))
        self.act_guide_v.triggered.connect(
            lambda _c=False: self.add_guide_at_cursor(False))
        self.act_guide_clear = QAction(_icons.icon("delete", size=16),
                                       _tr("清除全部参考线"), self)
        self.act_guide_clear.setToolTip(_tr("删掉所有参考线"))
        self.act_guide_clear.triggered.connect(
            lambda _c=False: self.clear_guides_all())
        for a in (self.act_guide_h, self.act_guide_v, self.act_guide_clear):
            self._keep_action(a)
        self._link(self.act_guide_clear, LINK_GUIDES)
        pg.add_group(g)

        g = RibbonGroup(_tr("地图框"))
        self.act_activate = QAction(_icons.icon("layout_map", size=BIG_ICON),
                                    _tr("激活"), self)
        self.act_activate.setCheckable(True)
        self.act_activate.setToolTip(
            _tr("激活地图框"))
        self.act_activate.toggled.connect(self._on_activate_map)
        self._keep_action(self.act_activate)
        self._link(self.act_activate, LINK_MAP)
        g.add_action(self.act_activate, variant="GgsBigCheckButtonStyle1")

        col = g.small_column()
        a = QAction(_icons.icon("zoom_layer", size=16), _tr("缩放到全图"), self)
        a.setToolTip("")
        a.triggered.connect(lambda _c=False: self._map_frame_full())
        self._keep_action(a)
        self._link(a, LINK_MAP)
        g.add_action(a, big=False, col=col)
        for label, icon_name, slot, tip in (
                (_tr("缩放到视图范围"), "zoom_map", self._adopt_view,
                 ""),
                (_tr("缩放到比例尺"), "ruler", self._adopt_scale,
                 "")):
            a = QAction(_icons.icon(icon_name, size=16), label, self)
            a.setToolTip(tip)
            a.triggered.connect(lambda _c=False, sl=slot: sl())
            self._keep_action(a)
            self._link(a, LINK_MAP)
            g.add_action(a, big=False, col=col)
        pg.add_group(g)

        if mine and hasattr(self, "fill_help_ribbon_page"):
            pg_h = rb.add_tab(_tr("帮助"), tag="__always__")
            try:
                self.ctx.region("ribbon").fill_help_ribbon_page(pg_h)
            except Exception:
                _log.exception("布局：帮助页构建失败")

        if not mine:
            for _i in (getattr(self, "_ribbon_indexes", None) or []):
                try:
                    rb.set_tab_visible(_i, False)
                except Exception:
                    exc_note("_ribbon_bar @ ggis/ui/views/layout/workspace.py:1448")
                    pass

        return rb

    def _add_insert_groups(self, page):
        by_type = {t: (t, lb, ic) for t, lb, ic in ADD_BUTTONS}
        from ggis.ui.framework.ribbon import BIG_ICON, RibbonGroup
        for gname, members in INSERT_GROUPS:
            g = RibbonGroup(_tr(gname))
            for t in members:
                row = by_type.get(t)
                if row is None:
                    _log.warning("布局：INSERT_GROUPS 里的 %r 不在 ADD_BUTTONS 中",
                                 t)
                    continue
                tn, label, icon_name = row
                a = QAction(_icons.icon(icon_name, size=BIG_ICON),
                            _tr(label), self)
                a.setToolTip(_tr("添加") + _tr(label))
                a.triggered.connect(
                    lambda _c=False, t=tn: self._begin_insert(t))
                self._keep_action(a)
                if tn in FRAME_BOUND_ITEMS:
                    self._link(a, LINK_FRAME)
                if tn == "map_frame":
                    self.act_mapframe = a
                    self._link(a, LINK_MAPVIEW)
                    m = GgsLayoutMapViewMenu(self)
                    self._fill_map_view_menu(m)
                    self.m_mapframe = m
                    try:
                        m.aboutToShow.connect(
                            lambda _m=m: self._fill_map_view_menu(
                                _m, refill=True))
                    except Exception:
                        exc_note("_add_insert_groups @ ggis/ui/views/layout/workspace.py:1515")
                        pass
                    try:
                        _vh = getattr(self._win, "view_host", None)
                        if _vh is not None:
                            _vh.viewsChanged.connect(
                                self._refresh_map_view_menu)
                    except Exception:
                        exc_note("_add_insert_groups @ ggis/ui/views/layout/workspace.py:1522")
                        pass
                    self.act_mapframe_btn = g.add_dropdown(
                        a, m, big=True, style2=True, variant="GgsBigMenuButtonStyle2",
                        tip=_tr("插入地图框（在页面上拖出一个方框）"))
                    self._refresh_map_view_menu()
                    continue
                g.add_action(a, big=True, variant="GgsBigButtonStyle1")
            page.add_group(g)

    def _keep_action(self, action):
        if not hasattr(self, "_ins_actions"):
            self._ins_actions = []
        self._ins_actions.append(action)
        return action

    def _update_action_states(self):
        try:
            sel = len(self._selected_or_current())
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1558")
            sel = 0
        try:
            items = len(list(getattr(self.lay, "items", None) or []))
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1562")
            items = 0
        clip = bool(getattr(self, "_clip", None))
        has_map = False
        try:
            has_map = any(str(getattr(i, "type_name", "")) == "map_frame"
                          for i in (self.lay.items or []))
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1569")
            has_map = False
        try:
            n_guide = len(self.view.guides())
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1573")
            n_guide = 0
        try:
            prev_ok = bool(self.view.can_prev_view())
            next_ok = bool(self.view.can_next_view())
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1578")
            prev_ok = next_ok = False
        try:
            has_frame_sel = self._selected_map_frame() is not None
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1583")
            has_frame_sel = False

        table = {
            LINK_SEL: sel >= 1,
            LINK_SEL2: sel >= 2,
            LINK_CLIP: clip,
            LINK_ITEMS: items >= 1,
            LINK_MAP: has_map,
            LINK_PREV: prev_ok,
            LINK_NEXT: next_ok,
            LINK_GUIDES: n_guide >= 1,
            LINK_FRAME: has_frame_sel,
            LINK_MAPVIEW: self._has_map_view(),
        }
        try:
            acts = list(self.findChildren(QAction))
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1601")
            acts = []
        d = getattr(self, "_delegate", None)
        if d is not None and d is not self:
            try:
                acts.extend(d.findChildren(QAction))
            except Exception:
                exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1611")
                pass
        for a in acts:
            try:
                key = a.property("ggsLink")
            except Exception:
                exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1616")
                continue
            if not key:
                continue
            try:
                a.setEnabled(bool(table.get(str(key), True)))
            except Exception:
                exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1622")
                pass
        try:
            self._update_items_bar()
        except Exception:
            exc_note("_update_action_states @ ggis/ui/views/layout/workspace.py:1627")
            pass
        return table

    def _link(self, action, key):
        try:
            action.setProperty("ggsLink", str(key))
        except Exception:
            exc_note("_link @ ggis/ui/views/layout/workspace.py:1635")
            pass
        return action

    def _stacked(self, *rows, width=150):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(2)
        for tag, wdg in rows:
            line = QHBoxLayout()
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(4)
            lb = GgsRibbonMini(str(tag))
            lb.setFixedWidth(42)
            lb.setAlignment(Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter)
            try:
                wdg.setFixedHeight(22)
                wdg.setMinimumWidth(max(60, int(width) - 50))
                wdg.setMaximumWidth(int(width))
            except Exception:
                exc_note("_stacked @ ggis/ui/views/layout/workspace.py:1659")
                pass
            line.addWidget(lb)
            line.addWidget(wdg, 1)
            lay.addLayout(line)
        return box

    def _left_panel(self):

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = GgsDockToolbar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        bl.setSpacing(2)
        self._item_btns = []

        def _btn(icon_name, tip, cb):
            b = GgsSmallButtonStyle1(icon_name, _tr(tip), cb)
            bl.addWidget(b)
            self._item_btns.append(b)
            return b

        self.b_item_all = _btn("checkbox_on", "全选",
                               lambda: self._later_run(self._select_all))
        self.b_item_rename = _btn("edit", "重命名",
                                  lambda: self._later_run(self._rename_current))
        self.b_item_del = _btn("delete", "删除元素",
                               lambda: self._later_run(self._delete_from_list))
        bl.addStretch(1)
        self.b_item_show = _btn("visible", "显示",
                                lambda: self._later_run(
                                    lambda: self._set_current_visible(True)))
        self.b_item_hide = _btn("hidden", "隐藏",
                                lambda: self._later_run(
                                    lambda: self._set_current_visible(False)))
        lay.addWidget(bar)
        lay.addSpacing(4)

        self.lst = _LayoutItemsTree()
        self.lst.setHeaderHidden(True)
        self.lst.setColumnCount(1)
        self.lst.setRootIsDecorated(False)
        self.lst.setIndentation(0)
        self.lst.setIconSize(QSize(16, 16))
        self.lst.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.lst.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.lst.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.lst.setDragEnabled(True)
        self.lst.setAcceptDrops(True)
        self.lst.setDropIndicatorShown(True)
        try:
            self.lst.rowsReordered.connect(self._on_rows_moved)
        except Exception:
            exc_note("_left_panel @ ggis/ui/views/layout/workspace.py:1767")
            pass
        self.lst.itemChanged.connect(self._on_item_changed)
        self.lst.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.lst.customContextMenuRequested.connect(self._on_list_menu)
        self.lst.currentItemChanged.connect(self._on_row_changed)
        lay.addWidget(self.lst, 1)

        self._update_items_bar()
        return body

    def _update_items_bar(self):
        btns = [b for b in (getattr(self, "_item_btns", None) or [])
                if _alive(b)]
        if not btns:
            return
        try:
            it = self._current_item()
        except Exception:
            exc_note("_update_items_bar @ ggis/ui/views/layout/workspace.py:1802")
            it = None
        on = it is not None
        try:
            has_items = bool(list(getattr(self.lay, "items", None) or []))
        except Exception:
            exc_note("_update_items_bar @ ggis/ui/views/layout/workspace.py:1807")
            has_items = False
        b_all = getattr(self, "b_item_all", None)
        for b in btns:
            try:
                b.setEnabled(bool(has_items) if b is b_all else bool(on))
            except Exception:
                exc_note("_update_items_bar @ ggis/ui/views/layout/workspace.py:1815")
                pass

    def _center_panel(self):
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.view = LayoutView()
        self.view.deleteRequested.connect(
            lambda it: self.remove_item(it))
        self.view.layout_scene().set_layout(self.lay, self._project)
        self.view.layout_scene().geometryChanged.connect(self._on_geom)
        self.view.itemPicked.connect(self._on_picked)
        try:
            self.view.itemDoubleClicked.connect(self._on_item_dblclicked)
        except Exception:
            _log.exception("布局：双击元素信号接线失败")
        try:
            self.view.textEdited.connect(self._on_canvas_text_edited)
        except Exception:
            exc_note("_center_panel @ ggis/ui/views/layout/workspace.py:1839")
            pass
        try:
            self.view.guidesShown.connect(self._on_guides_shown)
        except Exception:
            exc_note("_center_panel @ ggis/ui/views/layout/workspace.py:1845")
            pass
        try:
            self.view.contextMenuRequested.connect(self._on_canvas_menu)
        except Exception:
            exc_note("_center_panel @ ggis/ui/views/layout/workspace.py:1851")
            pass
        try:
            self.view.viewHistoryChanged.connect(
                lambda: self._update_action_states())
        except Exception:
            exc_note("_center_panel @ ggis/ui/views/layout/workspace.py:1857")
            pass
        try:
            self.view.rectDrawn.connect(self._on_rect_drawn)
        except Exception:
            exc_note("_center_panel @ ggis/ui/views/layout/workspace.py:1864")
            pass
        lay.addWidget(self.view, 1)
        return box

    def _right_panel(self):
        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 6, 8, 2)
        lay.setSpacing(6)
        self.lbl_sel = GgsLayoutSelLabel(_tr("未选中元素"))
        self.lbl_sel.setVisible(False)

        self.row_props_top = QWidget()
        ht = QHBoxLayout(self.row_props_top)
        ht.setContentsMargins(0, 0, 0, 0)
        ht.setSpacing(6)
        self.spn_z = QSpinBox()
        self.spn_z.setRange(-99, 999)
        self.spn_z.setToolTip(_tr("同一位置上的元素，值大的画在上面"))
        self.spn_z.valueChanged.connect(self._apply_common)
        _lb = QLabel(_tr("绘制顺序"))
        ht.addWidget(_lb)
        ht.addWidget(self.spn_z)
        ht.addStretch(1)
        lay.addWidget(self.row_props_top)

        self.row_props_sep = GgsSepH()
        self.row_props_sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(self.row_props_sep)

        host = QWidget()
        self.props_lay = QVBoxLayout(host)
        self.props_lay.setContentsMargins(0, 0, 0, 0)
        self.props_lay.setSpacing(8)
        self.scroll_props = GgsLayoutPropsScroll()
        self.scroll_props.setWidgetResizable(True)
        self.scroll_props.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_props.setWidget(host)
        lay.addWidget(self.scroll_props, 1)

        self._build_common_props()
        self._build_type_props()
        self.props_lay.addStretch(1)

        foot = QHBoxLayout()
        foot.setSpacing(6)
        foot.addStretch(1)
        foot.addWidget(self.btn_fit_content)
        lay.addLayout(foot)

        try:
            from ggis.common.widgets.inputs import relax_wide_inputs
            relax_wide_inputs(body, limit=96)
        except Exception:
            exc_note("_right_panel @ ggis/ui/views/layout/workspace.py:1962")
            pass
        self._set_props_content(False)
        return body

    def _set_props_content(self, on):
        for _w in (getattr(self, "row_props_top", None),
                   getattr(self, "row_props_sep", None),
                   getattr(self, "scroll_props", None),
                   getattr(self, "btn_fit_content", None)):
            if _w is None:
                continue
            try:
                _w.setVisible(bool(on))
            except Exception:
                exc_note("_set_props_content @ ggis/ui/views/layout/workspace.py:1987")
                pass

    def _grp(self, title):
        gb = QGroupBox(_tr(title))
        f = QFormLayout(gb)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(5)
        try:
            f.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            exc_note("_grp @ ggis/ui/views/layout/workspace.py:2000")
            pass
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter)
        self.props_lay.addWidget(gb)
        return gb, f

    def _build_common_props(self):
        gb, f = self._grp("位置与尺寸")
        self.spn_rect = []
        for i, tag in enumerate(("X", "Y", "宽", "高")):
            sp = QDoubleSpinBox()
            sp.setRange(-2000.0 if i < 2 else 1.0, 3000.0)
            sp.setDecimals(1)
            sp.setSingleStep(1.0)
            sp.setSuffix(" mm")
            sp.valueChanged.connect(self._apply_common)
            self.spn_rect.append(sp)
        row = QGridLayout()
        row.addWidget(QLabel("X"), 0, 0)
        row.addWidget(self.spn_rect[0], 0, 1)
        row.addWidget(QLabel("Y"), 0, 2)
        row.addWidget(self.spn_rect[1], 0, 3)
        row.addWidget(QLabel(_tr("宽")), 1, 0)
        row.addWidget(self.spn_rect[2], 1, 1)
        row.addWidget(QLabel(_tr("高")), 1, 2)
        row.addWidget(self.spn_rect[3], 1, 3)
        f.addRow(row)


        self.chk_align = QCheckBox(_tr("对齐页面内容区（页边距内）"))
        self.chk_align.setToolTip(
            "")
        self.btn_fit_content = GgsStandardButton("fit", _tr("铺满内容区"), parent=self)
        self.btn_fit_content.clicked.connect(self._fit_to_content)
        f.addRow(self.chk_align)

        self.gb_common = gb

    def _build_type_props(self):
        self.stack = QStackedWidget()
        self.props_lay.addWidget(self.stack)
        self.pages = {}

        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.lst_layers = QListWidget()
        self.lst_layers.itemChanged.connect(self._apply_map)
        f.addRow(_tr("图层"), self.lst_layers)
        self.btn_all_layers = GgsStandardButton("select", _tr("全选 / 全不选"), parent=self)
        self.btn_all_layers.clicked.connect(self._toggle_all_layers)
        f.addRow(self.btn_all_layers)
        self.cmb_mode = GgsComboBox()
        self.cmb_mode.addItem(_tr("按比例尺"), "scale")
        self.cmb_mode.addItem(_tr("指定范围"), "extent")
        self.cmb_mode.addItem(_tr("全图"), "full")
        self.cmb_mode.addItem(_tr("所选图层"), "layer")
        self.cmb_mode.currentIndexChanged.connect(self._apply_map)
        f.addRow(_tr("定位方式"), self.cmb_mode)
        self.spn_scale = QDoubleSpinBox()
        self.spn_scale.setRange(1.0, 1e9)
        self.spn_scale.setDecimals(0)
        self.spn_scale.setSingleStep(1000.0)
        self.spn_scale.setGroupSeparatorShown(True)
        self.spn_scale.valueChanged.connect(self._apply_map)
        self.spn_scale.setPrefix("1 : ")
        f.addRow(_tr("比例尺分母"), self.spn_scale)
        self.spn_center = []
        for tag in ("中心 X", "中心 Y"):
            sp = QDoubleSpinBox()
            sp.setRange(-1e12, 1e12)
            sp.setDecimals(2)
            sp.setGroupSeparatorShown(True)
            sp.valueChanged.connect(self._apply_map)
            self.spn_center.append(sp)
            f.addRow(_tr(tag), sp)
        self.btn_from_view = GgsStandardButton("layout_map", _tr("用当前地图视图"), parent=self)
        self.btn_from_view.setToolTip(
            "")
        self.btn_from_view.clicked.connect(self._adopt_view)
        f.addRow(self.btn_from_view)
        self.chk_frame = QCheckBox(_tr("绘制图框边框"))
        self.chk_frame.stateChanged.connect(self._apply_map)
        f.addRow(self.chk_frame)
        self.chk_map_all_layers = QCheckBox(_tr("包含已隐藏的图层"))
        self.chk_map_all_layers.setToolTip(
            _tr(""
                ""))
        self.chk_map_all_layers.stateChanged.connect(self._apply_map)
        f.addRow(self.chk_map_all_layers)
        self.chk_map_fill = QCheckBox(_tr("充满图框"))
        self.chk_map_fill.setToolTip(
            _tr(""
                ""))
        self.chk_map_fill.stateChanged.connect(self._apply_map)
        f.addRow(self.chk_map_fill)
        self.fld_map_bg = GgsColorField("#FFFFFF", self, shape="rect")
        self.fld_map_bg.colorChanged.connect(self._apply_map)
        f.addRow(_tr("背景色"), self.fld_map_bg)

        sep = GgsSepH()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        f.addRow(sep)
        self.chk_frame_grid = QCheckBox(_tr("格网"))
        self.chk_frame_grid.setToolTip(
            _tr(""
                ""))
        self.chk_frame_grid.stateChanged.connect(self._on_frame_grid_toggled)
        f.addRow(self.chk_frame_grid)
        self.cmb_gd_kind = GgsComboBox()
        self.cmb_gd_kind.addItem(_tr("方里网"), "grid")
        self.cmb_gd_kind.addItem(_tr("经纬网"), "graticule")
        self.cmb_gd_kind.currentIndexChanged.connect(self._apply_grid)
        f.addRow(_tr("类型"), self.cmb_gd_kind)
        self.spn_gd_int = QDoubleSpinBox()
        self.spn_gd_int.setRange(0.0, 1e9)
        self.spn_gd_int.setDecimals(0)
        self.spn_gd_int.setSingleStep(100.0)
        self.spn_gd_int.setGroupSeparatorShown(True)
        self.spn_gd_int.valueChanged.connect(self._apply_grid)
        f.addRow(_tr("间隔（图面单位）"), self.spn_gd_int)
        self.spn_gd_deg = QDoubleSpinBox()
        self.spn_gd_deg.setRange(0.000001, 10.0)
        self.spn_gd_deg.setDecimals(6)
        self.spn_gd_deg.valueChanged.connect(self._apply_grid)
        f.addRow(_tr("间隔（度）"), self.spn_gd_deg)
        self.spn_gd_font = self._pt_spin(4.0, 20.0, self._apply_grid)
        f.addRow(_tr("注记字号"), self.spn_gd_font)
        self.chk_gd_labels = QCheckBox(_tr("显示注记"))
        self.chk_gd_labels.stateChanged.connect(self._apply_grid)
        f.addRow(self.chk_gd_labels)
        self.fld_gd_color = GgsColorField("#7A7A7A", self, shape="line")
        self.fld_gd_color.colorChanged.connect(self._apply_grid)
        f.addRow(_tr("线条颜色"), self.fld_gd_color)
        self.fld_gd_label = GgsColorField(LI.TEXT_COLOR, self, shape="rect")
        self.fld_gd_label.colorChanged.connect(self._apply_grid)
        f.addRow(_tr("注记颜色"), self.fld_gd_label)
        self.pages["map_frame"] = self._wrap("地图框", w)
        self.pages["grid"] = self.pages["map_frame"]

        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.ed_leg_title = QLineEdit()
        self.ed_leg_title.editingFinished.connect(self._apply_legend)
        f.addRow(_tr("标题"), self.ed_leg_title)
        self.lst_leg_layers = QListWidget()
        self.lst_leg_layers.itemChanged.connect(self._apply_legend)
        f.addRow(_tr("图层"), self.lst_leg_layers)
        self.spn_leg_font = self._pt_spin(4.0, 40.0,
                                          self._apply_legend)
        f.addRow(_tr("正文字号"), self.spn_leg_font)
        self.spn_leg_titlefont = self._pt_spin(4.0, 48.0,
                                               self._apply_legend)
        f.addRow(_tr("标题字号"), self.spn_leg_titlefont)
        self.spn_leg_cols = QSpinBox()
        self.spn_leg_cols.setRange(1, 4)
        self.spn_leg_cols.valueChanged.connect(self._apply_legend)
        f.addRow(_tr("列数"), self.spn_leg_cols)
        self.chk_leg_layername = QCheckBox(_tr("显示图层名"))
        self.chk_leg_layername.stateChanged.connect(self._apply_legend)
        f.addRow(self.chk_leg_layername)
        self.chk_leg_title = QCheckBox(_tr("显示标题"))
        self.chk_leg_title.stateChanged.connect(self._apply_legend)
        f.addRow(self.chk_leg_title)
        self.fld_leg_text = GgsColorField(LI.TEXT_COLOR, self, shape="rect")
        self.fld_leg_text.colorChanged.connect(self._apply_legend)
        f.addRow(_tr("文字颜色"), self.fld_leg_text)
        self.fld_leg_bg = GgsColorField("#FFFFFF", self, shape="rect")
        self.fld_leg_bg.colorChanged.connect(self._apply_legend)
        f.addRow(_tr("背景色"), self.fld_leg_bg)
        self.chk_leg_fit = QCheckBox(_tr("按内容自动收缩高度"))
        self.chk_leg_fit.stateChanged.connect(self._apply_legend)
        f.addRow(self.chk_leg_fit)
        self.btn_leg_auto = GgsStandardButton("fit", _tr("按内容调整到合适大小"), parent=self)
        self.btn_leg_auto.clicked.connect(self._legend_autosize)
        f.addRow(self.btn_leg_auto)
        self.pages["legend"] = self._wrap("图例", w)

        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.cmb_sb_link = GgsComboBox()
        self.cmb_sb_link.currentIndexChanged.connect(self._apply_scale)
        f.addRow(_tr("链接地图框"), self.cmb_sb_link)
        self.cmb_sb_units = GgsComboBox()
        self.cmb_sb_units.addItem(_tr("图面单位"), "map")
        self.cmb_sb_units.addItem(_tr("公制 (m/km)"), "metric")
        self.cmb_sb_units.addItem(_tr("英制 (ft)"), "imperial")
        self.cmb_sb_units.currentIndexChanged.connect(self._apply_scale)
        f.addRow(_tr("计量单位"), self.cmb_sb_units)
        self.spn_sb_div = QSpinBox()
        self.spn_sb_div.setRange(1, 12)
        self.spn_sb_div.valueChanged.connect(self._apply_scale)
        f.addRow(_tr("分段数"), self.spn_sb_div)
        self.spn_sb_font = self._pt_spin(4.0, 24.0, self._apply_scale)
        f.addRow(_tr("字号"), self.spn_sb_font)
        self.spn_sb_h = QDoubleSpinBox()
        self.spn_sb_h.setRange(0.6, 12.0)
        self.spn_sb_h.setDecimals(1)
        self.spn_sb_h.setSuffix(" mm")
        self.spn_sb_h.valueChanged.connect(self._apply_scale)
        f.addRow(_tr("条高"), self.spn_sb_h)
        self.chk_sb_units = QCheckBox(_tr("显示单位"))
        self.chk_sb_units.stateChanged.connect(self._apply_scale)
        f.addRow(self.chk_sb_units)
        self.chk_sb_scale = QCheckBox(_tr("显示 1:N 比例文字"))
        self.chk_sb_scale.stateChanged.connect(self._apply_scale)
        f.addRow(self.chk_sb_scale)
        self.fld_sb_text = GgsColorField(LI.TEXT_COLOR, self, shape="rect")
        self.fld_sb_text.colorChanged.connect(self._apply_scale)
        f.addRow(_tr("文字颜色"), self.fld_sb_text)
        self.fld_sb_a = GgsColorField("#FFFFFF", self, shape="rect")
        self.fld_sb_a.colorChanged.connect(self._apply_scale)
        f.addRow(_tr("分段色 1"), self.fld_sb_a)
        self.fld_sb_b = GgsColorField("#2B2B2B", self, shape="rect")
        self.fld_sb_b.colorChanged.connect(self._apply_scale)
        f.addRow(_tr("分段色 2"), self.fld_sb_b)
        self.pages["scale_bar"] = self._wrap("比例尺", w)

        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.cmb_na_style = GgsComboBox()
        for label, code in (("罗盘", "compass"), ("玫瑰", "rose"),
                            ("箭头", "arrow"), ("北字", "letter")):
            self.cmb_na_style.addItem(_tr(label), code)
        self.cmb_na_style.currentIndexChanged.connect(self._apply_north)
        f.addRow(_tr("样式"), self.cmb_na_style)
        self.spn_na_angle = QDoubleSpinBox()
        self.spn_na_angle.setRange(-360.0, 360.0)
        self.spn_na_angle.setDecimals(1)
        self.spn_na_angle.setSuffix(" °")
        self.spn_na_angle.valueChanged.connect(self._apply_north)
        f.addRow(_tr("旋转角"), self.spn_na_angle)
        self.spn_na_font = self._pt_spin(5.0, 36.0, self._apply_north)
        f.addRow(_tr("字号"), self.spn_na_font)
        self.chk_na_label = QCheckBox(_tr("显示「北」"))
        self.chk_na_label.stateChanged.connect(self._apply_north)
        f.addRow(self.chk_na_label)
        self.fld_na_color = GgsColorField("#333333", self, shape="rect")
        self.fld_na_color.colorChanged.connect(self._apply_north)
        f.addRow(_tr("颜色"), self.fld_na_color)
        self.fld_na_fill = GgsColorField("#FFFFFF", self, shape="rect")
        self.fld_na_fill.colorChanged.connect(self._apply_north)
        f.addRow(_tr("填充色"), self.fld_na_fill)
        self.pages["north_arrow"] = self._wrap("指北针", w)


        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.ed_txt = QTextEdit()
        self.ed_txt.setMaximumHeight(90)
        self.ed_txt.textChanged.connect(self._apply_text)
        f.addRow(_tr("内容"), self.ed_txt)
        self.spn_txt_font = self._pt_spin(4.0, 120.0, self._apply_text)
        f.addRow(_tr("字号"), self.spn_txt_font)
        self.chk_txt_bold = QCheckBox(_tr("粗体"))
        self.chk_txt_bold.stateChanged.connect(self._apply_text)
        f.addRow(self.chk_txt_bold)
        self.chk_txt_italic = QCheckBox(_tr("斜体"))
        self.chk_txt_italic.stateChanged.connect(self._apply_text)
        f.addRow(self.chk_txt_italic)
        self.cmb_txt_align = GgsComboBox()
        for label, code in (("居中", "center"), ("左", "left"),
                            ("右", "right")):
            self.cmb_txt_align.addItem(_tr(label), code)
        self.cmb_txt_align.currentIndexChanged.connect(self._apply_text)
        f.addRow(_tr("对齐"), self.cmb_txt_align)
        self.cmb_txt_family = ggs_font_combo(self)
        self.cmb_txt_family.currentIndexChanged.connect(self._apply_text)
        f.addRow(_tr("字体"), self.cmb_txt_family)
        self.btn_txt_color = GgsColorField(LI.TEXT_COLOR, self, shape="rect")
        self.btn_txt_color.colorChanged.connect(self._apply_text)
        f.addRow(_tr("颜色"), self.btn_txt_color)
        self.chk_txt_bg = QCheckBox(_tr("背景"))
        self.chk_txt_bg.stateChanged.connect(self._apply_text)
        f.addRow(self.chk_txt_bg)
        self.fld_txt_bg = GgsColorField("#FFFFFF", self, shape="rect")
        self.fld_txt_bg.colorChanged.connect(self._apply_text)
        f.addRow(_tr("背景色"), self.fld_txt_bg)
        self.pages["text"] = self._wrap("文字", w)

        w = QWidget()
        f = QFormLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        self.ed_img = QLineEdit()
        self.ed_img.editingFinished.connect(self._apply_image)
        f.addRow(_tr("文件"), self.ed_img)
        self.btn_img = GgsStandardButton("folder", _tr("浏览…"), parent=self)
        self.btn_img.clicked.connect(self._browse_image)
        f.addRow(self.btn_img)
        self.chk_img_aspect = QCheckBox(_tr("保持长宽比"))
        self.chk_img_aspect.stateChanged.connect(self._apply_image)
        f.addRow(self.chk_img_aspect)
        self.pages["image"] = self._wrap("图片", w)

        self.pages[""] = self._wrap("（未选中）", QLabel(
            ""))

    def _wrap(self, title, widget):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        gb = QGroupBox(_tr(title + "属性"))
        g = QVBoxLayout(gb)
        g.setContentsMargins(8, 8, 8, 8)
        g.addWidget(widget)
        v.addWidget(gb)
        idx = self.stack.addWidget(page)
        self._pump()
        return idx

    def _pt_spin(self, lo, hi, slot):
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(1)
        sp.setSingleStep(0.5)
        sp.setSuffix(" pt")
        sp.valueChanged.connect(slot)
        return sp

    def _vsep(self):
        f = GgsLayoutStatusSep()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setFrameShadow(QFrame.Shadow.Plain)
        f.setFixedWidth(1)
        return f

    def _bottom_bar(self):
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.lbl_page = GgsLayoutStatus()
        row.addWidget(self.lbl_page)
        self._sep1 = self._vsep()
        row.addWidget(self._sep1)

        self.lbl_stat_sel = GgsLayoutStatus()
        row.addWidget(self.lbl_stat_sel)
        self._sep2 = self._vsep()
        row.addWidget(self._sep2)

        self.lbl_msg = QLabel()
        self.lbl_msg.setWordWrap(False)
        self.lbl_msg.setSizePolicy(QSizePolicy.Policy.Ignored,
                                   QSizePolicy.Policy.Preferred)
        row.addWidget(self.lbl_msg, 1)

        self.lbl_zoom = GgsLayoutStatus(_tr("缩放"))
        row.addWidget(self.lbl_zoom)
        self.cmb_zoom = GgsLayoutZoom()
        self.cmb_zoom.setToolTip(_tr("缩放"))
        for pct in (25, 50, 75, 100, 150, 200, 400, 800):
            self.cmb_zoom.addItem("%d%%" % pct, pct / 100.0)
        self.cmb_zoom.setEditable(True)
        self.cmb_zoom.setFixedWidth(88)
        try:
            self.cmb_zoom.lineEdit().setAlignment(
                Qt.AlignmentFlag.AlignRight)
        except Exception:
            exc_note("_bottom_bar @ ggis/ui/views/layout/workspace.py:2460")
            pass
        self.cmb_zoom.activated.connect(self._on_zoom_picked)
        try:
            self.cmb_zoom.lineEdit().editingFinished.connect(
                self._on_zoom_typed)
        except Exception:
            exc_note("_bottom_bar @ ggis/ui/views/layout/workspace.py:2468")
            pass
        row.addWidget(self.cmb_zoom)

        self.btn_export = GgsLayoutExport(_tr("导出"))
        self.btn_export.setToolTip(_tr("导出") + " / " + _tr("打印"))
        self.btn_export.setAutoDefault(True)
        m_exp = QMenu(self.btn_export)
        for label, fmt in ((_tr("导出 PDF"), "pdf"),
                           (_tr("导出 SVG"), "svg"),
                           (_tr("导出图片"), None),
                           (_tr("打印…"), "print")):
            a = m_exp.addAction(label)
            a.triggered.connect(lambda _c=False, f=fmt: self.export(f))
        self.btn_export.setMenu(m_exp)
        row.addWidget(self.btn_export)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        try:
            btns.button(QDialogButtonBox.StandardButton.Close)\
                .setText(_tr("关闭"))
        except Exception:
            exc_note("_bottom_bar @ ggis/ui/views/layout/workspace.py:2491")
            pass
        row.addWidget(btns)

        from ggis.ui.framework.statusbar import STATUS_CTRL_H, STATUS_H
        w.setFixedHeight(STATUS_H + 2)
        row.setContentsMargins(4, 0, 4, 0)
        for _wd in (self.lbl_page, self.lbl_stat_sel, self.lbl_msg,
                    self.lbl_zoom, self.cmb_zoom, self._sep1, self._sep2):
            try:
                _wd.setFixedHeight(STATUS_CTRL_H)
            except Exception:
                exc_note("_bottom_bar @ ggis/ui/views/layout/workspace.py:2506")
                pass
        self.btn_export.setFixedHeight(STATUS_CTRL_H)
        try:
            for _b in btns.buttons():
                _b.setFixedHeight(STATUS_CTRL_H)
        except Exception:
            exc_note("_bottom_bar @ ggis/ui/views/layout/workspace.py:2512")
            pass

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(400)
        self._status_timer.timeout.connect(self._sync_status)
        self._status_timer.start()
        self.bottom = w
        return w

    def status_texts(self):
        try:
            self._sync_status()
        except Exception:
            exc_note("status_texts @ ggis/ui/views/layout/workspace.py:2543")
            pass

        def _txt(w):
            try:
                return str(w.text() or "")
            except Exception:
                exc_note("_txt @ ggis/ui/views/layout/workspace.py:2549")
                return ""

        zoom = ""
        try:
            zoom = str(self.cmb_zoom.currentText() or "")
        except Exception:
            exc_note("status_texts @ ggis/ui/views/layout/workspace.py:2555")
            zoom = ""
        return (_txt(getattr(self, "lbl_page", None)),
                _txt(getattr(self, "lbl_stat_sel", None)), zoom)

    def _on_pan_toggled(self, on):
        try:
            self.view.set_pan_mode(bool(on))
        except Exception:
            exc_note("_on_pan_toggled @ ggis/ui/views/layout/workspace.py:2564")
            pass

    def _on_zoom_typed(self):
        try:
            txt = str(self.cmb_zoom.currentText() or "")
            txt = txt.replace("%", "").replace("％", "").strip()
            if not txt:
                return
            v = float(txt)
            if v > 10.0:
                v = v / 100.0
            self.view.set_zoom(v)
        except Exception:
            exc_note("_on_zoom_typed @ ggis/ui/views/layout/workspace.py:2578")
            pass
        self._sync_status()

    def _on_zoom_picked(self, idx):
        try:
            z = self.cmb_zoom.itemData(int(idx))
            if z:
                self.view.set_zoom(float(z))
        except Exception:
            exc_note("_on_zoom_picked @ ggis/ui/views/layout/workspace.py:2588")
            pass
        self._sync_status()

    def _sync_status(self):
        try:
            if not self.isVisible():
                return
        except Exception:
            exc_note("_sync_status @ ggis/ui/views/layout/workspace.py:2597")
            return
        try:
            orient = (_tr("横向")
                      if self.lay.orientation == ORIENTATION_LANDSCAPE
                      else _tr("纵向"))
            self.lbl_page.setText("%s %s %s" % (
                _tr("页面"), self._page_label(self.lay.page), orient))
        except Exception:
            exc_note("_sync_status @ ggis/ui/views/layout/workspace.py:2608")
            pass
        try:
            it = self._current_item()
            if it is None:
                self.lbl_stat_sel.setText("")
            else:
                r = it.rect()
                self.lbl_stat_sel.setText("%s %s (%.1f, %.1f) %.1f×%.1f" % (
                    _tr("位置"), str(getattr(it, "label", "") or ""),
                    r.x(), r.y(), r.width(), r.height()))
        except Exception:
            exc_note("_sync_status @ ggis/ui/views/layout/workspace.py:2619")
            pass
        try:
            self.cmb_zoom.setEditText("%d%%" % int(
                round(float(self.view.zoom()) * 100.0)))
        except Exception:
            exc_note("_sync_status @ ggis/ui/views/layout/workspace.py:2627")
            pass
        for sep, lbl in ((self._sep1, self.lbl_page),
                         (self._sep2, self.lbl_stat_sel)):
            try:
                sep.setVisible(bool(str(lbl.text() or "").strip()))
            except Exception:
                exc_note("_sync_status @ ggis/ui/views/layout/workspace.py:2634")
                pass
        self._sync_props_title()

    def _reload_all(self):
        self._syncing = True
        try:
            i = self.cmb_page.findData(self.lay.page)
            if i >= 0:
                self.cmb_page.setCurrentIndex(i)
            j = self.cmb_orient.findData(self.lay.orientation)
            if j >= 0:
                self.cmb_orient.setCurrentIndex(j)
            for sp, v in zip(self.spn_margins, self.lay.margins_mm):
                sp.setValue(float(v))
            k = self.cmb_dpi.findData(int(self.lay.dpi or 300))
            if k >= 0:
                self.cmb_dpi.setCurrentIndex(k)
            self._reload_links()
            self._reload_layer_lists()
            self._reload_list()
            self._sync_page_buttons()
            self._update_action_states()
        finally:
            self._syncing = False
        self._pump()

    def _reload_list(self):
        lst = self.lst
        lst.blockSignals(True)
        try:
            lst.clear()
            items = list(self.lay.items_in_draw_order())
            by_host = {}
            tops = []
            for it in reversed(items):
                host = None
                try:
                    lk = str(getattr(it, "link", "") or "")
                    if lk and not isinstance(it, LI.MapFrame):
                        host = self.lay.resolve_link(lk)
                except Exception:
                    exc_note("_reload_list @ ggis/ui/views/layout/workspace.py:2698")
                    host = None
                if (isinstance(host, LI.MapFrame) and host is not it):
                    by_host.setdefault(host.id, []).append(it)
                else:
                    tops.append(it)
            for it in tops:
                node = self._make_elem_item(it)
                lst.addTopLevelItem(node)
                if isinstance(it, LI.MapFrame):
                    for child in by_host.get(it.id, []):
                        node.addChild(self._make_elem_item(child))
                    try:
                        node.setExpanded(True)
                    except Exception:
                        exc_note("_reload_list @ ggis/ui/views/layout/workspace.py:2712")
                        pass
        finally:
            lst.blockSignals(False)
        self._update_action_states()

    def _make_elem_item(self, it):
        nm = str(getattr(it, "name", "") or "") or str(it.label or "")
        li = QTreeWidgetItem([nm])
        li.setData(0, ROLE_ELEM_ID, it.id)
        li.setFlags(li.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEditable
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled)
        _elem_set_drop(li, False)
        try:
            li.setCheckState(
                0, Qt.CheckState.Checked
                if getattr(it, "visible", True)
                else Qt.CheckState.Unchecked)
        except Exception:
            exc_note("_make_elem_item @ ggis/ui/views/layout/workspace.py:2741")
            pass
        self._set_item_icon(
            li, ELEMENT_ICONS.get(str(it.type_name), "layer"))
        self._apply_row_visible_style(li, bool(getattr(it, "visible", True)))
        try:
            summ = str(it.preview_text() or "")
            if summ and summ != nm:
                li.setToolTip(0, summ)
        except Exception:
            exc_note("_make_elem_item @ ggis/ui/views/layout/workspace.py:2750")
            pass
        return li

    @staticmethod
    def _apply_row_visible_style(li, visible):
        try:
            if visible:
                col = None
            else:
                from ggis.common.styling import icons as _ic
                from ggis.common.styling import themes as _th
                col = QColor(_th.theme_color("text_disabled",
                                             bool(_ic.is_dark())))
            for c in range(li.columnCount()):
                li.setForeground(c, QBrush(col) if col is not None
                                 else QBrush())
        except Exception:
            exc_note("_apply_row_visible_style @ ggis/ui/views/layout/workspace.py:2773")
            pass

    def _set_item_icon(self, item, icon_name, col=0):
        try:
            item.setData(col, ROLE_ICON_NAME, icon_name)
        except Exception:
            exc_note("_set_item_icon @ ggis/ui/views/layout/workspace.py:2787")
            pass
        try:
            item.setIcon(col, _icons.icon(icon_name, size=16))
        except Exception:
            exc_note("_set_item_icon @ ggis/ui/views/layout/workspace.py:2791")
            pass

    def retheme(self):
        lst = getattr(self, "lst", None)
        if lst is None:
            return
        try:
            for i in range(lst.topLevelItemCount()):
                li = lst.topLevelItem(i)
                if li is None:
                    continue
                name = li.data(0, ROLE_ICON_NAME)
                if name:
                    try:
                        li.setIcon(0, _icons.icon(str(name), size=16))
                    except Exception:
                        exc_note("retheme @ ggis/ui/views/layout/workspace.py:2813")
                        pass
                it = self.lay.item_by_id(li.data(0, ROLE_ELEM_ID))
                if it is not None:
                    self._apply_row_visible_style(
                        li, bool(getattr(it, "visible", True)))
            lst.viewport().update()
        except Exception:
            exc_note("retheme @ ggis/ui/views/layout/workspace.py:2821")
            pass

    def _rename_current(self):
        li = self.lst.currentItem()
        if li is None:
            return
        try:
            self.lst.setCurrentItem(li)
            self.lst.editItem(li, 0)
        except Exception:
            exc_note("_rename_current @ ggis/ui/views/layout/workspace.py:2837")
            pass

    def _set_current_visible(self, on):
        it = self._current_item()
        if it is None:
            return
        if bool(getattr(it, "visible", True)) == bool(on):
            return
        it.visible = bool(on)
        self._set_row_check(it.id, bool(on))
        self._refresh_view()

    def _set_row_check(self, item_id, checked):
        lst = getattr(self, "lst", None)
        if lst is None:
            return
        try:
            lst.blockSignals(True)
            for i in range(lst.topLevelItemCount()):
                li = lst.topLevelItem(i)
                if li is None or li.data(0, ROLE_ELEM_ID) != item_id:
                    continue
                li.setCheckState(
                    0, Qt.CheckState.Checked if checked
                    else Qt.CheckState.Unchecked)
                self._apply_row_visible_style(li, bool(checked))
                break
        except Exception:
            exc_note("_set_row_check @ ggis/ui/views/layout/workspace.py:2875")
            pass
        finally:
            try:
                lst.blockSignals(False)
            except Exception:
                exc_note("_set_row_check @ ggis/ui/views/layout/workspace.py:2880")
                pass

    def _reload_links(self):
        names = self.lay.link_names()
        for cmb in (self.cmb_sb_link,):
            cmb.blockSignals(True)
            cmb.clear()
            cmb.addItem(_tr("（第一个地图框）"), "")
            for n in names:
                cmb.addItem(n, n)
            cmb.blockSignals(False)

    def _reload_layer_lists(self):
        layers = list(self._project.layers()) if self._project else []
        for lst, chosen in ((self.lst_layers, "map"),
                            (self.lst_leg_layers, "legend")):
            lst.blockSignals(True)
            lst.clear()
            cur = self._current_item()
            ids = []
            if cur is not None:
                ids = list(getattr(cur, "layer_ids", []) or [])
            for lyr in reversed(layers):
                it = QListWidgetItem("%s  ·  %s" % (lyr.name(),
                                                    lyr.type_label()))
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(
                    Qt.CheckState.Checked
                    if (not ids or lyr.id() in ids)
                    else Qt.CheckState.Unchecked)
                it.setData(Qt.ItemDataRole.UserRole, lyr.id())
                lst.addItem(it)
            lst.blockSignals(False)
        del layers

    def _checked_layer_ids(self, lst):
        out, all_checked = [], True
        for i in range(lst.count()):
            it = lst.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
            else:
                all_checked = False
        return [] if all_checked else out

    def _current_item(self):
        lst = getattr(self, "lst", None)
        if not _alive(lst):
            return None
        try:
            li = lst.currentItem()
            if li is None:
                return None
            lid = li.data(0, ROLE_ELEM_ID)
        except Exception:
            exc_note("_current_item @ ggis/ui/views/layout/workspace.py:2941")
            return None
        if not lid:
            return None
        try:
            return self.lay.item_by_id(lid)
        except Exception:
            exc_note("_current_item @ ggis/ui/views/layout/workspace.py:2947")
            return None

    def _later_run(self, fn):
        def _run():
            try:
                fn()
            except Exception:
                _log.exception("布局元素动作失败")
        try:
            QTimer.singleShot(0, _run)
        except Exception:
            exc_note("_later_run @ ggis/ui/views/layout/workspace.py:2968")
            _run()

    def _cur_row(self):
        try:
            li = self.lst.currentItem()
            if li is None:
                return -1
            return int(self.lst.indexOfTopLevelItem(li))
        except Exception:
            exc_note("_cur_row @ ggis/ui/views/layout/workspace.py:2979")
            return -1

    def _select_index(self, row):
        try:
            n = int(self.lst.topLevelItemCount())
            if n <= 0:
                return
            li = self.lst.topLevelItem(max(0, min(int(row), n - 1)))
            if li is not None:
                self.lst.setCurrentItem(li)
        except Exception:
            exc_note("_select_index @ ggis/ui/views/layout/workspace.py:2991")
            pass

    def _sync_props(self, item):
        self._syncing = True
        try:
            if item is None:
                self.stack.setCurrentIndex(self.pages[""])
                self.lbl_sel.setText(_tr("未选中元素"))
                self.gb_common.setEnabled(False)
                self._set_props_content(False)
                return
            self.gb_common.setEnabled(True)
            self._set_props_content(True)
            _nm = (str(getattr(item, "name", "") or "")
                   or str(item.label or ""))
            _sm = str(item.preview_text() or "")
            if not _sm or _sm == _nm:
                self.lbl_sel.setText(_nm)
            elif _sm.startswith(_nm):
                self.lbl_sel.setText(_sm)
            else:
                self.lbl_sel.setText("%s · %s" % (_nm, _sm))
            r = item.rect_mm
            self.spn_rect[0].setValue(r.x())
            self.spn_rect[1].setValue(r.y())
            self.spn_rect[2].setValue(r.width())
            self.spn_rect[3].setValue(r.height())
            self.spn_z.setValue(int(item.z))
            t = item.type_name
            self.stack.setCurrentIndex(self.pages.get(t, self.pages[""]))
            self._reload_layer_lists()

            if t == "map_frame":
                i = self.cmb_mode.findData(item.mode)
                if i >= 0:
                    self.cmb_mode.setCurrentIndex(i)
                self.spn_scale.setValue(float(item.scale or 50000.0))
                for sp, v in zip(self.spn_center, item.center):
                    sp.setValue(float(v))
                self.chk_frame.setChecked(bool(item.show_frame))
                self.chk_map_all_layers.setChecked(
                    not bool(getattr(item, "visible_only", True)))
                self.chk_map_fill.setChecked(
                    str(getattr(item, "fit_mode", "expand")) == "fill")
                self.fld_map_bg.setColor(str(item.background or "#FFFFFF"))
                self.spn_scale.setEnabled(item.mode == "scale")
                self.spn_center[0].setEnabled(item.mode == "scale")
                self.spn_center[1].setEnabled(item.mode == "scale")
                self._reload_grid_props(getattr(item, "grid", None))
            elif t == "legend":
                self.ed_leg_title.setText(item.title)
                self.spn_leg_font.setValue(item.font_size_pt)
                self.spn_leg_titlefont.setValue(item.title_size_pt)
                self.spn_leg_cols.setValue(int(item.columns))
                self.chk_leg_layername.setChecked(item.show_layer_name)
                self.chk_leg_title.setChecked(item.show_title)
                self.fld_leg_text.setColor(
                    str(item.text_color or LI.TEXT_COLOR))
                self.fld_leg_bg.setColor(str(item.background or "#FFFFFF"))
                self.chk_leg_fit.setChecked(item.fit_height)
            elif t == "scale_bar":
                i = self.cmb_sb_link.findData(item.link)
                self.cmb_sb_link.setCurrentIndex(max(0, i))
                i = self.cmb_sb_units.findData(item.units)
                self.cmb_sb_units.setCurrentIndex(max(0, i))
                self.spn_sb_div.setValue(int(item.divisions))
                self.spn_sb_font.setValue(item.font_size_pt)
                self.spn_sb_h.setValue(item.bar_height_mm)
                self.chk_sb_units.setChecked(item.show_units)
                self.chk_sb_scale.setChecked(item.show_scale_text)
                self.fld_sb_text.setColor(str(item.text_color or LI.TEXT_COLOR))
                self.fld_sb_a.setColor(str(item.fill_a or "#FFFFFF"))
                self.fld_sb_b.setColor(str(item.fill_b or "#2B2B2B"))
            elif t == "north_arrow":
                i = self.cmb_na_style.findData(item.style)
                self.cmb_na_style.setCurrentIndex(max(0, i))
                self.spn_na_angle.setValue(item.angle)
                self.spn_na_font.setValue(item.label_size_pt)
                self.chk_na_label.setChecked(item.show_label)
                self.fld_na_color.setColor(str(item.color or "#333333"))
                self.fld_na_fill.setColor(str(item.fill or "#FFFFFF"))
            elif t == "grid":
                self._reload_grid_props(item)
            elif t == "text":
                self.ed_txt.setPlainText(item.content)
                ggs_font_select(self.cmb_txt_family,
                                str(item.font_family or ""))
                self.btn_txt_color.setColor(item.color)
                self.spn_txt_font.setValue(item.font_size_pt)
                self.chk_txt_bold.setChecked(item.bold)
                self.chk_txt_italic.setChecked(item.italic)
                i = self.cmb_txt_align.findData(item.align)
                self.cmb_txt_align.setCurrentIndex(max(0, i))
                _bg = str(getattr(item, "background", "") or "")
                self.chk_txt_bg.setChecked(bool(_bg))
                self.fld_txt_bg.setColor(_bg or "#FFFFFF")
                self.fld_txt_bg.setEnabled(bool(_bg))
            elif t == "image":
                self.ed_img.setText(item.path)
                self.chk_img_aspect.setChecked(item.keep_aspect)
        finally:
            self._syncing = False

    def _reload_grid_props(self, g):
        on = g is not None
        try:
            self.chk_frame_grid.setChecked(bool(on))
        except Exception:
            exc_note("_reload_grid_props @ ggis/ui/views/layout/workspace.py:3122")
            pass
        for w in (self.cmb_gd_kind, self.spn_gd_int, self.spn_gd_deg,
                  self.spn_gd_font, self.chk_gd_labels, self.fld_gd_color,
                  self.fld_gd_label):
            try:
                w.setEnabled(on)
            except Exception:
                exc_note("_reload_grid_props @ ggis/ui/views/layout/workspace.py:3129")
                pass
        if not on:
            return
        try:
            i = self.cmb_gd_kind.findData(g.kind)
            self.cmb_gd_kind.setCurrentIndex(max(0, i))
            self.spn_gd_int.setValue(float(g.interval))
            self.spn_gd_deg.setValue(float(g.interval_deg))
            self.spn_gd_font.setValue(float(g.font_size_pt))
            self.chk_gd_labels.setChecked(bool(g.show_labels))
            self.fld_gd_color.setColor(str(g.color or "#7A7A7A"))
            self.fld_gd_label.setColor(str(g.label_color or LI.TEXT_COLOR))
            self.spn_gd_int.setEnabled(str(g.kind) == "grid")
            self.spn_gd_deg.setEnabled(str(g.kind) == "graticule")
        except Exception:
            _log.exception("布局：格网参数回填失败")

    def _apply_common(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if item is None:
            return
        r = QRectF(self.spn_rect[0].value(), self.spn_rect[1].value(),
                   max(3.0, self.spn_rect[2].value()),
                   max(3.0, self.spn_rect[3].value()))
        item.set_rect_mm(r)
        item.z = int(self.spn_z.value())
        self._refresh_view_silent()

    def _apply_map(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if not isinstance(item, LI.MapFrame):
            return
        item.layer_ids = self._checked_layer_ids(self.lst_layers)
        item.mode = self.cmb_mode.currentData() or "scale"
        item.scale = float(self.spn_scale.value())
        item.center = [self.spn_center[0].value(),
                       self.spn_center[1].value()]
        item.show_frame = bool(self.chk_frame.isChecked())
        item.visible_only = not bool(self.chk_map_all_layers.isChecked())
        item.fit_mode = ("fill" if self.chk_map_fill.isChecked()
                         else "expand")
        item.background = QColor(self.fld_map_bg.color()).name()
        self.spn_scale.setEnabled(item.mode == "scale")
        self.spn_center[0].setEnabled(item.mode == "scale")
        self.spn_center[1].setEnabled(item.mode == "scale")
        self._refresh_view_silent()

    def _apply_legend(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if not isinstance(item, LI.Legend):
            return
        item.layer_ids = self._checked_layer_ids(self.lst_leg_layers)
        item.title = self.ed_leg_title.text()
        item.font_size_pt = self.spn_leg_font.value()
        item.title_size_pt = self.spn_leg_titlefont.value()
        item.columns = int(self.spn_leg_cols.value())
        item.show_layer_name = bool(self.chk_leg_layername.isChecked())
        item.show_title = bool(self.chk_leg_title.isChecked())
        item.text_color = QColor(self.fld_leg_text.color()).name()
        item.background = QColor(self.fld_leg_bg.color()).name()
        item.fit_height = bool(self.chk_leg_fit.isChecked())
        self._refresh_view_silent()

    def _apply_scale(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if not isinstance(item, LI.ScaleBar):
            return
        item.link = self.cmb_sb_link.currentData() or ""
        item.units = self.cmb_sb_units.currentData() or "map"
        item.divisions = int(self.spn_sb_div.value())
        item.font_size_pt = self.spn_sb_font.value()
        item.bar_height_mm = self.spn_sb_h.value()
        item.show_units = bool(self.chk_sb_units.isChecked())
        item.show_scale_text = bool(self.chk_sb_scale.isChecked())
        item.text_color = QColor(self.fld_sb_text.color()).name()
        item.fill_a = QColor(self.fld_sb_a.color()).name()
        item.fill_b = QColor(self.fld_sb_b.color()).name()
        self._refresh_view_silent()

    def _apply_north(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if not isinstance(item, LI.NorthArrow):
            return
        item.style = self.cmb_na_style.currentData() or "compass"
        item.angle = self.spn_na_angle.value()
        item.label_size_pt = self.spn_na_font.value()
        item.show_label = bool(self.chk_na_label.isChecked())
        item.color = QColor(self.fld_na_color.color()).name()
        item.fill = QColor(self.fld_na_fill.color()).name()
        self._refresh_view_silent()

    def _apply_grid(self, *_):
        if self._syncing:
            return
        item = self._grid_target()
        if item is None:
            return
        item.kind = self.cmb_gd_kind.currentData() or "grid"
        item.interval = self.spn_gd_int.value()
        item.interval_deg = self.spn_gd_deg.value()
        item.font_size_pt = self.spn_gd_font.value()
        item.show_labels = bool(self.chk_gd_labels.isChecked())
        item.color = QColor(self.fld_gd_color.color()).name()
        item.label_color = QColor(self.fld_gd_label.color()).name()
        self.spn_gd_int.setEnabled(str(item.kind) == "grid")
        self.spn_gd_deg.setEnabled(str(item.kind) == "graticule")
        self._refresh_view_silent()

    def _on_canvas_text_edited(self, item, text):
        try:
            if item is self._current_item():
                self._syncing = True
                try:
                    self.ed_txt.setPlainText(item.content)
                finally:
                    self._syncing = False
        except Exception:
            exc_note("_on_canvas_text_edited @ ggis/ui/views/layout/workspace.py:3274")
            pass
        try:
            self._refresh_view()
        except Exception:
            exc_note("_on_canvas_text_edited @ ggis/ui/views/layout/workspace.py:3278")
            pass

    def _apply_text(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if not isinstance(item, LI.TextItem):
            return
        item.content = self.ed_txt.toPlainText()
        item.font_size_pt = self.spn_txt_font.value()
        item.bold = bool(self.chk_txt_bold.isChecked())
        item.italic = bool(self.chk_txt_italic.isChecked())
        item.align = self.cmb_txt_align.currentData() or "center"
        item.font_family = str(ggs_combo_value(self.cmb_txt_family) or "")
        item.color = QColor(self.btn_txt_color.color()).name()
        _on = bool(self.chk_txt_bg.isChecked())
        item.background = (QColor(self.fld_txt_bg.color()).name() if _on
                           else "")
        try:
            self.fld_txt_bg.setEnabled(_on)
        except Exception:
            exc_note("_apply_text @ ggis/ui/views/layout/workspace.py:3301")
            pass
        self._refresh_view_silent()

    def _apply_image(self, *_):
        if self._syncing:
            return
        item = self._current_item()
        if not isinstance(item, LI.ImageItem):
            return
        item.path = self.ed_img.text().strip()
        item.keep_aspect = bool(self.chk_img_aspect.isChecked())
        self._refresh_view_silent()

    def _page_label(self, name):
        key = str(name or "")
        base = PAGE_SIZES.get(key)
        if base is None:
            return key
        ww, hh = base
        if self.lay.orientation == ORIENTATION_PORTRAIT:
            ww, hh = min(ww, hh), max(ww, hh)
        else:
            ww, hh = max(ww, hh), min(ww, hh)
        unit = str(getattr(self.lay, "unit", "") or DEFAULT_UNIT)
        return "%s (%s×%s)" % (key, fmt_len(unit, ww), fmt_len(unit, hh))

    def _refresh_page_labels(self):
        for i in range(self.cmb_page.count()):
            name = self.cmb_page.itemData(i)
            if name in PAGE_SIZES:
                self.cmb_page.setItemText(i, self._page_label(name))

    def _apply_page(self):
        self.lay.set_page(self.cmb_page.currentData() or DEFAULT_PAGE,
                             self.cmb_orient.currentData())
        self.lay.set_margins(*[sp.value() for sp in self.spn_margins])
        self.lay.dpi = float(self.cmb_dpi.currentData() or 300)
        self._refresh_page_labels()
        sc = self.view.layout_scene()
        sc.set_layout(self.lay, self._project)
        self.view.fit_page()
        self._reload_list()
        self._select_index(self._cur_row())

    def _pick_page_size(self, name):
        try:
            i = self.cmb_page.findData(str(name))
            if i >= 0:
                self.cmb_page.setCurrentIndex(i)
        except Exception:
            exc_note("_pick_page_size @ ggis/ui/views/layout/workspace.py:3366")
            pass
        self._sync_page_buttons()

    def _pick_orient(self, code):
        try:
            i = self.cmb_orient.findData(str(code))
            if i >= 0:
                self.cmb_orient.setCurrentIndex(i)
        except Exception:
            exc_note("_pick_orient @ ggis/ui/views/layout/workspace.py:3376")
            pass
        self._sync_page_buttons()

    def _sync_page_buttons(self):
        try:
            for a in self.m_size.actions():
                a.setChecked(str(a.data() or "") == str(self.lay.page or ""))
        except Exception:
            exc_note("_sync_page_buttons @ ggis/ui/views/layout/workspace.py:3392")
            pass
        try:
            for a in self.m_orient.actions():
                a.setChecked(str(a.data() or "")
                             == str(self.lay.orientation or ""))
        except Exception:
            exc_note("_sync_page_buttons @ ggis/ui/views/layout/workspace.py:3398")
            pass

    def _on_page_changed(self, *_):
        if self._syncing:
            return
        self._apply_page()

    def _on_margins_changed(self, *_):
        if self._syncing:
            return
        self.lay.set_margins(*[sp.value() for sp in self.spn_margins])
        self._refresh_view()

    def _selected_map_frame(self):
        for it in self._selected_or_current():
            if isinstance(it, LI.MapFrame):
                return it
        return None

    def toggle_frame_grid(self, on=None):
        frame = self._selected_map_frame()
        if frame is None:
            self._msg(_tr("请先选中一个地图框，再开关格网"))
            return None
        want = (frame.grid is None) if on is None else bool(on)
        if want:
            if frame.grid is None:
                try:
                    frame.grid = LI.GridFrame(rect_mm=QRectF(frame.rect_mm),
                                              kind="grid")
                except Exception as e:
                    exc_note("toggle_frame_grid @ ggis/ui/views/layout/workspace.py:3449")
                    self._msg(_tr("格网创建失败：{0}").format(e))
                    return None
            self._msg(_tr("已为地图框「{0}」打开格网").format(
                frame.name or frame.label))
        else:
            frame.grid = None
            self._msg(_tr("已关闭该地图框的格网"))
        try:
            self._refresh_view()
        except Exception:
            exc_note("toggle_frame_grid @ ggis/ui/views/layout/workspace.py:3459")
            pass
        self._reload_list()
        self._select_by_id(frame.id)
        self._update_action_states()
        return frame.grid

    def _grid_target(self):
        it = self._current_item()
        if isinstance(it, LI.MapFrame):
            return it.grid
        if isinstance(it, LI.GridFrame):
            return it
        return None

    def _on_frame_grid_toggled(self, state):
        if self._syncing:
            return
        try:
            on = bool(int(state))
        except Exception:
            exc_note("_on_frame_grid_toggled @ ggis/ui/views/layout/workspace.py:3485")
            on = bool(state)
        self.toggle_frame_grid(on)

    def _has_map_view(self):
        if not self._embedded:
            return True
        try:
            vh = getattr(self._win, "view_host", None)
            return vh is not None and vh.view("map") is not None
        except Exception:
            exc_note("_has_map_view @ ggis/ui/views/layout/workspace.py:3502")
            return False

    def _refresh_map_view_menu(self, *_a):
        m = getattr(self, "m_mapframe", None)
        if m is not None:
            try:
                self._fill_map_view_menu(m, refill=True)
            except Exception:
                _log.exception("布局：刷新地图视图菜单失败")
        a = getattr(self, "act_mapframe", None)
        if a is not None:
            try:
                a.setToolTip(_tr("插入地图框（在页面上拖出一个方框）")
                             if self._has_map_view()
                             else _tr("需要先打开地图视图（＋ → 地图）"))
            except Exception:
                exc_note("_refresh_map_view_menu @ ggis/ui/views/layout/workspace.py:3525")
                pass
        try:
            self._update_action_states()
        except Exception:
            exc_note("_refresh_map_view_menu @ ggis/ui/views/layout/workspace.py:3529")
            pass
        try:
            b = getattr(self, "act_mapframe_btn", None)
            if b is not None:
                b.setEnabled(bool(self._has_map_view()))
        except Exception:
            exc_note("_refresh_map_view_menu @ ggis/ui/views/layout/workspace.py:3541")
            pass

    def _fill_map_view_menu(self, m, refill=False):
        if refill:
            m.clear()
        views = []
        try:
            vh = getattr(self._win, "view_host", None)
            if vh is not None:
                v = vh.view("map")
                if v is not None:
                    views.append(v)
        except Exception:
            exc_note("_fill_map_view_menu @ ggis/ui/views/layout/workspace.py:3566")
            views = []
        if not views:
            if not self._embedded:
                m.addAction(_icons.icon("map_street", size=16), _tr("地图框"),
                            lambda: self._begin_insert("map_frame"))
                return
            a = m.addAction(_tr("（无地图视图）"))
            a.setEnabled(False)
            return
        for v in views:
            # 视图名创建后即固定（用户数据），不走翻译。
            title = str(getattr(v, "title", "") or "地图")
            a = m.addAction(_icons.icon("map_street", size=16), title)
            a.triggered.connect(
                lambda _c=False: self._begin_insert("map_frame"))

    def _begin_insert(self, type_name):
        t = str(type_name or "")
        if t == "grid":
            return self.toggle_frame_grid()
        if t in FRAME_BOUND_ITEMS and self._selected_map_frame() is None:
            self._msg(_tr("请先选中一个地图框"))
            return None
        try:
            self.view.begin_draw(t)
        except Exception:
            exc_note("_begin_insert @ ggis/ui/views/layout/workspace.py:3603")
            return self.add_item(t)
        label = {x[0]: x[1] for x in ADD_BUTTONS}.get(t, t)
        self._msg(_tr("拖出方框插入{0}").format(
            _tr(label)))
        return None

    def _on_rect_drawn(self, rect):
        t = ""
        try:
            t = str(self.view.draw_kind() or "")
        except Exception:
            exc_note("_on_rect_drawn @ ggis/ui/views/layout/workspace.py:3618")
            t = ""
        if not t:
            return None
        return self.add_item(t, rect)

    def add_item(self, type_name, rect=None):
        t = str(type_name or "")
        if t == "grid":
            return self.toggle_frame_grid()
        if rect is None:
            rect = self._default_rect(t)
        rect = QRectF(rect).normalized()
        if rect.width() < 3.0 or rect.height() < 3.0:
            rect = QRectF(rect.x(), rect.y(), max(3.0, rect.width()),
                          max(3.0, rect.height()))
        try:
            if t == "map_frame":
                item = LI.create_item(t, rect, mode="full")
            else:
                item = LI.create_item(t, rect)
        except LayoutError as exc:
            exc_note("add_item @ ggis/ui/views/layout/workspace.py:3651")
            self._msg(str(exc))
            return None
        host = self._selected_map_frame()
        if host is not None and t != "map_frame":
            try:
                item.link = str(host.id)
            except Exception:
                exc_note("add_item @ ggis/ui/views/layout/workspace.py:3658")
                item.link = ""
        base = max([int(x.z) for x in self.lay.items] or [0])
        item.z = base + 1
        self.lay.add_item(item)
        self.view.layout_scene().add_frame(item)
        self._reload_list()
        self._select_by_id(item.id)
        return item

    def _default_rect(self, type_name):
        cr = self.lay.content_rect_mm()
        w, h = LI.DEFAULT_SIZES.get(type_name, (40.0, 20.0))
        if type_name in ("map_frame", "grid"):
            return QRectF(cr.x(), cr.y(), cr.width(), cr.height())
        if type_name == "text":
            return QRectF(cr.x(), cr.bottom() - h - 8, cr.width(), h)
        step = 4.0
        for i in range(24):
            x = cr.x() + 2 + (i % 6) * (14.0 + step)
            y = cr.y() + 2 + (i // 6) * (30.0 + step)
            cand = QRectF(x, y, w, h)
            if not any(cand.intersects(it.rect_mm)
                       for it in self.lay.items):
                return cand
        return QRectF(cr.x() + 2, cr.y() + 2, w, h)

    def _select_by_id(self, item_id):
        lst = getattr(self, "lst", None)
        if lst is None:
            return
        try:
            for i in range(lst.topLevelItemCount()):
                li = lst.topLevelItem(i)
                if li is not None and li.data(0, ROLE_ELEM_ID) == item_id:
                    lst.setCurrentItem(li)
                    return
        except Exception:
            exc_note("_select_by_id @ ggis/ui/views/layout/workspace.py:3699")
            pass

    def show_message(self, text, level=0):
        try:
            from PySide6.QtGui import QCursor
            from PySide6.QtWidgets import QToolTip
            QToolTip.showText(QCursor.pos(), str(text), self)
            return
        except Exception:
            exc_note("show_message @ ggis/ui/views/layout/workspace.py:3720")
            pass
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.information(self, _tr("打印布局设计器"), str(text))
        except Exception:
            exc_note("show_message @ ggis/ui/views/layout/workspace.py:3725")
            pass

    def _align_item(self, edge):
        items = self._selected_or_current()
        if not items:
            self.show_message(_tr("请先在左侧选中一个元素"), 1)
            return
        moved = 0
        try:
            pr = self.lay.page_rect_mm()
            pw, ph = float(pr.width()), float(pr.height())
            for item in items:
                r = item.rect_mm
                w, h, x, y = r.width(), r.height(), r.x(), r.y()
                if edge == "left":
                    x = 0.0
                elif edge == "hcenter":
                    x = (pw - w) / 2.0
                elif edge == "right":
                    x = pw - w
                elif edge == "top":
                    y = 0.0
                elif edge == "vcenter":
                    y = (ph - h) / 2.0
                elif edge == "bottom":
                    y = ph - h
                item.set_rect_mm(QRectF(x, y, w, h))
                f = self.view.layout_scene().frame_of(item)
                if f is not None:
                    f.sync_from_item()
                moved += 1
        except Exception:
            exc_note("_align_item @ ggis/ui/views/layout/workspace.py:3768")
            return
        if not moved:
            return
        self._refresh_view()
        try:
            cur = self._current_item()
            if cur is not None:
                self._sync_props(cur)
        except Exception:
            exc_note("_align_item @ ggis/ui/views/layout/workspace.py:3777")
            pass

    def _distribute(self, axis):
        items = [x for x in self._selected_or_current() if x is not None]
        if len(items) < 3:
            self.show_message(_tr("分布至少需要选中 3 个元素"), 1)
            return
        horiz = str(axis) != "v"
        try:
            if horiz:
                items.sort(key=lambda it: float(it.rect_mm.left()))
                lo = float(items[0].rect_mm.left())
                hi = float(items[-1].rect_mm.right())
                span = hi - lo
                total = sum(float(it.rect_mm.width()) for it in items)
                gap = (span - total) / float(len(items) - 1)
                cur = lo
                for it in items:
                    r = QRectF(it.rect_mm)
                    r.moveLeft(cur)
                    it.set_rect_mm(r)
                    cur += float(r.width()) + gap
            else:
                items.sort(key=lambda it: float(it.rect_mm.top()))
                lo = float(items[0].rect_mm.top())
                hi = float(items[-1].rect_mm.bottom())
                span = hi - lo
                total = sum(float(it.rect_mm.height()) for it in items)
                gap = (span - total) / float(len(items) - 1)
                cur = lo
                for it in items:
                    r = QRectF(it.rect_mm)
                    r.moveTop(cur)
                    it.set_rect_mm(r)
                    cur += float(r.height()) + gap
        except Exception:
            _log.exception("布局：分布元素失败")
            return
        try:
            for it in items:
                f = self.view.layout_scene().frame_of(it)
                if f is not None:
                    f.sync_from_item()
        except Exception:
            exc_note("_distribute @ ggis/ui/views/layout/workspace.py:3831")
            pass
        self._refresh_view()
        self._msg(_tr("已按等间距分布 {0} 个元素").format(len(items)))

    def move_item_to(self, top):
        items = [x for x in self._selected_or_current() if x is not None]
        if not items:
            return
        try:
            zs = [int(getattr(x, "z", 0)) for x in self.lay.items]
        except Exception:
            exc_note("move_item_to @ ggis/ui/views/layout/workspace.py:3849")
            zs = []
        z = (max(zs) + 1) if top else (min(zs) - 1)
        step = 1 if top else -1
        for it in items:
            it.z = int(z)
            z += step
        self._reload_list()
        if len(items) == 1:
            self._select_by_id(getattr(items[0], "id", ""))
        self._refresh_view()
        self._msg(_tr("已置于顶层") if top else _tr("已置于底层"))

    def _delete_from_list(self):
        many = 0
        try:
            many = len(self.view.selected_items())
        except Exception:
            exc_note("_delete_from_list @ ggis/ui/views/layout/workspace.py:3878")
            many = 0
        if many > 1:
            self.delete_selected()
            return
        self.remove_current()

    def remove_current(self):
        item = self._current_item()
        if item is not None:
            self.remove_item(item)

    def remove_item(self, item):
        try:
            _log.info("布局元素：删除 %s（%s）",
                      getattr(item, "label", ""),
                      str(getattr(item, "id", "") or ""))
        except Exception:
            exc_note("remove_item @ ggis/ui/views/layout/workspace.py:3907")
            pass
        try:
            self.view._end_inline_edit()
        except Exception:
            exc_note("remove_item @ ggis/ui/views/layout/workspace.py:3912")
            pass
        try:
            if self.view.activated_frame() is item \
                    and getattr(self, "act_activate", None) is not None \
                    and self.act_activate.isChecked():
                self.act_activate.setChecked(False)
        except Exception:
            exc_note("remove_item @ ggis/ui/views/layout/workspace.py:3927")
            pass
        self.view.layout_scene().remove_frame(item)
        self.lay.remove_item(item)
        self._reload_list()
        self._select_index(self._cur_row())

    def _on_rows_moved(self, *_):
        if self._syncing:
            return
        try:
            ids = [str(self.lst.topLevelItem(i).data(0, ROLE_ELEM_ID) or "")
                   for i in range(self.lst.topLevelItemCount())]
            items = [self.lay.item_by_id(x) for x in ids]
        except Exception:
            exc_note("_on_rows_moved @ ggis/ui/views/layout/workspace.py:3950")
            return
        if not items or any(it is None for it in items):
            self._reload_list()
            return
        cur = self._current_item()
        n = len(items)
        for i, it in enumerate(items):
            it.z = n - i
        try:
            self._refresh_view()
        except Exception:
            exc_note("_on_rows_moved @ ggis/ui/views/layout/workspace.py:3961")
            pass
        self._reload_list()
        if cur is not None:
            self._select_by_id(cur.id)

    def _on_item_changed(self, li, col=0):
        if self._syncing:
            return
        try:
            iid = li.data(0, ROLE_ELEM_ID)
            it = self.lay.item_by_id(iid)
        except Exception:
            exc_note("_on_item_changed @ ggis/ui/views/layout/workspace.py:3984")
            return
        if it is None:
            return
        try:
            txt = str(li.text(0) or "").strip()
            cur = (str(getattr(it, "name", "") or "")
                   or str(getattr(it, "label", "") or ""))
            if txt != cur:
                it.name = "" if txt == str(getattr(it, "label", "") or "") \
                    else txt
                self._sync_props_title()
                if not txt:
                    self._later_run(lambda: self._rebuild_after_rename(it.id))
                    return
        except Exception:
            exc_note("_on_item_changed @ ggis/ui/views/layout/workspace.py:4005")
            pass
        try:
            vis = (li.checkState(0) == Qt.CheckState.Checked)
            if vis != bool(getattr(it, "visible", True)):
                it.visible = vis
                self._refresh_view()
        except Exception:
            exc_note("_on_item_changed @ ggis/ui/views/layout/workspace.py:4013")
            pass

    def _rebuild_after_rename(self, iid):
        self._reload_list()
        self._select_by_id(iid)

    def _toggle_item_visible(self):
        it = self._current_item()
        if it is None:
            return
        it.visible = not bool(getattr(it, "visible", True))
        self._set_row_check(it.id, bool(it.visible))
        self._refresh_view()

    def _on_list_menu(self, pos):
        li = self.lst.itemAt(pos)
        if li is not None:
            self.lst.setCurrentItem(li)
        it = self._current_item()
        if it is None:
            return
        iid = str(getattr(it, "id", "") or "")
        li = None

        def _later(fn):
            def _run():
                try:
                    fn()
                except Exception:
                    _log.exception("布局元素清单的菜单动作失败")
            return lambda _c=False: QTimer.singleShot(0, _run)

        m = GgsLayerTreeMenu(self)
        a = m.addAction(_tr("显示"))
        a.setCheckable(True)
        a.setChecked(bool(getattr(it, "visible", True)))
        a.triggered.connect(_later(self._toggle_item_visible))
        m.addSeparator()
        a = m.addAction(_tr("重命名"))
        a.triggered.connect(_later(lambda: self._rename_item(iid)))
        m.addAction(_tr("上移一层"), _later(lambda: self.move_item(1)))
        m.addAction(_tr("下移一层"), _later(lambda: self.move_item(-1)))
        m.addSeparator()
        m.addAction(_tr("删除"), _later(self.remove_current))
        try:
            m.exec(self.lst.viewport().mapToGlobal(pos))
        except Exception:
            _log.exception("布局元素清单的右键菜单出错")


    def _rename_item(self, iid):
        lst = getattr(self, "lst", None)
        if lst is None:
            return
        try:
            for i in range(lst.topLevelItemCount()):
                li = lst.topLevelItem(i)
                if li is not None and li.data(0, ROLE_ELEM_ID) == iid:
                    lst.setCurrentItem(li)
                    lst.editItem(li, 0)
                    return
        except Exception:
            exc_note("_rename_item @ ggis/ui/views/layout/workspace.py:4114")
            pass

    def _sync_props_title(self):
        try:
            it = self._current_item()
        except Exception:
            exc_note("_sync_props_title @ ggis/ui/views/layout/workspace.py:4127")
            it = None
        base = _tr("元素设置")
        if it is None:
            txt = base
        else:
            nm = (str(getattr(it, "name", "") or "")
                  or str(getattr(it, "label", "") or ""))
            txt = "%s — %s" % (base, nm) if nm else base
        dock = getattr(self, "dock_props", None)
        if dock is None:
            return
        try:
            dock.set_title_label(txt)
        except Exception:
            exc_note("_sync_props_title @ ggis/ui/views/layout/workspace.py:4141")
            try:
                dock.setWindowTitle(txt)
            except Exception:
                exc_note("_sync_props_title @ ggis/ui/views/layout/workspace.py:4144")
                pass

    def move_item(self, delta):
        item = self._current_item()
        if item is None:
            return
        if delta > 0:
            self.lay.raise_item(item)
        else:
            self.lay.lower_item(item)
        self._reload_list()
        self._select_by_id(item.id)

    def _toggle_all_layers(self):
        lst = self.lst_layers if self.stack.currentIndex() == \
            self.pages["map_frame"] else self.lst_leg_layers
        checked = any(lst.item(i).checkState() == Qt.CheckState.Unchecked
                      for i in range(lst.count()))
        for i in range(lst.count()):
            lst.item(i).setCheckState(Qt.CheckState.Checked if checked
                                      else Qt.CheckState.Unchecked)
        self._apply_map()
        self._apply_legend()

    def _fit_to_content(self):
        item = self._current_item()
        if item is None:
            return
        cr = self.lay.content_rect_mm()
        item.set_rect_mm(QRectF(cr))
        self._sync_props(item)
        f = self.view.layout_scene().frame_of(item)
        if f is not None:
            f.sync_from_item()
            f.setSelected(True)
        self._refresh_view()

    def _legend_autosize(self):
        item = self._current_item()
        if not isinstance(item, LI.Legend):
            return
        need = item.needed_height_mm(self._project)
        r = item.rect_mm
        item.set_rect_mm(QRectF(r.x(), r.y(), r.width(),
                                max(12.0, need)))
        self._sync_props(item)
        f = self.view.layout_scene().frame_of(item)
        if f is not None:
            f.sync_from_item()
        self._refresh_view()

    def _adopt_view(self):
        item = self._current_item()
        if not isinstance(item, LI.MapFrame):
            return
        ext = getattr(self, "_map_extent", None)
        if ext is None or ext.is_empty():
            self._msg(_tr("主窗口当前没有可用范围"))
            return
        item.mode = "extent"
        item.extent = [ext.xmin, ext.ymin, ext.xmax, ext.ymax]
        i = self.cmb_mode.findData("extent")
        self.cmb_mode.setCurrentIndex(max(0, i))
        self._refresh_view()

    def _browse_image(self):
        path, _f = GgsFileDialog.getOpenFileName(
            self, _tr("选择图片"), "", "图片 (*.png *.jpg *.jpeg *.bmp *.svg)")
        if path:
            self.ed_img.setText(path)
            self._apply_image()

    def _on_geom(self, *_):
        self._msg("")

    def _on_item_dblclicked(self, item):
        try:
            dock = getattr(self, "dock_props", None)
            if dock is not None:
                dock.show()
                dock.raise_()
        except Exception:
            _log.exception("布局：双击元素后亮出「元素设置」失败")
        try:
            self._msg(_tr("在右侧「元素设置」里改这个元素"))
        except Exception:
            exc_note("_on_item_dblclicked @ ggis/ui/views/layout/workspace.py:4242")
            pass

    def _on_picked(self, item):
        self._update_action_states()
        if item is None:
            return
        many = 0
        try:
            many = len(self.view.selected_items())
        except Exception:
            exc_note("_on_picked @ ggis/ui/views/layout/workspace.py:4259")
            many = 0
        if many <= 1:
            self._select_by_id(item.id)
        self._sync_props(item)

    def _on_row_changed(self, cur=None, prev=None):
        item = self._current_item() if cur is not None else None
        self._update_action_states()
        self._sync_props(item)
        if item is not None:
            self.view.layout_scene().select_item(item)

    def _refresh_view(self, now=False):
        try:
            self.view.sync_frames()
        except Exception:
            exc_note("_refresh_view @ ggis/ui/views/layout/workspace.py:4298")
            pass
        self.view.layout_scene().notify_changed()

    def _selected_or_current(self):
        try:
            items = self.view.selected_items()
        except Exception:
            exc_note("_selected_or_current @ ggis/ui/views/layout/workspace.py:4309")
            items = []
        if items:
            return items
        it = self._current_item()
        return [it] if it is not None else []

    def copy_selected(self):
        items = self._selected_or_current()
        if not items:
            self._msg(_tr("请先选中要复制的元素"))
            return
        try:
            self._clip = [LI.item_to_dict(it) for it in items]
            self._msg(_tr("已复制 {0} 个元素").format(len(self._clip)))
        except Exception as e:
            exc_note("copy_selected @ ggis/ui/views/layout/workspace.py:4332")
            self._msg(_tr("复制失败：{0}").format(e))

    def cut_selected(self):
        items = self._selected_or_current()
        if not items:
            self._msg(_tr("请先选中要剪切的元素"))
            return
        self.copy_selected()
        self.remove_items(items)

    def paste_items(self, in_place=False):
        clip = list(getattr(self, "_clip", None) or [])
        if not clip:
            self._msg(_tr("剪贴板里没有可粘贴的元素"))
            return
        base = max([int(x.z) for x in self.lay.items] or [0])
        added = []
        for i, d in enumerate(clip):
            try:
                dd = dict(d)
                dd.pop("id", None)
                it = LI.item_from_dict(dd)
            except Exception:
                exc_note("paste_items @ ggis/ui/views/layout/workspace.py:4365")
                it = None
            if it is None:
                continue
            try:
                r = QRectF(it.rect_mm)
                if not in_place:
                    r.moveTo(r.x() + 3.0, r.y() + 3.0)
                it.set_rect_mm(r)
                it.z = base + 1 + i
                self.lay.add_item(it)
                self.view.layout_scene().add_frame(it)
                added.append(it)
            except Exception:
                _log.exception("粘贴元素失败")
        if not added:
            self._msg(_tr("粘贴失败"))
            return
        self._reload_list()
        self._select_by_id(added[-1].id)
        self._refresh_view()
        self._msg(_tr("已粘贴 {0} 个元素").format(len(added)))

    def _select_all(self):
        try:
            self.view.select_all()
            its = self.view.selected_items()
            if its:
                self._select_by_id(its[-1].id)
            self._msg(_tr("已选中 {0} 个元素").format(len(its)))
        except Exception:
            exc_note("_select_all @ ggis/ui/views/layout/workspace.py:4402")
            pass

    def delete_selected(self):
        items = self._selected_or_current()
        if not items:
            self._msg(_tr("请先选中要删除的元素"))
            return
        self._later_run(lambda: self.remove_items(items))

    def remove_items(self, items):
        n = 0
        for it in list(items or []):
            try:
                self.remove_item(it)
                n += 1
            except Exception:
                _log.exception("删除元素失败")
        if n:
            self._msg(_tr("已删除 {0} 个元素").format(n))

    def _set_select_mode(self, code):
        code = str(code or "rect").lower()
        if code not in ("rect", "point", "poly", "lasso", "circle", "line"):
            code = "rect"
        try:
            self.view.set_select_mode(code)
        except Exception:
            exc_note("_set_select_mode @ ggis/ui/views/layout/workspace.py:4438")
            pass
        try:
            for a in self.m_select.actions():
                a.setChecked(str(a.data() or "") == code)
        except Exception:
            exc_note("_set_select_mode @ ggis/ui/views/layout/workspace.py:4443")
            pass
        if getattr(self, "act_pan", None) is not None:
            try:
                if self.act_pan.isChecked():
                    self.act_pan.setChecked(False)
            except Exception:
                exc_note("_set_select_mode @ ggis/ui/views/layout/workspace.py:4451")
                pass
        self._msg(_tr("选择方式：{0}").format(
            {"rect": _tr("矩形"), "point": _tr("点选"),
             "poly": _tr("多边形"), "lasso": _tr("套索"),
             "circle": _tr("圆"), "line": _tr("线")}.get(code, _tr("矩形"))))

    def _pick_select_by_type(self):
        try:
            from PySide6.QtGui import QCursor
        except Exception:
            exc_note("_pick_select_by_type @ ggis/ui/views/layout/workspace.py:4467")
            QCursor = None
        m = GgsLayoutSelTypeMenu(self)
        for t, label, icon_name in ADD_BUTTONS:
            a = m.addAction(_icons.icon(icon_name, size=16), _tr(label))
            a.setData(str(t))
            a.triggered.connect(
                lambda _c=False, tt=str(t): self._select_by_type(tt))
        if not m.actions():
            return
        try:
            m.exec(QCursor.pos() if QCursor is not None
                   else self.view.mapToGlobal(self.view.rect().center()))
        except Exception:
            exc_note("_pick_select_by_type @ ggis/ui/views/layout/workspace.py:4480")
            pass

    def _select_by_type(self, type_name):
        n = 0
        try:
            n = int(self.view.select_by_type(type_name))
        except Exception:
            exc_note("_select_by_type @ ggis/ui/views/layout/workspace.py:4488")
            n = 0
        self._msg(_tr("已按类型选中 {0} 个元素").format(n) if n > 0
                  else _tr("页面里没有这种元素"))

    def _select_by_location(self):
        try:
            sel = len(self._selected_or_current())
        except Exception:
            exc_note("_select_by_location @ ggis/ui/views/layout/workspace.py:4497")
            sel = 0
        if sel <= 0:
            self._msg(_tr("请先选中一个元素，再按位置选择"))
            return
        n = 0
        try:
            n = int(self.view.select_by_location("intersect"))
        except Exception:
            exc_note("_select_by_location @ ggis/ui/views/layout/workspace.py:4505")
            n = 0
        self._msg(_tr("已按位置追加选中 {0} 个元素").format(n))

    def _on_ruler_toggled(self, on):
        try:
            self.view.set_rulers(bool(on))
        except Exception:
            exc_note("_on_ruler_toggled @ ggis/ui/views/layout/workspace.py:4514")
            pass

    def _on_guides_toggled(self, on):
        try:
            self.view.set_guides_visible(bool(on))
        except Exception:
            exc_note("_on_guides_toggled @ ggis/ui/views/layout/workspace.py:4521")
            pass
        if not on:
            return
        c = getattr(self, "chk_ruler", None)
        if c is not None and not c.isChecked():
            c.setChecked(True)
        if not self.view.guides():
            self._msg(_tr("参考线：在标尺上按住拖动可移动，"
                          "在标尺空白处拖动可新建，标尺上右键可删除"))

    def _on_guides_shown(self):
        c = getattr(self, "chk_guides", None)
        if c is not None:
            try:
                c.blockSignals(True)
                c.setChecked(True)
            except Exception:
                exc_note("_on_guides_shown @ ggis/ui/views/layout/workspace.py:4547")
                pass
            finally:
                try:
                    c.blockSignals(False)
                except Exception:
                    exc_note("_on_guides_shown @ ggis/ui/views/layout/workspace.py:4552")
                    pass
        self._sync_guide_actions()

    def add_guide_at_cursor(self, horizontal):
        g = None
        try:
            g = self.view.add_guide_at(
                bool(horizontal),
                scene_pos=getattr(self, "_menu_scene_pos", None))
        except Exception:
            _log.exception("布局：添加参考线失败")
        if g is None:
            self._msg(_tr("添加参考线失败"))
            return
        self._sync_guide_actions()
        self._msg(_tr("参考线已添加（{0} mm）")
                  .format("%g" % round(g.pos_mm(), 1)))

    def clear_guides_all(self):
        n = 0
        try:
            n = len(self.view.guides())
            self.view.clear_guides()
        except Exception:
            exc_note("clear_guides_all @ ggis/ui/views/layout/workspace.py:4590")
            n = 0
        try:
            self.view.viewport().update()
        except Exception:
            exc_note("clear_guides_all @ ggis/ui/views/layout/workspace.py:4594")
            pass
        self._sync_guide_actions()
        self._msg(_tr("已清除 {0} 条参考线").format(n) if n
                  else _tr("当前没有参考线"))

    def _sync_guide_actions(self):
        try:
            n = len(self.view.guides())
        except Exception:
            exc_note("_sync_guide_actions @ ggis/ui/views/layout/workspace.py:4609")
            n = 0
        self._update_action_states()
        return n

    def _on_canvas_menu(self, gpos):
        try:
            vp_pt = self.view.viewport().mapFromGlobal(gpos)
            self._menu_scene_pos = self.view.mapToScene(vp_pt)
        except Exception:
            exc_note("_on_canvas_menu @ ggis/ui/views/layout/workspace.py:4627")
            self._menu_scene_pos = None
        try:
            m = GgsLayoutCanvasMenu(self)
            m.addAction(self.act_guide_h)
            m.addAction(self.act_guide_v)
            m.addAction(self.act_guide_clear)
            self._sync_guide_actions()
            m.addSeparator()
            for label, chk in ((_tr("标尺"), getattr(self, "chk_ruler", None)),
                               (_tr("参考线"), getattr(self, "chk_guides", None)),
                               (_tr("边距"), getattr(self, "chk_margin", None))):
                if chk is None:
                    continue
                a = m.addAction(label)
                a.setCheckable(True)
                a.setChecked(bool(chk.isChecked()))
                a.toggled.connect(chk.setChecked)
            m.addSeparator()
            a = m.addAction(_tr("适应页面"))
            a.triggered.connect(lambda _c=False: self.view.fit_page())
            a = m.addAction(_tr("缩放到 100%"))
            a.triggered.connect(lambda _c=False: self.view.zoom_actual())
            m.exec(QPoint(int(gpos.x()), int(gpos.y())))
        except Exception:
            _log.exception("布局：画布右键菜单失败")

    def _on_margin_toggled(self, on):
        try:
            self.view.set_margins_visible(bool(on))
        except Exception:
            exc_note("_on_margin_toggled @ ggis/ui/views/layout/workspace.py:4658")
            pass

    def _map_frame_of(self):
        it = None
        try:
            it = self.view.activated_frame()
        except Exception:
            exc_note("_map_frame_of @ ggis/ui/views/layout/workspace.py:4667")
            it = None
        if it is None:
            for x in self._selected_or_current():
                if isinstance(x, LI.MapFrame):
                    it = x
                    break
        if it is None:
            try:
                for x in self.lay.items_in_draw_order():
                    if isinstance(x, LI.MapFrame):
                        it = x
                        break
            except Exception:
                exc_note("_map_frame_of @ ggis/ui/views/layout/workspace.py:4680")
                it = None
        return it

    def _on_activate_map(self, on):
        it = self.view.set_map_activate(bool(on))
        if on and it is None:
            try:
                self.act_activate.setChecked(False)
            except Exception:
                exc_note("_on_activate_map @ ggis/ui/views/layout/workspace.py:4690")
                pass
            self._msg(_tr("页面里还没有地图框"))
            return
        if on:
            self._select_by_id(getattr(it, "id", ""))
            self._msg(_tr("已激活地图框"))
        else:
            self._msg(_tr("已取消激活地图框"))

    def _map_frame_full(self):
        it = self._map_frame_of()
        if it is None:
            self._msg(_tr("页面里还没有地图框"))
            return
        it.mode = "full"
        self.view.layout_scene().notify_changed()
        self._sync_props(it)

    def _adopt_scale(self):
        it = self._map_frame_of()
        if it is None:
            self._msg(_tr("页面里还没有地图框"))
            return
        try:
            ext = it.compute_extent(self._project, None)
            d = float(it.scale_denominator(ext, self._project) or 0.0)
        except Exception:
            exc_note("_adopt_scale @ ggis/ui/views/layout/workspace.py:4725")
            d = 0.0
        if d <= 0:
            self._msg(_tr("算不出当前比例尺"))
            return
        it.mode = "scale"
        it.scale = d
        self.view.layout_scene().notify_changed()
        self._sync_props(it)
        self._msg(_tr("已锁定比例尺 1:{0}").format("{:.0f}".format(d)))

    def duplicate_layout(self):
        try:
            d = dict(self.lay.to_dict())
            d.pop("id", None)
            d["name"] = _tr("{0} 副本").format(self.lay.name)
            new = Layout.from_dict(d)
        except Exception as e:
            exc_note("duplicate_layout @ ggis/ui/views/layout/workspace.py:4750")
            self._msg(_tr("复制布局失败：{0}").format(e))
            return None
        try:
            self.layoutDuplicated.emit(new)
            self._msg(_tr("已复制布局：{0}").format(new.name))
        except Exception:
            exc_note("duplicate_layout @ ggis/ui/views/layout/workspace.py:4756")
            pass
        return new

    def use_printer_page(self):
        try:
            from PySide6.QtPrintSupport import QPrinter
            pr = QPrinter(QPrinter.PrinterMode.HighResolution)
            pl = pr.pageLayout()
        except Exception as e:
            exc_note("use_printer_page @ ggis/ui/views/layout/workspace.py:4766")
            self._msg(_tr("取不到打印机：{0}").format(e))
            return
        name = ""
        try:
            ps = pl.pageSize()
            pid = ps.id()
            name = {
                QPageSize.PageSizeId.A3: "A3", QPageSize.PageSizeId.A4: "A4",
                QPageSize.PageSizeId.A5: "A5", QPageSize.PageSizeId.B4: "B4",
                QPageSize.PageSizeId.B5: "B5",
                QPageSize.PageSizeId.Letter: "Letter",
                QPageSize.PageSizeId.Legal: "Legal",
            }.get(pid, "")
        except Exception:
            exc_note("use_printer_page @ ggis/ui/views/layout/workspace.py:4781")
            name = ""
        try:
            land = (pl.orientation() == QPageLayout.Orientation.Landscape)
            self.cmb_orient.setCurrentIndex(0 if land else 1)
        except Exception:
            exc_note("use_printer_page @ ggis/ui/views/layout/workspace.py:4787")
            pass
        if name and name in PAGE_SIZES:
            self._pick_page_size(name)
        try:
            m = pl.margins(QPageLayout.Unit.Millimeter)
            mm = (float(m.left()), float(m.top()), float(m.right()),
                  float(m.bottom()))
            cur = self.lay.margins()
            new = tuple(max(cur[i], mm[i]) for i in range(4))
            self.lay.set_margins(*new)
            for sp, v in zip(self.spn_margins, new):
                sp.setValue(float(v))
            self._on_margins_changed()
        except Exception:
            exc_note("use_printer_page @ ggis/ui/views/layout/workspace.py:4803")
            pass
        self._msg(_tr("已按打印机中的页面设置：{0}").format(
            name or self.lay.page))

    def _open_page_setup(self):
        try:
            dlg = GgsDialog(self)
            dlg.setWindowTitle(_tr("页面设置"))
            dlg.setModal(True)
            body = QVBoxLayout()
            body.setContentsMargins(20, 16, 20, 14)
            body.setSpacing(10)
            form = QFormLayout()
            cmb_page = QComboBox()
            for nm in PAGE_ORDER:
                if nm in PAGE_SIZES:
                    cmb_page.addItem(self._page_label(nm), nm)
            i = cmb_page.findData(self.lay.page)
            cmb_page.setCurrentIndex(max(0, i))
            cmb_orient = QComboBox()
            cmb_orient.addItem(_tr("横向"), ORIENTATION_LANDSCAPE)
            cmb_orient.addItem(_tr("纵向"), ORIENTATION_PORTRAIT)
            j = cmb_orient.findData(self.lay.orientation)
            cmb_orient.setCurrentIndex(max(0, j))
            cmb_dpi = QComboBox()
            for label, dpi in DPI_CHOICES:
                cmb_dpi.addItem(label, dpi)
            k = cmb_dpi.findData(int(self.lay.dpi or 300))
            cmb_dpi.setCurrentIndex(max(0, k))
            form.addRow(_tr("纸张"), cmb_page)
            form.addRow(_tr("方向"), cmb_orient)
            form.addRow(_tr("分辨率"), cmb_dpi)
            spins = []
            for tag in ("左", "上", "右", "下"):
                sp = QDoubleSpinBox()
                sp.setRange(0.0, 60.0)
                sp.setDecimals(1)
                sp.setSuffix(" mm")
                sp.setValue(0.0)
                spins.append(sp)
            form.addRow(_tr("页边距"),
                        self._stacked(("左", spins[0]), ("上", spins[1]),
                                      ("右", spins[2]), ("下", spins[3]),
                                      width=200))
            for sp, v in zip(spins, self.lay.margins()):
                sp.setValue(float(v))
            body.addLayout(form)
            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel)
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            body.addWidget(btns)
            _host = QWidget()
            _host.setLayout(body)
            dlg.setLayout(_host.layout())
            dlg.setMinimumWidth(420)
            if not dlg.exec():
                return
            self.cmb_page.setCurrentIndex(
                max(0, self.cmb_page.findData(cmb_page.currentData())))
            self.cmb_orient.setCurrentIndex(
                max(0, self.cmb_orient.findData(cmb_orient.currentData())))
            self.cmb_dpi.setCurrentIndex(
                max(0, self.cmb_dpi.findData(cmb_dpi.currentData())))
            for sp, v in zip(self.spn_margins, spins):
                sp.setValue(sp.value() * 0 + float(v.value()))
            self._on_margins_changed()
        except Exception as e:
            _log.exception("页面设置对话框失败")
            self._msg(_tr("页面设置失败：{0}").format(e))

    def _refresh_view_silent(self):
        item = self._current_item()
        if item is not None:
            f = self.view.layout_scene().frame_of(item)
            if f is not None:
                f.sync_from_item()
        self.view.layout_scene().notify_changed()
        if item is not None:
            self.lbl_sel.setText("%s · %s" % (item.label,
                                              item.preview_text()))

    def _msg(self, text):
        try:
            self.lbl_msg.setText(text or "")
        except Exception:
            exc_note("_msg @ ggis/ui/views/layout/workspace.py:4898")
            pass

    def dpi(self):
        try:
            return float(self.cmb_dpi.currentData() or 300)
        except Exception:
            exc_note("dpi @ ggis/ui/views/layout/workspace.py:4907")
            return 300.0

    def export(self, fmt=None):
        lay = self.lay
        lay.dpi = self.dpi()
        if fmt == "print":
            return self.do_print()
        if fmt is None:
            path, _f = GgsFileDialog.getSaveFileName(
                self, _tr("导出图片"), lay.name + ".png",
                "PNG 图片 (*.png);;JPG 图片 (*.jpg);;TIFF 图片 (*.tif)")
        else:
            flt = {"pdf": "PDF (*.pdf)", "svg": "SVG (*.svg)"}[fmt]
            path, _f = GgsFileDialog.getSaveFileName(
                self, _tr("导出") + fmt.upper(),
                "%s.%s" % (lay.name, fmt), flt)
        if not path:
            return None
        r = EX.export_layout(lay, path, self._project, dpi=self.dpi())
        if hasattr(r, "on_done"):
            self._export_task = r
            self._msg(_tr("出图中…"))
            r.on_done(lambda ev: self._finish_export(ev.get("result")))
            r.on_fail(lambda ev: self._msg(
                _tr("出图失败：{0}").format(ev.get("error"))))
            return r
        return self._finish_export(r)

    def _finish_export(self, r):
        self._report(r)
        try:
            self.exported.emit(r)
        except Exception:
            exc_note("_finish_export @ ggis/ui/views/layout/workspace.py:4943")
            pass
        return r

    def do_print(self):
        try:
            from PySide6.QtPrintSupport import (QPrintDialog, QPrinter)
        except Exception as exc:
            exc_note("do_print @ ggis/ui/views/layout/workspace.py:4951")
            self._msg(_tr("打印模块不可用：") + str(exc))
            return None
        try:
            from ggis.main_window import is_headless
            if is_headless():
                self._msg(_tr("无头环境无法弹出打印对话框"))
                return None
        except Exception:
            exc_note("do_print @ ggis/ui/views/layout/workspace.py:4959")
            pass
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        w_mm, h_mm = self.lay.page_mm()
        try:
            printer.setPageSize(QPageSize(
                QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter,
                self.lay.name))
            printer.setPageMargins(QMarginsF(0, 0, 0, 0),
                                   QPageLayout.Unit.Millimeter)
        except Exception:
            exc_note("do_print @ ggis/ui/views/layout/workspace.py:4969")
            pass
        dlg = QPrintDialog(printer, self)
        if not dlg.exec():
            return None
        r = EX.print_layout(self.lay, self._project, printer,
                            dpi=self.dpi())
        self._report(r)
        try:
            self.exported.emit(r)
        except Exception:
            exc_note("do_print @ ggis/ui/views/layout/workspace.py:4979")
            pass
        return r

    def _report(self, r):
        self._msg(r.summary())
        if not r.ok:
            GgsMsgBox.warning(self, _tr("出图失败"), r.error or _tr("未知原因"))
        elif r.warnings:
            GgsMsgBox.information(self, _tr("出图完成"),
                                  "\n".join(r.warnings))

    def select_layout_item(self, index=0):
        self._select_index(index)


    def closeEvent(self, e):
        try:
            self.lay.dpi = self.dpi()
        except Exception:
            exc_note("closeEvent @ ggis/ui/views/layout/workspace.py:5009")
            pass
        try:
            self.view.layout_scene().shutdown()
        except Exception:
            exc_note("closeEvent @ ggis/ui/views/layout/workspace.py:5014")
            pass
        super().closeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            e.accept()
            return
        super().keyPressEvent(e)


class GgsLayoutDialog(GgsDialog):

    exported = Signal(object)

    def __init__(self, project, layout=None, parent=None, dark_bg=True,
                 map_extent=None, map_crs=None, default_dpi=300):
        super().__init__(parent)
        self.setObjectName("GgsLayoutDialogShell")
        self.workspace = GgsLayoutWorkspace(
            project, layout, self, dark_bg=dark_bg, map_extent=map_extent,
            map_crs=map_crs, default_dpi=default_dpi, embedded=False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(0)
        lay.addWidget(self.workspace, 1)
        try:
            self.workspace.exported.connect(self.exported)
        except Exception:
            exc_note("__init__ @ ggis/ui/views/layout/workspace.py:5051")
            pass

    def __getattr__(self, name):
        ws = self.__dict__.get("workspace")
        if ws is not None:
            try:
                return getattr(ws, name)
            except AttributeError:
                exc_note("__getattr__ @ ggis/ui/views/layout/workspace.py:5064")
                pass
        raise AttributeError(name)


__all__ = ["GgsLayoutDialog", "GgsLayoutWorkspace"]


class GgsLayerTreeMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayerTreeMenu")
class GgsLayoutAlignMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutAlignMenu")
class GgsLayoutCanvasMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutCanvasMenu")
class GgsLayoutDistMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutDistMenu")
class GgsLayoutExport(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutExport")
class GgsLayoutMapViewMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutMapViewMenu")
class GgsLayoutPropsScroll(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutPropsScroll")
class GgsLayoutSelLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutSelLabel")
class GgsLayoutSelTypeMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutSelTypeMenu")
class GgsLayoutStatus(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutStatus")
class GgsLayoutStatusSep(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutStatusSep")
class GgsLayoutZoom(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsLayoutZoom")
class GgsRibbonMini(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonMini")
