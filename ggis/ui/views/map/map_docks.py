# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note
import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from ggis.ui.framework.docks import GgsDockWidget
from ggis.ui.panels.placeholders import GgsPlaceholderDock
from ggis.ui.views.map.map_overview import GgsMapOverviewCanvas
from ggis.ui.views.map.browser import GgsBrowserView

from ggis.core.app import i18n
from ggis.ui.views.map.map_view import MapView

_tr = i18n.tr
_log = logging.getLogger("gmagis")


class MapDockManager:

    def __init__(self, main_window):
        self.mw = main_window
        self._coord_dock = None
        self._profile_dock = None
        self._spectral_dock = None
        self._identify_pick_wired = False
        self.browser_dock = None
        self.browser_view = None
        self.overview_dock = None
        self.overview = None
        self.identify_dock = None
        self.toolbox_dock = None
        self._identify_mode = "visible"

    def build_view_docks(self):
        self.browser_dock = GgsDockWidget(_tr("浏览器"), self.mw)
        self.browser_dock.setObjectName("GgsBrowserDock")
        try:
            bv = GgsBrowserView()
            bv.fileActivated.connect(
                lambda *a: self.mw.ctx.svc("views")._on_view_method("add_uri_layer", *a))
            bv.layerActivated.connect(
                lambda *a: self.mw.ctx.svc("views")._on_view_method("add_uri_layer_from_db", *a))
            self.browser_dock.setWidget(bv)
            self.browser_view = bv
        except Exception as e:
            exc_note("build_view_docks @ ggis/ui/views/map/map_docks.py:90")
            self.browser_dock = GgsPlaceholderDock(
                _tr("浏览器"), _tr("浏览器初始化失败：{}").format(e),
                "folder", self.mw)
            self.browser_dock.setObjectName("GgsBrowserDock")

        self.overview_dock = GgsDockWidget(_tr("鹰眼图"), self.mw)
        self.overview_dock.setObjectName("GgsOverviewDock")
        try:
            ov_host = QWidget()
            ov_lay = QVBoxLayout(ov_host)
            ov_lay.setContentsMargins(0, 0, 0, 0)
            self.overview = GgsMapOverviewCanvas(ov_host, None)
            self.overview.setBackgroundColor(self.mw.ctx.svc("settings_ctl").canvas_bg_color())
            self.overview.enable(True)
            ov_lay.addWidget(self.overview)
            self.overview_dock.setWidget(ov_host)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:109", exc_info=True)

        try:
            from ggis.ui.panels.identify import GgsIdentifyPanel
            self.identify_dock = GgsIdentifyPanel(None, self.mw)
            self.identify_dock.zoomRequested.connect(
                lambda *a: self.mw._forward_to_map_view("_zoom_to_feature", *a))
            self.identify_dock.modeChanged.connect(self._on_identify_mode)
            self.identify_dock.visibilityChanged.connect(
                self._on_identify_dock_activated)
            self.identify_dock.frontChanged.connect(
                self._on_identify_front_changed)
            self.identify_dock.pickToggled.connect(
                self._on_identify_pick_toggled)
        except Exception as e:
            exc_note("build_view_docks @ ggis/ui/views/map/map_docks.py:135")
            self.identify_dock = GgsPlaceholderDock(
                _tr("识别结果"), _tr("识别面板初始化失败：{}").format(e),
                "identify", self.mw)
        self.identify_dock.setObjectName("GgsIdentifyDock")
        self._identify_mode = "visible"


        try:
            from ggis.ui.panels.analysis import GgsToolboxPanel
            self.toolbox_dock = GgsToolboxPanel(self.mw)
            self.toolbox_dock.algorithmTriggered.connect(
                lambda op: self.mw.ctx.svc("views")._on_view_method("open_analysis", op))
        except Exception as e:
            exc_note("build_view_docks @ ggis/ui/views/map/map_docks.py:158")
            self.toolbox_dock = GgsPlaceholderDock(
                _tr("处理工具箱"), _tr("工具箱初始化失败：{}").format(e),
                "tool", self.mw)
        self.toolbox_dock.setObjectName("GgsToolboxDock")

    def _ensure_coord_dock(self):
        dock = getattr(self, "_coord_dock", None)
        if dock is not None:
            return dock
        from ggis.ui.panels.coord_transform_dock import GgsCoordinateTransformDock

        def _coord_map_provider():
            mv = None
            try:
                mv = self.mw.current_map_view()
            except Exception:
                exc_note("_coord_map_provider @ ggis/ui/views/map/map_docks.py:192")
                mv = None
            if mv is None:
                return None
            cv = getattr(mv, "canvas", None)
            if cv is None:
                return None
            t = getattr(mv, "_tools", {}).get("coord_add")
            if t is None:
                return None
            return (cv, t)

        def _coord_proj_crs():
            cv = self.mw.canvas
            if cv is None:
                return None
            try:
                c = cv.effectiveCrs()
                if c is not None and c.is_valid():
                    return c.authid()
            except Exception:
                exc_note("_coord_proj_crs @ ggis/ui/views/map/map_docks.py:228")
                return None
            return None

        dock = GgsCoordinateTransformDock(_tr("坐标转换"), self.mw)
        dock.set_map_provider(_coord_map_provider)
        dock.set_proj_crs_provider(_coord_proj_crs)
        try:
            _proj = self.mw.ctx.region("title")._canvas_crs_authid()
            dock.configure_crs(_proj, self.mw.ctx.region("title")._coord_layer_crs())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:246", exc_info=True)
        self.mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        try:
            _anchor = (list(getattr(self.mw, "_right_docks", None) or [])
                       or [None])[0]
            if _anchor is not None and _anchor is not dock:
                self.mw.tabifyDockWidget(_anchor, dock)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:257", exc_info=True)
        self._coord_dock = dock
        try:
            dock.visibilityChanged.connect(self._sync_coord_action)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:263", exc_info=True)
        self.mw.ctx.region("dock")._register_right_dock(dock)
        dock.setObjectName("GgsCoordinateTransformDock")
        dock.hide()
        return dock

    def _sync_coord_action(self, _vis=None):
        d = getattr(self, "_coord_dock", None)
        if d is None:
            return
        try:
            vis = bool(self.mw.ctx.region("dock")._dock_is_front(d))
        except Exception:
            exc_note("_sync_coord_action @ ggis/ui/views/map/map_docks.py:288")
            return
        a = self.mw.ctx.svc("actions")._acts.get("coord_transform")
        if a is not None and a.isCheckable():
            try:
                if a.isChecked() != vis:
                    a.setChecked(vis)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:300", exc_info=True)

    def toggle_coord_transform(self):
        _existed = getattr(self, "_coord_dock", None) is not None
        dock = self._ensure_coord_dock()
        if dock is None:
            return None
        if not _existed:
            self.mw._interaction.activate("coord_transform")
            self._sync_coord_action()
            return dock
        self.mw.ctx.region("dock")._toggle_dock_action(dock, "coord_transform")
        return dock

    def _activate_coord_transform(self):
        dock = self._ensure_coord_dock()
        if dock is not None:
            self.mw.ctx.region("dock")._activate_dock(dock)

    def open_coord_transform(self, x=None, y=None):
        dock = self._ensure_coord_dock()
        if dock is None:
            return None
        try:
            proj = self.mw.ctx.region("title")._canvas_crs_authid()
            if proj:
                dock.configure_crs(proj, self.mw.ctx.region("title")._coord_layer_crs())
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:353", exc_info=True)
        if x is not None and y is not None:
            try:
                dock._add_input(float(x), float(y))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:358", exc_info=True)
        self.mw.ctx.region("dock")._activate_dock(dock)
        self._sync_coord_action()
        return dock

    def _sync_coord_button(self):
        a = self.mw.ctx.svc("actions")._acts.get("coord_transform")
        if a is None:
            return
        has = bool(self.mw.ctx.region("title")._canvas_crs_authid())
        try:
            a.setEnabled(has)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:377", exc_info=True)

    def _lazy_panel_docks(self):
        return (
            ("raster_profile", self._ensure_profile_dock),
            ("spectral_profile", self._ensure_spectral_dock),
            ("coord_transform", self._ensure_coord_dock),
        )

    def _ensure_lazy_panel_docks(self):
        for _name, fn in self._lazy_panel_docks():
            try:
                fn()
            except Exception:
                _log.exception("惰性面板 %s 常驻化失败", _name)

    def _notify_profile_docks_layer_changed(self):
        d = getattr(self, "_profile_dock", None)
        if d is not None:
            try:
                if d.isVisible():
                    d.on_current_layer_changed()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:423", exc_info=True)

    def _ensure_profile_dock(self):
        dock = getattr(self, "_profile_dock", None)
        if dock is not None:
            return dock
        from ggis.ui.views.map.dialogs.raster_profile import GgsProfileDock

        def _profile_map_provider():
            mv = None
            try:
                mv = self.mw.current_map_view()
            except Exception:
                exc_note("_profile_map_provider @ ggis/ui/views/map/map_docks.py:435")
                mv = None
            if mv is None:
                return None
            cv = getattr(mv, "canvas", None)
            if cv is None:
                return None
            t = getattr(mv, "_tools", {}).get("raster_profile")
            return (cv, t)

        def _profile_layer_provider():
            lyr = None
            try:
                lyr = self.mw._forward_to_map_view("_current_layer")
            except Exception:
                exc_note("_profile_layer_provider @ ggis/ui/views/map/map_docks.py:452")
                lyr = None
            if lyr is not None and lyr.is_raster() and lyr.is_valid():
                return lyr
            return None

        def _profile_centre_provider():
            mv = self.mw.current_map_view()
            cv = getattr(mv, "canvas", None) if mv is not None else None
            if cv is None:
                return None
            try:
                e = cv.extent()
                cx, cy = e.center()
            except Exception:
                exc_note("_profile_centre_provider @ ggis/ui/views/map/map_docks.py:466")
                return None
            return (float(cx), float(cy))

        def _profile_tree_provider():
            mv = None
            try:
                mv = self.mw.current_map_view()
            except Exception:
                exc_note("_profile_tree_provider @ ggis/ui/views/map/map_docks.py:474")
                mv = None
            if mv is None:
                return None
            try:
                return mv.layer_tree()
            except Exception:
                exc_note("_profile_tree_provider @ ggis/ui/views/map/map_docks.py:480")
                return None

        dock = GgsProfileDock(_tr("剖面曲线"), self.mw)
        dock.set_map_provider(_profile_map_provider)
        dock.set_layer_provider(_profile_layer_provider)
        dock.set_centre_provider(_profile_centre_provider)
        dock.set_layer_tree_provider(_profile_tree_provider)
        self.mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        try:
            _anchor = (list(getattr(self.mw, "_right_docks", None) or [])
                       or [None])[0]
            if _anchor is not None and _anchor is not dock:
                self.mw.tabifyDockWidget(_anchor, dock)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:499", exc_info=True)
        self._profile_dock = dock
        try:
            dock.visibilityChanged.connect(self._sync_profile_action)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:504", exc_info=True)
        self.mw.ctx.region("dock")._register_right_dock(dock)
        dock.setObjectName("GgsProfileDock")
        dock.hide()
        return dock

    def _sync_profile_action(self, _vis=None):
        d = getattr(self, "_profile_dock", None)
        if d is None:
            return
        try:
            vis = bool(self.mw.ctx.region("dock")._dock_is_front(d))
        except Exception:
            exc_note("_sync_profile_action @ ggis/ui/views/map/map_docks.py:515")
            return
        a = self.mw.ctx.svc("actions")._acts.get("raster_profile")
        if a is not None and a.isCheckable():
            try:
                if a.isChecked() != vis:
                    a.setChecked(vis)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:527", exc_info=True)

    def toggle_profile_dock(self):
        existed = getattr(self, "_profile_dock", None) is not None
        dock = self._ensure_profile_dock()
        if dock is None:
            return None
        if not existed:
            self.mw._interaction.activate("raster_profile")
            self._sync_profile_action()
            return dock
        self.mw.ctx.region("dock")._toggle_dock_action(dock, "raster_profile")
        return dock

    def open_profile_dock(self, layer=None, x=None, y=None):
        dock = self._ensure_profile_dock()
        if dock is None:
            return None
        if layer is not None:
            dock.set_layer(layer)
        if x is not None and y is not None:
            dock.set_point(x, y)
        self.mw.ctx.region("dock")._activate_dock(dock)
        self._sync_profile_action()
        return dock

    def _ensure_spectral_dock(self):
        dock = getattr(self, "_spectral_dock", None)
        if dock is not None:
            return dock
        from ggis.ui.panels.spectral_profile_dock import GgsSpectralDock

        def _sp_map_provider():
            mv = self.mw.current_map_view()
            if mv is None:
                return None
            cv = getattr(mv, "canvas", None)
            if cv is None:
                return None
            t = getattr(mv, "_tools", {}).get("spectral")
            return (cv, t)

        def _sp_layers_provider():
            layers = []
            mv = self.mw.current_map_view()
            if mv is not None:
                try:
                    proj = mv._shared_project()
                    layers = list(proj.layers() or [])
                except Exception:
                    exc_note("_sp_layers_provider @ ggis/ui/views/map/map_docks.py:591")
                    layers = []
            if not layers:
                try:
                    proj = self.mw.ctx.project
                    layers = list(proj.layers() or [])
                except Exception:
                    exc_note("_sp_layers_provider @ ggis/ui/views/map/map_docks.py:598")
                    layers = []
            return [l for l in layers
                    if l is not None and l.is_raster() and l.is_valid()]

        def _sp_layer_provider():
            lyr = None
            try:
                lyr = self.mw._forward_to_map_view("_current_layer")
            except Exception:
                exc_note("_sp_layer_provider @ ggis/ui/views/map/map_docks.py:607")
                lyr = None
            if lyr is not None and lyr.is_raster() and lyr.is_valid():
                return lyr
            return None

        def _sp_centre_provider():
            mv = self.mw.current_map_view()
            cv = getattr(mv, "canvas", None) if mv is not None else None
            if cv is None:
                return None
            try:
                e = cv.extent()
                cx, cy = e.center()
            except Exception:
                exc_note("_sp_centre_provider @ ggis/ui/views/map/map_docks.py:621")
                return None
            return (float(cx), float(cy))

        def _sp_tree_provider():
            mv = self.mw.current_map_view()
            if mv is None:
                return None
            try:
                return mv.layer_tree()
            except Exception:
                exc_note("_sp_tree_provider @ ggis/ui/views/map/map_docks.py:632")
                return None

        dock = GgsSpectralDock(_tr("光谱曲线"), self.mw)
        dock.set_map_provider(_sp_map_provider)
        dock.set_layers_provider(_sp_layers_provider)
        dock.set_layer_provider(_sp_layer_provider)
        dock.set_layer_tree_provider(_sp_tree_provider)
        dock.set_centre_provider(_sp_centre_provider)
        self.mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        try:
            _anchor = (list(getattr(self.mw, "_right_docks", None) or [])
                       or [None])[0]
            if _anchor is not None and _anchor is not dock:
                self.mw.tabifyDockWidget(_anchor, dock)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:655", exc_info=True)
        self._spectral_dock = dock
        try:
            dock.visibilityChanged.connect(self._sync_spectral_action)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:660", exc_info=True)
        self.mw.ctx.region("dock")._register_right_dock(dock)
        dock.setObjectName("GgsSpectralDock")
        dock.hide()
        return dock

    def _sync_spectral_action(self, _vis=None):
        d = getattr(self, "_spectral_dock", None)
        if d is None:
            return
        try:
            vis = bool(self.mw.ctx.region("dock")._dock_is_front(d))
        except Exception:
            exc_note("_sync_spectral_action @ ggis/ui/views/map/map_docks.py:670")
            return
        a = self.mw.ctx.svc("actions")._acts.get("spectral_profile")
        if a is not None and a.isCheckable():
            try:
                if a.isChecked() != vis:
                    a.setChecked(vis)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:683", exc_info=True)

    def _seed_spectral_dock(self, dock):
        try:
            mv = self.mw.current_map_view()
            cv = getattr(mv, "canvas", None)
            if cv is not None:
                e = cv.extent()
                cx, cy = e.center()
                dock.set_point(float(cx), float(cy))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:698", exc_info=True)

    def toggle_spectral_dock(self):
        existed = getattr(self, "_spectral_dock", None) is not None
        dock = self._ensure_spectral_dock()
        if dock is None:
            return None
        if not existed:
            self._seed_spectral_dock(dock)
            self.mw._interaction.activate("spectral_profile")
            self._sync_spectral_action()
            return dock
        self.mw.ctx.region("dock")._toggle_dock_action(dock, "spectral_profile")
        return dock

    def open_spectral_dock(self, x=None, y=None):
        existed = getattr(self, "_spectral_dock", None) is not None
        dock = self._ensure_spectral_dock()
        if dock is None:
            return None
        if not existed:
            self._seed_spectral_dock(dock)
        if x is not None and y is not None:
            dock.set_point(float(x), float(y))
        self.mw.ctx.region("dock")._activate_dock(dock)
        self._sync_spectral_action()
        return dock

    def _sync_identify_action(self, _vis=None):
        a = self.mw.ctx.svc("actions")._acts.get("identify")
        d = self.identify_dock
        if a is None or d is None or not a.isCheckable():
            return
        try:
            vis = bool(d.isVisible())
        except Exception:
            exc_note("_sync_identify_action @ ggis/ui/views/map/map_docks.py:741")
            return
        try:
            if not vis and a.isChecked():
                a.setChecked(False)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:752", exc_info=True)

    def _on_identify_mode(self, mode):
        try:
            self._identify_mode = mode
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:765", exc_info=True)
        vh = getattr(self.mw, "view_host", None)
        if vh is None:
            return
        views = []
        try:
            views = vh.findChildren(MapView)
        except Exception:
            exc_note("_on_identify_mode @ ggis/ui/views/map/map_docks.py:767")
            views = []
        for v in views:
            try:
                v._identify_mode = mode
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:778", exc_info=True)

    def _on_identify_dock_activated(self, visible):
        if getattr(self.mw, "_booting", False):
            return
        self._ensure_identify_pick_wired()
        a = self.mw.ctx.svc("actions")._acts.get("identify")
        d = self.identify_dock
        if d is None:
            return
        if visible:
            if not self.mw.ctx.region("dock")._dock_is_front(d):
                return
            if getattr(self.mw, "_identifying_from_dock", False):
                return
            self.mw._identifying_from_dock = True
            try:
                self.mw.ctx.svc("views")._on_view_method("set_map_tool", "identify")
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:820", exc_info=True)
            finally:
                self.mw._identifying_from_dock = False
        else:
            if a is not None and a.isCheckable() and a.isChecked():
                try:
                    a.setChecked(False)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:828", exc_info=True)

    def _on_identify_front_changed(self, front):
        if getattr(self.mw, "_booting", False):
            return
        self._ensure_identify_pick_wired()
        if not front:
            a = self.mw.ctx.svc("actions")._acts.get("identify")
            if a is not None and a.isCheckable() and a.isChecked():
                try:
                    a.setChecked(False)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:851", exc_info=True)
            self._release_identify_tool()
            return
        if getattr(self.mw, "_identifying_from_dock", False):
            return
        self.mw._identifying_from_dock = True
        try:
            self.mw.ctx.svc("views")._on_view_method("set_map_tool", "identify")
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:865", exc_info=True)
        finally:
            self.mw._identifying_from_dock = False
        mgr = getattr(self.mw, "_interaction", None)
        if mgr is not None:
            try:
                mgr.uncheck_others("identify")
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:876", exc_info=True)

    def _release_identify_tool(self):
        try:
            cv = self.mw.canvas
        except Exception:
            exc_note("_release_identify_tool @ ggis/ui/views/map/map_docks.py:886")
            return
        if cv is None:
            return
        try:
            cur = cv.mapTool()
        except Exception:
            exc_note("_release_identify_tool @ ggis/ui/views/map/map_docks.py:892")
            return
        if cur is None:
            return
        try:
            mv = self.mw.current_map_view()
        except Exception:
            exc_note("_release_identify_tool @ ggis/ui/views/map/map_docks.py:898")
            mv = None
        ti = (getattr(mv, "_tools", None) or {}).get("identify")
        if ti is None:
            try:
                if str(getattr(cur, "name", lambda: "")() or "") != "identify":
                    return
            except Exception:
                exc_note("_release_identify_tool @ ggis/ui/views/map/map_docks.py:906")
                return
        elif cur is not ti:
            return
        try:
            cv.setMapTool(None)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:918", exc_info=True)

    def _ensure_identify_pick_wired(self):
        if getattr(self, "_identify_pick_wired", False):
            return
        a = self.mw.ctx.svc("actions")._acts.get("identify")
        d = self.identify_dock
        if a is None or d is None:
            return
        self._identify_pick_wired = True
        try:
            a.toggled.connect(lambda on, dd=d: dd.set_pick_checked(bool(on)))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:936", exc_info=True)

    def _on_identify_pick_toggled(self, on):
        self._ensure_identify_pick_wired()
        if on:
            if getattr(self.mw, "_identifying_from_dock", False):
                return
            self.mw._identifying_from_dock = True
            try:
                self.mw.ctx.svc("views")._on_view_method("set_map_tool", "identify")
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:953", exc_info=True)
            finally:
                self.mw._identifying_from_dock = False
            mgr = getattr(self.mw, "_interaction", None)
            if mgr is not None:
                try:
                    mgr.uncheck_others("identify")
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:962", exc_info=True)
            return
        a = self.mw.ctx.svc("actions")._acts.get("identify")
        if a is not None and a.isCheckable() and a.isChecked():
            try:
                a.setChecked(False)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/views/map_docks.py:969", exc_info=True)
