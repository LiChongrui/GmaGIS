# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import functools
import os
import threading
import traceback

__all__ = [
    "OnUiThreadError", "on_ui_thread", "ui_thread_name",
    "assert_off_ui", "off_ui",
    "set_strict", "strict", "violations", "reset_violations",
    "violation_report", "warned_of",
    "set_ui_mode", "ui_mode",
]

ENV_STRICT = "GGIS_STRICT_THREADS"


class OnUiThreadError(RuntimeError):
    pass


_STRICT = threading.Event()
if os.environ.get(ENV_STRICT, "").strip() not in ("", "0", "false", "False"):
    _STRICT.set()


def set_strict(flag):
    if flag:
        _STRICT.set()
    else:
        _STRICT.clear()


def strict():
    return _STRICT.is_set()


_UI_MODE = threading.Event()


def set_ui_mode(flag):
    if flag:
        _UI_MODE.set()
    else:
        _UI_MODE.clear()


def ui_mode():
    return _UI_MODE.is_set()


def on_ui_thread():
    try:
        from PySide6.QtCore import QCoreApplication, QThread
    except Exception:
        exc_note("on_ui_thread @ ggis/exec/guard.py:129")
        return False
    try:
        app = QCoreApplication.instance()
        if app is None:
            return False
        return QThread.currentThread() is app.thread()
    except Exception:
        exc_note("on_ui_thread @ ggis/exec/guard.py:138")
        return False


def ui_thread_name():
    try:
        from PySide6.QtCore import QThread
        t = QThread.currentThread()
        if t is not None and t.objectName():
            return str(t.objectName())
    except Exception:
        exc_note("ui_thread_name @ ggis/exec/guard.py:149")
        pass
    return threading.current_thread().name


_VIOL_LOCK = threading.Lock()
_VIOLATIONS = []
_WARNED = set()


def violations():
    with _VIOL_LOCK:
        return [v[0] for v in _VIOLATIONS]


def warned_of():
    with _VIOL_LOCK:
        return set(_WARNED)


def reset_violations():
    with _VIOL_LOCK:
        _VIOLATIONS[:] = []
        _WARNED.clear()


def violation_report():
    with _VIOL_LOCK:
        items = list(_VIOLATIONS)
    seen = {}
    for what, tname, stack in items:
        if what not in seen:
            seen[what] = (tname, stack)
    if not seen:
        return "（无违规：没有算法被 UI 线程调用）"
    out = ["UI 线程直接调用算法 %d 处：" % len(seen)]
    for what in sorted(seen):
        tname, stack = seen[what]
        out.append("  · %s   (线程 %s)" % (what, tname))
        for line in (stack or "").strip().splitlines()[-6:]:
            out.append("      " + line.strip())
    return "\n".join(out)


def _warn_once(what):
    with _VIOL_LOCK:
        if what in _WARNED:
            return False
        _WARNED.add(what)
    return True


def assert_off_ui(what=""):
    if not on_ui_thread():
        return
    stack = "".join(traceback.format_stack()[:-1])
    tname = ui_thread_name()
    with _VIOL_LOCK:
        _VIOLATIONS.append((str(what), tname, stack))
    if _STRICT.is_set():
        raise OnUiThreadError(
            "算法 %r 在 UI 线程被调用 —— 界面会在这段计算期间冻住。"
            "请改成 ggis.exec.task.submit(...) 提交到后台；"
            "若这是脚本/验收，设 %s=0 或调 ggis.exec.guard.set_strict(False)。"
            % (what, ENV_STRICT))


def off_ui(what=None):
    def deco(fn):
        label = what or ("%s.%s" % (fn.__module__, fn.__qualname__))

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            assert_off_ui(label)
            return fn(*args, **kwargs)

        wrapper.__off_ui_label__ = label
        return wrapper

    return deco


def offloaded(what=None, kind="cpu", name="", protect=False):
    def deco(fn):
        label = what or ("%s.%s" % (fn.__module__, fn.__qualname__))
        tname = name or getattr(fn, "__name__", "task")

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            assert_off_ui(label)
            if not (ui_mode() and on_ui_thread()):
                return fn(*args, **kwargs)
            from .task import submit_meta
            return submit_meta(fn, args, kwargs, kind=kind, name=tname,
                               protect=protect)

        wrapper.__off_ui_label__ = label
        wrapper.__offloaded__ = True
        return wrapper

    return deco
