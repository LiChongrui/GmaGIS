# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import os
import logging
import threading
import time

_log = logging.getLogger("gmagis")

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

__all__ = ["load_async", "cancel_all", "active_count",
           "loadProgressSignal", "loadFinishedSignal", "loadFailedSignal"]

_MAX_THREADS = 4

_ASYNC_THRESHOLD = 512 * 1024


class _LoadEmitter(QObject):

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(object)
    partial = Signal(object)


_EMITTER = _LoadEmitter()


def loadProgressSignal():
    return _EMITTER.progress


def loadFinishedSignal():
    return _EMITTER.finished


def loadFailedSignal():
    return _EMITTER.failed


def loadPartialSignal():
    return _EMITTER.partial


_POOL = None
_POOL_LOCK = threading.Lock()


def _pool():
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                p = QThreadPool()
                p.setMaxThreadCount(_MAX_THREADS)
                _POOL = p
    return _POOL


_TASKS = {}
_TASKS_LOCK = threading.Lock()
_TOKEN_SEQ = [0]


def _next_token():
    with _TASKS_LOCK:
        _TOKEN_SEQ[0] += 1
        return _TOKEN_SEQ[0]


def active_count():
    with _TASKS_LOCK:
        return sum(1 for t in _TASKS.values() if not t.done())


def cancel_all():
    with _TASKS_LOCK:
        tasks = list(_TASKS.values())
    for t in tasks:
        t.cancel()


def shutdown(wait_ms=3000):
    global _POOL, _FLAT_POOL
    cancel_all()
    for p in (_POOL, _FLAT_POOL):
        if p is None:
            continue
        try:
            p.clear()
        except Exception as exc:
            _log.warning("退出清理线程池失败（clear %s）：%s", p, exc)
        try:
            p.waitForDone(int(wait_ms))
        except Exception as exc:
            _log.warning("退出清理线程池失败（waitForDone %s）：%s", p, exc)
    _POOL = None
    _FLAT_POOL = None


class _LoadTask(QRunnable):

    def __init__(self, path, layer, token, progressive=False):
        super().__init__()
        self.setAutoDelete(True)
        self._path = str(path)
        self._layer = layer
        self._token = int(token)
        self._progressive = bool(progressive)
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def cancelled(self):
        return self._cancel.is_set()

    def done(self):
        return self._cancel.is_set() or self._finished

    _finished = False

    def _emit_cancelled(self):
        self._finished = True
        with _TASKS_LOCK:
            _TASKS.pop(self._token, None)
        _EMITTER.failed.emit(
            {"token": self._token, "path": self._path,
             "error": "已取消", "cancelled": True})

    def run(self):
        result = {"token": self._token, "path": self._path, "layer": None,
                  "error": None}
        try:
            if self._cancel.is_set():
                self._emit_cancelled()
                return
            from .registry import load_file
            from .vector_io import is_vector_path, _read_vector_sync
            from .table_io import is_table_path

            self._yield("reading", 0, 0)

            if (is_vector_path(self._path) and self._layer is None
                    and not is_table_path(self._path)):
                _defer = False
                try:
                    import os as _os
                    if _os.path.isfile(self._path) and \
                            _os.path.getsize(self._path) > 300 * 1024 * 1024:
                        _defer = True
                except Exception:
                    _log.exception("silent exception in run")
                    _defer = False
                layer = _read_vector_sync(
                    self._path, layer=self._layer,
                    on_progress=self._yield,
                    on_partial=(self._on_partial if self._progressive
                                else None),
                    defer_geometry=_defer)
            else:
                layer = load_file(self._path, layer=self._layer)
            if self._cancel.is_set():
                self._emit_cancelled()
                return
            if layer is None:
                result["error"] = "不支持的文件类型"
            elif not layer.is_valid():
                result["error"] = layer.error() or "未知错误"
            else:
                result["layer"] = layer
                if layer.is_raster():
                    try:
                        from ggis.core.style import raster_display as _rd
                        _rd.sample_array(layer, band=0)
                    except Exception as exc:
                        _log.warning("首帧样本预计算失败（%s）：%s",
                                     self._path, exc)
        except Exception as exc:
            _log.exception("silent exception in run")
            result["error"] = "%s: %s" % (type(exc).__name__, exc)

        self._finished = True
        with _TASKS_LOCK:
            _TASKS.pop(self._token, None)
        if self._cancel.is_set():
            self._emit_cancelled()
            return

        if result["error"]:
            _EMITTER.failed.emit(
                {"token": self._token, "path": self._path,
                 "error": result["error"]})
        else:
            _EMITTER.finished.emit(
                {"token": self._token, "path": self._path,
                 "layer": result["layer"]})

    def _on_partial(self, lyr, first):
        if self._cancel.is_set() or lyr is None:
            return
        try:
            _EMITTER.partial.emit(
                {"token": self._token, "path": self._path,
                 "layer": lyr, "first": bool(first)})
        except Exception as exc:
            _log.warning("发送加载部分数据信号失败（%s）：%s",
                         self._path, exc)

    def _yield(self, phase, done=0, total=0):
        if self._cancel.is_set():
            return
        try:
            _EMITTER.progress.emit(
                {"token": self._token, "path": self._path,
                 "done": int(done), "total": int(total), "phase": phase})
        except Exception as exc:
            _log.warning("发送加载进度信号失败（%s）：%s",
                         self._path, exc)
        time.sleep(0)


