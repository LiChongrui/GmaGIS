from ggis.common.util.exc_report import exc_note

import logging

from ggis.core.app import i18n

_log = logging.getLogger("gmagis")
_tr = i18n.tr


class GgsViewRegion:

    def __init__(self, mw):
        self.mw = mw

    def build(self, tick=None):
        mw = self.mw
        dock = mw.ctx.region("dock")
        dock._build_view_host()
        if tick:
            tick("正在准备视图区域…")
        dock._build_edge_grips()
        if tick:
            tick("正在准备视图区域…")
        mw.ctx.svc("views")._init_views()

    def _view_docks_of_kind(self, kind):
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return []
        out = []
        for v in vh.views():
            if str(getattr(v, "kind", "")) != kind:
                continue
            out.extend(self.mw._view_docks.get(str(v.view_id), []))
        return out

    def _sync_view_tabs(self, *_):
        tabs = getattr(self.mw, "view_tabs", None)
        vh = getattr(self.mw, "view_host", None)
        if tabs is None or vh is None:
            return
        items = [(v.view_id, v.title, bool(getattr(v, "closable", True)),
                  str(getattr(v, "icon_name", "") or ""))
                 for v in vh.views()]
        cur = vh.current_view()
        try:
            tabs.set_views(items, cur.view_id if cur is not None else "")
        except Exception:
            exc_note("_sync_view_tabs @ ggis/ui/framework/regions/ViewRegion.py:91")
            pass
        try:
            if hasattr(tabs, "setVisible"):
                tabs.setVisible(bool(items))
        except Exception:
            exc_note("_sync_view_tabs @ ggis/ui/framework/regions/ViewRegion.py:97")
            pass

    def _apply_zero_view_state(self):
        try:
            vh = getattr(self.mw, "view_host", None)
            if vh is not None:
                vh.setVisible(False)
        except Exception:
            exc_note("_apply_zero_view_state @ ggis/ui/framework/regions/ViewRegion.py:111")
            pass
        try:
            vt = getattr(self.mw, "view_tabs", None)
            if vt is not None:
                vt.setVisible(False)
        except Exception:
            exc_note("_apply_zero_view_state @ ggis/ui/framework/regions/ViewRegion.py:117")
            pass
        try:
            rib = getattr(self.mw, "ribbon", None)
            if rib is not None:
                for i in range(rib.tabs.count()):
                    d = None
                    try:
                        d = rib.tabs.tabData(i)
                    except Exception:
                        exc_note("_apply_zero_view_state @ ggis/ui/framework/regions/ViewRegion.py:133")
                        pass
                    if isinstance(d, str) and d == "__always__":
                        rib.set_tab_visible(i, True)
                    else:
                        rib.set_tab_visible(i, False)
        except Exception:
            exc_note("_apply_zero_view_state @ ggis/ui/framework/regions/ViewRegion.py:139")
            pass
        # 零视图起始页：隐藏所有 dock（左侧图层树/日志、右侧 Browser 等）。
        # 用通用遍历，不依赖 _hide_all_right_docks 等并不存在的方法。
        try:
            from PySide6.QtWidgets import QDockWidget
            for d in self.mw.findChildren(QDockWidget):
                try:
                    d.hide()
                except Exception:
                    exc_note("_apply_zero_view_state hide dock")
        except Exception:
            exc_note("_apply_zero_view_state @ ggis/ui/framework/regions/ViewRegion.py:144")
            pass
        try:
            _um = getattr(self.mw, "_unmount_view_status", None)
            if callable(_um):
                _um(getattr(self.mw, "_mounted_status_view", None))
        except Exception:
            exc_note("_apply_zero_view_state @ ggis/ui/framework/regions/ViewRegion.py:169")
            pass

    def _hide_other_kind_docks(self, keep_kind):
        for kind in ("map", "layout", "model"):
            if kind == str(keep_kind):
                continue
            try:
                for d in self._view_docks_of_kind(kind):
                    d.setVisible(False)
            except Exception:
                exc_note("_hide_other_kind_docks @ ggis/ui/framework/regions/ViewRegion.py:188")
                pass
        if str(keep_kind) != "map":
            try:
                self.mw._panel_rebinding = True
                for an in ("styling_dock", "labeling_dock", "attribute_dock"):
                    d = getattr(self.mw, an, None)
                    if d is not None:
                        d.setVisible(False)
            except Exception:
                exc_note("_hide_other_kind_docks @ ggis/ui/framework/regions/ViewRegion.py:200")
                pass
            finally:
                self.mw._panel_rebinding = False

    def apply_view(self, kind, view):
        mw = self.mw
        try:
            mw.ribbon_region._mark_ribbon_current()
        except Exception:
            exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:219")
            pass
        try:
            self._sync_view_tabs()
        except Exception:
            exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:224")
            pass
        if view is None:
            if getattr(mw, "_applying_project_ui", False):
                return
            try:
                mw._current_view_kind = None
                self._apply_zero_view_state()
            except Exception:
                _log.exception("零视图状态落实失败")
            return
        kind = str(kind or getattr(view, "kind", "map") or "map")
        mw._current_view_kind = kind
        if kind == "map":
            try:
                mw.ctx.svc("views")._activate_map_view(view)
            except Exception:
                exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:245")
                pass
            try:
                mw.dock_region._reorient_context_docks(view)
            except Exception:
                exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:250")
                pass
        try:
            mw.view_region._apply_view_chrome(kind, view)
            mw.ribbon_region._rebuild_view_tab(kind, view)
        except Exception:
            try:
                _log.exception(
                    "视图切换外壳更新失败 kind=%r view=%r",
                    kind, getattr(view, "view_id", None))
            except Exception:
                exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:263")
                pass
        try:
            mw.status_region._sync_status_for_view(kind, view)
        except Exception:
            exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:268")
            pass
        if kind == "layout":
            try:
                mw.ribbon_region._relink_shared_layout(view)
            except Exception:
                exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:275")
                pass
        if kind in ("layout", "model"):
            try:
                mw.ribbon_region._sync_view_app_menu(view)
            except Exception:
                exc_note("apply_view @ ggis/ui/framework/regions/ViewRegion.py:282")
                pass


    def _apply_view_chrome(self, kind, view=None):
        mw = self.mw
        k = str(kind)
        full = (k != "map")
        try:
            ev = getattr(mw, "empty_view", None)
            if ev is not None:
                ev.hide_empty()
        except Exception:
            exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:341")
            pass
        try:
            vh0 = getattr(mw, "view_host", None)
            if vh0 is not None:
                vh0.setVisible(True)
        except Exception:
            exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:352")
            pass
        try:
            vt = getattr(mw, "view_tabs", None)
            vh1 = getattr(mw, "view_host", None)
            if vt is not None and vh1 is not None and vh1.views():
                vt.setVisible(True)
        except Exception:
            exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:363")
            pass
        try:
            for nm in ("left_info", "scale_info"):
                w = getattr(mw, nm, None)
                if w is not None:
                    w.setVisible(True)
        except Exception:
            exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:372")
            pass
        try:
            mw._sync_ribbon_for_view(view)
        except Exception:
            exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:380")
            pass
        rib = getattr(mw, "ribbon", None)
        if rib is not None:
            try:
                rib.setVisible(True)
                mw.ribbon_region._sync_view_ribbon(view, True)
            except Exception:
                _log.exception("视图切换：功能区页签同步失败 view=%r",
                               getattr(view, "view_id", None))
        try:
            mw.dock_region._set_map_chrome_visible(not full)
        except Exception:
            _log.exception("视图切换：地图外壳显隐失败 view=%r",
                           getattr(view, "view_id", None))
        if full:
            try:
                mw.dock_region._show_active_map_layer_dock(view)
            except Exception:
                _log.exception("视图切换：收起地图图层树 DOCK 失败 view=%r",
                               getattr(view, "view_id", None))
        try:
            mw._bind_crs_label_signal()
        except Exception:
            exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:419")
            pass
        vh = getattr(mw, "view_host", None)
        if vh is not None:
            k = str(getattr(view, "kind", "") or "") if view is not None else ""
            if k:
                try:
                    mw.view_region._hide_other_kind_docks(k)
                except Exception:
                    _log.exception("视图切换：收起其它类型 DOCK 失败 kind=%r",
                                   k)
            g = mw._control_group_of(view) if view is not None else None
            if g is not None:
                try:
                    g.show(mw, view)
                except Exception:
                    exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:449")
                    pass
            elif view is not None:
                try:
                    mw.dock_region._show_active_map_layer_dock(view)
                except Exception:
                    exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:455")
                    pass
            else:
                try:
                    mw.dock_region._hide_all_map_layer_docks()
                except Exception:
                    exc_note("_apply_view_chrome @ ggis/ui/framework/regions/ViewRegion.py:461")
                    pass
