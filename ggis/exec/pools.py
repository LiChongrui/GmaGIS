# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import os
import threading

__all__ = ["cpu_pool", "io_pool", "proc_pool", "shutdown",
           "CPU_THREADS", "IO_THREADS", "active_count", "pool_stats"]

CPU_THREADS = max(2, min(6, (os.cpu_count() or 4) - 1))

IO_THREADS = 6

_CPU = None
_IO = None
_PROC = None
_LOCK = threading.Lock()


def cpu_pool():
    global _CPU
    if _CPU is None:
        with _LOCK:
            if _CPU is None:
                from PySide6.QtCore import QThreadPool
                p = QThreadPool()
                p.setMaxThreadCount(CPU_THREADS)
                p.setObjectName("ggs-exec-cpu")
                _CPU = p
    return _CPU


def io_pool():
    global _IO
    if _IO is None:
        with _LOCK:
            if _IO is None:
                from PySide6.QtCore import QThreadPool
                p = QThreadPool()
                p.setMaxThreadCount(IO_THREADS)
                p.setObjectName("ggs-exec-io")
                _IO = p
    return _IO


def proc_pool():
    global _PROC
    if _PROC is None:
        with _LOCK:
            if _PROC is None:
                from concurrent.futures import ProcessPoolExecutor
                _PROC = ProcessPoolExecutor(
                    max_workers=max(1, (os.cpu_count() or 2) - 1),
                    thread_name_prefix="ggs-exec-proc")
    return _PROC


def pool_of(kind):
    k = str(kind or "cpu").lower()
    if k in ("cpu", "io"):
        return cpu_pool() if k == "cpu" else io_pool()
    if k == "proc":
        return proc_pool()
    raise ValueError("未知的任务类型 %r（取 cpu / io / proc）" % (kind,))


def active_count():
    n = 0
    for p in (_CPU, _IO):
        if p is None:
            continue
        try:
            n += int(p.activeThreadCount())
        except Exception:
            exc_note("active_count @ ggis/exec/pools.py:114")
            pass
    return n


def pool_stats():
    out = {"cpu_threads": CPU_THREADS, "io_threads": IO_THREADS}
    for name, p in (("cpu", _CPU), ("io", _IO)):
        if p is None:
            out[name] = None
            continue
        try:
            out[name] = {"max": int(p.maxThreadCount()),
                         "active": int(p.activeThreadCount())}
        except Exception:
            exc_note("pool_stats @ ggis/exec/pools.py:129")
            out[name] = "(取不到)"
    out["proc"] = None if _PROC is None else "已建"
    return out


def shutdown(wait_ms=3000):
    global _CPU, _IO, _PROC
    for p in (_CPU, _IO):
        if p is None:
            continue
        try:
            p.clear()
        except Exception:
            exc_note("shutdown @ ggis/exec/pools.py:152")
            pass
        try:
            p.waitForDone(int(wait_ms))
        except Exception:
            exc_note("shutdown @ ggis/exec/pools.py:156")
            pass
    _CPU = None
    _IO = None
    p = _PROC
    _PROC = None
    if p is not None:
        try:
            p.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            exc_note("shutdown @ ggis/exec/pools.py:165")
            try:
                p.shutdown(wait=False)
            except Exception:
                exc_note("shutdown @ ggis/exec/pools.py:168")
                pass
        except Exception:
            exc_note("shutdown @ ggis/exec/pools.py:170")
            pass
