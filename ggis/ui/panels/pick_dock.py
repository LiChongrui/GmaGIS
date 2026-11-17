# -*- coding: utf-8 -*-

from __future__ import annotations
import logging

import math

from PySide6.QtCore import QTimer

from ggis.ui.framework.docks import GgsDockWidget
from ggis.ui.framework.docks import GgsDockBody
_log = logging.getLogger("gmagis")


def _canvas_crs(canvas):
    try:
        c = canvas.effectiveCrs()
    except Exception:
        _log.exception("silent exception in _canvas_crs")
        return None
    if c is not None and getattr(c, "is_valid", lambda: False)():
        return c
    return None


def _layer_crs(layer):
    try:
        from ggis.core.expr.query import crs_of
        return crs_of(layer)
    except Exception:
        _log.exception("silent exception in _layer_crs")
        return None


def convert_point(src_crs, dst_crs, x, y):
    if src_crs is None or dst_crs is None:
        return (float(x), float(y))
    from ggis.core.crs import crs_transformer
    try:
        tf = crs_transformer(src_crs, dst_crs)
    except Exception:
        _log.exception("silent exception in convert_point")
        return (float(x), float(y))
    if tf is None:
        return (float(x), float(y))
    try:
        tx, ty = tf.transform(float(x), float(y))
    except Exception:
        _log.exception("silent exception in convert_point")
        return (float(x), float(y))
    if not (math.isfinite(tx) and math.isfinite(ty)):
        return (float(x), float(y))
    return (float(tx), float(ty))


def _fmt_coord(v):
    try:
        s = "%.6f" % float(v)
    except Exception:
        _log.exception("silent exception in _fmt_coord")
        return str(v)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


