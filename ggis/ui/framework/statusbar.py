# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QSize, QTimer, Signal, QEvent, QPoint
from PySide6.QtWidgets import (QStatusBar, QLabel, QToolButton, QMenu,
                               QWidget, QHBoxLayout,
                               QComboBox, QSizePolicy, QTabBar, QFrame)
from PySide6.QtGui import QActionGroup

from ggis.common.styling import icons
from ggis.core.app import i18n
from ggis.common.widgets.inputs import GgsComboBox
from ggis.common.widgets.displays import GgsRenderStatus
from ggis.common.base.dialog import GgsDockTitleBtn
from ggis.common.widgets.buttons import GgsSmallButtonStyle1, GgsSmallButtonStyle2

_tr = i18n.tr

STATUS_H = 24
from ggis.common.widgets.buttons import STATUS_CTRL_H
from PySide6.QtWidgets import QProgressBar
TAB_ICON_SIZE = 16

COMMON_SCALES = (500, 1000, 2000, 5000, 10000, 25000,
                 50000, 100000, 250000, 500000, 1000000)


def _scale_text(denom):
    d = float(denom)
    if d < 1.0:
        d = 1.0
    return "1:{:.0f}".format(d)


def _parse_scale(text):
    s = str(text or "").strip().replace(",", "").replace(" ", "")
    if not s:
        return 0.0
    s = s.replace("：", ":").replace("/", ":").replace("／", ":")
    if ":" in s:
        parts = [p for p in s.split(":") if p]
        s = parts[-1] if parts else ""
    try:
        d = float(s)
    except Exception:
        exc_note("_parse_scale @ ggis/ui/framework/statusbar.py:84")
        return 0.0
    if not (d > 0) or d != d or d in (float("inf"),):
        return 0.0
    return d


def _on_render_status_clicked(view, state):
    cv = getattr(view, "canvas", None)
    if cv is None:
        return
    try:
        if not view.has_layers():
            return
    except Exception:
        exc_note("_on_render_status_clicked @ ggis/ui/framework/statusbar.py:114")
        pass
    lbl = getattr(view, "lbl_render", None)
    try:
        if str(state) == "busy":
            fn = getattr(cv, "stop_render", None)
            if callable(fn):
                fn()
            if lbl is not None:
                lbl.set_done()
        else:
            if lbl is not None:
                lbl.set_busy()
            fn = getattr(cv, "rerender", None)
            if callable(fn):
                fn()
    except Exception:
        exc_note("_on_render_status_clicked @ ggis/ui/framework/statusbar.py:130")
        pass


def _status_vsep(parent=None):
    try:
        f = QFrame(parent)
        f.setObjectName("GgsStatusSep")
        f.setFrameShape(QFrame.Shape.NoFrame)
        f.setLineWidth(0)
        f.setFixedWidth(7)
        f.setSizePolicy(QSizePolicy.Policy.Fixed,
                        QSizePolicy.Policy.Expanding)
        f.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        f.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return f
    except Exception:
        exc_note("_status_vsep @ ggis/ui/framework/statusbar.py:152")
        return QWidget(parent)


class _StatusSepWrap(QWidget):

    def __init__(self, child, parent=None, left_sibling=None):
        super().__init__(parent)
        self._sep_child = child
        self._sep_left = left_sibling
        self._sep = None
        self._sep_suppressed = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._sep = _status_vsep(self)
        lay.addWidget(self._sep)
        if child is not None:
            lay.addWidget(child, 1)
            try:
                child.installEventFilter(self)
            except Exception:
                exc_note("__init__ @ ggis/ui/framework/statusbar.py:196")
                pass
        try:
            self.setSizePolicy(QSizePolicy.Policy.Maximum,
                               QSizePolicy.Policy.Preferred)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/statusbar.py:208")
            pass
        try:
            self.setVisible(False)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/statusbar.py:213")
            pass

    def set_left_sibling(self, w):
        self._sep_left = w
        self._update()

    @staticmethod
    def _shown(w):
        if w is None:
            return False
        try:
            return not w.isHidden()
        except Exception:
            exc_note("_shown @ ggis/ui/framework/statusbar.py:227")
            return False

    def set_suppressed(self, on):
        self._sep_suppressed = bool(on)
        self._update()

    def _update(self):
        try:
            if self._sep_suppressed:
                self.setVisible(False)
                if self._sep is not None:
                    self._sep.setVisible(False)
                return
            self.setVisible(self._shown(self._sep_child))
            if self._sep is not None:
                self._sep.setVisible(
                    self._shown(self._sep_child) and self._shown(self._sep_left))
        except Exception:
            exc_note("_update @ ggis/ui/framework/statusbar.py:259")
            pass

    def eventFilter(self, obj, ev):
        try:
            if obj is self._sep_child and ev.type() in (
                    QEvent.Type.Show, QEvent.Type.Hide):
                self._update()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/statusbar.py:267")
            pass
        return super().eventFilter(obj, ev)




def build_map_status_controls(view):
    _init_view_status_state(view)


def ensure_status_controls(view):
    if getattr(view, "_status_ctrl_bound", False):
        return
    host = getattr(view, "_host", None)
    ctrl = getattr(host, "_status_ctrl", None) if host is not None else None
    if ctrl is None:
        ctrl = _new_status_controls(host if host is not None else view)
        if host is not None:
            host._status_ctrl = ctrl
    _bind_status_controls(view, ctrl)


