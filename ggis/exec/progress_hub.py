# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import threading


class ProgressPresenter:

    def show(self, token, name):
        pass

    def update(self, token, frac, text):
        pass

    def done(self, token):
        pass

    def cancel_requested(self, token):
        return False


class ProgressHub:

    def __init__(self):
        self._presenters = []
        self._tasks = {}
        self._lock = threading.Lock()

    def subscribe(self, presenter):
        if presenter not in self._presenters:
            self._presenters.append(presenter)
        return self

    def detach(self, presenter):
        try:
            self._presenters.remove(presenter)
        except ValueError:
            exc_note("detach @ ggis/exec/progress_hub.py:80")
            pass
        return self

    def attach(self, task):
        if task is None:
            return None
        token = getattr(task, "token", None)
        if token is None:
            return task
        with self._lock:
            self._tasks[token] = task
        name = getattr(task, "name", "") or ""
        try:
            task.on_progress(self._on_progress)
            task.on_done(self._on_finish)
            task.on_fail(self._on_finish)
        except Exception:
            exc_note("attach @ ggis/exec/progress_hub.py:107")
            pass
        for p in list(self._presenters):
            try:
                p.show(token, name)
            except Exception:
                exc_note("attach @ ggis/exec/progress_hub.py:112")
                pass
        if getattr(task, "done", False):
            try:
                self._on_finish({"token": token, "name": name})
            except Exception:
                exc_note("attach @ ggis/exec/progress_hub.py:119")
                pass
        return task

    def request_cancel(self, token):
        t = self._tasks.get(token)
        if t is not None:
            try:
                t.cancel()
            except Exception:
                exc_note("request_cancel @ ggis/exec/progress_hub.py:132")
                pass

    def _on_progress(self, ev):
        token = ev.get("token")
        frac = ev.get("frac", 0.0)
        text = ev.get("text", "")
        cancel = False
        for p in list(self._presenters):
            try:
                p.update(token, frac, text)
                if p.cancel_requested(token):
                    cancel = True
            except Exception:
                exc_note("_on_progress @ ggis/exec/progress_hub.py:146")
                pass
        if cancel:
            t = self._tasks.get(token)
            if t is not None:
                try:
                    t.cancel()
                except Exception:
                    exc_note("_on_progress @ ggis/exec/progress_hub.py:153")
                    pass

    def _on_finish(self, ev):
        token = ev.get("token")
        for p in list(self._presenters):
            try:
                p.done(token, ev)
            except Exception:
                exc_note("_on_finish @ ggis/exec/progress_hub.py:161")
                pass
        with self._lock:
            self._tasks.pop(token, None)


_hub = None
_hub_lock = threading.Lock()


def hub():
    global _hub
    if _hub is None:
        with _hub_lock:
            if _hub is None:
                _hub = ProgressHub()
    return _hub
