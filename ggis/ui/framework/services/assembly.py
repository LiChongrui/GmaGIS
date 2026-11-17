# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication

_log = logging.getLogger("gmagis")


class AssemblyOrderError(RuntimeError):

    def __init__(self, stage, missing):
        super().__init__(
            "启动阶段顺序错误：{0} 依赖未满足 {1}".format(stage, missing))
        self.stage = stage
        self.missing = missing


class Stage:

    name = "stage"
    boot_label = ""
    requires = ()
    fatal = False

    def run(self, ctx):
        raise NotImplementedError


class WindowShellStage(Stage):
    name = "WindowShell"
    boot_label = "正在构建界面…"
    requires = ()

    def run(self, ctx):
        mw = ctx.mw
        mw.setObjectName("GgsMainWindow")
        mw.setMinimumSize(QSize(900, 600))
        mw.setDockNestingEnabled(False)
        mw.setWindowFlags(mw.windowFlags() | Qt.WindowType.FramelessWindowHint)
        mw.setContentsMargins(5, 0, 5, 0)


class ServiceStage(Stage):
    name = "Service"
    boot_label = "正在构建界面…"
    requires = ("WindowShell",)

    def run(self, ctx):
        mw = ctx.mw
        ctx.svc("actions")._acts = {}
        ctx.svc("actions")._icon_actions = []
        ctx.svc("actions")._placeholders = set()
        mw._sub_windows = []
        mw._open_tables = {}
        mw._quitting = False
        mw._cpu_last = None
        mw._active_dock = None
        mw._docks_attached = False
        mw._native_frame_done = False
        mw._init_regions()
        mw._map_dock_state = {}


class ActionStage(Stage):
    name = "Action"
    boot_label = "正在构建界面…"
    requires = ("Service",)

    def run(self, ctx):
        mw = ctx.mw
        ctx.svc("actions").build()
        from ggis.ui.panels.interaction_manager import MapInteractionManager
        from ggis.ui.views.map.map_docks import MapDockManager
        mw._interaction = MapInteractionManager(mw)
        mw._map_dock_mgr = MapDockManager(mw)
        mw._interaction.register("identify", "identify", None)
        mw._interaction.register("coord_transform", "coord_transform",
                                 "_coord_dock")
        mw._interaction.register("raster_profile", "raster_profile",
                                 "_profile_dock")
        mw._interaction.register("spectral_profile", "spectral_profile",
                                 "_spectral_dock")


class DockStage(Stage):
    name = "Dock"
    boot_label = "正在创建面板与功能区…"
    requires = ("Action",)

    def run(self, ctx):
        mw = ctx.mw
        mw.dock_region.build()
        mw.title_region.build()


class RibbonStage(Stage):
    name = "Ribbon"
    boot_label = "正在创建面板与功能区…"
    requires = ("Dock",)

    def run(self, ctx):
        ctx.mw.ribbon_region.build()


class StatusStage(Stage):
    name = "Status"
    boot_label = "正在创建面板与功能区…"
    requires = ("Ribbon",)

    def run(self, ctx):
        ctx.mw.status_region.build()


class SettingsStage(Stage):
    name = "Settings"
    boot_label = "正在应用设置…"
    requires = ("Status",)

    def run(self, ctx):
        ctx.svc("settings_ctl").apply_all()


class ViewHostStage(Stage):
    name = "ViewHost"
    boot_label = "正在准备视图区域…"
    requires = ("Settings",)

    def run(self, ctx):
        mw = ctx.mw
        try:
            from ggis.ui.framework.docks import UriDropFilter
            mw._drop = UriDropFilter(mw)
            mw.installEventFilter(mw._drop)
        except Exception:
            exc_note("run @ ggis/ui/framework/services/assembly.py:208")
            mw._drop = None


