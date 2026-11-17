# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note




import logging
import os

from PySide6.QtCore import QThread
from ggis.core.app import settings

from ggis.ui.views._hostdeps import (
                                     _tr,
                                     LEVEL_INFO,
                                     LEVEL_WARN,
                                     LEVEL_SUCCESS,
                                     app_settings,
                                     find_basemap,
                                     Qt,
                                     QTimer,
                                     QApplication,
                                     QDialog,
)


class _IpLocatorThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._res = None

    def run(self):
        try:
            import json
            import urllib.request
            req = urllib.request.Request(
                "https://ipapi.co/json/",
                headers={"User-Agent": "GmaGIS/1.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            lat = float(data.get("latitude"))
            lon = float(data.get("longitude"))
            self._res = (lon, lat, None)
        except Exception as e:
            exc_note("run @ ggis/ui/views/map/map_data.py:69")
            self._res = (None, None, str(e))

    def result(self):
        return self._res


class MapDataMixin:

    def _item_layer(self, item):
        if item is None:
            return None
        from ggis.ui.panels.layertree import ROLE_KIND, ROLE_LAYER_ID
        kind = item.data(0, ROLE_KIND)
        if kind != "layer":
            return None
        layer_id = item.data(0, ROLE_LAYER_ID)
        if not layer_id:
            return None
        try:
            lt = self.layer_tree()
            for l in (list(lt.layers()) if lt is not None else []):
                if str(l.id()) == str(layer_id):
                    return l
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:102", exc_info=True)
        try:
            return self._host.ctx.project.layer_by_id(layer_id)
        except Exception:
            exc_note("_item_layer @ ggis/ui/views/map/map_data.py:115")
            return None

    def _remove_tree_items(self, view, item):

        items = []
        if view is not None:
            try:
                items = [it for it in view.picked_layer_items(item)]
            except Exception:
                exc_note("_remove_tree_items @ ggis/ui/views/map/map_data.py:129")
                items = []
        if not items:
            items = [item] if item is not None else []
        layers = [l for l in (self._item_layer(it) for it in items)
                  if l is not None]
        if not layers:
            return
        for l in layers:
            if not self._confirm_drop_unsaved_layer(l, _tr("移除图层")):
                return
        if len(layers) > 1:
            names = "、".join(l.name() for l in layers[:5])
            if len(layers) > 5:
                names += "…"
            if not self._host.ctx.region("dock")._confirm(
                    _tr("移除图层"),
                    _tr("确定要移除这 {0} 个图层吗？\n{1}").format(
                        len(layers), names)):
                return
        n = 0
        for l in layers:
            if self._host.ctx.project.remove_layer(l):
                n += 1
        if n:
            self._host.show_message(
                _tr("已移除 {0} 个图层").format(n) if n > 1
                else _tr("已移除：{0}").format(layers[0].name()), LEVEL_INFO)
        if self._host.ctx.project.count() == 0:
            try:
                self.canvas.setExtent(self.canvas.extent().copy())
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:157", exc_info=True)

    def _remove_all_layers(self, view):
        if view is None:
            return
        root = view.invisibleRootItem()
        if root is None or root.childCount() == 0:
            return
        layers = []
        seen = set()

        def _walk(it):
            lyr = self._item_layer(it)
            if lyr is not None and str(lyr.id()) not in seen:
                seen.add(str(lyr.id()))
                layers.append(lyr)
            for i in range(it.childCount()):
                _walk(it.child(i))

        for i in range(root.childCount()):
            _walk(root.child(i))
        if not layers:
            return
        for l in layers:
            if not self._confirm_drop_unsaved_layer(l, _tr("移除图层")):
                return
        names = "、".join(l.name() for l in layers[:5])
        if len(layers) > 5:
            names += "…"
        if not self._host.ctx.region("dock")._confirm(
                _tr("移除全部图层"),
                _tr("确定要移除全部 {0} 个图层吗？\n{1}").format(
                    len(layers), names)):
            return
        n = 0
        for l in layers:
            try:
                self._host.ctx.project.remove_layer(l)
                n += 1
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:211", exc_info=True)
        if n:
            self._host.show_message(
                _tr("已移除 {0} 个图层").format(n), LEVEL_INFO)
        if self._host.ctx.project.count() == 0:
            try:
                self.canvas.setExtent(self.canvas.extent().copy())
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:219", exc_info=True)

    def _remove_group_item(self, item):
        from ggis.ui.panels.layertree import ROLE_KIND

        if item is None or item.data(0, ROLE_KIND) != "group":
            return
        layers = []

        def _walk(it):
            lyr = self._item_layer(it)
            if lyr is not None:
                layers.append(lyr)
            for i in range(it.childCount()):
                _walk(it.child(i))

        _walk(item)
        if layers:
            for l in layers:
                if not self._confirm_drop_unsaved_layer(l, _tr("移除分组")):
                    return
            if not self._host.ctx.region("dock")._confirm(
                    _tr("移除分组"),
                    _tr("分组「{0}」里有 {1} 个图层，确定要一起移除吗？").format(
                        item.text(0), len(layers))):
                return
            n = sum(1 for l in layers if self._host.ctx.project.remove_layer(l))
            _msg = _tr("已移除分组及其 {0} 个图层").format(n)
        else:
            _msg = _tr("已移除分组「{0}」").format(item.text(0))
        try:
            view = self.layer_dock.view
            p = item.parent()
            if p is None:
                view.takeTopLevelItem(view.indexOfTopLevelItem(item))
            else:
                p.removeChild(item)
            view.viewport().update()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:282", exc_info=True)
        self._host.show_message(_msg, LEVEL_INFO)

    def _set_tree_items_visible(self, view, item, on):
        layers = self._picked_layers(item)
        if not layers:
            return
        proj = None
        try:
            proj = self.canvas.project()
        except Exception:
            exc_note("_set_tree_items_visible @ ggis/ui/views/map/map_data.py:306")
            proj = None
        for lyr in layers:
            it = None
            try:
                it = self.layer_dock._find_item_by_layer_id(lyr.id())
            except Exception:
                exc_note("_set_tree_items_visible @ ggis/ui/views/map/map_data.py:316")
                it = None
            if it is not None:
                try:
                    it.setCheckState(
                        0, Qt.CheckState.Checked if on
                        else Qt.CheckState.Unchecked)
                    continue
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:321", exc_info=True)
            try:
                if proj is not None:
                    proj.set_layer_visible(lyr, bool(on))
                else:
                    lyr.set_visible(bool(on))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:328", exc_info=True)
        try:
            self.layer_dock.sync_check_states()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:335", exc_info=True)
        if proj is None:
            try:
                self.canvas.refresh_layers()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:341", exc_info=True)
        self._host.show_message(
            _tr("已显示 {0} 个图层").format(len(layers)) if on
            else _tr("已隐藏 {0} 个图层").format(len(layers)), LEVEL_INFO)

    def measure_crs(self):
        try:
            cv = getattr(self, "canvas", None)
            c = cv.effectiveCrs() if cv is not None else None
            if c is not None and c.is_valid():
                return c
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:374", exc_info=True)
        try:
            lyr = self._current_layer()
            if lyr is not None and lyr.crs():
                return lyr.crs()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:380", exc_info=True)
        try:
            c = settings.default_crs()
            if c:
                return c
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:386", exc_info=True)
        for lyr in self._selectable_layers():
            try:
                if lyr.crs():
                    return lyr.crs()
            except Exception:
                exc_note("measure_crs @ ggis/ui/views/map/map_data.py:394")
                continue
        return None

    def _extent_in_canvas_crs(self, rect, layer=None):
        if rect is None or rect.is_empty() or layer is None:
            return rect
        try:
            dst = self.canvas.effectiveCrs()
            src = layer.crs()
        except Exception:
            exc_note("_extent_in_canvas_crs @ ggis/ui/views/map/map_data.py:409")
            return rect
        if dst is None or src is None:
            return rect
        try:
            from ggis.core.crs import (convert_bounds, crs_transformer,
                                    needs_reproject)
            if not needs_reproject(src, dst):
                return rect
            tf = crs_transformer(src, dst)
            if tf is None:
                return rect
            b = convert_bounds((rect.xmin, rect.ymin, rect.xmax, rect.ymax),
                               tf)
            if b is None:
                return rect
            from ggis.core.crs.extent import GgsRectangle
            return GgsRectangle(b[0], b[1], b[2], b[3])
        except Exception:
            exc_note("_extent_in_canvas_crs @ ggis/ui/views/map/map_data.py:427")
            return rect

    def _export_start_dir(self):
        p = self._host.ctx.svc("projects").project_path()
        if p:
            return os.path.dirname(p)
        return self._default_open_dir()

    def _place_measure_panel(self):
        p = self.measure()
        if p is None:
            return
        try:
            c = self.canvas
            tl = c.mapToGlobal(c.rect().topLeft())
            x = tl.x() + c.width() - p.width() - 16
            y = tl.y() + 16
            scr = None
            try:
                scr = QApplication.screenAt(tl) or c.screen()
            except Exception:
                exc_note("_place_measure_panel @ ggis/ui/views/map/map_data.py:463")
                scr = None
            if scr is not None:
                av = scr.availableGeometry()
                x = min(max(x, av.left() + 8),
                        av.right() - p.width() - 8)
                y = min(max(y, av.top() + 8),
                        av.bottom() - p.height() - 8)
            p.move(int(x), int(y))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:470", exc_info=True)

    def _measure_clear(self):
        for n in ("measure_len", "measure_area", "measure_angle"):
            t = getattr(self, "_tools", {}).get(n)
            if t is not None and hasattr(t, "clear"):
                try:
                    t.clear()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:480", exc_info=True)
        p = self.measure()
        if p is not None:
            p.set_result("", "")

    def _measure_close(self):
        self._measure_clear()
        self.set_map_tool("pan")

    def _measure_live_changed(self, on):
        for n in ("measure_len", "measure_area", "measure_angle"):
            t = getattr(self, "_tools", {}).get(n)
            if t is not None:
                try:
                    t.set_show_overlay(bool(on))
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:509", exc_info=True)
        try:
            app_settings.set("measure_show_overlay", bool(on))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:513", exc_info=True)
        try:
            self.canvas.update()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:517", exc_info=True)

    def _recheck_pan_tool(self):
        a = self._host.ctx.svc("actions")._acts.get("pan")
        if a is not None:
            a.setChecked(True)
        try:
            self.canvas.setMapTool("pan")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:527", exc_info=True)

    def _on_nav_action_toggled(self, checked):
        try:
            self._host.ctx.svc("actions").refresh_states()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:540", exc_info=True)
        if checked:
            return
        try:
            QTimer.singleShot(0, self._ensure_nav_checked)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:546", exc_info=True)

    def _ensure_nav_checked(self):
        g = getattr(self, "nav_group", None)
        if g is None:
            return
        try:
            if any(a.isChecked() for a in g.actions()):
                return
        except Exception:
            exc_note("_ensure_nav_checked @ ggis/ui/views/map/map_data.py:566")
            return
        _host = getattr(self, "_host", None)
        if _host is not None:
            mgr = getattr(_host, "_interaction", None)
            if mgr is not None and mgr.has_active_canvas_tool():
                return
        self._recheck_pan_tool()

    def _activate_new_layer(self, lyr, start_drawing=True):
        self.adopt_layer(lyr, select=True, zoom_first=False,
                         check_crs=False, silent=True)
        self._host.log(_tr("已新建图层：{0}").format(lyr.name()))
        if start_drawing:
            try:
                self.set_map_tool("add_feature")
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:593", exc_info=True)
            try:
                self._host.ribbon_region._sync_contextual_tabs()
                i = self._host.ribbon.tab_index(_tr("要素编辑"))
                if i >= 0:
                    self._host.ribbon.tabs.setCurrentIndex(i)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:608", exc_info=True)
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:612", exc_info=True)
        return lyr

    def new_vector_file(self, ext=""):
        from ggis.ui.views.map.dialogs.new_layer import GgsNewLayerDialog
        from ggis.common.base.dialog import GgsFileDialog
        from ggis.io.vector_io import create_vector
        from ggis.core.model.layer import GgsVectorLayer

        dlg = GgsNewLayerDialog(self, title="新建矢量文件",
                                crs=self._host.ctx.region("title")._default_new_crs())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        cfg = dlg.result()

        if ext:
            filt = next((f for f, e in self._NEW_FILE_FORMATS if e == ext),
                        _tr("所有文件 (*)"))
            formats = [(filt, ext)] + [x for x in self._NEW_FILE_FORMATS
                                       if x[1] != ext]
        else:
            formats = list(self._NEW_FILE_FORMATS)
        formats = [(_tr(f), e) for f, e in formats]
        filter_text = ";;".join(
            [f for f, _e in formats] + [_tr("所有文件 (*)")])

        default = os.path.join(self._default_open_dir(),
                               _tr("新建图层") + (ext or ".gpkg"))
        path, chosen = GgsFileDialog.getSaveFileName(
            self, _tr("新建矢量文件"), default, filter_text)
        if not path:
            return None

        if not os.path.splitext(path)[1]:
            guess = ext or ".gpkg"
            for f, e in formats:
                if chosen and str(chosen).startswith(f.split(" (")[0]):
                    guess = e
                    break
            path += guess
        self._remember_dir(path)

        try:
            create_vector(path, geometry_type=cfg["geometry_type"],
                          crs=cfg["crs"], layer=cfg["name"] or None)
        except Exception as e:
            self._host.show_message(
                _tr("无法创建数据源：{0}").format(
                    "%s: %s" % (type(e).__name__, e)), LEVEL_WARN)
            return None

        from ggis.core.crs import GgsCoordinateReferenceSystem as GgsCrs
        try:
            crs_obj = GgsCrs.from_user_input(str(cfg["crs"]))
        except Exception:
            exc_note("new_vector_file @ ggis/ui/views/map/map_data.py:679")
            crs_obj = self._default_layer_crs()
        name = self._unique_layer_name(
            cfg["name"] or os.path.splitext(os.path.basename(path))[0])
        lyr = GgsVectorLayer(name, path, crs_obj, cfg["geometry_type"],
                             [], [], [])
        lyr._valid = True
        self._activate_new_layer(lyr)
        self._host.show_message(
            _tr("已新建：{0}（{1}）").format(
                name, os.path.basename(path)), LEVEL_INFO)
        return lyr

    def new_layer_from_dialog(self):
        from ggis.ui.views.map.dialogs.new_layer import GgsNewLayerDialog
        from ggis.common.base.dialog import GgsFileDialog
        from ggis.io.vector_io import create_vector
        from ggis.io.formats import vector_filter_for
        from ggis.core.model.layer import GgsVectorLayer
        from ggis.core.crs import GgsCoordinateReferenceSystem as GgsCrs

        dlg = GgsNewLayerDialog(
            self, title="新建图层", kind="polygon", crs="EPSG:4326",
            show_format=True, show_create_type=True, show_fields=True,
            create_type="file")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        cfg = dlg.result()
        fields = list(cfg["fields"] or [])
        geo = cfg["geometry_type"] or "Polygon"

        try:
            crs_obj = GgsCrs.from_user_input(str(cfg["crs"] or "EPSG:4326"))
        except Exception:
            exc_note("new_layer_from_dialog @ ggis/ui/views/map/map_data.py:718")
            crs_obj = self._default_layer_crs()

        if cfg["create_type"] == "memory":
            name = self._unique_layer_name(cfg["name"] or _tr("新建图层"))
            lyr = GgsVectorLayer(name, "", crs_obj, geo, [], [], fields)
            lyr._valid = True
            self._activate_new_layer(lyr)
            self._host.show_message(
                _tr("已新建内存图层：{0}（{1}）").format(name, geo), LEVEL_INFO)
            return lyr

        suffix = cfg["format"] or ".gpkg"
        driver = cfg["driver"] or None
        path = (cfg.get("filename") or "").strip()
        if not path:
            default = os.path.join(self._default_open_dir(),
                                   _tr("新建图层") + suffix)
            f = vector_filter_for(suffix)
            filter_text = ";;".join([_tr(f), _tr("所有文件 (*)")]) if f \
                else _tr("所有文件 (*)")
            path, _chosen = GgsFileDialog.getSaveFileName(
                self, _tr("新建图层"), default, filter_text)
            if not path:
                return None
            if not os.path.splitext(path)[1]:
                path += suffix
        self._remember_dir(path)

        try:
            create_vector(path, geometry_type=geo,
                          crs=str(cfg["crs"] or "EPSG:4326"),
                          driver=driver or None,
                          layer=cfg["name"] or None, fields=fields)
        except Exception as e:
            self._host.show_message(
                _tr("无法创建数据源：{0}").format(
                    "%s: %s" % (type(e).__name__, e)), LEVEL_WARN)
            return None

        name = self._unique_layer_name(
            cfg["name"] or os.path.splitext(os.path.basename(path))[0])
        lyr = GgsVectorLayer(name, path, crs_obj, geo, [], [], fields)
        lyr._valid = True
        self._activate_new_layer(lyr)
        self._host.show_message(
            _tr("已新建：{0}（{1}）").format(
                name, os.path.basename(path)), LEVEL_INFO)
        return lyr

    def _default_open_dir(self):
        last = str(app_settings.get("last_open_dir") or "")
        if last and os.path.isdir(last):
            return last
        try:
            for lyr in self._host.ctx.project.layers():
                src = str(lyr.source() or "")
                d = os.path.dirname(src)
                if d and os.path.isdir(d):
                    return d
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:779", exc_info=True)
        return os.path.expanduser("~")

    def _remember_dir(self, path):
        try:
            d = os.path.dirname(str(path or ""))
            if d and os.path.isdir(d):
                app_settings.set("last_open_dir", d)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:788", exc_info=True)

    def _load_paths(self, paths):
        ok, bad = 0, []
        _ps = list(paths or [])
        single = len(_ps) == 1
        for p in reversed(_ps):
            if self._add_data_path(p, is_user=True, activate=single):
                ok += 1
            else:
                bad.append(p)
        if ok and not bad:
            self._host.show_message(_tr("已加载 {0} 个图层").format(ok), LEVEL_INFO)
        elif bad and not ok:
            self._host.show_message(_tr("{0} 个文件加载失败").format(len(bad)),
                              LEVEL_WARN)
        elif ok and bad:
            self._host.show_message(
                _tr("已加载 {0} 个图层，{1} 个失败").format(ok, len(bad)),
                LEVEL_WARN)
        return ok

    def add_vector(self):
        from ggis.common.base.dialog import GgsFileDialog
        from ggis.io.vector_io import VECTOR_SUFFIXES
        pat = " ".join("*" + s for s in sorted(VECTOR_SUFFIXES))
        paths, _ = GgsFileDialog.getOpenFileNames(
            self, _tr("添加矢量图层"), self._default_open_dir(),
            _tr("矢量数据 ({0});;所有文件 (*)").format(pat))
        if paths:
            self._remember_dir(paths[0])
        return self._load_paths(paths)

    def add_raster(self):
        from ggis.common.base.dialog import GgsFileDialog
        from ggis.io.raster_io import RASTER_SUFFIXES
        pat = " ".join("*" + s for s in sorted(RASTER_SUFFIXES))
        paths, _ = GgsFileDialog.getOpenFileNames(
            self, _tr("添加栅格图层"), self._default_open_dir(),
            _tr("栅格数据 ({0});;所有文件 (*)").format(pat))
        if paths:
            self._remember_dir(paths[0])
        return self._load_paths(paths)

    def add_from_path(self):
        from ggis.common.base.dialog import GgsInputDialog
        text, ok = GgsInputDialog.getMultiLineText(
            self, _tr("从路径添加"),
            _tr("每行一个文件路径："),
            "")
        if not ok or not text:
            return 0
        paths = []
        for line in str(text).splitlines():
            p = line.strip().strip('"').strip("'")
            if p:
                paths.append(p)
        if not paths:
            return 0
        return self._load_paths(paths)

    def add_xy_points(self):
        return self.add_text_layer()

    def _import_text(self, path):
        from ggis.ui.views.map.dialogs.csv import GgsCsvImportDialog
        from ggis.io.csv_io import read_table_points
        dlg = GgsCsvImportDialog(self, path=path)
        try:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
        except AttributeError:
            exc_note("_import_text @ ggis/ui/views/map/map_data.py:881")
            return None
        info = dlg.result_info()
        if not info:
            return None
        r = read_table_points(
            info["path"], info["x_field"], info["y_field"],
            crs=info["crs"], encoding=info["encoding"],
            delimiter=info["delimiter"], name=info["name"] or None)
        if hasattr(r, "on_done"):
            r.on_done(lambda ev: self._adopt_table_layer(ev.get("result")))
            r.on_fail(lambda ev: self._host.show_message(
                _tr("导入失败：{0}").format(ev.get("error")), LEVEL_WARN))
            return r
        return self._adopt_table_layer(r)

    def _alloc_load_seq(self):
        try:
            t = self.layer_tree()
            return t.next_seq() if t is not None else None
        except Exception:
            logging.getLogger("gmagis").warning(
                "swallowed _alloc_load_seq @ map_data.py", exc_info=True)
            return None

    def _take_drop_target(self, path):
        try:
            dock = getattr(self, "layer_dock", None)
            fn = getattr(dock, "take_drop_target", None)
            if callable(fn):
                return fn(path)
        except Exception:
            logging.getLogger("gmagis").warning(
                "swallowed _take_drop_target @ map_data.py", exc_info=True)
        return None

    def adopt_layer(self, layer, *, pos=None, group=None, ctx=None, seq=None,
                    select=True, zoom_first=True, check_crs=True,
                    silent=False, note="", what="", add_to_project=True):
        if layer is None or not layer.is_valid():
            self._host.show_message(
                _tr("加载失败：{0}").format(
                    layer.error() if layer is not None else _tr("未知错误")),
                LEVEL_WARN)
            return None
        proj = self._host.ctx.project
        tree = self.layer_tree()
        had = bool(tree is not None and list(tree.layers()))
        if ctx is not None:
            ctx["had"] = had
        if seq is None and ctx is not None:
            seq = ctx.get("seq")
        if seq is None:
            seq = self._alloc_load_seq()
        if group is None and ctx is not None:
            group = ctx.get("drop_group") or None
        if group is None and ctx is None:
            try:
                src = layer.source()
            except Exception:
                src = None
            if src:
                group = self._take_drop_target(src)
        if add_to_project:
            proj.add_layer(layer)
        try:
            self._add_layer_to_current_view_tree(
                layer, pos=pos, group=group, seq=seq)
        except Exception:
            logging.getLogger("gmagis").warning(
                "swallowed adopt_layer @ map_data.py", exc_info=True)
        if select:
            try:
                self._select_layer_in_tree(layer)
            except Exception:
                logging.getLogger("gmagis").warning(
                    "swallowed adopt_layer select @ map_data.py",
                    exc_info=True)
        if check_crs:
            try:
                self._check_crs_mismatch(layer, proj)
            except Exception:
                logging.getLogger("gmagis").warning(
                    "swallowed adopt_layer crs @ map_data.py",
                    exc_info=True)
        if (zoom_first and not had and not layer.is_table()
                and not (ctx is not None and ctx.get("zoomed"))):
            try:
                self.canvas.zoomToLayer(layer)
                if ctx is not None:
                    ctx["zoomed"] = True
            except Exception:
                logging.getLogger("gmagis").warning(
                    "swallowed adopt_layer zoom @ map_data.py",
                    exc_info=True)
            try:
                self._host.ctx.svc("views")._on_view_method(
                    "set_map_tool", "pan")
            except Exception:
                logging.getLogger("gmagis").warning(
                    "swallowed adopt_layer pan @ map_data.py",
                    exc_info=True)
        if not silent:
            msg = what or _tr("已加载：{0}（{1}）").format(
                layer.name(), layer.type_label())
            if note:
                msg = _tr("{0}，{1}").format(msg, note)
            self._host.show_message(
                msg, LEVEL_INFO if not note else LEVEL_WARN)
        return layer

    def _adopt_layer(self, lyr, note="", what=""):
        return self.adopt_layer(lyr, note=note, what=what)

    def add_data(self):
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, _tr("添加数据"),
            "", _tr("空间数据 ({0});;所有文件 (*)").format(
                " ".join("*" + s for s in
                         ("shp geojson gpkg json tif tiff "
                          "csv tsv txt xlsx").split())))
        single = len(paths or []) == 1
        _ps = list(paths or [])
        for p in reversed(_ps):
            self._add_data_path(p, is_user=True, activate=single)

    def add_basemap(self, key):
        src = find_basemap(key)
        if src is None:
            return None
        return self.add_tile_layer(src)

    def _init_async_load(self):
        if getattr(self, "_async_wired", False):
            return
        from ggis.io import async_loader as async_io
        try:
            async_io.loadProgressSignal().connect(self._on_load_progress)
            async_io.loadFinishedSignal().connect(self._on_load_finished)
            async_io.loadFailedSignal().connect(self._on_load_failed)
            async_io.loadPartialSignal().connect(self._on_load_partial)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:985", exc_info=True)
        try:
            from ggis.io import raster_pyramid as pyr
            pyr.pyramidProgressSignal().connect(self._on_pyramid_progress)
            pyr.pyramidFinishedSignal().connect(self._on_pyramid_finished)
            pyr.pyramidPartialSignal().connect(self._on_pyramid_partial)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:993", exc_info=True)
        self._async_wired = True

    def _on_load_progress(self, info):
        try:
            if info.get("total"):
                self._host.update_load(info.get("done", 0), info.get("total", 0))
            else:
                self._host.begin_load(os.path.basename(info.get("path", "")))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1005", exc_info=True)

    def _on_load_partial(self, info):
        try:
            ctx = self._async_pending.get(info.get("token"), None)
            if ctx is None:
                return
            lyr = info.get("layer")
            if lyr is None or not lyr.is_valid():
                return
            if bool(info.get("first")) and not ctx.get("added"):
                ctx["added"] = True
                self.adopt_layer(
                    lyr, ctx=ctx, select=False, silent=True,
                    zoom_first=bool(ctx.get("is_user")),
                    check_crs=not lyr.is_table())
            try:
                self.canvas.rerender()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1050", exc_info=True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1052", exc_info=True)

    def _on_load_finished(self, info):
        ctx = self._async_pending.pop(info.get("token"), None)
        try:
            self._host.end_load()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1060", exc_info=True)
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.hide_busy()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1066", exc_info=True)
        if ctx is None:
            return
        lyr = info.get("layer")
        if lyr is None:
            return
        try:
            if not ctx.get("added"):
                self.adopt_layer(
                    lyr, ctx=ctx, select=False, silent=True,
                    zoom_first=bool(ctx.get("is_user")),
                    check_crs=not lyr.is_table())
            if ctx.get("activate"):
                try:
                    self._select_layer_in_tree(lyr)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1097", exc_info=True)
            if ctx.get("added"):
                try:
                    self.canvas.rerender()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1135", exc_info=True)
            try:
                self.canvas.prewarm_flat(force=True)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1139", exc_info=True)
            if not ctx.get("silent"):
                self._host.show_message(
                    _tr("已加载：{0}（{1}）").format(
                        lyr.name(), lyr.type_label()),
                    LEVEL_INFO)
            self._maybe_build_pyramid(lyr)
        except Exception as e:
            self._host.show_message(
                _tr("加载失败：{0} ({1})").format(info.get("path"), e),
                LEVEL_WARN)

    def _maybe_build_pyramid(self, layer):
        try:
            if layer is None or not layer.is_raster():
                return False
            src = str(layer.source() or "")
            from ggis.io import raster_pyramid as pyr
            if not pyr.needs_pyramid(src):
                return False
            if not pyr.build_async(src):
                return False
            self._pyr_quicklook_path = None
            self._host.show_message(
                _tr("正在建立显示金字塔（{0}）").format(
                    layer.name()), LEVEL_INFO)
            self._host.log(_tr("后台建立显示金字塔：{0}").format(src))
            return True
        except Exception:
            exc_note("_maybe_build_pyramid @ ggis/ui/views/map/map_data.py:1168")
            return False

    def _on_pyramid_progress(self, info):
        try:
            done = float(info.get("done") or 0)
            total = max(1.0, float(info.get("total") or 1))
            if not getattr(self, "_pyr_active", False):
                self._pyr_active = True
                try:
                    from ggis.ui.dialogs import busy as _busy
                    _busy.show_busy(
                        self, _tr("建立显示金字塔"),
                        _tr("正在建立显示金字塔…"),
                        owner="pyramid")
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1197", exc_info=True)
            self._host.update_load(int(1000 * min(1.0, done / total)), 1000)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1200", exc_info=True)

    def _on_pyramid_partial(self, info):
        try:
            path = str(info.get("path") or "")
        except Exception:
            exc_note("_on_pyramid_partial @ ggis/ui/views/map/map_data.py:1204")
            return
        if not path:
            return
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1219", exc_info=True)
        try:
            if getattr(self, "_pyr_quicklook_path", None) != path:
                self._pyr_quicklook_path = path
                self._host.show_message(
                    _tr("缩略图已就绪，正在精细化显示金字塔"), LEVEL_INFO)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1227", exc_info=True)

    def _on_pyramid_finished(self, info):
        try:
            if getattr(self, "_pyr_active", False):
                self._pyr_active = False
                from ggis.ui.dialogs import busy as _busy
                _busy.hide_busy(owner="pyramid")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1239", exc_info=True)
        try:
            if info.get("meta"):
                self.canvas.refresh()
                self._host.show_message(
                    _tr("显示金字塔已就绪"),
                    LEVEL_SUCCESS)
                self._host.log(_tr("显示金字塔已就绪：{0}").format(
                    os.path.basename(str(info.get("path") or ""))))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1249", exc_info=True)

    def _on_load_failed(self, info):
        ctx = self._async_pending.pop(info.get("token"), None)
        try:
            _p = info.get("path")
            _dock = getattr(self, "layer_dock", None)
            if (_p and _dock is not None
                    and hasattr(_dock, "discard_pending")):
                _dock.discard_pending([_p])
        except Exception:
            logging.getLogger("gmagis").warning(
                "swallowed discard_pending @ map_data.py", exc_info=True)
        try:
            self._host.end_load()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1257", exc_info=True)
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.hide_busy()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1263", exc_info=True)
        if ctx is not None and ctx.get("silent"):
            return
        if info.get("cancelled"):
            return
        self._host.show_message(
            _tr("加载失败：{0} ({1})").format(
                info.get("path", ""), info.get("error", "")),
            LEVEL_WARN)

    def _add_data_path(self, path, is_user=False, silent=False, layer=None,
                       activate=False):
        from ggis.io.registry import is_supported, load_file
        from ggis.io import async_loader as async_io
        if not is_supported(path):
            if not silent:
                self._host.show_message(
                    _tr("不支持的文件类型：{0}").format(path), LEVEL_WARN)
            return False

        if layer is None and not silent and is_user:
            asked = self._ask_multi_layers(path)
            if asked is not None:
                picked, group_name = asked
                if not picked:
                    return False
                _one = (len(picked) == 1)
                ok = False
                for nm in reversed(list(picked)):
                    lyr = self._add_data_path(
                        path, is_user=is_user, silent=silent, layer=nm,
                        activate=_one)
                    ok = bool(lyr) or ok
                    if lyr is not None and group_name:
                        self._place_layer_in_file_group(lyr, group_name)
                return ok

        seq = self._alloc_load_seq()
        drop_group = self._take_drop_target(path)

        if layer is None:
            from ggis.io.vector_io import is_vector_path as _is_vector_path
            from ggis.io.table_io import is_table_path as _is_table_path
            _tab = _is_table_path(path)
            if not _tab:
                try:
                    self.canvas.prefetch_source(str(path))
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1351", exc_info=True)
            token = async_io.load_async(
                path, layer=layer,
                progressive=bool(_is_vector_path(path) and not _tab))
            self._async_pending[token] = {
                "is_user": bool(is_user), "silent": bool(silent),
                "activate": bool(activate), "seq": seq,
                "drop_group": drop_group}
            try:
                from ggis.ui.dialogs import busy as _busy
                _busy.show_busy_delayed(
                    self, _tr("读取数据"),
                    _tr("正在读取：{0}").format(os.path.basename(str(path))),
                    delay_ms=300, cancellable=True,
                    cancel_cb=lambda t=int(token): async_io.cancel(t))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1372", exc_info=True)
            try:
                self._host.begin_load(os.path.basename(str(path)))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1376", exc_info=True)
            self._host.log(_tr("正在后台加载：{0}").format(path))
            return True

        lyr = load_file(path, layer=layer)
        if lyr is None:
            if not silent:
                self._host.show_message(
                    _tr("无法加载：{0}").format(path), LEVEL_WARN)
            return False
        if not lyr.is_valid():
            if not silent:
                self._host.show_message(
                    _tr("加载失败：{0} ({1})").format(path, lyr.error()),
                    LEVEL_WARN)
            return False
        self.adopt_layer(lyr, select=False, silent=True,
                         zoom_first=bool(is_user),
                         check_crs=not lyr.is_table(),
                         seq=seq, group=drop_group)
        try:
            self.canvas.prewarm_flat(force=True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1423", exc_info=True)
        if not silent:
            self._host.show_message(
                _tr("已加载：{0}（{1}）").format(
                    lyr.name(), lyr.type_label()),
                LEVEL_INFO)
        self._maybe_build_pyramid(lyr)
        if activate:
            try:
                self._select_layer_in_tree(lyr)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1438", exc_info=True)
        return lyr

    def _place_layer_in_file_group(self, lyr, group_name):
        if lyr is None or not group_name:
            return
        try:
            dock = self.layer_dock
            if dock is None:
                logging.getLogger("gmagis").warning(
                    "按文件名建分组失败：图层 DOCK 未挂载（group=%s）",
                    group_name)
                return
            grp = dock.ensure_group(group_name)
            if grp is None:
                logging.getLogger("gmagis").warning(
                    "按文件名建分组失败：ensure_group 返回空（group=%s）",
                    group_name)
                return
            dock.move_layer_to_group(lyr.id(), grp)
        except Exception:
            logging.getLogger("gmagis").warning(
                "swallowed ggis/ui/views/map_data.py:1486 "
                "_place_layer_in_file_group", exc_info=True)

    def _parse_xy(text):
        import re
        s = str(text or "")
        for ch in ("，", "；", ";", "\t"):
            s = s.replace(ch, ",")
        parts = [p for p in re.split(r"[,\s]+", s.strip()) if p]
        if len(parts) < 2:
            return None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            exc_note("_parse_xy @ ggis/ui/views/map/map_data.py:1458")
            return None

    def locate_xy(self):
        from PySide6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QLabel,
            QWidget, QPushButton,
        )
        from ggis.common.base.dialog import GgsDialog
        from ggis.core.crs.extent import GgsRectangle

        dlg = GgsDialog(self)
        dlg.setWindowTitle(_tr("定位到"))
        try:
            from ggis.common.styling import icons as _icons
            dlg.setWindowIcon(_icons.icon("locate", size=16))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1475", exc_info=True)
        dlg.setModal(True)

        body = QVBoxLayout()
        body.setContentsMargins(20, 16, 20, 14)
        body.setSpacing(12)

        grid = QFormLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        ed_x = QLineEdit("")
        ed_y = QLineEdit("")
        for _ed in (ed_x, ed_y):
            _ed.setMinimumWidth(180)
        grid.addRow(_tr("X（经度 / 东向）") + "：", ed_x)
        grid.addRow(_tr("Y（纬度 / 北向）") + "：", ed_y)
        body.addLayout(grid)

        cs = QComboBox()
        cs.addItem(_tr("地图坐标系"))
        cs.addItem(_tr("经纬度（WGS84）"))
        body.addWidget(QLabel(_tr("坐标参照：")))
        body.addWidget(cs)

        row = QHBoxLayout()
        row.addStretch(1)
        btn_ok = QPushButton(_tr("定位"))
        btn_ok.setDefault(True)
        btn_cancel = QPushButton(_tr("取消"))
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)
        body.addLayout(row)

        w = QWidget()
        w.setLayout(body)
        dlg.setLayout(w.layout())
        dlg.setFixedWidth(380)
        dlg._ok = False

        def _accept():
            dlg._ok = True
            dlg.accept()

        btn_ok.clicked.connect(_accept)
        btn_cancel.clicked.connect(dlg.reject)

        dlg.exec()
        if not getattr(dlg, "_ok", False):
            return False
        try:
            x = float(str(ed_x.text()).strip())
            y = float(str(ed_y.text()).strip())
        except ValueError:
            self._host.show_message(
                _tr("坐标格式无法识别：{0}, {1}").format(
                    ed_x.text(), ed_y.text()), LEVEL_WARN)
            return False
        if cs.currentIndex() == 1:
            pt = self._wgs84_to_project(y, x)
            if pt is None:
                self._host.show_message(
                    _tr("经纬度转换失败"), LEVEL_WARN)
                return False
            x, y = pt
        self._pan_to(x, y)
        self._host.show_message(
            _tr("已定位到 {0}, {1}").format("%.6f" % x, "%.6f" % y),
            LEVEL_INFO)
        return True

    def _wgs84_to_project(self, lat, lon):
        try:
            from ggis.core.crs import crs_transformer
            dst = self.canvas.effectiveCrs()
            tf = crs_transformer("EPSG:4326", dst)
            if tf is None:
                return (lon, lat)
            return tf.transform(lon, lat)
        except Exception:
            exc_note("_wgs84_to_project @ ggis/ui/views/map/map_data.py:1565")
            return None

    def _pan_to(self, x, y):
        try:
            from ggis.core.crs.extent import GgsRectangle
            ext = self.canvas.extent()
            w = ext.width() or 1.0
            h = ext.height() or 1.0
            self.canvas.setExtent(
                GgsRectangle(x - w / 2.0, y - h / 2.0,
                             x + w / 2.0, y + h / 2.0))
        except Exception as e:
            self._host.show_message(
                _tr("定位失败：{0}").format(e), LEVEL_WARN)

    def visible_extent_layers(self):
        src = None
        tree = getattr(self, "_layer_tree", None)
        if tree is not None:
            try:
                src = list(tree.visible_layers())
            except Exception:
                exc_note("visible_extent_layers @ ggis/ui/views/map/map_data.py:1600")
                src = None
        if src is None:
            try:
                src = list(self._project().layers())
            except Exception:
                exc_note("visible_extent_layers @ ggis/ui/views/map/map_data.py:1605")
                src = []
        out = []
        for l in src:
            try:
                if l is None or not l.is_valid():
                    continue
            except Exception:
                exc_note("visible_extent_layers @ ggis/ui/views/map/map_data.py:1612")
                continue
            out.append(l)
        return out

    def zoom_visible(self):
        cv = self.canvas
        if cv is None:
            return False
        proj = self._project()
        if proj is None:
            return False
        try:
            dst = cv.destinationCrs()
        except Exception:
            exc_note("zoom_visible @ ggis/ui/views/map/map_data.py:1637")
            dst = None
        src = self.visible_extent_layers()
        if not src:
            self._host.show_message(
                _tr("没有可见图层，无法缩放"), LEVEL_WARN)
            return False
        ext = proj.extent_of_layers(src, dst, include_tiles=True)
        if ext is None or ext.is_empty():
            self._host.show_message(
                _tr("没有可见图层，无法缩放"), LEVEL_WARN)
            return False
        try:
            cv.setExtent(ext)
        except Exception as e:
            self._host.show_message(
                _tr("缩放失败：{0}").format(e), LEVEL_WARN)
            return False
        return True

    def new_group(self, parent_item=None):
        try:
            parent, idx = self.layer_dock.resolve_add_target()
            if parent_item is not None:
                parent, idx = parent_item, 0
            it = self.layer_dock.add_group(_tr("组"), parent=parent, pos=idx)
            try:
                self.layer_dock.view.setCurrentItem(it)
                self.layer_dock.view.editItem(it, 0)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1672", exc_info=True)
            return it
        except Exception as e:
            self._host.show_message(
                _tr("新建分组失败：{0}").format(e), LEVEL_WARN)
            return None

    def _reflow_measure_panel(self):
        p = self.measure()
        if p is None:
            return
        try:
            if p.isVisible():
                self._place_measure_panel()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_data.py:1707", exc_info=True)

