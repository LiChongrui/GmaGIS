# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage, QPainter

_POLL_MS = 4


class FrameContext:

    def __init__(self, canvas, width, height, qc=None, raster=None,
                 qc_ras=None, tile=None):
        self._cv = canvas
        self._w = int(width)
        self._h = int(height)
        if qc is not None:
            self.__dict__["_qc_painter"] = qc
        if raster is not None:
            self.__dict__["_ras_painter"] = raster
        if qc_ras is not None:
            self.__dict__["_qc_ras_painter"] = qc_ras
        if tile is not None:
            self.__dict__["_tile_painter"] = tile

    def width(self):
        return self._w

    def height(self):
        return self._h

    def __getattr__(self, name):
        return getattr(self._cv, name)


class FrameRenderer(QThread):

    rendered = Signal(object, int)

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsFrameRenderer")
        self._cv = canvas
        self._lock = threading.Lock()
        self._want = None
        self._alive = True
        self._busy = False
        self.last_error = ""
        self._err_n = 0

    def request(self, seq, task):
        with self._lock:
            self._want = (int(seq), task)
        if not self.isRunning():
            try:
                self.start()
            except Exception as e:
                exc_note("request @ ggis/render/async_frame.py:121")
                self.last_error = "线程启动失败: %r" % (e,)
                self._err_n += 1
        return self.isRunning()

    def invalidate(self):
        with self._lock:
            self._want = None

    def is_busy(self):
        return bool(self._busy)

    def warmup(self):
        if not self.isRunning():
            try:
                self.start()
            except Exception:
                exc_note("warmup @ ggis/render/async_frame.py:144")
                pass

    def stop(self):
        self._alive = False
        with self._lock:
            self._want = None
        try:
            self.wait(3000)
        except Exception:
            exc_note("stop @ ggis/render/async_frame.py:154")
            pass

    def run(self):
        while self._alive:
            with self._lock:
                item = self._want
                self._want = None
            if item is None:
                self.msleep(_POLL_MS)
                continue
            seq, task = item
            self._busy = True
            try:
                img = self._render(task)
                self.last_error = ""
            except Exception as e:
                exc_note("run @ ggis/render/async_frame.py:175")
                img = None
                self._err_n += 1
                self.last_error = "%s: %s" % (type(e).__name__, e)
                import traceback
                traceback.print_exc()
            finally:
                self._busy = False
            if img is not None and self._alive:
                try:
                    self.rendered.emit(img, seq)
                except Exception:
                    exc_note("run @ ggis/render/async_frame.py:188")
                    pass

    def _render(self, task):
        w, h = task["size"]
        dpr = float(task["dpr"] or 1.0)
        img = QImage(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(task["color"])
        p = QPainter(img)
        try:
            if task.get("aa"):
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            from .map_canvas import GgsMapCanvas
            ctx = FrameContext(self._cv, w, h,
                               qc=task.get("qc"), raster=task.get("ras"),
                               qc_ras=task.get("qc_ras"),
                               tile=task.get("tile"))
            GgsMapCanvas._paint_scene(ctx, p, task["settings"],
                                      raster_budget_ms=None, vec_cache=False)
        finally:
            p.end()
        return img
