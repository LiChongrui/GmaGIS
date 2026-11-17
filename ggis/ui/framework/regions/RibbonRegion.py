from ggis.common.util.exc_report import exc_note

import logging

from ggis.core.app import i18n
from ggis.ui.features.map_ribbon_groups import MAP_RIBBON_TAG
from ggis.ui.framework.titlebar import TITLE_H, TitleBar
from ggis.ui.framework.ribbon import GgsRibbon
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout
from ggis.core.app import settings as app_settings
from ggis.ui.framework.ribbon import RibbonGroup
from PySide6.QtWidgets import QWidget

_log = logging.getLogger("gmagis")
_tr = i18n.tr


class GgsRibbonRegion:

    def __init__(self, mw):
        self.mw = mw

    def build(self):
        mw = self.mw
        self._build_ribbon()
        try:
            self._sync_contextual_tabs()
        except Exception:
            exc_note("build @ ggis/ui/framework/regions/RibbonRegion.py:50")
            pass
        try:
            mw.ctx.region("ribbon")._apply_ribbon_prefs()
        except Exception:
            exc_note("build @ ggis/ui/framework/regions/RibbonRegion.py:54")
            pass

    def _build_ribbon(self):
        self.mw.ribbon = GgsRibbon()


        pg = self.mw.ribbon.add_tab(_tr("帮助"), tag="__always__")
        self.fill_help_ribbon_page(pg)

        try:
            from ggis.ui.framework.searchbar import GgsSearchBar, SEARCH_SHORTCUT
            self.mw.search_bar = GgsSearchBar()
            self.mw.search_bar.set_actions(
                [self.mw.ctx.svc("actions")._acts[k] for k in self.mw.ctx.svc("actions").index_order()])
            self.mw.search_bar.set_extra_provider(self.mw._search_extra_algorithms)
            from PySide6.QtGui import QShortcut, QKeySequence
            sc = QShortcut(QKeySequence(SEARCH_SHORTCUT), self.mw)
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)
            sc.activated.connect(self.mw._focus_search)
        except Exception:
            exc_note("_build_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:158")
            self.mw.search_bar = None

        self.mw._title_bar = TitleBar(self.mw, search=self.mw.search_bar)
        self.mw._title_bar.setGeometry(0, 0, self.mw.width(), TITLE_H)
        host = GgsTitleHost()
        v = QVBoxLayout(host)
        v.setContentsMargins(0, TITLE_H, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.mw.ribbon)
        self.mw.setMenuWidget(host)
        self.mw._title_bar.raise_()
        try:
            self.mw._title_bar.set_project_menu(self.mw._info_menu)
        except Exception:
            _log.exception("标题栏「工程」下拉挂载失败")
        try:
            self.mw.ribbon.set_app_menu(self.mw._app_menu)
        except Exception:
            _log.exception("「工程」按钮挂应用菜单失败")
        self.mw.ribbon.setContentsMargins(0, 3, 0, 4)

    def _relink_shared_layout(self, view):
        delegate = getattr(self.mw, "_shared_layout_delegate", None)
        if delegate is None or not hasattr(delegate, "_relink_to"):
            return
        ws = getattr(view, "workspace", None) if view is not None else None
        if ws is None:
            return
        try:
            _vh = getattr(self.mw, "view_host", None)
            _alive = _vh is not None and any(
                getattr(v, "workspace", None) is delegate
                for v in _vh.views())
        except Exception:
            exc_note("_relink_shared_layout @ ggis/ui/framework/regions/RibbonRegion.py:220")
            _alive = True
        if not _alive:
            try:
                self.mw._shared_layout_delegate = None
            except Exception:
                exc_note("_relink_shared_layout @ ggis/ui/framework/regions/RibbonRegion.py:225")
                pass
            return
        try:
            delegate._relink_to(ws)
        except Exception:
            _log.exception(
                "共享布局功能区重定向到 %r 失败",
                getattr(view, "view_id", None))

    def _sync_view_app_menu(self, view):
        ws = getattr(view, "workspace", None)
        if ws is None:
            return
        rb = getattr(ws, "rb", None)
        btn = getattr(rb, "app_button", None) if rb is not None else None
        if btn is None:
            return
        try:
            menu = getattr(self.mw, "_app_menu", None)
            if menu is None:
                app_btn = getattr(getattr(self.mw, "ribbon", None),
                                  "app_button", None)
                menu = app_btn.menu() if app_btn is not None else None
            if menu is not None:
                btn.setMenu(menu)
            from ggis.ui.framework.ribbon import fit_app_button
            fit_app_button(btn)
            rb.retext()
        except Exception:
            exc_note("_sync_view_app_menu @ ggis/ui/framework/regions/RibbonRegion.py:273")
            pass


    def _mark_ribbon_current(self):
        mw = self.mw
        try:
            rib = getattr(mw, "ribbon", None)
            if rib is None:
                return
            if (getattr(mw, "_applying_project_ui", False)
                    or getattr(mw, "_booting", False)):
                return
            rid = str(getattr(mw, "_ribbon_active_view_id", "") or "")
            if not rid:
                return
            uid = rib.current_uid()
            if not uid:
                return
            _ci = -1
            try:
                _ci = rib.tabs.currentIndex()
            except Exception:
                exc_note("_mark_ribbon_current @ ggis/ui/framework/regions/RibbonRegion.py:326")
                _ci = -1
            if 0 <= _ci < rib.tabs.count():
                try:
                    if rib.tabs.tabData(_ci) == "__always__":
                        return
                except Exception:
                    exc_note("_mark_ribbon_current @ ggis/ui/framework/regions/RibbonRegion.py:332")
                    pass
            mw._ribbon_current_set(mw._tag_of_view_id(rid), uid)
        except Exception:
            exc_note("_mark_ribbon_current @ ggis/ui/framework/regions/RibbonRegion.py:335")
            pass


    def _sync_view_ribbon(self, view, on):
        mw = self.mw
        rib = getattr(mw, "ribbon", None)
        if rib is None:
            return
        tag = ""
        try:
            tag = mw._view_tag_of(view) or ""
        except Exception:
            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:383")
            tag = ""
        if not tag and view is not None:
            ws = getattr(view, "workspace", None)
            if ws is not None:
                tag = getattr(ws, "_tab_tag", None) or ""
        if not tag:
            _log.warning("页签显隐跳过：view=%r 拿不到组标记",
                         getattr(view, "view_id", None))
            return
        try:
            n = rib.tabs.count()
        except Exception:
            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:400")
            return

        _batched = False
        try:
            rib.begin_batch()
            _batched = True
        except Exception:
            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:416")
            pass

        for i in range(n):
            try:
                d = rib.tabs.tabData(i)
            except Exception:
                exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:423")
                d = None
            is_ctx = isinstance(d, str) and d.startswith("ctx:")
            if is_ctx:
                parts = d.split(":", 2)
                d_ctx_owner = parts[1] if len(parts) > 1 else ""
            else:
                d_ctx_owner = None
            is_view_tab = (isinstance(d, str) and ":" in d) and not is_ctx
            is_keep = d == "__always__"
            try:
                if is_keep:
                    rib.set_tab_visible(i, True)
                elif is_ctx:
                    rib.set_tab_visible(i, bool(on) and d_ctx_owner == tag)
                elif is_view_tab:
                    rib.set_tab_visible(i, bool(on) and d == tag)
                else:
                    rib.set_tab_visible(i, not on)
            except Exception:
                exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:460")
                pass


        try:
            mw.ribbon_region._sync_contextual_tabs(view)
        except Exception:
            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:488")
            pass

        try:
            hit = -1
            if on:
                try:
                    _cur_rid = str(getattr(view, "view_id", "") or "")
                    want_uid = mw._ribbon_current_of(
                        mw._tag_of_view_id(_cur_rid))
                except Exception:
                    exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:515")
                    want_uid = 0
                if want_uid:
                    try:
                        hit = rib.index_of_uid(want_uid)
                    except Exception:
                        exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:520")
                        hit = -1
                if hit < 0:
                    for i in range(rib.tabs.count()):
                        try:
                            if rib.tabs.tabData(i) != tag:
                                continue
                            if hasattr(rib.tabs, "isTabVisible") \
                                    and not rib.tabs.isTabVisible(i):
                                continue
                        except Exception:
                            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:531")
                            continue
                        hit = i
                        break
                if hit < 0:
                    for i in range(rib.tabs.count()):
                        try:
                            if hasattr(rib.tabs, "isTabVisible") \
                                    and not rib.tabs.isTabVisible(i):
                                continue
                        except Exception:
                            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:542")
                            continue
                        hit = i
                        break
                try:
                    if hit >= 0 and hasattr(rib.tabs, "isTabVisible") \
                            and not rib.tabs.isTabVisible(hit):
                        hit = -1
                except Exception:
                    exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:557")
                    pass
                if hit < 0:
                    for i in range(rib.tabs.count()):
                        try:
                            _td = rib.tabs.tabData(i)
                            if _td != tag and _td != "__always__":
                                continue
                            if hasattr(rib.tabs, "isTabVisible") \
                                    and not rib.tabs.isTabVisible(i):
                                continue
                        except Exception:
                            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:568")
                            continue
                        hit = i
                        break
            else:
                hit = -1
                for i in range(rib.tabs.count()):
                    try:
                        if hasattr(rib.tabs, "isTabVisible") \
                                and not rib.tabs.isTabVisible(i):
                            continue
                    except Exception:
                        exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:579")
                        continue
                    hit = i
                    break
            if hit >= 0:
                try:
                    rib.set_current_tab(hit)
                except Exception:
                    exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:590")
                    rib.tabs.setCurrentIndex(hit)
        except Exception:
            exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:592")
            pass
        if view is None:
            try:
                rib._move_keep_tabs_to_tail()
            except Exception:
                exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:604")
                pass

        if _batched:
            try:
                rib.end_batch()
            except Exception:
                exc_note("_sync_view_ribbon @ ggis/ui/framework/regions/RibbonRegion.py:614")
                pass


    def _rebuild_view_tab(self, kind, view=None):
        mw = self.mw
        pg = mw._view_page_of(view) if view is not None \
            else getattr(mw, "_view_ribbon_page", None)
        if pg is not None:
            mw._view_ribbon_page = pg
        if pg is None:
            return
        try:
            sig = mw.ctx.region("dock")._view_tab_signature(view, kind)
        except Exception:
            exc_note("_rebuild_view_tab @ ggis/ui/framework/regions/RibbonRegion.py:651")
            sig = None
        if sig is not None and getattr(pg, "_built_sig", None) == sig \
                and pg.groups():
            try:
                mw.ctx.region("dock")._sync_panel_actions()
            except Exception:
                exc_note("_rebuild_view_tab @ ggis/ui/framework/regions/RibbonRegion.py:658")
                pass
            return
        try:
            pg.clear_groups()
        except Exception:
            exc_note("_rebuild_view_tab @ ggis/ui/framework/regions/RibbonRegion.py:663")
            pass
        if view is not None:
            mw._panel_acts = mw.ctx.region("dock")._panel_acts_of(view)
        else:
            mw._panel_acts = []
        k = str(kind)
        if k == "layout":
            mw._build_view_tab_layout(view)
        elif k == "model":
            mw._build_view_tab_model(view)
        else:
            mw._build_view_tab_map()
        try:
            idx = -1
            rib = getattr(mw, "ribbon", None)
            if rib is not None and view is not None:
                tag = mw._view_tag_of(view)
                for i in range(rib.tabs.count()):
                    try:
                        d = rib.tabs.tabData(i)
                        if d == tag and rib.tabs.tabText(i) == _tr("视图"):
                            idx = i
                            break
                    except Exception:
                        exc_note("_rebuild_view_tab @ ggis/ui/framework/regions/RibbonRegion.py:693")
                        continue
            if idx < 0:
                idx = -1
            sa = rib.stack.widget(idx) if (rib is not None and idx >= 0) else None
            if sa is not None and hasattr(rib, "_update_overflow"):
                rib._update_overflow(sa)
        except Exception:
            exc_note("_rebuild_view_tab @ ggis/ui/framework/regions/RibbonRegion.py:704")
            pass
        try:
            if sig is not None:
                pg._built_sig = sig
        except Exception:
            exc_note("_rebuild_view_tab @ ggis/ui/framework/regions/RibbonRegion.py:710")
            pass


    def _sync_contextual_tabs(self, view=None):
        mw = self.mw
        lyr = mw._forward_to_map_view("_selected_tree_layer")
        is_vec = is_ras = False
        try:
            is_vec = bool(lyr is not None and lyr.is_vector()
                          and not lyr.is_table())
            is_ras = bool(lyr is not None and lyr.is_raster())
        except Exception:
            exc_note("_sync_contextual_tabs @ ggis/ui/framework/regions/RibbonRegion.py:761")
            is_vec = is_ras = False
        try:
            _cnt = mw._forward_to_map_view("_selected_tree_item_count")
            if _cnt is not None and _cnt > 1:
                is_vec = is_ras = False
        except Exception:
            exc_note("_sync_contextual_tabs @ ggis/ui/framework/regions/RibbonRegion.py:767")
            pass
        _kind = None
        if view is not None:
            _kind = str(getattr(view, "kind", "map") or "map")
        if _kind is None:
            _kind = getattr(mw, "_current_view_kind", None)
        if _kind is None:
            try:
                _vh = getattr(mw, "view_host", None)
                _cv = _vh.current_view() if _vh is not None else None
                _kind = str(getattr(_cv, "kind", "map") or "map")
            except Exception:
                exc_note("_sync_contextual_tabs @ ggis/ui/framework/regions/RibbonRegion.py:786")
                _kind = "map"
        if _kind != "map":
            is_vec = is_ras = False
        if is_vec:
            _mv = mw.current_map_view()
            if _mv is not None:
                _mv._ensure_edit_session(lyr)
        rib = getattr(mw, "ribbon", None)
        if rib is None:
            return
        _owner = MAP_RIBBON_TAG
        for title, show in ((_tr("要素编辑"), is_vec),
                            (_tr("栅格图层"), is_ras)):
            try:
                rib.set_tab_visible(title, show, owner=_owner)
            except Exception:
                exc_note("_sync_contextual_tabs @ ggis/ui/framework/regions/RibbonRegion.py:817")
                pass
        try:
            i = rib.tabs.currentIndex()
            if i > 0 and hasattr(rib.tabs, "isTabVisible") \
                    and not rib.tabs.isTabVisible(i):
                j = int(getattr(rib, "_main_before_ctx", -1))
                if not (0 <= j < i and rib.tabs.isTabVisible(j)):
                    j = -1
                    for k in range(i - 1, -1, -1):
                        if rib.tabs.isTabVisible(k):
                            j = k
                            break
                    if j < 0:
                        j = 0
                try:
                    rib.set_current_tab(j)
                except Exception:
                    exc_note("_sync_contextual_tabs @ ggis/ui/framework/regions/RibbonRegion.py:840")
                    rib.tabs.setCurrentIndex(j)
        except Exception:
            exc_note("_sync_contextual_tabs @ ggis/ui/framework/regions/RibbonRegion.py:842")
            pass

    def _apply_ribbon_prefs(self):
        try:
            self.mw.ribbon.set_collapsed(
                bool(app_settings.get("ribbon_collapsed")))
        except Exception:
            exc_note("_apply_ribbon_prefs @ ggis/ui/framework/regions/RibbonRegion.py:849")
            pass
        try:
            self.mw.ctx.wiring.connect((self.mw.ribbon.collapsedChanged), (self._on_ribbon_collapsed), "ribbon")
            try:
                self.mw.ctx.wiring.connect((self.mw.ribbon.tabPicked), (self.mw._on_ribbon_tab_picked), "ribbon")
                self.mw.ribbon.tabGroupGuard = self.mw._ribbon_tab_group_is_current
            except Exception:
                exc_note("_apply_ribbon_prefs @ ggis/ui/framework/regions/RibbonRegion.py:860")
                pass
        except Exception:
            exc_note("_apply_ribbon_prefs @ ggis/ui/framework/regions/RibbonRegion.py:862")
            pass


    def _on_ribbon_collapsed(self, collapsed):
        app_settings.set("ribbon_collapsed", bool(collapsed))


    def fill_help_ribbon_page(self, pg):
        g = RibbonGroup(_tr("帮助"))
        try:
            g.add_action(self.mw.ctx.svc("actions").get("open_help"), variant="GgsBigCheckButtonStyle1")
            g.add_action(self.mw.ctx.svc("actions").get("open_shortcuts"),
                         variant="GgsBigButtonStyle1")
        except Exception:
            import logging as _logging
            _logging.getLogger("gmagis").exception("帮助页构建失败（动作缺失？）")
        pg.add_group(g)

        gw = RibbonGroup(_tr("控件画廊"))
        try:
            gw.add_action(self.mw.ctx.svc("actions").get("widget_gallery"),
                          variant="GgsBigButtonStyle1")
        except Exception:
            import logging as _logging
            _logging.getLogger("gmagis").exception("控件画廊分组构建失败")
        pg.add_group(gw)
        return g


class GgsTitleHost(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsTitleHost")
