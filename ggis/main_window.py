# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import os
import ctypes

from PySide6.QtCore import QPoint, QTimer, QEvent, QVariantAnimation, \
    QEasingCurve
from PySide6.QtWidgets import QMainWindow, QMenu, QApplication


from ggis.ui.framework.titlebar import TITLE_H

def _argv_project_stem():
    import sys as _sys
    try:
        for _a in _sys.argv[1:]:
            if str(_a).lower().endswith(".ggs") \
                    and os.path.isfile(_a):
                return os.path.splitext(os.path.basename(_a))[0]
    except Exception:
        _log.exception("silent exception in _argv_project_stem")
    return ""

from ggis.ui.framework.statusbar import StatusbarMixin
from ggis.ui.features.viewshell import ViewShellFeatureMixin
from ggis.ui.features.view_ribbon import ViewRibbonFeatureMixin
from ggis.common.styling import icons
from ggis.core.app import i18n
from ggis.core.app import settings as app_settings
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

EDGE = 6
DOCK_W = 300
RIGHT_DOCK_W = DOCK_W

LEVEL_INFO = "Info"
LEVEL_SUCCESS = "Success"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"

LEVEL_WARN = LEVEL_WARNING

_MESSAGE_LEVEL_KEYS = {
    LEVEL_INFO: "show_info_messages",
    LEVEL_SUCCESS: "show_success_messages",
    LEVEL_WARNING: "show_warning_messages",
    LEVEL_CRITICAL: "show_critical_messages",
}


def message_level_visible(level):
    key = _MESSAGE_LEVEL_KEYS.get(str(level))
    if key is None:
        low = str(level).rsplit(".", 1)[-1].strip().lower()
        for name, k in _MESSAGE_LEVEL_KEYS.items():
            if name.lower() == low:
                key = k
                break
    if key is None:
        key = "show_other_messages"
    try:
        return bool(app_settings.get(key, True))
    except Exception:
        _log.exception("silent exception in message_level_visible")
        return True


PLACEHOLDER_ACTIONS = frozenset()


def is_headless():
    try:
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.platformName().strip().lower() in (
            "offscreen", "minimal")
    except Exception:
        _log.exception("silent exception in is_headless")
        return False

