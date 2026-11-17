# -*- coding: utf-8 -*-
# 原来从 `_hostdeps` 导入的 `RibbonGroup` / `QMenu` / `QAction` /
# `icons` / `basemap_choices` **已全部不需要** —— 每一个 `RibbonGroup`
# 都变成 `map_ribbon_groups` 里的一个类，建组时用的菜单 / 图标 / 底图表
# 全部搬进了那个文件。这里只留页面与显隐机制真正还在用的。
from ggis.common.util.exc_report import exc_note
from ._hostdeps import _tr, _log
from .map_ribbon_groups import (MAP_RIBBON_TAG, GgsPanelDockGroup,
                                GgsViewToolsGroup)

"""**Ribbon 页签 × 视图**：两者的对应关系与交互（R493o，由
`main_window.py` 搬迁而来）。

这是**纯搬迁**：方法体一个字符都没改，行为与搬迁前完全一致。

用户 要求：main_window.py 代码太大，按照每个视图分离的逻辑，
main_window 应该很小才对！—— 本 Mixin 收「功能区页签怎么跟着视图变」：

* 页签归属：`_view_tag_of` / `_tag_of_view_id` / `_view_page_of` ——
 一个视图的页签用`map:{view_id}`（布局 / 模型用工作区自己的标记）当组标记。
* 切视图时换页签：`_sync_ribbon_for_view` / `_sync_view_ribbon` ——
 起**不再摘挂页签**，页签常驻、只按组标记切显隐。
* 记住每张视图停在哪个页签：`_mark_ribbon_current`（**切走的瞬间**记下
 当前页签的**永久编号**，`Ribbon` 在页面出生时发的号）+ `_ribbon_current_of`
 / `_ribbon_current_set`（按组标记存取那个编号）—— 切走再切回来时**原样
 恢复**（用户要求）。⚠ **不靠"用户点了页签"那个信号**：它与程序改可见性
 在信号层完全一样，判据永远不可靠（详见 `_on_ribbon_tab_picked` 的说明）。
* 「视图」页内容随视图类型重建：`_rebuild_view_tab` + `_build_view_tab_*`。
* 地图视图的页签本体 `_build_map_ribbon_pages` —— **唯一来源**。
 `main_window._build_ribbon` 原先也建过
 「地图 / 分析 / 视图」三页（内容与本方法几乎一字不差），启动时又被
 `_drop_startup_view_tabs` 整批拆掉、运行期再由这里重建 ⇒ **同一份代码
 存在两处**，且视图专属内容寄存在窗口里。**现已整段删除**，
 `_drop_startup_view_tabs` 一并删除。窗口侧只剩**全局**的「帮助」页。
两个**上下文**页签
 （「要素编辑」/「栅格图层」）也**搬进本文件的 `_build_map_ribbon_pages`**
 ⇒ 每张地图视图各一份。`Ribbon` 的上下文页签身份相应从 `title` 改成
 **`(owner, title)`**（`add_contextual_tab(..., owner=vid_tag)` /
 `set_tab_visible(..., owner=vid_tag)`）—— 原来只按标题去重与寻址，
 多张视图会共用一份、显隐串台。**窗口现在只持有「帮助」一个页签。**

⚠**视图标签行的交互已搬走**（`_on_view_tab_close` /
`_on_view_tab_close_others` / `_on_view_tab_close_all` / `_on_view_tab_rename` /
`_on_view_tab_requested` / `_on_view_tabs_reordered`）—— 它们属于**标签行**，
不属"Ribbon 页签 × 视图"，现在在 `viewshell.py`（那里本来就有
`_sync_view_tabs`）。同理，"至少保留一个
视图"这条**策略本体**已收回 `ViewHost.close_view`，不在任何界面层。

只允许通过 `self.<成员>` 访问主窗口（Mixin 惯例），不要 import 主窗口。
`ggis/ui/features/` 被静态门禁 `_r492ff_names.py` 整体豁免（本文件用的
`_tr` 等是宿主 import 的符号），漏 import 只能靠真的构造一次 MainWindow 兜。
"""


