# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import sys
import threading
import time
import traceback

from PySide6.QtCore import QObject, QRunnable, Signal

from . import guard, pools

__all__ = ["Task", "submit", "submit_meta", "to_ui", "progressSignal",
           "finishedSignal", "failedSignal", "active_tasks", "cancel_all",
           "shutdown", "protected_tasks", "wait_protected"]

_PROGRESS_MIN_DT = 0.05


class _Router(QObject):

    deliver = Signal(object)

    def on_deliver(self, payload):
        fn, args, kwargs = payload
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            exc_note("on_deliver @ ggis/exec/task.py:81")
            try:
                sys.stderr.write(
                    "GmaGIS[后台回调]: %r 在主线程执行时抛出 %r\n"
                    % (getattr(fn, "__qualname__", fn), exc))
            except Exception:
                exc_note("on_deliver @ ggis/exec/task.py:86")
                pass


_ROUTER = _Router()
_ROUTER.deliver.connect(_ROUTER.on_deliver)


def to_ui(fn, *args, **kwargs):
    if guard.ui_mode() and not guard.on_ui_thread():
        _ROUTER.deliver.emit((fn, args, kwargs))
    else:
        fn(*args, **kwargs)


class _Emitter(QObject):

    progress = Signal(object)
    finished = Signal(object)
    failed = Signal(object)


_EMITTER = _Emitter()


def progressSignal():
    return _EMITTER.progress


def finishedSignal():
    return _EMITTER.finished


def failedSignal():
    return _EMITTER.failed


_TASKS = {}
_TASKS_LOCK = threading.Lock()
_SEQ = [0]


def _next_token():
    with _TASKS_LOCK:
        _SEQ[0] += 1
        return _SEQ[0]


def active_tasks():
    with _TASKS_LOCK:
        return sum(1 for t in _TASKS.values() if not t.done)


def protected_tasks():
    with _TASKS_LOCK:
        return [t for t in _TASKS.values() if not t.done and t.protected]


def wait_protected(timeout_ms=15000):
    import time as _time
    t0 = _time.perf_counter()
    for t in protected_tasks():
        left = float(timeout_ms) - (_time.perf_counter() - t0) * 1000.0
        if left <= 0:
            break
        try:
            t.wait(int(left))
        except Exception:
            exc_note("wait_protected @ ggis/exec/task.py:184")
            pass


def cancel_all():
    with _TASKS_LOCK:
        tasks = list(_TASKS.values())
    for t in tasks:
        if not t.protected:
            t.cancel()


def shutdown(wait_ms=3000):
    cancel_all()
    pools.shutdown(wait_ms)


class Task(object):

    __slots__ = ("token", "name", "kind", "fn", "protected", "_cancel",
                 "_ok_event", "_done", "_result", "_error", "_tb",
                 "_cancelled", "_t0", "_ms", "_last_progress", "_callbacks",
                 "_state")

    def __init__(self, token, name, kind, fn, protected=False):
        self.token = token
        self.name = name
        self.kind = kind
        self.fn = fn
        self.protected = bool(protected)
        self._cancel = threading.Event()
        self._ok_event = threading.Event()
        self._done = False
        self._result = None
        self._error = None
        self._tb = ""
        self._cancelled = False
        self._t0 = time.perf_counter()
        self._ms = 0.0
        self._last_progress = 0.0
        self._callbacks = {"done": [], "fail": [], "progress": []}
        self._state = "pending"

    @property
    def done(self):
        return self._done

    @property
    def cancelled(self):
        return self._cancelled

    @property
    def result(self):
        return self._result

    @property
    def error(self):
        return self._error

    @property
    def traceback_text(self):
        return self._tb

    @property
    def state(self):
        return self._state

    @property
    def ms(self):
        if self._done:
            return self._ms
        return (time.perf_counter() - self._t0) * 1000.0

    def __repr__(self):
        return ("<Task #%d %r %s %.1fms>" %
                (self.token, self.name, self._state, self.ms))

    def cancel(self):
        if not self._done:
            self._cancel.set()
            self._cancelled = True

    def cancel_check(self):
        return self._cancel.is_set()

    def progress(self, frac, text=""):
        f = float(frac)
        if f < 0.0:
            f = 0.0
        elif f > 1.0:
            f = 1.0
        now = time.perf_counter()
        if now - self._last_progress < _PROGRESS_MIN_DT and f < 1.0:
            return
        self._last_progress = now
        ev = {"token": self.token, "name": self.name, "frac": f,
              "text": str(text), "ms": (now - self._t0) * 1000.0}
        for cb in list(self._callbacks["progress"]):
            to_ui(cb, ev)
        try:
            _EMITTER.progress.emit(ev)
        except Exception:
            exc_note("progress @ ggis/exec/task.py:302")
            pass

    def on_done(self, cb):
        self._callbacks["done"].append(cb)
        if self._done and self._state in ("done", "cancelled"):
            to_ui(cb, self._event("finished"))
        return self

    def on_fail(self, cb):
        self._callbacks["fail"].append(cb)
        if self._done and self._state == "failed":
            to_ui(cb, self._event("failed"))
        return self

    def on_progress(self, cb):
        self._callbacks["progress"].append(cb)
        return self

    def wait(self, timeout_ms=30000):
        return self._ok_event.wait(max(0.0, float(timeout_ms) / 1000.0))

    def _event(self, kind):
        ev = {"token": self.token, "name": self.name, "ms": self.ms,
              "cancelled": self._cancelled}
        if kind == "finished":
            ev["result"] = self._result
        else:
            ev["error"] = self._error
            ev["traceback"] = self._tb
        return ev

    def _finish(self, result, error=None, tb=""):
        if self._done:
            return
        self._done = True
        self._ms = (time.perf_counter() - self._t0) * 1000.0
        self._result = result
        self._error = error
        self._tb = tb
        if self._cancelled:
            self._state = "cancelled"
            emit_fail = False
        elif error is not None:
            self._state = "failed"
            emit_fail = True
        else:
            self._state = "done"
            emit_fail = False
        self._ok_event.set()
        with _TASKS_LOCK:
            _TASKS.pop(self.token, None)
        if emit_fail:
            ev = self._event("failed")
            for cb in list(self._callbacks["fail"]):
                to_ui(cb, ev)
            try:
                _EMITTER.failed.emit(ev)
            except Exception:
                exc_note("_finish @ ggis/exec/task.py:376")
                pass
        else:
            ev = self._event("finished")
            for cb in list(self._callbacks["done"]):
                to_ui(cb, ev)
            try:
                _EMITTER.finished.emit(ev)
            except Exception:
                exc_note("_finish @ ggis/exec/task.py:384")
                pass

    def _mark_running(self):
        if not self._done:
            self._state = "running"