def _new_status_controls(owner):
    import types as _types
    ns = _types.SimpleNamespace()
    ns.owner = owner
    coords_label = GgsCoordsValue("—, —")
    coords_label.setFixedHeight(STATUS_CTRL_H)
    coords_label.setAlignment(Qt.AlignmentFlag.AlignLeft |
                              Qt.AlignmentFlag.AlignVCenter)
    coords_label.setToolTip(_tr("XY 坐标"))

    left_w = QWidget(owner)
    left_lay = QHBoxLayout(left_w)
    left_lay.setContentsMargins(0, 0, 0, 0)
    left_lay.setSpacing(2)

    lbl_render = GgsRenderStatus("")
    lbl_render.setFixedHeight(STATUS_CTRL_H)
    lbl_render.setVisible(True)
    lbl_render.clicked.connect(
        lambda st, h=owner: _on_render_status_clicked(
            (getattr(h, "current_map_view", None) or (lambda: None))(), st))

    btn_coord_fmt = GgsSmallButtonStyle1(
        "chevron_down", _tr("坐标显示格式"), size=14, parent=owner)
    btn_coord_fmt.setFixedHeight(STATUS_CTRL_H)
    btn_coord_fmt.setAutoRaise(True)
    btn_coord_fmt.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_coord_fmt.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu_fmt = QMenu(btn_coord_fmt)
    grp_fmt = QActionGroup(menu_fmt)
    ns.coord_fmt_actions = {}
    for text, data in ((_tr("地图坐标"), "map"), (_tr("十进制度"), "decdeg"),
                       (_tr("度分"), "dm"), (_tr("度分秒"), "dms")):
        a = menu_fmt.addAction(text)
        a.setCheckable(True)
        a.setChecked(data == "map")
        grp_fmt.addAction(a)
        ns.coord_fmt_actions[data] = a
        a.triggered.connect(
            lambda _c=False, d=data, h=owner:
            (getattr(h, "_set_coord_fmt", None)
             and h._set_coord_fmt(d)))
    btn_coord_fmt.setMenu(menu_fmt)
    left_lay.addWidget(coords_label)
    left_lay.insertWidget(1, btn_coord_fmt)

    progress = GgsStatusProgress(owner)
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setFixedWidth(120)
    progress.setFixedHeight(STATUS_CTRL_H - 4)
    progress.setVisible(False)
    progress.setProperty("ggs_autohide", True)

    lbl_scale = GgsStatusScaleLabel(_tr("比例"), owner)
    lbl_scale.setFixedHeight(STATUS_CTRL_H)

    cmb_scale = GgsComboBox(owner)
    cmb_scale.setObjectName("GgsStatusScale")
    cmb_scale.setFixedHeight(STATUS_CTRL_H)
    cmb_scale.setEditable(True)
    try:
        cmb_scale.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:434")
        pass
    cmb_scale.setToolTip(_tr(
        "当前比例尺（1:N）。可挑选常见比例，也可直接输入（如 1:25000）"))
    cmb_scale.addItems([_scale_text(d) for d in COMMON_SCALES])
    try:
        _fm = cmb_scale.fontMetrics()
        _longest = int(max(_fm.horizontalAdvance(_scale_text(d))
                           for d in COMMON_SCALES))
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:443")
        _longest = 80
    try:
        cmb_scale.setMinimumWidth(_longest + 24 + 6 + 18 + 4)
        cmb_scale.view().setMinimumWidth(_longest + 24 + 6 + 18 + 4)
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:448")
        pass
    try:
        cmb_scale.setMaxVisibleItems(len(COMMON_SCALES))
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:452")
        pass
    cmb_scale.setCurrentIndex(-1)
    try:
        cmb_scale.lineEdit().setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:458")
        pass
    try:
        cmb_scale.textActivated.connect(
            lambda _t, h=owner:
            (getattr(h, "_apply_typed_scale", None)
             and h._apply_typed_scale()))
        cmb_scale.lineEdit().returnPressed.connect(
            lambda h=owner:
            (getattr(h, "_apply_typed_scale", None)
             and h._apply_typed_scale()))
        cmb_scale.lineEdit().editingFinished.connect(
            lambda h=owner:
            (getattr(h, "_apply_typed_scale", None)
             and h._apply_typed_scale()))
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:473")
        pass

    btn_scale_lock = GgsStatusScaleLock(owner)
    btn_scale_lock.setCheckable(True)
    btn_scale_lock.setFixedSize(QSize(20, 20))
    btn_scale_lock.setAutoRaise(True)
    btn_scale_lock.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn_scale_lock.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_scale_lock.setToolTip(_tr(
        "锁定比例：开启后滚轮与缩放工具都不再改变比例（平移不受影响）"))
    try:
        btn_scale_lock.toggled.connect(
            lambda on, h=owner:
            (getattr(h, "_on_scale_lock_toggled", None)
             and h._on_scale_lock_toggled(on)))
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:491")
        pass
    try:
        icons.bind(btn_scale_lock, "lock_open", size=14)
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:495")
        try:
            btn_scale_lock.setIcon(icons.icon("lock_open", size=14))
        except Exception:
            exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:498")
            pass
    try:
        btn_scale_lock.setIconSize(QSize(14, 14))
    except Exception:
        exc_note("_new_status_controls @ ggis/ui/framework/statusbar.py:502")
        pass

    scale_info = QWidget(owner)
    _sc_lay = QHBoxLayout(scale_info)
    _sc_lay.setContentsMargins(0, 0, 0, 0)
    _sc_lay.setSpacing(2)
    _sc_lay.addWidget(lbl_scale)
    _sc_lay.addWidget(cmb_scale)
    _sc_lay.addWidget(btn_scale_lock)

    btn_crs = GgsSmallButtonStyle2(
        "crs_disabled", "EPSG:——", _tr("点击：设置底图坐标系"),
        size=16, parent=owner)
    btn_crs.setFixedHeight(STATUS_CTRL_H)
    btn_crs.clicked.connect(
        lambda _c=False, h=owner:
        (getattr(h, "choose_project_crs", None)
         and h.choose_project_crs()))

    ns.coords_label = coords_label
    ns.lbl_render = lbl_render
    ns.left_info = left_w
    ns.btn_coord_fmt = btn_coord_fmt
    ns.progress = progress
    ns.lbl_scale = lbl_scale
    ns.cmb_scale = cmb_scale
    ns.btn_scale_lock = btn_scale_lock
    ns.scale_info = scale_info
    ns.btn_crs = btn_crs
    _left_wrap = _StatusSepWrap(left_w, owner)
    _render_wrap = _StatusSepWrap(lbl_render, owner)
    _scale_wrap = _StatusSepWrap(scale_info, owner)
    _btn_crs_wrap = _StatusSepWrap(btn_crs, owner)
    ns.widgets = [_left_wrap, _render_wrap, _scale_wrap, _btn_crs_wrap]
    return ns


def _bind_status_controls(view, ns):
    for _n in ("coords_label", "lbl_render", "left_info", "btn_coord_fmt",
               "progress", "lbl_scale", "cmb_scale", "btn_scale_lock",
               "scale_info", "btn_crs"):
        setattr(view, _n, getattr(ns, _n, None))
    view._status_widgets = list(getattr(ns, "widgets", []) or [])
    _init_view_status_state(view)
    view._status_ctrl_bound = True


def _init_view_status_state(view):
    view._coord_fmt = "map"
    view._scale_cur = None
    view._last_xy = None
    view._render_busy = False
    view._loading = False
    if getattr(view, "_render_hide_timer", None) is not None:
        return
    try:
        view._render_hide_timer = QTimer(view)
        view._render_hide_timer.setSingleShot(True)
        view._render_hide_timer.timeout.connect(
            lambda *_, v=view:
            (getattr(getattr(v, "_host", None),
                     "_render_idle_for_view", None)
             and v._host._render_idle_for_view(v)))
    except Exception:
        exc_note("_init_view_status_state @ ggis/ui/framework/statusbar.py:606")
        view._render_hide_timer = None


class GgsStatusBar(QStatusBar):


    def __init__(self, parent=None):
        super().__init__(parent)
        self._left_children = []
        self._right_children = []
        self._sep_refreshing = False

    def addWidget(self, widget, *args, **kwargs):
        super().addWidget(widget, *args, **kwargs)
        if widget not in self._left_children:
            self._left_children.append(widget)
        try:
            widget.installEventFilter(self)
        except Exception:
            exc_note("addWidget @ ggis/ui/framework/statusbar.py:640")
            pass
        self._refresh_seps()
        return widget

    def addPermanentWidget(self, widget, *args, **kwargs):
        super().addPermanentWidget(widget, *args, **kwargs)
        if widget not in self._right_children:
            self._right_children.append(widget)
        try:
            widget.installEventFilter(self)
        except Exception:
            exc_note("addPermanentWidget @ ggis/ui/framework/statusbar.py:651")
            pass
        self._refresh_seps()
        return widget

    def removeWidget(self, widget):
        super().removeWidget(widget)
        for _lst in (self._left_children, self._right_children):
            if widget in _lst:
                try:
                    _lst.remove(widget)
                except Exception:
                    exc_note("removeWidget @ ggis/ui/framework/statusbar.py:662")
                    pass
        try:
            widget.removeEventFilter(self)
        except Exception:
            exc_note("removeWidget @ ggis/ui/framework/statusbar.py:666")
            pass
        self._refresh_seps()

    def eventFilter(self, obj, ev):
        try:
            if ev.type() in (QEvent.Type.Show, QEvent.Type.Hide):
                if obj in self._left_children or obj in self._right_children:
                    self._refresh_seps()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/statusbar.py:675")
            pass
        return super().eventFilter(obj, ev)

    def _refresh_seps(self):
        if self._sep_refreshing:
            return
        self._sep_refreshing = True
        try:
            for _lst in (self._left_children, self._right_children):
                _lst[:] = [w for w in _lst
                           if w is not None and w.parent() is self]
            for _lst in (self._left_children, self._right_children):
                _prev = None
                for _w in _lst:
                    _wrap = _w if isinstance(_w, _StatusSepWrap) else None
                    if _wrap is not None:
                        _wrap.set_left_sibling(_prev)
                    try:
                        _vis = not _w.isHidden()
                    except Exception:
                        exc_note("_refresh_seps @ ggis/ui/framework/statusbar.py:708")
                        _vis = False
                    if _vis:
                        _prev = _w
        finally:
            self._sep_refreshing = False

    def showEvent(self, e):
        try:
            self._refresh_seps()
        except Exception:
            exc_note("showEvent @ ggis/ui/framework/statusbar.py:719")
            pass
        super().showEvent(e)



