# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
from ggis.ui.views._hostdeps import (_tr, LEVEL_INFO, LEVEL_WARN,
                        GgsSelection, QDialog)


def _geom_size(geom):
    if geom is None:
        return 0.0
    try:
        gt = str(getattr(geom, "geom_type", ""))
        if "Polygon" in gt:
            return float(geom.area)
        if "Line" in gt:
            return float(geom.length)
        return 0.0
    except Exception:
        exc_note("_geom_size @ ggis/ui/views/map/map_commands.py:38")
        return 0.0


class MapCommandsMixin:







    def feature_clip_count(self):
        return len(getattr(self._host, "_feature_clip", None) or [])


    def _take_selected_features(self, lyr, fids):
        out = []
        try:
            geoms = lyr.geoms()
            attrs = lyr.attrs()
        except Exception:
            exc_note("_take_selected_features @ ggis/ui/views/map/map_commands.py:78")
            return out
        for f in sorted(int(x) for x in (fids or ())):
            try:
                g = geoms[f]
            except Exception:
                exc_note("_take_selected_features @ ggis/ui/views/map/map_commands.py:83")
                continue
            if g is None:
                continue
            a = {}
            try:
                if 0 <= f < len(attrs) and attrs[f]:
                    a = dict(attrs[f])
            except Exception:
                exc_note("_take_selected_features @ ggis/ui/views/map/map_commands.py:91")
                a = {}
            out.append((g, a))
        return out


    def copy_selected_features(self, cut=False):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先在图层树中选中一个矢量图层"), LEVEL_WARN)
            return 0
        try:
            fids = set(GgsSelection.instance().fids(lyr))
        except Exception:
            exc_note("copy_selected_features @ ggis/ui/views/map/map_commands.py:111")
            fids = set()
        if not fids:
            self._host.show_message(
                _tr("请先选中要{0}的要素").format(
                    _tr("剪切") if cut else _tr("复制")), LEVEL_WARN)
            return 0
        if cut and not self._confirm_before_drop_dirty_edits(
                lyr, _tr("剪切要素")):
            return 0
        items = self._take_selected_features(lyr, fids)
        if not items:
            self._host.show_message(_tr("选中的要素读不出几何"), LEVEL_WARN)
            return 0
        s = None
        if cut:
            s = self._session_for(lyr)
            if s is None:
                self._host.show_message(_tr("剪切要素需要先在图层上开始编辑"),
                                  LEVEL_WARN)
                return 0
            if not s.is_active():
                try:
                    s.start()
                except Exception:
                    exc_note("copy_selected_features @ ggis/ui/views/map/map_commands.py:139")
                    return 0
        try:
            crs = lyr.crs()
        except Exception:
            exc_note("copy_selected_features @ ggis/ui/views/map/map_commands.py:143")
            crs = None
        self._host._feature_clip = [{"geom": g, "attrs": a, "crs": crs,
                               "layer": lyr.name()}
                              for g, a in items]
        n = len(self._host._feature_clip)
        if cut:
            try:
                s.delete_features(sorted(int(f) for f in fids))
            except Exception as e:
                self._host.show_message(_tr("剪切失败：{0}").format(e), LEVEL_WARN)
                return 0
            try:
                GgsSelection.instance().clear(lyr)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_commands.py:169", exc_info=True)
        self._host.show_message(
            _tr("已{0} {1} 个要素到剪贴板").format(
                _tr("剪切") if cut else _tr("复制"), n), LEVEL_INFO)
        self._host.ctx.svc("actions").refresh_states()
        return n


    def paste_features_special(self):
        clip = list(getattr(self._host, "_feature_clip", None) or [])
        if not clip:
            self._host.show_message(_tr("剪贴板里没有要素"), LEVEL_WARN)
            return 0
        try:
            layers = list(self._project().layers())
        except Exception:
            exc_note("paste_features_special @ ggis/ui/views/map/map_commands.py:199")
            layers = []
        from ggis.ui.views.map.dialogs.paste_target import (GgsPasteTargetDialog, build_rows,
                                           clip_summary)
        rows = build_rows(layers, clip)
        dlg = GgsPasteTargetDialog(rows, clip_summary(clip), self)
        if not dlg.exec():
            return 0
        lyr = dlg.picked()
        if lyr is None:
            return 0
        return self.paste_features_to_layer(lyr)



    def undo_edit(self):
        s = self.active_session()
        if s is None or not s.undo_stack().canUndo():
            self._host.show_message(_tr("没有可撤销的编辑"), LEVEL_INFO)
            return
        s.undo_stack().undo()
        self._target_session_refresh()


    def redo_edit(self):
        s = self.active_session()
        if s is None or not s.undo_stack().canRedo():
            self._host.show_message(_tr("没有可重做的编辑"), LEVEL_INFO)
            return
        s.undo_stack().redo()
        self._target_session_refresh()


    def _selected_fids(self, layer=None):
        lyr = layer or self._current_layer()
        if lyr is None:
            return lyr, []
        try:
            fids = [int(f) for f in GgsSelection.instance().fids(lyr)]
        except Exception:
            exc_note("_selected_fids @ ggis/ui/views/map/map_commands.py:243")
            fids = []
        return lyr, fids


    def merge_selected(self):
        lyr, fids = self._selected_fids()
        if lyr is None or len(fids) < 2:
            self._host.show_message(_tr("请先选中至少两个要素"), LEVEL_WARN)
            return
        from shapely.ops import unary_union
        s = self._session_for(lyr)
        try:
            merged = unary_union([lyr.geoms()[f] for f in fids])
        except Exception as e:
            self._host.show_message(_tr("融合失败：{0}").format(e), LEVEL_WARN)
            return
        keeper = max(fids, key=lambda f: _geom_size(lyr.geoms()[f]))
        s.set_geometry(keeper, merged)
        s.delete_features([f for f in fids if f != keeper])
        GgsSelection.instance().set_fids(lyr, [keeper])
        self._host.show_message(_tr("已融合 {0} 个要素").format(len(fids)),
                          LEVEL_INFO)


    def combine_selected(self):
        lyr, fids = self._selected_fids()
        if lyr is None or len(fids) < 2:
            self._host.show_message(_tr("请先选中至少两个要素"), LEVEL_WARN)
            return
        from shapely.geometry import (MultiLineString, MultiPoint,
                                      MultiPolygon)
        gt = str(lyr.geometry_type() or "")
        kinds = {"Point": MultiPoint, "LineString": MultiLineString,
                 "Polygon": MultiPolygon}
        cls = kinds.get(gt)
        if cls is None:
            for k, v in kinds.items():
                if k in gt:
                    cls = v
                    break
        s = self._session_for(lyr)
        try:
            merged = cls([lyr.geoms()[f] for f in fids])
        except Exception as e:
            self._host.show_message(_tr("合并失败：{0}").format(e), LEVEL_WARN)
            return
        keeper = max(fids, key=lambda f: _geom_size(lyr.geoms()[f]))
        s.set_geometry(keeper, merged)
        s.delete_features([f for f in fids if f != keeper])
        GgsSelection.instance().set_fids(lyr, [keeper])
        self._host.show_message(_tr("已合并为多部件要素"), LEVEL_INFO)


    def split_multipart_selected(self):
        lyr, fids = self._selected_fids()
        if lyr is None or not fids:
            self._host.show_message(_tr("请先选中要拆分的要素"), LEVEL_WARN)
            return
        s = self._session_for(lyr)
        n = 0
        for fid in fids:
            g = lyr.geoms()[fid]
            parts = list(getattr(g, "geoms", []) or [])
            if len(parts) < 2:
                continue
            s.set_geometry(fid, parts[-1])
            for p in parts[:-1]:
                s.add_feature(p, dict(lyr.attrs()[fid] or {}))
                n += 1
        if n:
            self._host.show_message(_tr("已拆出 {0} 个部件").format(n), LEVEL_INFO)
        else:
            self._host.show_message(_tr("所选要素不是多部件"), LEVEL_WARN)




    def simplify_selected(self):
        lyr, fids = self._selected_fids()
        if lyr is None or not fids:
            self._host.show_message(_tr("请先选中要概化的要素"), LEVEL_WARN)
            return
        from PySide6.QtWidgets import QInputDialog
        s = self._session_for(lyr)
        try:
            tol = float(lyr.extent().width()) / 500.0
        except Exception:
            exc_note("simplify_selected @ ggis/ui/views/map/map_commands.py:335")
            tol = 1.0
        val, ok = QInputDialog.getDouble(
            self, _tr("概化"), _tr("容差（地图单位）"), tol, 0.0, 1e12, 6)
        if not ok:
            return
        done = 0
        s.begin_batch()
        try:
            for fid in fids:
                g = lyr.geoms()[fid]
                try:
                    simplified = g.simplify(float(val), preserve_topology=True)
                except Exception:
                    exc_note("simplify_selected @ ggis/ui/views/map/map_commands.py:352")
                    continue
                if simplified is not None and not simplified.is_empty:
                    s.set_geometry(fid, simplified)
                    done += 1
        finally:
            s.end_batch()
        self._host.show_message(_tr("已概化 {0} 个要素").format(done), LEVEL_INFO)


    def delete_selected_features(self):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            return 0
        try:
            fids = [int(f) for f in GgsSelection.instance().fids(lyr)]
        except Exception:
            exc_note("delete_selected_features @ ggis/ui/views/map/map_commands.py:379")
            fids = []
        if not fids:
            return 0
        s = self._session_for(lyr)
        if s is None:
            return 0
        if not self._confirm_before_drop_dirty_edits(lyr, _tr("删除要素")):
            return 0
        try:
            fids = [int(f) for f in GgsSelection.instance().fids(lyr)]
        except Exception:
            exc_note("delete_selected_features @ ggis/ui/views/map/map_commands.py:395")
            fids = []
        if not fids:
            return 0
        s = self._session_for(lyr)
        if s is None:
            return 0
        try:
            n = s.delete_features(fids)
        except Exception:
            exc_note("delete_selected_features @ ggis/ui/views/map/map_commands.py:404")
            n = 0
        try:
            GgsSelection.instance().clear(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_commands.py:414", exc_info=True)
        try:
            self._host.show_message(_tr("已删除 {0} 个要素").format(n), LEVEL_INFO)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_commands.py:418", exc_info=True)
        return n


    def select_invert(self):
        lyr = self._current_layer()
        if lyr is None:
            self._host.show_message(_tr("请先在图层树里选一个图层"), LEVEL_WARN)
            return
        GgsSelection.instance().invert(lyr)
        self._host.ctx.svc("actions").refresh_states()


    def select_clear(self):
        GgsSelection.instance().clear()
        self._host.show_message(_tr("已清除全部选择"), LEVEL_INFO)
        self._host.ctx.svc("actions").refresh_states()


    def select_by_expression(self):
        proj = self._project()
        vectors = [l for l in proj.layers() if l.is_vector()]
        if not vectors:
            self._host.show_message(_tr("没有可用的矢量图层"), LEVEL_WARN)
            return
        cur = self._current_layer()
        if cur is None or not cur.is_vector():
            self._host.show_message(_tr("请先选择一个矢量图层"), LEVEL_WARN)
            return
        from ggis.ui.views.map.dialogs.select_by_expression import GgsSelectByExpressionDialog
        dlg = GgsSelectByExpressionDialog(
            cur, self, apply_cb=lambda: self.canvas.refresh_selection())
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        fids = dlg.result_fids()
        GgsSelection.instance().set_fids(cur, fids if fids is not None else [])
        self.canvas.refresh_selection()
        self._host.show_message(
            _tr("按表达式选中 {0} 个要素").format(len(fids) if fids else 0),
            LEVEL_INFO)
        self._host.ctx.svc("actions").refresh_states()


    def select_by_location(self):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先选择一个矢量图层"), LEVEL_WARN)
            return False
        from ggis.ui.views.map.dialogs.select_bylocation import GgsSelectByLocationDialog
        dlg = GgsSelectByLocationDialog(lyr, self._project(), self.canvas,
                                        self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        n = dlg.apply_to_selection()
        try:
            self.canvas.refresh_selection()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_commands.py:485", exc_info=True)
        self._host.show_message(_tr("按位置选中：当前共 {0} 个要素").format(n),
                          LEVEL_INFO)
        self._host.log(_tr("按位置选择：{0} → 共 {1} 个").format(
            lyr.name(), n))
        self._host.ctx.svc("actions").refresh_states()
        return True


    def _pick_edit_select(self, name):
        self.set_map_tool(name)
        a_sel = self._host.ctx.svc("actions")._acts.get(name)
        try:
            if (a_sel is not None and a_sel.isCheckable()
                    and not a_sel.isChecked()):
                return
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_commands.py:524", exc_info=True)
        a = self._host.ctx.svc("actions")._acts.get("move_feature")
        if a is not None and a.isCheckable():
            a.setChecked(True)
