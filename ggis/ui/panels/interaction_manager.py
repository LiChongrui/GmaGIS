# -*- coding: utf-8 -*-

from __future__ import annotations
import logging
_log = logging.getLogger("gmagis")


class MapInteractionManager:

    def __init__(self, main_win):
        self._mw = main_win
        self._modes = {}

    def register(self, name, action_name, dock_attr=None):
        self._modes[name] = {"action": action_name, "dock": dock_attr}

    def modes(self):
        return self._modes

    def uncheck_others(self, except_name):
        acts = self._mw.ctx.svc("actions")._acts or {}
        for name, info in self._modes.items():
            if name == except_name:
                continue
            a = acts.get(info["action"])
            if a is not None and a.isCheckable() and a.isChecked():
                try:
                    a.setChecked(False)
                except Exception:
                    _log.exception("silent exception in uncheck_others")

    def has_active_canvas_tool(self):
        for name, info in self._modes.items():
            dock_attr = info.get("dock")
            if not dock_attr:
                continue
            d = getattr(self._mw, dock_attr, None)
            if d is None:
                continue
            fn = getattr(d, "_reassert_front_tool", None)
            if callable(fn) and fn():
                return True
        return False

    def activate(self, name):
        if name not in self._modes:
            return
        self.uncheck_others(name)
        dock_attr = self._modes[name].get("dock")
        if dock_attr:
            d = getattr(self._mw, dock_attr, None)
            if d is not None:
                try:
                    self._mw.ctx.region("dock")._activate_dock(d)
                except Exception:
                    _log.exception("silent exception in activate")