def should_load_async(path):
    try:
        if os.path.isdir(path):
            return False
        sz = os.path.getsize(path)
    except OSError:
        exc_note("should_load_async @ ggis/io/async_loader.py:365")
        return False
    return sz >= _ASYNC_THRESHOLD


def load_async(path, layer=None, progressive=False):
    token = _next_token()
    task = _LoadTask(path, layer, token, progressive=progressive)
    with _TASKS_LOCK:
        _TASKS[token] = task
    _pool().start(task)
    return token


def cancel(token):
    with _TASKS_LOCK:
        t = _TASKS.get(int(token))
    if t is not None:
        t.cancel()
        return True
    return False


class _FlatTask(QRunnable):

    def __init__(self, layer, tol, dst_crs):
        super().__init__()
        self.setAutoDelete(True)
        self._layer = layer
        self._tol = tol
        self._crs = dst_crs
        self._cancel = threading.Event()
        self._key = id(layer)

    def cancel(self):
        self._cancel.set()

    def run(self):
        try:
            self._run_inner()
        finally:
            try:
                with _FLAT_LOCK:
                    _FLAT_BUSY.discard(self._key)
            except Exception as exc:
                _log.warning("预热销账失败（层 %s）：%s", self._key, exc)

    def _run_inner(self):
        try:
            from ..render.rasterize import warm_flat_chunked
            warm_flat_chunked(self._layer, self._tol, dst_crs=self._crs,
                              should_stop=self._cancel.is_set,
                              yield_fn=lambda: time.sleep(0))
        except Exception as exc:
            _log.warning("flat_coords 预热失败（层 %s）：%s",
                         getattr(self._layer, "name", lambda: "?")(),
                         exc)
        if self._cancel.is_set():
            return
        try:
            from ..render.cpu import backend as _B
            from ..render.rasterize import flat_coords
            kind = ("line" if self._layer.base_kind() == "line"
                    else "polygon")
            flat = flat_coords(self._layer, 0.0, kind=kind, dst_crs=self._crs)
            if flat and (_B.wanted_count(flat) or not _B.polys_ready(flat)):
                _B.prewarm_part_polys(flat, should_stop=self._cancel.is_set,
                                      yield_fn=lambda: time.sleep(0))
        except Exception as exc:
            _log.warning("部件多边形预热失败（层 %s）：%s",
                         getattr(self._layer, "name", lambda: "?")(),
                         exc)


_FLAT_POOL = None
_FLAT_LOCK = threading.Lock()
_FLAT_BUSY = set()


def _flat_pool():
    global _FLAT_POOL
    if _FLAT_POOL is None:
        with _FLAT_LOCK:
            if _FLAT_POOL is None:
                p = QThreadPool()
                p.setMaxThreadCount(1)
                _FLAT_POOL = p
    return _FLAT_POOL


def prewarm_flat_async(layer, tol=0.0, dst_crs=None):
    try:
        cache = layer.__dict__.get("_ggs_flat")
    except Exception as exc:
        _log.warning("读取 _ggs_flat 缓存失败（层 %s）：%s",
                     getattr(layer, "name", lambda: "?")(), exc)
        return None
    if isinstance(cache, dict) and cache:
        try:
            from ..render.cpu import backend as _B
            from ..render.rasterize import flat_coords
            kind = "line" if layer.base_kind() == "line" else "polygon"
            flat = flat_coords(layer, 0.0, kind=kind, dst_crs=dst_crs)
            if not flat:
                return None
            if _B.polys_ready(flat) and not _B.wanted_count(flat):
                return None
        except Exception as exc:
            _log.warning("判断 flat 部件缓存状态失败（层 %s）：%s",
                         getattr(layer, "name", lambda: "?")(), exc)
            return None
    t = _FlatTask(layer, tol, dst_crs)
    with _FLAT_LOCK:
        if t._key in _FLAT_BUSY:
            return None
        _FLAT_BUSY.add(t._key)
    _flat_pool().start(t)
    return t