class _ViewTabBar(QTabBar):

    hoveredChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._hov = -1

    def sizeHint(self):
        # QTabBar 内建行为坑（R-X79 定位）：条子一旦被压窄（装载期宿主
        # 窗口未显示、默认宽 ~100px），它会内部滚动"保当前页签可见"——
        # 非当前页签被滚到 x<0 不可见，且此后 sizeHint 锁死成"可见页签
        # 之和"，布局层永远只给一条页签的宽度，其它页签再也回不来。
        # 本控件宿主是整宽条子，直接声明全部页签总宽：布局层给足宽度，
        # 内部滚动根本不发生。
        w = 0
        h = 0
        try:
            for i in range(self.count()):
                s = self.tabSizeHint(i)
                w += int(s.width())
                h = max(h, int(s.height()))
        except Exception:
            exc_note("sizeHint @ ggis/ui/framework/statusbar.py:_ViewTabBar")
            return super().sizeHint()
        return QSize(w + 2, h)

    def minimumSizeHint(self):
        return self.sizeHint()

    def _sync_hover(self, pos):
        try:
            i = int(self.tabAt(pos))
        except Exception:
            exc_note("_sync_hover @ ggis/ui/framework/statusbar.py:809")
            return
        if i != self._hov:
            self._hov = i
            self.hoveredChanged.emit(i)

    def mouseMoveEvent(self, e):
        try:
            self._sync_hover(e.position().toPoint())
        except Exception:
            exc_note("mouseMoveEvent @ ggis/ui/framework/statusbar.py:818")
            pass
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hov != -1:
            self._hov = -1
            self.hoveredChanged.emit(-1)
        super().leaveEvent(e)


