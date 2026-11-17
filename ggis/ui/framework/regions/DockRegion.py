from ggis.common.util.exc_report import exc_note

import logging

try:
    import shiboken6
except Exception:
    exc_note("<module> @ ggis/ui/framework/regions/DockRegion.py:26")
    shiboken6 = None

from ggis.core.app import i18n
from ggis.ui.panels.placeholders import GgsLogDock
from ggis.ui.panels.placeholders import GgsPlaceholderDock
from PySide6.QtWidgets import QDockWidget
from PySide6.QtCore import Qt, QEvent, QObject
from ggis.ui.framework.docks import GgsDockWidget
from PySide6.QtCore import QTimer
from ggis.common.base.dialog import GgsMsgBox
from ggis.common.widgets.msgbar import GgsMessageBar
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import QVBoxLayout
from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QTabBar
from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from ggis.common.styling import icons
from ggis.ui.framework.titlebar import EdgeGrip
from ggis.ui.panels.layertree import GgsLayerTreeDock

_log = logging.getLogger("gmagis")
_tr = i18n.tr

from ggis.ui.features._hostdeps import (
                                        DOCK_W,
                                        EDGE,
                                        _CANVAS_MIN_W,
                                        _CANVAS_MIN_H,
)
from ggis.ui.framework.services.lifecycle import is_headless
from PySide6.QtWidgets import QWidget
try:
    from shiboken6 import wrapInstance as _shiboken_wrap
except Exception:
    exc_note("<module> @ ggis/ui/framework/regions/DockRegion.py:59")
    _shiboken_wrap = None


class _DockResizeWatcher(QObject):

    def __init__(self, mw):
        super().__init__(mw)
        self._mw = mw

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.Type.Resize:
                svc = self._mw.ctx.svc("lifecycle")
                if svc is not None:
                    svc.schedule_state_save()
        except Exception:
            pass
        return False