class GgsPickDockBase(GgsDockWidget):

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self._map_provider = None
        self._pick_on = True
        self._is_front = False
        self._canvas = None
        self._tool = None
        self._picked_connected = False
        self._canvas_pt = None
        self._yield_tool = False
        self._wired_canvas = None
        self._pick_btn = None
        self._action_name = None
        self._pick_action = None
        self._nav_bound = False
        self.visibilityChanged.connect(self._on_visibility_changed)
        self.frontChanged.connect(self._on_front_changed)

    def set_map_provider(self, fn):
        self._map_provider = fn

    def _build(self, lay):
        raise NotImplementedError

    def _handle_pick(self, cx, cy):
        raise NotImplementedError

    def _tool_pair(self):
        if self._map_provider is None:
            return None
        try:
            return self._map_provider()
        except Exception:
            _log.exception("silent exception in _tool_pair")
            return None

    def _need_tool(self):
        return bool(self._pick_on or self._canvas_pt is not None)

    def _sync_tool(self):
        if getattr(self, "_yield_tool", False):
            return True
        if not getattr(self, "_is_front", False):
            self._unmount_tool()
            return True
        if not self._need_tool():
            self._unmount_tool()
            return True
        pair = self._tool_pair()
        if pair is None:
            self._unmount_tool()
            return False
        canvas, tool = pair
        self._ensure_canvas_wired(canvas)
        if self._tool is not tool:
            self._unmount_tool()
            self._canvas = canvas
            self._tool = tool
            try:
                tool.picked.connect(self._on_map_picked)
                self._picked_connected = True
            except Exception:
                _log.exception("silent exception in _sync_tool")
                self._picked_connected = False
        if canvas is not None:
            try:
                canvas.setMapTool(tool)
            except Exception:
                _log.exception("silent exception in _sync_tool")
                return False
        self._push_tool_point()
        self._uncheck_others()
        redraw = getattr(self, "_redraw", None)
        if callable(redraw):
            try:
                redraw()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:191", exc_info=True)
        return True

    def _clear_drawn_points(self, tool):
        try:
            tool.clear_display_point()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:203", exc_info=True)

    def _holds_front_tool(self):
        return bool(getattr(self, "_is_front", False)
                    and self._tool is not None)

    def _reassert_front_tool(self):
        if not self._holds_front_tool():
            return False
        try:
            canvas = self._canvas
            if canvas is None:
                return False
            if canvas.mapTool() is not self._tool:
                canvas.setMapTool(self._tool)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:225", exc_info=True)
        return True

    def _unmount_tool(self):
        tool = self._tool
        canvas = self._canvas
        connected = self._picked_connected
        self._tool = None
        self._canvas = None
        self._picked_connected = False
        if tool is not None:
            try:
                self._clear_drawn_points(tool)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:239", exc_info=True)
            if connected:
                try:
                    tool.picked.disconnect(self._on_map_picked)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:244", exc_info=True)
        if canvas is not None and tool is not None:
            try:
                _cur = canvas.mapTool()
            except Exception:
                _log.exception("silent exception in _unmount_tool")
                _cur = None
            if _cur is tool:
                try:
                    canvas.setMapTool(None)
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:254", exc_info=True)

    def _ensure_canvas_wired(self, canvas):
        if canvas is self._wired_canvas:
            return
        if self._wired_canvas is not None:
            try:
                self._wired_canvas.mapToolSet.disconnect(
                    self._on_canvas_tool_changed)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:264", exc_info=True)
        self._wired_canvas = canvas
        if canvas is not None:
            try:
                canvas.mapToolSet.connect(self._on_canvas_tool_changed)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:270", exc_info=True)

    def _on_canvas_tool_changed(self, tool):
        if tool is self._tool:
            return
        if self._tool is not None or self._canvas is not None:
            self._yield_tool = True
            self._unmount_tool()
        act = getattr(self, "_pick_action", None)
        if act is not None and act.isCheckable() and act.isChecked():
            try:
                act.setChecked(False)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:287", exc_info=True)
        elif not getattr(self, "_nav_bound", False):
            self._pick_on = False
        self._reassert_browse()

    def _push_tool_point(self):
        if self._tool is not None and self._canvas_pt is not None:
            try:
                self._tool.set_display_point(*self._canvas_pt)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:297", exc_info=True)

    def _set_canvas_point(self, cx, cy):
        self._canvas_pt = (float(cx), float(cy))
        self._push_tool_point()

    def _clear_canvas_point(self):
        self._canvas_pt = None
        if self._tool is not None:
            try:
                self._tool.clear_display_point()
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:310", exc_info=True)

    def _on_map_picked(self, cx, cy):
        if not self._pick_on:
            return
        try:
            self._handle_pick(float(cx), float(cy))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:322", exc_info=True)

    def _uncheck_others(self):
        mw = getattr(self, "_main_win", None)
        if mw is None:
            return
        mgr = getattr(mw, "_interaction", None)
        if mgr is None:
            return
        try:
            mgr.uncheck_others(self._action_name)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:340", exc_info=True)

    def _on_toggle_pick(self, checked):
        self._bind_nav_pick_tool()
        act = getattr(self, "_pick_action", None)
        if act is not None and act.isCheckable() \
                and act.isChecked() != bool(checked):
            try:
                act.setChecked(bool(checked))
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:358", exc_info=True)

    def _bind_nav_pick_tool(self):
        if getattr(self, "_nav_bound", False):
            return
        mw = getattr(self, "_main_win", None)
        name = getattr(self, "_action_name", None)
        if mw is None or not name:
            return
        acts = mw.ctx.svc("actions")._acts or {}
        act = acts.get(name)
        grp = getattr(mw, "nav_group", None)
        if act is None or grp is None:
            return
        if act not in grp.actions():
            try:
                grp.addAction(act)
            except Exception:
                logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:386", exc_info=True)
        try:
            act.toggled.connect(self._on_pick_action_toggled)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:390", exc_info=True)
        self._pick_action = act
        self._nav_bound = True

    def _on_pick_action_toggled(self, checked):
        self._pick_on = bool(checked)
        if checked:
            self._yield_tool = False
            self._sync_tool()
        else:
            self._unmount_tool()
            self._reassert_browse()
        self._sync_pick_btn_checked()

    def _on_front_changed(self, front):
        self._is_front = bool(front)
        self._bind_nav_pick_tool()
        act = getattr(self, "_pick_action", None)
        if act is not None and act.isCheckable():
            if act.isChecked() != bool(front):
                try:
                    act.setChecked(bool(front))
                except Exception:
                    logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:425", exc_info=True)
        else:
            if front:
                self._yield_tool = False
                self._sync_tool()
            else:
                self._unmount_tool()
                self._reassert_browse()
        self._sync_pick_btn_checked()

    def _reassert_browse(self):
        mw = getattr(self, "_main_win", None)
        if mw is None:
            return
        ms = getattr(mw, "_map_state", None)
        if not callable(ms):
            return
        try:
            QTimer.singleShot(0, lambda: self._safe_nav_check(ms))
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:454", exc_info=True)

    def _safe_nav_check(self, ms):
        try:
            obj = ms()
            if obj is not None:
                obj._ensure_nav_checked()
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:462", exc_info=True)

    def _on_visibility_changed(self, visible):
        self._bind_nav_pick_tool()
        if visible:
            _mw = getattr(self, "_main_win", None)
            _front = False
            if _mw is not None and hasattr(_mw, "ctx"):
                try:
                    _front = bool(_mw.ctx.region("dock")._dock_is_front(self))
                except Exception:
                    _log.exception("silent exception in _on_visibility_changed")
                    _front = False
            if _front:
                self._is_front = True
                self._yield_tool = False
                self._sync_tool()
        else:
            self._unmount_tool()
        self._sync_pick_btn_checked()

    def _sync_pick_btn_checked(self):
        btn = getattr(self, "_pick_btn", None)
        if btn is None:
            return
        act = getattr(self, "_pick_action", None)
        on = bool(act.isChecked()) if act is not None \
            else bool(self._is_front and self._pick_on)
        try:
            btn.blockSignals(True)
            btn.setChecked(on)
            btn.blockSignals(False)
        except Exception:
            logging.getLogger("gmagis").warning("swallowed ggis/ui/pick_dock.py:511", exc_info=True)
