# -*- coding: utf-8 -*-
import logging
import threading
import time

_log = logging.getLogger("gmagis")

_ui_reporter = None
_reporter_lock = threading.Lock()

_THROTTLE_S = 2.0
_last_seen = {}
_last_lock = threading.Lock()


def set_ui_reporter(fn):
    global _ui_reporter
    with _reporter_lock:
        _ui_reporter = fn


def _push_hint(text):
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            return
        if QThread.currentThread() is not app.thread():
            return
        now = time.monotonic()
        with _last_lock:
            t = _last_seen.get(text)
            if t is not None and (now - t) < _THROTTLE_S:
                return
            if len(_last_seen) > 64:
                _last_seen.clear()
            _last_seen[text] = now
        with _reporter_lock:
            fn = _ui_reporter
        if fn is not None:
            fn(text)
    except Exception:
        _log.exception("ggs-exc-note: ui hint push failed")


def exc_note(where):
    _log.exception("ggs-exc-swallow %s", where)
    detail = ""
    try:
        import sys
        exc = sys.exc_info()[1]
        if exc is not None:
            detail = "%s: %s" % (type(exc).__name__, exc)
            detail = detail.strip()
            if len(detail) > 160:
                detail = detail[:159] + "…"
    except Exception:
        _log.debug("ggs-exc-note: exception detail extract failed",
                   exc_info=True)
        detail = ""
    _push_hint("发生异常：%s" % detail if detail else "发生异常")