class GgsDockRegion:

    def __init__(self, mw):
        self.mw = mw

    def build(self):
        self._build_docks()

    def _show_only_kind_docks(self, kind, view):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return
        aid = str(getattr(view, "view_id", ""))
        for v in vh.views():
            if str(getattr(v, "kind", "")) != kind:
                continue
            _on = bool(str(v.view_id) == aid)
            for d in self.mw._view_docks.get(str(v.view_id), []):
                try:
                    if _on:
                        d.show()
                        d.raise_()
                    else:
                        d.hide()
                except Exception:
                    exc_note("_show_only_kind_docks @ ggis/ui/framework/regions/DockRegion.py:96")
                    pass

    def _show_active_map_layer_dock(self, active_view):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return
        aid = str(getattr(active_view, "view_id", ""))
        _prev_id = getattr(self.mw, "_last_active_map_view_id", None)
        if _prev_id is not None and _prev_id != aid:
            _prev = None
            for _v in vh.views():
                if str(getattr(_v, "view_id", "")) == _prev_id:
                    _prev = _v
                    break
            if _prev is not None:
                self._snapshot_global_panels(_prev)
        self.mw._last_active_map_view_id = aid
        _active_dock = None
        for v in vh.views():
            if str(getattr(v, "kind", "")) != "map":
                continue
            d = getattr(v, "layer_dock", None)
            if d is None:
                continue
            if str(v.view_id) == aid:
                _active_dock = d
                try:
                    d.show()
                except Exception:
                    exc_note("_show_active_map_layer_dock @ ggis/ui/framework/regions/DockRegion.py:149")
                    pass
                try:
                    d.bind_tree(v._layer_tree)
                    d.restore_expand(aid)
                except Exception:
                    exc_note("_show_active_map_layer_dock @ ggis/ui/framework/regions/DockRegion.py:159")
                    pass
                try:
                    self._rebind_global_panels(v)
                except Exception:
                    exc_note("_show_active_map_layer_dock @ ggis/ui/framework/regions/DockRegion.py:166")
                    pass
                try:
                    self._restore_view_panels(v)
                except Exception:
                    exc_note("_show_active_map_layer_dock @ ggis/ui/framework/regions/DockRegion.py:172")
                    pass
            else:
                try:
                    for _ad in getattr(v, "_attr_docks", {}).values():
                        _ad.hide()
                except Exception:
                    exc_note("_show_active_map_layer_dock @ ggis/ui/framework/regions/DockRegion.py:187")
                    pass
        if _active_dock is None:
            _ld = self.mw.layer_dock
            if _ld is not None:
                try:
                    _ld.hide()
                except Exception:
                    exc_note("_show_active_map_layer_dock @ ggis/ui/framework/regions/DockRegion.py:195")
                    pass

    def _hide_all_map_layer_docks(self):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return
        for v in vh.views():
            if str(getattr(v, "kind", "")) != "map":
                continue
            d = getattr(v, "layer_dock", None)
            if d is not None:
                try:
                    d.setVisible(False)
                except Exception:
                    exc_note("_hide_all_map_layer_docks @ ggis/ui/framework/regions/DockRegion.py:209")
                    pass

    def _map_docks(self):
        out = []
        mgr = getattr(self.mw, "_map_dock_mgr", None)
        for n in ("browser_dock", "overview_dock",
                  "identify_dock", "toolbox_dock"):
            d = getattr(mgr, n, None) if mgr is not None else None
            if d is not None and d not in out:
                out.append(d)
        try:
            vh = getattr(self.mw, "view_host", None)
            if vh is not None:
                for v in vh.views():
                    if str(getattr(v, "kind", "")) != "map":
                        continue
                    for d in self.mw._view_docks.get(
                            str(getattr(v, "view_id", "")), []):
                        if (d is not None
                                and d.objectName() in (
                                    "GgsStylingDock", "GgsLabelingDock",
                                    "GgsAttributeTableDock")
                                and d not in out):
                            out.append(d)
        except Exception:
            exc_note("_map_docks @ ggis/ui/framework/regions/DockRegion.py:254")
            pass
        return out

    def _set_map_chrome_visible(self, on):
        docks = self._map_docks()
        if not on:
            if not self.mw._map_dock_state:
                self.mw._map_dock_state = {id(d): (not d.isHidden())
                                        for d in docks}
            for d in docks:
                try:
                    d.setVisible(False)
                except Exception:
                    exc_note("_set_map_chrome_visible @ ggis/ui/framework/regions/DockRegion.py:290")
                    pass
        else:
            state = self.mw._map_dock_state or {}
            self.mw._map_dock_state = {}
            if not state:
                return
            for d in docks:
                try:
                    d.setVisible(bool(state.get(id(d), True)))
                except Exception:
                    exc_note("_set_map_chrome_visible @ ggis/ui/framework/regions/DockRegion.py:300")
                    pass
        try:
            self._sync_panel_actions()
        except Exception:
            exc_note("_set_map_chrome_visible @ ggis/ui/framework/regions/DockRegion.py:304")
            pass

    def _layout_docks(self):
        out = []
        for n in ("layout_items_dock", "layout_props_dock"):
            d = getattr(self.mw, n, None)
            if d is not None:
                out.append(d)
        return out

    def _set_layout_chrome_visible(self, on, view=None):
        if on:
            ws = getattr(view, "workspace", None) if view is not None else None
            if ws is not None:
                try:
                    ws.attach_to_main_docks()
                except Exception:
                    _log.exception("布局：把元素面板装进主窗口 DOCK 失败")
            self._enforce_right_dock_tabs(reset_width=False)
            self._show_only_kind_docks("layout", view)
        else:
            for d in self.mw.view_region._view_docks_of_kind("layout"):
                try:
                    d.setVisible(False)
                except Exception:
                    exc_note("_set_layout_chrome_visible @ ggis/ui/framework/regions/DockRegion.py:348")
                    pass

    def _model_docks(self):
        out = []
        for n in ("model_ops_dock", "model_layers_dock", "model_props_dock"):
            d = getattr(self.mw, n, None)
            if d is not None:
                out.append(d)
        return out

    def _set_model_chrome_visible(self, on, view=None):
        if on:
            ws = getattr(view, "workspace", None) if view is not None else None
            if ws is not None:
                try:
                    ws.attach_to_main_docks()
                except Exception:
                    _log.exception("模型：把面板装进主窗口 DOCK 失败")
            self._enforce_right_dock_tabs(reset_width=False)
            self._show_only_kind_docks("model", view)
        else:
            for d in self.mw.view_region._view_docks_of_kind("model"):
                try:
                    d.setVisible(False)
                except Exception:
                    exc_note("_set_model_chrome_visible @ ggis/ui/framework/regions/DockRegion.py:391")
                    pass

    def apply_default_panels(self, kind, view=None):
        k = str(kind or "")
        if k == "map":
            mgr = getattr(self.mw, "_map_dock_mgr", None)
            br = getattr(mgr, "browser_dock", None) if mgr is not None else None
            if br is not None:
                try:
                    if br.isFloating():
                        br.setFloating(False)
                    br.show()
                except Exception:
                    exc_note("apply_default_panels @ ggis/ui/framework/regions/DockRegion.py:427")
                    pass
            for _n in ("overview_dock", "identify_dock", "toolbox_dock"):
                _d = getattr(mgr, _n, None) if mgr is not None else None
                if _d is not None:
                    try:
                        _d.setVisible(False)
                    except Exception:
                        exc_note("apply_default_panels @ ggis/ui/framework/regions/DockRegion.py:436")
                        pass
            if view is not None:
                for _a in ("styling_dock", "labeling_dock",
                           "attribute_dock"):
                    _d = getattr(view, _a, None)
                    if _d is not None:
                        try:
                            _d.hide()
                        except Exception:
                            exc_note("apply_default_panels @ ggis/ui/framework/regions/DockRegion.py:449")
                            pass
                _ld = getattr(view, "layer_dock", None)
                if _ld is not None:
                    try:
                        _ld.show()
                    except Exception:
                        exc_note("apply_default_panels @ ggis/ui/framework/regions/DockRegion.py:457")
                        pass
        elif k == "layout":
            self._set_layout_chrome_visible(True, view)
        elif k == "model":
            self._set_model_chrome_visible(True, view)
        try:
            self._sync_panel_actions()
        except Exception:
            exc_note("apply_default_panels @ ggis/ui/framework/regions/DockRegion.py:467")
            pass

    _SESSION_DOCK_ATTRS_MGR = ("browser_dock", "overview_dock",
                               "identify_dock", "toolbox_dock",
                               "_coord_dock", "_profile_dock",
                               "_spectral_dock")
    _SESSION_DOCK_ATTRS_MW = ("task_dock", "log_dock")

    def _session_dock_candidates(self):
        out = {}
        mgr = getattr(self.mw, "_map_dock_mgr", None)
        for attr in self._SESSION_DOCK_ATTRS_MGR:
            d = getattr(mgr, attr, None) if mgr is not None else None
            if d is not None:
                out.setdefault(str(d.objectName()), d)
        for attr in self._SESSION_DOCK_ATTRS_MW:
            d = getattr(self.mw, attr, None)
            if d is not None:
                out.setdefault(str(d.objectName()), d)
        return out

    def _session_panel(self, d):
        for x in (d, d.widget() if d is not None else None):
            if x is not None \
                    and callable(getattr(x, "session_state", None)) \
                    and callable(getattr(x, "restore_session", None)):
                return x
        return None

    def _dock_span_size(self, d):
        try:
            if d is None or d.isFloating():
                return None
            a = self.mw.dockWidgetArea(d)
            if a in (Qt.DockWidgetArea.LeftDockWidgetArea,
                     Qt.DockWidgetArea.RightDockWidgetArea):
                return int(d.width())
            if a in (Qt.DockWidgetArea.TopDockWidgetArea,
                     Qt.DockWidgetArea.BottomDockWidgetArea):
                return int(d.height())
        except Exception:
            exc_note("_dock_span_size @ ggis/ui/framework/regions/DockRegion.py")
        return None

    def _apply_session_sizes(self, h_docks, h_sizes, v_docks, v_sizes):
        try:
            if h_docks:
                self.mw.resizeDocks(list(h_docks),
                                    [int(s) for s in h_sizes],
                                    Qt.Horizontal)
            if v_docks:
                self.mw.resizeDocks(list(v_docks),
                                    [int(s) for s in v_sizes],
                                    Qt.Vertical)
        except Exception:
            exc_note("_apply_session_sizes @ ggis/ui/framework/regions/DockRegion.py")

    _REG_PANEL_ATTRS = ("layer_dock", "styling_dock", "labeling_dock",
                        "attribute_dock")

    def collect_dock_sizes(self):
        out = {}
        try:
            for name, d in self._session_dock_candidates().items():
                sz = self._dock_span_size(d)
                if sz:
                    out["dock/%s" % str(name)] = int(sz)
        except Exception:
            exc_note("collect_dock_sizes @ ggis/ui/framework/regions/DockRegion.py")
        vh = getattr(self.mw, "view_host", None)
        cur = vh.current_view() if vh is not None else None
        if cur is not None and getattr(cur, "kind", None) == "map":
            for attr in self._REG_PANEL_ATTRS:
                sz = self._dock_span_size(getattr(cur, attr, None))
                if sz:
                    out["panel/%s" % attr] = int(sz)
        return out

    def apply_registry_dock_sizes(self):
        q = getattr(self.mw, "_qset", None)
        if q is None:
            return
        h_d, h_s, v_d, v_s = [], [], [], []

        def _want(d, key):
            try:
                sz = int(q.value("docksizes/%s" % key, 0))
            except (TypeError, ValueError):
                sz = 0
            if sz <= 0:
                return
            try:
                a = self.mw.dockWidgetArea(d)
            except Exception:
                a = None
            if a in (Qt.DockWidgetArea.LeftDockWidgetArea,
                     Qt.DockWidgetArea.RightDockWidgetArea):
                h_d.append(d)
                h_s.append(sz)
            elif a in (Qt.DockWidgetArea.TopDockWidgetArea,
                       Qt.DockWidgetArea.BottomDockWidgetArea):
                v_d.append(d)
                v_s.append(sz)

        try:
            for name, d in self._session_dock_candidates().items():
                if isinstance(d, QDockWidget):
                    _want(d, "dock/%s" % str(name))
        except Exception:
            exc_note("apply_registry_dock_sizes @ ggis/ui/framework/regions/DockRegion.py")
        vh = getattr(self.mw, "view_host", None)
        cur = vh.current_view() if vh is not None else None
        if cur is not None and getattr(cur, "kind", None) == "map":
            for attr in self._REG_PANEL_ATTRS:
                d = getattr(cur, attr, None)
                if isinstance(d, QDockWidget):
                    _want(d, "panel/%s" % attr)
        if h_d or v_d:
            self._apply_session_sizes(h_d, h_s, v_d, v_s)
            _hd, _hs = list(h_d), list(h_s)
            _vd, _vs = list(v_d), list(v_s)
            QTimer.singleShot(
                0, lambda: self._apply_session_sizes(_hd, _hs, _vd, _vs))

    def _hook_dock_resize_save(self):
        mw = self.mw
        watcher = getattr(mw, "_dock_resize_watcher", None)
        if watcher is None:
            try:
                watcher = mw._dock_resize_watcher = _DockResizeWatcher(mw)
            except Exception:
                exc_note("_hook_dock_resize_save @ ggis/ui/framework/regions/DockRegion.py")
                return
        hooked = getattr(mw, "_dock_resize_hooked", None)
        if hooked is None:
            hooked = mw._dock_resize_hooked = set()
        ds = list(self._session_dock_candidates().values())
        vh = getattr(mw, "view_host", None)
        cur = vh.current_view() if vh is not None else None
        if cur is not None and getattr(cur, "kind", None) == "map":
            ds.extend(getattr(cur, a, None) for a in self._REG_PANEL_ATTRS)
        for d in ds:
            if not isinstance(d, QDockWidget) or id(d) in hooked:
                continue
            try:
                d.installEventFilter(watcher)
                hooked.add(id(d))
            except Exception:
                exc_note("_hook_dock_resize_save @ ggis/ui/framework/regions/DockRegion.py")

    def collect_session_docks(self):
        shared = {}
        cands = self._session_dock_candidates()
        amap = {
            Qt.DockWidgetArea.LeftDockWidgetArea: "left",
            Qt.DockWidgetArea.RightDockWidgetArea: "right",
            Qt.DockWidgetArea.TopDockWidgetArea: "top",
            Qt.DockWidgetArea.BottomDockWidgetArea: "bottom",
        }
        _chrome = {"GgsBrowserDock", "GgsOverviewDock", "GgsIdentifyDock",
                   "GgsToolboxDock"}
        pending = getattr(self.mw, "_map_dock_state", None) or {}
        for name, d in cands.items():
            try:
                if name in _chrome and pending:
                    open_ = bool(pending.get(id(d), False))
                    front = bool(open_ and name == "GgsBrowserDock")
                else:
                    open_ = not d.isHidden()
                    front = bool(open_ and d.isVisible())
                if not open_:
                    continue
                rec = {"open": bool(open_), "front": bool(front),
                       "float": bool(d.isFloating()),
                       "area": amap.get(self.mw.dockWidgetArea(d), "")}
                if rec["float"]:
                    g = d.geometry()
                    rec["geo"] = [int(g.x()), int(g.y()),
                                  int(g.width()), int(g.height())]
                if isinstance(d, QDockWidget) and not d.isFloating():
                    try:
                        _tb = [str(x.objectName()) for x in
                               self.mw.tabifiedDockWidgets(d)
                               if x is not d]
                        if _tb:
                            rec["tabs"] = _tb
                    except Exception:
                        exc_note("collect_session_docks @ ggis/ui/framework/regions/DockRegion.py:604")
                shared[str(name)] = rec
            except Exception:
                exc_note("collect_session_docks @ ggis/ui/framework/regions/DockRegion.py:569")
                pass
        _front_members = set()
        for _nm, _rec in shared.items():
            if not _rec.get("front"):
                continue
            if str(_nm) in _front_members:
                _rec["front"] = False
                continue
            _front_members.add(str(_nm))
            for _peer in (_rec.get("tabs") or []):
                _front_members.add(str(_peer))
        panels = {}
        vh = getattr(self.mw, "view_host", None)
        if vh is not None:
            cur = vh.current_view()
            for v in vh.views():
                if str(getattr(v, "kind", "")) != "map":
                    continue
                st = {}
                if v is cur:
                    for _a in ("styling_dock", "labeling_dock",
                               "attribute_dock"):
                        _d = getattr(v, _a, None)
                        _val = False
                        if _d is not None:
                            try:
                                _val = not _d.isHidden()
                            except Exception:
                                exc_note("collect_session_docks @ ggis/ui/framework/regions/DockRegion.py:626")
                                _val = False
                        if _val:
                            st[_a] = True
                    ld = getattr(v, "layer_dock", None)
                    if ld is not None:
                        try:
                            if not ld.isHidden():
                                st["layer_dock"] = True
                        except Exception:
                            exc_note("collect_session_docks @ ggis/ui/framework/regions/DockRegion.py:636")
                            pass
                else:
                    src = getattr(v, "_panel_state", None) or {}
                    for _a in ("styling_dock", "labeling_dock",
                               "attribute_dock"):
                        if src.get(_a):
                            st[_a] = True
                vid = str(getattr(v, "view_id", "") or "")
                if vid:
                    panels[vid] = st
        panel_ui = {}
        for name, d in cands.items():
            if d.isHidden():
                continue
            p = self._session_panel(d)
            if p is None:
                continue
            try:
                st = p.session_state()
            except Exception:
                exc_note("collect_session_docks @ ggis/ui/framework/regions/DockRegion.py:621")
                continue
            if isinstance(st, dict) and st:
                panel_ui[str(name)] = st
        return {"shared": shared, "panels": panels, "panel_ui": panel_ui}

    def apply_session_docks(self, info):
        if not isinstance(info, dict):
            return
        shared = info.get("shared") or {}
        cands = self._session_dock_candidates()
        amap = {
            "left": Qt.DockWidgetArea.LeftDockWidgetArea,
            "right": Qt.DockWidgetArea.RightDockWidgetArea,
            "top": Qt.DockWidgetArea.TopDockWidgetArea,
            "bottom": Qt.DockWidgetArea.BottomDockWidgetArea,
        }
        recs = []
        for name, rec in shared.items():
            if not isinstance(rec, dict):
                continue
            d = cands.get(str(name))
            if d is None:
                continue
            recs.append((d, rec))
        if recs:
            _rec_ids = {id(d) for d, _ in recs}
            for d in cands.values():
                if id(d) not in _rec_ids:
                    try:
                        d.setVisible(False)
                    except Exception:
                        exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:699")
                        pass
            for d, rec in recs:
                try:
                    if bool(rec.get("float")):
                        if not d.isFloating():
                            d.setFloating(True)
                        geo = rec.get("geo")
                        if isinstance(geo, (list, tuple)) and len(geo) == 4:
                            d.setGeometry(QRect(int(geo[0]), int(geo[1]),
                                                int(geo[2]), int(geo[3])))
                    else:
                        if d.isFloating():
                            d.setFloating(False)
                        qa = amap.get(str(rec.get("area") or ""))
                        if qa is not None:
                            try:
                                if self.mw.dockWidgetArea(d) != qa:
                                    self.mw.addDockWidget(qa, d)
                            except Exception:
                                exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:719")
                                pass
                except Exception:
                    exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:721")
                    pass
            cur = (getattr(getattr(self.mw, "view_host", None),
                           "current_view", lambda: None)() or None)
            cur_kind = (str(getattr(cur, "kind", "") or "")
                        if cur is not None else "")
            chrome_hidden = (cur_kind != "map")
            chrome_ids = {id(x) for x in self._map_docks()}
            pending_seed = {}
            for phase in ("hide", "back", "front"):
                for d, rec in recs:
                    open_ = bool(rec.get("open"))
                    front = bool(rec.get("front"))
                    is_chrome = id(d) in chrome_ids
                    try:
                        if chrome_hidden and is_chrome:
                            if phase == "hide":
                                pending_seed[id(d)] = open_
                            continue
                        if not open_:
                            if phase == "hide":
                                d.setVisible(False)
                        elif front:
                            if phase == "front":
                                d.setVisible(True)
                        else:
                            if phase == "back" and d.isHidden():
                                d.setVisible(True)
                    except Exception:
                        exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:751")
                        pass
            if chrome_hidden:
                for x in self._map_docks():
                    if id(x) not in pending_seed:
                        pending_seed[id(x)] = False
                try:
                    self.mw._map_dock_state = pending_seed
                except Exception:
                    exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:762")
                    pass
            _rec_by_name = {str(nm): rec for nm, rec in shared.items()
                            if isinstance(rec, dict)}
            _tab_done = set()
            for d, rec in recs:
                _tb = rec.get("tabs")
                if not isinstance(_tb, (list, tuple)) or not _tb:
                    continue
                for _nm in _tb:
                    _od = cands.get(str(_nm))
                    if _od is None or _od is d:
                        continue
                    if not (isinstance(d, QDockWidget)
                            and isinstance(_od, QDockWidget)):
                        continue
                    _orec = _rec_by_name.get(str(_nm))
                    if _orec is not None and not bool(_orec.get("open")):
                        continue
                    try:
                        if d.isFloating() or _od.isFloating():
                            continue
                    except Exception:
                        continue
                    _key = tuple(sorted((str(d.objectName()), str(_nm))))
                    if _key in _tab_done:
                        continue
                    _tab_done.add(_key)
                    try:
                        self.mw.tabifyDockWidget(d, _od)
                    except Exception:
                        exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:790")
                        pass
        panels = info.get("panels") or {}
        vh = getattr(self.mw, "view_host", None)
        if isinstance(panels, dict) and panels and vh is not None:
            cur = vh.current_view()
            cur_vid = (str(getattr(cur, "view_id", "") or "")
                       if cur is not None else "")
            for vid, st in panels.items():
                if not isinstance(st, dict):
                    continue
                v = vh.view(str(vid))
                if v is None or str(getattr(v, "kind", "")) != "map":
                    continue
                v._panel_state = {
                    _a: bool(st.get(_a, False))
                    for _a in ("styling_dock", "labeling_dock",
                               "attribute_dock")}
                if str(getattr(v, "view_id", "") or "") == cur_vid:
                    for _a, _want in v._panel_state.items():
                        _d = getattr(v, _a, None)
                        if _d is not None:
                            try:
                                _d.setVisible(_want)
                            except Exception:
                                exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:845")
                                pass
                    ld = getattr(v, "layer_dock", None)
                    if ld is not None:
                        try:
                            ld.setVisible(bool(st.get("layer_dock", False)))
                        except Exception:
                            exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:852")
                            pass
        pui = info.get("panel_ui")
        if isinstance(pui, dict) and pui:
            for name, st in pui.items():
                d = cands.get(str(name))
                p = self._session_panel(d) if d is not None else None
                if p is None or not isinstance(st, dict) or not st:
                    continue
                try:
                    p.restore_session(st)
                except Exception:
                    exc_note("apply_session_docks @ ggis/ui/framework/regions/DockRegion.py:808")
                    pass

    def _reorient_context_docks(self, view):
        idk = getattr(getattr(self.mw, "_map_dock_mgr", None),
                      "identify_dock", None)
        if idk is not None:
            try:
                idk.clear()
            except Exception:
                exc_note("_reorient_context_docks @ ggis/ui/framework/regions/DockRegion.py:866")
                pass
        self._clear_identify_marks_except(view)
        cdk = getattr(self.mw, "_coord_dock", None)
        if cdk is not None:
            try:
                proj = self.mw.ctx.region("title")._canvas_crs_authid()
                if proj:
                    cdk.reorient(proj, self._coord_layer_crs_of(view),
                                 view_id=getattr(view, "view_id", None))
                else:
                    cdk.reorient(None, None,
                                 view_id=getattr(view, "view_id", None))
            except Exception:
                exc_note("_reorient_context_docks @ ggis/ui/framework/regions/DockRegion.py:883")
                try:
                    cdk._sync_tool()
                except Exception:
                    exc_note("_reorient_context_docks @ ggis/ui/framework/regions/DockRegion.py:886")
                    pass

    def _clear_identify_marks_except(self, keep_view):
        try:
            vh = getattr(self.mw, "view_host", None)
            views = list(vh.views()) if vh is not None else []
        except Exception:
            exc_note("_clear_identify_marks_except @ ggis/ui/framework/regions/DockRegion.py:900")
            views = []
        for v in views:
            if v is keep_view:
                continue
            ti = (getattr(v, "_tools", None) or {}).get("identify")
            if ti is None:
                continue
            try:
                ti.clear_marks()
            except Exception:
                exc_note("_clear_identify_marks_except @ ggis/ui/framework/regions/DockRegion.py:910")
                pass

    def _coord_layer_crs_of(self, view):
        lyrs = []
        try:
            lt = getattr(view, "_layer_tree", None)
            if lt is not None:
                lyrs = list(lt.layers() or [])
        except Exception:
            exc_note("_coord_layer_crs_of @ ggis/ui/framework/regions/DockRegion.py:927")
            lyrs = []
        if not lyrs:
            try:
                lyrs = list(self.mw.ctx.project.layers() or [])
            except Exception:
                exc_note("_coord_layer_crs_of @ ggis/ui/framework/regions/DockRegion.py:932")
                lyrs = []
        out = []
        for lyr in lyrs:
            try:
                c = lyr.crs()
                a = c.authid() if c is not None else None
            except Exception:
                exc_note("_coord_layer_crs_of @ ggis/ui/framework/regions/DockRegion.py:939")
                a = None
            if a and a not in out:
                out.append(a)
        return out

    def _build_docks(self):
        self.mw._layer_dock_primary = None

        self.mw._map_dock_mgr.build_view_docks()
        _mdm = self.mw._map_dock_mgr

        try:
            from ggis.ui.panels.task_dock import GgsTaskDockPanel
            self.mw.task_dock = GgsTaskDockPanel(self.mw)
        except Exception as e:
            exc_note("_build_docks @ ggis/ui/framework/regions/DockRegion.py:969")
            self.mw.task_dock = GgsPlaceholderDock(
                _tr("任务"), _tr("任务面板初始化失败：{}").format(e),
                "task", self.mw)
        self.mw.task_dock.setObjectName("GgsTaskDock")

        self.mw.styling_dock = None
        self.mw.labeling_dock = None
        self.mw.attribute_dock = None

        self.mw._model_parked = {}
        self.mw._view_docks = {}

        self.mw.log_dock = GgsLogDock(_tr("日志"), self.mw)


        for dock, short in ((_mdm.identify_dock, "识别"),
                            (_mdm.toolbox_dock, "工具箱")):
            try:
                dock.set_short_title(short)
            except Exception:
                exc_note("_build_docks @ ggis/ui/framework/regions/DockRegion.py:1023")
                pass

        self.mw._right_docks = [
            _mdm.browser_dock, _mdm.overview_dock, _mdm.identify_dock,
            _mdm.toolbox_dock, self.mw.task_dock, self.mw.log_dock,
        ]
        self.mw._default_visible = _mdm.browser_dock




    def _rebind_global_panels(self, view):
        self.mw._panel_rebinding = True
        try:
            state = getattr(view, "_panel_state", None) or {}
            _applying = getattr(self.mw, "_applying_project_ui", False)
            for an in ("styling_dock", "labeling_dock", "attribute_dock"):
                d = getattr(self.mw, an, None)
                if d is None or _applying:
                    continue
                _v = state.get(an, None)
                if _v is None:
                    continue
                try:
                    d.setVisible(bool(_v))
                except Exception:
                    exc_note("_rebind_global_panels @ ggis/ui/framework/regions/DockRegion.py:1084")
                    pass
            try:
                _lyr = view._current_layer()
            except Exception:
                exc_note("_rebind_global_panels @ ggis/ui/framework/regions/DockRegion.py:1089")
                _lyr = None
            try:
                _proj = self.mw.ctx.project
                for an in ("styling_dock", "labeling_dock", "attribute_dock"):
                    d = getattr(self.mw, an, None)
                    if d is None:
                        continue
                    if _proj is not None and hasattr(d, "set_project"):
                        try:
                            d.set_project(_proj)
                        except Exception:
                            exc_note("_rebind_global_panels @ ggis/ui/framework/regions/DockRegion.py:1101")
                            pass
                    if _lyr is not None and hasattr(d, "set_layer"):
                        try:
                            d.set_layer(_lyr)
                        except Exception:
                            exc_note("_rebind_global_panels @ ggis/ui/framework/regions/DockRegion.py:1106")
                            pass
            except Exception:
                exc_note("_rebind_global_panels @ ggis/ui/framework/regions/DockRegion.py:1108")
                pass
        except Exception:
            exc_note("_rebind_global_panels @ ggis/ui/framework/regions/DockRegion.py:1110")
            pass
        finally:
            self.mw._panel_rebinding = False


    def _apply_dock_widths(self):
        min_w, max_w = 0, 1 << 24
        _ld = getattr(self.mw, "_layer_dock_primary", None)
        # 起始主页零视图时没有图层 DOCK，保持默认宽度即可，不算异常。
        if _ld is not None:
            try:
                min_w = int(_ld.minimumSizeHint().width() or 0)
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1144")
                min_w = 0
            try:
                max_w = int(_ld.maximumWidth() or 0) or (1 << 24)
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1148")
                max_w = 1 << 24
        _view_docks_flat = []
        try:
            for _v in (getattr(self.mw, "view_host", None).views()
                       if getattr(self.mw, "view_host", None) is not None
                       else []):
                for _a in ("styling_dock", "labeling_dock", "attribute_dock"):
                    _d = getattr(_v, _a, None)
                    if _d is not None:
                        _view_docks_flat.append(_d)
        except Exception:
            exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1164")
            pass
        for d in ([self.mw._layer_dock_primary] + list(self.mw._right_docks)
                  + list(self.mw.dock_region._layout_docks()) + _view_docks_flat):
            if d is None:
                continue
            try:
                d.setMinimumWidth(int(min_w))
                d.setMaximumWidth(int(max_w))
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1173")
                pass
            try:
                if int(d.width()) != int(DOCK_W):
                    d.resize(int(DOCK_W), int(d.height()))
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1180")
                pass
        try:
            first_right = self.mw._right_docks[0]
        except Exception:
            exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1184")
            first_right = None
        docks, sizes = [], []
        if self.mw._layer_dock_primary is not None:
            try:
                if (self.mw.dockWidgetArea(self.mw._layer_dock_primary)
                        != Qt.DockWidgetArea.NoDockWidgetArea):
                    docks.append(self.mw._layer_dock_primary)
                    sizes.append(DOCK_W)
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1200")
                pass
        if first_right is not None:
            try:
                if (self.mw.dockWidgetArea(first_right)
                        != Qt.DockWidgetArea.NoDockWidgetArea):
                    docks.append(first_right)
                    sizes.append(DOCK_W)
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1208")
                pass
        if docks:
            try:
                self.mw.resizeDocks(docks, sizes, Qt.Orientation.Horizontal)
            except Exception:
                exc_note("_apply_dock_widths @ ggis/ui/framework/regions/DockRegion.py:1213")
                pass


    def _attach_docks(self):
        self.mw._booting = True
        feats = (QDockWidget.DockWidgetFeature.DockWidgetMovable
                 | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                 | QDockWidget.DockWidgetFeature.DockWidgetClosable)

        try:
            for corner, area in (
                (Qt.Corner.TopLeftCorner,
                 Qt.DockWidgetArea.LeftDockWidgetArea),
                (Qt.Corner.BottomLeftCorner,
                 Qt.DockWidgetArea.LeftDockWidgetArea),
                (Qt.Corner.TopRightCorner,
                 Qt.DockWidgetArea.RightDockWidgetArea),
                (Qt.Corner.BottomRightCorner,
                 Qt.DockWidgetArea.RightDockWidgetArea),
            ):
                self.mw.setCorner(corner, area)
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1245")
            pass

        _ld = getattr(self.mw, "_layer_dock_primary", None)
        if _ld is not None:
            try:
                _ld.setFeatures(feats)
                self.mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, _ld)
                _ld.setFloating(False)
                _ld.show()
            except Exception:
                exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1262")
                pass
        try:
            if _ld is not None:
                self.mw.resizeDocks([_ld], [DOCK_W], Qt.Orientation.Horizontal)
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1270")
            pass

        try:
            ad = getattr(self.mw, "attribute_dock", None)
            if ad is not None and isinstance(ad, GgsDockWidget):
                ad.setFeatures(feats)
                self.mw.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, ad)
                ad.setFloating(False)
                ad.hide()
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1282")
            pass



        first = None
        for d in self.mw._right_docks:
            d.setFeatures(feats)
            if first is None:
                self.mw.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, d)
                first = d
            else:
                self.mw.tabifyDockWidget(first, d)
            d.setFloating(False)
            d.show()

        self._enforce_right_dock_tabs()
        for d in self.mw._right_docks:
            if d is not self.mw._default_visible:
                d.hide()
        try:
            self.mw._default_visible.raise_()
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1314")
            pass
        self._restore_layout()
        self._reattach_view_docks()
        try:
            self.mw.dock_region._set_layout_chrome_visible(False)
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1330")
            pass
        try:
            self.mw.dock_region._set_model_chrome_visible(False)
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1334")
            pass
        try:
            self._name_dock_tabbars()
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1343")
            pass
        try:
            QTimer.singleShot(0, self._name_dock_tabbars)
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1347")
            pass
        try:
            QTimer.singleShot(0, self.mw.ctx.svc("shell")._finish_boot)
        except Exception:
            exc_note("_attach_docks @ ggis/ui/framework/regions/DockRegion.py:1354")
            pass


    def _reattach_view_docks(self):
        feats = (QDockWidget.DockWidgetFeature.DockWidgetMovable
                 | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                 | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        try:
            _right_anchor = (list(self.mw._right_docks) or [None])[0]
        except Exception:
            exc_note("_reattach_view_docks @ ggis/ui/framework/regions/DockRegion.py:1381")
            _right_anchor = None
        vh = getattr(self.mw, "view_host", None)
        views = vh.views() if vh is not None else []
        for v in views:
            if str(getattr(v, "kind", "")) != "map":
                continue
            for attr, area in (("styling_dock",
                                Qt.DockWidgetArea.RightDockWidgetArea),
                               ("labeling_dock",
                                Qt.DockWidgetArea.RightDockWidgetArea),
                               ("attribute_dock",
                                Qt.DockWidgetArea.BottomDockWidgetArea)):
                d = getattr(v, attr, None)
                if d is None:
                    continue
                try:
                    d.setFeatures(feats)
                    self.mw.addDockWidget(area, d)
                    d.setFloating(False)
                    if (area == Qt.DockWidgetArea.RightDockWidgetArea
                            and _right_anchor is not None
                            and d is not _right_anchor):
                        self.mw.tabifyDockWidget(_right_anchor, d)
                except Exception:
                    exc_note("_reattach_view_docks @ ggis/ui/framework/regions/DockRegion.py:1405")
                    pass
        try:
            self._enforce_right_dock_tabs(reset_width=False)
        except Exception:
            exc_note("_reattach_view_docks @ ggis/ui/framework/regions/DockRegion.py:1410")
            pass


    def _raise_grips(self):
        for g in getattr(self.mw, "_grips", []) or []:
            g.raise_()




    def _init_separators(self):
        self.mw._seps = []
        self.mw._sep_tip = None


    def _layout_separators(self):
        for s in getattr(self.mw, "_seps", []) or []:
            try:
                s.hide()
                s.deleteLater()
            except Exception:
                exc_note("_layout_separators @ ggis/ui/framework/regions/DockRegion.py:1459")
                pass
        self.mw._seps = []
        tip = getattr(self.mw, "_sep_tip", None)
        if tip is not None:
            try:
                tip.hide()
                tip.deleteLater()
            except Exception:
                exc_note("_layout_separators @ ggis/ui/framework/regions/DockRegion.py:1467")
                pass
            self.mw._sep_tip = None
        self._raise_grips()


    def _sep_hover(self, global_pos):
        try:
            from ggis.common.widgets.separators import update_sep_hover
            update_sep_hover(self, getattr(self.mw, "_seps", []) or [], global_pos)
        except Exception:
            exc_note("_sep_hover @ ggis/ui/framework/regions/DockRegion.py:1478")
            pass


    def _sep_drag_begin(self, local_pos):
        try:
            from ggis.common.widgets.separators import sep_at
            s = sep_at(getattr(self.mw, "_seps", []) or [], local_pos)
        except Exception:
            exc_note("_sep_drag_begin @ ggis/ui/framework/regions/DockRegion.py:1487")
            s = None
        if s is None:
            return False
        self.mw._sep_dragging = s
        self.mw._sep_drag_start = (local_pos.x(), local_pos.y())
        self._sep_show_tip(s, local_pos)
        return True


    def _sep_show_tip(self, sep, local_pos):
        tip = getattr(self.mw, "_sep_tip", None)
        if tip is None or sep is None:
            return
        try:
            width = self._sep_current_width(sep)
            tip.set_text(_tr("{0} px").format(width))
            x = local_pos.x() + 14
            y = local_pos.y() + 14
            x = min(max(0, x), max(0, self.mw.width() - tip.width()))
            y = min(max(0, y), max(0, self.mw.height() - tip.height()))
            tip.move(int(x), int(y))
            tip.show()
            tip.raise_()
        except Exception:
            exc_note("_sep_show_tip @ ggis/ui/framework/regions/DockRegion.py:1513")
            pass


    def _sep_current_width(self, sep):
        try:
            if sep.is_horizontal():
                d = getattr(self.mw, "layer_dock", None)
                lg = self.mw.centralWidget().geometry()
                if d is not None and sep.x() + sep.width() <= lg.x() + 1:
                    return int(d.width())
                for r in getattr(self.mw, "_right_docks", ()) or ():
                    if r.isVisible() and not r.isFloating():
                        return int(r.width())
                return int(sep.width())
            d = getattr(self.mw, "attribute_dock", None)
            if d is not None and d.isVisible():
                return int(d.height())
            return int(sep.height())
        except Exception:
            exc_note("_sep_current_width @ ggis/ui/framework/regions/DockRegion.py:1534")
            return int(sep.width() if sep.is_horizontal() else sep.height())


    def _sep_drag_move(self, local_pos):
        sep = getattr(self.mw, "_sep_dragging", None)
        if sep is None:
            return False
        self._layout_separators()
        self._sep_show_tip(sep, local_pos)
        return True


    def _sep_drag_end(self):
        self.mw._sep_dragging = None
        self.mw._sep_drag_start = None
        tip = getattr(self.mw, "_sep_tip", None)
        if tip is not None:
            try:
                tip.hide()
            except Exception:
                exc_note("_sep_drag_end @ ggis/ui/framework/regions/DockRegion.py:1557")
                pass
        self._layout_separators()




    def _confirm(self, title, text):
        if is_headless():
            return True
        try:
            ans = GgsMsgBox.question(
                self.mw, title,
                text if isinstance(text, str) else "",
                GgsMsgBox.StandardButton.Yes | GgsMsgBox.StandardButton.No)
        except Exception:
            exc_note("_confirm @ ggis/ui/framework/regions/DockRegion.py:1579")
            return True
        return ans == GgsMsgBox.StandardButton.Yes










    def _build_view_host(self):

        """中央部件：**视图页签条 + 视图容器** + 浮动消息条。

 （视图整合 R492j252 定稿"功能区下方、画布紧上方；状态栏左侧标签
 就不要了"）：中心区从"一个画布"升级成"**一页一个视图**"的 `ViewHost`，
 页签条是视图区域第一行、与视图同属一个独立区域，构造即落位
 （不再"先建进状态栏、启动末尾再搬运"）：

 [ 地图视图 ] [ 布局 1 ] [ 布局 2 ] …   ← 页签条（视图区域第一行）
 [ 画布（当前视图页）                ]  ← ViewHost（一页一个视图）

 **地图视图只是第一页**（`closable=False`，关不掉）。**画布本身不重建**
 —— 地图工具 / 选择集 / 编辑会话 / 渲染子进程 / 状态栏全都绑在
 `self.mw.canvas` 上，这里只把它的父换成 `MapView`（`setParent` 而已）。
 """
        host = GgsCanvasHost()
        host.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        host.setMinimumSize(_CANVAS_MIN_W, _CANVAS_MIN_H)
        lay = QVBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.mw._host_lay = lay

        # 视图页签条 = 视图区域第一行（R492j252 定稿），与视图同属一个
        # 独立区域；Settings 阶段已过，title_bar_height 取值可靠。
        from ggis.ui.framework.statusbar import GgsViewTabs
        self.mw.view_tabs = GgsViewTabs(host)
        lay.addWidget(self.mw.view_tabs, 0)

        from ggis.ui.views import ViewHost
        from ggis.ui.views.map.map_view import MapView
        self.mw.view_host = ViewHost(host)
        self.mw.ctx.view_host = self.mw.view_host
        self.mw.view_host.ctx = self.mw.ctx
        self.mw.empty_view = None
        lay.addWidget(self.mw.view_host, 1)
        self.mw.setCentralWidget(host)

        self.mw.msg_bar = GgsMessageBar(host)
        self.mw.msg_bar.setObjectName("GgsMessageBar")
        self.mw.msg_bar.setSizePolicy(QSizePolicy.Policy.Minimum,
                                   QSizePolicy.Policy.Fixed)
        self.mw.msg_bar.hide()
        try:
            self.mw.ctx.wiring.connect((self.mw.msg_bar.widgetAdded), (self._on_msg_bar_changed), "msg_bar")
            self.mw.ctx.wiring.connect((self.mw.msg_bar.widgetRemoved), (self._on_msg_bar_changed), "msg_bar")
        except Exception:
            exc_note("_build_view_host @ ggis/ui/framework/regions/DockRegion.py:1690")
            pass
        self._reposition_msg_bar()




    def _build_canvas(self):
        return self._build_view_host()


    def _bind_primary_layer_dock(self):
        return


    def _reposition_msg_bar(self):
        bar = getattr(self.mw, "msg_bar", None)
        cv = self.mw.canvas
        if bar is None or cv is None:
            return
        try:
            w = max(320, cv.width() - 16)
            bar.setFixedWidth(w)
            bar._sync_size()
            h = max(0, bar.height())
            host = self.mw.centralWidget()
            try:
                tl = cv.mapTo(host, QPoint(0, 0)) if host is not None \
                    else QPoint(0, 0)
            except Exception:
                exc_note("_reposition_msg_bar @ ggis/ui/framework/regions/DockRegion.py:1740")
                tl = QPoint(0, 0)
            cv_bottom = tl.y() + cv.height()
            y = max(tl.y() + 8, cv_bottom - h - 12)
            x = tl.x() + (cv.width() - w) // 2
            bar.move(x, y)
            bar.raise_()
        except Exception:
            exc_note("_reposition_msg_bar @ ggis/ui/framework/regions/DockRegion.py:1747")
            pass


    def _on_msg_bar_changed(self, *_):
        bar = self.mw.msg_bar
        try:
            if bar.items():
                self._reposition_msg_bar()
                bar.show()
                bar.raise_()
                bar._sync_size()
            else:
                bar.hide()
        except Exception:
            exc_note("_on_msg_bar_changed @ ggis/ui/framework/regions/DockRegion.py:1761")
            pass




    def _name_dock_tabbars(self):
        try:
            for bar in self.mw.findChildren(QTabBar):
                if not bar.objectName() and bar.parent() is self.mw:
                    bar.setObjectName("GgsDockTabBar")
                    try:
                        bar.setElideMode(Qt.TextElideMode.ElideNone)
                        bar.setUsesScrollButtons(True)
                    except Exception:
                        exc_note("_name_dock_tabbars @ ggis/ui/framework/regions/DockRegion.py:1799")
                        pass
                    try:
                        bar.setContextMenuPolicy(
                            Qt.ContextMenuPolicy.CustomContextMenu)
                        self.mw.ctx.wiring.connect((bar.customContextMenuRequested), (lambda pos, b=bar: self._dock_tab_menu(b, pos)), "dock_tab")
                    except Exception:
                        exc_note("_name_dock_tabbars @ ggis/ui/framework/regions/DockRegion.py:1808")
                        pass
                    try:
                        if not getattr(bar, "_front_wired", False):
                            self.mw.ctx.wiring.connect((bar.currentChanged), (lambda _i, b=bar: self._on_dock_tab_changed(b)), "dock_tab")
                            bar._front_wired = True
                    except Exception:
                        exc_note("_name_dock_tabbars @ ggis/ui/framework/regions/DockRegion.py:1818")
                        pass
                    st = bar.style()
                    st.unpolish(bar)
                    st.polish(bar)
        except Exception:
            exc_note("_name_dock_tabbars @ ggis/ui/framework/regions/DockRegion.py:1823")
            pass
        try:
            self._refresh_all_dock_fronts()
        except Exception:
            exc_note("_name_dock_tabbars @ ggis/ui/framework/regions/DockRegion.py:1832")
            pass


    def _dock_tab_menu(self, bar, pos):
        try:
            idx = int(bar.tabAt(pos))
        except Exception:
            exc_note("_dock_tab_menu @ ggis/ui/framework/regions/DockRegion.py:1853")
            return
        if idx < 0:
            return
        try:
            name = str(bar.tabText(idx) or "").strip()
        except Exception:
            exc_note("_dock_tab_menu @ ggis/ui/framework/regions/DockRegion.py:1859")
            name = ""
        if not name:
            return
        dock = None
        try:
            for d in self.mw.findChildren(QDockWidget):
                if self._dock_tab_index(bar, d) == idx:
                    dock = d
                    break
        except Exception:
            exc_note("_dock_tab_menu @ ggis/ui/framework/regions/DockRegion.py:1872")
            dock = None
        if dock is None:
            return
        try:
            menu = QMenu(self.mw)
            act_close = menu.addAction(_tr("关闭"))
            picked = menu.exec(bar.mapToGlobal(pos))
            if picked is act_close:
                dock.close()
                try:
                    self._sync_panel_actions()
                except Exception:
                    exc_note("_dock_tab_menu @ ggis/ui/framework/regions/DockRegion.py:1884")
                    pass
        except Exception:
            exc_note("_dock_tab_menu @ ggis/ui/framework/regions/DockRegion.py:1886")
            pass




    def _panel_action(self, dock, text, icon_name=None):
        a = QAction(_tr(text), self.mw)
        a.setCheckable(True)
        a.setChecked(bool(dock.isVisible()))

        def _sync(vis=None, act=a):
            self._sync_panel_actions()
        try:
            self.mw.ctx.wiring.connect((dock.visibilityChanged), (_sync), "action")
        except Exception:
            exc_note("_panel_action @ ggis/ui/framework/regions/DockRegion.py:1924")
            pass

        self.mw.ctx.wiring.connect((a.triggered), (lambda _c=False, d=dock: self._toggle_dock_action(d, None)), "action")
        if icon_name:
            try:
                icons.bind(a, icon_name)
            except Exception:
                exc_note("_panel_action @ ggis/ui/framework/regions/DockRegion.py:1933")
                pass
        return a


    def _panel_activate_action(self, dock, text, icon_name=None):
        a = QAction(_tr(text), self.mw)
        a.setCheckable(False)
        self.mw.ctx.wiring.connect((a.triggered), (lambda _c=False, d=dock: self._activate_dock(d)), "action")
        if icon_name:
            try:
                icons.bind(a, icon_name)
            except Exception:
                exc_note("_panel_activate_action @ ggis/ui/framework/regions/DockRegion.py:1954")
                pass
        return a


    def _unwrap_dock(self, ptr):
        if _shiboken_wrap is None or not ptr:
            return None
        try:
            return _shiboken_wrap(int(ptr), GgsDockWidget)
        except Exception:
            exc_note("_unwrap_dock @ ggis/ui/framework/regions/DockRegion.py:1970")
            return None


    def _dock_tab_containing(self, dock):
        if dock is None:
            return (None, -1)
        try:
            for bar in self.mw.findChildren(QTabBar):
                if bar.objectName() != "GgsDockTabBar":
                    continue
                for i in range(bar.count()):
                    try:
                        p = bar.tabData(i)
                    except Exception:
                        exc_note("_dock_tab_containing @ ggis/ui/framework/regions/DockRegion.py:1991")
                        p = None
                    if not p:
                        continue
                    d = self._unwrap_dock(p)
                    if d is not None and d == dock:
                        return (bar, i)
        except Exception:
            exc_note("_dock_tab_containing @ ggis/ui/framework/regions/DockRegion.py:1998")
            pass
        try:
            want = dock.windowTitle()
            for bar in self.mw.findChildren(QTabBar):
                for i in range(bar.count()):
                    if bar.tabText(i) == want:
                        return (bar, i)
        except Exception:
            exc_note("_dock_tab_containing @ ggis/ui/framework/regions/DockRegion.py:2009")
            pass
        return (None, -1)


    def _dock_tabbar(self):
        try:
            for bar in self.mw.findChildren(QTabBar):
                if bar.objectName() == "GgsDockTabBar":
                    return bar
        except Exception:
            exc_note("_dock_tabbar @ ggis/ui/framework/regions/DockRegion.py:2020")
            pass
        return None


    def _dock_tab_index(self, bar, dock):
        if bar is None or dock is None:
            return -1
        try:
            for i in range(bar.count()):
                try:
                    p = bar.tabData(i)
                except Exception:
                    exc_note("_dock_tab_index @ ggis/ui/framework/regions/DockRegion.py:2037")
                    p = None
                if not p:
                    continue
                d = self._unwrap_dock(p)
                if d is not None and d == dock:
                    return i
        except Exception:
            exc_note("_dock_tab_index @ ggis/ui/framework/regions/DockRegion.py:2044")
            pass
        try:
            want = dock.windowTitle()
            for i in range(bar.count()):
                if bar.tabText(i) == want:
                    return i
        except Exception:
            exc_note("_dock_tab_index @ ggis/ui/framework/regions/DockRegion.py:2051")
            pass
        return -1


    def _dock_at_tab(self, bar, idx):
        if bar is None or idx < 0 or idx >= bar.count():
            return None
        try:
            p = bar.tabData(idx)
            if p:
                d = self._unwrap_dock(p)
                if isinstance(d, GgsDockWidget):
                    return d
        except Exception:
            exc_note("_dock_at_tab @ ggis/ui/framework/regions/DockRegion.py:2072")
            pass
        try:
            want = bar.tabText(idx)
            for d in self.mw.findChildren(GgsDockWidget):
                if d.windowTitle() == want:
                    return d
        except Exception:
            exc_note("_dock_at_tab @ ggis/ui/framework/regions/DockRegion.py:2081")
            pass
        return None


    def _refresh_all_dock_fronts(self):
        try:
            for bar in self.mw.findChildren(QTabBar):
                if bar.objectName() != "GgsDockTabBar":
                    continue
                self._on_dock_tab_changed(bar)
        except Exception:
            exc_note("_refresh_all_dock_fronts @ ggis/ui/framework/regions/DockRegion.py:2100")
            pass




    def _set_dock_front(self, bar, new_front):
        try:
            if bar is None:
                return
            if not hasattr(self.mw, "_dock_front"):
                self.mw._dock_front = {}
            bid = id(bar)
            old = self.mw._dock_front.get(bid)
            if old is new_front:
                return

            def _alive(x):
                if x is None:
                    return False
                try:
                    import shiboken6
                    return bool(shiboken6.isValid(x))
                except Exception:
                    return False

            if (old is not None and isinstance(old, GgsDockWidget)
                    and _alive(old)):
                try:
                    old.frontChanged.emit(False)
                except Exception:
                    exc_note("_set_dock_front @ ggis/ui/framework/regions/DockRegion.py:2132")
                    pass
            if (new_front is not None
                    and isinstance(new_front, GgsDockWidget)
                    and _alive(new_front)):
                try:
                    new_front.frontChanged.emit(True)
                except Exception:
                    exc_note("_set_dock_front @ ggis/ui/framework/regions/DockRegion.py:2138")
                    pass
            self.mw._dock_front[bid] = new_front
        except Exception:
            exc_note("_set_dock_front @ ggis/ui/framework/regions/DockRegion.py:2141")
            pass


    def _on_dock_tab_changed(self, bar):
        try:
            if bar is None:
                return
            cur = bar.currentIndex()
            new_front = self._dock_at_tab(bar, cur)
            self._set_dock_front(bar, new_front)
        except Exception:
            exc_note("_on_dock_tab_changed @ ggis/ui/framework/regions/DockRegion.py:2154")
            pass


    def _place_new_dock(self, dock):
        if dock is None:
            return
        try:
            if getattr(dock, "_ggs_placed_once", False):
                return
            dock._ggs_placed_once = True
        except Exception:
            exc_note("_place_new_dock @ ggis/ui/framework/regions/DockRegion.py:2178")
            return
        if getattr(self.mw, "_booting", False):
            return
        try:
            if dock.isFloating():
                return
            area = self.mw.dockWidgetArea(dock)
            self._enforce_right_dock_tabs(reset_width=False)
            if area == Qt.DockWidgetArea.BottomDockWidgetArea:
                for corner, side in (
                    (Qt.Corner.TopLeftCorner,
                     Qt.DockWidgetArea.LeftDockWidgetArea),
                    (Qt.Corner.BottomLeftCorner,
                     Qt.DockWidgetArea.LeftDockWidgetArea),
                    (Qt.Corner.TopRightCorner,
                     Qt.DockWidgetArea.RightDockWidgetArea),
                    (Qt.Corner.BottomRightCorner,
                     Qt.DockWidgetArea.RightDockWidgetArea),
                ):
                    self.mw.setCorner(corner, side)
        except Exception:
            import logging
            logging.getLogger("gmagis").warning(
                "dock first-place failed", exc_info=True)

    def _activate_dock(self, dock):
        if dock is None:
            return
        try:
            if dock.isFloating():
                dock.show()
                dock.raise_()
                if hasattr(dock, "activateWindow"):
                    dock.activateWindow()
                self._layout_separators()
                return
        except Exception:
            exc_note("_activate_dock @ ggis/ui/framework/regions/DockRegion.py:2225")
            pass
        dock.show()
        self._place_new_dock(dock)
        try:
            _is_bottom = (self.mw.dockWidgetArea(dock)
                          == Qt.DockWidgetArea.BottomDockWidgetArea)
            if _is_bottom and not getattr(dock, "_ggs_initial_h_done", False):
                dock._ggs_initial_h_done = True
                h = max(160, int(self.mw.height() // 3))
                self.mw.resizeDocks([dock], [h], Qt.Orientation.Vertical)
        except Exception:
            exc_note("_activate_dock @ ggis/ui/framework/regions/DockRegion.py:2241")
            pass
        bar, i = self._dock_tab_containing(dock)
        if bar is None or i < 0:
            bar, i = self._find_bar_for_dock(dock)
        if bar is not None and i >= 0:
            try:
                dock.show()
                bar.setCurrentIndex(i)
                dock.raise_()
                try:
                    self._set_dock_front(bar, dock)
                except Exception:
                    exc_note("_activate_dock @ ggis/ui/framework/regions/DockRegion.py:2263")
                    pass
                self._layout_separators()
                return
            except Exception:
                exc_note("_activate_dock @ ggis/ui/framework/regions/DockRegion.py:2267")
                pass
        try:
            if isinstance(dock, GgsDockWidget):
                dock.frontChanged.emit(True)
        except Exception:
            exc_note("_activate_dock @ ggis/ui/framework/regions/DockRegion.py:2274")
            pass
        try:
            dock.raise_()
            self._layout_separators()
        except Exception:
            exc_note("_activate_dock @ ggis/ui/framework/regions/DockRegion.py:2279")
            pass
        self._sync_panel_actions()


    def _sync_panel_actions(self):
        stale = []
        for dock, act in list(getattr(self.mw, "_panel_acts", []) or []):
            if dock is None or (shiboken6 is not None
                                and not shiboken6.isValid(dock)):
                stale.append((dock, act))
                continue
            try:
                act.setChecked(bool(dock.isVisible()))
            except Exception:
                exc_note("_sync_panel_actions @ ggis/ui/framework/regions/DockRegion.py:2298")
                pass
        if stale:
            try:
                dead = {id(it) for it in stale}
                self.mw._panel_acts = [
                    it for it in self.mw._panel_acts
                    if id(it) not in dead]
                _log.warning(
                    "「视图→面板」注册表自愈：摘除 %d 个已销毁 DOCK 的悬空项",
                    len(stale))
            except Exception:
                exc_note("_sync_panel_actions @ ggis/ui/framework/regions/DockRegion.py:2310")
                pass


    def _find_bar_for_dock(self, dock):
        if dock is None:
            return (None, -1)
        try:
            want = dock.windowTitle()
            for bar in self.mw.findChildren(QTabBar):
                for i in range(bar.count()):
                    if bar.tabText(i) == want:
                        return (bar, i)
        except Exception:
            exc_note("_find_bar_for_dock @ ggis/ui/framework/regions/DockRegion.py:2320")
            pass
        return (None, -1)

    def _dock_is_front(self, dock):
        if dock is None:
            return False
        try:
            if dock.isFloating():
                return bool(dock.isVisible())
        except Exception:
            exc_note("_dock_is_front @ ggis/ui/framework/regions/DockRegion.py:2341")
            return False
        try:
            if not dock.isVisible():
                return False
        except Exception:
            exc_note("_dock_is_front @ ggis/ui/framework/regions/DockRegion.py:2346")
            return False
        bar, i = self._dock_tab_containing(dock)
        if bar is None or i < 0:
            return True
        try:
            return bar.currentIndex() == i
        except Exception:
            exc_note("_dock_is_front @ ggis/ui/framework/regions/DockRegion.py:2354")
            return True


    def _toggle_dock_action(self, dock, act_name):
        if dock is None:
            return
        self._activate_dock(dock)
        vis = True
        a = self.mw.ctx.svc("actions")._acts.get(act_name) if act_name else None
        if a is not None and a.isCheckable() and a.isChecked() != vis:
            a.setChecked(vis)
        self._sync_panel_actions()


    def _set_active_dock(self, dock):
        if dock is self.mw._active_dock:
            return
        old, self.mw._active_dock = self.mw._active_dock, dock
        for d in (old, dock):
            if d is None:
                continue
            try:
                if shiboken6 is not None and not shiboken6.isValid(d):
                    continue
                d.update()
            except Exception:
                exc_note("_set_active_dock @ ggis/ui/framework/regions/DockRegion.py:2412")
                pass




    def _panel_acts_of(self, view):
        rid = str(getattr(view, "view_id", "") or "")
        reg = self.mw.ctx.svc("actions")._panel_acts_reg
        if reg is None:
            reg = self.mw.ctx.svc("actions")._panel_acts_reg = {}
        if rid not in reg:
            reg[rid] = []
        return reg[rid]


    def _view_tab_signature(self, view, kind):
        try:
            if view is None:
                ids = ()
            else:
                g = self.mw._control_group_of(view)
                names = []
                if g is not None:
                    for d in g.docks():
                        names.append(str(d.objectName() or id(d)))
                for d in (self.mw._view_docks.get(
                        str(getattr(view, "view_id", "")), []) or []):
                    names.append(str(d.objectName() or id(d)))
                ids = tuple(sorted(set(names)))
        except Exception:
            exc_note("_view_tab_signature @ ggis/ui/framework/regions/DockRegion.py:2435")
            ids = ()
        return (str(kind or ""), ids)


    def _show_dock(self, dock):
        self._activate_dock(dock)



    def _register_right_dock(self, dock):
        try:
            rd = getattr(self.mw, "_right_docks", None)
            if rd is not None and dock not in rd:
                rd.append(dock)
        except Exception:
            exc_note("_register_right_dock @ ggis/ui/framework/regions/DockRegion.py:2466")
            pass
        try:
            _ld = getattr(self.mw, "_layer_dock_primary", None)
            if _ld is not None:
                mw = int(_ld.minimumSizeHint().width() or 0)
                dock.setMinimumWidth(mw)
                dock.setMaximumWidth(1 << 24)
                dock.resize(int(DOCK_W), dock.height())
        except Exception:
            exc_note("_register_right_dock @ ggis/ui/framework/regions/DockRegion.py:2475")
            pass




    def _reflow_all_measure_panels(self):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return
        try:
            vs = vh.views()
        except Exception:
            exc_note("_reflow_all_measure_panels @ ggis/ui/framework/regions/DockRegion.py:2502")
            return
        for v in vs:
            if str(getattr(v, "kind", "")) != "map":
                continue
            p = getattr(v, "_measure_panel", None)
            if p is None or not p.isVisible():
                continue
            try:
                v._place_measure_panel()
            except Exception:
                exc_note("_reflow_all_measure_panels @ ggis/ui/framework/regions/DockRegion.py:2512")
                pass



    def _dispose_view_ribbon(self, vid):
        key = str(vid)
        try:
            reg = getattr(self.mw, "_view_tabs", None)
            if isinstance(reg, dict):
                reg.pop(key, None)
                det = (reg.get("_detached") or {}).pop(key, None)
            else:
                det = None
        except Exception:
            exc_note("_dispose_view_ribbon @ ggis/ui/framework/regions/DockRegion.py:2535")
            det = None
        entries = []
        rib = getattr(self.mw, "ribbon", None)
        if rib is not None and key != self.mw._primary_view_id():
            try:
                _tag = self.mw._tag_of_view_id(key)
            except Exception:
                exc_note("_dispose_view_ribbon @ ggis/ui/framework/regions/DockRegion.py:2543")
                _tag = ""
            try:
                from ggis.ui.features.map_ribbon_groups import MAP_RIBBON_TAG as _SHARED
            except Exception:
                exc_note("_dispose_view_ribbon @ ggis/ui/framework/regions/DockRegion.py:2556")
                _SHARED = "map:__shared__"
            if _tag and _tag == _SHARED:
                entries = []
            else:
                try:
                    entries = rib.detach_tabs_by_tag(_tag)
                except Exception:
                    exc_note("_dispose_view_ribbon @ ggis/ui/framework/regions/DockRegion.py:2563")
                    entries = []
        for _title, _page, _wrap, _tag in list(det or []) + list(entries):
            for w in (_wrap, _page):
                try:
                    if w is not None:
                        w.deleteLater()
                except Exception:
                    exc_note("_dispose_view_ribbon @ ggis/ui/framework/regions/DockRegion.py:2570")
                    pass
        try:
            pareg = self.mw.ctx.svc("actions")._panel_acts_reg
            if isinstance(pareg, dict):
                pareg.pop(key, None)
        except Exception:
            exc_note("_dispose_view_ribbon @ ggis/ui/framework/regions/DockRegion.py:2576")
            pass


    def _register_view_docks(self, view_id, docks):
        self.mw._view_docks[str(view_id)] = list(docks or [])


    def _restore_view_panels(self, view):
        try:
            for _ad in getattr(view, "_attr_docks", {}).values():
                _ad.show()
        except Exception:
            exc_note("_restore_view_panels @ ggis/ui/framework/regions/DockRegion.py:2595")
            pass


    def _on_panel_visibility(self, view, attr, visible):
        if getattr(self.mw, "_panel_rebinding", False):
            return
        cur = self.mw.current_map_view()
        if view is None:
            view = cur
        if cur is None or view is None or cur is not view:
            return
        try:
            if not hasattr(view, "_panel_state"):
                view._panel_state = {}
            view._panel_state[attr] = bool(visible)
        except Exception:
            exc_note("_on_panel_visibility @ ggis/ui/framework/regions/DockRegion.py:2620")
            pass


    def _snapshot_global_panels(self, view):
        if (getattr(self.mw, "_applying_project_ui", False)
                or getattr(self.mw, "_booting", False)):
            return
        try:
            if not hasattr(view, "_panel_state"):
                view._panel_state = {}
            self.mw._panel_rebinding = True
            for an in ("styling_dock", "labeling_dock", "attribute_dock"):
                d = getattr(self, an, None)
                if d is None:
                    continue
                view._panel_state[an] = bool(d.isVisible())
                d.hide()
        except Exception:
            exc_note("_snapshot_global_panels @ ggis/ui/framework/regions/DockRegion.py:2653")
            pass
        finally:
            self.mw._panel_rebinding = False


    def _enforce_right_dock_tabs(self, reset_width=True):
        mw = self.mw
        try:
            all_docks = [w for w in mw.findChildren(QDockWidget)
                         if not w.isFloating()]
        except Exception:
            exc_note("_enforce_right_dock_tabs @ ggis/ui/framework/regions/DockRegion.py")
            return
        areas = (Qt.DockWidgetArea.LeftDockWidgetArea,
                 Qt.DockWidgetArea.RightDockWidgetArea,
                 Qt.DockWidgetArea.TopDockWidgetArea,
                 Qt.DockWidgetArea.BottomDockWidgetArea)
        right_first = None
        for area in areas:
            try:
                group = [w for w in all_docks
                         if mw.dockWidgetArea(w) == area]
            except Exception:
                exc_note("_enforce_right_dock_tabs @ ggis/ui/framework/regions/DockRegion.py")
                continue
            if not group:
                continue
            first = None
            if area == Qt.DockWidgetArea.RightDockWidgetArea:
                for cand in getattr(mw, "_right_docks", None) or []:
                    if cand in group:
                        first = cand
                        break
            if first is None:
                first = group[0]
            if area == Qt.DockWidgetArea.RightDockWidgetArea:
                right_first = first
            for d in group:
                if d is first:
                    continue
                try:
                    mw.tabifyDockWidget(first, d)
                except Exception:
                    exc_note("_enforce_right_dock_tabs @ ggis/ui/framework/regions/DockRegion.py")
        if reset_width and right_first is not None:
            try:
                mw.resizeDocks([right_first], [DOCK_W],
                               Qt.Orientation.Horizontal)
            except Exception:
                exc_note("_enforce_right_dock_tabs @ ggis/ui/framework/regions/DockRegion.py")


    def _rebind_tools(self, cv):
        mv = self.mw.current_map_view()
        tools = getattr(mv, "_tools", None) if mv is not None else None
        if not tools:
            return
        for t in tools.values():
            try:
                t.setCanvas(cv)
            except Exception:
                exc_note("_rebind_tools @ ggis/ui/framework/regions/DockRegion.py:2747")
                pass


    def _ensure_default_docks_visible(self):
        vh = getattr(self.mw, "view_host", None)
        if vh is not None and not vh.views():
            return
        cands = []
        _ld = getattr(self.mw, "_layer_dock_primary", None)
        if _ld is not None:
            cands.append(_ld)
        for n in ("browser_dock", "overview_dock",
                  "identify_dock", "toolbox_dock"):
            d = getattr(self.mw._map_dock_mgr, n, None)
            if d is not None:
                cands.append(d)
        d = getattr(self.mw, "log_dock", None)
        if d is not None:
            cands.append(d)
        cands += list(getattr(self.mw, "_right_docks", []) or [])
        cands = [d for d in cands if d is not None]
        if any(not d.isHidden() for d in cands):
            return
        if _ld is not None:
            try:
                _ld.show()
            except Exception:
                exc_note("_ensure_default_docks_visible @ ggis/ui/framework/regions/DockRegion.py:2783")
                pass
        _def = getattr(self.mw, "_default_visible", None)
        if _def is not None:
            try:
                _def.show()
                _def.raise_()
            except Exception:
                exc_note("_ensure_default_docks_visible @ ggis/ui/framework/regions/DockRegion.py:2790")
                pass


    def reset_layout(self):
        try:
            self.mw._qset.remove("window/geometry")
            self.mw._qset.remove("window/state")
            self.mw._qset.sync()
        except Exception:
            exc_note("reset_layout @ ggis/ui/framework/regions/DockRegion.py:2800")
            pass
        self.mw._layout_restored = True
        for d in [self.mw.layer_dock] + list(self.mw._right_docks):
            try:
                d.setFloating(False)
                d.show()
            except Exception:
                exc_note("reset_layout @ ggis/ui/framework/regions/DockRegion.py:2807")
                pass
        self.mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.mw.layer_dock)
        first = None
        for d in self.mw._right_docks:
            if first is None:
                self.mw.addDockWidget(
                    Qt.DockWidgetArea.RightDockWidgetArea, d)
                first = d
            else:
                self.mw.tabifyDockWidget(first, d)
        self._enforce_right_dock_tabs()
        for d in self.mw._right_docks:
            if d is not self.mw._default_visible:
                d.hide()
        try:
            self.mw._default_visible.raise_()
        except Exception:
            exc_note("reset_layout @ ggis/ui/framework/regions/DockRegion.py:2825")
            pass
        try:
            _w = max(320, int(self.mw.width()) // 10 * 10)
            _h = max(240, int(self.mw.height()) // 10 * 10)
            self.mw.resize(_w, _h)
        except Exception:
            exc_note("reset_layout @ ggis/ui/framework/regions/DockRegion.py:2835")
            self.mw.resize(1440, 900)
        self._apply_dock_widths()
        self._name_dock_tabbars()
        self._raise_grips()
        self.mw.show_message(_tr("窗口布局已重置为默认。"))




    def _build_edge_grips(self):
        self.mw._grips = []
        combos = (
            (Qt.Edge.LeftEdge,), (Qt.Edge.RightEdge,),
            (Qt.Edge.TopEdge,), (Qt.Edge.BottomEdge,),
            (Qt.Edge.LeftEdge, Qt.Edge.TopEdge),
            (Qt.Edge.RightEdge, Qt.Edge.TopEdge),
            (Qt.Edge.LeftEdge, Qt.Edge.BottomEdge),
            (Qt.Edge.RightEdge, Qt.Edge.BottomEdge),
        )
        for parts in combos:
            mask = parts[0]
            for p in parts[1:]:
                mask |= p
            grip = EdgeGrip(mask, self.mw)
            grip.raise_()
            self.mw._grips.append(grip)
        self._layout_edge_grips()


    def _layout_edge_grips(self):
        grips = getattr(self.mw, "_grips", None)
        if not grips:
            return
        w, h = self.mw.width(), self.mw.height()
        b = EDGE
        hid = self.mw.isMaximized() or self.mw.isFullScreen()
        for grip in grips:
            grip.setVisible(not hid)
            if hid:
                continue
            e = grip._edges
            x = y = 0
            cw, ch = w, h
            if e & Qt.Edge.LeftEdge:
                x, cw = 0, b
            elif e & Qt.Edge.RightEdge:
                x, cw = w - b, b
            if e & Qt.Edge.TopEdge:
                y, ch = 0, b
            elif e & Qt.Edge.BottomEdge:
                y, ch = h - b, b
            grip.setGeometry(x, y, cw, ch)


    def _wire_layer_dock(self, dock):
        self.mw.ctx.wiring.connect((dock.nodeActionRequested), (lambda *a: self.mw._forward_to_map_view("_on_tree_action", *a)), "layer_tree", rebindable=True)
        self.mw.ctx.wiring.connect((dock.legendActionRequested), (lambda *a: self.mw.ctx.svc("views")._on_view_method("_on_legend_action", *a)), "layer_tree", rebindable=True)
        try:
            from ggis.ui.views.map.map_layer import ggs_layer_clip
            dock.view.can_paste = lambda: bool(ggs_layer_clip())
        except Exception:
            exc_note("_wire_layer_dock @ ggis/ui/framework/regions/DockRegion.py:2933")
            pass
        try:
            self.mw.ctx.wiring.connect((dock.view.currentItemChanged), (lambda *_: self.mw.ctx.svc("actions").refresh_states()), "layer_tree", rebindable=True)
            self.mw.ctx.wiring.connect((dock.view.itemSelectionChanged), (lambda *_: self.mw.ctx.svc("actions").refresh_states()), "layer_tree", rebindable=True)
        except Exception:
            exc_note("_wire_layer_dock @ ggis/ui/framework/regions/DockRegion.py:2941")
            pass
        try:
            self.mw.ctx.wiring.connect((dock.view.currentItemChanged), (lambda *_: self.mw._forward_to_map_view(
                    "_sync_symbology_to_active")), "layer_tree", rebindable=True)
        except Exception:
            exc_note("_wire_layer_dock @ ggis/ui/framework/regions/DockRegion.py:2951")
            pass
        for _sig in ("currentItemChanged", "itemClicked", "itemActivated",
                     "itemSelectionChanged"):
            try:
                self.mw.ctx.wiring.connect((getattr(dock.view, _sig)), (lambda *_: self.mw.ribbon_region._sync_contextual_tabs()), "layer_tree", rebindable=True)
            except Exception:
                exc_note("_wire_layer_dock @ ggis/ui/framework/regions/DockRegion.py:2963")
                pass
        try:
            self.mw.ctx.wiring.connect((dock.view.currentItemChanged), (lambda *_: self.mw._map_dock_mgr._notify_profile_docks_layer_changed()), "layer_tree", rebindable=True)
        except Exception:
            exc_note("_wire_layer_dock @ ggis/ui/framework/regions/DockRegion.py:2970")
            pass


    def _make_layer_dock(self, map_title=None):
        d = GgsLayerTreeDock(_tr("图层"), self.mw)
        d.setObjectName("GgsLayersDock")
        self._wire_layer_dock(d)
        return d


    def _restore_layout(self):
        if getattr(self.mw, "_layout_restored", False):
            return
        self.mw._layout_restored = True
        try:
            self.mw._map_dock_mgr._ensure_lazy_panel_docks()
        except Exception:
            exc_note("_restore_layout @ ggis/ui/framework/regions/DockRegion.py:3001")
            pass
        q = getattr(self.mw, "_qset", None)
        if q is not None:
            try:
                q.remove("window/state")
                q.sync()
            except Exception:
                exc_note("_restore_layout @ ggis/ui/framework/regions/DockRegion.py:3014")
                pass
            geo = self.mw._pending_geo if hasattr(self.mw, "_pending_geo") \
                else q.value("window/geometry")
            if geo is not None:
                try:
                    self.mw.restoreGeometry(geo)
                except Exception:
                    exc_note("_restore_layout @ ggis/ui/framework/regions/DockRegion.py:3021")
                    pass
        self._enforce_right_dock_tabs(reset_width=False)
        self._name_dock_tabbars()
        self._raise_grips()
        try:
            self._ensure_default_docks_visible()
        except Exception:
            exc_note("_restore_layout @ ggis/ui/framework/regions/DockRegion.py:3032")
            pass
        try:
            self.apply_registry_dock_sizes()
        except Exception:
            exc_note("_restore_layout @ ggis/ui/framework/regions/DockRegion.py:3040")
            pass
        try:
            self._hook_dock_resize_save()
        except Exception:
            exc_note("_restore_layout @ ggis/ui/framework/regions/DockRegion.py:3045")
            pass




class GgsCanvasHost(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCanvasHost")