class GgsViewTabs(QWidget):

    viewRequested = Signal(str)
    createRequested = Signal(str)
    closeRequested = Signal(str)
    closeOthersRequested = Signal(str)
    closeAllRequested = Signal()
    renameRequested = Signal(str)
    propsRequested = Signal(str)
    orderChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsViewTabs")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 4, 0)
        lay.setSpacing(2)
        self._tab_h = 0
        try:
            from ggis.ui.framework.docks import title_bar_height
            self._tab_h = int(title_bar_height(self))
            self.setFixedHeight(self._tab_h)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/statusbar.py:914")
            self._tab_h = int(STATUS_CTRL_H) + 8
            self.setFixedHeight(self._tab_h)
        self._lay = lay
        self._items = []
        self._cur = ""
        self._icons = {}

        self.tabs = _ViewTabBar(self)
        self.tabs.setObjectName("GgsViewTabBar")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setIconSize(QSize(TAB_ICON_SIZE, TAB_ICON_SIZE))
        self.tabs.setMovable(True)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tabs.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.currentChanged.connect(self._on_current)
        self.tabs.tabBarDoubleClicked.connect(self._on_dbl)
        self.tabs.customContextMenuRequested.connect(self._on_ctx)
        self.tabs.tabMoved.connect(self._on_tab_moved)
        self._hover_i = -1
        self._syncing = False
        self.tabs.hoveredChanged.connect(self._on_tab_hovered)
        lay.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignVCenter)

        self.btn_new = GgsSmallButtonStyle1(
            "plus", _tr("新建视图"), size=14, parent=self)
        self.btn_new.setAutoRaise(True)
        self.btn_new.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setFixedSize(QSize(20, 20))
        self._menu_new = QMenu(self.btn_new)
        self._menu_new.aboutToShow.connect(self._fill_new_menu)
        self.btn_new.setMenu(self._menu_new)
        self.btn_new.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        lay.addWidget(self.btn_new, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addStretch(1)

    def _sync_height(self):
        try:
            from ggis.ui.framework.docks import sync_title_bar_height
            sync_title_bar_height(self, "_tab_h")
        except Exception:
            exc_note("_sync_height @ ggis/ui/framework/statusbar.py:1014")
            pass

    def changeEvent(self, e):
        try:
            if e.type() in (QEvent.Type.FontChange,
                            QEvent.Type.ApplicationFontChange):
                self._sync_height()
        except Exception:
            exc_note("changeEvent @ ggis/ui/framework/statusbar.py:1022")
            pass
        super().changeEvent(e)

    def showEvent(self, e):
        try:
            self._sync_height()
        except Exception:
            exc_note("showEvent @ ggis/ui/framework/statusbar.py:1029")
            pass
        super().showEvent(e)

    def _icon_for(self, name):
        try:
            sz = int(self.tabs.iconSize().width())
        except Exception:
            exc_note("_icon_for @ ggis/ui/framework/statusbar.py:1044")
            sz = int(TAB_ICON_SIZE)
        if sz <= 0:
            sz = int(TAB_ICON_SIZE)
        try:
            ic = icons.icon(str(name), size=sz)
            if ic is not None and not ic.isNull():
                return ic
        except Exception:
            exc_note("_icon_for @ ggis/ui/framework/statusbar.py:1052")
            pass
        return None

    def _mk_close(self, vid):
        b = GgsDockTitleBtn(self.tabs)
        b.setAutoRaise(True)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip(_tr("关闭视图"))
        try:
            icons.bind(b, "dock_close", size=14)
        except Exception:
            exc_note("_mk_close @ ggis/ui/framework/statusbar.py:1091")
            b.setText("✕")
        b.setFixedSize(QSize(20, 20))
        try:
            _sz = 14
        except Exception:
            exc_note("_mk_close @ ggis/ui/framework/statusbar.py:1098")
            _sz = 14
        try:
            b.setIconSize(QSize(_sz, _sz))
        except Exception:
            exc_note("_mk_close @ ggis/ui/framework/statusbar.py:1102")
            pass
        b.clicked.connect(
            lambda _c=False, v=str(vid): self.closeRequested.emit(str(v)))
        return b

    @staticmethod
    def _close_holder(btn, gap=6):
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, int(gap), 0)
        h.setSpacing(0)
        try:
            btn.setParent(box)
        except Exception:
            exc_note("_close_holder @ ggis/ui/framework/statusbar.py:1141")
            pass
        h.addWidget(btn)
        return box

    def _close_button(self, i):
        try:
            w = self.tabs.tabButton(i, QTabBar.ButtonPosition.RightSide)
        except Exception:
            exc_note("_close_button @ ggis/ui/framework/statusbar.py:1150")
            return None
        if w is None:
            return None
        if isinstance(w, QToolButton):
            return w
        try:
            return w.findChild(QToolButton)
        except Exception:
            exc_note("_close_button @ ggis/ui/framework/statusbar.py:1158")
            return None

    def _on_tab_hovered(self, index):
        try:
            self._hover_i = int(index)
        except Exception:
            exc_note("_on_tab_hovered @ ggis/ui/framework/statusbar.py:1165")
            self._hover_i = -1
        self._sync_close_buttons()

    def _sync_close_buttons(self):
        if getattr(self, "_syncing", False):
            return
        try:
            cur = int(self.tabs.currentIndex())
            hov = int(getattr(self, "_hover_i", -1))
            for i in range(self.tabs.count()):
                b = self._close_button(i)
                if b is None:
                    continue
                b.setVisible(i == cur or i == hov)
        except Exception:
            exc_note("_sync_close_buttons @ ggis/ui/framework/statusbar.py:1190")
            pass

    def _on_tab_moved(self, _frm, _to):
        if getattr(self, "_syncing", False):
            return
        ids = []
        try:
            for i in range(self.tabs.count()):
                ids.append(str(self.tabs.tabData(i)))
        except Exception:
            exc_note("_on_tab_moved @ ggis/ui/framework/statusbar.py:1201")
            return
        by_id = {}
        for vid, title, closable, icon_name in self._items:
            by_id.setdefault(str(vid), (vid, title, closable, icon_name))
        self._items = [by_id[v] for v in ids if v in by_id] or list(self._items)
        try:
            self.orderChanged.emit(ids)
        except Exception:
            exc_note("_on_tab_moved @ ggis/ui/framework/statusbar.py:1210")
            pass
        self._sync_close_buttons()

    def retheme(self):
        try:
            for i in range(self.tabs.count()):
                nm = self._icons.get(str(self.tabs.tabData(i)))
                if nm:
                    ic = self._icon_for(nm)
                    if ic is not None:
                        self.tabs.setTabIcon(i, ic)
        except Exception:
            exc_note("retheme @ ggis/ui/framework/statusbar.py:1223")
            pass

    def set_views(self, items, current_id):
        self._items = list(items or [])
        self._cur = str(current_id or "")
        self._icons = {}
        tb = self.tabs
        tb.blockSignals(True)
        self._syncing = True
        try:
            while tb.count():
                tb.removeTab(0)
            for vid, title, closable, icon_name in self._items:
                svid = str(vid)
                i = tb.addTab(str(title))
                tb.setTabData(i, svid)
                if icon_name:
                    self._icons[svid] = str(icon_name)
                    ic = self._icon_for(str(icon_name))
                    if ic is not None:
                        tb.setTabIcon(i, ic)
                if closable:
                    tb.setTabButton(
                        i, QTabBar.ButtonPosition.RightSide,
                        self._close_holder(self._mk_close(svid)))
            j = 0
            for i in range(tb.count()):
                if str(tb.tabData(i)) == self._cur:
                    j = i
                    break
            tb.setCurrentIndex(j)
        finally:
            tb.blockSignals(False)
            self._syncing = False
        # QTabBar 增删页签只重排自身内部布局，不触发宿主布局重算——
        # 宿主（本条子）布局项的 sizeHint 缓存会滞留在上一次页签数上：
        # 装载期先同步 1 视图（缓存=1 页签宽）再同步 2 视图，条子被
        # 永久锁在 1 页签宽度，QTabBar 内部滚动把其它页签藏到 x<0
        # （R-X79 "只显示一个标签"）。这里强制失效并立即重算。
        tb.updateGeometry()
        _lay = self.layout()
        if _lay is not None:
            _lay.invalidate()
            _lay.activate()
        self._sync_close_buttons()

    def current_id(self):
        return self._cur

    def _on_current(self, i):
        try:
            vid = str(self.tabs.tabData(int(i)))
        except Exception:
            exc_note("_on_current @ ggis/ui/framework/statusbar.py:1288")
            return
        self._sync_close_buttons()
        if vid and vid != self._cur:
            self._cur = vid
            self.viewRequested.emit(vid)

    def _on_dbl(self, i):
        try:
            vid = str(self.tabs.tabData(int(i)))
        except Exception:
            exc_note("_on_dbl @ ggis/ui/framework/statusbar.py:1300")
            return
        if vid:
            self.renameRequested.emit(vid)

    def _on_ctx(self, pos):
        try:
            i = int(self.tabs.tabAt(pos))
        except Exception:
            exc_note("_on_ctx @ ggis/ui/framework/statusbar.py:1309")
            return
        if i < 0:
            return
        try:
            vid = str(self.tabs.tabData(i))
        except Exception:
            exc_note("_on_ctx @ ggis/ui/framework/statusbar.py:1315")
            return
        if vid:
            self._on_menu(vid, self.tabs.mapToGlobal(pos))

    def _fill_new_menu(self):
        m = self._menu_new
        m.clear()
        try:
            m.addSection(_tr("新建视图"))
        except Exception:
            exc_note("_fill_new_menu @ ggis/ui/framework/statusbar.py:1336")
            pass
        for icon_name, label, kind in (
                ("map_street", _tr("新建地图"), "map"),
                ("layout", _tr("新建布局"), "layout"),
                ("model", _tr("新建模型构建器"), "model")):
            ic = None
            try:
                ic = icons.icon(icon_name, size=16)
            except Exception:
                exc_note("_fill_new_menu @ ggis/ui/framework/statusbar.py:1354")
                ic = None
            self._menu_action(
                m, ic, label,
                lambda _c=False, k=kind: self.createRequested.emit(str(k)))

    def _is_closable(self, vid):
        for v, _t, c, _i in self._items:
            if v == vid:
                return bool(c)
        return False

    def _build_tab_menu(self, vid):
        m = QMenu(self)
        ic_close = None
        ic_props = None
        ic_all = None
        try:
            ic_close = icons.icon("cancel", size=16)
            ic_props = icons.icon("info", size=16)
            ic_all = icons.icon("clear", size=16)
        except Exception:
            exc_note("_build_tab_menu @ ggis/ui/framework/statusbar.py:1389")
            ic_close = ic_props = ic_all = None
        a_close = self._menu_action(
            m, ic_close, _tr("关闭视图"),
            lambda: self.closeRequested.emit(vid))
        a_close.setEnabled(self._is_closable(vid))
        a_all = self._menu_action(
            m, ic_all, _tr("关闭其他视图"),
            lambda: self.closeOthersRequested.emit(str(vid)))
        a_all.setEnabled(len(self._items) > 1)
        self._menu_action(
            m, ic_props, _tr("视图属性…"),
            lambda: self.propsRequested.emit(vid))
        return m

    @staticmethod
    def _menu_action(menu, icon, text, slot):
        try:
            if icon is not None and not icon.isNull():
                return menu.addAction(icon, str(text), slot)
        except Exception:
            exc_note("_menu_action @ ggis/ui/framework/statusbar.py:1416")
            pass
        return menu.addAction(str(text), slot)

    def _on_menu(self, vid, gpos):
        try:
            self._build_tab_menu(vid).exec(gpos)
        except Exception:
            exc_note("_on_menu @ ggis/ui/framework/statusbar.py:1431")
            pass