class _RunTask(QRunnable):

    def __init__(self, task, args, kwargs):
        super().__init__()
        self.setAutoDelete(True)
        self._task = task
        self._args = args
        self._kwargs = kwargs

    def run(self):
        t = self._task
        if t.cancel_check():
            t._finish(None)
            return
        t._mark_running()
        try:
            r = t.fn(*self._args, **self._kwargs)
        except BaseException as exc:
            exc_note("run @ ggis/exec/task.py:411")
            t._finish(None, error=exc,
                      tb="".join(traceback.format_exception(
                          type(exc), exc, exc.__traceback__)))
            return
        if t.cancel_check():
            t._finish(None)
            return
        t._finish(r)


def _proc_entry(fn, args, kwargs):
    return fn(*args, **kwargs)


def _submit_proc(task, args, kwargs):
    try:
        fut = pools.proc_pool().submit(_proc_entry, task.fn, args, kwargs)
    except Exception as exc:
        exc_note("_submit_proc @ ggis/exec/task.py:430")
        task._finish(None, error=exc,
                     tb="".join(traceback.format_exception(
                         type(exc), exc, exc.__traceback__)))
        return task

    def _cb(f):
        try:
            r = f.result()
        except BaseException as exc:
            exc_note("_cb @ ggis/exec/task.py:439")
            task._finish(None, error=exc,
                         tb="".join(traceback.format_exception(
                             type(exc), exc, exc.__traceback__)))
        else:
            task._finish(None if task.cancel_check() else r)

    fut.add_done_callback(_cb)
    task._state = "running"
    return task


def submit_meta(fn, args=(), kwargs=None, kind="cpu", name="",
                protect=False, on_done=None, on_fail=None, on_progress=None,
                token=None):
    """:func:`submit` 的"元信息与参数分开传"版本 —— 给 :func:`ggis.exec.guard.offloaded` 用。

 为什么不能直接调 :func:`submit`
 -------------------------------
 ``submit`` 是从 ``**kwargs`` 里 pop 出 ``kind`` / ``name`` / ``protect``
 的（对人是好用的语法糖），代价是**被包装的函数自己不能有同名形参** ——
 本项目的 ``csv_io.read_table_points(..., name="__probe__")`` 正好叫
 ``name``（那是个图层名），于是撞出
 ``TypeError: submit() got multiple values for keyword argument 'name'``。

 语法糖留着（面板与作业都按老写法调），但装饰器走这条**没有键冲突**的路。
 """
    if kwargs is None:
        kwargs = {}
    kind = str(kind or "cpu").lower()
    name = str(name or getattr(fn, "__name__", "task"))

    if token is None:
        token = _next_token()
    task = Task(token, name, kind, fn, protected=bool(protect))
    with _TASKS_LOCK:
        _TASKS[token] = task
    if on_done is not None:
        task.on_done(on_done)
    if on_fail is not None:
        task.on_fail(on_fail)
    if on_progress is not None:
        task.on_progress(on_progress)

    return _launch(task, args, kwargs)


def submit(fn, *args, **kwargs):
    kind = kwargs.pop("kind", "cpu")
    name = kwargs.pop("name", "")
    protect = kwargs.pop("protect", False)
    on_done = kwargs.pop("on_done", None)
    on_fail = kwargs.pop("on_fail", None)
    on_progress = kwargs.pop("on_progress", None)
    token = kwargs.pop("token", None)

    return submit_meta(fn, args, kwargs, kind=kind, name=name,
                       protect=protect, on_done=on_done, on_fail=on_fail,
                       on_progress=on_progress, token=token)


def _launch(task, args, kwargs):
    fn = task.fn
    try:
        import inspect
        params = inspect.signature(fn).parameters
        if "progress" in params and "progress" not in kwargs:
            kwargs["progress"] = task.progress
        if "cancel" in params and "cancel" not in kwargs:
            kwargs["cancel"] = task.cancel_check
    except (TypeError, ValueError):
        exc_note("_launch @ ggis/exec/task.py:539")
        pass

    if task.kind == "proc":
        return _submit_proc(task, args, kwargs)
    if task.kind not in ("cpu", "io"):
        raise ValueError("未知的任务类型 %r（取 cpu / io / proc）" % (task.kind,))
    pool = pools.cpu_pool() if task.kind == "cpu" else pools.io_pool()
    pool.start(_RunTask(task, args, kwargs))
    return task
