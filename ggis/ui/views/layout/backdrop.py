# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import threading
import time
import traceback

from PySide6.QtCore import QThread, Signal

_log = logging.getLogger("gmagis")

__all__ = ["BackdropRenderer"]

_POLL_MS = 12


class BackdropRenderer(QThread):

    rendered = Signal(object, int)

    patch_ready = Signal(object, int)

    elem_ready = Signal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsBackdropRenderer")
        self._lock = threading.Lock()
        self._want = None
        self._alive = True
        self._busy = False
        self.last_error = ""

    def request(self, seq, layout, project, width_px):
        return self._post("full", seq, (layout, project, int(width_px)))

    def request_patch(self, seq, layout, project, rect_mm, exclude, width_px,
                      dpi=None):
        return self._post("patch", seq,
                          (layout, project, rect_mm, exclude, int(width_px),
                           dpi))

    def request_elem(self, seq, layout, project, item, width_px, pad_mm,
                     background="#00000000"):
        return self._post("elem", seq,
                          (layout, project, item, int(width_px),
                           float(pad_mm), str(background)),
                          keep=("patch", "full"))

    def _post(self, kind, seq, payload, keep=None):
        with self._lock:
            cur = self._want
            if (keep is not None and cur is not None
                    and cur[0] in (keep if isinstance(keep, tuple) else (keep,))):
                return False
            self._want = (str(kind), int(seq), payload)
        if not self.isRunning():
            try:
                self.start()
            except Exception as e:
                self.last_error = "线程启动失败: %r" % (e,)
                _log.exception("布局：底图渲染线程启动失败")
                return False
        return True

    def invalidate(self):
        with self._lock:
            self._want = None

    def is_busy(self):
        return bool(self._busy)

    def wait_idle(self, wait_ms=4000):
        t0 = time.monotonic()
        while self._alive:
            with self._lock:
                pending = self._want is not None
            if not pending and not self._busy:
                return True
            if (time.monotonic() - t0) * 1000.0 > float(wait_ms):
                _log.warning("布局：后台渲染 %.0f ms 内没结束（继续，可能有竞态）",
                             wait_ms)
                return False
            try:
                from ggis.ui.dialogs.busy import pump as _pump
                _pump()
            except Exception:
                exc_note("wait_idle @ ggis/ui/views/layout/backdrop.py:198")
                pass
            self.msleep(10)
        return True

    def stop(self, wait_ms=5000):
        self._alive = False
        with self._lock:
            self._want = None
        try:
            if self.isRunning():
                self.wait(int(wait_ms))
        except Exception:
            exc_note("stop @ ggis/ui/views/layout/backdrop.py:211")
            pass

    def run(self):
        while self._alive:
            with self._lock:
                task = self._want
                self._want = None
            if task is None:
                self.msleep(_POLL_MS)
                continue
            try:
                kind, seq, payload = task
            except Exception:
                exc_note("run @ ggis/ui/views/layout/backdrop.py:225")
                continue
            self._busy = True
            img = None
            try:
                if kind == "patch":
                    img = self._render_patch(*payload)
                elif kind == "elem":
                    img = self._render_elem(*payload)
                else:
                    img = self._render(*payload)
                self.last_error = ""
            except Exception as e:
                self.last_error = "%s: %s" % (type(e).__name__, e)
                _log.error("布局：后台%s渲染失败：%s",
                           {"patch": "补丁", "elem": "元素位图"}.get(kind, "底图"),
                           self.last_error)
                traceback.print_exc()
            finally:
                self._busy = False
            if self._alive:
                try:
                    sig = {"patch": self.patch_ready,
                           "elem": self.elem_ready}.get(kind, self.rendered)
                    sig.emit(img, seq)
                except Exception:
                    exc_note("run @ ggis/ui/views/layout/backdrop.py:251")
                    pass

    def _render(self, layout, project, width_px):
        from ggis.ui.views.layout import exporter as EX
        return EX.preview_image(layout, project, width_px=int(width_px))

    def _render_patch(self, layout, project, rect_mm, exclude, width_px, dpi):
        from ggis.ui.views.layout import exporter as EX
        return EX.preview_region(layout, rect_mm, project, width_px=int(width_px),
                                 exclude=exclude, dpi=dpi)

    def _render_elem(self, layout, project, item, width_px, pad_mm, background):
        from ggis.ui.views.layout import exporter as EX
        return EX.preview_item(layout, item, project, int(width_px),
                               background=background, pad_mm=pad_mm)
