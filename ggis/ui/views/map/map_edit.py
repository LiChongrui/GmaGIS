# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note




import logging
from ggis.ui.views._hostdeps import (
    _tr, LEVEL_INFO, LEVEL_WARN, GgsSelection, GgsMsgBox,
    app_settings,
)

_INTERACTIVE_TOOL_NAMES = frozenset({
    "identify", "select", "select_rect", "select_poly", "select_lasso",
    "select_circle", "select_line", "raster_profile", "measure_len",
    "measure_area", "measure_angle", "add_feature", "move_feature",
    "vertex_edit", "edit_select",
})


def _shared_acts(view):
    host = getattr(view, "_host", None)
    ctx = getattr(host, "ctx", None)
    if ctx is None:
        return {}
    try:
        return ctx.svc("actions")._acts
    except Exception:
        exc_note("_shared_acts @ ggis/ui/views/map/map_edit.py:65")
        return {}


class MapEditMixin:

    def _auto_finish_vertex_edit(self):
        try:
            a = self._host.ctx.svc("actions")._acts.get("vertex_edit")
            if a is None or not a.isChecked():
                return
            lyr = self._current_layer()
            if lyr is not None and lyr.is_vector() \
                    and GgsSelection.instance().fids(lyr):
                return
        except Exception:
            exc_note("_auto_finish_vertex_edit @ ggis/ui/views/map/map_edit.py:107")
            return
        try:
            t = self._vertex_tool()
            if t is not None:
                try:
                    t.cancel_edit()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:115", exc_info=True)
            self.set_map_tool("edit_select")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:119", exc_info=True)
        try:
            self._host.ctx.svc("actions").refresh_states()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:123", exc_info=True)

    def _init_editing(self):
        pass

    def _on_snap_act(self, name):
        if getattr(self, "_snap_syncing", False):
            return
        self._snap_syncing = True
        try:
            acts = _shared_acts(self)
            a = acts.get(name)
            if a is not None and a.isChecked():
                for n in self.SNAP_KIND_ACTS:
                    if n == name:
                        continue
                    b = acts.get(n)
                    if b is not None and b.isChecked():
                        b.setChecked(False)
        finally:
            self._snap_syncing = False
        self._apply_snapping()

    def _snap_kinds_from_actions(self):
        acts = _shared_acts(self)
        out = set()
        for n, k in (("snap_endpoint", "endpoint"),
                     ("snap_vertex", "vertex"),
                     ("snap_intersection", "intersection"),
                     ("snap_midpoint", "midpoint"),
                     ("snap_edge", "edge")):
            a = acts.get(n)
            if a is not None and a.isChecked():
                out.add(k)
        return out

    def _effective_snap_kinds(self):
        return self._snap_kinds_from_actions()

    def snapper(self):
        _mv = self
        _cur = getattr(_mv, "_snapper", None) if _mv is not None else None
        if _cur is None:
            from ggis.core.model.snapping import GgsSnapper
            try:
                _tol = float(app_settings.get("snap_tolerance_px", 8) or 8)
            except Exception:
                exc_note("snapper @ ggis/ui/views/map/map_edit.py:208")
                _tol = 8.0
            sn = GgsSnapper(tolerance_px=_tol)
            sn.kinds = self._effective_snap_kinds()
            _mv = self
            if _mv is not None:
                _mv._snapper = sn
                return sn
            return None
        return _cur

    def _sync_snapper_layers(self):
        sn = self.snapper()
        try:
            layers = [l for l in self._host.ctx.project.layers()
                      if l.is_vector() and l.is_valid()]
        except Exception:
            exc_note("_sync_snapper_layers @ ggis/ui/views/map/map_edit.py:232")
            layers = []
        keep = set()
        for l in layers:
            lid = str(l.id())
            keep.add(lid)
            sn.register_layer(l)
            sn.invalidate(l)
        for lid in list(getattr(sn, "_layers", {}).keys()):
            if lid not in keep:
                sn._layers.pop(lid, None)

    def _apply_snapping(self):
        if getattr(self, "_snap_syncing", False):
            return
        self._snap_syncing = True
        try:
            kinds = self._effective_snap_kinds()
            is_on = bool(kinds)
            a_on = self._host.ctx.svc("actions")._acts.get("snap_enable")
            if a_on is not None and a_on.isChecked() != is_on:
                a_on.setChecked(is_on)
            for t in getattr(self, "_tools", {}).values():
                if hasattr(t, "snap_enabled"):
                    t.snap_enabled = is_on
                    t.snap_kinds = set(kinds)
            sn = getattr(self, "_snapper", None)
            if sn is not None:
                sn.kinds = set(kinds)
            try:
                self._host.ctx.svc("actions").refresh_states()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:294", exc_info=True)
        finally:
            self._snap_syncing = False

    def _session_for(self, layer):
        if layer is None or not layer.is_vector():
            return None
        key = str(layer.id())
        _mv = self
        _sess_tbl = _mv.sessions() if _mv is not None else {}
        s = _sess_tbl.get(key)
        if s is None or str(getattr(s.layer(), "id", lambda: None)()) != key:
            from ggis.core.model.editsession import EditSession
            s = EditSession(layer, snapper=self.snapper(), parent=self)
            s.changed.connect(
                lambda _lyr=layer: self._on_edit_changed(_lyr))
            s.structureChanged.connect(self._on_edit_structure_changed)
            s.dirtyChanged.connect(
                lambda _d, k=key: self._on_edit_dirty_changed(k))
            try:
                _st = s.undo_stack()
                for _sig in ("canUndoChanged", "canRedoChanged",
                             "indexChanged"):
                    _s = getattr(_st, _sig, None)
                    if _s is not None:
                        _s.connect(lambda *_: self._host.ctx.svc("actions").refresh_states())
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:330", exc_info=True)
            _sess_tbl[key] = s
        return s

    def active_session(self):
        return self._session_for(self._current_layer())

    def _active_editing(self):
        try:
            lyr = self._current_layer()
            if lyr is None or not lyr.is_vector():
                return False
            sessions = getattr(self, "_edit_sessions", {}) or {}
            s = sessions.get(str(lyr.id()))
            return bool(s is not None and s.is_active())
        except Exception:
            exc_note("_active_editing @ ggis/ui/views/map/map_edit.py:350")
            return False

    def sessions(self):
        return [s for s in getattr(self, "_edit_sessions", {}).values()]

    def _dirty_sessions(self):
        return [s for s in self.sessions().values() if s.is_dirty()]

    def has_dirty_edits(self):
        return bool(self._dirty_sessions())

    def paste_features_to_layer(self, lyr=None):
        _host = getattr(self, "_host", None)
        clip = list(getattr(_host, "_feature_clip", None) or [])
        if not clip:
            self._host.show_message(_tr("剪贴板里没有要素"), LEVEL_WARN)
            return 0
        if lyr is None:
            lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(_tr("请先选中要粘贴到的矢量图层"), LEVEL_WARN)
            return 0
        s = self._session_for(lyr)
        if s is None:
            return 0
        if not s.is_active():
            try:
                s.start()
            except Exception:
                exc_note("paste_features_to_layer @ ggis/ui/views/map/map_edit.py:402")
                return 0
        from ggis.core.analysis import transform_geometry
        try:
            dst_crs = lyr.crs()
        except Exception:
            exc_note("paste_features_to_layer @ ggis/ui/views/map/map_edit.py:407")
            dst_crs = None
        try:
            names = {str(_f[0]) for _f in (lyr.fields() or ())}
        except Exception:
            exc_note("paste_features_to_layer @ ggis/ui/views/map/map_edit.py:411")
            names = set()
        n = 0
        s.begin_batch()
        try:
            for it in clip:
                g = it.get("geom")
                if g is None:
                    continue
                src_crs = it.get("crs")
                if src_crs is not None and dst_crs is not None:
                    try:
                        g = transform_geometry(g, src_crs, dst_crs)
                    except Exception:
                        logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:427", exc_info=True)
                a = dict(it.get("attrs") or {})
                if names:
                    a = {k: v for k, v in a.items() if k in names}
                try:
                    s.add_feature(g, a)
                    n += 1
                except Exception:
                    exc_note("paste_features_to_layer @ ggis/ui/views/map/map_edit.py:432")
                    continue
        finally:
            s.end_batch()
        if n:
            try:
                self.canvas.invalidate_edit(lyr)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:443", exc_info=True)
        self._host.show_message(
            _tr("已粘贴 {0} 个要素到「{1}」").format(n, lyr.name()),
            LEVEL_INFO if n else LEVEL_WARN)
        self._host.ctx.svc("actions").refresh_states()
        return n

    def discard_edits(self):
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            return False
        s = self._session_for(lyr)
        if s is None or not s.is_active():
            return False
        tool = self.canvas.mapTool()
        if tool is not None and hasattr(tool, "cancel_edit"):
            try:
                tool.cancel_edit()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:478", exc_info=True)
        if not s.is_dirty():
            return True
        try:
            s.rollback()
        except Exception as e:
            self._host.show_message(_tr("放弃失败：{0}").format(e), LEVEL_WARN)
            return False
        self._host.show_message(_tr("已放弃「{0}」的全部改动").format(
            lyr.name()), LEVEL_INFO)
        return True

    def _commit_session(self, session):
        lyr = session.layer()
        if int(lyr.feature_count() or 0) <= 0:
            self._host.show_message(
                _tr("{0}：图层里还没有要素，未保存").format(lyr.name()),
                LEVEL_INFO)
            return None
        path = str(lyr.source() or "")
        if not path:
            try:
                session.accept_in_memory()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:520", exc_info=True)
            self._host.show_message(
                _tr("「{0}」的编辑已应用").format(
                    lyr.name()), LEVEL_INFO)
            return ""
        out = session.commit(path or None)
        if out is not None and hasattr(out, "on_done"):
            return out
        if out and str(out) != str(lyr.source() or ""):
            try:
                lyr.relink_source(str(out))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:537", exc_info=True)
        return out

    def save_edits(self):
        dirty = self._dirty_sessions()
        if not dirty:
            self._host.show_message(_tr("没有需要保存的编辑"), LEVEL_INFO)
            return
        state = {"pending": 0, "ok": 0, "mem": [], "fail": []}

        def _report():
            from ggis.ui.dialogs import busy as _busy
            try:
                _busy.hide_busy()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:563", exc_info=True)
            if state["fail"]:
                self._host.show_message(
                    _tr("保存失败：{0}").format("；".join(state["fail"])),
                    LEVEL_WARN)
            elif state["ok"]:
                text = _tr("已保存 {0} 个图层的编辑").format(state["ok"])
                if state["mem"]:
                    text += "　" + _tr("（另有 {0} 个内存图层未写盘）").format(
                        len(state["mem"]))
                self._host.show_message(text, LEVEL_INFO)
            elif state["mem"]:
                self._host.show_message(
                    _tr("编辑已收下，但未写盘：{0}").format(
                            "、".join(state["mem"])), LEVEL_INFO)
            self._after_edit_saved()

        def _tick(*_a):
            state["pending"] -= 1
            if state["pending"] <= 0:
                _report()

        def _done(ev, _n):
            if (ev or {}).get("cancelled"):
                state["ok"] = max(0, state["ok"] - 1)
                state["fail"].append("%s: %s" % (_n, _tr("写入被取消")))
                self._host.log(_tr("保存被取消：{0}").format(_n))
            else:
                self._host.log(_tr("已保存编辑：{0} → {1}").format(
                    _n, (ev or {}).get("result") or ""))
            _tick()

        for s in dirty:
            name = s.layer().name()
            try:
                r = self._commit_session(s)
            except Exception as e:
                exc_note("save_edits @ ggis/ui/views/map/map_edit.py:602")
                state["fail"].append("%s: %s" % (name, e))
                continue
            if r is None:
                continue
            if hasattr(r, "on_done"):
                state["pending"] += 1
                state["ok"] += 1
                self._host.log(_tr("正在保存编辑：{0}").format(name))
                r.on_done(lambda ev, _n=name: _done(ev, _n))
                r.on_fail(lambda ev, _n=name: (
                    state["fail"].append(
                        "%s: %s" % (_n, (ev or {}).get("error") or _tr("写入失败"))),
                    state.__setitem__("ok", max(0, state["ok"] - 1)),
                    _tick()))
                continue
            if not r:
                state["mem"].append(name)
                self._host.log(_tr("已收下编辑：{0}").format(name))
                continue
            state["ok"] += 1
            self._host.log(_tr("已保存编辑：{0} → {1}").format(name, r))
        if state["pending"] > 0:
            from ggis.ui.dialogs import busy as _busy
            _busy.show_busy_delayed(self, _tr("保存编辑"), _tr("正在写盘…"))
            return
        _report()

    def _selected_fids_of(self, layer):
        try:
            return [int(f) for f in GgsSelection.instance().fids(layer)]
        except Exception:
            exc_note("_selected_fids_of @ ggis/ui/views/map/map_edit.py:634")
            return []

    def _set_geom_op_checked(self, kind, on):
        for name, key in self._GEOM_OP_ACTS:
            a = self._host.ctx.svc("actions")._acts.get(name)
            if a is None or not a.isCheckable():
                continue
            want = bool(on and key == kind)
            if a.isChecked() != want:
                a.blockSignals(True)
                a.setChecked(want)
                a.blockSignals(False)

    def run_geometry_op(self, kind):
        from ggis.tools.geotools import GgsMapToolDrawLine

        spec = self._GEOM_OP_SPECS.get(str(kind))
        if spec is None:
            return False
        lyr = self._current_layer()
        if lyr is None or not lyr.is_vector():
            self._host.show_message(
                _tr("请先在图层树中选中一个矢量图层"), LEVEL_WARN)
            return False
        fids = self._selected_fids_of(lyr)
        if not fids:
            self._host.show_message(_tr("请先选中要处理的要素"), LEVEL_WARN)
            return False
        base = ""
        try:
            base = lyr.base_kind()
        except Exception:
            exc_note("run_geometry_op @ ggis/ui/views/map/map_edit.py:668")
            base = ""
        if kind == "break" and base != "line":
            self._host.show_message(_tr("打断只对线图层有效"), LEVEL_WARN)
            return False
        if kind in ("split", "reshape") and base == "point":
            self._host.show_message(_tr("点要素不能分割或修整"), LEVEL_WARN)
            return False

        hint, need_snap = spec
        sess = self._session_for(lyr)
        try:
            sess.start()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:687", exc_info=True)
        tool = GgsMapToolDrawLine(self.canvas, hint=hint, expect="line",
                                  need_snap=need_snap)
        try:
            tool.setSnapper(self.snapper())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:693", exc_info=True)
        self._geom_op = {"kind": kind, "layer": lyr, "fids": fids,
                         "session": sess, "tool": tool}
        tool.lineDrawn.connect(self._on_geom_op_line)
        tool.cancelled.connect(self._on_geom_op_cancelled)
        self.canvas.setMapTool(tool)
        self._set_geom_op_checked(kind, True)
        self._host.show_message(_tr(hint), LEVEL_INFO)
        return True

    def _on_geom_op_cancelled(self):
        self._geom_op = None
        self._set_geom_op_checked(None, False)
        try:
            self.set_map_tool("pan")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:709", exc_info=True)

    def _on_geom_op_line(self, line):
        ctx = getattr(self, "_geom_op", None)
        self._geom_op = None
        self._set_geom_op_checked(None, False)
        if not ctx:
            return
        try:
            n = self._apply_geom_op(ctx["kind"], ctx["layer"], ctx["fids"],
                                    ctx["session"], line)
        except Exception as e:
            self._host.show_message(_tr("操作失败：{0}").format(e), LEVEL_WARN)
            n = 0
        if n:
            self._host.log(_tr("几何编辑：{0}，影响 {1} 个要素").format(
                ctx["kind"], n))
        try:
            self.set_map_tool("pan")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:729", exc_info=True)

    def _apply_geom_op(self, kind, lyr, fids, session, line):
        from ggis.core.model import geometry as gops

        if kind == "align":
            geoms = []
            for fid in fids:
                _a, g = lyr.feature(fid)
                if g is not None:
                    geoms.append(g)
            off = gops.align_offset(geoms, line)
            if off is None:
                self._host.show_message(
                    _tr("无法对齐：参考线或要素无效"), LEVEL_WARN)
                return 0
            dx, dy = off
            if abs(dx) < 1e-12 and abs(dy) < 1e-12:
                self._host.show_message(
                    _tr("要素已经在参考线上，无需移动"), LEVEL_INFO)
                return 0
            session.move_features(fids, dx, dy)
            self._after_geom_op(lyr)
            return len(fids)

        mapping = []
        for fid in fids:
            _a, g = lyr.feature(fid)
            if g is None:
                continue
            if kind == "split":
                parts = gops.split_geometry(g, line)
            elif kind == "reshape":
                parts = gops.split_keep_main(g, line)
            elif kind == "break":
                parts = gops.break_line(g, line)
            else:
                parts = [g]
            if len(parts) <= 1:
                continue
            mapping.append((fid, parts))
        if not mapping:
            self._host.show_message(
                _tr("参考线未穿过选中要素"), LEVEL_INFO)
            return 0
        n = session.replace_features(mapping)
        self._after_geom_op(lyr)
        return n

    def _after_geom_op(self, lyr):
        try:
            GgsSelection.instance().clear(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:790", exc_info=True)
        try:
            lyr.invalidate_extent()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:794", exc_info=True)
        try:
            self.canvas.refresh()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:798", exc_info=True)

    def _on_edit_changed(self, layer=None):
        lyr = layer if layer is not None else self._current_layer()
        try:
            self.canvas.invalidate_edit(lyr)
        except Exception:
            try:
                self.canvas.update()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:822", exc_info=True)

    def _confirm_before_drop_dirty_edits(self, lyr, what):
        try:
            s = self._session_for(lyr)
            dirty = bool(s is not None and s.is_dirty())
        except Exception:
            exc_note("_confirm_before_drop_dirty_edits @ ggis/ui/views/map/map_edit.py:833")
            dirty = False
        if not dirty:
            return True
        try:
            _nm = lyr.name()
        except Exception:
            exc_note("_confirm_before_drop_dirty_edits @ ggis/ui/views/map/map_edit.py:839")
            _nm = ""
        try:
            ret = GgsMsgBox.question(
                self, _tr(what),
                _tr(""
                    "").format(_nm, what),
                GgsMsgBox.StandardButton.Save
                | GgsMsgBox.StandardButton.Discard
                | GgsMsgBox.StandardButton.Cancel,
                GgsMsgBox.StandardButton.Save)
        except Exception:
            exc_note("_confirm_before_drop_dirty_edits @ ggis/ui/views/map/map_edit.py:850")
            return True
        if ret == GgsMsgBox.StandardButton.Cancel:
            return False
        if ret == GgsMsgBox.StandardButton.Save:
            try:
                self.save_edits()
            except Exception:
                exc_note("_confirm_before_drop_dirty_edits @ ggis/ui/views/map/map_edit.py:857")
                return False
        return True

    def _vertex_tool(self):
        try:
            v = self
            return v.tools().get("vertex_edit") if v is not None else None
        except Exception:
            exc_note("_vertex_tool @ ggis/ui/views/map/map_edit.py:870")
            return None

    def commit_vertex_edit(self):
        t = self._vertex_tool()
        ok = False
        try:
            ok = bool(t.commit_draft()) if t is not None else False
        except Exception:
            exc_note("commit_vertex_edit @ ggis/ui/views/map/map_edit.py:882")
            ok = False
        if not ok:
            try:
                self._host.show_message(_tr("没有待确认的折点编辑"),
                                  LEVEL_INFO)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:896", exc_info=True)
        return ok

    def cancel_vertex_edit(self):
        t = self._vertex_tool()
        ok = False
        try:
            ok = bool(t.cancel_edit()) if t is not None else False
        except Exception:
            exc_note("cancel_vertex_edit @ ggis/ui/views/map/map_edit.py:910")
            ok = False
        try:
            self.set_map_tool("edit_select")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:923", exc_info=True)
        try:
            self._host.show_message(_tr("已结束折点编辑"), LEVEL_INFO)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:927", exc_info=True)
        return ok

    def reset_vertex_edit(self):
        t = self._vertex_tool()
        try:
            ok = bool(t.reset_draft()) if t is not None else False
        except Exception:
            exc_note("reset_vertex_edit @ ggis/ui/views/map/map_edit.py:939")
            ok = False
        if not ok:
            try:
                self._host.show_message(_tr("没有待重置的折点改动"), LEVEL_INFO)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:953", exc_info=True)
        return ok

    def _on_draft_changed(self, _has=False):
        try:
            self._host.ctx.svc("actions").refresh_states()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:966", exc_info=True)

    def _on_draft_committed(self, fids):
        ids = []
        for _f in (fids or ()):
            try:
                ids.append(int(_f))
            except Exception:
                exc_note("_on_draft_committed @ ggis/ui/views/map/map_edit.py:984")
                continue
        lyr = None
        try:
            lyr = self._current_layer()
        except Exception:
            exc_note("_on_draft_committed @ ggis/ui/views/map/map_edit.py:989")
            lyr = None
        if lyr is not None and ids:
            try:
                GgsSelection.instance().set_fids(lyr, ids)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1003", exc_info=True)
        try:
            self.set_map_tool("edit_select")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1007", exc_info=True)
        if lyr is not None:
            try:
                self.canvas.invalidate_edit(lyr)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1025", exc_info=True)
        if ids:
            try:
                self._host.show_message(
                    _tr("已确认 {0} 个要素的折点编辑").format(len(ids)),
                    LEVEL_INFO)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1032", exc_info=True)

    def _on_edit_structure_changed(self):
        try:
            lyr = self._current_layer()
            if lyr is not None:
                lyr.invalidate_extent()
                self.canvas.invalidate_symbol(lyr)
                self.canvas.invalidate_labels(lyr)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1049", exc_info=True)
        for table in list(getattr(self, "_open_tables", {}).values()):
            try:
                if table is not None and table.isVisible():
                    table.refresh()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1056", exc_info=True)
        try:
            self.canvas.update()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1060", exc_info=True)
        self._host.ctx.svc("actions").refresh_states()

    def _on_edit_dirty_changed(self, _key):
        self._host.ctx.svc("actions").refresh_states()
        self._sync_edit_proc_block()

    def _sync_edit_proc_block(self):
        dirty = False
        _mv = self
        for s in list((_mv.sessions() if _mv is not None else {}).values()):
            try:
                if s.is_dirty():
                    dirty = True
                    break
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1090", exc_info=True)
        try:
            self.canvas.set_edit_proc_block(dirty)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1094", exc_info=True)

    def _on_edit_tool_finished(self):
        self._target_session_refresh()

    def _target_session_refresh(self):
        s = None
        try:
            s = self.active_session()
        except Exception:
            exc_note("_target_session_refresh @ ggis/ui/views/map/map_edit.py:1090")
            s = None
        if s is not None:
            try:
                s.layer().invalidate_extent()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1110", exc_info=True)
        self._on_edit_structure_changed()

    def _after_edit_saved(self):
        try:
            self._sync_snapper_layers()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1117", exc_info=True)

    def _restore_wait_cursor(self):
        if not getattr(self, "_wait_cursor_active", False):
            return
        self._wait_cursor_active = False
        try:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.restoreOverrideCursor()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1130", exc_info=True)

    def set_map_tool(self, name):
        if name in ("measure_len", "measure_area", "measure_angle"):
            try:
                _cv = self.canvas
                if _cv is None or not _cv.hasExplicitCrs():
                    self._host.show_message(
                        _tr("请先设置视图坐标系，再使用测量工具"), LEVEL_WARN)
                    _ma = self._host.ctx.svc("actions")._acts.get(name)
                    if _ma is not None and _ma.isCheckable():
                        _ma.setChecked(False)
                    self._recheck_pan_tool()
                    return
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1152", exc_info=True)
        a = self._host.ctx.svc("actions")._acts.get(name)
        tool = getattr(self, "_tools", {}).get(name)
        if tool is None and name in _INTERACTIVE_TOOL_NAMES:
            try:
                if not getattr(self, "_tools", {}):
                    self._build_map_tools()
                    tool = self._tools.get(name)
            except Exception:
                import logging as _lg
                _lg.getLogger("gmagis").warning(
                    "地图视图 %s：补建工具表失败（name=%s）"
                    % (self.view_id, name))
            if tool is None and name == "identify":
                try:
                    from ggis.tools.maptools import GgsMapToolIdentify
                    _ti = GgsMapToolIdentify(self.canvas,
                                             self._identify_layers, self)
                    _ti.identified.connect(self._on_identified)
                    self._tools[name] = _ti
                    tool = _ti
                except Exception:
                    import logging as _lg
                    _lg.getLogger("gmagis").exception(
                        "地图视图 %s：补建识别工具失败" % self.view_id)
        if tool is None and name in _INTERACTIVE_TOOL_NAMES:
            self._host.show_message(
                _tr("地图工具「{}」不可用")
                .format(a.text() if a is not None else name), LEVEL_WARN)
        try:
            if tool is not None:
                if getattr(tool, "isEditTool", lambda: False)():
                    lyr = self._current_layer()
                    if lyr is None or not lyr.is_vector():
                        self._host.show_message(
                            _tr("请先在图层树中选中一个矢量图层"),
                            LEVEL_WARN)
                        if a is not None and a.isCheckable():
                            a.setChecked(False)
                        self._recheck_pan_tool()
                        return
                    self._sync_snapper_layers()
                    sess = self._session_for(lyr)
                    tool.setLayer(lyr)
                    tool.setSession(sess)
                    tool.setSnapper(self.snapper())
                    self._apply_snapping()
                elif hasattr(tool, "setCrsProvider"):
                    tool.setCrsProvider(self.measure_crs)
                self.canvas.setMapTool(tool)
                if name == "identify":
                    try:
                        _idock = getattr(
                            getattr(self._host, "_map_dock_mgr", None),
                            "identify_dock", None)
                        if _idock is not None:
                            self._host.ctx.region("dock")._show_dock(_idock)
                    except Exception:
                        logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1230", exc_info=True)
                hint = tool.statusHint()
                if hint:
                    self._host.show_message(_tr(hint), LEVEL_INFO)
                else:
                    self._host.show_message(
                        _tr("地图工具「{}」已激活").format(
                            a.text() if a is not None else name), LEVEL_INFO)
            else:
                self.canvas.setMapTool(name)
                if name in ("pan",):
                    self._host.show_message(_tr("浏览：拖动平移，滚轮缩放"),
                                      LEVEL_INFO)
                else:
                    self._host.show_message(
                        _tr("地图工具「{}」已激活（占位）").format(
                            a.text() if a is not None else name), LEVEL_INFO)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1248", exc_info=True)
        if a is not None and a.isCheckable():
            a.setChecked(True)
        try:
            self._sync_measure_panel(name)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1255", exc_info=True)

    def set_vertex_mode(self, mode):
        t = getattr(self, "_tools", {}).get("vertex_edit")
        if t is None:
            self._host.show_message(_tr("折点工具不可用"), LEVEL_WARN)
            return False
        self.set_map_tool("vertex_edit")
        try:
            real = t.setMode(mode)
        except Exception:
            exc_note("set_vertex_mode @ ggis/ui/views/map/map_edit.py:1264")
            return False
        for n in ("vertex_edit", "vertex_select", "vertex_add",
                  "vertex_move", "vertex_delete",
                  "vertex_select_rect", "vertex_select_lasso"):
            a = self._host.ctx.svc("actions")._acts.get(n)
            if a is None or not a.isCheckable():
                continue
            if n == "vertex_select":
                want = real in ("select", "select_rect", "select_lasso")
            elif n == "vertex_edit":
                want = True
            else:
                want = (n == "vertex_" + real)
            if a.isChecked() != bool(want):
                a.setChecked(bool(want))
        return True


    def _ensure_edit_session(self, layer=None):
        try:
            lyr = layer if layer is not None else self._current_layer()
            if lyr is None or not lyr.is_vector():
                return None
            s = self._session_for(lyr)
            if s is not None and not s.is_active():
                s.start()
                try:
                    self._sync_snapper_layers()
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_edit.py:1333", exc_info=True)
            return s
        except Exception:
            exc_note("_ensure_edit_session @ ggis/ui/views/map/map_edit.py:1318")
            return None
