# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note
import logging

from PySide6.QtWidgets import QVBoxLayout

from ggis.core.app import i18n
from ggis.core.crs.extent import GgsRectangle
from ggis.core.model.maplayer_tree import MapLayerTree
from ggis.core.model.selection import GgsSelection
from ggis.core.model.layer import layer_allows
from ggis.common.base.view import GgsView
from ggis.ui.views.map.map_edit import MapEditMixin
from ggis.ui.views.map.map_commands import MapCommandsMixin
from ggis.ui.views.map.map_data import MapDataMixin
from ggis.ui.views.map.map_layer import MapLayerMixin

_tr = i18n.tr

LEVEL_INFO = "Info"
LEVEL_WARN = "Warning"


class MapView(MapCommandsMixin, MapLayerMixin, MapDataMixin,
             MapEditMixin, GgsView):

    def __init__(self, canvas=None, parent=None, view_id="map", title=None,
                 canvas_color=None):
        # 视图名创建后即固定（用户数据），不走翻译。
        super().__init__(view_id, title or "地图", parent)

        if canvas is None:

            from ggis.render.map_canvas import GgsMapCanvas
            canvas = GgsMapCanvas(self)

        if canvas_color:
            canvas.setCanvasColor(canvas_color)
        self.kind = "map"

        self.closable = True

        self.park_on_close = True

        self.icon_name = "map_street"
        self.canvas = canvas

        self._tools = {}

        self._edit_sessions = {}

        self._snapper = None

        self._geom_op = None

        self._snap_syncing = False

        self._host = None

        self.ribbon_pages = []

        self._async_pending = {}
        self._async_wired = False
        self._pyr_active = False
        self._pyr_quicklook_path = None
        self._states_pending = False
        self._docks_attached = False
        self._export_vec_task = None
        self._export_raster_task = None
        self._profile_dlg = None

        self._measure_panel = None
        self._measure_panel_was_visible = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if canvas is not None:
            try:
                canvas.setParent(self)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:105", exc_info=True)
            lay.addWidget(canvas, 1)

        self.layer_dock = None

        self._layer_tree = None
        proj = getattr(canvas, "_project", None) if canvas is not None else None
        if proj is not None:
            try:
                self._layer_tree = MapLayerTree(proj)
                try:
                    canvas.set_layer_source(self._layer_tree.visible_layers)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:121", exc_info=True)
                try:
                    self._layer_tree.membershipChanged.connect(
                        canvas._on_layers_changed)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:126", exc_info=True)
            except Exception:
                exc_note("__init__ @ ggis/ui/views/map/map_view.py:129")
                self._layer_tree = None

        try:
            from ggis.ui.framework.statusbar import build_map_status_controls
            build_map_status_controls(self)
        except Exception:

            import logging as _lg
            _lg.getLogger("gmagis").exception("build_map_status_controls 失败")
            self._status_widgets = []

    def layer_tree(self):
        return getattr(self, "_layer_tree", None)

    def rename(self, title):
        return super().rename(title)

    def crs(self):
        cv = self.canvas
        if cv is None:
            return None
        try:
            return cv.effectiveCrs()
        except Exception:
            exc_note("crs @ ggis/ui/views/map/map_view.py:156")
            return None

    def has_explicit_crs(self):
        cv = self.canvas
        if cv is None:
            return False
        try:
            return bool(cv.hasExplicitCrs())
        except Exception:
            exc_note("has_explicit_crs @ ggis/ui/views/map/map_view.py:177")
            return False

    def has_crs(self):
        return self.has_explicit_crs()

    def set_crs(self, crs):
        cv = self.canvas
        if cv is None:
            return False
        try:
            cv.setDestinationCrs(crs)
            return True
        except Exception:
            exc_note("set_crs @ ggis/ui/views/map/map_view.py:195")
            return False

    def visible_layers(self):
        lt = self.layer_tree()
        if lt is None:
            return []
        try:
            return list(lt.visible_layers())
        except Exception:
            exc_note("visible_layers @ ggis/ui/views/map/map_view.py:205")
            return []

    def add_layer(self, layer):
        out = self.adopt_layer(layer, select=False, zoom_first=False,
                               check_crs=False, silent=True)
        if out is None:
            return False
        try:
            cv = self.canvas
            if cv is not None:
                cv.refresh_layers()
        except Exception:
            exc_note("add_layer @ ggis/ui/views/map/map_view.py:219")
        return True

    def remove_layer(self, layer):
        lt = self.layer_tree()
        if lt is None or layer is None:
            return False
        try:
            key = layer if isinstance(layer, str) else str(layer.id())
            lt.remove(key)
            cv = self.canvas
            if cv is not None:
                cv.refresh_layers()
            return True
        except Exception:
            exc_note("remove_layer @ ggis/ui/views/map/map_view.py:234")
            return False

    def refresh(self):
        cv = self.canvas
        if cv is None:
            return
        try:
            cv.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:243", exc_info=True)

    def extent(self):
        cv = self.canvas
        if cv is None:
            return None
        try:
            r = cv.extent()
            return (float(r.xmin), float(r.ymin),
                    float(r.xmax), float(r.ymax))
        except Exception:
            exc_note("extent @ ggis/ui/views/map/map_view.py:256")
            return None

    def tools(self):
        return self._tools

    def sessions(self):
        return self._edit_sessions

    def activate_map_state(self):
        cv = self.canvas
        if cv is None:
            return
        try:
            from ggis.core.model.selection import GgsSelection
            GgsSelection.set_active(cv.selection())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:284", exc_info=True)

    def layer_dock_view(self):
        d = getattr(self, "layer_dock", None)
        return getattr(d, "view", None) if d is not None else None

    def _current_layer(self):
        # layer_dock 在 viewshell 注册时才挂到视图上（view.layer_dock = d）；
        # 启动早期同步（标注/符号化面板）会先到这里，dock 视图可能仍是 None。
        tree = self.layer_dock_view()
        try:
            it = tree.currentItem() if tree is not None else None
        except Exception:
            exc_note("_current_layer @ ggis/ui/views/map/map_view.py:306")
            it = None
        lyr = self._item_layer(it)
        if lyr is not None:
            return lyr
        try:
            lt = self.layer_tree()
            for l in reversed(list(lt.layers()) if lt is not None else []):
                if l.is_vector() and l.is_visible():
                    return l
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:316", exc_info=True)
        return None

    def _selected_tree_layer(self):
        try:
            tree = self.layer_dock_view()
            if tree is None:
                return None
            if not (tree.selectedItems() or []):
                return None
            return self._item_layer(tree.currentItem())
        except Exception:
            exc_note("_selected_tree_layer @ ggis/ui/views/map/map_view.py:335")
            return None

    def _selected_tree_item_count(self):
        try:
            tree = self.layer_dock_view()
            return len(tree.selectedItems() or []) if tree is not None else 0
        except Exception:
            exc_note("_selected_tree_item_count @ ggis/ui/views/map/map_view.py:345")
            return 0

    def dispose_map_state(self):
        for s in list(self._edit_sessions.values()):
            try:
                s.dispose()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:342", exc_info=True)
        try:
            self._edit_sessions.clear()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:346", exc_info=True)

    def view_deactivated(self):

        p = getattr(self, "_measure_panel", None)
        if p is not None:
            try:
                self._measure_panel_was_visible = bool(p.isVisible())
            except Exception:
                exc_note("view_deactivated @ ggis/ui/views/map/map_view.py:366")
                self._measure_panel_was_visible = False
            try:
                p.hide()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:359", exc_info=True)

    def view_activated(self):

        p = getattr(self, "_measure_panel", None)
        if p is None or not getattr(self, "_measure_panel_was_visible", False):
            return
        try:
            self._place_measure_panel()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:369", exc_info=True)
        try:
            p.show()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:373", exc_info=True)

    def cleanup(self):

        _mp = getattr(self, "_measure_panel", None)
        if _mp is not None:

            self._measure_panel_was_visible = False
            try:
                _mp.hide()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:389", exc_info=True)
        try:
            cv = self.canvas
            if cv is not None:
                cv.shutdown_render()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:395", exc_info=True)

        try:
            if not getattr(self, "park_on_close", False):
                self.dispose_map_state()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:401", exc_info=True)

        try:
            if not getattr(self, "park_on_close", False):
                self.dispose_map_signals()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:409", exc_info=True)

        try:
            if getattr(self, "park_on_close", False):
                d = getattr(self, "layer_dock", None)
                if d is not None:
                    d.setVisible(False)
            else:
                win = (self.canvas.window()
                       if self.canvas is not None else None)
                if win is not None and hasattr(win, "_unregister_view_docks"):
                    win._unregister_view_docks(self.view_id)
                try:
                    self.layer_dock = None
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:424", exc_info=True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:426", exc_info=True)

        try:
            if not getattr(self, "park_on_close", False):
                lt = getattr(self, "_layer_tree", None)
                if lt is not None:
                    lt.dispose()
                    self._layer_tree = None
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:435", exc_info=True)

    def ribbon_tabs(self):
        out = []
        for pg, title in (getattr(self, "ribbon_pages", None) or []):
            if pg is not None:
                out.append((str(title), pg))
        return out

    def build_map_ribbon(self, host):
        from ggis.ui.features.map_ribbon_groups import (
            build_map_ribbon_pages, MAP_RIBBON_TAG)
        shared = getattr(host, "_shared_map_ribbon", None)
        if shared is None:
            try:
                shared = build_map_ribbon_pages(host)
                host._shared_map_ribbon = shared
            except Exception:
                import logging as _lg
                _lg.getLogger("gmagis").exception(
                    "build_map_ribbon 失败")
                shared = {}
        self.ribbon_pages = [
            (shared.get("map"), _tr("地图")),
            (shared.get("analyze"), _tr("分析")),
            (shared.get("view"), _tr("视图")),
            (shared.get("edit"), _tr("要素编辑")),
            (shared.get("raster"), _tr("栅格图层")),
        ]

    def _shared_project(self):
        from ggis.core.model.project import GgsProject
        return GgsProject.instance()

    def _project(self):
        """工程**单例**（`GgsProject.instance()`）。

 这三个方法（视野 / 缩放 / 图层）原来挂在 `MainWindow` 上，
 `self._shared_project()` 走的是窗口那个同名方法。`GgsProject` 是单例，
 **视图直接调即可**，不必经窗口 —— 这正是"操作不与 main_window
 挂接"的口径。
 """
        from ggis.core.model.project import GgsProject
        return GgsProject.instance()

    def measure(self):
        p = getattr(self, "_measure_panel", None)
        if p is not None:
            return p
        try:
            from ggis.ui.panels.measure import GgsMeasurePanel
        except Exception:
            exc_note("measure @ ggis/ui/views/map/map_view.py:564")
            return None
        try:
            p = GgsMeasurePanel(self)

            p.clearRequested.connect(self._measure_clear)
            p.closeRequested.connect(self._measure_close)
            p.liveChanged.connect(self._measure_live_changed)
            self._measure_panel = p
        except Exception:
            exc_note("measure @ ggis/ui/views/map/map_view.py:573")
            return None
        return p

    def _notify(self, text, level=None, duration=4):
        return self._show_status_message(text, level, duration)

    def _show_status_message(self, text, level=None, duration=4):
        host = self._host
        if host is None:
            return
        if level is None:
            host.show_message(text, duration=duration)
        else:
            host.show_message(text, level, duration)

    def retheme(self):
        host = self._host
        if host is None:
            return
        fn = None
        try:
            fn = getattr(host.ctx.svc("settings_ctl"),
                         "apply_canvas_color", None)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:608", exc_info=True)
        if callable(fn):
            try:
                fn()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:613", exc_info=True)

    def _zoom_to_tree_item(self, item):
        layers = self._picked_layers(item)
        if not layers:
            return
        if len(layers) == 1:
            try:
                self.canvas.zoomToLayer(layers[0])
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:628", exc_info=True)
            return
        try:
            dst = self.canvas.effectiveCrs()
        except Exception:
            exc_note("_zoom_to_tree_item @ ggis/ui/views/map/map_view.py:643")
            dst = None
        ext = None
        for lyr in layers:
            try:
                e = self._layer_extent(lyr, dst)
            except Exception:
                exc_note("_zoom_to_tree_item @ ggis/ui/views/map/map_view.py:649")
                continue
            if e is None or e.is_empty():
                continue
            if ext is None:
                ext = e
            else:
                ext.combine_extent_with(e)
        if ext is not None and not ext.is_empty():
            self.canvas.zoomToExtent(ext)

    def _zoom_to_group_item(self, item):
        from ggis.ui.panels.layertree import ROLE_KIND
        from ggis.core.crs.extent import GgsRectangle

        if item is None or item.data(0, ROLE_KIND) != "group":
            return
        ext = None
        dst = None
        try:
            dst = self.canvas.effectiveCrs()
        except Exception:
            exc_note("_zoom_to_group_item @ ggis/ui/views/map/map_view.py:672")
            dst = None

        def _walk(it):
            nonlocal ext
            lyr = self._item_layer(it)
            if lyr is not None:
                try:
                    e = self._layer_extent(lyr, dst)
                except Exception:
                    exc_note("_walk @ ggis/ui/views/map/map_view.py:681")
                    e = None
                if e is not None:
                    ext = e if ext is None else ext.combine_extent_with(e)
            for i in range(it.childCount()):
                _walk(it.child(i))

        _walk(item)
        if ext is None or not isinstance(ext, GgsRectangle) or ext.is_empty():
            self._show_status_message(_tr("分组里没有可缩放的图层"), LEVEL_INFO)
            return
        try:
            self.canvas.zoomToExtent(ext)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:685", exc_info=True)

    def _extent(self):
        try:
            e = self.canvas.extent()
            return e if not e.is_empty() else None
        except Exception:
            exc_note("_extent @ ggis/ui/views/map/map_view.py:702")
            return None

    def _layer_extent(self, layer, dst_crs=None):
        from ggis.core.crs.extent import layer_extent as _impl
        return _impl(layer, dst_crs)

    def _collect_layer_extents(self):
        vh = getattr(self, "view_host", None)
        out = {}
        if vh is None:
            return out
        for v in vh.views():
            if str(getattr(v, "kind", "")) != "map":
                continue
            cv = getattr(v, "canvas", None)
            if cv is None:
                continue
            try:
                e = cv.extent()
                if e is not None and not e.is_empty():
                    out[str(v.view_id)] = [float(e.xmin), float(e.ymin),
                                           float(e.xmax), float(e.ymax)]
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:727", exc_info=True)
        return out

    def _remember_layer_extent(self, ext):
        vh = getattr(self, "view_host", None)
        cur = vh.current_view() if vh is not None else None
        vid = getattr(cur, "view_id", "") if cur is not None else ""
        if not str(vid).startswith("map"):
            return
        proj = self._shared_project()
        if proj is None:
            return
        try:
            d = dict(proj.map_views_extent() or {})
            if ext and len(ext) == 4:
                d[str(vid)] = [float(v) for v in ext]
            else:
                d.pop(str(vid), None)
            proj.set_map_views_extent(d)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:748", exc_info=True)

    def _zoom_to_feature(self, layer, fid):
        if layer is None:
            return
        try:
            rect = GgsRectangle.from_shapely(layer.geoms()[int(fid)])
        except Exception:
            exc_note("_zoom_to_feature @ ggis/ui/views/map/map_view.py:767")
            return
        self._zoom_rect(rect)

    def _zoom_rect(self, rect):
        if rect is None or rect.is_empty():
            return
        try:
            self.canvas.zoomToExtent(rect, 1.35)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:767", exc_info=True)

    def _zoom_to_selection_layer(self, layer=None):
        layer = layer or self._current_layer()
        sel = GgsSelection.instance()
        rect = sel.extent(layer) if layer is not None else sel.extent()
        if rect is None or rect.is_empty():
            self._show_status_message(_tr("没有选中要素"), LEVEL_INFO)
            return

        self._zoom_rect(self._extent_in_canvas_crs(rect, layer))

    def zoom_to_selection(self):
        self._zoom_to_selection_layer(None)

    def zoom_to_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None:
            self._show_status_message(_tr("请先选择一个图层"), LEVEL_WARN)
            return False
        try:
            self.canvas.zoomToLayer(lyr)
        except Exception as e:
            exc_note("zoom_to_layer @ ggis/ui/views/map/map_view.py:802")
            self._show_status_message(
                _tr("缩放失败：{0}").format(e), LEVEL_WARN)
            return False
        return True

    def zoom_full(self):
        try:
            self.canvas.zoomToFullExtent()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:801", exc_info=True)

    def _extent_or_none(self):
        try:
            r = self.canvas.extent()
            return (float(r.xmin), float(r.ymin),
                    float(r.xmax), float(r.ymax))
        except Exception:
            exc_note("_extent_or_none @ ggis/ui/views/map/map_view.py:826")
            return None

    def _remember_current_extent(self):
        proj = self._shared_project()
        if proj is None:
            return
        try:
            proj.set_view_extent(self._extent_or_none())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:834", exc_info=True)

        try:
            proj.set_map_views_extent(self._collect_layer_extents())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:839", exc_info=True)

    @property
    def _extent_handler(self):
        h = self.__dict__.get("_extent_handler_obj")
        if h is None:
            h = self._on_view_extent_changed
            self.__dict__["_extent_handler_obj"] = h
        return h

    def _canvas_extent(self):
        return self._extent()

    def _collect_map_view_extents(self):
        return self._collect_layer_extents()

    def _remember_map_view_extent(self, ext):
        return self._remember_layer_extent(ext)

    def _current_view_extent(self):
        return self._extent_or_none()

    def _remember_view_extent(self):
        return self._remember_current_extent()

    def _on_view_extent_changed(self):
        proj = self._shared_project()
        if proj is None:
            return
        ext = self._extent_or_none()
        if ext is None:
            return
        key = [(ext[0] + ext[2]) / 2.0, (ext[1] + ext[3]) / 2.0]
        try:
            key.append(float(self.canvas.scale()))
        except Exception:
            exc_note("_on_view_extent_changed @ ggis/ui/views/map/map_view.py:909")
            key.append(None)
        key = tuple(None if v is None else round(v, 6) for v in key)
        prev = getattr(self, "_view_key", None)
        self._view_key = key
        if getattr(getattr(self, "_host", None), "_mute_view_dirty", False):
            return
        try:
            proj.set_view_extent(ext)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:920", exc_info=True)
        try:
            self._remember_layer_extent(ext)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:925", exc_info=True)
        if prev is not None and prev == key:
            return
        try:
            proj.set_dirty(True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:931", exc_info=True)

    def _on_tree_action(self, kind, item):
        if kind in ("add", "paste", "paste_into", "newgroup", "newgroup_in"):
            if kind == "add":
                self.add_data()
            elif kind == "paste":
                self.paste_layer_from_clipboard()
            elif kind == "paste_into":
                self.paste_layer_from_clipboard(parent_item=item)
            elif kind == "newgroup_in":
                self.new_group(parent_item=item)
            else:
                self.new_group()
            return

        if kind == "refresh_view":

            try:
                self.canvas.refresh_layers()
                self.canvas.invalidate_labels()
            except Exception:
                exc_note("_on_tree_action @ ggis/ui/views/map/map_view.py:971")
                import traceback
                traceback.print_exc()
            return

        view = getattr(self.layer_dock, "view", None)
        if view is not None:
            try:
                view.select_layer_item(item)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:971", exc_info=True)

        lyr = self._item_layer(item)

        if not layer_allows(lyr, kind):
            return

        if kind == "remove":
            self._remove_tree_items(view, item)
        elif kind == "remove_all":
            self._remove_all_layers(view)
        elif kind == "remove_group":
            self._remove_group_item(item)
        elif kind == "zoom":
            self._zoom_to_tree_item(item)
        elif kind == "zoom_sel":
            self._zoom_to_selection_layer(self._item_layer(item))
        elif kind in ("vis_on", "vis_off"):
            self._set_tree_items_visible(view, item, kind == "vis_on")
        elif kind == "zoom_group":
            self._zoom_to_group_item(item)
        elif kind == "table":
            if lyr is None:
                self._show_status_message(_tr("请选择一个图层"), LEVEL_WARN)
                return
            if lyr.is_tile():
                self.open_layer_properties(lyr)
                return
            if not lyr.is_vector():
                self.open_raster_attr_table(lyr)
                return
            self.open_attribute_table(lyr)
        elif kind == "group_selected":
            if view is not None:
                try:
                    view.group_selected_items(item)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:1012", exc_info=True)
        elif kind == "props":
            if lyr is not None:
                self.open_layer_properties(lyr)
            else:
                self.open_group_properties(item)
        elif kind == "symbol":
            if lyr is None:
                return
            self.open_symbology(lyr)
        elif kind == "raster_display":
            self.open_raster_display(lyr)
        elif kind == "raster_histogram":
            self.open_raster_display(lyr, focus="histogram")
        elif kind == "raster_profile":
            self.open_raster_profile(lyr)
        elif kind == "raster_attr":
            self.open_raster_attr_table(lyr)
        elif kind == "filter":
            if lyr is not None and not lyr.is_vector():
                self._show_status_message(
                    _tr("「{0}」是栅格图层，不能按属性过滤").format(lyr.name()),
                    LEVEL_WARN)
                return
            self.filter_active_layer()
        elif kind == "labels":
            self.open_label_settings()
        elif kind == "toggle_labels":
            self.toggle_labels()
        elif kind == "export":
            if lyr is None:
                return
            if lyr.is_tile():
                self.export_tile_layer(lyr)
            elif lyr.is_table():
                self.export_table_layer(lyr)
            elif lyr.is_vector():
                self.export_vector_layer(lyr)
            else:
                self.export_raster_layer(lyr)
        elif kind == "export_style":
            self.export_layer_style(lyr)
        elif kind == "table_to_layer":
            self.table_to_layer_layer(lyr)
        elif kind == "copypath":
            self.copy_layer_path()
        elif kind == "dup":
            self.duplicate_layer(lyr)
        elif kind == "copy":
            self.copy_layer_to_clipboard()
        elif kind == "cut":
            self.cut_layer_to_clipboard()
        else:
            self._show_status_message(
                _tr("该功能将在后续里程碑接入"), LEVEL_INFO)

    def _sync_labeling_to_active(self):
        d = self._view_dock("GgsLabelingDock")
        if d is None or not hasattr(d, "set_layer"):
            return
        try:
            lyr = self._current_layer()
        except Exception:
            exc_note("_sync_labeling_to_active @ ggis/ui/views/map/map_view.py:1088")
            lyr = None
        try:
            d.set_layer(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:1085", exc_info=True)

    def _sync_symbology_to_active(self):

        self._sync_labeling_to_active()
        d = self._view_dock("GgsStylingDock")
        if d is None or not hasattr(d, "set_layer"):
            return
        try:
            lyr = self._current_layer()
        except Exception:
            exc_note("_sync_symbology_to_active @ ggis/ui/views/map/map_view.py:1109")
            lyr = None
        try:
            d.set_layer(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_view.py:1108", exc_info=True)

    def control_group(self):
        from ggis.ui.views.control_group import ViewControlGroup
        _status_widgets = list(getattr(self, "_status_widgets", []) or [])
        return ViewControlGroup(
            "map",
            [self.layer_dock] if getattr(self, "layer_dock", None) is not None
            else [],
            view_tag = self.view_tab_tag(),
            toolbar_tabs = self.ribbon_tabs(),
            status_kind = "map",
            canvas = getattr(self, "canvas", None),
            status_widgets = _status_widgets,
        )

    def view_tab_tag(self):
        from ggis.ui.features.map_ribbon_groups import MAP_RIBBON_TAG
        return MAP_RIBBON_TAG
