# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note


from ._hostdeps import _tr, _log, GgsMsgBox, GgsMapCanvas, Qt, QWidget
from ._hostdeps import LEVEL_INFO, LEVEL_WARN, DOCK_W
from ggis.core.app import settings


class ViewShellFeatureMixin:




    def _current_map_view(self):
        vh = getattr(self, "view_host", None)
        if vh is not None:
            cur = vh.current_view()
            if cur is not None and str(getattr(cur, "kind", "")) == "map":
                return cur
            for _v in vh.views():
                if str(getattr(_v, "kind", "")) == "map":
                    return _v
        return None

    def current_map_view(self):
        vh = getattr(self, "view_host", None)
        if vh is not None:
            cur = vh.current_view()
            if cur is not None and str(getattr(cur, "kind", "")) == "map":
                return cur
        return None

    def _forward_to_map_view(self, method, *args):
        v = self.current_map_view()
        if v is None:
            return None
        fn = getattr(v, str(method), None)
        if fn is None:
            return None
        return fn(*args)

    @property
    def _view_extent_handler(self):
        v = self.current_map_view()
        if v is None:
            return None
        return getattr(v, "_extent_handler", None)

    def current_layer_tree(self):
        v = self.current_map_view()
        if v is None:
            return None
        try:
            return v.layer_tree()
        except Exception:
            exc_note("current_layer_tree @ ggis/ui/features/viewshell.py:146")
            return None

    def current_view_crs(self):
        v = self.current_map_view()
        if v is not None:
            try:
                return v.crs()
            except Exception:
                exc_note("current_view_crs @ ggis/ui/features/viewshell.py:161")
                pass
        try:
            return settings.default_crs()
        except Exception:
            exc_note("current_view_crs @ ggis/ui/features/viewshell.py:166")
            return None

    def set_current_view_crs(self, crs):
        v = self.current_map_view()
        if v is None:
            return False
        try:
            return bool(v.set_crs(crs))
        except Exception:
            exc_note("set_current_view_crs @ ggis/ui/features/viewshell.py:176")
            return False

    def current_visible_layers(self):
        v = self.current_map_view()
        if v is None:
            return []
        try:
            return v.visible_layers()
        except Exception:
            exc_note("current_visible_layers @ ggis/ui/features/viewshell.py:186")
            return []

    def _shared_dock_set(self):
        """全局共享 dock 集合（图层树/样式/标注/属性表/浏览器等单例）。
        这些 dock 全局只建一份，关闭视图只解绑/藏起，绝不销毁。"""
        shared = set()
        for name in ("_layer_dock_primary", "styling_dock", "labeling_dock",
                     "attribute_dock"):
            d = getattr(self, name, None)
            if d is not None:
                shared.add(d)
        mgr = getattr(self, "_map_dock_mgr", None)
        if mgr is not None:
            for name in ("browser_dock", "overview_dock", "identify_dock"):
                d = getattr(mgr, name, None)
                if d is not None:
                    shared.add(d)
        return shared

    def _retire_unclaimed_shared_docks(self, shared, closed_vid):
        """共享 dock 不再被任何现存/parked 视图占用时藏起（绝不销毁）。"""
        vh = getattr(self, "view_host", None)
        if vh is None:
            return
        pools = list(vh.views()) + list(getattr(vh, "_parked", {}).values())
        for d in shared:
            claimed = False
            for v in pools:
                if str(getattr(v, "view_id", "")) == closed_vid:
                    continue
                for attr in ("layer_dock", "styling_dock", "labeling_dock",
                             "attribute_dock"):
                    if getattr(v, attr, None) is d:
                        claimed = True
                        break
                if claimed:
                    break
            if not claimed:
                try:
                    d.setVisible(False)
                except Exception:
                    exc_note("_retire_unclaimed_shared_docks @ "
                             "ggis/ui/features/viewshell.py")
                    pass

    def _unregister_view_docks(self, view_id):
        docks = self._view_docks.pop(str(view_id), [])
        shared = self._shared_dock_set()
        for d in docks:
            if d in shared:
                # 全局共享 dock：绝不 deleteLater（旧实现连共享 dock 一并
                # 销毁但全局引用未清 ⇒ 下一个视图绑上死引用、layer_dock 失效）。
                continue
            try:
                w = d.widget()
                if w is not None:
                    try:
                        w.hide()
                    except Exception:
                        exc_note("_unregister_view_docks @ ggis/ui/features/viewshell.py:204")
                        pass
                    d.setWidget(QWidget())
            except Exception:
                exc_note("_unregister_view_docks @ ggis/ui/features/viewshell.py:207")
                pass
            try:
                self.removeDockWidget(d)
            except Exception:
                exc_note("_unregister_view_docks @ ggis/ui/features/viewshell.py:211")
                pass
            try:
                d.deleteLater()
            except Exception:
                exc_note("_unregister_view_docks @ ggis/ui/features/viewshell.py:215")
                pass
        self._retire_unclaimed_shared_docks(shared, str(view_id))
        return docks

    def _control_group_of(self, view):
        fn = getattr(view, "control_group", None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                exc_note("_control_group_of @ ggis/ui/features/viewshell.py:225")
                pass
        return None


    def _register_map_view_layer_dock(self, view):
        if getattr(view, "layer_dock", None) is not None:
            return
        d = getattr(self, "_layer_dock_primary", None)
        first = d is None
        if d is None:
            d = self.ctx.region("dock")._make_layer_dock(getattr(view, "title", None))
            if first:
                self._layer_dock_primary = d
            try:
                self.addDockWidget(Qt.LeftDockWidgetArea, d)
                try:
                    self.ctx.region("dock")._enforce_right_dock_tabs(
                        reset_width=False)
                except Exception:
                    exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:302")
                    pass
                d.hide()
                if self.isVisible():
                    try:
                        d.setFloating(False)
                    except Exception:
                        exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:310")
                        pass
                try:
                    d.resize(int(DOCK_W), int(d.height()))
                    self.resizeDocks([d], [int(DOCK_W)],
                                     Qt.Orientation.Horizontal)
                except Exception:
                    exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:320")
                    pass
            except Exception:
                exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:322")
                pass
        view.layer_dock = d
        try:
            self._register_view_map_docks(view)
        except Exception:
            exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:333")
            pass
        try:
            from PySide6.QtWidgets import QDockWidget
            d.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                          | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                          | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        except Exception:
            exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:345")
            pass
        try:
            d.bind_tree(view._layer_tree)
        except Exception:
            exc_note("_register_map_view_layer_dock @ ggis/ui/features/viewshell.py:354")
            pass

    def _register_view_map_docks(self, view):
        vid = str(getattr(view, "view_id", ""))
        existing = list(self._view_docks.get(vid, []))
        try:
            from PySide6.QtWidgets import QDockWidget
            feats = (QDockWidget.DockWidgetFeature.DockWidgetMovable
                     | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                     | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        except Exception:
            exc_note("_register_view_map_docks @ ggis/ui/features/viewshell.py:385")
            feats = None

        def _claim(global_name, attr_name, obj_name, make, wire,
                   fallback, area, anchor):
            cur = getattr(view, attr_name, None)
            if cur is not None:
                if cur not in existing:
                    existing.append(cur)
                return cur
            g = getattr(self, global_name, None)
            if g is not None:
                setattr(view, attr_name, g)
                return g
            first = not any(
                getattr(v, attr_name, None) is not None
                for v in (self.view_host.views()
                          if getattr(self, "view_host", None) is not None
                          else [])
                if str(getattr(v, "kind", "")) == "map")
            try:
                d = make()
            except Exception:
                exc_note("_claim @ ggis/ui/features/viewshell.py:426")
                d = None
            if d is None:
                try:
                    d = fallback()
                except Exception:
                    exc_note("_claim @ ggis/ui/features/viewshell.py:432")
                    d = None
            if d is not None:
                try:
                    d.setObjectName(obj_name)
                except Exception:
                    exc_note("_claim @ ggis/ui/features/viewshell.py:437")
                    pass
                try:
                    wire(d)
                except Exception:
                    exc_note("_claim @ ggis/ui/features/viewshell.py:441")
                    pass
                if first:
                    setattr(self, global_name, d)
            if d is None:
                return None
            setattr(view, attr_name, d)
            try:
                if not hasattr(view, "_panel_state"):
                    view._panel_state = {}
                if not getattr(d, "_panel_vis_wired", False):
                    d._panel_vis_wired = True
                    _attr = attr_name
                    d.visibilityChanged.connect(
                        lambda vis, _a=_attr:
                            self.ctx.region("dock")._on_panel_visibility(None, _a, vis))
            except Exception:
                exc_note("_claim @ ggis/ui/features/viewshell.py:465")
                pass
            try:
                _proj = self.ctx.project
                if _proj is not None and hasattr(d, "set_project"):
                    d.set_project(_proj)
            except Exception:
                exc_note("_claim @ ggis/ui/features/viewshell.py:476")
                pass
            if getattr(self, global_name, None) is not d:
                if d not in existing:
                    existing.append(d)
            if feats is not None:
                try:
                    self.addDockWidget(area, d)
                    d.setFeatures(feats)
                    d.setFloating(False)
                    d.hide()
                    if area == Qt.RightDockWidgetArea:
                        try:
                            self.resizeDocks([d], [int(DOCK_W)],
                                             Qt.Orientation.Horizontal)
                        except Exception:
                            exc_note("_claim @ ggis/ui/features/viewshell.py:497")
                            pass
                        if anchor is not None:
                            try:
                                self.tabifyDockWidget(anchor, d)
                            except Exception:
                                exc_note("_claim @ ggis/ui/features/viewshell.py:502")
                                pass
                except Exception:
                    exc_note("_claim @ ggis/ui/features/viewshell.py:504")
                    pass
            return d

        def _mk_styling():
            from ..panels.symbology import GgsSymbologyPanel
            return GgsSymbologyPanel(None, self)

        def _wire_styling(d):
            if hasattr(d, "styleChanged"):
                d.styleChanged.connect(
                    lambda layer: self.ctx.svc("views")._on_view_method(
                        "_refresh_layer_appearance", layer))
            if hasattr(d, "activated"):
                d.activated.connect(
                    lambda *a: self._forward_to_map_view(
                        "_sync_symbology_to_active", *a))

        def _fallback_styling():
            from ..panels.placeholders import GgsPlaceholderDock
            return GgsPlaceholderDock(_tr("图层样式"),
                                       _tr("样式面板初始化失败"), "styling", self)

        def _mk_labeling():
            from ..panels.labeling import GgsLabelingPanel
            return GgsLabelingPanel(None, self)

        def _wire_labeling(d):
            if hasattr(d, "labelChanged"):
                d.labelChanged.connect(
                    lambda layer: self._forward_to_map_view(
                        "_on_label_changed", layer))
            if hasattr(d, "activated"):
                d.activated.connect(
                    lambda *a: self._forward_to_map_view(
                        "_sync_labeling_to_active", *a))

        def _fallback_labeling():
            from ..panels.placeholders import GgsPlaceholderDock
            return GgsPlaceholderDock(_tr("标注"),
                                       _tr("标注面板初始化失败"), "labeling", self)

        def _mk_attribute():
            from ..dialogs.attribute_table import GgsAttributeTableDock
            return GgsAttributeTableDock(self)

        def _wire_attribute(d):
            if hasattr(d, "zoomToFeature"):
                d.zoomToFeature.connect(
                    lambda *a: self._forward_to_map_view(
                        "_zoom_to_feature", *a))

        def _fallback_attribute():
            from ..panels.placeholders import GgsPlaceholderDock
            return GgsPlaceholderDock(_tr("属性表"),
                                       _tr("属性表面板初始化失败"), "table", self)

        _right_anchor = (getattr(self, "_right_docks", None) or [None])[0]
        _claim("styling_dock", "styling_dock", "GgsStylingDock",
               _mk_styling, _wire_styling, _fallback_styling,
               Qt.RightDockWidgetArea, _right_anchor)
        _claim("labeling_dock", "labeling_dock", "GgsLabelingDock",
               _mk_labeling, _wire_labeling, _fallback_labeling,
               Qt.RightDockWidgetArea, _right_anchor)
        from ..dialogs.attribute_table import _ATTR_PER_LAYER
        if not _ATTR_PER_LAYER:
            _claim("attribute_dock", "attribute_dock", "GgsAttributeTableDock",
                   _mk_attribute, _wire_attribute, _fallback_attribute,
                   Qt.BottomDockWidgetArea, None)
        self._view_docks[vid] = existing

    def _on_view_tabs_reordered(self, ids):
        vh = getattr(self, "view_host", None)
        if vh is None:
            return
        try:
            vh.reorder(list(ids or []))
        except Exception:
            _log.exception("视图：标签重排失败")

    def _on_view_tab_requested(self, vid):
        vh = getattr(self, "view_host", None)
        if vh is not None:
            try:
                vh.activate(vid)
            except Exception:
                exc_note("_on_view_tab_requested @ ggis/ui/features/viewshell.py:640")
                pass

    def _on_view_tab_close(self, vid):
        vh = getattr(self, "view_host", None)
        if vh is None:
            return
        v = vh.view(vid)
        kind = str(getattr(v, "kind", "") or "")
        if len(getattr(vh, "views", lambda: [])()) <= 1:
            self.show_message(_tr("至少要保留一个视图"), LEVEL_WARN)
            return
        try:
            ans = GgsMsgBox.question(
                self, _tr("关闭视图"),
                _tr("确定要关闭当前视图吗？"),
                GgsMsgBox.StandardButton.Yes | GgsMsgBox.StandardButton.No)
        except Exception:
            exc_note("_on_view_tab_close @ ggis/ui/features/viewshell.py:661")
            ans = GgsMsgBox.StandardButton.Yes
        if ans != GgsMsgBox.StandardButton.Yes:
            return
        try:
            ok = self.ctx.svc("views").close_view(vid)
        except Exception:
            exc_note("_on_view_tab_close @ ggis/ui/features/viewshell.py:667")
            ok = False
        if not ok:
            self.show_message(_tr("至少要保留一个视图"), LEVEL_WARN)
            return
        msg = (_tr("已关闭视图（模型仍保留在工程中）") if kind == "model"
               else _tr("已关闭视图（布局仍保留在工程中）") if kind == "layout"
               else _tr("已关闭地图视图"))
        self.show_message(msg, LEVEL_INFO)

    def _on_view_tab_close_others(self, vid):
        vh = getattr(self, "view_host", None)
        if vh is None:
            return
        try:
            vh.close_others(vid)
        except Exception:
            exc_note("_on_view_tab_close_others @ ggis/ui/features/viewshell.py:687")
            pass

    def _on_view_tab_close_all(self):
        vh = getattr(self, "view_host", None)
        if vh is None:
            return
        try:
            n = len(vh.views())
        except Exception:
            exc_note("_on_view_tab_close_all @ ggis/ui/features/viewshell.py:702")
            return
        if n <= 1:
            self.show_message(_tr("至少要保留一个视图"), LEVEL_WARN)
            return
        try:
            ok = GgsMsgBox.question(
                self, _tr("关闭全部视图"),
                _tr("确定要关闭全部 {0} 个视图吗？").format(n - 1))
        except Exception:
            exc_note("_on_view_tab_close_all @ ggis/ui/features/viewshell.py:711")
            ok = True
        if not ok:
            return
        try:
            vh.close_all()
        except Exception:
            _log.exception("关闭多个视图失败")

    def _on_view_tab_rename(self, vid):
        vh = getattr(self, "view_host", None)
        v = vh.view(vid) if vh is not None else None
        if v is None:
            return
        try:
            from ggis.common.base.dialog import GgsInputDialog
            txt, ok = GgsInputDialog.getText(
                self, _tr("重命名视图"), _tr("名称："), text=v.title)
        except Exception:
            _log.exception("视图：重命名对话框失败")
            return
        if not ok or not str(txt or "").strip():
            return
        try:
            vh.rename_view(vid, txt)
        except Exception:
            exc_note("_on_view_tab_rename @ ggis/ui/features/viewshell.py:750")
            pass
        self.view_region._sync_view_tabs()

    def new_map_view(self, activate=True, ask=True):
        # 薄壳：统一入口。构造/dock 注册/默认面板全部收编在
        # views.open_view("map")，此处不再旁路建视图。
        return self.ctx.svc("views").open_view(
            "map", activate=bool(activate), ask_crs=bool(ask))

    def _update_map_view_parking(self):
        vh = getattr(self, "view_host", None)
        if vh is None:
            return
        maps = [v for v in vh.views()
                if str(getattr(v, "kind", "")) == "map"]
        only_one = len(maps) <= 1
        for v in maps:
            try:
                v.park_on_close = only_one
            except Exception:
                exc_note("_update_map_view_parking @ ggis/ui/features/viewshell.py:948")
                pass



    def _view_open_failed(self, msg):
        text = str(msg or "")
        try:
            GgsMsgBox.warning(self, _tr("视图"), text)
        except Exception:
            exc_note("_view_open_failed @ ggis/ui/features/viewshell.py:977")
            pass
        try:
            import logging as _logging
            _logging.getLogger("gmagis").warning("%s", text)
        except Exception:
            exc_note("_view_open_failed @ ggis/ui/features/viewshell.py:982")
            pass
        return None

