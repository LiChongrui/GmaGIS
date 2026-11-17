# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note




import logging
import os

from ggis.ui.views._hostdeps import (
    _tr, LEVEL_INFO, LEVEL_SUCCESS, LEVEL_WARN, LEVEL_WARNING,
    LEVEL_CRITICAL, GgsSelection, GgsMsgBox, app_settings,
    VECTOR_WRITE_FORMATS, vector_suffix_for_driver,
    ROLE_KIND, ROLE_LAYER_ID, Qt, QTimer, QApplication, QDialog,
)


_LAYER_CLIP = {"entries": None}


def ggs_layer_clip():
    c = _LAYER_CLIP["entries"]
    if not c:
        return []
    if isinstance(c, dict):
        return [{"kind": "layer", "snap": c}]
    try:
        return list(c)
    except Exception:
        exc_note("ggs_layer_clip @ ggis/ui/views/map/map_layer.py:52")
        return []


def ggs_set_layer_clip(entries):
    _LAYER_CLIP["entries"] = entries


class MapLayerMixin:

    SNAP_KIND_ACTS = ("snap_endpoint", "snap_vertex", "snap_intersection",
                      "snap_midpoint", "snap_edge")

    _GEOM_OP_SPECS = {
        "split": ("分割：在地图上画一条分割线（画完自动切开被穿过的要素）",
                  True),
        "reshape": ("修整：画一条线切一刀，只保留含原中心的那一块", False),
        "align": ("对齐：画一条参考线，所选要素会整体平移到线上", False),
        "break": ("打断：画一条线，与它相交的线要素会在交点处断开", True),
    }

    _GEOM_OP_ACTS = (("split_features", "split"),
                     ("reshape_features", "reshape"),
                     ("align_features", "align"),
                     ("break_features", "break"))

    _NEW_FILE_FORMATS = tuple(
        (filter_text, suffix)
        for suffix, _drv, _name, filter_text in VECTOR_WRITE_FORMATS)

    _MULTI_LAYER_SUFFIXES = (".gpkg", ".gdb", ".sqlite", ".kml", ".kmz",
                           ".gml")

    def _add_layer_to_current_view_tree(self, layer, pos=None, group=None,
                                        seq=None):
        if layer is None:
            return
        v = self._host._current_map_view()
        if v is None:
            return
        tree = getattr(v, "_layer_tree", None)
        if tree is None:
            return
        try:
            tree.add(layer, pos=pos, group=group, seq=seq)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map/map_layer.py:_add_layer_to_current_view_tree", exc_info=True)

    def _layer_has_unsaved_edits(self, lyr):
        if lyr is None:
            return (False, "")
        dirty = False
        try:
            dirty = any(s.layer() is lyr for s in self._dirty_sessions())
        except Exception:
            exc_note("_layer_has_unsaved_edits @ ggis/ui/views/map/map_layer.py:144")
            dirty = False
        draft = False
        try:
            t = self._vertex_tool()
            if t is not None and t.has_draft() and t.layer() is lyr:
                draft = True
        except Exception:
            exc_note("_layer_has_unsaved_edits @ ggis/ui/views/map/map_layer.py:151")
            draft = False
        if not (dirty or draft):
            return (False, "")
        parts = []
        if dirty:
            parts.append(_tr("有未保存的编辑"))
        if draft:
            parts.append(_tr("有尚未确认的折点改动"))
        return (True, _tr("，".join(parts)))

    def _confirm_drop_unsaved_layer(self, lyr, action):
        try:
            has, why = self._layer_has_unsaved_edits(lyr)
        except Exception:
            exc_note("_confirm_drop_unsaved_layer @ ggis/ui/views/map/map_layer.py:178")
            return True
        if not has:
            return True
        try:
            nm = lyr.name()
        except Exception:
            exc_note("_confirm_drop_unsaved_layer @ ggis/ui/views/map/map_layer.py:184")
            nm = ""
        return self._host.ctx.region("dock")._confirm(
            action,
            _tr("图层「{0}」{1}。\n确定要{2}吗？").format(nm, why, action))

    def _picked_layers(self, item):
        view = getattr(self.layer_dock, "view", None)
        items = []
        if view is not None:
            try:
                items = list(view.picked_layer_items(item))
            except Exception:
                exc_note("_picked_layers @ ggis/ui/views/map/map_layer.py:198")
                items = []
        if not items:
            items = [item] if item is not None else []
        out, seen = [], set()
        for it in items:
            lyr = self._item_layer(it)
            if lyr is None:
                continue
            lid = lyr.id()
            if lid in seen:
                continue
            seen.add(lid)
            out.append(lyr)
        return out

    def duplicate_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先选择一个图层"), LEVEL_WARN)
            return None
        try:
            from ggis.core.model.layer import GgsVectorLayer, GgsRasterLayer
            if lyr.is_vector():
                copy = GgsVectorLayer(
                    _tr("{0} 副本").format(lyr.name()), lyr.source(),
                    lyr.crs(), lyr.geometry_type(),
                    list(lyr.geoms()), list(lyr.attrs()), list(lyr.fields()))
            else:
                copy = GgsRasterLayer(
                    _tr("{0} 副本").format(lyr.name()), lyr.source(),
                    lyr.crs(), lyr.dataset())
            copy.set_visible(lyr.is_visible())
            copy.set_opacity(lyr.opacity())
        except Exception as e:
            self._host.show_message(_tr("复制图层失败：{}").format(e), LEVEL_WARNING)
            return None
        try:
            self._copy_layer_style(lyr, copy)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:257", exc_info=True)
        try:
            copy.set_subset(lyr.subset_fids(), lyr.subset_expression())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:266", exc_info=True)
        self.adopt_layer(copy, select=False, zoom_first=False,
                         check_crs=False, silent=True)
        self._host.show_message(
            _tr("已复制图层：{0}").format(copy.name()), LEVEL_SUCCESS)
        return copy

    @staticmethod
    def _copy_layer_style(src, dst):
        from ggis.render import renderers as _rd
        from ggis.render import labeling as _lab
        try:
            r = _rd.get_renderer(src)
            if r is not None:
                _rd.set_renderer(dst, _rd.GgsFeatureRenderer.from_dict(
                    r.to_dict()))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:302", exc_info=True)
        try:
            ls = _lab.get_label_style(src)
            if ls is not None:
                _lab.set_label_style(dst, _lab.LabelStyle.from_dict(
                    ls.to_dict()))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:309", exc_info=True)

    def open_layer_properties(self, layer=None):
        layer = layer or self._current_layer()
        if layer is None:
            self._host.show_message(_tr("请先选择一个图层"), LEVEL_WARN)
            return None
        try:
            from ggis.ui.dialogs.app import LayerPropertiesDialog
        except Exception as e:
            self._host.show_message(_tr("图层属性对话框加载失败：{}").format(e),
                              LEVEL_WARNING)
            return None
        dlg = LayerPropertiesDialog(layer, self, self)
        if not dlg.exec():
            return None
        action = dlg.crs_action()
        target = dlg.selected_crs()
        if action != LayerPropertiesDialog.CRS_KEEP and target is not None:
            self.apply_layer_crs(layer, target, action)
        try:
            _new_src = dlg.new_source()
        except Exception:
            exc_note("open_layer_properties @ ggis/ui/views/map/map_layer.py:336")
            _new_src = ""
        if _new_src:
            self.relink_layer_source(layer, _new_src)
        return dlg

    def open_group_properties(self, item):
        if item is None:
            return None
        from ggis.ui.panels.layertree import ROLE_KIND
        name = item.text(0)
        n_layers = 0
        n_groups = 0

        def _walk(it):
            nonlocal n_layers, n_groups
            for i in range(it.childCount()):
                c = it.child(i)
                k = c.data(0, ROLE_KIND)
                if k == "layer":
                    n_layers += 1
                elif k == "group":
                    n_groups += 1
                    _walk(c)

        _walk(item)
        try:
            from ggis.ui.dialogs.app import GroupPropertiesDialog
        except Exception as e:
            self._host.show_message(
                _tr("分组属性对话框加载失败：{}").format(e), LEVEL_WARNING)
            return None
        dlg = GroupPropertiesDialog(name, n_layers, n_groups, self)
        dlg.exec()
        return dlg

    def relink_layer_source(self, layer, new_source):
        if layer is None:
            return False
        src = str(new_source or "").strip()
        if not src or src == str(layer.source() or ""):
            return False

        if bool(layer.is_tile()):
            try:
                from ggis.core.analysis.tile import GgsTileSource
            except Exception as e:
                self._host.show_message(_tr("换数据源失败：{0}").format(e), LEVEL_WARN)
                return False
            old = layer.tile_source()
            try:
                new = GgsTileSource(
                    url=src,
                    name=(old.name if old else ""),
                    title=(old.title if old else ""),
                    icon=(old.icon if old else "xyz_tile"),
                    subdomains=(old.subdomains if old else ()),
                    min_zoom=(old.min_zoom if old else 0),
                    max_zoom=(old.max_zoom if old else 19),
                    crs=(old.crs if old else ""),
                    tile_size=(old.tile_size if old else 256),
                    tms=(old.tms if old else False),
                    attribution=(old.attribution if old else ""),
                    headers=(old.headers if old else None))
            except Exception as e:
                self._host.show_message(_tr("换数据源失败：{0}").format(e), LEVEL_WARN)
                return False
            if not new.is_valid():
                self._host.show_message(
                    _tr("服务地址无效：模板必须含 {x} {y} {z} 占位符"),
                    LEVEL_WARN)
                return False
            layer.set_tile_source(new)
            layer.relink_source(src)
            self._after_relink(layer, src)
            return True

        import os as _os
        if not _os.path.exists(src):
            self._host.show_message(
                _tr("数据源不存在：{0}").format(src),
                LEVEL_WARN)
            return False
        from ggis.io.registry import is_supported, load_file
        if not is_supported(src):
            self._host.show_message(
                _tr("不支持的文件类型：{0}").format(src),
                LEVEL_WARN)
            return False
        new = load_file(src)
        err = ""
        if new is None:
            err = _tr("不支持的文件类型")
        elif not new.is_valid():
            err = str(new.error() or "")
        if new is None or not new.is_valid():
            self._host.show_message(
                _tr("读取失败，已保留原数据源：{0}").format(err), LEVEL_WARN)
            return False
        if bool(new.is_raster()) != bool(layer.is_raster()):
            self._host.show_message(
                _tr("数据源类型不一致，已取消"),
                LEVEL_WARN)
            return False

        try:
            if layer.is_vector():
                layer.set_data(new.geoms(), new.attrs(), new.fields(),
                               geometry_type=new.geometry_type())
                layer.setCrs(new.crs())
                try:
                    layer.clear_subset()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:491", exc_info=True)
            else:
                if not layer.replace_dataset(new):
                    raise RuntimeError(_tr("接管数据集失败"))
            layer.relink_source(src)
        except Exception as e:
            self._host.show_message(_tr("换数据源失败：{0}").format(e), LEVEL_WARN)
            return False
        self._after_relink(layer, src)
        return True

    def apply_layer_crs(self, layer, target, action):
        from ggis.ui.dialogs.app import LayerPropertiesDialog as LPD

        old = layer.crs()
        old_key = old.authid() if (old is not None and old.is_valid()) else ""
        new_key = target.authid()

        if old_key and old_key == new_key:
            return

        if action == LPD.CRS_SET:
            layer.setCrs(target)
            self._after_layer_crs_changed(layer)
            self._host.show_message(
                _tr("已把「{0}」的坐标系改为 {1}")
                .format(layer.name(), new_key), LEVEL_SUCCESS)
            return

        if not layer.is_vector():
            self._host.show_message(
                _tr("「{0}」是栅格图层，不能重投影")
                .format(layer.name()), LEVEL_WARN)
            return
        if not old_key:
            self._host.show_message(
                _tr("「{0}」的坐标系未定义，无法重投影").format(layer.name()),
                LEVEL_WARN)
            return
        try:
            from ggis.io.vector_io import reproject_geoms
            geoms = reproject_geoms(list(layer.geoms()), old_key, new_key)
            layer.set_data(geoms, list(layer.attrs()), list(layer.fields()))
            layer.setCrs(target)
        except Exception as e:
            self._host.show_message(_tr("重投影失败：{}").format(e), LEVEL_CRITICAL)
            return
        self._after_layer_crs_changed(layer)
        self._host.show_message(
            _tr("已把「{0}」的 {1} 个要素从 {2} 重投影到 {3}"
                "（只改了内存，要保存请用导出）")
            .format(layer.name(), layer.feature_count(), old_key, new_key),
            LEVEL_SUCCESS)

    def _after_layer_crs_changed(self, layer):
        try:
            layer.invalidate_extent()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:561", exc_info=True)
        try:
            from ggis.render.cache import invalidate_caches
            invalidate_caches(layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:566", exc_info=True)
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:570", exc_info=True)

    def _on_layers_changed(self, *_a):
        if getattr(self, "_states_pending", False):
            return
        self._states_pending = True

        def _run():
            self._states_pending = False
            self._host.ctx.svc("actions").refresh_states()

        try:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, _run)
        except Exception:
            exc_note("_on_layers_changed @ ggis/ui/views/map/map_layer.py:576")
            _run()

    def _ask_layer_save_path(self, layer):
        from ggis.common.base.dialog import GgsFileDialog
        kind = str(layer.geometry_type() or "").lower()
        if "point" in kind:
            base = _tr("新建点图层")
        elif "line" in kind:
            base = _tr("新建线图层")
        else:
            base = _tr("新建面图层")
        fmts = [(_tr(f), e) for f, e in self._NEW_FILE_FORMATS]
        want = str(app_settings.get("temp_layer_format") or "GPKG").lower()
        def_ext = vector_suffix_for_driver(want)
        fmts.sort(key=lambda fe: 0 if fe[1] == def_ext else 1)
        filters = ";;".join(f for f, _e in fmts)
        default = os.path.join(self._default_open_dir(), base + def_ext)
        path, chosen = GgsFileDialog.getSaveFileName(
            self, _tr("保存图层 — {0}").format(layer.name()),
            default, filters)
        if not path:
            return ""
        if not os.path.splitext(path)[1]:
            guess = def_ext
            for f, e in fmts:
                if chosen and str(chosen).startswith(f.split(" (")[0]):
                    guess = e
                    break
            path += guess
        return path

    def _on_selection_edit(self):
        pass

    def _on_measured(self, payload):
        text, detail = "", ""
        if isinstance(payload, (tuple, list)):
            if payload:
                text = str(payload[0] or "")
            if len(payload) > 1:
                detail = str(payload[1] or "")
        else:
            text = str(payload or "")
        p = self.measure()
        if p is not None:
            p.set_result(text, detail)
            if text and not p.isVisible():
                self._place_measure_panel()
                p.show()
                self._measure_panel_was_visible = True

    def _default_label_colors(self):
        dark = True
        try:
            dark = bool(self.canvas._is_dark_bg())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:687", exc_info=True)
        if dark:
            return "#FFFFFF", "#000000"
        return "#1B2430", "#FFFFFF"

    def _view_dock(self, obj_name):
        host = getattr(self, "_host", None)
        if host is None:
            return None
        vid = str(getattr(self, "view_id", ""))
        for d in getattr(host, "_view_docks", {}).get(vid, []):
            if d is not None and d.objectName() == obj_name:
                return d
        for n in ("styling_dock", "labeling_dock", "attribute_dock"):
            g = getattr(host, n, None)
            if g is not None and g.objectName() == obj_name:
                return g
        return None

    def open_label_settings(self):
        d = self._view_dock("GgsLabelingDock")
        if d is None:
            try:
                self._host._register_view_map_docks(self)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:735", exc_info=True)
            d = self._view_dock("GgsLabelingDock")
        if d is None:
            return
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先在图层树中选中一个矢量图层"),
                              LEVEL_WARN)
            return
        try:
            from ggis.render.labeling import get_label_style, set_label_style
            cur = get_label_style(lyr)
            if not cur.field:
                col, halo = self._default_label_colors()
                cur.color = col
                cur.halo_color = halo
                try:
                    set_label_style(lyr, cur)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:758", exc_info=True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:760", exc_info=True)
        try:
            if hasattr(d, "set_layer"):
                d.set_layer(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:765", exc_info=True)
        self._host.ctx.region("dock")._show_dock(d)

    def _on_label_changed(self, layer):
        try:
            self.canvas.invalidate_labels(layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:794", exc_info=True)
        try:
            lid = layer.id()
            dock = getattr(self, "layer_dock", None)
            if dock is not None and hasattr(dock, "refresh_legend"):
                dock.refresh_legend(lid)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:801", exc_info=True)
        try:
            self._host.show_message(
                _tr("已更新「{0}」的标注设置").format(layer.name()),
                LEVEL_SUCCESS)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:807", exc_info=True)

    def toggle_labels(self):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先在图层树中选中一个矢量图层"),
                              LEVEL_WARN)
            self._recheck_label_action()
            return
        try:
            from ggis.render.labeling import (get_label_style, set_label_style,
                                           suggest_label_field)
        except Exception:
            exc_note("toggle_labels @ ggis/ui/views/map/map_layer.py:807")
            return
        st = get_label_style(lyr)
        if st.enabled:
            st.enabled = False
            set_label_style(lyr, st)
            self.canvas.invalidate_labels(lyr)
            self._host.show_message(_tr("已关闭「{0}」的标注").format(lyr.name()),
                              LEVEL_INFO)
        else:
            if not st.field:
                st.field = suggest_label_field(lyr)
            if not st.field:
                self._host.show_message(_tr("该图层没有可用的标注字段"), LEVEL_WARN)
                self._recheck_label_action()
                return
            col, halo = self._default_label_colors()
            st.color = col
            st.halo_color = halo
            st.enabled = True
            set_label_style(lyr, st)
            self.canvas.invalidate_labels(lyr)
            self._host.show_message(
                _tr("已开启「{0}」的标注（字段：{1}）").format(
                    lyr.name(), st.field), LEVEL_SUCCESS)
        self._host.ctx.svc("actions").refresh_states()

    def _recheck_label_action(self):
        a = self._host.ctx.svc("actions")._acts.get("toggle_labels")
        if a is not None:
            a.setChecked(False)

    def open_analysis(self, op=None, batch=False):
        from ggis.core.analysis.raster_ops import RASTER_OPS
        if op and str(op) in RASTER_OPS:
            self.open_raster_analysis(op)
            return
        from ggis.ui.dialogs.analysis import GgsAnalysisDialog
        cur = self._current_layer()
        if cur is not None and not cur.is_vector():
            cur = None
        try:
            dark = bool(self.canvas._is_dark_bg())
        except Exception:
            exc_note("open_analysis @ ggis/ui/views/map/map_layer.py:862")
            dark = True
        try:
            dlg = GgsAnalysisDialog(self._host.ctx.project, cur, self,
                                    dark_bg=dark, op=op,
                                    lock_op=bool(op))
            try:
                from ggis.common.styling import icons as _icons
                from ggis.ui.panels.analysis import GROUPS
                _op_icon = {_o: _n for _g, _items in GROUPS
                            for _o, _n in _items}
                _icon_name = (_op_icon.get(op, "processing")
                              if op else "processing")
                dlg.setWindowIcon(_icons.icon(_icon_name, size=16))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:908", exc_info=True)
            dlg.set_runner(self._analysis_runner(dlg))
            dlg.setModal(False)
            dlg.show()
            if getattr(dlg, "_runner", None) is not None:
                return
            params = dlg.params()
            to_file = dlg.write_to_file()
            path = dlg.output_path()
            add_to_map = dlg.add_to_map()
            copts = dlg.creation_options()
        except Exception as e:
            self._host.show_message(_tr("空间分析失败：{0}").format(e), LEVEL_WARN)
            return
        self.run_analysis(params, to_file=to_file, path=path,
                          add_to_map=add_to_map,
                          creation_options=copts)

    def _analysis_runner(self, dlg):
        def _run(params, progress, cancel):
            t = self._run_analysis_async(
                params,
                to_file=dlg.write_to_file(),
                path=dlg.output_path(),
                add_to_map=dlg.add_to_map(),
                creation_options=dlg.creation_options(),
                progress=progress, cancel=cancel,
                token=getattr(dlg, "_task_token", None))
            dlg._task_token = t.token
            return t
        return _run

    def _fill_analysis_fids(self, p):
        if p is None or not p.selected_only:
            return p
        try:
            from ggis.core.model.selection import GgsSelection
            sel = GgsSelection.instance()
            lyr = p.input_layer
            p.fids = set(sel.fids(lyr)) if lyr is not None else set()
        except Exception:
            exc_note("_fill_analysis_fids @ ggis/ui/views/map/map_layer.py:949")
            p.fids = set()
        return p

    def run_analysis(self, params, jobs=None, to_file=False, path="",
                     creation_options=None, add_to_map=True,
                     progress=None, cancel=None, on_done=None):
        from ggis.exec import guard as _g
        if _g.ui_mode() and _g.on_ui_thread():
            return self._run_analysis_async(
                params, jobs=jobs, to_file=to_file, path=path,
                creation_options=creation_options,
                add_to_map=add_to_map,
                progress=progress, cancel=cancel, on_done=on_done)
        return self._run_analysis_sync(
            params, jobs=jobs, to_file=to_file, path=path,
            creation_options=creation_options,
            add_to_map=add_to_map,
            progress=progress, cancel=cancel, on_done=on_done)

    def _run_analysis_async(self, params, jobs=None, to_file=False, path="",
                            creation_options=None, add_to_map=True,
                            progress=None, cancel=None, on_done=None,
                            token=None):
        from ggis.core import analysis as A
        from ggis.exec import jobs as _jobs
        from ggis.exec import task as _et
        from ggis.exec.progress_hub import hub

        jobs = list(jobs or [])
        label = (_tr("批处理") if jobs
                 else (_tr(A.op_label(str(params.op)))
                       if params is not None else _tr("空间分析")))
        for p in (jobs if jobs else [params]):
            self._fill_analysis_fids(p)

        prog = None
        if progress is None and cancel is None:
            prog = self._analysis_progress(label)
            if prog is not None:
                progress = prog.feed
                cancel = prog.cancelled
        if progress is not None:
            def _prog_cb(ev, _p=progress):
                _et.to_ui(_p, ev.get("frac", 0.0), ev.get("text", ""))
        else:
            _prog_cb = None

        t = _et.submit(
            _jobs.run_analysis_job, params, jobs=jobs, to_file=to_file,
            path=path, creation_options=creation_options,
            result_name=_tr("批处理结果"),
            name=label, kind="cpu",
            cancel=cancel, on_progress=_prog_cb, token=token)
        self._track_analysis_task(t)
        hub().attach(t)
        t.on_done(lambda ev: self._on_analysis_done(
            ev, t, params, jobs, to_file, path, creation_options,
            add_to_map, prog, on_done))
        t.on_fail(lambda ev: self._on_analysis_failed(ev, t, prog))
        return t

    def _track_analysis_task(self, t):
        s = getattr(self, "_analysis_tasks", None)
        if s is None:
            s = set()
            self._analysis_tasks = s
        s.add(t)

    def _untrack_analysis_task(self, t):
        s = getattr(self, "_analysis_tasks", None)
        if s is not None:
            s.discard(t)

    def _on_analysis_done(self, ev, task, params, jobs, to_file, path,
                          creation_options, add_to_map, prog,
                          on_done=None):
        lyr = None
        try:
            self._untrack_analysis_task(task)
            if ev.get("cancelled"):
                self._host.show_message(_tr("分析已取消"), LEVEL_INFO)
                return None
            result, br = ev.get("result") or (None, None)
            if br is not None and br.errors:
                self._host.show_message(
                    _tr("批处理有 {0} 个作业失败").format(len(br.errors)),
                    LEVEL_WARN)
                for m in [e[1] for e in br.errors[:3]]:
                    try:
                        self._host.log_dock.append(
                            _tr("批处理作业失败：{0}").format(m))
                    except Exception:
                        logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1142", exc_info=True)
            if result is None:
                if br is not None and not br.results:
                    self._host.show_message(_tr("批处理没有产生任何结果"), LEVEL_WARN)
                return None
            lyr = self._deliver_analysis(
                result, params, to_file, path, creation_options,
                add_to_map=add_to_map, written=bool(to_file and path))
            return lyr
        except Exception as e:
            self._host.show_message(_tr("空间分析失败：{0}").format(e), LEVEL_WARN)
            return None
        finally:
            self._host.ctx.svc("views")._close_progress(prog)
            self._restore_wait_cursor()
            if on_done is not None:
                try:
                    on_done(lyr)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1163", exc_info=True)

    def _on_analysis_failed(self, ev, task, prog):
        self._untrack_analysis_task(task)
        self._host.ctx.svc("views")._close_progress(prog)
        self._restore_wait_cursor()
        self._host.show_message(
            _tr("空间分析失败：{0}").format(ev.get("error")), LEVEL_WARN)
        try:
            self._host.log_dock.append(str(ev.get("traceback") or ev.get("error")))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1174", exc_info=True)

    def _run_analysis_sync(self, params, jobs=None, to_file=False, path="",
                           creation_options=None, add_to_map=True,
                           progress=None, cancel=None, on_done=None):
        from ggis.core import analysis as A
        jobs = list(jobs or [])
        prog = None
        try:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QGuiApplication.processEvents()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1188", exc_info=True)
        try:
            if jobs:
                if progress is None:
                    prog = self._analysis_progress(_tr("批处理"))
                    progress = prog.feed if prog is not None else None
                    cancel = prog.cancelled if prog is not None else None
                for p in jobs:
                    self._fill_analysis_fids(p)
                br = A.run_batch(jobs, progress=progress, cancel=cancel)
                if br.errors:
                    self._host.show_message(
                        _tr("批处理有 {0} 个作业失败").format(len(br.errors)),
                        LEVEL_WARN)
                lost = [e[1] for e in br.errors[:3]]
                for m in lost:
                    try:
                        self._host.log_dock.append(_tr("批处理作业失败：{0}").format(m))
                    except Exception:
                        logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1207", exc_info=True)
                if not br.results:
                    self._host.show_message(_tr("批处理没有产生任何结果"), LEVEL_WARN)
                    return None
                result = br.merged(_tr("批处理结果"),
                                   crs=jobs[0].input_layer.crs()
                                   if jobs[0].input_layer is not None else None)
                result.ms = br.ms
            else:
                if progress is None:
                    prog = self._analysis_progress(
                        _tr(A.op_label(str(params.op)))
                        if params is not None else _tr("空间分析"))
                    progress = prog.feed if prog is not None else None
                    cancel = prog.cancelled if prog is not None else None
                self._fill_analysis_fids(params)
                result = A.run_analysis(params, progress=progress,
                                        cancel=cancel)
            self._host.ctx.svc("views")._close_progress(prog)
            prog = None
            lyr = self._deliver_analysis(result, params, to_file, path,
                                         creation_options,
                                         add_to_map=add_to_map)
            if on_done is not None:
                try:
                    on_done(lyr)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1239", exc_info=True)
            return lyr
        except A.AnalysisCancelled:
            self._host.show_message(_tr("分析已取消"), LEVEL_INFO)
            if on_done is not None:
                try:
                    on_done(None)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1247", exc_info=True)
            return None
        except Exception as e:
            self._host.show_message(_tr("空间分析失败：{0}").format(e), LEVEL_WARN)
            if on_done is not None:
                try:
                    on_done(None)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1255", exc_info=True)
            return None
        finally:
            self._host.ctx.svc("views")._close_progress(prog)
            try:
                from PySide6.QtGui import QGuiApplication
                QGuiApplication.restoreOverrideCursor()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1263", exc_info=True)

    def _analysis_progress(self, title):
        try:
            from ggis.ui.dialogs.analysis import GgsAnalysisProgress
            from PySide6.QtWidgets import QApplication
            d = GgsAnalysisProgress(self, title=str(title or ""))
            d.show()
            QApplication.processEvents()
            return d
        except Exception:
            exc_note("_analysis_progress @ ggis/ui/views/map/map_layer.py:1233")
            return None

    def _deliver_analysis(self, result, params, to_file, path,
                          creation_options=None, add_to_map=True,
                          written=False):
        from ggis.core import analysis as A
        for w in result.warnings:
            self._host.show_message(w, LEVEL_WARN)
        if result.is_empty():
            self._host.show_message(
                _tr("「{0}」没有产生任何要素").format(
                    A.op_label(result.op)), LEVEL_WARN)
            return None
        if to_file and path:
            if not written:
                A.write_result(result, path,
                               driver=(params.output_driver if params else ""),
                               creation_options=creation_options)
            self._host.show_message(
                _tr("已写出分析结果：{0}（{1} 个要素）").format(
                    os.path.basename(path), result.count()), LEVEL_SUCCESS)
            if not add_to_map:
                return None
        name = (params.output_name if params is not None
                else result.name) or ""
        if not name:
            base = A.op_label(result.op).split("（")[0]
            src = result.source or _tr("结果")
            idx = 1
            names = set()
            try:
                names = {l.name() for l in self._host.ctx.project.layers()}
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1316", exc_info=True)
            name = "%s_%s" % (src, base)
            while name in names:
                idx += 1
                name = "%s_%s_%d" % (src, base, idx)
        lyr = result.to_layer(name)
        if add_to_map:
            self.adopt_layer(lyr, select=False, zoom_first=False,
                             check_crs=False, silent=True)
            try:
                self.canvas.refresh()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1328", exc_info=True)
        self._host.show_message(
            _tr("「{0}」完成：{1} 个要素（{2:.0f} ms）").format(
                A.op_label(result.op), result.count(), result.ms),
            LEVEL_SUCCESS)
        return lyr

    def open_raster_analysis(self, op=None):
        from ggis.ui.dialogs.raster_analysis import GgsRasterAnalysisDialog
        from ggis.core.analysis.raster_ops import raster_op_label
        cur = self._current_layer()
        if cur is not None and not cur.is_raster():
            cur = None
        try:
            dark = bool(self.canvas._is_dark_bg())
        except Exception:
            exc_note("open_raster_analysis @ ggis/ui/views/map/map_layer.py:1309")
            dark = True
        try:
            dlg = GgsRasterAnalysisDialog(self._host.ctx.project, cur, self,
                                          dark_bg=dark, op=op,
                                          lock_op=bool(op))
            try:
                from ggis.common.styling import icons as _icons
                _icon_name = str(op) if op else "processing"
                dlg.setWindowIcon(_icons.icon(_icon_name, size=16))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1367", exc_info=True)
            dlg.set_runner(self._raster_runner(dlg))
            dlg.setModal(False)
            dlg.show()
        except Exception as e:
            self._host.show_message(
                _tr("栅格分析失败：{0}").format(e), LEVEL_WARN)
            return

    def _raster_runner(self, dlg):
        def _run(op, params, out_spec, progress, cancel):
            t = self._run_raster_async(
                op, params, out_spec, progress=progress, cancel=cancel,
                add_to_map=dlg.add_to_map(),
                token=getattr(dlg, "_task_token", None))
            dlg._task_token = t.token
            return t
        return _run

    def _run_raster_async(self, op, params, out_spec, progress=None,
                          cancel=None, on_done=None, add_to_map=True,
                          token=None):
        from ggis.core.analysis import raster_ops as R
        from ggis.exec import task as _et
        from ggis.exec.progress_hub import hub

        to_file = bool(out_spec.get("filename"))
        path = out_spec.get("filename") or ""
        driver = out_spec.get("driver") or ""
        creation_options = []
        for _part in str(out_spec.get("options") or "").split(";"):
            _part = _part.strip()
            if _part and "=" in _part:
                creation_options.append(_part)

        label = (_tr(R.raster_op_label(str(op)))
                 if op else _tr("栅格分析"))

        prog = None
        if progress is None and cancel is None:
            prog = self._analysis_progress(label)
            if prog is not None:
                progress = prog.feed
                cancel = prog.cancelled
        if progress is not None:
            def _prog_cb(ev, _p=progress):
                _et.to_ui(_p, ev.get("frac", 0.0), ev.get("text", ""))
        else:
            _prog_cb = None

        t = _et.submit(
            R.run_raster_job, op, params, to_file=to_file, path=path,
            driver=driver, creation_options=creation_options,
            result_name=label, name=label, kind="cpu",
            cancel=cancel, on_progress=_prog_cb, token=token)
        self._track_analysis_task(t)
        hub().attach(t)
        t.on_done(lambda ev: self._on_raster_done(
            ev, t, op, params, out_spec, prog, on_done,
            add_to_map=add_to_map))
        t.on_fail(lambda ev: self._on_raster_failed(ev, t, prog))
        return t

    def _on_raster_done(self, ev, task, op, params, out_spec, prog,
                        on_done=None, add_to_map=True):
        lyr = None
        try:
            self._untrack_analysis_task(task)
            if ev.get("cancelled"):
                self._host.show_message(_tr("栅格分析已取消"), LEVEL_INFO)
                return None
            res = ev.get("result")
            if res is None:
                self._host.show_message(_tr("栅格分析没有产生任何结果"),
                                        LEVEL_WARN)
                return None
            lyr = self._deliver_raster(res, params, out_spec,
                                       add_to_map=add_to_map)
            return lyr
        except Exception as e:
            self._host.show_message(
                _tr("栅格分析失败：{0}").format(e), LEVEL_WARN)
            return None
        finally:
            self._host.ctx.svc("views")._close_progress(prog)
            self._restore_wait_cursor()
            if on_done is not None:
                try:
                    on_done(lyr)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1471", exc_info=True)

    def _on_raster_failed(self, ev, task, prog):
        self._untrack_analysis_task(task)
        self._host.ctx.svc("views")._close_progress(prog)
        self._restore_wait_cursor()
        self._host.show_message(
            _tr("栅格分析失败：{0}").format(ev.get("error")), LEVEL_WARN)
        try:
            self._host.log_dock.append(str(ev.get("traceback") or ev.get("error")))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1482", exc_info=True)

    def _deliver_raster(self, res, params, out_spec, add_to_map=True):
        for w in (getattr(res, "warnings", []) or []):
            self._host.show_message(w, LEVEL_WARN)
        out_path = (str(out_spec.get("filename") or "")
                    if isinstance(out_spec, dict) else "")
        if out_path:
            self._host.show_message(
                _tr("已写出分析结果：{0}").format(os.path.basename(out_path)),
                LEVEL_SUCCESS)
            if not add_to_map:
                return None
        if out_path:
            name = os.path.splitext(os.path.basename(out_path))[0]
        else:
            name = ((params.get("output_name") if isinstance(params, dict)
                     else "") or getattr(res, "name", "") or "")
        if not name:
            name = _tr("栅格结果")
        if res.out_kind == "raster":
            path = res.raster_path
            if not path:
                self._host.show_message(_tr("栅格结果路径缺失"), LEVEL_WARN)
                return None
            try:
                from ggis.io.raster_io import read_raster
                lyr = read_raster(path)
            except Exception as e:
                self._host.show_message(
                    _tr("读回栅格结果失败：{0}").format(e), LEVEL_WARN)
                return None
            if lyr is None or not lyr.is_valid():
                self._host.show_message(_tr("栅格结果图层无效"), LEVEL_WARN)
                return None
            lyr.setName(name)
            if add_to_map:
                self.adopt_layer(lyr, select=False, zoom_first=False,
                                 check_crs=False, silent=True)
                try:
                    self.canvas.refresh()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1535", exc_info=True)
            self._host.show_message(
                _tr("「{0}」完成（{1}）").format(name, _tr("栅格")),
                LEVEL_SUCCESS)
            return lyr
        lyr = res.vector_layer
        if lyr is None or not lyr.is_valid():
            self._host.show_message(_tr("矢量结果图层无效"), LEVEL_WARN)
            return None
        lyr.setName(name)
        if add_to_map:
            self.adopt_layer(lyr, select=False, zoom_first=False,
                             check_crs=False, silent=True)
            try:
                self.canvas.refresh()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1552", exc_info=True)
        self._host.show_message(
            _tr("「{0}」完成：{1} 个要素").format(name, lyr.feature_count()),
            LEVEL_SUCCESS)
        return lyr

    def _selectable_layers(self):
        try:
            return [l for l in self._host.ctx.project.layers()
                    if l.is_vector() and not l.is_table()
                    and l.is_visible() and l.is_valid()]
        except Exception:
            exc_note("_selectable_layers @ ggis/ui/views/map/map_layer.py:1526")
            return []

    def _identify_layers(self, mode=None):
        mode = mode or getattr(self, "_identify_mode", "visible")
        try:
            proj = self._host.ctx.project
            lt = None
            try:
                lt = self.layer_tree()
            except Exception:
                exc_note("_identify_layers @ ggis/ui/views/map/map_layer.py:1550")
                lt = None
            if lt is not None:
                _tree_ids = {str(l.id()) for l in lt.layers()}
                all_ = [l for l in proj.layers()
                        if l.is_valid() and not l.is_table()
                        and (l.is_vector() or l.is_raster() or l.is_tile())
                        and str(l.id()) in _tree_ids]
            else:
                all_ = [l for l in proj.layers()
                        if l.is_valid() and not l.is_table()
                        and (l.is_vector() or l.is_raster() or l.is_tile())]
        except Exception:
            exc_note("_identify_layers @ ggis/ui/views/map/map_layer.py:1566")
            return []
        if mode == "all":
            return all_
        if mode == "top":
            return all_[-1:] if all_ else []
        lt = None
        try:
            lt = self.layer_tree()
        except Exception:
            exc_note("_identify_layers @ ggis/ui/views/map/map_layer.py:1584")
            lt = None
        if lt is not None:
            vis_ids = {str(l.id()) for l in lt.visible_layers()}
            return [l for l in all_ if str(l.id()) in vis_ids]
        return [l for l in all_ if l.is_visible()]

    def _edit_select_layers(self):
        try:
            lyr = self._current_layer()
        except Exception:
            exc_note("_edit_select_layers @ ggis/ui/views/map/map_layer.py:1600")
            return []
        if lyr is None or not lyr.is_vector():
            return []
        return [lyr]

    def _on_selection_requested(self, layer, fids, mode):
        sel = GgsSelection.instance()
        fids = list(fids or [])
        try:
            if mode == "add":
                sel.add_fids(layer, fids)
            elif mode == "subtract":
                sel.remove_fids(layer, fids)
            elif mode == "intersect":
                keep = set(fids)
                sel.set_fids(layer, [f for f in sel.fids(layer)
                                     if f in keep])
            else:
                sel.set_fids(layer, fids)
        except Exception:
            exc_note("_on_selection_requested @ ggis/ui/views/map/map_layer.py:1631")
            return
        self._after_selection_change(layer, fids, mode)

    def _after_selection_change(self, layer, fids, mode):
        n = len(fids)
        verb = {"add": _tr("加选"), "subtract": _tr("减选"),
                "intersect": _tr("交集"), "replace": _tr("选中")}.get(
                    mode, _tr("选中"))
        total = GgsSelection.instance().total()
        if n == 0 and mode == "replace":
            self._host.show_message(_tr("未选中要素（已清空选择）"), LEVEL_INFO)
        else:
            self._host.show_message(_tr("{0} {1} 个要素，当前共选中 {2} 个").format(
                verb, n, total), LEVEL_INFO)
        self._host.ctx.svc("actions").refresh_states()

    def filter_active_layer(self):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先选择一个矢量图层"), LEVEL_WARN)
            return False
        from ggis.ui.views.map.dialogs.filter import GgsFilterDialog
        dlg = GgsFilterDialog(
            lyr, self, apply_cb=lambda: self._after_filter_change(lyr))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        if dlg.cleared():
            lyr.clear_subset()
            self._after_filter_change(lyr)
            self._host.show_message(_tr("已清除「{0}」的过滤").format(lyr.name()),
                              LEVEL_INFO)
            return True
        text = dlg.expression_text()
        fids = dlg.result_fids()
        if fids is None or not text:
            lyr.clear_subset()
            self._after_filter_change(lyr)
            self._host.show_message(_tr("已清除「{0}」的过滤").format(lyr.name()),
                              LEVEL_INFO)
            return True
        lyr.set_subset(fids, text)
        self._after_filter_change(lyr)
        self._host.show_message(
            _tr("已过滤「{0}」：保留 {1} / {2} 个要素").format(
                lyr.name(), len(fids), lyr.feature_count()), LEVEL_INFO)
        return True

    @staticmethod
    def _prune_selection_to_subset(lyr):
        try:
            sub = lyr.subset_fids()
        except Exception:
            exc_note("_prune_selection_to_subset @ ggis/ui/views/map/map_layer.py:1696")
            return 0
        if sub is None:
            return 0
        try:
            sel = GgsSelection.instance()
            drop = set(sel.fids(lyr)) - set(sub)
            if drop:
                sel.remove_fids(lyr, sorted(drop))
            return len(drop)
        except Exception:
            exc_note("_prune_selection_to_subset @ ggis/ui/views/map/map_layer.py:1706")
            return 0

    def _after_filter_change(self, lyr):
        self._prune_selection_to_subset(lyr)
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1760", exc_info=True)
        try:
            docks = getattr(self, "_attr_docks", None)
            if docks:
                d = docks.get(lyr.id())
                if d is not None and hasattr(d, "refresh"):
                    d.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1774", exc_info=True)
        self._host.ctx.svc("actions").refresh_states()

    def open_histogram(self, layer=None, field=None, band=None):
        lyr = layer or self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先在图层树里选一个图层"), LEVEL_WARN)
            return None
        if not lyr.is_valid():
            self._host.show_message(_tr("图层无效或尚未加载完成"), LEVEL_WARN)
            return None
        from ggis.ui.views.map.dialogs.histogram import GgsHistogramDialog
        dlg = GgsHistogramDialog(lyr, self, field=field, band=band)
        dlg.exec()
        return dlg

    def open_raster_display(self, layer=None, focus="display"):
        lyr = layer or self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先在图层树里选一个栅格图层"),
                              LEVEL_WARN)
            return None
        if not lyr.is_raster():
            self._host.show_message(_tr("「{0}」不是栅格图层").format(lyr.name()),
                              LEVEL_WARN)
            return None
        if not lyr.is_valid():
            self._host.show_message(_tr("图层无效或尚未加载完成"), LEVEL_WARN)
            return None
        if str(focus) != "histogram":
            self.open_symbology(lyr)
            return None
        return self.open_histogram(lyr)

    def open_raster_attr_table(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先在图层树里选一个栅格图层"),
                              LEVEL_WARN)
            return None
        if not lyr.is_raster():
            self._host.show_message(_tr("「{0}」不是栅格图层").format(lyr.name()),
                              LEVEL_WARN)
            return None
        if not lyr.is_valid():
            self._host.show_message(_tr("图层无效或尚未加载完成"), LEVEL_WARN)
            return None
        from ggis.ui.views.map.dialogs.raster_table import GgsRasterAttrDock
        docks = getattr(self, "_raster_attr_docks", None)
        if docks is None:
            docks = {}
            self._raster_attr_docks = docks
        lid = lyr.id()
        d = docks.get(lid)
        if d is None:
            d = GgsRasterAttrDock(lyr, self)
            d.closed.connect(
                lambda _lid=lid, _self=self:
                    _self._on_raster_attr_dock_closed(_lid))
            self._host.addDockWidget(
                Qt.DockWidgetArea.BottomDockWidgetArea, d)
            docks[lid] = d
        self._host.ctx.region("dock")._activate_dock(d)
        return d

    def _on_raster_attr_dock_closed(self, lid):
        docks = getattr(self, "_raster_attr_docks", None)
        if docks is not None:
            docks.pop(lid, None)

    def open_raster_profile(self, layer=None, x=None, y=None, modeless=False):
        host = getattr(self, "_host", None)
        if host is not None and hasattr(host, "open_profile_dock"):
            try:
                return host._map_dock_mgr.open_profile_dock(layer=layer, x=x, y=y)
            except Exception:
                exc_note("open_raster_profile @ ggis/ui/views/map/map_layer.py:1844")
                return None
        return None

    def _on_profile_picked(self, cx, cy):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_raster():
            self._host.show_message(_tr("剖面曲线只对栅格图层有效"),
                              LEVEL_WARN)
            return
        try:
            from ggis.core.expr.query import to_layer_point
            x, y = to_layer_point(lyr, float(cx), float(cy), self.canvas)
        except Exception:
            exc_note("_on_profile_picked @ ggis/ui/views/map/map_layer.py:1866")
            x, y = float(cx), float(cy)
        dlg = getattr(self, "_profile_dlg", None)
        same = False
        try:
            same = (dlg is not None and dlg.isVisible()
                    and getattr(dlg, "_layer", None) is lyr)
        except Exception:
            exc_note("_on_profile_picked @ ggis/ui/views/map/map_layer.py:1873")
            same = False
        if same:
            try:
                dlg.set_point(x, y)
                dlg.raise_()
                dlg.activateWindow()
                return
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1906", exc_info=True)
        self.open_raster_profile(lyr, x=x, y=y, modeless=True)

    def _raster_probe_centre(self, layer):
        try:
            from ggis.core.expr.query import to_layer_point
            e = self.canvas.extent()
            cx, cy = e.center()
            return to_layer_point(layer, float(cx), float(cy), self.canvas)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:1917", exc_info=True)
        try:
            e = layer.extent()
            return e.center()
        except Exception:
            exc_note("_raster_probe_centre @ ggis/ui/views/map/map_layer.py:1897")
            return (0.0, 0.0)

    def export_vector_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先选择一个矢量图层"), LEVEL_WARN)
            return False
        if lyr.feature_count() <= 0:
            self._host.show_message(_tr("「{0}」里没有要素，无法导出").format(
                lyr.name()), LEVEL_WARN)
            return False
        from ggis.ui.dialogs.export import GgsExportVectorDialog

        dlg = GgsExportVectorDialog(
            lyr, self, self._export_start_dir(),
            n_selected=len(self._selected_fids_of(lyr) or []))
        p = {}

        def _runner(params, progress=None, cancel=None):
            p.clear()
            p.update(params)
            fid_filter = (self._selected_fids_of(lyr)
                          if params.get("only_selected") else None)
            from ggis.io.vector_io import export_layer
            return export_layer(
                lyr, params["path"], driver=params["driver"],
                fields=params["fields"], fid_filter=fid_filter,
                target_crs=params["target_crs"],
                progress=progress, cancel=cancel)

        def _finisher(ev):
            if ev.get("cancelled"):
                self._host.show_message(_tr("导出已取消"), LEVEL_INFO)
                return
            if ev.get("error"):
                self._host.log(_tr("导出矢量失败：{0}").format(ev["error"]))
                return
            self._on_vector_exported(
                ev.get("result"), lyr, bool(p.get("add_to_map")))

        dlg.set_runner(_runner)
        dlg.set_finisher(_finisher)
        dlg.show()
        return True

    def export_table_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None or not lyr.is_table():
            self._host.show_message(_tr("请先选择一个表格图层"), LEVEL_WARN)
            return False
        if lyr.feature_count() <= 0:
            self._host.show_message(
                _tr("「{0}」里没有数据，无法导出").format(lyr.name()),
                LEVEL_WARN)
            return False
        from ggis.ui.dialogs.export import GgsExportTableDialog

        dlg = GgsExportTableDialog(lyr, self, self._export_start_dir())
        p = {}

        def _runner(params, progress=None, cancel=None):
            p.clear()
            p.update(params)
            from ggis.io.table_io import export_table
            return export_table(
                lyr, params["path"], driver=params["driver"],
                fields=params["fields"])

        def _finisher(ev):
            if ev.get("cancelled"):
                self._host.show_message(_tr("导出已取消"), LEVEL_INFO)
                return
            if ev.get("error"):
                self._host.log(_tr("导出表格失败：{0}").format(ev["error"]))
                return
            self._on_table_exported(ev.get("result"), lyr)

        dlg.set_runner(_runner)
        dlg.set_finisher(_finisher)
        dlg.show()
        return True

    def _on_table_exported(self, out, lyr):
        if not out:
            return False
        self._host.ctx.svc("views")._on_view_method("_remember_dir", out)
        self._host.show_message(_tr("已导出表格 → {0}").format(out),
                          LEVEL_INFO)
        self._host.log(_tr("导出表格：{0} → {1}").format(lyr.name(), out))
        return True

    def table_to_layer_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None or not lyr.is_table():
            self._host.show_message(_tr("请先选择一个表格图层"), LEVEL_WARN)
            return False
        from ggis.ui.dialogs.table_to_layer import GgsTableToLayerDialog
        from ggis.common.base.dialog import GgsDialog
        dlg = GgsTableToLayerDialog(lyr, self, host=self._host)
        dlg.setModal(True)
        if dlg.exec() == GgsDialog.Accepted:
            res = dlg.result_layer
            if res is not None:
                ctx = getattr(self._host, "ctx", None)
                if ctx is None:
                    ctx = getattr(getattr(self._host, "_host", None),
                                  "ctx", None)
                if ctx is not None:
                    ctx.svc("views")._on_view_method("_adopt_layer", res)
                    self._host.show_message(
                        _tr("已生成矢量图层：{0}").format(res.name()),
                        LEVEL_INFO)
        return True

    def export_layer_style(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先选择一个图层"), LEVEL_WARN)
            return False
        try:
            from ggis.render.renderers import get_renderer
            from ggis.render.labeling import get_label_style
        except Exception as e:
            self._host.show_message(_tr("导出样式失败：{0}").format(e), LEVEL_WARN)
            return False
        try:
            style = {"format": "gmagis-layer-style", "version": 1,
                     "name": str(lyr.name() or ""),
                     "renderer": get_renderer(lyr).to_dict(),
                     "label": get_label_style(lyr).to_dict()}
        except Exception as e:
            self._host.show_message(_tr("导出样式失败：{0}").format(e), LEVEL_WARN)
            self._host.log(_tr("导出样式失败：{0}").format(e))
            return False
        start = self._export_start_dir()
        default = ""
        try:
            import os as _os
            default = _os.path.join(
                start or "", "%s.ggisstyle" % (str(lyr.name() or "style")))
        except Exception:
            exc_note("export_layer_style @ ggis/ui/views/map/map_layer.py:1993")
            default = ""
        from PySide6.QtWidgets import QFileDialog
        path, _f = QFileDialog.getSaveFileName(
            self, _tr("导出图层样式"), default,
            _tr("GmaGIS 图层样式 (*.ggisstyle);;JSON (*.json)"),
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return False
        try:
            import json as _json
            with open(path, "w", encoding="utf-8") as f:
                _json.dump(style, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._host.show_message(_tr("导出样式失败：{0}").format(e), LEVEL_WARN)
            return False
        self._remember_dir(path)
        self._host.show_message(_tr("已导出图层样式 → {0}").format(path), LEVEL_INFO)
        self._host.log(_tr("导出样式：{0} → {1}").format(lyr.name(), path))
        return True

    def export_raster_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None or not lyr.is_raster():
            self._host.show_message(_tr("请先选择一个栅格图层"), LEVEL_WARN)
            return False
        if not lyr.is_valid() or lyr.dataset() is None:
            self._host.show_message(_tr("栅格图层没有打开的数据集"), LEVEL_WARN)
            return False
        from ggis.ui.dialogs.export import GgsExportRasterDialog

        dlg = GgsExportRasterDialog(lyr, self, self.canvas,
                                    self._export_start_dir())
        p = {}

        def _runner(params, progress=None, cancel=None):
            p.clear()
            p.update(params)
            from ggis.io.raster_io import write_raster
            return write_raster(
                lyr, params["path"], progress=progress, cancel=cancel,
                driver=params["driver"], extent=params["extent"],
                bands=params["bands"], compression=params["compression"])

        def _finisher(ev):
            if ev.get("cancelled"):
                self._host.show_message(_tr("导出已取消"), LEVEL_INFO)
                return
            if ev.get("error"):
                self._host.log(_tr("导出栅格失败：{0}").format(ev["error"]))
                return
            self._on_raster_exported(
                ev.get("result"), lyr, bool(p.get("add_to_map")))

        dlg.set_runner(_runner)
        dlg.set_finisher(_finisher)
        dlg.show()
        return True

    def export_tile_layer(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None or not lyr.is_tile():
            self._host.show_message(_tr("请先选择一个瓦片图层"), LEVEL_WARN)
            return False
        if not lyr.is_valid() or lyr.tile_source() is None:
            self._host.show_message(_tr("瓦片图层没有有效的数据源"), LEVEL_WARN)
            return False
        from ggis.ui.views.map.dialogs.export_tile import GgsExportTileDialog

        dlg = GgsExportTileDialog(
            lyr, self, self.canvas, self._export_start_dir())
        p = {}

        def _runner(params, progress=None, cancel=None):
            p.clear()
            p.update(params)
            from ggis.io.tile_export import download_tiles_to_raster
            res = download_tiles_to_raster(
                lyr.tile_source(), params["extent"], params["zoom"],
                params["driver"], params["path"],
                progress=progress, cancel=cancel)
            if res is None:
                return None
            out, failed = res
            return out, failed

        def _finisher(ev):
            if ev.get("cancelled"):
                self._host.show_message(_tr("导出已取消"), LEVEL_INFO)
                return
            if ev.get("error"):
                self._host.log(_tr("导出瓦片失败：{0}").format(ev["error"]))
                return
            result = ev.get("result")
            out, failed = (result if isinstance(result, (tuple, list))
                           else (result, 0))
            if failed and failed > 0:
                try:
                    GgsMsgBox.warning(
                        self._host, _tr("瓦片下载不完整"),
                        _tr("本次导出有 {0} 张瓦片下载失败")
                        .format(failed))
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2139", exc_info=True)
            self._on_tile_exported(
                out, lyr, bool(p.get("add_to_map")))

        dlg.set_runner(_runner)
        dlg.set_finisher(_finisher)
        dlg.show()
        return True

    def _on_tile_exported(self, out, lyr, add_to_map=False):
        if not out:
            return False
        self._remember_dir(out)
        self._host.show_message(_tr("已导出瓦片图层 → {0}").format(out),
                          LEVEL_INFO)
        self._host.log(_tr("导出瓦片：{0} → {1}").format(lyr.name(), out))
        if add_to_map:
            self._add_exported_layer_to_project(out)
        return True

    def _on_raster_exported(self, out, lyr, add_to_map=False):
        if not out:
            return False
        self._remember_dir(out)
        self._host.show_message(_tr("已导出栅格图层 → {0}").format(out),
                          LEVEL_INFO)
        self._host.log(_tr("导出栅格：{0} → {1}").format(lyr.name(), out))
        if add_to_map:
            self._add_exported_layer_to_project(out)
        return True

    def export_map_image(self):
        if self.canvas is None:
            return False
        try:
            if self.canvas.extent().is_empty():
                self._host.show_message(_tr("地图还没有内容，先添加数据"),
                                  LEVEL_WARN)
                return False
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2182", exc_info=True)
        from ggis.ui.dialogs.export import GgsExportMapImageDialog
        dlg = GgsExportMapImageDialog(self.canvas, self,
                                      self._export_start_dir())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        p = dlg.params()
        if not p.get("path"):
            self._host.show_message(_tr("请先选择输出图片"), LEVEL_WARN)
            return False
        try:
            img = self.canvas.render_to_image(
                p["width"], p["height"], dpi=p["dpi"],
                with_labels=p["with_labels"],
                with_selection=p["with_selection"])
        except Exception as e:
            self._host.show_message(_tr("渲染失败：{0}").format(e), LEVEL_WARN)
            return False
        fmt = "PNG"
        if str(p["path"]).lower().endswith((".jpg", ".jpeg")):
            fmt = "JPEG"
            from PySide6.QtGui import QImage, QPainter, QColor
            flat = QImage(img.size(), QImage.Format.Format_RGB32)
            flat.fill(QColor("white"))
            pp = QPainter(flat)
            try:
                pp.drawImage(0, 0, img)
            finally:
                pp.end()
            img = flat
        ok = img.save(str(p["path"]), fmt)
        if not ok:
            self._host.show_message(_tr("图片写入失败：{0}").format(p["path"]),
                              LEVEL_WARN)
            return False
        self._remember_dir(p["path"])
        self._host.show_message(_tr("已导出地图图片 → {0}").format(p["path"]),
                          LEVEL_INFO)
        self._host.log(_tr("导出地图图片：{0} × {1} → {2}").format(
            p["width"], p["height"], p["path"]))
        return True

    def _refresh_layer_appearance(self, layer):
        if layer is None:
            return
        try:
            self.canvas.invalidate_symbol(layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2232", exc_info=True)
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2236", exc_info=True)
        try:
            lid = layer.id()
            dock = getattr(self, "layer_dock", None)
            if dock is not None and hasattr(dock, "refresh_legend"):
                dock.refresh_legend(lid)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2244", exc_info=True)
        try:
            _panel = self._view_dock("GgsStylingDock")
            if _panel is not None and hasattr(_panel, "reload_from_layer"):
                _panel.reload_from_layer(layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2257", exc_info=True)

    def _on_legend_action(self, kind, item, payload):
        lyr = self._item_layer(item)
        if lyr is None:
            return
        if kind == "legend_color":
            if isinstance(payload, (tuple, list)):
                idx, col = (payload + (None,))[:2]
            else:
                idx, col = 0, payload
            self._set_legend_item_color(lyr, idx, col)
        elif kind == "ramp":
            self._set_raster_ramp(lyr, payload)
        elif kind == "ramp_invert_set":
            self._set_raster_ramp_invert(lyr, bool(payload))
        elif kind == "raster_mode":
            self._set_raster_mode(lyr, payload)
        elif kind == "raster_swatch_color":
            if isinstance(payload, (tuple, list)):
                row, col = (list(payload) + [None, None])[:2]
            else:
                row, col = 0, payload
            self._set_raster_swatch_color(lyr, row, col)
        elif kind == "raster_rgb_band":
            if isinstance(payload, (tuple, list)) and len(payload) >= 2:
                self._set_raster_rgb_band(lyr, payload[0], payload[1])

    def _set_raster_swatch_color(self, lyr, row, color):
        if lyr is None or color is None:
            return
        try:
            from PySide6.QtGui import QColor
            from ggis.core.style import raster_display as rd
            c = QColor(color)
            if not c.isValid():
                return
            row = int(row)
            hexs = c.name().upper()
            d = rd.get_display(lyr)
            mode = rd.render_mode(d)
            if mode == rd.MODE_CLASSIFY:
                n = rd.class_steps(d) or 0
                if not (0 <= row < n):
                    return
                cols = ["#%02X%02X%02X" % tuple(t)
                        for t in rd.class_color_list(d)]
                cs = list(d.class_colors or [])
                if len(cs) < n:
                    cs = list(cols) + [""] * max(0, n - len(cs))
                cs[row] = hexs
                d.class_colors = cs[:n]
            else:
                keys, _cmap = rd.legend_palette(lyr, d)
                if not (0 <= row < len(keys)):
                    return
                out = dict(d.color_map or {})
                out[str(int(keys[row]))] = hexs
                d.color_map = out
            rd.set_display(lyr, d)
        except Exception:
            exc_note("_set_raster_swatch_color @ ggis/ui/views/map/map_layer.py:2326")
            return
        self._refresh_layer_appearance(lyr)

    def _set_raster_rgb_band(self, lyr, channel, band):
        if lyr is None:
            return
        try:
            from ggis.core.style import raster_display as rd
            i = int(channel)
            if not (0 <= i < 3):
                return
            b = max(1, int(band or 1))
            d = rd.get_display(lyr)
            rb = list(d.rgb_bands or (0, 0, 0))
            while len(rb) < 3:
                rb.append(0)
            for k in range(3):
                try:
                    if int(rb[k] or 0) <= 0:
                        rb[k] = k + 1
                except Exception:
                    exc_note("_set_raster_rgb_band @ ggis/ui/views/map/map_layer.py:2354")
                    rb[k] = k + 1
            rb[i] = b
            d.rgb_bands = tuple(int(v) for v in rb[:3])
            d.band = 0
            rd.set_render_mode(d, rd.MODE_RGB)
            rd.set_display(lyr, d)
        except Exception:
            exc_note("_set_raster_rgb_band @ ggis/ui/views/map/map_layer.py:2362")
            return
        self._refresh_layer_appearance(lyr)

    def _set_legend_item_color(self, lyr, index, color):
        if lyr is None or color is None:
            return
        try:
            from ggis.render.renderers import get_renderer, _bump_render_version
            r = get_renderer(lyr)
            syms = list(r.legend_symbols())
        except Exception:
            exc_note("_set_legend_item_color @ ggis/ui/views/map/map_layer.py:2382")
            return
        try:
            i = int(index)
        except Exception:
            exc_note("_set_legend_item_color @ ggis/ui/views/map/map_layer.py:2386")
            return
        if not (0 <= i < len(syms)):
            return
        sym = syms[i]
        try:
            from PySide6.QtGui import QColor
            c = QColor(color)
        except Exception:
            exc_note("_set_legend_item_color @ ggis/ui/views/map/map_layer.py:2394")
            return
        if not c.isValid():
            return
        try:
            kind = str(lyr.base_kind() or "")
        except Exception:
            exc_note("_set_legend_item_color @ ggis/ui/views/map/map_layer.py:2400")
            kind = ""
        try:
            if kind == "line":
                sym.stroke = c
            else:
                sym.fill = c
        except Exception:
            exc_note("_set_legend_item_color @ ggis/ui/views/map/map_layer.py:2407")
            return
        try:
            _bump_render_version(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2440", exc_info=True)
        self._refresh_layer_appearance(lyr)

    def _set_raster_ramp(self, lyr, code):
        try:
            from ggis.core.style import raster_display as rd
            d = rd.get_display(lyr)
            d.ramp = str(code or rd.RAMP_NONE)
            rd.set_display(lyr, d)
        except Exception:
            exc_note("_set_raster_ramp @ ggis/ui/views/map/map_layer.py:2422")
            return
        self._refresh_layer_appearance(lyr)

    def _set_raster_ramp_invert(self, lyr, on):
        try:
            from ggis.core.style import raster_display as rd
            d = rd.get_display(lyr)
            d.invert_ramp = bool(on)
            rd.set_display(lyr, d)
        except Exception:
            exc_note("_set_raster_ramp_invert @ ggis/ui/views/map/map_layer.py:2437")
            return
        self._refresh_layer_appearance(lyr)

    def _set_raster_mode(self, lyr, mode):
        try:
            from ggis.core.style import raster_display as rd
            d = rd.get_display(lyr)
            rd.set_render_mode(d, mode, ramp=d.ramp)
            rd.set_display(lyr, d)
        except Exception:
            exc_note("_set_raster_mode @ ggis/ui/views/map/map_layer.py:2453")
            return
        self._refresh_layer_appearance(lyr)

    def open_symbology(self, layer=None):
        d = self._view_dock("GgsStylingDock")
        if d is None:
            try:
                self._host._register_view_map_docks(self)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2496", exc_info=True)
            d = self._view_dock("GgsStylingDock")
        if d is None:
            return
        layer = layer or self._current_layer()
        try:
            if layer is not None and hasattr(d, "set_layer"):
                d.set_layer(layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2505", exc_info=True)
        self._host.ctx.region("dock")._show_dock(d)
        try:
            self._host.ctx.svc("actions").get("symbol_editor").setChecked(True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2510", exc_info=True)

    def open_attribute_table(self, layer=None, as_dock=True):
        layer = layer or self._current_layer()
        if layer is None or not layer.is_vector():
            self._host.show_message(_tr("请先选择一个矢量图层"), LEVEL_WARN)
            return None
        if as_dock:
            from ggis.ui.dialogs.attribute_table import _ATTR_PER_LAYER
            if _ATTR_PER_LAYER:
                docks = getattr(self, "_attr_docks", None)
                if docks is None:
                    docks = {}
                    self._attr_docks = docks
                lid = layer.id()
                d = docks.get(lid)
                if d is None:
                    from ggis.ui.dialogs.attribute_table import GgsLayerAttributeDock
                    d = GgsLayerAttributeDock(layer, self.canvas,
                                             self._host, self)
                    d.zoomToFeature.connect(
                        lambda *a, _h=self._host:
                            _h._forward_to_map_view("_zoom_to_feature", *a))
                    d.closed.connect(
                        lambda _lid=lid, _self=self:
                            _self._on_attr_dock_closed(_lid))
                    self._host.addDockWidget(
                        Qt.DockWidgetArea.BottomDockWidgetArea, d)
                    docks[lid] = d
                self._host.ctx.region("dock")._activate_dock(d)
                return d
            ad = self._view_dock("GgsAttributeTableDock")
            if ad is None:
                try:
                    self._host._register_view_map_docks(self)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2565", exc_info=True)
                ad = self._view_dock("GgsAttributeTableDock")
            if ad is not None and hasattr(ad, "show_layer"):
                ad.show_layer(layer, self.canvas)
                if not getattr(self, "_docks_attached", False):
                    try:
                        self._docks_attached = True
                        self._host.ctx.region("dock")._reattach_view_docks()
                    except Exception:
                        logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2574", exc_info=True)
                self._host.ctx.region("dock")._activate_dock(ad)
                return ad
        from ggis.ui.dialogs.attribute_table import GgsAttributeTableDialog
        dlg = GgsAttributeTableDialog.open_for(layer, self, self.canvas)
        if dlg is not None:
            try:
                dlg.zoomToFeature.connect(self._zoom_to_feature)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2587", exc_info=True)
        return dlg

    def _on_attr_dock_closed(self, lid):
        docks = getattr(self, "_attr_docks", None)
        if not docks:
            return
        d = docks.pop(lid, None)
        if d is not None:
            if getattr(self._host, "_active_dock", None) is d:
                self._host._active_dock = None
            try:
                d.deleteLater()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2604", exc_info=True)

    def show_selected_attributes(self):
        sel = GgsSelection.instance()
        pairs = sel.summary()
        if not pairs:
            self._host.show_message(_tr("没有选中要素"), LEVEL_INFO)
            return
        layers = sel.selected_layers()
        if len(layers) == 1:
            dlg = self.open_attribute_table(layers[0])
            w = dlg
            try:
                if dlg is not None and not hasattr(w, "chk_sel") \
                        and hasattr(dlg, "content"):
                    w = dlg.content()
            except Exception:
                exc_note("show_selected_attributes @ ggis/ui/views/map/map_layer.py:2598")
                w = dlg
            try:
                w.chk_sel.setChecked(True)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2634", exc_info=True)
            return
        lines = [_tr("当前选择：")]
        for name, cnt in pairs:
            lines.append("  %s：%d" % (name, cnt))
        self._host.show_message("　".join(lines), LEVEL_INFO)

    def remove_current_layer(self):
        lyr = self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先选择一个图层"), LEVEL_WARN)
            return False
        if not self._confirm_drop_unsaved_layer(lyr, _tr("移除图层")):
            return False
        proj = self._host.ctx.project
        lid = str(lyr.id())
        if proj.layer_by_id(lid) is None:
            return False
        name = lyr.name()
        try:
            idx = proj.layers().index(lyr)
        except ValueError:
            exc_note("remove_current_layer @ ggis/ui/views/map/map_layer.py:2633")
            idx = None
        vis = bool(lyr.is_visible())
        dock = getattr(self, "layer_dock", None)
        _dbg = logging.getLogger("gmagis")

        def _refresh():
            try:
                self.canvas.refresh()
            except Exception:
                _dbg.debug("remove_current_layer canvas.refresh failed",
                           exc_info=True)

        def _do():
            proj.remove_layer(lyr, close=False)
            _refresh()

        def _undo():
            restore = getattr(dock, "restore_removed_layer", None)
            if callable(restore):
                restore(lyr, idx, vis)
            elif proj.layer_by_id(lid) is None:
                proj.add_layer(lyr, idx)
                proj.set_layer_visible(lyr, vis)
            _refresh()

        push = getattr(proj, "push_layer_command", None)
        if callable(push):
            try:
                push(_tr("移除图层"), _do, _undo)
            except Exception:
                _dbg.exception("silent exception in remove_current_layer")
                _do()
        else:
            _do()
        self._host.show_message(_tr("已移除：{0}").format(name), LEVEL_INFO)
        return True

    def _picked_tree_items(self):
        view = getattr(getattr(self, "layer_dock", None), "view", None)
        if view is None:
            return []
        try:
            return list(view.picked_items(view.currentItem()))
        except Exception:
            exc_note("_picked_tree_items @ ggis/ui/views/map/map_layer.py:2680")
            return []

    def copy_layer_to_clipboard(self):
        items = self._picked_tree_items()
        if not items:
            lyr = self._current_layer()
            if lyr is None:
                self._host.show_message(_tr("请先选择一个图层"), LEVEL_WARN)
                return False
            try:
                from ggis.io.project_io import layer_to_dict
                ggs_set_layer_clip([{"kind": "layer",
                                     "snap": layer_to_dict(lyr)}])
            except Exception as e:
                self._host.show_message(_tr("复制失败：{0}").format(e), LEVEL_WARN)
                return False
            self._after_clip_changed(
                _tr("已复制图层到剪贴板：{0}").format(lyr.name()))
            return True
        entries = [e for e in (self._snapshot_tree_item(it) for it in items)
                   if e]
        if not entries:
            self._host.show_message(_tr("这些条目不包含可复制的图层"), LEVEL_WARN)
            return False
        ggs_set_layer_clip(entries)
        if len(entries) == 1 and entries[0].get("kind") == "layer":
            self._after_clip_changed(_tr("已复制图层到剪贴板：{0}").format(
                (entries[0].get("snap") or {}).get("name")
                or _tr("未命名图层")))
        else:
            self._after_clip_changed(
                _tr("已复制 {0} 项到剪贴板").format(len(entries)))
        return True

    def cut_layer_to_clipboard(self):
        if not self.copy_layer_to_clipboard():
            return False
        for it in self._picked_tree_items():
            lyr = self._item_layer(it)
            if lyr is None:
                continue
            if not self._confirm_drop_unsaved_layer(lyr, _tr("剪切图层")):
                self._host.show_message(_tr("已取消剪切"), LEVEL_WARN)
                return False
        n = 0
        for it in self._picked_tree_items():
            n += self._cut_tree_item(it)
        self._host.show_message(
            _tr("已剪切 {0} 个图层").format(n) if n
            else _tr("已剪切（按 Ctrl+V 可恢复）"), LEVEL_INFO)
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2741", exc_info=True)
        return True

    def paste_layer_from_clipboard(self, parent_item=None):
        entries = self._clip_entries()
        if not entries:
            self._host.show_message(_tr("剪贴板里没有图层"), LEVEL_WARN)
            return False
        n = self._paste_entries(entries, parent_item)
        if not n:
            return False
        self._host.show_message(_tr("已粘贴 {0} 个图层").format(n), LEVEL_INFO)
        return True

    def copy_layer_path(self):
        lyr = self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先选择一个图层"), LEVEL_WARN)
            return False
        src = str(lyr.source() or "")
        if not src:
            self._host.show_message(
                _tr("「{0}」没有路径可复制").format(lyr.name()),
                LEVEL_WARN)
            return False
        try:
            QApplication.clipboard().setText(src)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2775", exc_info=True)
        self._host.show_message(_tr("已复制路径：{0}").format(src), LEVEL_INFO)
        return True

    def _sync_measure_panel(self, tool_name):
        p = self.measure()
        if p is None:
            return
        kinds = {"measure_len": "length", "measure_area": "area",
                 "measure_angle": "angle"}
        kind = kinds.get(str(tool_name or ""))
        if kind is None:
            self._measure_panel_was_visible = False
            p.hide()
            return
        p.set_kind(kind)
        a = self._host.ctx.svc("actions")._acts.get("measure_" + ("len" if kind == "length" else kind))
        if a is None:
            a = self._host.ctx.svc("actions")._acts.get(str(tool_name))
        live = True
        try:
            live = bool(a.isChecked()) if a is not None else True
        except Exception:
            exc_note("_sync_measure_panel @ ggis/ui/views/map/map_layer.py:2813")
            live = True
        if live:
            self._place_measure_panel()
            p.show()
            self._measure_panel_was_visible = True
        else:
            self._measure_panel_was_visible = False
            p.hide()

    @staticmethod
    def _kind_label(kind):
        return {"point": _tr("点"), "line": _tr("线"),
                "polygon": _tr("面"), "poly": _tr("面")}.get(
                    str(kind), _tr("点"))

    def _unique_layer_name(self, base):
        base = str(base or "").strip() or _tr("新建图层")
        proj = self._host.ctx.project
        try:
            taken = {str(l.name()) for l in proj.layers()}
        except Exception:
            exc_note("_unique_layer_name @ ggis/ui/views/map/map_layer.py:2838")
            return base
        if base not in taken:
            return base
        i = 2
        while "%s (%d)" % (base, i) in taken:
            i += 1
        return "%s (%d)" % (base, i)

    def _select_layer_in_tree(self, layer):
        if layer is None:
            return False
        try:
            view = self.layer_dock.view
        except Exception:
            exc_note("_select_layer_in_tree @ ggis/ui/views/map/map_layer.py:2853")
            return False
        from ggis.ui.panels.layertree import ROLE_KIND, ROLE_LAYER_ID

        def _walk(item):
            if item is None:
                return None
            if (item.data(0, ROLE_KIND) == "layer"
                    and item.data(0, ROLE_LAYER_ID) == layer.id()):
                return item
            for i in range(item.childCount()):
                hit = _walk(item.child(i))
                if hit is not None:
                    return hit
            return None

        try:
            for i in range(view.topLevelItemCount()):
                hit = _walk(view.topLevelItem(i))
                if hit is not None:
                    view.setCurrentItem(hit)
                    return True
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2868", exc_info=True)
        return False

    def _default_layer_crs(self):
        try:
            pc = self._host.current_view_crs()
            if pc and pc.is_valid():
                return pc
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2884", exc_info=True)
        try:
            for l in self._host.ctx.project.layers():
                c = l.crs()
                if c and c.is_valid():
                    return c
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:2891", exc_info=True)
        from ggis.core.crs import GgsCoordinateReferenceSystem as GgsCrs
        return GgsCrs.from_epsg(4326)

    def new_graphic_layer(self, kind="point"):
        from ggis.core.model.layer import GgsVectorLayer
        ogr = self._kind_to_ogr(kind)
        name = self._unique_layer_name(
            _tr("新建{0}图层").format(self._kind_label(kind)))
        lyr = GgsVectorLayer(name, "", self._default_layer_crs(), ogr,
                             [], [], [])
        lyr._valid = True
        self._activate_new_layer(lyr)
        self._host.show_message(
            _tr("已新建 {0} 图层")
            .format(self._kind_label(kind)), LEVEL_INFO)
        return lyr

    def add_graphic_layer(self):
        from ggis.ui.views.map.dialogs.new_layer import GgsNewLayerDialog
        dlg = GgsNewLayerDialog(self, title="添加图形图层", show_name=False,
                                crs=self._host.ctx.region("title")._default_new_crs())
        dlg.set_hint("图形图层建在内存里，随工程一起保存，无需单独存文件。")
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.new_graphic_layer(dlg.kind())

    def add_text_layer(self):
        from ggis.common.base.dialog import GgsFileDialog
        path, _ = GgsFileDialog.getOpenFileName(
            self, _tr("添加文本数据 (CSV)"), self._default_open_dir(),
            _tr("分隔文本 (*.csv *.tsv *.txt);;所有文件 (*)"))
        if not path:
            return None
        self._remember_dir(path)
        return self._import_text(path)

    def _adopt_table_layer(self, lyr):
        if lyr is None:
            return None
        if not lyr.is_valid():
            self._host.show_message(
                _tr("导入失败：{0}").format(lyr.error()), LEVEL_WARN)
            return None
        return self._adopt_layer(
            lyr, note=lyr.error(),
            what=_tr("已导入 {0} 个点").format(lyr.feature_count()))

    def add_db_layer(self):
        from ggis.common.base.dialog import GgsInputDialog
        text, ok = GgsInputDialog.getMultiLineText(
            self, _tr("数据库 / Web 服务"),
            _tr("连接串或服务地址："),
            "")
        if not ok or not text or not str(text).strip():
            return None
        return self._load_paths([str(text).strip()])

    def add_uri_layer(self, path, activate=True):
        return self._add_data_path(path, is_user=True, activate=activate)

    def add_uri_layer_from_db(self, path, layer_name, activate=True):
        return self._add_data_path(path, is_user=True, layer=layer_name,
                                   activate=activate)

    def add_tile_layer(self, source=None):
        from ggis.core.model.layer import GgsTileLayer
        if source is None:
            from ggis.ui.views.map.dialogs.tile import GgsTileLayerDialog
            dlg = GgsTileLayerDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return None
            source = dlg.source()
        if source is None or not source.is_valid():
            self._host.show_message(_tr("在线瓦片地址无效：{0}").format(
                getattr(source, "url", "")), LEVEL_WARN)
            return None

        dup = self._tile_layer_with_source(source)
        if dup is not None:
            _lt0 = self.layer_tree()
            _had = bool(_lt0 is not None and list(_lt0.layers()))
            self._add_layer_to_current_view_tree(dup)
            _mv = self._host._current_map_view()
            _tree = getattr(_mv, "_layer_tree", None) if _mv is not None else None
            if _tree is not None:
                try:
                    _tree.set_visible(dup.id(), True)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3007", exc_info=True)
            try:
                self.layer_dock.sync_check_states()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3011", exc_info=True)
            if not _had:
                try:
                    self.canvas.zoomToLayer(dup)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3016", exc_info=True)
            self._host.show_message(
                _tr("底图已在工程中：{0}").format(dup.name()), LEVEL_INFO)
            return dup

        name = _tr(source.title) if source.title else \
            (source.name or source.key)
        lyr = GgsTileLayer(name=name, source_obj=source)
        if not lyr.is_valid():
            self._host.show_message(_tr("在线瓦片地址无效：{0}").format(
                source.url), LEVEL_WARN)
            return None
        self.adopt_layer(lyr, select=True, zoom_first=True,
                         check_crs=True, silent=True)
        if not self.canvas.tile_renderable(lyr):
            try:
                crs = self.canvas.effectiveCrs()
                auth = crs.authid() if crs else "?"
                self._host.show_message(
                    _tr("在线瓦片「{0}」在当前坐标系 {1} 下无法显示"
                        "（投影失败），已保留图层。").format(lyr.name(), auth),
                    LEVEL_WARN)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3085", exc_info=True)
            return lyr
        msg = _tr("已加载在线底图：{0}").format(lyr.name())
        if source.attribution:
            msg = "%s　·　%s" % (msg, source.attribution)
        self._host.show_message(msg, LEVEL_INFO)
        return lyr

    def _tile_layer_with_source(self, source):
        try:
            layers = list(self._host.ctx.project.layers())
        except Exception:
            exc_note("_tile_layer_with_source @ ggis/ui/views/map/map_layer.py:3098")
            return None
        for lyr in layers:
            try:
                if not lyr.is_tile():
                    continue
                other = lyr.tile_source()
                if other is not None and other.url == source.url:
                    return lyr
            except Exception:
                exc_note("_tile_layer_with_source @ ggis/ui/views/map/map_layer.py:3107")
                continue
        return None

    def clear_tile_cache(self, disk=True):
        from ggis.render.tiles import clear_tile_cache as _clear
        _clear(disk=bool(disk))
        try:
            self.canvas.update()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3117", exc_info=True)

    def _ask_multi_layers(self, path):
        s = str(path or "")
        sfx = os.path.splitext(s)[1].lower()
        is_conn = ("://" in s) or s.upper().startswith("PG:")
        if not is_conn and sfx not in self._MULTI_LAYER_SUFFIXES:
            return None
        try:
            from ggis.io.vector_io import list_vector_layers
            layers = list_vector_layers(s) or []
        except Exception:
            exc_note("_ask_multi_layers @ ggis/ui/views/map/map_layer.py:3137")
            return None
        if len(layers) <= 1:
            return None
        from ggis.ui.views.map.dialogs.layer_pick import GgsLayerPickDialog
        try:
            dlg = GgsLayerPickDialog(layers, s, self)
        except Exception as e:
            exc_note("_ask_multi_layers @ ggis/ui/views/map/map_layer.py:3144")
            self._host.log("[错误] 打开图层选择对话框失败：{}".format(e))
            return None
        if not dlg.exec():
            return ([], None)
        return (list(dlg.picked_names() or []), dlg.group_name())

    def has_layers(self):
        try:
            v = self._host._current_map_view()
            lt = getattr(v, "_layer_tree", None)
            if lt is not None:
                return bool(list(lt.entries()))
        except Exception:
            logging.getLogger("gmagis").warning(
                "swallowed has_layers @ map_layer.py", exc_info=True)
        return self._host.ctx.project.count() > 0

    def _refresh_layer_tree(self):
        proj = self._host.ctx.project
        vh = getattr(self, "view_host", None)
        for v in (vh.views() if vh is not None else []):
            if str(getattr(v, "kind", "")) != "map":
                continue
            tree = getattr(v, "_layer_tree", None)
            if tree is not None:
                try:
                    tree.init_from_project()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3169", exc_info=True)
            d = getattr(v, "layer_dock", None)
            if d is not None and tree is not None:
                try:
                    d.bind_tree(tree)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3178", exc_info=True)
            elif d is not None:
                try:
                    d.sync_check_states()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3183", exc_info=True)
        w = self._host.ctx.svc("views")._model_workspace()
        if w is not None and hasattr(w, "reload_layers"):
            try:
                w.reload_layers()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3193", exc_info=True)


    @property
    def _layers_changed_handler(self):
        h = self.__dict__.get("_layers_changed_handler_obj")
        if h is None:
            h = self._on_layers_changed
            self.__dict__["_layers_changed_handler_obj"] = h
        return h

    @property
    def _layer_removed_handler(self):
        h = self.__dict__.get("_layer_removed_handler_obj")
        if h is None:
            h = self._on_project_layer_removed
            self.__dict__["_layer_removed_handler_obj"] = h
        return h

    @property
    def _selection_edit_handler(self):
        h = self.__dict__.get("_selection_edit_handler_obj")
        if h is None:
            h = self._on_selection_edit
            self.__dict__["_selection_edit_handler_obj"] = h
        return h

    def dispose_map_signals(self):
        refs = list(self.__dict__.get("_view_sig_refs") or [])
        for sig, handler in refs:
            try:
                sig.disconnect(handler)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3251", exc_info=True)
        self.__dict__["_view_sig_refs"] = []

    def _build_map_tools(self):
        _cv = self.canvas
        _tools = self._tools
        try:
            from ggis.tools.maptools import (GgsMapToolAddCoord, GgsMapToolIdentify,
                                          GgsMapToolProfile, GgsMapToolSelect,
                                          GgsMapToolSpectral)
        except Exception:
            exc_note("_build_map_tools @ ggis/ui/views/map/map_layer.py:3272")
            return
        try:
            ti = GgsMapToolIdentify(_cv, self._identify_layers,
                                    self)
            ti.identified.connect(self._on_identified)
            _tools["identify"] = ti
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            tp = GgsMapToolProfile(_cv, self)
            _tools["raster_profile"] = tp
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            tsp = GgsMapToolSpectral(_cv, self)
            _tools["spectral"] = tsp
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建光谱取点工具失败" % self.view_id)
        try:
            tca = GgsMapToolAddCoord(_cv, self)
            _tools["coord_add"] = tca
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建坐标取点工具失败" % self.view_id)
        try:
            for _key, _shape in (("select", "rect"),
                                 ("select_poly", "polygon"),
                                 ("select_lasso", "lasso"),
                                 ("select_circle", "circle"),
                                 ("select_line", "line")):
                _ts = GgsMapToolSelect(_cv, self._selectable_layers,
                                       self, shape=_shape)
                _ts.selectionRequested.connect(self._on_selection_requested)
                _tools[_key] = _ts
            for _key, _shape in (("edit_select", "rect"),
                                 ("edit_select_poly", "polygon"),
                                 ("edit_select_lasso", "lasso"),
                                 ("edit_select_circle", "circle"),
                                 ("edit_select_line", "line")):
                _es = GgsMapToolSelect(_cv, self._edit_select_layers,
                                       self, shape=_shape)
                _es.selectionRequested.connect(self._on_selection_requested)
                _tools[_key] = _es
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            from ggis.tools.edittools import (GgsMapToolAddFeature,
                                           GgsMapToolDeleteFeature,
                                           GgsMapToolMoveFeature,
                                           GgsMapToolVertexEdit)
            sel = GgsSelection.instance()
            for key, cls in (("add_feature", GgsMapToolAddFeature),
                             ("move_feature", GgsMapToolMoveFeature),
                             ("delete_feature", GgsMapToolDeleteFeature),
                             ("vertex_edit", GgsMapToolVertexEdit)):
                try:
                    t = cls(_cv, layer_provider=self._current_layer,
                            selection=sel, snapper=self.snapper(),
                            parent=self)
                    t.finished.connect(self._on_edit_tool_finished)
                    _dc = getattr(t, "draftCommitted", None)
                    if _dc is not None:
                        _dc.connect(self._on_draft_committed)
                    _dch = getattr(t, "draftChanged", None)
                    if _dch is not None:
                        _dch.connect(self._on_draft_changed)
                    _tools[key] = t
                except Exception:
                    import logging as _lg
                    _lg.getLogger("gmagis").exception(
                        "地图视图 %s：建地图工具失败" % self.view_id)
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            from ggis.tools.measuretools import GgsMapToolMeasure
            for key, kind in (("measure_len", "length"),
                              ("measure_area", "area"),
                              ("measure_angle", "angle")):
                try:
                    t = GgsMapToolMeasure(_cv, kind=kind,
                                          parent=self)
                    t.measured.connect(self._on_measured)
                    _tools[key] = t
                except Exception:
                    import logging as _lg
                    _lg.getLogger("gmagis").exception(
                        "地图视图 %s：建地图工具失败" % self.view_id)
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            _h = self._host
            if not getattr(_h, "_ggs_sel_states_hooked", False):
                GgsSelection.any_changed_signal().connect(
                    _h.ctx.svc("actions").refresh_states)
                _h._ggs_sel_states_hooked = True
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            _sig = GgsSelection.any_changed_signal()
            _hh = self._selection_edit_handler
            _sig.connect(_hh)
            self.__dict__.setdefault("_view_sig_refs", []).append((_sig, _hh))
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)
        try:
            proj = self._host.ctx.project
            _lh = self._layers_changed_handler
            for sig_name in ("layerAdded", "layerRemoved", "layersChanged"):
                sig = getattr(proj, sig_name, None)
                if sig is not None:
                    sig.connect(_lh)
                    self.__dict__.setdefault("_view_sig_refs", []).append(
                        (sig, _lh))
            _rm = getattr(proj, "layerRemoved", None)
            if _rm is not None:
                _rh = self._layer_removed_handler
                _rm.connect(_rh)
                self.__dict__.setdefault("_view_sig_refs", []).append(
                    (_rm, _rh))
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").exception(
                "地图视图 %s：建地图工具失败" % self.view_id)


    def _on_project_layer_removed(self, lid):
        from ggis.ui.dialogs.attribute_table import _ATTR_PER_LAYER
        if _ATTR_PER_LAYER:
            docks = getattr(self, "_attr_docks", None)
            if not docks:
                return
            d = docks.pop(lid, None)
            if d is not None:
                try:
                    d.close()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3493", exc_info=True)
                try:
                    d.deleteLater()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3497", exc_info=True)
            return
        try:
            ad = getattr(self, "attribute_dock", None)
        except Exception:
            exc_note("_on_project_layer_removed @ ggis/ui/views/map/map_layer.py:3501")
            ad = None
        if ad is None:
            return
        try:
            ad.close_layer_tab(lid)
        except Exception:
            import logging as _lg
            _lg.getLogger("gmagis").debug(
                "地图视图 %s：关属性表页签失败（lid=%s）" % (self.view_id, lid))

    def _after_relink(self, layer, src):
        try:
            from ggis.core.model.selection import GgsSelection
            GgsSelection.instance().clear(layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3524", exc_info=True)
        try:
            self._host.ctx.svc("views")._on_view_method("_refresh_layer_appearance", layer)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3528", exc_info=True)
        try:
            self._host.ctx.svc("views")._on_view_method("_refresh_layer_tree")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3532", exc_info=True)
        try:
            from ggis.ui.dialogs.attribute_table import _ATTR_PER_LAYER
            if _ATTR_PER_LAYER:
                docks = getattr(self, "_attr_docks", None)
                d = docks.get(layer.id()) if docks else None
                if d is not None:
                    d.reload(getattr(self, "canvas", None))
            else:
                ad = self._view_dock("GgsAttributeTableDock")
                if ad is not None and getattr(ad, "has_layer",
                                              lambda _l: False)(layer):
                    ad.show_layer(layer, getattr(self, "canvas", None),
                                  reload=True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3551", exc_info=True)
        try:
            self._host.ctx.project.set_dirty(True)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3555", exc_info=True)
        self._host.show_message(_tr("已重新读取数据源：{0}").format(src), LEVEL_INFO)
        try:
            self._host.log(_tr("数据源已更换：{0} → {1}").format(layer.name(), src))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3560", exc_info=True)
        return True

    def _on_identified(self, hits):
        _mgr = getattr(self._host, "_map_dock_mgr", None)
        d = getattr(_mgr, "identify_dock", None) if _mgr is not None else None
        if d is None:
            return
        try:
            _pt = None
            _ti = (self._tools or {}).get("identify")
            if _ti is not None:
                _pt = _ti.last_point()
            d.set_results(hits, _pt)
            self._host.ctx.region("dock")._show_dock(d)
        except Exception:
            exc_note("_on_identified @ ggis/ui/views/map/map_layer.py:3585")
            return
        n = len(hits or [])
        if n:
            names = []
            for h in hits:
                nm = h.layer_name()
                if nm not in names:
                    names.append(nm)
            self._host.show_message(_tr("识别到 {0} 个要素（{1}）").format(
                n, "、".join(names)), LEVEL_INFO)
        else:
            self._host.show_message(_tr("此处没有要素"), LEVEL_INFO)

    def _on_vector_exported(self, out, lyr, add_to_map=False):
        if not out:
            return False
        self._host.ctx.svc("views")._on_view_method("_remember_dir", out)
        self._host.show_message(_tr("已导出矢量图层 → {0}").format(out),
                          LEVEL_INFO)
        self._host.log(_tr("导出矢量：{0} → {1}").format(lyr.name(), out))
        if add_to_map:
            self._add_exported_layer_to_project(out)
        return True

    def _add_exported_layer_to_project(self, path):
        try:
            from ggis.io.registry import load_file
            layer = load_file(path)
            if layer is None:
                self._host.show_message(
                    _tr("已导出，但无法读回加入地图：{0}").format(path),
                    LEVEL_WARN)
                return
            self.adopt_layer(layer, select=False, zoom_first=False,
                             check_crs=False, silent=True)
            try:
                self.canvas.refresh()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3633", exc_info=True)
            self._host.show_message(
                _tr("已加入地图：{0}").format(layer.name()), LEVEL_SUCCESS)
        except Exception as e:
            self._host.log(_tr("导出后加入地图失败：{0}").format(e))
            self._host.show_message(
                _tr("已导出，但加入地图失败：{0}").format(e), LEVEL_WARN)

    def _clip_entries(self):
        return ggs_layer_clip()

    def _snapshot_tree_item(self, item):
        from ggis.ui.panels.layertree import ROLE_KIND
        if item is None:
            return None
        try:
            kind = item.data(0, ROLE_KIND)
        except Exception:
            exc_note("_snapshot_tree_item @ ggis/ui/views/map/map_layer.py:3668")
            return None
        if kind == "layer":
            lyr = self._host.ctx.svc("views")._on_view_method("_item_layer", item)
            if lyr is None:
                return None
            try:
                from ggis.io.project_io import layer_to_dict
                return {"kind": "layer", "snap": layer_to_dict(lyr)}
            except Exception:
                exc_note("_snapshot_tree_item @ ggis/ui/views/map/map_layer.py:3677")
                return None
        if kind == "group":
            kids = []
            for i in range(item.childCount()):
                e = self._snapshot_tree_item(item.child(i))
                if e:
                    kids.append(e)
            return {"kind": "group",
                    "name": str(item.text(0) or ""),
                    "children": kids}
        return None

    def _after_clip_changed(self, msg):
        try:
            self._host.show_message(msg, LEVEL_INFO)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3696", exc_info=True)
        try:
            self._host.ctx.svc("actions").refresh_states()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3700", exc_info=True)

    def _cut_tree_item(self, item):
        from ggis.ui.panels.layertree import ROLE_KIND
        if item is None:
            return 0
        try:
            kind = item.data(0, ROLE_KIND)
        except Exception:
            exc_note("_cut_tree_item @ ggis/ui/views/map/map_layer.py:3713")
            return 0
        if kind == "group":
            n = 0
            for i in range(item.childCount()):
                n += self._cut_tree_item(item.child(i))
            from ggis.ui.panels.layertree import ROLE_GROUP_ID
            try:
                dock = getattr(self, "layer_dock", None)
                tree = getattr(dock, "_tree", None) if dock is not None else None
                gid = str(item.data(0, ROLE_GROUP_ID) or "")
                if tree is not None and gid:
                    tree.remove_group(gid)
            except Exception:
                exc_note("_cut_tree_item @ ggis/ui/views/map/map_layer.py:3793")
            return n
        lyr = self._host.ctx.svc("views")._on_view_method("_item_layer", item)
        if lyr is None:
            return 0
        try:
            self._host.ctx.project.remove_layer(lyr)
        except Exception:
            exc_note("_cut_tree_item @ ggis/ui/views/map/map_layer.py:3734")
            return 0
        return 1

    def _paste_entries(self, entries, parent_item=None):
        n = 0
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            if e.get("kind") == "group":
                g = None
                try:
                    g = self.layer_dock.add_group(
                        str(e.get("name") or _tr("组")), parent=parent_item)
                except Exception:
                    exc_note("_paste_entries @ ggis/ui/views/map/map_layer.py:3749")
                    g = None
                n += self._paste_entries(e.get("children") or [],
                                         g or parent_item)
                continue
            if self._paste_one(e.get("snap") or {}, parent_item):
                n += 1
        return n

    @staticmethod
    def _kind_to_ogr(kind):
        return {"point": "Point", "line": "LineString",
                "polygon": "Polygon", "poly": "Polygon",
                "multi_point": "MultiPoint",
                "multi_line": "MultiLineString",
                "multi_polygon": "MultiPolygon"}.get(str(kind), "Point")

    def _check_crs_mismatch(self, new_layer, proj):
        try:
            no_view_crs = not self.has_explicit_crs()
        except Exception:
            exc_note("_check_crs_mismatch @ ggis/ui/views/map/map_layer.py:3803")
            no_view_crs = False
        try:
            lyr_crs = new_layer.crs()
        except Exception:
            exc_note("_check_crs_mismatch @ ggis/ui/views/map/map_layer.py:3807")
            lyr_crs = None
        if no_view_crs and lyr_crs is not None and lyr_crs.is_valid():
            if self.set_crs(lyr_crs):
                _dn = lyr_crs.display_name()
                self._host.show_message(
                    _tr("视图坐标系已设为 {0}").format(
                        _dn or _tr("自定义坐标系"),
                        new_layer.name()),
                    LEVEL_INFO)
                return

        if not self.has_explicit_crs():
            try:
                host = getattr(self, "_host", None)
                if host is not None and hasattr(host, "_update_crs_label"):
                    host._update_crs_label()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3834", exc_info=True)

        proj_crs = self.crs()
        if not proj_crs or not proj_crs.is_valid():
            return
        if not new_layer.crs() or not new_layer.crs().is_valid():
            self._host.show_message(
                _tr("{0}：未声明 CRS").format(
                    new_layer.name()),
                LEVEL_INFO)
            return
        if new_layer.crs().authid() != proj_crs.authid():
            self._host.show_message(
                _tr("CRS 不一致：{0} 是 {1}，视图是 {2}").format(
                    new_layer.name(), new_layer.crs().authid(),
                    proj_crs.authid()),
                LEVEL_INFO)


    def _paste_one(self, snap, parent_item=None):
        src = str(snap.get("source") or "")
        if not src:
            self._host.show_message(
                _tr("「{0}」无法粘贴")
                .format(snap.get("name") or _tr("未命名图层")), LEVEL_WARN)
            return False
        from ggis.io.project_io import layer_from_snapshot
        try:
            lyr = layer_from_snapshot(snap)
        except Exception as e:
            self._host.show_message(
                _tr("粘贴失败：{0}").format(e), LEVEL_WARN)
            return False
        if lyr is None:
            self._host.show_message(
                _tr("粘贴失败：数据源不可用（{0}）").format(src), LEVEL_WARN)
            return False
        try:
            lyr.setName(self._unique_layer_name(lyr.name()))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3880", exc_info=True)
        if parent_item is not None:
            try:
                self.layer_dock.set_pending_drop([src], parent_item, 0)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_layer.py:3890", exc_info=True)
        return self._host.ctx.svc("views")._on_view_method("_adopt_layer", lyr) is not None


