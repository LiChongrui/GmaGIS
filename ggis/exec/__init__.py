# -*- coding: utf-8 -*-
from __future__ import annotations

from . import guard

__all__ = ["guard", "task", "pools", "jobs", "submit", "Task", "to_ui",
           "active_tasks", "cancel_all", "shutdown"]

_LAZY = {
    "task": "task",
    "pools": "pools",
    "jobs": "jobs",
    "submit": "task",
    "Task": "task",
    "to_ui": "task",
    "active_tasks": "task",
    "cancel_all": "task",
    "shutdown": "task",
}


def __getattr__(name):
    mod = _LAZY.get(name)
    if mod is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    import importlib
    m = importlib.import_module("." + mod, __name__)
    value = m if name == mod else getattr(m, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(list(globals()) + __all__))
