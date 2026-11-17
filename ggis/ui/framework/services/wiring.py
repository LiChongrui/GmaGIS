# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
from dataclasses import dataclass

_log = logging.getLogger("gmagis")


def _repr(obj, limit=110):
    try:
        s = repr(obj)
    except Exception:
        exc_note("_repr @ ggis/ui/framework/services/wiring.py:29")
        s = "<unrepresentable %s>" % type(obj).__name__
    return s[:limit]


@dataclass(frozen=True)
class Wire:
    group: str
    signal: str
    slot: str
    rebindable: bool
    action: str = "connect"


class Wiring:

    def __init__(self, ctx):
        self.ctx = ctx
        self._wires = []
        self._live = []
        self.canvas = None
        self.extent_handler = None

    def connect(self, signal, slot, group="misc", rebindable=False):
        sig_r, slot_r = _repr(signal), _repr(slot)
        try:
            signal.connect(slot)
        except Exception:
            _log.exception("信号接线失败 [%s] %s -> %s", group, sig_r, slot_r)
            return False
        self._wires.append(Wire(group, sig_r, slot_r, bool(rebindable), "connect"))
        self._live.append((signal, slot))
        return True

    def disconnect(self, signal, slot, group="misc"):
        sig_r, slot_r = _repr(signal), _repr(slot)
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            exc_note("disconnect @ ggis/ui/framework/services/wiring.py:74")
            pass
        except Exception:
            _log.exception("信号断开失败 [%s] %s -> %s", group, sig_r, slot_r)
            return False
        self._wires.append(Wire(group, sig_r, slot_r, False, "disconnect"))
        if (signal, slot) in self._live:
            self._live.remove((signal, slot))
        return True

    def disconnect_all(self):
        n = 0
        for signal, slot in reversed(self._live):
            try:
                signal.disconnect(slot)
                n += 1
            except Exception:
                _log.debug("disconnect_all: wire already dead",
                           exc_info=True)
        self._live.clear()
        self._wires.append(Wire("shutdown", "disconnect_all", "", False,
                                "disconnect"))
        return n

    def audit(self):
        problems = []
        seen = {}
        for w in self._wires:
            if w.action != "connect":
                continue
            key = (w.group, w.signal, w.slot)
            if key in seen:
                problems.append("重复接线: %s | %s -> %s" % key)
            seen[key] = True
        groups_rebind = {w.group for w in self._wires if w.rebindable}
        groups_disconnected = {w.group for w in self._wires
                               if w.action == "disconnect"}
        for g in sorted(groups_rebind - groups_disconnected):
            problems.append("可重绑组 %s 没有任何断开记录" % g)
        return problems

    def summary(self):
        n_conn = sum(1 for w in self._wires if w.action == "connect")
        n_disc = sum(1 for w in self._wires if w.action == "disconnect")
        by_group = {}
        for w in self._wires:
            if w.action == "connect":
                by_group[w.group] = by_group.get(w.group, 0) + 1
        return {"connect": n_conn, "disconnect": n_disc,
                "groups": dict(sorted(by_group.items()))}

    @property
    def wires(self):
        return tuple(self._wires)
