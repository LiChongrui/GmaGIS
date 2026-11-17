# -*- coding: utf-8 -*-

import os
import time

from ggis.core.app import i18n
from ggis.core.app import settings
import logging
_log = logging.getLogger("gmagis")


def human_size(n):
    try:
        v = float(n)
    except Exception:
        _log.exception("silent exception in human_size")
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if v < 1024.0 or unit == "TB":
            return ("%.0f %s" % (v, unit)) if unit == "B" \
                else ("%.1f %s" % (v, unit))
        v /= 1024.0
    return ""


def file_path(parent=None):
    try:
        f = getattr(parent, "_project_path", None)
        return str(f() or "") if callable(f) else ""
    except Exception:
        _log.exception("silent exception in file_path")
        return ""


def project_of(parent=None):
    try:
        c = getattr(parent, "canvas", None)
        p = c.project() if c is not None else None
        if p is not None:
            return p
    except Exception:
        _log.exception("silent exception in project_of")
    try:
        from .project import GgsProject
        return GgsProject.instance()
    except Exception:
        _log.exception("silent exception in project_of")
        return None


def snapshot(project=None, path=""):
    snap = {"path": str(path or ""), "crs": "", "layers": "",
            "features": "", "size": "", "mtime": ""}
    try:
        crs = settings.default_crs()
        if crs is not None and crs.is_valid():
            snap["crs"] = str(crs.display_name() or crs.authid() or "")
    except Exception:
        _log.exception("silent exception in snapshot")
    try:
        layers = list(project.layers()) if project is not None else []
        n_vec = sum(1 for l in layers if l.is_vector())
        snap["layers"] = i18n.tr("矢量 {0} / 栅格 {1}").format(
            n_vec, len(layers) - n_vec)
        total = 0
        for l in layers:
            if not l.is_vector():
                continue
            try:
                total += int(l.feature_count())
            except Exception:
                _log.exception("silent exception in snapshot")
        snap["features"] = "{0:,}".format(total)
    except Exception:
        _log.exception("silent exception in snapshot")
    try:
        p = snap["path"]
        if p and os.path.isfile(p):
            snap["size"] = human_size(os.path.getsize(p))
            snap["mtime"] = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(p)))
    except Exception:
        _log.exception("silent exception in snapshot")
    return snap


def snapshot_of(parent=None):
    return snapshot(project_of(parent), file_path(parent))
