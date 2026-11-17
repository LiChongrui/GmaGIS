# -*- coding: utf-8 -*-

import os
import re

from . import i18n
from . import settings as _settings
import logging
_log = logging.getLogger("gmagis")

MAX = 8
KEY = "recent_projects"

COLOR_MAX = 12
COLOR_KEY = "recent_colors"

_RE_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")



def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def load():
    try:
        raw = _settings.get(KEY) or []
    except Exception:
        _log.exception("silent exception in load")
        return []
    out, seen = [], set()
    for p in raw:
        try:
            s = str(p or "").strip()
        except Exception:
            _log.exception("silent exception in load")
            continue
        if not s:
            continue
        k = _norm(s)
        if k in seen:
            continue
        seen.add(k)
        out.append(os.path.abspath(s))
    return out[:MAX]


def _save(paths):
    try:
        _settings.set(KEY, [str(p) for p in list(paths)[:MAX]])
        _settings.save()
    except Exception:
        _log.exception("silent exception in _save")


def add(path):
    p = str(path or "").strip()
    if not p:
        return load()
    cur = [x for x in load() if _norm(x) != _norm(p)]
    cur.insert(0, os.path.abspath(p))
    cur = cur[:MAX]
    _save(cur)
    return cur


def remove(path):
    k = _norm(path)
    cur = [x for x in load() if _norm(x) != k]
    _save(cur)
    return cur


def clear():
    _save([])


def exists(path):
    try:
        return os.path.isfile(str(path or ""))
    except Exception:
        _log.exception("silent exception in exists")
        return False


def label(path):
    p = str(path or "")
    base = os.path.basename(p) or p
    try:
        from ggis.io.project_io import describe_project
        d = describe_project(p) or {}
        title = str(d.get("title") or "").strip()
        n = int(d.get("layers") or 0)
        if title:
            return "{0}  —  {1}".format(title,
                                        i18n.tr("{0} 个图层").format(n))
    except Exception:
        _log.exception("silent exception in label")
    return base



def _norm_color(value):
    try:
        s = value.name() if hasattr(value, "name") else str(value or "")
    except Exception:
        _log.exception("silent exception in _norm_color")
        return ""
    s = str(s or "").strip()
    if not _RE_HEX.match(s):
        return ""
    return s.upper()


def load_colors():
    try:
        raw = _settings.get(COLOR_KEY) or []
    except Exception:
        _log.exception("silent exception in load_colors")
        return []
    out, seen = [], set()
    for item in raw:
        s = _norm_color(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out[:COLOR_MAX]


def _save_colors(items):
    try:
        _settings.set(COLOR_KEY, [str(x) for x in list(items)[:COLOR_MAX]])
        _settings.save()
    except Exception:
        _log.exception("silent exception in _save_colors")


def add_color(color):
    s = _norm_color(color)
    if not s:
        return load_colors()
    cur = [x for x in load_colors() if x != s]
    cur.insert(0, s)
    cur = cur[:COLOR_MAX]
    _save_colors(cur)
    return cur


def clear_colors():
    _save_colors([])
