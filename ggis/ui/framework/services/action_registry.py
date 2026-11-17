# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QApplication

from ggis.core.app import i18n
from ggis.core.model.selection import GgsSelection
from ggis.common.styling import icons

_tr = i18n.tr
_log = logging.getLogger("gmagis")

# 「底图」是纯下拉宿主：按钮只负责弹出 GgsBasemapMenu，真实行为
# 在菜单项里（BasemapLayerGroup → add_basemap）。其 ggis_dropdown
# 豁免属性要等地图视图构建 ribbon 页时才打上去，而 verify_placeholders
# 在装配期运行（彼时可能还没有任何视图）⇒ 必须在此登记，非未实现占位。
PLACEHOLDER_ACTIONS = frozenset({"basemap"})
LEVEL_INFO = "Info"
LEVEL_SUCCESS = "Success"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"


class ActionRegistry:

    def __init__(self, ctx):
        self.ctx = ctx
        self._acts = {}
        self._icon_actions = []
        self._placeholders = set()
        self._unregistered_placeholders = set()
        self._panel_acts_reg = {}

    @property
    def mw(self):
        return self.ctx.mw

    def get(self, name):
        return self._acts[name]

    def acts(self):
        return self._acts

    def reset(self):
        self._acts = {}
        self._placeholders = set()
        self._icon_actions = []


    def refresh_states(self):

        if getattr(self.ctx.mw, "_quitting", False):
            return
        has, has_vec = self._update_states_base()
        self._update_states_no_layer(has)
        self._update_states_pick(has)
        self._update_states_select(has, has_vec)
        is_vec, editing, lyr_e, _has_sel, _ve_on = self._update_states_edit_context()
        self._update_states_edit_tools(editing, _has_sel, _ve_on)
        self._update_states_edit_save(editing, is_vec, lyr_e)
        self._update_states_misc()
        self.refresh_measure_states()

    def _update_states_base(self):
        try:
            has = bool(self.ctx.svc("views")._on_view_method("has_layers"))
        except Exception:
            exc_note("_update_states_base @ ggis/ui/framework/services/action_registry.py:127")
            has = False
        try:
            has_vec = any(l.is_vector() and l.is_valid()
                          for l in self.ctx.project.layers())
        except Exception:
            exc_note("_update_states_base @ ggis/ui/framework/services/action_registry.py:133")
            has_vec = False
        return has, has_vec

    def _update_states_no_layer(self, has):
        try:
            _rs = self.ctx.mw.lbl_render
            if _rs is not None and hasattr(_rs, "set_clickable"):
                _rs.set_clickable(has)
        except Exception:
            exc_note("_update_states_no_layer @ ggis/ui/framework/services/action_registry.py:147")
            pass
        for n in ("zoom_sel", "zoom_layer", "selected_attrs",
                  "attribute_table", "layer_props", "symbol_editor",
                  "filter_active", "label_settings",
                  "toggle_labels", "export_vector", "export_raster",
                  "remove_layer", "histogram",
                  "refresh"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(has)
        for n in ("pan", "zoom_in", "zoom_out", "zoom_full", "locate_xy",
                  "refresh"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(has)

    def _update_states_pick(self, has):
        try:
            _v = self.ctx.mw.current_map_view()
            has_visible = (len(_v.visible_extent_layers()) > 0
                           if _v is not None else False)
        except Exception:
            exc_note("_update_states_pick @ ggis/ui/framework/services/action_registry.py:189")
            try:
                has_visible = any(l.is_valid() and l.is_visible()
                                  for l in self.ctx.project.layers())
            except Exception:
                exc_note("_update_states_pick @ ggis/ui/framework/services/action_registry.py:193")
                has_visible = False
        a = self._acts.get("zoom_visible")
        if a is not None:
            a.setEnabled(has_visible)
        a = self._acts.get("identify")
        if a is not None:
            a.setEnabled(has)
        a = self._acts.get("paste_features")
        if a is not None:
            from ggis.ui.views.map.map_layer import ggs_layer_clip
            a.setEnabled(bool(ggs_layer_clip()))
        try:
            _tree_sel = int(self.ctx.mw._forward_to_map_view(
                "_selected_tree_item_count") or 0) > 0
        except Exception:
            exc_note("_update_states_pick @ ggis/ui/framework/services/action_registry.py:224")
            _tree_sel = False
        for n in ("copy_features", "cut_features", "copy_path"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(_tree_sel)
        try:
            lyr = self.ctx.mw._forward_to_map_view("_current_layer")
            is_ras = bool(lyr is not None and lyr.is_raster()
                          and lyr.is_valid())
        except Exception:
            exc_note("_update_states_pick @ ggis/ui/framework/services/action_registry.py:236")
            is_ras = False
        for n in ("raster_transparency", "raster_histogram", "raster_attr_table"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(is_ras)
        try:
            _proj = self.ctx.project
            _all = list(_proj.layers() or []) if _proj is not None else []
            _has_any_raster = any(
                l is not None and l.is_raster() and l.is_valid() for l in _all)
        except Exception:
            exc_note("_update_states_pick @ ggis/ui/framework/services/action_registry.py:252")
            _has_any_raster = False
        for n in ("raster_profile", "spectral_profile"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(_has_any_raster)

    def _update_states_select(self, has, has_vec):
        for n in ("select", "select_rect", "select_poly", "select_lasso",
                  "select_circle", "select_line", "select_invert"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(has_vec)
        try:
            _lyr = self.ctx.mw._forward_to_map_view("_selected_tree_layer")
            _sel_vec = bool(_lyr is not None and _lyr.is_vector()
                            and _lyr.is_valid())
        except Exception:
            exc_note("_update_states_select @ ggis/ui/framework/services/action_registry.py:279")
            _sel_vec = False
        for n in ("select_attr", "select_bylocation"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(_sel_vec)
        try:
            has_sel = GgsSelection.instance().total() > 0
        except Exception:
            exc_note("_update_states_select @ ggis/ui/framework/services/action_registry.py:290")
            has_sel = False
        for n in ("selected_attrs",):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(has and has_sel)
        for n in ("select_clear",):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(has_vec and has_sel)
        for n in ("snap_enable",) + self.snap_acts():
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(has_vec)

    def _update_states_edit_context(self):
        lyr_e = None
        try:
            lyr_e = self.ctx.mw._forward_to_map_view("_current_layer")
            is_vec = bool(lyr_e is not None and lyr_e.is_vector()
                          and lyr_e.is_valid())
        except Exception:
            exc_note("_update_states_edit_context @ ggis/ui/framework/services/action_registry.py:330")
            is_vec = False
        editing = is_vec
        if is_vec:
            self.ctx.svc("views")._on_view_method("_ensure_edit_session")
        _has_sel = False
        try:
            _lyr_sel0 = self.ctx.mw._forward_to_map_view("_current_layer")
            if _lyr_sel0 is not None and _lyr_sel0.is_vector():
                _has_sel = bool(GgsSelection.instance().fids(_lyr_sel0))
        except Exception:
            exc_note("_update_states_edit_context @ ggis/ui/framework/services/action_registry.py:351")
            _has_sel = False
        _ve_on = False
        try:
            _a_ve = self._acts.get("vertex_edit")
            _ve_on = bool(_a_ve is not None and _a_ve.isChecked())
        except Exception:
            exc_note("_update_states_edit_context @ ggis/ui/framework/services/action_registry.py:364")
            _ve_on = False
        if _ve_on and not (is_vec and _has_sel):
            try:
                QTimer.singleShot(0, self.ctx.svc("views")._map_state()._auto_finish_vertex_edit)
            except Exception:
                exc_note("_update_states_edit_context @ ggis/ui/framework/services/action_registry.py:375")
                pass
        return is_vec, editing, lyr_e, _has_sel, _ve_on

    def _update_states_edit_tools(self, editing, _has_sel, _ve_on):
        for n in ("move_feature", "align_features"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and _has_sel and not _ve_on))
        a = self._acts.get("vertex_edit")
        if a is not None:
            a.setEnabled(bool(editing and _has_sel))
        for n in ("vertex_select", "vertex_add", "vertex_move", "vertex_delete",
                  "vertex_select_rect", "vertex_select_lasso",
                  "cancel_edit"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and _has_sel and _ve_on))
        _draft_now = False
        try:
            _t_ve = None
            try:
                _mv0 = self.ctx.mw.current_map_view()
                _t_ve = (getattr(_mv0, "_tools", {}) or {}).get("vertex_edit")
            except Exception:
                exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:418")
                _t_ve = None
            _draft_now = bool(_t_ve is not None and _t_ve.has_draft())
        except Exception:
            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:421")
            _draft_now = False
        for n in ("commit_edit", "reset_edit"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and _has_sel and _ve_on
                                  and _draft_now))
        for n in ("zoom_sel", "selected_attrs"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(_has_sel))
        for n in ("edit_select", "edit_select_rect", "edit_select_poly",
                  "edit_select_lasso", "edit_select_circle",
                  "edit_select_line"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and not _ve_on))
        _dirty_now = False
        try:
            _lyr_c = self.ctx.mw._forward_to_map_view("_current_layer")
            if _lyr_c is not None and _lyr_c.is_vector():
                _s_c = self.ctx.svc("views")._on_view_method("_session_for", _lyr_c)
                _dirty_now = bool(_s_c is not None and _s_c.is_active()
                                  and _s_c.is_dirty())
        except Exception:
            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:460")
            _dirty_now = False
        a = self._acts.get("discard_edits")
        if a is not None:
            a.setEnabled(bool(editing and _dirty_now))
        for n in ("snap_enable",) + tuple(self.snap_acts()):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and _ve_on))
        for n in ("add_feature", "merge_selected", "combine_selected"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and not _ve_on))
        _clip_n = 0
        try:
            _cnt = self.ctx.svc("views")._on_view_method("feature_clip_count")
            # 零视图时 _on_view_method 返回 None，按 0 处理，不算异常。
            _clip_n = int(_cnt) if _cnt is not None else 0
        except Exception:
            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:485")
            _clip_n = 0
        for n in ("copy_feat", "cut_feat"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and _has_sel))
        for n in ("paste_feat", "paste_feat_to"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(bool(editing and _clip_n))
        _gk = ""
        _gmulti = False
        _kinds = set()
        try:
            _gl = self.ctx.mw._forward_to_map_view("_current_layer")
            if (_gl is not None and _gl.is_vector()
                    and not _gl.is_table()):
                _gk = str(_gl.geometry_type() or "").lower()
                if not _gk or _gk in ("unknown", "none"):
                    _gk = str(_gl.base_kind() or "").lower()
                if _has_sel:
                    from ggis.core.model.geometry import (base_kind as _bk,
                                                 is_multi)
                    _geoms_g = _gl.geoms()
                    for _f in GgsSelection.instance().fids(_gl):
                        try:
                            _g0 = _geoms_g[int(_f)]
                        except Exception:
                            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:522")
                            continue
                        try:
                            _k0 = str(_bk(_g0) or "")
                        except Exception:
                            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:527")
                            _k0 = ""
                        if _k0:
                            _kinds.add(_k0)
                        try:
                            _parts = list(getattr(_g0, "geoms", []) or [])
                        except Exception:
                            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:533")
                            _parts = []
                        if len(_parts) >= 2 or (not _parts
                                                and is_multi(_g0)):
                            _gmulti = True
        except Exception:
            exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:540")
            pass
        _src_kind = "".join(sorted(_kinds)) if _kinds else _gk
        _is_line = "line" in _src_kind
        _is_poly = "polygon" in _src_kind
        for _n, _ok in (("split_features", _is_line or _is_poly),
                        ("reshape_features", _is_line or _is_poly),
                        ("simplify_selected", _is_line or _is_poly),
                        ("break_features", _is_line),
                        ("multipart_single", _gmulti)):
            a = self._acts.get(_n)
            if a is not None:
                a.setEnabled(bool(editing and _has_sel and _ok
                                  and not _ve_on))
        a = self._acts.get("delete_feature")
        if a is not None:
            _sel_n = 0
            try:
                _lyr_sel = self.ctx.mw._forward_to_map_view("_current_layer")
                if _lyr_sel is not None and _lyr_sel.is_vector():
                    _sel_n = len(GgsSelection.instance().fids(_lyr_sel))
            except Exception:
                exc_note("_update_states_edit_tools @ ggis/ui/framework/services/action_registry.py:567")
                _sel_n = 0
            a.setEnabled(bool(editing and _sel_n and not _ve_on))

    def _update_states_edit_save(self, editing, is_vec, lyr_e):
        sess = None
        if editing:
            try:
                v = self.ctx.svc("views")._map_state()
                if v is not None:
                    sess = v.sessions().get(str(lyr_e.id()))
            except Exception:
                exc_note("_update_states_edit_save @ ggis/ui/framework/services/action_registry.py:587")
                sess = None
        dirty = bool(editing and sess is not None and sess.is_dirty())
        a = self._acts.get("save_edits")
        if a is not None:
            a.setEnabled(dirty)
        undo_ok = redo_ok = False
        if editing and sess is not None:
            try:
                st = sess.undo_stack()
                undo_ok = bool(st.canUndo())
                redo_ok = bool(st.canRedo())
            except Exception:
                exc_note("_update_states_edit_save @ ggis/ui/framework/services/action_registry.py:599")
                undo_ok = redo_ok = False
        a = self._acts.get("undo_edit")
        if a is not None:
            a.setEnabled(undo_ok)
        a = self._acts.get("redo_edit")
        if a is not None:
            a.setEnabled(redo_ok)
        try:
            n_sel = len(self.ctx.svc("views")._on_view_method("_selected_fids_of", lyr_e)) if is_vec else 0
        except Exception:
            exc_note("_update_states_edit_save @ ggis/ui/framework/services/action_registry.py:612")
            n_sel = 0
        for n in ("merge_selected", "combine_selected"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(editing and n_sel >= 2)

    def _update_states_misc(self):
        a = self._acts.get("toggle_labels")
        if a is not None:
            on = False
            try:
                from ggis.render.labeling import get_label_style
                lyr = self.ctx.mw._forward_to_map_view("_current_layer")
                if lyr is not None and lyr.is_vector():
                    on = bool(get_label_style(lyr).enabled)
            except Exception:
                exc_note("_update_states_misc @ ggis/ui/framework/services/action_registry.py:630")
                on = False
            a.setChecked(on)
        try:
            n_vec = sum(1 for l in self.ctx.project.layers()
                        if l.is_vector() and l.is_valid())
        except Exception:
            exc_note("_update_states_misc @ ggis/ui/framework/services/action_registry.py:637")
            n_vec = 0
        for n in ("analysis", "analysis_buffer", "analysis_clip",
                  "analysis_dissolve"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(n_vec >= 1)
        for n in ("analysis_intersect", "analysis_union"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(n_vec >= 2)
        try:
            n_all = sum(1 for l in self.ctx.project.layers()
                        if l.is_valid())
        except Exception:
            exc_note("_update_states_misc @ ggis/ui/framework/services/action_registry.py:652")
            n_all = 0
        has_layout = bool(self.ctx.svc("views").layouts())
        for n in ("layout_designer", "layout_new"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(True)
        for n in ("export_pdf", "export_image", "print_map"):
            a = self._acts.get(n)
            if a is not None:
                a.setEnabled(n_all >= 1 or has_layout)

    def refresh_measure_states(self):
        try:
            cv = self.ctx.mw.canvas
            ok = bool(cv is not None and cv.hasExplicitCrs())
        except Exception:
            exc_note("refresh_measure_states @ ggis/ui/framework/services/action_registry.py:674")
            ok = False
        for n in ("measure_len", "measure_area", "measure_angle"):
            a = self._acts.get(n)
            if a is not None:
                try:
                    a.setEnabled(ok)
                except Exception:
                    exc_note("refresh_measure_states @ ggis/ui/framework/services/action_registry.py:681")
                    pass

    def verify_placeholders(self):
        bad = []
        for name in sorted(self._placeholders):
            if name in PLACEHOLDER_ACTIONS:
                continue
            a = self._acts.get(name)
            if a is not None and a.property("ggis_dropdown"):
                continue
            bad.append(name)
        for name in bad:
            print("[placeholder] 动作 %r 没有槽也没登记，"
                  "请实现它或加进 main_window.PLACEHOLDER_ACTIONS"
                  % name, file=sys.stderr, flush=True)
        self._unregistered_placeholders = tuple(bad)
        return self._unregistered_placeholders

    def index_order(self):
        return list(self._acts.keys())

    def stub(self, name):
        a = self._acts.get(name)
        text = a.text() if a is not None else name
        self.ctx.mw.show_message(
            _tr("{}：功能占位，将在 GIS 里程碑接入").format(text),
            LEVEL_INFO)

    def snap_acts(self):
        v = self.ctx.svc("views")._map_state()
        if v is not None:
            try:
                return tuple(v.SNAP_KIND_ACTS)
            except Exception:
                exc_note("snap_acts @ ggis/ui/framework/services/action_registry.py:737")
                pass
        return self.ctx.mw._SNAP_ACTS_FALLBACK

    def _on_auto_save_toggled(self, on):
        try:
            from ggis.core.app import settings as _st
            _st.set("auto_save_enabled", bool(on))
            tb = getattr(self.ctx.mw, "_title_bar", None)
            sw = getattr(tb, "_auto_save_switch", None)
            if sw is not None and sw.isChecked() != bool(on):
                sw.setChecked(bool(on))
        except Exception:
            _log.exception("silent exception in _on_auto_save_toggled")

    def _on_layer_undo_available(self, on):
        try:
            if getattr(self.ctx.mw, "_quitting", False):
                return
            a = self._acts.get("undo_layer")
            if a is not None:
                a.setEnabled(bool(on))
        except Exception:
            _log.exception("silent exception in _on_layer_undo_available")

    def _on_layer_redo_available(self, on):
        try:
            if getattr(self.ctx.mw, "_quitting", False):
                return
            a = self._acts.get("redo_layer")
            if a is not None:
                a.setEnabled(bool(on))
        except Exception:
            _log.exception("silent exception in _on_layer_redo_available")

    def _new_project_wizard(self):
        """新建工程向导：先选保存文件与视图类型（复用起始页对话框），
        再走原服务建工程、按勾选建视图。取消则什么都不做。
        保存位置留空 = 内存工程（不绑定文件，退出前需另存）。
        """
        try:
            from ggis.ui.launch.home import NewProjectDialog
            dlg = NewProjectDialog(self.mw)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
            path = dlg.chosen_path().strip()
            kinds = dlg.chosen_kinds()  # 零勾选 = 零视图工程（合法）
        except Exception:
            _log.exception("silent exception in new project wizard")
            return
        try:
            if not self.ctx.svc("projects").new_project(path):
                return
            # 与打开工程同一装载机制：先关现有工程的全部视图再按勾选建。
            self.ctx.svc("views").apply_new_project_views(kinds)
        except Exception:
            exc_note("new project wizard @ ggis/ui/framework/services/action_registry.py")

    def build(self):
        self._acts = {}
        self._placeholders = set()

        def act(name, icon_name, text, tip, slot=None, shortcut=None,
                checkable=False):
            a = QAction(icons.icon(icon_name), _tr(text), self.ctx.mw)
            a.setProperty("ggsIconName", icon_name)
            if tip:
                a.setToolTip(_tr(tip))
                a.setStatusTip("")
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            a.setCheckable(checkable)
            if slot is None:
                self._placeholders.add(name)
                slot = lambda _c=False, n=name: self.stub(n)
            self.ctx.wiring.connect((a.triggered), (slot), "action")
            self._acts[name] = a
            self._icon_actions.append((a, icon_name))
            return a

        self._build_map_actions(act)

        act("new_map_view", "map_street", "新建地图",
            "新开一张独立的地图视图（各自的选择集、渲染进程与视野）",
            lambda _c=False: self.ctx.mw.new_map_view())
        act("new_layout_view", "layout", "新建布局",
            "新建一张布局：先确认大小、单位、方向与标签名，再在主窗口内打开",
            lambda _c=False: self.ctx.svc("views").new_layout_view())

        act("new_project", "new", "新建工程",
            "关闭当前工程并新建空工程 (Ctrl+Shift+N)",
            lambda _c=False: self._new_project_wizard(), "Ctrl+Shift+N")
        act("open_project", "project_open", "打开工程…",
            "打开工程文件 (Ctrl+O)", lambda _c=False: self.ctx.svc("projects").open_project(),
            "Ctrl+O")
        act("save_project", "save", "保存工程", "保存当前工程 (Ctrl+S)",
            lambda _c=False: self.ctx.svc("projects").save_project(),
            QKeySequence.StandardKey.Save)
        act("reset_window", "reset_edit", "重置窗口",
            "把窗口重置到默认位置和大小（取消最大化/最小化）",
            lambda _c=False: self.ctx.mw.reset_window_geometry())
        act("auto_save_toggle", "save", "自动保存",
            "开启或关闭定时自动保存工程（间隔在选项里设置）",
            lambda checked=False: self._on_auto_save_toggled(bool(checked)),
            checkable=True)
        act("undo_layer", "undo", "撤销图层操作",
            "撤销上一次图层操作（显隐、删除、恢复、排序）",
            lambda _c=False: self.ctx.project.undo_stack().undo())
        act("redo_layer", "redo", "重做图层操作",
            "重做上一次被撤销的图层操作",
            lambda _c=False: self.ctx.project.undo_stack().redo())
        act("save_project_as", "save", "工程另存为…",
            "把当前工程另存为新文件 (Ctrl+Shift+S)",
            lambda _c=False: self.ctx.svc("projects").save_project_as(), "Ctrl+Shift+S")
        act("project_props", "project_props", "工程属性…",
            "工程标题、量算单位、坐标精度、画布底色与目标坐标系"
            " (Ctrl+Shift+P)",
            lambda _c=False: self.ctx.svc("projects").open_project_properties(), "Ctrl+Shift+P")
        act("camera", "camera", "导出地图图片…",
            "把当前地图画布保存为 PNG 图片",
            lambda _c=False: self.ctx.svc("views")._on_view_method("export_map_image"))
        act("settings", "settings", "选项…",
            "工程设置（名称 / 单位）与应用程序选项（主题 / 语言等）",
            lambda _c=False: self.ctx.svc("settings_ctl").open_dialog())
        act("quit", "quit", "退出", "退出程序 (Ctrl+Q)",
            lambda _c=False: self.ctx.mw.close(), "Ctrl+Q")

        act("layout_designer", "layout", "布局设计器…",
            "新建 / 编辑打印布局：图框、图例、比例尺、指北针、格网",
            lambda _c=False: self.ctx.svc("views").open_layout())
        act("layout_new", "layout", "新建布局",
            "按当前地图视图创建一个 A4 横向布局",
            lambda _c=False: self.ctx.svc("views").new_layout())
        act("export_pdf", "export_pdf", "导出 PDF",
            "把当前布局导出为矢量 PDF（文字可选中、线条不糊）",
            lambda _c=False: self.ctx.mw.export_layout("pdf"))
        act("export_image", "export_image", "导出图片",
            "把当前布局导出为 PNG / JPG / TIFF",
            lambda _c=False: self.ctx.mw.export_layout("image"))
        act("print_map", "print", "打印…",
            "把当前布局送到打印机",
            lambda _c=False: self.ctx.mw.export_layout("print"))

        act("open_help", "info", "使用手册",
            "打开使用手册：界面、数据、编辑、分析、出图逐个讲一遍 (F1)",
            lambda _c=False: self.ctx.svc("settings_ctl").open_help(), "F1")
        act("open_shortcuts", "keyboard", "快捷键",
            "查看全部菜单功能的快捷键 (Ctrl+F1)",
            lambda _c=False: self.ctx.svc("settings_ctl").open_shortcuts(), "Ctrl+F1")
        act("about_act", "about", "关于", "版本、运行环境与项目说明",
            lambda _c=False: self.ctx.svc("settings_ctl").about())
        act("widget_gallery", "settings", "控件画廊",
            "浏览项目内全部 Ggs 标准控件的外观",
            lambda _c=False: self.ctx.svc("settings_ctl").open_widget_gallery())

        self._acts["undo"] = self._acts["undo_edit"]
        self._acts["redo"] = self._acts["redo_edit"]
        try:
            st = self.ctx.project.undo_stack()
            st.canUndoChanged.connect(self._on_layer_undo_available)
            st.canRedoChanged.connect(self._on_layer_redo_available)
            self._on_layer_undo_available(st.canUndo())
            self._on_layer_redo_available(st.canRedo())
        except Exception:
            _log.exception("silent exception in build")
        try:
            from ggis.core.app import settings as _st
            self._acts["auto_save_toggle"].setChecked(
                bool(_st.get("auto_save_enabled", True)))
        except Exception:
            _log.exception("silent exception in build")

    def _build_map_actions(self, act):

        def vf(meth, *args, **kwargs):
            return lambda _c=False: self.ctx.svc("views")._on_view_method(meth, *args, **kwargs)

        act("add_vector", "add_vector", "添加矢量图层",
            "添加矢量图层 (Ctrl+Shift+V)：Shapefile / GeoPackage / GeoJSON…",
            vf("add_vector"), "Ctrl+Shift+V")
        act("add_raster", "add_raster", "添加栅格图层",
            "添加栅格图层 (Ctrl+Shift+R)：GeoTIFF / IMG / ASCII Grid…",
            vf("add_raster"), "Ctrl+Shift+R")
        act("add_data", "add_data_main", "添加数据",
            "向当前工程添加图层 / 数据",
            vf("add_data"))
        act("add_browse", "open", "浏览…",
            "从文件添加数据（自动识别矢量 / 栅格 / 文本）",
            vf("add_data"))
        act("add_text_layer", "add_vector", "添加文本数据 (CSV)…",
            "添加分隔文本数据（CSV / TSV / TXT），按经纬度列转成点图层",
            vf("add_text_layer"))
        act("add_db_layer", "browser", "数据库 / Web 服务…",
            "打开数据源浏览器：本地文件、数据库、OGC 服务",
            vf("add_db_layer"))
        act("basemap", "basemap_main", "底图", "添加在线底图")
        act("add_tile", "xyz_tile", "在线瓦片…",
            "添加在线瓦片图层（XYZ URL 模板）",
            vf("add_tile_layer"))
        act("add_from_path", "project_open", "从路径…",
            "从路径输入数据源添加",
            vf("add_from_path"))
        act("new_file", "new_file", "新建文件", "新建矢量 / 数据库文件",
            vf("new_vector_file", ""))
        act("new_shapefile", "new_shapefile", "形状文件",
            "新建形状文件（.shp）",
            vf("new_vector_file", ".shp"))
        act("new_gpkg", "database", "地理包", "新建地理包（.gpkg）图层",
            vf("new_vector_file", ".gpkg"))
        act("new_gdb", "database", "Esri 文件地理数据库",
            "新建 Esri 文件地理数据库（.gdb）",
            vf("new_vector_file", ".gdb"))
        act("insert_shape", "new_shape", "新建形状",
            "新建矢量图层并绘制点 / 线 / 面要素",
            vf("add_graphic_layer"))
        act("add_xy_points", "table", "XY 表转点…",
            "把含经纬度字段的 CSV / 文本表转为点图层",
            vf("add_xy_points"))
        act("add_graphic_layer", "add_feature", "添加图形图层…",
            "新建可绘制点 / 线 / 面的图形图层",
            vf("add_graphic_layer"))
        act("new_layer", "new_shape", "新建图层", "新建矢量图层",
            vf("new_layer_from_dialog"))

        self.ctx.mw.nav_group = QActionGroup(self.ctx.mw)
        self.ctx.mw.nav_group.setExclusive(True)
        for name, icon_name, text, tip, sc in (
            ("pan", "pan", "浏览", "浏览 / 平移地图", "Alt+1"),
            ("identify", "identify", "识别", "查询要素属性",
             "Ctrl+Shift+I"),
            ("select", "sel_rect", "选择", "矩形框选要素", None),
            ("select_poly", "sel_poly", "多边形", "多边形框选要素", None),
            ("select_lasso", "sel_lasso", "套索", "套索圈选要素", None),
            ("select_circle", "sel_circle", "圆形", "圆形框选要素", None),
            ("select_line", "sel_line", "线", "折线框选要素", None),
            ("measure_len", "measure_length", "测量", "测量地图上的距离",
             None),
            ("measure_area", "measure_area", "测量面积", "测量多边形面积",
             None),
            ("insert_point", "ins_point", "点", "新建点图层并绘制要素", None),
            ("insert_line", "ins_line", "线", "新建线图层并绘制要素", None),
            ("insert_poly", "ins_poly", "面", "新建面图层并绘制要素", None),
        ):
            if name.startswith("insert_"):
                kind = name.split("_", 1)[1]
                act(name, icon_name, text, tip,
                    vf("new_graphic_layer", kind), sc)
                continue
            a = act(name, icon_name, text, tip,
                    vf("set_map_tool", name),
                    sc, checkable=True)
            self.ctx.mw.nav_group.addAction(a)

        act("coord_transform", "coord_transform", "坐标转换",
            "打开 / 收起「坐标转换」面板：在源 / 目标坐标系之间换算坐标",
            lambda _c=False: self.ctx.mw._map_dock_mgr.toggle_coord_transform(), None,
            checkable=True)
        act("measure_angle", "measure_angle", "测量角度",
            "测量两条线之间的角度",
            vf("set_map_tool", "measure_angle"),
            None, checkable=True)
        self.ctx.mw.nav_group.addAction(self._acts["measure_angle"])
        _ms = self.ctx.svc("views")._map_state()
        if _ms is not None:
            for _a in self.ctx.mw.nav_group.actions():
                _a.toggled.connect(_ms._on_nav_action_toggled)
        _ms0 = self.ctx.svc("views")._map_state()
        if _ms0 is not None:
            QTimer.singleShot(0, _ms0._ensure_nav_checked)
        act("select_rect", "sel_rect", "矩形", "矩形框选要素",
            vf("set_map_tool", "select"))
        act("measure_dist", "measure_length", "测量距离", "测量地图上的距离",
            vf("set_map_tool", "measure_len"))

        act("zoom_in", "zoom_in", "放大", "点击放大一档 (Alt+2)",
            lambda _c=False: self.ctx.mw.canvas.zoomIn(), "Alt+2")
        act("zoom_out", "zoom_out", "缩小", "点击缩小一档 (Alt+3)",
            lambda _c=False: self.ctx.mw.canvas.zoomOut(), "Alt+3")
        act("zoom_full", "zoom_full", "全图显示",
            "缩放到全部图层的完整范围 (Ctrl+Shift+F)",
            vf("zoom_full"),
            "Ctrl+Shift+F")
        act("zoom_layer", "zoom_layer", "缩放至图层",
            "缩放到活动图层范围 (Ctrl+Shift+L)",
            vf("zoom_to_layer"),
            "Ctrl+Shift+L")
        act("zoom_sel", "zoom_layer", "缩放至",
            "缩放到矢量图层中选中的要素 (Ctrl+J)",
            vf("zoom_to_selection"),
            "Ctrl+J")
        act("selected_attrs", "identify", "属性",
            "查看选中要素的属性（弹出窗口，可复制）",
            vf("show_selected_attributes"))
        act("discard_edits", "discard", "放弃",
            "放弃全部未保存的改动，恢复到保存后的状态",
            vf("discard_edits"))
        act("refresh", "refresh", "刷新画布", "重绘全部图层 (F5)",
            lambda _c=False: self.ctx.mw.canvas.refresh(), "F5")

        act("attribute_table", "table", "打开属性表",
            "打开当前活动图层的属性表 (F6)",
            vf("open_attribute_table"), "F6")
        act("layer_props", "info", "图层属性…", "打开活动图层的属性窗口",
            vf("open_layer_properties"))
        act("symbol_editor", "styling", "符号系统…",
            "设置图层的符号系统（矢量：颜色/符号/渲染方式；"
            "栅格：波段/色带/拉伸/重采样）",
            vf("open_symbology"))
        act("raster_transparency", "opacity", "栅格符号系统…",
            "打开符号系统面板（栅格页）：色带、波段、对比度拉伸与透明度",
            vf("open_raster_display"))
        act("raster_histogram", "stretch", "直方图…",
            "查看栅格像元值分布并调整对比度拉伸",
            vf("open_raster_display"))
        act("raster_profile", "histogram", "剖面曲线",
            "打开剖面曲线面板：选择波段、在地图上取点，画出该点行 / 列方向的像素值曲线",
            lambda _c=False: self.ctx.mw._map_dock_mgr.toggle_profile_dock(),
            checkable=True)
        act("spectral_profile", "spectrum", "光谱曲线",
            "打开光谱曲线面板：在多个栅格图层的同一位置取各波段值，画成多色折线对比",
            lambda _c=False: self.ctx.mw._map_dock_mgr.toggle_spectral_dock(),
            checkable=True)
        for _n in ("coord_transform", "raster_profile", "spectral_profile"):
            _a = self._acts.get(_n)
            if _a is not None and _a not in self.ctx.mw.nav_group.actions():
                self.ctx.mw.nav_group.addAction(_a)
                _ms2 = self.ctx.svc("views")._map_state()
                if _ms2 is not None:
                    _a.toggled.connect(_ms2._on_nav_action_toggled)
        act("raster_attr_table", "table", "栅格属性表…",
            "查看分类栅格的值 / 类别 / 颜色 / 像素数",
            vf("open_raster_attr_table"))
        act("toolbox", "processing", "基础工具箱",
            "打开基础工具箱（空间分析算法）(Ctrl+Alt+T)",
            lambda _c=False: self.ctx.svc("views").toggle_toolbox(), "Ctrl+Alt+T",
            checkable=True)
        act("model_builder", "model", "新建模型构建器",
            "新建一张模型：弹名称框确认后，在主窗口内打开一个独立的模型构建器视图（可与已有模型共存、同时打开多张）",
            lambda _c=False: self.ctx.svc("views").new_model_view())

        act("style_manager", "color_swatch", "样式管理器…",
            "样式库管理：符号 / 色带 / 标注 / 文本格式",
            lambda _c=False: self.ctx.region("title").open_style_manager())
        act("histogram", "histogram", "直方图…",
            "绘制活动图层选中字段的分布",
            vf("open_histogram"))

        act("add_feature", "feature_new", "创建",
            "创建：按活动图层的几何类型在地图上数字化新要素 (Ctrl+.)",
            vf("set_map_tool", "add_feature"),
            "Ctrl+.", checkable=True)
        act("move_feature", "move_feature", "移动",
            "移动：按住选中的要素拖动 (Ctrl+Alt+M)",
            vf("set_map_tool", "move_feature"),
            "Ctrl+Alt+M", checkable=True)
        act("delete_feature", "delete_feature", "删除",
            "删除选中的要素（需先选中要素，与「选择要素」配合使用）",
            vf("delete_selected_features"))
        act("vertex_edit", "vertex_edit", "编辑折点",
            "编辑折点：拖动折点移动、双击线段加点、Delete 删除所选折点",
            vf("set_vertex_mode", "all"),
            None, checkable=True)
        act("vertex_select", "vertex_select", "选择折点",
            "选择折点：单击折点选中（Ctrl 加选 / 减选）",
            vf("set_vertex_mode", "select"),
            None, checkable=True)
        act("vertex_add", "vertex_add", "添加",
            "添加折点：在要素线段上单击插入新折点",
            vf("set_vertex_mode", "add"),
            None, checkable=True)
        act("vertex_move", "vertex_move", "移动",
            "移动折点：按住任一所选折点拖动，整组一起移动",
            vf("set_vertex_mode", "move"),
            None, checkable=True)
        act("vertex_delete", "vertex_delete", "删除",
            "删除折点：单击折点即删除",
            vf("set_vertex_mode", "delete"),
            None, checkable=True)
        act("vertex_select_rect", "sel_rect", "矩形",
            "矩形框选折点：拖出一个矩形，选中框内的所有折点",
            vf("set_vertex_mode", "select_rect"),
            None, checkable=True)
        act("vertex_select_lasso", "sel_lasso", "套索",
            "套索选择折点：按住拖出任意形状，选中圈内的所有折点",
            vf("set_vertex_mode", "select_lasso"),
            None, checkable=True)
        act("commit_edit", "finish", "完成",
            "完成编辑：提交当前折点编辑（等价于在地图上双击）",
            vf("commit_vertex_edit"))
        act("cancel_edit", "cancel", "取消",
            "取消：丢弃未确认的改动，并结束这次折点编辑",
            vf("cancel_vertex_edit"))
        act("reset_edit", "reset_edit", "重置",
            "重置：丢弃未确认的改动，几何回到原样（不退出折点编辑）",
            vf("reset_vertex_edit"))
        act("split_features", "split_features", "分割",
            "分割：画一条分割线，被穿过的要素被切开（所有块都保留）",
            vf("run_geometry_op", "split"))
        act("reshape_features", "reshape", "修整",
            "修整：画一条线切一刀，只保留含原中心的那一块",
            vf("run_geometry_op", "reshape"))
        act("merge_selected", "merge_features", "融合",
            "融合：选中要素的几何合并为一个，属性保留最大要素",
            vf("merge_selected"))
        act("multipart_single", "multipart_single", "拆分",
            "拆分多部件要素：选中要素的每个部件拆成独立要素",
            vf("split_multipart_selected"))
        act("combine_selected", "combine_features", "合并",
            "合并：所选要素合为一个多部件要素",
            vf("combine_selected"))
        act("align_features", "align", "对齐",
            "对齐：画一条参考线，所选要素整体平移到其中心的投影点",
            vf("run_geometry_op", "align"))
        act("break_features", "break", "打断",
            "打断：画一条线，线图层中与线相交的要素在交点处断开",
            vf("run_geometry_op", "break"))
        act("simplify_selected", "simplify", "概化",
            "概化：按容差简化所选要素几何（Douglas-Peucker）",
            vf("simplify_selected"))
        act("save_edits", "save", "保存",
            "提交所有图层中未保存的编辑 (Ctrl+Shift+E)",
            vf("save_edits"),
            "Ctrl+Shift+E")
        act("edit_select", "sel_rect", "选择",
            "选择当前图层中的要素",
            vf("_pick_edit_select", "edit_select"),
            None, checkable=True)
        for _n, _icon, _lbl, _tip in (
                ("edit_select_rect", "sel_rect", "矩形", "矩形框选要素"),
                ("edit_select_poly", "sel_poly", "多边形", "多边形框选要素"),
                ("edit_select_lasso", "sel_lasso", "套索", "套索圈选要素"),
                ("edit_select_circle", "sel_circle", "圆形", "圆形框选要素"),
                ("edit_select_line", "sel_line", "线", "折线框选要素")):
            _target = "edit_select" if _n == "edit_select_rect" else _n
            act(_n, _icon, _lbl, _tip,
                vf("_pick_edit_select", _target),
                None, checkable=True)
        for _n in ("add_feature", "vertex_edit",
                   "edit_select", "edit_select_poly", "edit_select_lasso",
                   "edit_select_circle", "edit_select_line"):
            self.ctx.mw.nav_group.addAction(self._acts[_n])

        act("undo_edit", "undo", "撤销",
            "撤销活动图层最近一次编辑操作 (Ctrl+Z)",
            vf("undo_edit"), "Ctrl+Z")
        act("redo_edit", "redo", "重做",
            "重做活动图层上一次被撤销的编辑 (Ctrl+Y)",
            vf("redo_edit"), "Ctrl+Y")

        act("snap_enable", "lock", "捕捉",
            "捕捉：打开后鼠标落点吸附到几何的指定部位",
            vf("_apply_snapping"),
            None, checkable=True)
        for _n, _ic, _tx, _tp in (
                ("snap_endpoint", "ins_line", "端点",
                 "捕捉到线 / 面的首末顶点"),
                ("snap_vertex", "vertex_edit", "节点",
                 "捕捉到任意折点"),
                ("snap_intersection", "combine_features", "交点",
                 "捕捉到两条线段的交叉点"),
                ("snap_midpoint", "snap_midpoint", "中点",
                 "捕捉到线段的中间点"),
                ("snap_edge", "snap_edge", "边",
                 "捕捉到线段上距离鼠标最近的点（不限于端点与折点）")):
            act(_n, _ic, _tx, _tp,
                vf("_on_snap_act", _n),
                None, checkable=True)


        act("select_attr", "select_attr", "按属性…",
            "用表达式筛选活动图层的要素 (Ctrl+F3)",
            vf("select_by_expression"), "Ctrl+F3")
        act("select_bylocation", "sel_bylocation", "按位置…",
            "按空间位置筛选要素：与参考图层相交 / 包含 / 位于其中 /"
            " 接触 / 距离内",
            vf("select_by_location"))
        act("select_invert", "invert_sel", "反选",
            "把当前选择换成未选中的那些要素 (Ctrl+Shift+U)",
            vf("select_invert"), "Ctrl+Shift+U")
        act("select_clear", "deselect", "清除",
            "取消活动图层的全部选择 (Ctrl+Shift+D)",
            vf("select_clear"), "Ctrl+Shift+D")


        act("copy_features", "copy_features", "复制",
            "复制活动图层（可重复粘贴）(Ctrl+C)",
            vf("copy_layer_to_clipboard"), "Ctrl+C")
        act("cut_features", "cut_features", "剪切",
            "剪切活动图层：从图层树移除，粘贴时恢复 (Ctrl+X)",
            vf("cut_layer_to_clipboard"), "Ctrl+X")
        act("paste_features", "paste_features", "粘贴",
            "把剪贴板里的图层添加到图层树 (Ctrl+V)",
            vf("paste_layer_from_clipboard"), "Ctrl+V")
        act("copy_path", "copy_path", "复制路径",
            "复制活动图层数据源路径到系统剪贴板",
            vf("copy_layer_path"))

        act("copy_feat", "copy_features", "复制",
            "复制选中的要素（可粘贴到当前图层或指定图层）",
            vf("copy_selected_features"))
        act("cut_feat", "cut_features", "剪切",
            "剪切选中的要素：从原图层移除，可粘贴到其它图层",
            vf("copy_selected_features", cut=True))
        act("paste_feat", "paste_features", "粘贴",
            "把剪贴板里的要素粘贴到当前图层",
            vf("paste_features_to_layer"))
        act("paste_feat_to", "paste_special", "选择性粘贴",
            "把剪贴板里的要素粘贴到指定的图层（弹出对话框；"
            "几何类型不同的图层会显示为禁用）",
            vf("paste_features_special"))

        act("locate_xy", "locate", "定位到",
            "输入 XY 坐标，视图平移到该点（支持工程坐标或经纬度）",
            vf("locate_xy"))
        act("zoom_visible", "zoom_layer", "缩放至可见图层范围",
            "缩放到当前地图视图中所有可见图层的合并范围；没有可见图层时不可用",
            vf("zoom_visible"))

        act("filter_active", "filter", "过滤要素…",
            "用 SQL WHERE 条件过滤活动图层的要素",
            vf("filter_active_layer"))
        act("label_settings", "label", "标注设置…",
            "独立设置活动图层的标注字段与样式",
            vf("open_label_settings"))
        act("toggle_labels", "label", "切换标注",
            "开 / 关活动图层的标注显示",
            vf("toggle_labels"), None, checkable=True)
        act("export_vector", "export", "导出矢量图层…",
            "用对话框导出活动矢量图层（可选格式/CRS/字段）",
            vf("export_vector_layer"))
        act("export_raster", "export_raster", "导出栅格图层…",
            "把活动栅格图层另存为 GeoTIFF 等格式",
            vf("export_raster_layer"))
        act("remove_layer", "remove", "移除图层", "从工程中移除活动图层",
            vf("remove_current_layer"))
        act("new_group_action", "new_group", "新建组",
            "在图层树中新建一个分组",
            vf("new_group"))

        act("analysis", "overlay", "空间分析…",
            "矢量空间分析：缓冲 / 相交 / 联合 / 擦除 / 裁剪 / 融合",
            vf("open_analysis"))
        act("analysis_buffer", "buffer", "缓冲…",
            "按距离外扩或收缩要素",
            vf("open_analysis", "buffer"))
        act("analysis_intersect", "overlay", "相交…",
            "保留两层相交的部分（两层属性都带出来）",
            vf("open_analysis", "intersect"))
        act("analysis_union", "overlay", "联合…",
            "两层充分剖分后输出全部碎块",
            vf("open_analysis", "union"))
        act("analysis_clip", "clip", "裁剪…",
            "用叠加图层裁剪输入图层（只保留输入层属性）",
            vf("open_analysis", "clip"))
        act("analysis_dissolve", "dissolve", "融合…",
            "按字段分组做并集",
            vf("open_analysis", "dissolve"))