class MainWindow(ViewRibbonFeatureMixin, ViewShellFeatureMixin,
                 StatusbarMixin, QMainWindow):

    LEVEL_INFO = LEVEL_INFO
    LEVEL_SUCCESS = LEVEL_SUCCESS
    LEVEL_WARNING = LEVEL_WARNING
    LEVEL_WARN = LEVEL_WARNING
    LEVEL_CRITICAL = LEVEL_CRITICAL

    _HT = {"CLIENT": 1, "CAPTION": 2, "MAXBUTTON": 9,
           "TOP": 12, "TOPLEFT": 13, "TOPRIGHT": 14}

    def __init__(self, boot=None):
        super().__init__()

        self._boot = boot or (lambda *_a, **_k: None)
        from ggis.ui.framework.app_context import AppContext
        from ggis.ui.framework.services.wiring import Wiring
        self.ctx = AppContext(self)
        self.ctx.boot = self._boot
        self.ctx.wiring = self.ctx.register("wiring", Wiring(self.ctx))
        from ggis.ui.framework.services.settings_ctrl import SettingsCtrl
        self.ctx.register("settings_ctl", SettingsCtrl(self.ctx))
        from ggis.ui.framework.services.action_registry import ActionRegistry
        self.ctx.register("actions", ActionRegistry(self.ctx))
        from ggis.ui.framework.services.project_ctrl import ProjectCtrl
        self.ctx.register("projects", ProjectCtrl(self.ctx))
        from ggis.ui.framework.services.view_coord import ViewCoord
        self.ctx.register("views", ViewCoord(self.ctx))
        from ggis.ui.framework.services.window_shell import WindowShell
        self.ctx.register("shell", WindowShell(self.ctx))
        from ggis.ui.framework.services.lifecycle import Lifecycle
        self.ctx.register("lifecycle", Lifecycle(self.ctx))
        self._pending_argv_title = _argv_project_stem()
        self.setWindowTitle(self._pending_argv_title or _tr("未命名工程"))
        try:
            _qapp = QApplication.instance()
            if _qapp is not None:
                _qapp.aboutToQuit.connect(
                    lambda: self.ctx.svc("lifecycle").shutdown())
        except Exception:
            _log.exception("silent exception in __init__")
        from ggis.ui.framework.services.assembly import Assembly
        Assembly(self.ctx).run()
        from ggis.common.util import exc_report
        exc_report.set_ui_reporter(
            lambda text: self.show_message(text, LEVEL_WARNING, 6))
    def _init_regions(self):
        from ggis.ui.framework.regions import (GgsTitleRegion, GgsRibbonRegion,
                              GgsViewRegion, GgsDockRegion,
                              GgsStatusBarRegion)
        self.title_region = GgsTitleRegion(self)
        self.ribbon_region = GgsRibbonRegion(self)
        self.view_region = GgsViewRegion(self)
        self.dock_region = GgsDockRegion(self)
        self.status_region = GgsStatusBarRegion(self)
        self.ctx.regions = {
            "title": self.title_region,
            "ribbon": self.ribbon_region,
            "view": self.view_region,
            "dock": self.dock_region,
            "status": self.status_region,
        }

    def has_layers(self):
        try:
            return bool(self.ctx.svc("views")._on_view_method("has_layers"))
        except Exception:
            _log.exception("silent exception in has_layers")
            return False

    def showEvent(self, e):
        super().showEvent(e)
        if not self._docks_attached:
            self._docks_attached = True
            self.ctx.region("dock")._attach_docks()
            QTimer.singleShot(0, self.ctx.region("dock")._apply_dock_widths)
        self._apply_native_frame()
        self.ctx.region("dock")._layout_edge_grips()
        self._cache_hit_rects()
        if getattr(self, "_default_geometry", None) is None:
            try:
                self._default_geometry = self.normalGeometry()
            except Exception:
                _log.exception("silent exception in showEvent")
        if getattr(self, "_auto_save_timer", None) is None:
            try:
                self._auto_save_timer = QTimer(self)
                self._auto_save_timer.setInterval(1000)
                self._auto_save_timer.timeout.connect(self._auto_save_tick)
                self._auto_save_timer.start()
                self._last_auto_save_ms = None
            except Exception:
                _log.exception("silent exception in showEvent")
        self.ctx.region("dock")._layout_separators()
        self._apply_dwm_round()




    def _bind_canvas_signals(self, cv):
        if cv is None:
            return
        old = getattr(self, "_bound_canvas", None)
        old_handler = getattr(self, "_bound_extent_handler", None)
        if old is cv:
            return

        extent_handler = self._view_extent_handler
        if old is not None:
            try:
                self.ctx.wiring.disconnect((old.scaleChanged), (self._on_scale_changed), "canvas")
                self.ctx.wiring.disconnect((old.xyCoordinates), (self._on_xy_changed), "canvas")
                if old_handler is not None:
                    self.ctx.wiring.disconnect((old.extentChanged), (old_handler), "canvas")
                self.ctx.wiring.disconnect((old.renderStarting), (self._on_render_started), "canvas")
                self.ctx.wiring.disconnect((old.renderComplete), (self._on_render_finished), "canvas")
                self.ctx.wiring.disconnect((old.renderStatus), (self.set_render_status), "canvas")
                self.ctx.wiring.disconnect((old.crsChanged), (self._map_dock_mgr._sync_coord_button), "canvas")
            except Exception:
                _log.exception("silent exception in _bind_canvas_signals")
        try:
            self.ctx.wiring.connect((cv.scaleChanged), (self._on_scale_changed), "canvas", rebindable=True)
            self.ctx.wiring.connect((cv.xyCoordinates), (self._on_xy_changed), "canvas", rebindable=True)
            if extent_handler is not None:
                self.ctx.wiring.connect((cv.extentChanged), (extent_handler), "canvas", rebindable=True)
            self.ctx.wiring.connect((cv.renderStarting), (self._on_render_started), "canvas", rebindable=True)
            self.ctx.wiring.connect((cv.renderComplete), (self._on_render_finished), "canvas", rebindable=True)
            self.ctx.wiring.connect((cv.renderStatus), (self.set_render_status), "canvas", rebindable=True)
            self.ctx.wiring.connect((cv.crsChanged), (self._map_dock_mgr._sync_coord_button), "canvas", rebindable=True)
        except Exception:
                _log.exception("silent exception in _bind_canvas_signals")
        self._bound_canvas = cv
        self._map_dock_mgr._sync_coord_button()

        self._bound_extent_handler = extent_handler


    def createPopupMenu(self):
        m = QMenu(self)
        collapsed = bool(getattr(self.ribbon, "_collapsed", False))
        m.addAction(_tr("展开功能区") if collapsed else _tr("折叠功能区"),
                    lambda: self.ribbon.set_collapsed(not collapsed))
        return m

    def resizeEvent(self, e):
        super().resizeEvent(e)
        tb = getattr(self, "_title_bar", None)
        if tb is not None:
            if tb.width() != self.width():
                tb.setGeometry(0, 0, self.width(), TITLE_H)
            tb.raise_()
            for g in getattr(self, "_grips", ()):
                g.raise_()
        self.ctx.region("dock")._layout_edge_grips()
        self._cache_hit_rects()
        self.ctx.region("dock")._layout_separators()
        self.ctx.region("dock")._reflow_all_measure_panels()
        self.ctx.region("dock")._reposition_msg_bar()
        self.ctx.svc("lifecycle").schedule_state_save()



    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            tb = getattr(self, "_title_bar", None)
            if tb is not None:
                tb.refresh_icons()
            self.ctx.region("dock")._layout_edge_grips()
            self._cache_hit_rects()
            self.ctx.region("dock")._layout_separators()
            self._apply_dwm_round()
        elif event.type() == QEvent.Type.Show:
            self.ctx.region("dock")._layout_separators()


    def moveEvent(self, e):
        super().moveEvent(e)
        self._cache_hit_rects()
        self.ctx.region("dock")._reflow_all_measure_panels()
        self.ctx.svc("lifecycle").schedule_state_save()


    def _cache_hit_rects(self):
        try:
            tb = getattr(self, "_title_bar", None)
            if tb is None:
                self._hit_cache = None
                return
            lay = tb.layout()
            if lay is not None:
                try:
                    lay.activate()
                except Exception:
                    _log.exception("silent exception in _cache_hit_rects")

            def _local(w):
                return w.rect().translated(w.mapTo(self, QPoint(0, 0)))

            inter = []
            for w in ([tb._icon] + list(getattr(tb, "_qat_buttons", []))
                      + [tb._title, tb._search, tb._min, tb._close,
                         tb._auto_save_host]):
                if w is not None and not w.isHidden():
                    r = _local(w)
                    if w is tb._icon:
                        r = r.adjusted(-4, -4, 4, 4)
                    inter.append(r)
            self._hit_cache = {
                "dpr": self.devicePixelRatioF() or 1.0,
                "w": self.width(),
                "title": _local(tb),
                "inter": inter,
                "max": _local(tb._max),
                "maxed": self.isMaximized(),
            }
        except Exception as e:
            _log.exception("silent exception in _cache_hit_rects")
            self._hit_err = repr(e)
            self._hit_cache = None


    def _hit_test_caption(self, px, py):
        c = getattr(self, "_hit_cache", None)
        if c is None:
            return None
        try:
            from ctypes import wintypes
            rc = wintypes.RECT()
            if not ctypes.windll.user32.GetWindowRect(
                    int(self.winId()), ctypes.byref(rc)):
                return None
            dpr = c["dpr"]
            lx = (px - rc.left) / dpr
            ly = (py - rc.top) / dpr
        except Exception:
            _log.exception("silent exception in _hit_test_caption")
            return None
        if not c["title"].contains(int(lx), int(ly)):
            return None
        for r in c["inter"]:
            if r.contains(int(lx), int(ly)):
                return self._HT["CLIENT"]
        if c["max"].contains(int(lx), int(ly)):
            return self._HT["MAXBUTTON"]
        if not c["maxed"]:
            w = c["w"]
            if lx <= 10 and ly <= 10:
                return self._HT["TOPLEFT"]
            if w - lx <= 10 and ly <= 10 and lx <= w - 132:
                return self._HT["TOPRIGHT"]
            if ly <= 5 and 10 < lx < w - 132:
                return self._HT["TOP"]
        return self._HT["CAPTION"]


    def nativeEvent(self, eventType, message):
        if eventType == "windows_generic_MSG":
            try:
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0084:
                    pt = wintypes.POINT()
                    if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                        ht = self._hit_test_caption(pt.x, pt.y)
                        if ht is not None:
                            return True, ht
                elif msg.message == 0x0083 and int(msg.wParam):
                    try:
                        hwnd = int(msg.hWnd)
                        if ctypes.windll.user32.IsZoomed(hwnd):
                            SM_CXFRAME, SM_CXPADDEDBORDER = 32, 92
                            pad = (ctypes.windll.user32.GetSystemMetrics(
                                       SM_CXFRAME)
                                   + ctypes.windll.user32.GetSystemMetrics(
                                       SM_CXPADDEDBORDER))
                            rc = wintypes.RECT.from_address(int(msg.lParam))
                            rc.left += pad
                            rc.top += pad
                            rc.right -= pad
                            rc.bottom -= pad
                    except Exception:
                        _log.exception("silent exception in nativeEvent")
                    return True, 0
                elif msg.message == 0x00A3 and int(msg.wParam) == 2:
                    self._title_bar._toggle_max()
                    return True, 0
                elif msg.message == 0x00A0 and int(msg.wParam) == 9:
                    self._set_max_hot(True)
                    return True, 0
                elif msg.message == 0x02A2:
                    self._set_max_hot(False)
                elif msg.message == 0x00A1 and int(msg.wParam) == 9:
                    return True, 0
                elif msg.message == 0x00A2 and int(msg.wParam) == 9:
                    self._set_max_hot(False)
                    self._title_bar._toggle_max()
                    return True, 0
                elif msg.message == 0x00A0 and int(msg.wParam) == 2:
                    self._set_max_hot(False)
                elif msg.message == 0x00A5 and int(msg.wParam) == 2:
                    lp = int(msg.lParam)
                    cx = ctypes.c_short(lp & 0xFFFF).value
                    cy = ctypes.c_short((lp >> 16) & 0xFFFF).value
                    self._show_sys_menu(cx, cy)
                    return True, 0
                elif msg.message == 0x007B:
                    lp = int(msg.lParam)
                    if lp != -1:
                        cx = ctypes.c_short(lp & 0xFFFF).value
                        cy = ctypes.c_short((lp >> 16) & 0xFFFF).value
                        if self._hit_test_caption(cx, cy) == self._HT["CAPTION"]:
                            self._show_sys_menu(cx, cy)
                            return True, 0
                elif msg.message == 0x0200:
                    tb = getattr(self, "_title_bar", None)
                    if tb is not None and tb._max.property("hot"):
                        pt = wintypes.POINT()
                        if ctypes.windll.user32.GetCursorPos(
                                ctypes.byref(pt)):
                            if self._hit_test_caption(
                                    pt.x, pt.y) != self._HT["MAXBUTTON"]:
                                self._set_max_hot(False)
            except Exception:
                _log.exception("silent exception in nativeEvent")
        return False, 0


    def _set_max_hot(self, hot):
        tb = getattr(self, "_title_bar", None)
        if tb is None:
            return
        b = tb._max
        if b.property("hot") == hot:
            return
        b.setProperty("hot", bool(hot))
        st = b.style()
        st.unpolish(b)
        st.polish(b)
        b.update()
        if hot:
            try:
                from PySide6.QtWidgets import QToolTip
                from PySide6.QtGui import QCursor
                QToolTip.showText(QCursor.pos(), b.toolTip(), b)
            except Exception:
                _log.exception("silent exception in _set_max_hot")


    def _show_sys_menu(self, x, y):
        try:
            hwnd = int(self.winId())
            u32 = ctypes.windll.user32
            u32.GetSystemMenu.argtypes = [ctypes.c_void_p, ctypes.c_int]
            u32.GetSystemMenu.restype = ctypes.c_void_p
            u32.EnableMenuItem.argtypes = [ctypes.c_void_p,
                                           ctypes.c_uint, ctypes.c_uint]
            u32.EnableMenuItem.restype = ctypes.c_int
            u32.TrackPopupMenu.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                           ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_void_p,
                                           ctypes.c_void_p]
            u32.TrackPopupMenu.restype = ctypes.c_int
            u32.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                         ctypes.c_void_p, ctypes.c_void_p]
            u32.PostMessageW.restype = ctypes.c_int
            u32.IsZoomed.argtypes = [ctypes.c_void_p]
            u32.IsIconic.argtypes = [ctypes.c_void_p]
            u32.SetForegroundWindow.argtypes = [ctypes.c_void_p]

            hmenu = u32.GetSystemMenu(ctypes.c_void_p(hwnd), 0)
            if not hmenu:
                return
            MF_BYCOMMAND = 0x00000000
            MF_ENABLED = 0x00000000
            MF_GRAYED = 0x00000001
            SC_RESTORE = 0xF120
            SC_MOVE = 0xF010
            SC_SIZE = 0xF000
            SC_MINIMIZE = 0xF020
            SC_MAXIMIZE = 0xF030
            zoomed = bool(u32.IsZoomed(ctypes.c_void_p(hwnd)))
            iconic = bool(u32.IsIconic(ctypes.c_void_p(hwnd)))

            def _en(sc, on):
                u32.EnableMenuItem(
                    hmenu, int(sc),
                    MF_BYCOMMAND | (MF_ENABLED if on else MF_GRAYED))

            _en(SC_RESTORE, bool(zoomed or iconic))
            _en(SC_MOVE, not (zoomed or iconic))
            _en(SC_SIZE, not (zoomed or iconic))
            _en(SC_MINIMIZE, True)
            _en(SC_MAXIMIZE, not zoomed)
            u32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            cmd = u32.TrackPopupMenu(
                hmenu, 0x0100 | 0x0002, int(x), int(y), 0,
                ctypes.c_void_p(hwnd), None)
            if cmd:
                u32.PostMessageW(ctypes.c_void_p(hwnd), 0x0112,
                                 ctypes.c_void_p(int(cmd)),
                                 ctypes.c_void_p(0))
        except Exception:
            _log.exception("silent exception in _show_sys_menu")

    def reset_window_geometry(self):
        try:
            self.showNormal()
            g = getattr(self, "_default_geometry", None)
            if g is not None and not g.isNull():
                self.setGeometry(g)
            self._cache_hit_rects()
        except Exception:
            _log.exception("silent exception in reset_window_geometry")

    def _auto_save_tick(self):
        try:
            from ggis.core.app import settings as _st
            enabled = bool(_st.get("auto_save_enabled", True))
            if not enabled:
                return
            import time as _time
            now = _time.monotonic()
            last = getattr(self, "_last_auto_save_ms", None)
            if last is None:
                self._last_auto_save_ms = now
                return
            try:
                minutes = max(1, int(
                    _st.get("auto_save_interval_min", 1) or 1))
            except Exception:
                exc_note("_auto_save_tick @ ggis/main_window.py:630")
                minutes = 1
            if now - last < minutes * 60.0:
                return
            self._last_auto_save_ms = now
            pc = self.ctx.svc("projects")
            if not pc.is_dirty() or not pc.project_path():
                return
            pc._write_project(pc.project_path())
        except Exception:
            _log.exception("silent exception in _auto_save_tick")

    def _apply_dwm_round(self):
        try:
            hwnd = int(self.winId())
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), 4)
        except Exception:
            _log.exception("silent exception in _apply_dwm_round")


    def _apply_native_frame(self):
        if self._native_frame_done:
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            getlng = getattr(user32, "GetWindowLongPtrW",
                             user32.GetWindowLongW)
            setlng = getattr(user32, "SetWindowLongPtrW",
                             user32.SetWindowLongW)
            GWL_STYLE = -16
            style = getlng(hwnd, GWL_STYLE)
            setlng(hwnd, GWL_STYLE,
                   style | 0x00C00000
                   | 0x00040000
                   | 0x00080000
                   | 0x00020000
                   | 0x00010000)
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                                0x0002 | 0x0001 | 0x0004 | 0x0020)
            self._native_frame_done = True
        except Exception:
            _log.exception("silent exception in _apply_native_frame")


    def closeEvent(self, e):
        if not self.ctx.svc("lifecycle").on_close(e):
            e.ignore()
            return
        super().closeEvent(e)

    @property
    def canvas(self):
        vh = getattr(self, "view_host", None)
        cur = vh.current_view() if vh is not None else None
        if cur is not None:
            cv = getattr(cur, "canvas", None)
            if cv is not None:
                return cv
        return None


    @property
    def layer_dock(self):
        vh = getattr(self, "view_host", None)
        if vh is not None:
            cur = vh.current_view()
            if cur is not None:
                d = getattr(cur, "layer_dock", None)
                if d is not None:
                    return d
        return getattr(self, "_layer_dock_primary", None)

    _LAYOUT_TAB_TAG = "layout:%d"
    _MODEL_TAB_TAG = "model:%d"


    def _focus_search(self):
        sb = getattr(self, "search_bar", None)
        if sb is None:
            return
        try:
            sb.show()
            sb.raise_()
            sb.edit.setFocus()
            sb.edit.selectAll()
        except Exception:
            _log.exception("silent exception in _focus_search")


    def _search_extra_algorithms(self, query):
        try:
            q = str(query or "").strip()
            if not q or len(q) < 1:
                return []
            from ggis.ui.panels.analysis import GROUPS, HINTS
            from ggis.ui.framework.searchbar import _pinyin_initials
            from ggis.core.analysis import OPS
        except Exception:
            _log.exception("silent exception in _search_extra_algorithms")
            return []
        ql = q.lower()
        out = []
        for _group, ops in GROUPS:
            for op, icon_name in ops:
                spec = OPS.get(op, {})
                try:
                    text = _tr(str(spec.get("label", op)))
                except Exception:
                    _log.exception("silent exception in _search_extra_algorithms")
                    text = str(spec.get("label", op))
                try:
                    hint = _tr(HINTS.get(op, "") or "")
                except Exception:
                    _log.exception("silent exception in _search_extra_algorithms")
                    hint = ""
                tl = text.lower()
                if tl == ql:
                    score = 58
                elif tl.startswith(ql):
                    score = 55
                elif ql in tl:
                    score = 45
                else:
                    py = _pinyin_initials(text)
                    if py and ql == py:
                        score = 50
                    elif py and py.startswith(ql):
                        score = 40
                    elif ql in op.lower():
                        score = 38
                    elif ql in hint.lower():
                        score = 30
                    else:
                        continue
                out.append((score, text, icon_name,
                            (lambda _op=op: self.ctx.svc("views")._on_view_method("open_analysis", _op))))
        out.sort(key=lambda t: (-t[0], t[1]))
        return out


    _SNAP_ACTS_FALLBACK = ("snap_endpoint", "snap_vertex", "snap_intersection",
                          "snap_midpoint", "snap_edge")

    def _unique_view_title(self, base):
        base = str(base or "").strip()
        if not base:
            return base
        names = set()
        try:
            vh = getattr(self, "view_host", None)
            if vh is not None:
                for v in vh.views():
                    names.add(str(getattr(v, "title", "") or ""))
                for pv in (getattr(vh, "_parked", {}) or {}).values():
                    names.add(str(getattr(pv, "title", "") or ""))
        except Exception:
            _log.exception("silent exception in _unique_view_title")
            names = set()
        if base not in names:
            return base
        i = 1
        while i < 10000:
            cand = "{0}{1}".format(base, i)
            if cand not in names:
                return cand
            i += 1
        return base


    def show_message(self, text, level=LEVEL_INFO, duration=4):
        if message_level_visible(level):
            try:
                self.msg_bar.pushMessage("", text, level, duration)
            except Exception:
                _log.exception("silent exception in show_message")
        try:
            self.log_dock.append(text, level=level)
        except Exception:
            _log.exception("silent exception in show_message")


    def log(self, text, level=None):
        try:
            self.log_dock.append(text, level=level)
        except Exception:
            _log.exception("silent exception in log")

        try:
            import logging as _logging
            _logging.getLogger("gmagis").info("%s", text)
        except Exception:
            _log.exception("silent exception in log")


    def _update_dirty_ui(self, force=False):
        try:
            dirty = bool(self.ctx.project.is_dirty())
        except Exception:
            _log.exception("silent exception in _update_dirty_ui")
            return
        if not force and dirty == getattr(self, "_dirty_shown", None):
            return
        old = getattr(self, "_dirty_shown", None)
        self._dirty_shown = dirty
        try:
            a = self.ctx.svc("actions").get("save_project")
        except Exception:
            _log.exception("silent exception in _update_dirty_ui")
            return
        name = "save_modified" if dirty else "save"
        try:
            a.setToolTip(_tr("保存当前工程") + (
                _tr("（有未保存的更改）") if dirty else "") + " (Ctrl+S)")
        except Exception:
            _log.exception("silent exception in _update_dirty_ui")
        self._animate_save_icon(a, old, dirty, name)


    def _animate_save_icon(self, action, old_dirty, new_dirty, name):
        try:
            icons.save_modified_icon(0.0)
        except Exception:
            _log.exception("silent exception in _animate_save_icon")
            self._finish_save_icon(action, name)
            return
        prev = getattr(self, "_dirty_anim", None)
        if prev is not None:
            try:
                prev.finished.disconnect()
                prev.valueChanged.disconnect()
            except Exception:
                exc_note("_animate_save_icon @ ggis/main_window.py:906")
                pass
            try:
                prev.stop()
            except Exception:
                exc_note("_animate_save_icon @ ggis/main_window.py:910")
                pass
        anim = QVariantAnimation(self)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(1.0 if old_dirty else 0.0)
        anim.setEndValue(1.0 if new_dirty else 0.0)

        def _step(v):
            try:
                action.setIcon(icons.save_modified_icon(float(v)))
            except Exception:
                _log.exception("silent exception in _animate_save_icon")

        anim.valueChanged.connect(_step)
        anim.finished.connect(
            lambda: self._finish_save_icon(action, name))
        self._dirty_anim = anim
        anim.start()


    def _finish_save_icon(self, action, name):
        try:
            action.setIcon(icons.icon(name))
            action.setProperty("ggsIconName", name)
        except Exception:
            _log.exception("silent exception in _finish_save_icon")
            return
        try:
            self.ribbon.retheme()
        except Exception:
            _log.exception("silent exception in _finish_save_icon")
        for _r in self._all_ribbons():
            if _r is not self.ribbon:
                try:
                    _r.retheme()
                except Exception:
                    _log.exception("silent exception in _finish_save_icon")


