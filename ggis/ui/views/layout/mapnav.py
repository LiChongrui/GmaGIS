# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal

_log = logging.getLogger("gmagis")

__all__ = ["MapNavRenderer"]

_POLL_MS = 8
_BD_WAIT_MS = 3000


class MapNavRenderer(QThread):

    rendered = Signal(object, int)

    def __init__(self, bd=None, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsMapNavRenderer")
        self._bd = bd
        self._lock = threading.Lock()
        self._want = None
        self._alive = True
        self._busy = False
        self.last_error = ""

    def request(self, seq, layout, item, project, width_px):
        with self._lock:
            self._want = (int(seq), layout, item, project, int(width_px))
        if not self.isRunning():
            try:
                self.start()
            except Exception as e:
                self.last_error = "线程启动失败: %r" % (e,)
                _log.exception("布局：地图导航渲染线程启动失败")
                return False
        return True

    def invalidate(self):
        with self._lock:
            self._want = None

    def is_busy(self):
        return bool(self._busy)

    def wait_idle(self, wait_ms=2000):
        t0 = time.monotonic()
        while self._alive:
            with self._lock:
                pending = self._want is not None
            if not pending and not self._busy:
                return True
            if (time.monotonic() - t0) * 1000.0 > float(wait_ms):
                return False
            self.msleep(8)
        return True

    def stop(self, wait_ms=4000):
        self._alive = False
        with self._lock:
            self._want = None
        try:
            if self.isRunning():
                self.wait(int(wait_ms))
        except Exception:
            exc_note("stop @ ggis/ui/views/layout/mapnav.py:138")
            pass

    def run(self):
        while self._alive:
            with self._lock:
                job = self._want
                self._want = None
            if job is None:
                self.msleep(_POLL_MS)
                continue
            seq, layout, item, project, w = job
            self._busy = True
            img = None
            try:
                if self._bd is not None:
                    try:
                        self._bd.wait_idle(_BD_WAIT_MS)
                    except Exception:
                        exc_note("run @ ggis/ui/views/layout/mapnav.py:159")
                        pass
                img = self._render(layout, item, project, w)
                self.last_error = ""
            except Exception as e:
                self.last_error = "%s: %s" % (type(e).__name__, e)
                _log.error("布局：地图导航帧渲染失败：%s", self.last_error)
                traceback.print_exc()
            finally:
                self._busy = False
            if self._alive:
                try:
                    self.rendered.emit(img, seq)
                except Exception:
                    exc_note("run @ ggis/ui/views/layout/mapnav.py:173")
                    pass

    def _render(self, layout, item, project, width_px):
        from ggis.ui.views.layout import exporter as EX
        return EX.preview_item(layout, item, project, width_px=int(width_px))