class StatusbarMixin:

    def _cmv(self):
        fn = getattr(self, "current_map_view", None)
        if not callable(fn):
            return None
        try:
            return fn()
        except Exception:
            exc_note("_cmv @ ggis/ui/framework/statusbar.py:1455")
            return None

    @property
    def coords_label(self):
        mv = self._cmv()
        return getattr(mv, "coords_label", None) if mv is not None else None

    @property
    def lbl_render(self):
        mv = self._cmv()
        return getattr(mv, "lbl_render", None) if mv is not None else None

    @property
    def btn_coord_fmt(self):
        mv = self._cmv()
        return getattr(mv, "btn_coord_fmt", None) if mv is not None else None

    @property
    def progress(self):
        mv = self._cmv()
        return getattr(mv, "progress", None) if mv is not None else None

    @property
    def lbl_scale(self):
        mv = self._cmv()
        return getattr(mv, "lbl_scale", None) if mv is not None else None

    @property
    def cmb_scale(self):
        mv = self._cmv()
        return getattr(mv, "cmb_scale", None) if mv is not None else None

    @property
    def btn_scale_lock(self):
        mv = self._cmv()
        return getattr(mv, "btn_scale_lock", None) if mv is not None else None

    @property
    def scale_info(self):
        mv = self._cmv()
        return getattr(mv, "scale_info", None) if mv is not None else None

    @property
    def btn_crs(self):
        mv = self._cmv()
        return getattr(mv, "btn_crs", None) if mv is not None else None

    @property
    def left_info(self):
        mv = self._cmv()
        return getattr(mv, "left_info", None) if mv is not None else None

    @property
    def _render_hide_timer(self):
        mv = self._cmv()
        return getattr(mv, "_render_hide_timer", None) if mv is not None else None

    @property
    def _coord_fmt(self):
        mv = self._cmv()
        return getattr(mv, "_coord_fmt", None) if mv is not None else None

    @_coord_fmt.setter
    def _coord_fmt(self, v):
        mv = self._cmv()
        if mv is not None:
            mv._coord_fmt = v

    @property
    def _scale_cur(self):
        mv = self._cmv()
        return getattr(mv, "_scale_cur", None) if mv is not None else None

    @_scale_cur.setter
    def _scale_cur(self, v):
        mv = self._cmv()
        if mv is not None:
            mv._scale_cur = v

    @property
    def _last_xy(self):
        mv = self._cmv()
        return getattr(mv, "_last_xy", None) if mv is not None else None

    @_last_xy.setter
    def _last_xy(self, v):
        mv = self._cmv()
        if mv is not None:
            mv._last_xy = v

    @property
    def _render_busy(self):
        mv = self._cmv()
        return bool(getattr(mv, "_render_busy", False)) \
            if mv is not None else False

    @_render_busy.setter
    def _render_busy(self, v):
        mv = self._cmv()
        if mv is not None:
            mv._render_busy = bool(v)

    @property
    def _loading(self):
        mv = self._cmv()
        return bool(getattr(mv, "_loading", False)) \
            if mv is not None else False

    @_loading.setter
    def _loading(self, v):
        mv = self._cmv()
        if mv is not None:
            mv._loading = bool(v)

    def _render_idle_for_view(self, view):
        try:
            tm = getattr(view, "_render_hide_timer", None)
            if tm is not None:
                tm.stop()
        except Exception:
            exc_note("_render_idle_for_view @ ggis/ui/framework/statusbar.py:1584")
            pass
        try:
            view._render_busy = False
        except Exception:
            exc_note("_render_idle_for_view @ ggis/ui/framework/statusbar.py:1588")
            pass
        try:
            if self._cmv() is not view:
                return
        except Exception:
            exc_note("_render_idle_for_view @ ggis/ui/framework/statusbar.py:1594")
            pass
        try:
            p = getattr(view, "progress", None)
            if p is not None and not getattr(view, "_loading", False):
                p.setTextVisible(True)
                p.setRange(0, 100)
                p.setValue(0)
                p.setVisible(False)
        except Exception:
            exc_note("_render_idle_for_view @ ggis/ui/framework/statusbar.py:1603")
            pass
        try:
            lbl = getattr(view, "lbl_render", None)
            if lbl is not None:
                if str(getattr(lbl, "state", lambda: "")()) == "busy":
                    lbl.set_done()
        except Exception:
            exc_note("_render_idle_for_view @ ggis/ui/framework/statusbar.py:1613")
            pass

    def _build_statusbar(self):
        sb = GgsStatusBar(self)
        sb.setObjectName("GgsStatusBar")
        sb.setSizeGripEnabled(False)
        sb.setFixedHeight(STATUS_H + 2)
        self.setStatusBar(sb)

        self.lbl_lay_page = GgsStatusLayout("")
        self.lbl_lay_page.setFixedHeight(STATUS_CTRL_H)
        sb.addWidget(_StatusSepWrap(self.lbl_lay_page, sb))

        self.lbl_lay_sel = GgsStatusLayout("")
        self.lbl_lay_sel.setFixedHeight(STATUS_CTRL_H)
        sb.addWidget(_StatusSepWrap(self.lbl_lay_sel, sb))

        self.lbl_lay_zoom = GgsStatusScaleLabel(_tr("缩放"))
        self.lbl_lay_zoom.setFixedHeight(STATUS_CTRL_H)
        sb.addPermanentWidget(_StatusSepWrap(self.lbl_lay_zoom, sb))

        _ZOOM_STEPS = (25, 50, 75, 100, 150, 200, 400, 800)
        self.cmb_lay_zoom = GgsStatusLayoutZoom()
        self.cmb_lay_zoom.setFixedHeight(STATUS_CTRL_H)
        self.cmb_lay_zoom.setEditable(True)
        try:
            self.cmb_lay_zoom.setInsertPolicy(
                QComboBox.InsertPolicy.NoInsert)
        except Exception:
            exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1709")
            pass
        self.cmb_lay_zoom.setToolTip(_tr(
            "画布缩放（100% 为实际尺寸）。可挑选，也可直接输入（如 150%）"))
        for _pct in _ZOOM_STEPS:
            self.cmb_lay_zoom.addItem("%d%%" % _pct, _pct / 100.0)
        try:
            _fm = self.cmb_lay_zoom.fontMetrics()
            _longest = int(max(_fm.horizontalAdvance("%d%%" % _p)
                               for _p in _ZOOM_STEPS))
        except Exception:
            exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1722")
            _longest = 48
        try:
            self.cmb_lay_zoom.setMinimumWidth(_longest + 24 + 6 + 18 + 4)
            self.cmb_lay_zoom.view().setMinimumWidth(_longest + 24 + 6 + 4)
        except Exception:
            exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1727")
            pass
        try:
            self.cmb_lay_zoom.setMaxVisibleItems(len(_ZOOM_STEPS))
        except Exception:
            exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1731")
            pass
        try:
            self.cmb_lay_zoom.lineEdit().setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        except Exception:
            exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1737")
            pass
        try:
            self.cmb_lay_zoom.textActivated.connect(
                lambda _t: self._on_lay_zoom_typed())
            self.cmb_lay_zoom.lineEdit().returnPressed.connect(
                self._on_lay_zoom_typed)
            self.cmb_lay_zoom.lineEdit().editingFinished.connect(
                self._on_lay_zoom_typed)
        except Exception:
            exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1749")
            pass
        sb.addPermanentWidget(_StatusSepWrap(self.cmb_lay_zoom, sb))

        self.btn_lay_export = GgsStatusLayoutExport()
        self.btn_lay_export.setText(_tr("导出"))
        self.btn_lay_export.setToolTip(_tr("导出") + " / " + _tr("打印"))
        self.btn_lay_export.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_lay_export.setFixedHeight(STATUS_CTRL_H)
        _m_exp = QMenu(self.btn_lay_export)
        for _label, _fmt in ((_tr("导出 PDF"), "pdf"),
                             (_tr("导出 SVG"), "svg"),
                             (_tr("导出图片"), None),
                             (_tr("打印…"), "print")):
            _a = _m_exp.addAction(_label)
            _a.triggered.connect(
                lambda _c=False, f=_fmt: self._on_lay_export(f))
        self.btn_lay_export.setMenu(_m_exp)
        sb.addPermanentWidget(_StatusSepWrap(self.btn_lay_export, sb))

        self.lbl_model_stage = GgsStatusLayout("")
        self.lbl_model_stage.setFixedHeight(STATUS_CTRL_H)
        sb.addWidget(_StatusSepWrap(self.lbl_model_stage, sb))
        self.bar_model = GgsStatusProgress()
        self.bar_model.setRange(0, 100)
        self.bar_model.setFixedHeight(STATUS_CTRL_H)
        self.bar_model.setMaximumWidth(180)
        sb.addPermanentWidget(_StatusSepWrap(self.bar_model, sb))

        for _w in (self.lbl_lay_page, self.lbl_lay_sel,
                   self.lbl_lay_zoom, self.cmb_lay_zoom,
                   self.btn_lay_export, self.lbl_model_stage,
                   self.bar_model):
            try:
                _w.setVisible(False)
            except Exception:
                exc_note("_build_statusbar @ ggis/ui/framework/statusbar.py:1789")
                pass

        self._view_status_timer = QTimer(self)
        self._view_status_timer.setInterval(400)
        self._view_status_timer.timeout.connect(self._refresh_view_status)
        self._view_kind = ""
        self._view_ws = None

        self._bind_crs_label_signal()


        self._mounted_status_view = None


    def attach_view_status(self, kind, ws):
        self._view_kind = str(kind or "")
        self._view_ws = ws
        show_lay = (self._view_kind == "layout")
        show_mdl = (self._view_kind == "model")
        for _w, _on in ((getattr(self, "lbl_lay_page", None), show_lay),
                        (getattr(self, "lbl_lay_sel", None), show_lay),
                        (getattr(self, "lbl_lay_zoom", None), show_lay),
                        (getattr(self, "cmb_lay_zoom", None), show_lay),
                        (getattr(self, "btn_lay_export", None), show_lay),
                        (getattr(self, "lbl_model_stage", None), show_mdl),
                        (getattr(self, "bar_model", None), show_mdl)):
            if _w is None:
                continue
            try:
                _w.setVisible(bool(_on))
            except Exception:
                exc_note("attach_view_status @ ggis/ui/framework/statusbar.py:1856")
                pass
        tm = getattr(self, "_view_status_timer", None)
        if tm is None:
            self._refresh_status_seps()
            return
        try:
            if show_lay or show_mdl:
                self._refresh_view_status()
                if not tm.isActive():
                    tm.start()
            else:
                tm.stop()
        except Exception:
            exc_note("attach_view_status @ ggis/ui/framework/statusbar.py:1869")
            pass
        self._refresh_status_seps()

    def _refresh_status_seps(self):
        try:
            _sb = self.statusBar()
            if _sb is not None and hasattr(_sb, "_refresh_seps"):
                _sb._refresh_seps()
        except Exception:
            exc_note("_refresh_status_seps @ ggis/ui/framework/statusbar.py:1883")
            pass

    def _refresh_view_status(self):
        ws = getattr(self, "_view_ws", None)
        kind = getattr(self, "_view_kind", "")
        if ws is None:
            return
        fn = getattr(ws, "status_texts", None)
        if not callable(fn):
            return
        try:
            vals = list(fn())
        except Exception:
            exc_note("_refresh_view_status @ ggis/ui/framework/statusbar.py:1897")
            return
        try:
            if kind == "layout":
                page, sel, zoom = (vals + ["", "", ""])[:3]
                self.lbl_lay_page.setText(str(page or ""))
                self.lbl_lay_sel.setText(str(sel or ""))
                if str(zoom or "") and \
                        self.cmb_lay_zoom.currentText() != str(zoom):
                    self.cmb_lay_zoom.setEditText(str(zoom))
            elif kind == "model":
                stage, val, vis = (vals + ["", 0, False])[:3]
                self.lbl_model_stage.setText(str(stage or ""))
                try:
                    self.bar_model.setVisible(bool(vis))
                    self.bar_model.setValue(int(val))
                except Exception:
                    exc_note("_refresh_view_status @ ggis/ui/framework/statusbar.py:1913")
                    pass
        except Exception:
            exc_note("_refresh_view_status @ ggis/ui/framework/statusbar.py:1915")
            pass
        self._refresh_status_seps()

    def _on_lay_zoom_typed(self):
        ws = getattr(self, "_view_ws", None)
        if ws is None:
            return
        try:
            txt = str(self.cmb_lay_zoom.currentText() or "")
            txt = txt.replace("%", "").replace("％", "").strip()
            if txt:
                v = float(txt)
                if v > 10.0:
                    v = v / 100.0
                ws.view.set_zoom(v)
        except Exception:
            exc_note("_on_lay_zoom_typed @ ggis/ui/framework/statusbar.py:1934")
            pass
        self._refresh_view_status()

    def _on_lay_export(self, fmt):
        ws = getattr(self, "_view_ws", None)
        if ws is None:
            return
        try:
            ws.export(fmt)
        except Exception:
            exc_note("_on_lay_export @ ggis/ui/framework/statusbar.py:1945")
            pass

    def _busy(self, on):
        try:
            p = self.progress
        except Exception:
            exc_note("_busy @ ggis/ui/framework/statusbar.py:1962")
            return
        try:
            if on:
                self._render_hide_timer.stop()
                self._render_busy = True
                if not self._loading:
                    p.setVisible(False)
                return
            self._render_busy = False
            if self._loading:
                return
            p.setTextVisible(True)
            p.setRange(0, 100)
            p.setValue(0)
            p.setVisible(False)
        except Exception:
            exc_note("_busy @ ggis/ui/framework/statusbar.py:1979")
            pass

    def _on_render_started(self, *_):
        try:
            self._render_hide_timer.stop()
            self._busy(True)
        except Exception:
            exc_note("_on_render_started @ ggis/ui/framework/statusbar.py:1986")
            pass

    def _on_render_finished(self, *_):
        try:
            self._render_hide_timer.start(400)
        except Exception:
            exc_note("_on_render_finished @ ggis/ui/framework/statusbar.py:1992")
            pass

    def _render_idle(self, *_):
        try:
            self._busy(False)
        except Exception:
            exc_note("_render_idle @ ggis/ui/framework/statusbar.py:1998")
            pass
        try:
            self._set_render_label("")
        except Exception:
            exc_note("_render_idle @ ggis/ui/framework/statusbar.py:2005")
            pass

    def _set_render_label(self, text):
        lbl = getattr(self, "lbl_render", None)
        if lbl is None:
            return
        try:
            t = str(text or "").strip()
        except Exception:
            exc_note("_set_render_label @ ggis/ui/framework/statusbar.py:2027")
            t = ""
        if not t:
            try:
                if str(lbl.state()) == "busy":
                    lbl.set_done()
            except Exception:
                exc_note("_set_render_label @ ggis/ui/framework/statusbar.py:2036")
                try:
                    lbl.set_done()
                except Exception:
                    exc_note("_set_render_label @ ggis/ui/framework/statusbar.py:2039")
                    pass
            return
        if "渲染错误" in t:
            lbl.set_done()
        else:
            lbl.set_busy(_tr("渲染中"))

    def set_render_status(self, text):
        try:
            t = str(text or "").strip()
        except Exception:
            exc_note("set_render_status @ ggis/ui/framework/statusbar.py:2054")
            t = ""
        if t:
            try:
                self._set_render_label(t)
            except Exception:
                exc_note("set_render_status @ ggis/ui/framework/statusbar.py:2060")
                pass
            try:
                self._render_hide_timer.stop()
            except Exception:
                exc_note("set_render_status @ ggis/ui/framework/statusbar.py:2064")
                pass
            try:
                self._busy(True)
            except Exception:
                exc_note("set_render_status @ ggis/ui/framework/statusbar.py:2068")
                pass
        else:
            try:
                self._render_hide_timer.start(400)
            except Exception:
                exc_note("set_render_status @ ggis/ui/framework/statusbar.py:2076")
                self._render_idle()

    def begin_load(self, label="", total=0):
        self._loading = True
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.show_busy_delayed(
                self.window(),
                str(label or _tr("加载中")),
                (_tr("正在加载：{0}").format(label) if label
                 else _tr("正在读取…")),
                300)
        except Exception:
            exc_note("begin_load @ ggis/ui/framework/statusbar.py:2101")
            pass

    def update_load(self, done, total=0):
        try:
            from ggis.ui.dialogs import busy as _busy
            if total and total > 0:
                _busy.update_busy_progress(
                    max(0.0, min(1.0, float(done) / float(total))),
                    cancellable=False)
        except Exception:
            exc_note("update_load @ ggis/ui/framework/statusbar.py:2111")
            pass

    def end_load(self):
        self._loading = False
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.hide_busy()
        except Exception:
            exc_note("end_load @ ggis/ui/framework/statusbar.py:2120")
            pass

    def _update_scale_lock_icon(self, on):
        try:
            icons.bind(self.btn_scale_lock, "lock" if on else "lock_open",
                       size=14)
        except Exception:
            exc_note("_update_scale_lock_icon @ ggis/ui/framework/statusbar.py:2135")
            try:
                self.btn_scale_lock.setIcon(
                    icons.icon("lock" if on else "lock_open", size=14))
            except Exception:
                exc_note("_update_scale_lock_icon @ ggis/ui/framework/statusbar.py:2139")
                pass
        try:
            self.btn_scale_lock.setIconSize(QSize(14, 14))
        except Exception:
            exc_note("_update_scale_lock_icon @ ggis/ui/framework/statusbar.py:2148")
            pass

    def _on_scale_lock_toggled(self, on):
        on = bool(on)
        self._update_scale_lock_icon(on)
        try:
            self.canvas.setScaleLocked(on)
        except Exception:
            exc_note("_on_scale_lock_toggled @ ggis/ui/framework/statusbar.py:2157")
            pass
        try:
            self.cmb_scale.setEnabled(not on)
        except Exception:
            exc_note("_on_scale_lock_toggled @ ggis/ui/framework/statusbar.py:2164")
            pass
        try:
            self.show_message(_tr("已锁定比例") if on else _tr("已解除比例锁定"))
        except Exception:
            exc_note("_on_scale_lock_toggled @ ggis/ui/framework/statusbar.py:2168")
            pass

    def _show_scale(self, denom):
        cmb = getattr(self, "cmb_scale", None)
        if cmb is None:
            return
        try:
            denom = float(denom)
        except Exception:
            exc_note("_show_scale @ ggis/ui/framework/statusbar.py:2183")
            denom = 0.0
        hit = -1
        if denom > 0:
            for i, d in enumerate(COMMON_SCALES):
                if abs(denom - d) <= max(1.0, d * 0.005):
                    hit = i
                    break
        cur_val = COMMON_SCALES[hit] if hit >= 0 else None
        txt = _scale_text(denom) if denom > 0 else _tr("1:——")
        try:
            if (txt == cmb.lineEdit().text()
                    and cur_val == getattr(self, "_scale_cur", None)):
                return
        except Exception:
            exc_note("_show_scale @ ggis/ui/framework/statusbar.py:2198")
            pass
        try:
            blocked = cmb.blockSignals(True)
        except Exception:
            exc_note("_show_scale @ ggis/ui/framework/statusbar.py:2202")
            blocked = False
        try:
            cmb.setCurrentIndex(hit)
            cmb.setEditText(txt)
        except Exception:
            exc_note("_show_scale @ ggis/ui/framework/statusbar.py:2207")
            pass
        finally:
            try:
                cmb.blockSignals(blocked)
            except Exception:
                exc_note("_show_scale @ ggis/ui/framework/statusbar.py:2212")
                pass
        self._scale_cur = cur_val

    def _on_scale_changed(self, scale):
        cmb = getattr(self, "cmb_scale", None)
        if cmb is None:
            return
        try:
            _le = cmb.lineEdit()
            if _le is not None and _le.hasFocus():
                return
        except Exception:
            exc_note("_on_scale_changed @ ggis/ui/framework/statusbar.py:2230")
            pass
        self._show_scale(scale)

    def _apply_typed_scale(self):
        cmb = getattr(self, "cmb_scale", None)
        if cmb is None:
            return
        try:
            txt = cmb.lineEdit().text()
        except Exception:
            exc_note("_apply_typed_scale @ ggis/ui/framework/statusbar.py:2246")
            return
        d = _parse_scale(txt)
        try:
            cur = float(self.canvas.scale())
        except Exception:
            exc_note("_apply_typed_scale @ ggis/ui/framework/statusbar.py:2251")
            cur = 0.0
        if d <= 0:
            self._show_scale(cur)
            return
        if cur > 0 and abs(cur - d) <= max(1.0, d * 0.005):
            self._show_scale(cur)
            return
        self._apply_scale(d)

    def _apply_scale(self, denom):
        try:
            d = float(denom)
        except Exception:
            exc_note("_apply_scale @ ggis/ui/framework/statusbar.py:2272")
            return
        if d <= 0:
            return
        if d < 1.0:
            d = 1.0
        try:
            self.canvas.zoomScale(d)
        except Exception:
            exc_note("_apply_scale @ ggis/ui/framework/statusbar.py:2280")
            return
        try:
            self.show_message(
                _tr("已缩放到比例 1:{0}").format("{:.0f}".format(d)))
        except Exception:
            exc_note("_apply_scale @ ggis/ui/framework/statusbar.py:2285")
            pass

    def _on_xy_changed(self, pt):
        try:
            x, y = float(pt.x()), float(pt.y())
        except Exception:
            exc_note("_on_xy_changed @ ggis/ui/framework/statusbar.py:2291")
            return
        self._last_xy = (x, y)
        self.coords_label.setText(self._format_coord(x, y))

    def _xy_to_wgs84(self, x, y):
        try:
            from ggis.core.crs import (GgsCrs, crs_transformer)
            c = self.canvas.effectiveCrs()
            if c is None or not c.is_valid():
                return None
            wgs = GgsCrs.from_user_input("EPSG:4326")
            tf = crs_transformer(c, wgs)
            if tf is None:
                return (float(x), float(y)) if c.is_geographic() else None
            lon, lat = tf.transform(float(x), float(y))
            return (float(lon), float(lat))
        except Exception:
            exc_note("_xy_to_wgs84 @ ggis/ui/framework/statusbar.py:2316")
            return None

    @staticmethod
    def _deg_to_dm(v, pos="E", neg="W"):
        hemi = pos if v >= 0 else neg
        v = abs(v)
        d = int(v)
        m = (v - d) * 60.0
        if m >= 59.995:
            d, m = d + 1, 0.0
        return "%d\u00b0%05.2f\u2032%s" % (d, m, hemi)

    @staticmethod
    def _deg_to_dms(v, pos="E", neg="W"):
        hemi = pos if v >= 0 else neg
        v = abs(v)
        d = int(v)
        mf = (v - d) * 60.0
        m = int(mf)
        s = (mf - m) * 60.0
        if s >= 59.95:
            m, s = m + 1, 0.0
        if m >= 60:
            d, m = d + 1, 0
        return "%d\u00b0%d\u2032%04.1f\u2033%s" % (d, m, s, hemi)

    def _format_coord(self, x, y):
        fmt = getattr(self, "_coord_fmt", "map")
        if fmt == "map":
            return "{:,.3f}, {:,.3f}".format(x, y)
        lonlat = self._xy_to_wgs84(x, y)
        if lonlat is None:
            return "{:,.3f}, {:,.3f}".format(x, y)
        lon, lat = lonlat
        if fmt == "decdeg":
            return "%.6f\u00b0, %.6f\u00b0" % (lon, lat)
        if fmt == "dm":
            return "%s, %s" % (self._deg_to_dm(lon), self._deg_to_dm(lat, "N", "S"))
        return "%s, %s" % (self._deg_to_dms(lon),
                           self._deg_to_dms(lat, "N", "S"))

    def _set_coord_fmt(self, fmt):
        self._coord_fmt = fmt
        self.coords_label.setToolTip(
            _tr("坐标格式：{}").format(
                {"map": _tr("地图坐标"), "decdeg": _tr("十进制度"),
                 "dm": _tr("度分"), "dms": _tr("度分秒")}.get(fmt, fmt)))
        xy = getattr(self, "_last_xy", None)
        if xy is not None:
            try:
                self.coords_label.setText(self._format_coord(*xy))
            except Exception:
                exc_note("_set_coord_fmt @ ggis/ui/framework/statusbar.py:2373")
                pass

    def _bind_crs_label_signal(self):
        try:
            cv = self.canvas
            if cv is None:
                return
            old = getattr(self, "_crs_label_bound_canvas", None)
            if old is not None and old is not cv:
                try:
                    old.crsChanged.disconnect(self._update_crs_label)
                except Exception:
                    exc_note("_bind_crs_label_signal @ ggis/ui/framework/statusbar.py:2396")
                    pass
            if getattr(self, "_crs_label_bound_canvas", None) is cv:
                try:
                    cv.crsChanged.disconnect(self._update_crs_label)
                except Exception:
                    exc_note("_bind_crs_label_signal @ ggis/ui/framework/statusbar.py:2405")
                    pass
            cv.crsChanged.connect(self._update_crs_label)
            self._crs_label_bound_canvas = cv
        except Exception:
            exc_note("_bind_crs_label_signal @ ggis/ui/framework/statusbar.py:2409")
            pass
        self._update_crs_label()

    def set_project_crs(self, authid):
        a = str(authid or "").strip()
        if not a:
            return
        try:
            self.canvas.setDestinationCrs(a)
        except Exception:
            exc_note("set_project_crs @ ggis/ui/framework/statusbar.py:2434")
            pass
        self._bind_crs_label_signal()
        try:
            from ggis.ui.dialogs.crs import push_recent
            push_recent(a)
        except Exception:
            exc_note("set_project_crs @ ggis/ui/framework/statusbar.py:2442")
            pass
        from ggis.core.crs import GgsCrs as _GgsCrs
        c = _GgsCrs.from_user_input(a)
        disp = c.display_name() if (c is not None and c.is_valid()) else ""
        self.show_message(_tr("地图坐标系已切换为 {0}")
                          .format(disp or _tr("自定义坐标系")))
        try:
            self.ctx.svc("actions").refresh_measure_states()
        except Exception:
            exc_note("set_project_crs @ ggis/ui/framework/statusbar.py:2448")
            pass

    def choose_project_crs(self):
        try:
            from ggis.ui.dialogs.crs import GgsCrsDialog
        except Exception:
            exc_note("choose_project_crs @ ggis/ui/framework/statusbar.py:2514")
            return
        try:
            cur = self.canvas.destinationCrs()
        except Exception:
            exc_note("choose_project_crs @ ggis/ui/framework/statusbar.py:2518")
            cur = ""
        view_name = ""
        try:
            vh = getattr(self, "view_host", None)
            if vh is None:
                vh = getattr(self.window(), "view_host", None)
            v = vh.current_view() if vh is not None else None
            if v is not None:
                view_name = getattr(v, "title", "") or ""
        except Exception:
            exc_note("choose_project_crs @ ggis/ui/framework/statusbar.py:2529")
            view_name = ""
        if view_name:
            title = _tr("地图坐标系") + " · " + view_name
        else:
            title = _tr("地图坐标系")
        dlg = GgsCrsDialog(self, current=cur, title=title)
        try:
            if not dlg.exec():
                return
        except Exception:
            exc_note("choose_project_crs @ ggis/ui/framework/statusbar.py:2539")
            return
        self.set_project_crs(dlg.selected_authid())

    def retheme_statusbar(self):
        try:
            self._update_crs_label()
        except Exception:
            exc_note("retheme_statusbar @ ggis/ui/framework/statusbar.py:2555")
            pass

    def _update_crs_label(self):
        if getattr(self, "btn_crs", None) is None:
            return
        try:
            c = self.canvas.effectiveCrs()
        except Exception:
            exc_note("_update_crs_label @ ggis/ui/framework/statusbar.py:2571")
            c = None
        text = ""
        if c is not None and c.is_valid():
            epsg = None
            try:
                epsg = c.to_epsg()
            except Exception:
                exc_note("_update_crs_label @ ggis/ui/framework/statusbar.py:2578")
                epsg = None
            if epsg:
                text = "EPSG:%d" % int(epsg)
            else:
                text = (c.description() or c.authid() or "").strip()
                aid = (c.authid() or "").strip()
                if not text:
                    text = aid
                elif aid.upper().startswith("EPSG:"):
                    text = aid
        defined = bool(text)
        self.btn_crs.setText(text or "EPSG:——")
        try:
            self.btn_crs.setIcon(
                icons.icon("crs" if defined else "crs_disabled", size=16))
        except Exception:
            exc_note("_update_crs_label @ ggis/ui/framework/statusbar.py:2605")
            pass
        self.btn_crs.setToolTip(_tr("点击：设置底图坐标系"))



class GgsCoordsValue(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCoordsValue")
class GgsStatusLayout(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStatusLayout")
class GgsStatusLayoutExport(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStatusLayoutExport")
class GgsStatusLayoutZoom(QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStatusLayoutZoom")
class GgsStatusProgress(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStatusProgress")
class GgsStatusScaleLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStatusScaleLabel")
class GgsStatusScaleLock(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsStatusScaleLock")
