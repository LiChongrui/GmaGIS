# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
from ggis.core.model.selection import GgsSelection
from PySide6.QtCore import QTimer

_log = logging.getLogger("gmagis")

from ggis.ui.features._hostdeps import (
                                        _tr,
                                        LEVEL_INFO,
                                        LEVEL_SUCCESS,
                                        LEVEL_CRITICAL,
                                        LEVEL_WARN,
)


class ViewCoord:

    def __init__(self, ctx):
        self.ctx = ctx
        self.mw = ctx.mw

    def dispatch_current(self, meth, *args, **kwargs):
        v = self._map_state()
        if v is None:
            return None
        fn = getattr(v, meth, None)
        if fn is None or not callable(fn):
            return None
        try:
            return fn(*args, **kwargs)
        except Exception:
            _log.exception("地图视图方法 %s 调用失败" % meth)

    def on_view_changed(self, view):
        self.mw._last_active_view_id = (
            str(getattr(view, "view_id", "")) if view is not None else None)
        kind = (str(getattr(view, "kind", "map") or "map")
                if view is not None else None)
        region = self.ctx.region("view")
        if region is None:
            return None
        return region.apply_view(kind, view)

    def _optimizing_notice(self, msg):
        from ggis.ui.features._hostdeps import GgsMsgBox
        GgsMsgBox.information(self.mw, _tr("GmaGIS"), msg)
        return None

    def create(self, kind):
        return self.open_view(kind)

    def open_view(self, kind, vid=None, payload=None, activate=True,
                  title=None, crs="", ask_crs=False):
        """视图添加唯一入口：任何新建/打开/工程恢复都必须经过这里，
        不允许旁路构造。机制层 ViewHost.add_view 只管容器增删；
        本门面负责统一构造序列：建视图对象 → 注册 dock/工具 →
        入容器 → 停靠归属更新 → 默认面板（激活时）。
        id 规则：map 显式 vid = 复用现有 → 复用 parked → 按 vid 重建，
        无 vid = 先复用任意 parked 地图视图，否则自动编号 map:{n}；
        layout/model 维持 layout:{id} / model:{id}（payload=布局对象/模型id）。
        视图范围（extent）不在此恢复——唯一恢复点在工程装载收尾
        finalize_views。"""
        k = str(kind or "").strip().lower()
        if k == "map":
            return self._open_map_view(
                vid=vid, activate=activate, title=title, crs=crs,
                ask_crs=ask_crs)
        if k == "layout":
            if payload is None:
                raise ValueError(_tr("布局视图必须指定布局对象"))
            return self._open_layout_view(payload, activate=bool(activate))
        if k == "model":
            if not payload:
                raise ValueError(_tr("模型视图必须指定模型"))
            return self._open_model_view(str(payload), activate=bool(activate))
        raise ValueError(_tr("未知视图类型") + ": " + str(kind))

    def _open_map_view(self, vid=None, activate=True, title=None, crs="",
                       ask_crs=False):
        """地图视图统一构造序列（新建/打开/工程恢复三合一）。
        dock 注册 + 工具供给 + 停靠归属 + 默认面板对每条路径一视同仁，
        杜绝“有的入口没 dock、有的没默认面板”的行为漂移。"""
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return None
        activate = bool(activate)
        if vid:
            vid = str(vid)
            v = vh.view(vid)
            if v is not None:
                # 复用现有壳：构造期传入的 title 是唯一权威（工程恢复时
                # = 文件里的视图名）。旧壳可能挂着上个工程的视图名，
                # 必须对齐，否则页签显示上个工程的名字。
                if title and str(title) != str(getattr(v, "title", "") or ""):
                    vh.rename_view(vid, str(title))
                if activate:
                    vh.activate(vid)
                return v
            pv = vh.parked_view(vid)
            if pv is not None:
                return self._revive_parked_map(pv, activate)
            if title is None:
                # 按文件 vid 重建（工程恢复）也必须有唯一标题：页签条在
                # add_view 时即同步 title，事后 rename 不再刷新旧值。
                # 视图名创建后即固定（用户数据），不走翻译。
                title = self.mw._unique_view_title("地图")
        else:
            for pv in list(getattr(vh, "_parked", {}).values()):
                if str(getattr(pv, "kind", "")) == "map":
                    return self._revive_parked_map(pv, activate)
            vid = "map:%d" % self._next_map_view_index()
            if title is None:
                title = self.mw._unique_view_title("地图")
            if not ask_crs:
                try:
                    from ggis.core.app import settings as _settings
                    _c = _settings.default_crs()
                    crs = (getattr(_c, "authid", lambda: "")()
                           if _c is not None else "") or ""
                except Exception:
                    exc_note("open_view @ ggis/ui/framework/services"
                             "/view_coord.py:default_crs")
                    crs = ""
        if ask_crs:
            _name, _crs = self._ask_new_map(title)
            if _name is None:
                return None
            if _name:
                title = _name
            crs = _crs or ""
        try:
            from ggis.ui.views.map.map_view import MapView
            v = MapView(None, vh, view_id=vid, title=title,
                        canvas_color=self.mw.ctx.svc(
                            "settings_ctl").canvas_bg_color())
            if crs:
                try:
                    v.canvas.setDestinationCrs(crs)
                except Exception:
                    exc_note("open_view @ ggis/ui/framework/services"
                             "/view_coord.py:crs")
            self.mw._register_map_view_layer_dock(v)
            self._provision_map_tools(v)
            vh.add_view(v, activate=activate)
        except Exception as e:
            exc_note("open_view @ ggis/ui/framework/services"
                     "/view_coord.py:build")
            if self.mw.isVisible():
                return self.mw._view_open_failed(
                    _tr("地图视图打开失败：{0}").format(e))
            # 启动期（窗口未显示）装载失败：不吞——直接抛，main 无捕获即退出。
            raise
        self.mw._update_map_view_parking()
        if activate and vh.current_view() is v:
            self._apply_map_default_panels(v)
        return v

    def _revive_parked_map(self, pv, activate):
        """parked 地图视图复活：dock 绑定从未注销，直接回容器。
        激活时统一给默认面板（旧 new_map_view 漏了这一步）。"""
        vh = getattr(self.mw, "view_host", None)
        vh.add_view(pv, activate=bool(activate))
        self.mw._update_map_view_parking()
        if activate and vh.current_view() is pv:
            self._apply_map_default_panels(pv)
        return pv

    def _ask_new_map(self, default_name):
        """新建地图对话框（原 new_map_view 内联逻辑收编）。
        返回 (名称, crs)；取消/失败返回 (None, "")。"""
        try:
            from ggis.ui.dialogs.new_map import GgsNewMapDialog
            default_crs = ""
            try:
                c = self.mw.current_view_crs()
                default_crs = (getattr(c, "authid", lambda: "")()
                               if c is not None else "") or ""
            except Exception:
                exc_note("open_view @ ggis/ui/framework/services"
                         "/view_coord.py:ask_default_crs")
            dlg = GgsNewMapDialog(self.mw, name=default_name,
                                  crs=default_crs)
            if not dlg.exec():
                return None, ""
            return (dlg.map_name() or ""), dlg.crs()
        except Exception as e:
            exc_note("open_view @ ggis/ui/framework/services"
                     "/view_coord.py:ask_dialog")
            if self.mw.isVisible():
                self.mw._view_open_failed(
                    _tr("新建地图失败：{0}").format(e))
            return None, ""

    def _apply_map_default_panels(self, v):
        try:
            self.mw.dock_region.apply_default_panels("map", v)
        except Exception:
            exc_note("open_view @ ggis/ui/framework/services"
                     "/view_coord.py:panels")
        # GgsMapCanvas 构造色写死 #1E242C；工程装载链会刷设置色，
        # 手工新建/复活的视图在此补刷（与打开工程观感一致）。
        try:
            self.mw.ctx.svc("settings_ctl").apply_canvas_color()
        except Exception:
            exc_note("open_view @ ggis/ui/framework/services"
                     "/view_coord.py:color")

    def apply_new_project_views(self, kinds):
        """新建工程的视图装载：与打开工程完全同一机制——apply_shell →
        retain_for_project 关闭现有工程的全部视图，再按 kinds 建视图壳。
        新建工程必须至少选择一个视图：kinds 为空直接报错，不兜底。
        当前仅支持 map（_ensure_view_shells 只会建地图壳，
        layout/model 尚不能入集）。"""
        if not kinds:
            raise ValueError(_tr("新建工程必须至少选择一个视图"))
        built = {}
        for k in kinds:
            key = str(k).strip().lower()
            if key == "map":
                built["map:1"] = []
            else:
                raise ValueError(_tr("新建工程暂不支持视图类型") + f": {k}")
        self.ctx.svc("projects").apply_shell(
            {"built_views": built, "view_meta": {}})
        return built

    def activate(self, view_id):
        vh = self.ctx.view_host
        if vh is None:
            return None
        v = vh.view(view_id)
        if v is not None:
            vh.setCurrentWidget(v)
        return v

    def close(self, view_id):
        return self.close_view(view_id)

    def close_view(self, vid, force=False):
        """视图关闭唯一门面：机制层 ViewHost.close_view（cleanup +
        park/delete）之后统一做状态栏卸载 / dock 注销 / ribbon 注销。
        parked 视图（隐藏保留）不注销 dock——复活时直接复用绑定。
        force=True：工程装载语义——无视"至少保留一个"约束且不 park，
        清理必然完整执行。"""
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return False
        ok = vh.close_view(vid, force=bool(force))
        if ok and vh.parked_view(vid) is None:
            try:
                mv = getattr(self.mw, "_mounted_status_view", None)
                if mv is not None and str(getattr(mv, "view_id", "")) == str(vid):
                    self.mw.status_region._unmount_view_status(mv)
            except Exception:
                exc_note("close_view @ ggis/ui/framework/services/view_coord.py:status")
            try:
                self.mw._unregister_view_docks(vid)
            except Exception:
                exc_note("close_view @ ggis/ui/framework/services/view_coord.py:docks")
            try:
                self.mw.ctx.region("dock")._dispose_view_ribbon(vid)
            except Exception:
                exc_note("close_view @ ggis/ui/framework/services/view_coord.py:ribbon")
        return ok

    def _close_view(self, vid):
        return self.close_view(vid)




    def _init_views(self):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return
        try:
            self.mw.ctx.wiring.connect((vh.viewChanged), (self._on_view_changed), "view_host")
            self.mw.ctx.wiring.connect((vh.viewsChanged), (self.mw.view_region._sync_view_tabs), "view_host")
        except Exception:
            exc_note("_init_views @ ggis/ui/framework/services/view_coord.py:174")
            pass
        tabs = getattr(self.mw, "view_tabs", None)
        if tabs is not None:
            try:
                self.mw.ctx.wiring.connect((tabs.viewRequested), (self.mw._on_view_tab_requested), "view_tab")
                self.mw.ctx.wiring.connect((tabs.createRequested), (self._on_view_create), "view_tab")
                self.mw.ctx.wiring.connect((tabs.closeRequested), (self.mw._on_view_tab_close), "view_tab")
                self.mw.ctx.wiring.connect((tabs.closeOthersRequested), (self.mw._on_view_tab_close_others), "view_tab")
                try:
                    self.mw.ctx.wiring.connect((tabs.closeAllRequested), (self.mw._on_view_tab_close_all), "view_tab")
                except Exception:
                    exc_note("_init_views @ ggis/ui/framework/services/view_coord.py:188")
                    pass
                self.mw.ctx.wiring.connect((tabs.renameRequested), (self.mw._on_view_tab_rename), "view_tab")
                self.mw.ctx.wiring.connect((tabs.propsRequested), (self._on_view_props), "view_tab")
                self.mw.ctx.wiring.connect((tabs.orderChanged), (self.mw._on_view_tabs_reordered), "view_tab")
            except Exception:
                exc_note("_init_views @ ggis/ui/framework/services/view_coord.py:195")
                pass
        self.mw.view_region._sync_view_tabs()
        self._on_view_changed(vh.current_view())


    def _next_map_view_index(self):
        vh = getattr(self.mw, "view_host", None)
        max_n = 0
        if vh is not None:
            for v in vh.views():
                vid = str(getattr(v, "view_id", "") or "")
                if vid.startswith("map:") and vid[4:].isdigit():
                    max_n = max(max_n, int(vid[4:]))
        return max_n + 1


    def _activate_map_view(self, view):
        cv = getattr(view, "canvas", None)
        if cv is None:
            return
        old_cv = getattr(self.mw, "_bound_canvas", None)
        active_tool = None
        if old_cv is not None:
            try:
                active_tool = old_cv.mapTool()
            except Exception:
                exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:235")
                pass
        if cv is not old_cv:
            self.mw._bind_canvas_signals(cv)
            try:
                if (getattr(cv, "_proc", None) is None
                        and not getattr(cv, "_proc_failed", False)):
                    _new_proc = cv._ensure_proc()
                    if _new_proc is not None:
                        _new_proc.start()
            except Exception:
                exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:254")
                pass
            if not getattr(cv, "_nav_checked_wired", False):
                try:
                    self.mw.ctx.wiring.connect((cv.mapToolSet), (lambda _t: QTimer.singleShot(
                            0, self._map_state()._ensure_nav_checked)), "canvas", rebindable=True)
                    cv._nav_checked_wired = True
                except Exception:
                    exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:265")
                    pass
            try:
                _ms = self._map_state()
                _old = getattr(self.mw, "_nav_toggle_wired_to", None)
                if _old is not _ms:
                    _acts = list(self.mw.nav_group.actions())
                    if _old is not None:
                        for _a in _acts:
                            self.mw.ctx.wiring.disconnect(
                                (_a.toggled), (_old._on_nav_action_toggled),
                                "nav_toggle")
                    if _ms is not None:
                        for _a in _acts:
                            self.mw.ctx.wiring.connect(
                                (_a.toggled), (_ms._on_nav_action_toggled),
                                "nav_toggle")
                        QTimer.singleShot(0, _ms._ensure_nav_checked)
                    self.mw._nav_toggle_wired_to = _ms
            except Exception:
                exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:280")
                pass
            if self.mw._drop is not None:
                try:
                    cv.installEventFilter(self.mw._drop)
                except Exception:
                    exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:272")
                    pass
            try:
                if getattr(self.mw._map_dock_mgr, "overview", None) is not None:
                    self.mw._map_dock_mgr.overview.set_canvas(cv)
            except Exception:
                exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:279")
                pass
            # 激活即补发渲染：后台视图的渲染请求可能因子进程未热被挂起、
            # 自动重试耗尽后停发——切页签不算画布交互，不会自动重发，
            # 用户看到的正是"切过去一直空白（像被隐藏）"。激活时画布有
            # 未完成渲染意图（挂起中 / 帧未 settle / 从未渲染）就补发；
            # _kick_render 内部先查缓存帧，有缓存不浪费重渲染。
            try:
                _held = bool(getattr(cv, "_dirty", False))
                if not _held and hasattr(cv, "_proc_settle_held"):
                    try:
                        _held = bool(cv._proc_settle_held())
                    except Exception:
                        exc_note("_activate_map_view @ ggis/ui/framework"
                                 "/services/view_coord.py:settle")
                        _held = False
                if _held and hasattr(cv, "_kick_render"):
                    cv._kick_render()
            except Exception:
                exc_note("_activate_map_view @ ggis/ui/framework/services"
                         "/view_coord.py:kick")
                pass
        GgsSelection.set_active(cv.selection())
        self.mw.ctx.region("dock")._rebind_tools(cv)
        _new_tool = self._tool_for_view(view, active_tool)
        try:
            cv.setMapTool(_new_tool)
        except Exception:
            exc_note("_activate_map_view @ ggis/ui/framework/services/view_coord.py:296")
            pass
        self.mw._update_map_view_parking()


    def _tool_for_view(self, view, tool):
        if tool is None or view is None:
            return None
        key = None
        try:
            vh = getattr(self.mw, "view_host", None)
            views = list(vh.views()) if vh is not None else []
        except Exception:
            exc_note("_tool_for_view @ ggis/ui/framework/services/view_coord.py:319")
            views = []
        for v in views:
            try:
                for k, t in (getattr(v, "_tools", None) or {}).items():
                    if t is tool:
                        key = k
                        break
            except Exception:
                exc_note("_tool_for_view @ ggis/ui/framework/services/view_coord.py:327")
                continue
            if key:
                break
        if not key:
            return None
        return (getattr(view, "_tools", None) or {}).get(key)


    def _on_view_changed(self, view):
        return self.mw.ctx.svc("views").on_view_changed(view)


    def _on_view_create(self, kind):
        k = str(kind or "").lower()
        act_name = {"layout": "new_layout_view",
                    "model": "model_builder",
                    "map": "new_map_view"}.get(k, "")
        a = self.mw.ctx.svc("actions")._acts.get(act_name) if act_name else None
        if a is not None:
            a.trigger()
            return None
        if k == "layout":
            return self.mw.ctx.svc("views").new_layout_view()
        if k == "model":
            return self.mw.ctx.svc("views").new_model_view()
        if k == "map":
            return self.mw.new_map_view()
        return None


    def open_map_view(self, activate=True):
        # 薄壳：统一入口（vid="map" 保留"复用现有→复用 parked→重建"语义）。
        return self.open_view("map", vid="map", activate=bool(activate))


    def _on_view_props(self, vid):
        vh = getattr(self.mw, "view_host", None)
        v = vh.view(vid) if vh is not None else None
        if v is None:
            return
        try:
            from ggis.ui.dialogs.view_props import GgsViewPropsDialog
            dlg = GgsViewPropsDialog(
                str(getattr(v, "title", "") or ""),
                str(getattr(v, "kind", "") or ""),
                str(vid or ""),
                str(getattr(v, "icon_name", "") or ""),
                self)
            ok = bool(dlg.exec())
        except Exception:
            _log.exception("视图：属性对话框失败")
            return
        new = dlg.name() if ok else ""
        if not new or new == str(getattr(v, "title", "") or ""):
            return
        try:
            vh.rename_view(vid, new)
        except Exception:
            _log.exception("视图：重命名失败")
            return
        self.mw.view_region._sync_view_tabs()






    def _provision_map_tools(self, view):
        if view is None:
            return
        try:
            if getattr(view, "_host", None) is None:
                view._host = self.mw
        except Exception:
            exc_note("_provision_map_tools @ ggis/ui/framework/services/view_coord.py:521")
            pass
        try:
            fb = getattr(self.mw, "_map_state_fallback", None) or {}
            for k in ("_tools", "_edit_sessions"):
                val = fb.get(k)
                if val:
                    setattr(view, k, val)
                    fb[k] = None
            try:
                if not view.tools():
                    self._clone_map_tools_into(view)
            except Exception:
                exc_note("_provision_map_tools @ ggis/ui/framework/services/view_coord.py:540")
                pass
            try:
                if not getattr(view, "_async_wired", False):
                    view._init_async_load()
            except Exception:
                exc_note("_provision_map_tools @ ggis/ui/framework/services/view_coord.py:549")
                pass
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception("为地图视图准备工具失败")


    def _clone_map_tools_into(self, view):
        if view is None:
            return
        cv = getattr(view, "canvas", None)
        if cv is None:
            return
        try:
            tools = view.tools()
            if tools:
                return
            view._build_map_tools()
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception("为地图视图建工具失败")


    def _zoom_view_to_layers(self, view):
        if view is None:
            return False
        try:
            lt = view.layer_tree()
            if lt is None:
                return False
            _layers = list(lt.layers())
            if not _layers:
                return False
            _cv = getattr(view, "canvas", None)
            if _cv is None:
                return False
            try:
                _dst = _cv.effectiveCrs()
            except Exception:
                exc_note("_zoom_view_to_layers @ ggis/ui/framework/services/view_coord.py:616")
                _dst = None
            _ext = None
            for _lyr in _layers:
                try:
                    _e = view._layer_extent(_lyr, _dst)
                except Exception:
                    exc_note("_zoom_view_to_layers @ ggis/ui/framework/services/view_coord.py:622")
                    _e = None
                if _e is None or _e.is_empty():
                    try:
                        _e = _lyr.extent()
                    except Exception:
                        exc_note("_zoom_view_to_layers @ ggis/ui/framework/services/view_coord.py:629")
                        _e = None
                if _e is None or _e.is_empty():
                    continue
                if _ext is None:
                    _ext = _e
                else:
                    _ext.combine_extent_with(_e)
            if _ext is not None and not _ext.is_empty():
                _cv.zoomToExtent(_ext)
                return True
        except Exception:
            exc_note("_zoom_view_to_layers @ ggis/ui/framework/services/view_coord.py:640")
            pass
        return False


    def _find_layer_in_view(self, view, name):
        if not name:
            return None
        try:
            lt = view.layer_tree()
            if lt is not None:
                for _e in list(lt.entries()):
                    _lyr = _e[0] if isinstance(_e, (tuple, list)) else _e
                    try:
                        if str(getattr(_lyr, "name", lambda: "")() or "") == str(name):
                            return _lyr
                    except Exception:
                        exc_note("_find_layer_in_view @ ggis/ui/framework/services/view_coord.py:662")
                        pass
        except Exception:
            exc_note("_find_layer_in_view @ ggis/ui/framework/services/view_coord.py:664")
            pass
        try:
            for _lyr in list(self.mw.ctx.project.layers()):
                try:
                    if str(getattr(_lyr, "name", lambda: "")() or "") == str(name):
                        return _lyr
                except Exception:
                    exc_note("_find_layer_in_view @ ggis/ui/framework/services/view_coord.py:672")
                    pass
        except Exception:
            exc_note("_find_layer_in_view @ ggis/ui/framework/services/view_coord.py:674")
            pass
        return None


    def toggle_toolbox(self):
        self.mw.ctx.region("dock")._toggle_dock_action(getattr(self.mw._map_dock_mgr, "toolbox_dock", None),
                                 "toolbox")


    def _on_view_method(self, meth, *args, **kwargs):
        return self.mw.ctx.svc("views").dispatch_current(meth, *args, **kwargs)






    def _restore_map_view(self, vid, title=None):
        # 薄壳：工程装载统一走 open_view（不激活、按文件 vid 重建/复用）。
        # title 来自工程文件 view_meta——构造期即带正确标题，页签首次同步即对。
        # 视图范围（extent）不在此恢复，唯一恢复点在 finalize_views。
        return self.open_view("map", vid=str(vid),
                              title=title, activate=False)


    @staticmethod
    def _close_progress(prog):
        if prog is None:
            return
        try:
            prog.close()
            prog.deleteLater()
        except Exception:
            exc_note("_close_progress @ ggis/ui/framework/services/view_coord.py:764")
            pass


    def _map_state(self):
        try:
            vh = getattr(self.mw, "view_host", None)
            cur = vh.current_view() if vh is not None else None
            if cur is not None and str(getattr(cur, "kind", "")) == "map":
                return cur
        except Exception:
            exc_note("_map_state @ ggis/ui/framework/services/view_coord.py:780")
            pass
        return None


    def _map_state_attr(self, name, fallback_factory):
        v = self._map_state()
        if v is not None:
            try:
                return getattr(v, name)
            except Exception:
                exc_note("_map_state_attr @ ggis/ui/framework/services/view_coord.py:800")
                pass
        fb = getattr(self.mw, "_map_state_fallback", None)
        if fb is None:
            fb = {}
            self.mw._map_state_fallback = fb
        obj = fb.get(name)
        if obj is None:
            obj = fallback_factory()
            fb[name] = obj
        return obj









    def _close_all_model_views(self):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            self.mw._model_parked = {}
            return
        for v in vh.views():
            if str(getattr(v, "kind", "")) != "model":
                try:
                    vh.activate(v.view_id)
                except Exception:
                    exc_note("_close_all_model_views @ ggis/ui/framework/services/view_coord.py:844")
                    pass
                break
        self.mw._resetting_models = True
        try:
            for v in list(vh.views()):
                if str(getattr(v, "kind", "")) == "model":
                    try:
                        self.close_view(v.view_id)
                    except Exception:
                        exc_note("_close_all_model_views @ ggis/ui/framework/services/view_coord.py:853")
                        pass
        finally:
            self.mw._resetting_models = False
        self.mw._model_parked = {}


    def layouts(self):
        try:
            return self.mw.ctx.project.layouts()
        except Exception:
            exc_note("layouts @ ggis/ui/framework/services/view_coord.py:864")
            return []


    def current_layout(self):
        lays = self.layouts()
        return lays[-1] if lays else None


    def _new_layout_defaults(self, name=""):
        from ggis.core.model.layout_model import Layout, ORIENTATION_LANDSCAPE
        return Layout(name=name or _tr("布局"),
                      page="A4", orientation=ORIENTATION_LANDSCAPE,
                      margins_mm=(10, 10, 10, 10), dpi=300)


    def _unique_layout_name(self, base=_tr("布局")):
        names = set()
        try:
            for lay in self.layouts():
                names.add(str(getattr(lay, "name", "") or ""))
        except Exception:
            exc_note("_unique_layout_name @ ggis/ui/framework/services/view_coord.py:913")
            pass
        if base not in names:
            return base
        i = 1
        while i < 10000:
            cand = "{0}{1}".format(base, i)
            if cand not in names:
                return cand
            i += 1
        return base

    def new_layout(self):
        # 布局视图暂不可用：交互入口统一提示，实现保留待恢复；
        # 工程读盘恢复走 open_layout_view，不受影响。
        return self._optimizing_notice(_tr("布局视图正在优化"))
        lay = self._new_layout_defaults(name=self._unique_layout_name())
        self.mw.ctx.project.add_layout(lay)
        return self.open_layout(lay)


    def new_layout_view(self):
        # 同上：布局视图暂不可用。
        return self._optimizing_notice(_tr("布局视图正在优化"))
        try:
            from ggis.ui.views.layout.new_layout import GgsNewLayoutDialog
            unit = ""
            try:
                lays = self.layouts()
                if lays:
                    unit = str(getattr(lays[-1], "unit", "") or "")
            except Exception:
                exc_note("new_layout_view @ ggis/ui/framework/services/view_coord.py:967")
                unit = ""
            dlg = GgsNewLayoutDialog(self.mw, unit=unit or "mm",
                                     name=self._unique_layout_name())
            if not dlg.exec():
                return None
            lay = dlg.make_layout()
        except Exception as e:
            self.mw.show_message(_tr("新建布局失败：{0}").format(e), LEVEL_WARN)
            return None
        try:
            self.mw.ctx.project.add_layout(lay)
        except Exception as e:
            self.mw.show_message(_tr("新建布局失败：{0}").format(e), LEVEL_WARN)
            return None
        return self.open_layout_view(lay)


    def open_layout_view(self, layout=None, activate=True):
        # 薄壳：统一入口。payload=布局对象，必须给（不再自动创建）。
        return self.open_view("layout", payload=layout,
                              activate=bool(activate))

    def _open_layout_view(self, lay, activate=True):
        """布局视图统一构造序列（原 open_layout_view 本体收编）。
        lay 必须是已有布局对象——ensure_layout 自动创建兜底已废除，
        那是往工程里塞空布局的根源。"""
        if lay is None:
            raise ValueError(_tr("布局视图必须指定布局对象"))
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return self.mw._view_open_failed(
                _tr("布局视图打开失败：{0}").format(
                    _tr("视图容器或当前布局不可用")))
        try:
            from ggis.ui.views.layout.layout_view import LayoutViewPage, layout_view_id
        except Exception as e:
            exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1009")
            return self.mw._view_open_failed(
                _tr("布局视图打开失败：{0}").format(e))
        vid = layout_view_id(lay)
        exist = vh.view(vid)
        if exist is not None:
            if activate:
                vh.activate(vid)
            return exist
        try:
            from ggis.ui.views.layout.workspace import GgsLayoutWorkspace
            dark = bool(self.mw.canvas._is_dark_bg())
        except Exception:
            exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1021")
            dark = True
        if getattr(self.mw, "_layout_opening", False):
            return None
        self.mw._layout_opening = True
        _busy = None
        try:
            from ggis.ui.dialogs import busy as _busy_mod
            _busy_mod.show_busy(
                self.mw, _tr("布局视图"),
                _tr("正在加载布局「{0}」…").format(lay.name))
            _busy = _busy_mod
        except Exception:
            exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1041")
            _busy = None
        try:
            try:
                ws = GgsLayoutWorkspace(
                    self.mw.ctx.project, lay, vh, dark_bg=dark,
                    map_extent=self.mw._forward_to_map_view(
                        "_extent"),
                    map_crs=self.mw.current_view_crs(), embedded=True,
                    ribbon=getattr(self.mw, "ribbon", None), window=self.mw,
                    view_id=vid)
            except Exception as e:
                exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1055")
                return self.mw._view_open_failed(
                    _tr("布局视图打开失败：{0}").format(e))
            try:
                self.mw.ctx.wiring.connect((ws.exported), (self._on_layout_exported), "layout", rebindable=True)
            except Exception:
                exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1060")
                pass
            try:
                self.mw.ctx.wiring.connect((ws.layoutDuplicated), (self._on_layout_duplicated), "layout", rebindable=True)
            except Exception:
                exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1065")
                pass
            page = LayoutViewPage(ws, lay, vh)
            vh.add_view(page, activate=activate)
            if _busy is not None:
                try:
                    _busy.pump()
                except Exception:
                    exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1074")
                    pass
        finally:
            self.mw._layout_opening = False
            if _busy is not None:
                try:
                    _busy.hide_busy()
                except Exception:
                    exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1081")
                    pass
        self.mw.show_message(_tr("布局「{0}」：{1} 个页面元素").format(
            lay.name, len(lay.items)), LEVEL_INFO)
        try:
            if not list(lay.items or []):
                self.mw.show_message(
                    _tr("布局「{0}」里还没有页面元素").format(lay.name),
                    LEVEL_INFO)
        except Exception:
            exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1095")
            pass
        if activate and vh.current_view() is page:
            try:
                self.mw.dock_region.apply_default_panels("layout", page)
            except Exception:
                exc_note("open_layout_view @ ggis/ui/framework/services/view_coord.py:1103")
                pass
        return page




    def open_layout(self, layout=None):
        # 布局视图暂不可用：交互入口统一提示，实现保留待恢复。
        return self._optimizing_notice(_tr("布局视图正在优化"))
        return self.open_view("layout", payload=layout)


    def open_layout_window(self, layout=None):
        # 同上：布局视图暂不可用。
        return self._optimizing_notice(_tr("布局视图正在优化"))
        if layout is None:
            raise ValueError(_tr("布局视图必须指定布局对象"))
        lay = layout
        from ggis.ui.views.layout.workspace import GgsLayoutDialog
        try:
            dark = bool(self.mw.canvas._is_dark_bg())
        except Exception:
            exc_note("open_layout_window @ ggis/ui/framework/services/view_coord.py:1131")
            dark = True
        try:
            dlg = GgsLayoutDialog(self.mw.ctx.project, lay, self.mw, dark_bg=dark,
                                  map_extent=self.mw._forward_to_map_view(
                                      "_extent"),
                                  map_crs=self.mw.current_view_crs())
            self.mw.ctx.wiring.connect((dlg.exported), (self._on_layout_exported), "layout", rebindable=True)
            dlg.exec()
        except Exception as e:
            self.mw.show_message(_tr("布局设计器打开失败：{0}").format(e),
                              LEVEL_WARN)
            return lay
        n = len(lay.items)
        self.mw.show_message(_tr("布局「{0}」：{1} 个页面元素").format(
            lay.name, n), LEVEL_INFO)
        return lay


    def _on_layout_exported(self, result):
        if result is None:
            return
        if getattr(result, "ok", False):
            self.mw.show_message(_tr("出图完成：{0}").format(
                result.summary()), LEVEL_SUCCESS)
            for w in getattr(result, "warnings", []) or []:
                self.mw.show_message(_tr("出图提示：{0}").format(w), LEVEL_WARN)
        else:
            self.mw.show_message(_tr("出图失败：{0}").format(
                getattr(result, "error", "")), LEVEL_CRITICAL)
        try:
            self.mw.log_dock.append(_tr("出图") + " · " + result.summary())
        except Exception:
            exc_note("_on_layout_exported @ ggis/ui/framework/services/view_coord.py:1164")
            pass


    def _on_layout_duplicated(self, lay):
        if lay is None:
            return None
        try:
            self.mw.ctx.project.add_layout(lay)
        except Exception as e:
            self.mw.show_message(_tr("复制布局失败：{0}").format(e), LEVEL_WARN)
            return None
        page = self.open_layout_view(lay)
        try:
            self.mw.show_message(_tr("已复制布局：{0}").format(lay.name), LEVEL_INFO)
        except Exception:
            exc_note("_on_layout_duplicated @ ggis/ui/framework/services/view_coord.py:1184")
            pass
        return page


    def export_layout(self, fmt="pdf", path=""):
        # 出图功能依赖布局视图，随布局视图一并暂停；出图只作用于已有布局，
        # 不再自动创建（ensure_layout 已废除）。
        return self._optimizing_notice(_tr("布局视图正在优化"))
        from ggis.ui.views.layout import exporter as EX
        lay = self.current_layout()
        if lay is None:
            raise ValueError(_tr("布局视图必须指定布局对象"))
        if fmt == "print":
            self.open_layout_window(lay)
            return None
        if not path:
            from ggis.common.base.dialog import GgsFileDialog
            flt = {"pdf": "PDF (*.pdf)", "svg": "SVG (*.svg)"}.get(
                fmt, "PNG 图片 (*.png);;JPG 图片 (*.jpg);;TIFF 图片 (*.tif)")
            ext = {"pdf": "pdf", "svg": "svg"}.get(fmt, "png")
            path, _f = GgsFileDialog.getSaveFileName(
                self, _tr("导出") + str(fmt).upper(),
                "%s.%s" % (lay.name, ext), flt)
            if not path:
                return None
        r = EX.export_layout(lay, path, self.mw.ctx.project,
                             dpi=float(lay.dpi or 300))
        if hasattr(r, "on_done"):
            self.mw._export_task = r
            self.mw.show_message(_tr("出图中…"), LEVEL_INFO)
            r.on_done(lambda ev: self._on_layout_exported(ev.get("result")))
            r.on_fail(lambda ev: self._on_layout_export_failed(ev))
            return r
        self._on_layout_exported(r)
        return r


    def _on_layout_export_failed(self, ev):
        self.mw.show_message(
            _tr("出图失败：{0}").format(ev.get("error")), LEVEL_CRITICAL)
        try:
            self.mw.log_dock.append(str(ev.get("traceback") or ev.get("error")))
        except Exception:
            exc_note("_on_layout_export_failed @ ggis/ui/framework/services/view_coord.py:1229")
            pass




    def new_model_view(self, activate=True):
        # 模型管理器视图暂不可用：交互入口统一提示，实现保留待恢复；
        # 工程读盘恢复走 restore_model_view，不受影响。
        return self._optimizing_notice(_tr("模型管理器视图正在优化"))
        parked = getattr(self.mw, "_model_parked", {}) or {}
        if parked:
            # 复用最近 parked 的工作区（沿用旧语义：不弹命名框）。
            _mid = next(reversed(parked))
            return self.open_view("model", payload=_mid,
                                  activate=bool(activate))
        try:
            from ggis.common.base.dialog import GgsInputDialog
            _name, _ok = GgsInputDialog.getText(
                self.mw, _tr("新建模型构建器"), _tr("视图名称："),
                text=_tr("模型构建器"))
        except Exception:
            exc_note("new_model_view @ ggis/ui/framework/services/view_coord.py")
            _name, _ok = ("", False)
        if not _ok or not str(_name or "").strip():
            return None
        title = str(_name).strip()
        _mid = self._next_model_id()
        try:
            self.mw.ctx.project.add_model(_mid, title)
        except Exception:
            exc_note("new_model_view @ ggis/ui/framework/services/view_coord.py")
        # 构造 / parked 复活 / 默认面板统一走 open_view，不再旁路。
        return self.open_view("model", payload=_mid,
                              activate=bool(activate))


    def _next_model_id(self):
        import uuid
        for _ in range(20):
            _mid = uuid.uuid4().hex[:10]
            if self.mw.ctx.project.model_by_id(_mid) is None:
                return _mid
        return uuid.uuid4().hex

    def restore_model_view(self, mid, activate=False):
        # 薄壳：统一入口。
        return self.open_view("model", payload=mid, activate=bool(activate))

    def _open_model_view(self, mid, activate=True):
        """模型视图统一构造序列（原 restore_model_view 本体收编）。
        mid 必须是工程里已有的模型 id——不再允许无模型的旁路构造。"""
        vh = getattr(self.mw, "view_host", None)
        mid = str(mid or "")
        if not mid:
            raise ValueError(_tr("模型视图必须指定模型"))
        if vh is None:
            return None
        vid = "model:%s" % mid
        exist = vh.view(vid)
        if exist is not None:
            if activate:
                vh.activate(vid)
            return exist
        entry = self.mw.ctx.project.model_by_id(mid)
        if entry is None:
            raise ValueError(
                _tr("工程中不存在指定的模型") + ": " + mid)
        parked = getattr(self.mw, "_model_parked", None)
        ws = parked.pop(mid, None) if isinstance(parked, dict) else None
        try:
            from ggis.ui.views.model.model_view import ModelViewPage
        except Exception as e:
            exc_note("restore_model_view @ ggis/ui/framework/services/view_coord.py:1367")
            return self.mw._view_open_failed(
                _tr("模型构建器打开失败：{0}").format(e))
        if ws is None:
            try:
                from ggis.ui.panels.model_builder import GgsModelBuilderWorkspace
                ws = GgsModelBuilderWorkspace(
                    None, vh, embedded=True, window=self.mw,
                    ribbon=getattr(self.mw, "ribbon", None), model_id=mid,
                    view_id=vid)
            except Exception as e:
                exc_note("restore_model_view @ ggis/ui/framework/services/view_coord.py:1377")
                return self.mw._view_open_failed(
                    _tr("模型构建器打开失败：{0}").format(e))
            try:
                ws.load_from_project()
                ws.reload_layers()
            except Exception:
                exc_note("restore_model_view @ ggis/ui/framework/services/view_coord.py:1383")
                pass
        title = str((entry or {}).get("name") or "") or _tr("模型")
        try:
            page = ModelViewPage(ws, vh, title=title, view_id=vid)
            vh.add_view(page, activate=bool(activate))
            return page
        except Exception as e:
            exc_note("restore_model_view @ ggis/ui/framework/services/view_coord.py:1390")
            return self.mw._view_open_failed(
                _tr("模型构建器打开失败：{0}").format(e))


    def _park_model_workspace(self, ws):
        if ws is None:
            return
        _mid = getattr(ws, "model_id", None)
        if not _mid:
            return
        try:
            ws.hide()
        except Exception:
            exc_note("_park_model_workspace @ ggis/ui/framework/services/view_coord.py:1418")
            pass
        try:
            ws.setParent(self.mw)
        except Exception:
            exc_note("_park_model_workspace @ ggis/ui/framework/services/view_coord.py:1422")
            pass
        self.mw._model_parked[str(_mid)] = ws


    def _model_workspace(self):
        vh = getattr(self.mw, "view_host", None)
        if vh is not None:
            _cv = vh.current_view()
            if _cv is not None and str(getattr(_cv, "kind", "")) == "model":
                _ws = getattr(_cv, "workspace", None)
                if _ws is not None:
                    return _ws
        parked = getattr(self.mw, "_model_parked", {}) or {}
        for _ws in parked.values():
            if _ws is not None:
                return _ws
        return None


    def _reload_model_builder(self):
        vh = getattr(self.mw, "view_host", None)
        _wss = []
        if vh is not None:
            for v in vh.views():
                if str(getattr(v, "kind", "")) == "model":
                    _ws = getattr(v, "workspace", None)
                    if _ws is not None:
                        _wss.append(_ws)
        parked = getattr(self.mw, "_model_parked", {}) or {}
        for _ws in parked.values():
            if _ws is not None:
                _wss.append(_ws)
        for _w in _wss:
            if not hasattr(_w, "load_from_project"):
                continue
            try:
                _w.load_from_project()
                _w.reload_layers()
            except Exception:
                exc_note("_reload_model_builder @ ggis/ui/framework/services/view_coord.py:1477")
                pass