class ViewRibbonFeatureMixin:

    def _all_ribbons(self):
        r = getattr(self, "ribbon", None)
        return [r] if r is not None else []

    def _primary_view_id(self):
        mv = None
        vh = getattr(self, "view_host", None)
        if vh is not None:
            for _v in vh.views():
                if str(getattr(_v, "kind", "")) == "map":
                    mv = _v
                    break
        if mv is None:
            return ""
        return str(getattr(mv, "view_id", "") or "")

    def _ribbon_of_view(self, view):
        rib = getattr(self, "ribbon", None)
        if rib is None or view is None:
            return rib
        rid = str(getattr(view, "view_id", "") or "")
        if not rid:
            return rib
        if getattr(self, "_in_ribbon_of_view", False):
            return rib
        reg = getattr(self, "_view_tabs", None)
        if reg is None:
            reg = self._view_tabs = {}
        if rid in reg:
            return rib
        reg[rid] = True
        self._in_ribbon_of_view = True
        try:
            return self._ribbon_of_view_locked(rib, view, rid, reg)
        finally:
            self._in_ribbon_of_view = False

    def _ribbon_has_tag(self, rib, rid):
        if rib is None or not rid:
            return False
        want = "map:%s" % rid
        try:
            for i in range(min(int(rib._main_count), rib.tabs.count())):
                if rib.tabs.tabData(i) == want:
                    return True
        except Exception:
            exc_note("_ribbon_has_tag @ ggis/ui/features/view_ribbon.py:140")
            return False
        return False

    def _ribbon_of_view_locked(self, rib, view, rid, reg):
        if str(getattr(view, "kind", "")) == "map":
            try:
                if not getattr(self, "_shared_map_pages_built", False):
                    view.build_map_ribbon(self)
                    self._mount_map_ribbon_pages(rib, view)
                    self._shared_map_pages_built = True
                else:
                    _sh = getattr(self, "_shared_map_ribbon", None) or {}
                    view.ribbon_pages = [
                        (_sh.get("map"), _tr("地图")),
                        (_sh.get("analyze"), _tr("分析")),
                        (_sh.get("view"), _tr("视图")),
                        (_sh.get("edit"), _tr("要素编辑")),
                        (_sh.get("raster"), _tr("栅格图层")),
                    ]
            except Exception:
                _log.exception("地图视图功能区构建失败")
        else:
            pass
        try:
            view._ribbon_built = True
        except Exception:
            exc_note("_ribbon_of_view_locked @ ggis/ui/features/view_ribbon.py:189")
            pass
        return rib

    def _ribbon_tab_group_is_current(self, tab_data):
        return True

    def _on_ribbon_tab_picked(self, idx, tag, title):
        pass

    def _ribbon_current_of(self, tag):
        reg = getattr(self, "_ribbon_current", None)
        if reg is None:
            return 0
        try:
            return int(reg.get(str(tag)) or 0)
        except Exception:
            exc_note("_ribbon_current_of @ ggis/ui/features/view_ribbon.py:228")
            return 0

    def _ribbon_current_set(self, tag, uid):
        reg = getattr(self, "_ribbon_current", None)
        if reg is None:
            reg = self._ribbon_current = {}
        try:
            uid = int(uid or 0)
            if uid > 0:
                reg[str(tag)] = uid
        except Exception:
            exc_note("_ribbon_current_set @ ggis/ui/features/view_ribbon.py:247")
            pass

    def _sync_ribbon_for_view(self, view):
        rib = getattr(self, "ribbon", None)
        if rib is None:
            return
        reg = getattr(self, "_view_tabs", None)
        if reg is None:
            reg = self._view_tabs = {}
        rid = str(getattr(view, "view_id", "") or "") if view is not None else ""
        if rid and rid not in reg:
            self._ribbon_of_view(view)
            reg[rid] = True
        if "_detached" in reg:
            try:
                reg.pop("_detached", None)
            except Exception:
                exc_note("_sync_ribbon_for_view @ ggis/ui/features/view_ribbon.py:286")
                pass
        self._ribbon_active_view_id = rid

    def _tag_of_view_id(self, rid):
        rid = str(rid or "")
        if not rid:
            return ""
        try:
            vh = getattr(self, "view_host", None)
            if vh is not None:
                v = vh.view(rid)
                if v is not None:
                    if str(getattr(v, "kind", "")) == "map":
                        return rid
                    t = self._view_tag_of(v)
                    if t:
                        return t
                parked = vh.parked_view(rid)
                if parked is not None:
                    if str(getattr(parked, "kind", "")) == "map":
                        return rid
                    t = self._view_tag_of(parked)
                    if t:
                        return t
        except Exception:
            exc_note("_tag_of_view_id @ ggis/ui/features/view_ribbon.py:326")
            pass
        return "map:%s" % rid

    def _view_tag_of(self, view):
        if view is None:
            return ""
        rid = str(getattr(view, "view_id", "") or "")
        if not rid:
            return ""
        if str(getattr(view, "kind", "")) == "map":
            try:
                fn = getattr(view, "view_tab_tag", None)
                if callable(fn):
                    t = fn()
                    if t:
                        return str(t)
            except Exception:
                exc_note("_view_tag_of @ ggis/ui/features/view_ribbon.py:350")
                pass
            return "map:%s" % rid
        ws = getattr(view, "workspace", None)
        tag = getattr(ws, "_tab_tag", "") if ws is not None else ""
        if tag:
            return tag
        g = self._control_group_of(view)
        tag = getattr(g, "view_tag", "") if g is not None else ""
        return tag or ("%s:%s" % (str(getattr(view, "kind", "view")), rid))

    def _view_page_of(self, view, create=True):
        rib = self._ribbon_of_view(view)
        if rib is None:
            return getattr(self, "_view_ribbon_page", None)
        rid = str(getattr(view, "view_id", "") or "")
        if not rid:
            return getattr(self, "_view_ribbon_page", None)
        tag = self._view_tag_of(view)
        if not tag:
            return getattr(self, "_view_ribbon_page", None)
        try:
            n = rib.tabs.count()
        except Exception:
            exc_note("_view_page_of @ ggis/ui/features/view_ribbon.py:385")
            return getattr(self, "_view_ribbon_page", None)
        for i in range(n):
            try:
                d = rib.tabs.tabData(i)
                if d != tag:
                    continue
                if rib.tabs.tabText(i) != _tr("视图"):
                    continue
                w = rib.stack.widget(i)
                pg = w.widget() if w is not None else None
                if pg is not None:
                    return pg
            except Exception:
                exc_note("_view_page_of @ ggis/ui/features/view_ribbon.py:403")
                continue
        if not create:
            return None
        try:
            pg = rib.add_tab(_tr("视图"), tag=tag)
            return pg
        except Exception:
            _log.exception("「视图」页构建失败")
            return None

    def _build_view_tab_map(self):
        pg = getattr(self, "_view_ribbon_page", None)
        if pg is None:
            return

        pg.add_group(GgsPanelDockGroup(
            self, _tr("窗口"),
            ((self.layer_dock, _tr("图层"), "layer"),
             (self._map_dock_mgr.browser_dock, _tr("浏览器"), "browser"),
             (self._map_dock_mgr.overview_dock, _tr("鹰眼图"), "overview"),
             (self.task_dock, _tr("任务"), "task"),
             (self.log_dock, _tr("日志"), "log"))))

        pg.add_group(GgsViewToolsGroup(self))

        try:
            self.ctx.region("dock")._sync_panel_actions()
        except Exception:
            exc_note("_build_view_tab_map @ ggis/ui/features/view_ribbon.py:452")
            pass

    def _build_view_tab_layout(self, view):
        pg = getattr(self, "_view_ribbon_page", None)
        if pg is None:
            return
        _icons = {"GgsLayoutItemsDock": "table",
                  "GgsLayoutPropsDock": "settings"}
        vid = str(getattr(view, "view_id", ""))
        for dock in self._view_docks.get(vid, []):
            if dock is None:
                continue
            pg.add_group(GgsPanelDockGroup(
                self, dock.windowTitle(),
                ((dock, dock.windowTitle(),
                  _icons.get(dock.objectName(), "settings")),)))

    def _build_view_tab_model(self, view):
        pg = getattr(self, "_view_ribbon_page", None)
        if pg is None:
            return
        _icons = {"GgsModelOpsDock": "model",
                  "GgsModelLayersDock": "table",
                  "GgsModelPropsDock": "settings"}
        vid = str(getattr(view, "view_id", ""))
        for dock in self._view_docks.get(vid, []):
            if dock is None:
                continue
            pg.add_group(GgsPanelDockGroup(
                self, dock.windowTitle(),
                ((dock, dock.windowTitle(),
                  _icons.get(dock.objectName(), "settings")),)))

    def _mount_map_ribbon_pages(self, ribbon, view):
        pages = list(getattr(view, "ribbon_pages", None) or [])
        if not pages:
            return
        tag = MAP_RIBBON_TAG

        _ctx_to_hide = []
        for pg, title in pages:
            if pg is None:
                continue
            t = str(title)
            if t == _tr("要素编辑") or t == _tr("栅格图层"):
                ribbon.attach_contextual_page(pg, t, owner=tag)
                _ctx_to_hide.append(t)
            else:
                ribbon.attach_page(pg, t, tag=tag)

        for _t in _ctx_to_hide:
            try:
                ribbon.set_tab_visible(_t, False, owner=tag)
            except Exception:
                exc_note("_mount_map_ribbon_pages @ ggis/ui/features/view_ribbon.py:549")
                pass

        try:
            has_help = any(ribbon.tabs.tabText(i) == _tr("帮助")
                           for i in range(ribbon.tabs.count()))
        except Exception:
            exc_note("_mount_map_ribbon_pages @ ggis/ui/features/view_ribbon.py:557")
            has_help = False
        if not has_help:
            try:
                hp = ribbon.add_tab(_tr("帮助"), tag="__always__")
                self.ctx.region("ribbon").fill_help_ribbon_page(hp)
            except Exception:
                exc_note("_mount_map_ribbon_pages @ ggis/ui/features/view_ribbon.py:563")
                pass