class StartupViewStage(Stage):
    name = "StartupView"
    boot_label = "正在准备视图区域…"
    requires = ("ViewHost",)

    def run(self, ctx):
        ctx.mw.view_region.build(tick=ctx.boot)


class WiringStage(Stage):
    name = "Wiring"
    boot_label = "正在恢复窗口布局…"
    requires = ("StartupView",)

    def run(self, ctx):
        mw = ctx.mw
        ctx.svc("actions").verify_placeholders()
        mw.ctx.svc("shell")._update_window_title()

        mw._dirty_shown = None
        try:
            t = QTimer(mw)
            t.setInterval(700)
            ctx.wiring.connect((t.timeout), (mw._update_dirty_ui), "window")
            t.start()
            mw._dirty_poll = t
        except Exception:
            exc_note("run @ ggis/ui/framework/services/assembly.py:244")
            pass
        try:
            mw._update_dirty_ui(force=True)
        except Exception:
            exc_note("run @ ggis/ui/framework/services/assembly.py:248")
            pass

        try:
            ctx.svc("projects")._mark_saved_baseline()
            ctx.project.set_dirty(False)
        except Exception:
            exc_note("run @ ggis/ui/framework/services/assembly.py:257")
            pass

        mw._view_key = None
        mw._mute_view_dirty = False
        mw._applying_project_ui = False
        mw._last_active_view_id = None

        if mw.canvas is not None:
            mw._bind_canvas_signals(mw.canvas)
        ctx.svc("actions").refresh_states()


class RestoreStage(Stage):
    name = "Restore"
    boot_label = "正在恢复窗口布局…"
    requires = ("Wiring",)

    def run(self, ctx):
        ctx.svc("shell")._restore_geometry()


class FinishStage(Stage):
    name = "Finish"
    boot_label = "正在恢复窗口布局…"
    requires = ("Restore",)

    def run(self, ctx):
        mw = ctx.mw
        app = QApplication.instance()
        if app is not None:
            try:
                from ggis.common.styling import icons
                app.setWindowIcon(icons.app_icon())
            except Exception:
                exc_note("run @ ggis/ui/framework/services/assembly.py:298")
                pass
            from ggis.ui.framework.titlebar import (_GripRaiseFilter, _DockActiveFilter,
                                    _PopupRoundFilter)
            mw._combo_round_fix = _PopupRoundFilter()
            app.installEventFilter(mw._combo_round_fix)
            mw._grip_raise_fix = _GripRaiseFilter(mw)
            app.installEventFilter(mw._grip_raise_fix)
            mw._dock_active_fix = _DockActiveFilter(mw)
            app.installEventFilter(mw._dock_active_fix)

        mw._seps = []
        mw._sep_tip = None
        mw._sep_dragging = None
        mw._sep_drag_start = None
        mw.ctx.region("dock")._init_separators()

        try:
            mw._map_dock_mgr._ensure_lazy_panel_docks()
        except Exception:
            _log.exception("惰性面板 DOCK 构造期常驻化失败")


class Assembly:
    STAGES = (
        WindowShellStage,
        ServiceStage,
        ActionStage,
        DockStage,
        RibbonStage,
        StatusStage,
        SettingsStage,
        ViewHostStage,
        StartupViewStage,
        WiringStage,
        RestoreStage,
        FinishStage,
    )

    def __init__(self, ctx):
        self.ctx = ctx

    def run(self):
        done = set()
        for cls in self.STAGES:
            st = cls()
            missing = set(st.requires) - done
            if missing:
                raise AssemblyOrderError(st.name, sorted(missing))
            if st.boot_label:
                try:
                    self.ctx.boot(st.boot_label)
                except Exception:
                    exc_note("run @ ggis/ui/framework/services/assembly.py:356")
                    pass
            st.run(self.ctx)
            done.add(st.name)
        try:
            self.ctx.boot("就绪")
        except Exception:
            exc_note("run @ ggis/ui/framework/services/assembly.py:363")
            pass
