# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

__all__ = ["backend_name", "raster_backend", "path_pen", "path_brush",
           "AA_VERTEX_BUDGET", "BUILTIN_BACKEND"]

BUILTIN_BACKEND = "builtin"

AA_VERTEX_BUDGET = 180_000


def backend_name():
    return BUILTIN_BACKEND


def raster_backend():
    return BUILTIN_BACKEND


def path_pen(sym, kind):
    try:
        col = sym.stroke_color()
    except Exception:
        exc_note("path_pen @ ggis/render/pens.py:94")
        col = QColor("#3d7fd1")
    if col is None:
        col = QColor("#3d7fd1")
    if col.alpha() == 0:
        col = QColor(col)
        col.setAlpha(90)
    try:
        fn = getattr(sym, "px_width", None)
        if callable(fn):
            width = float(fn())
        elif callable(getattr(sym, "width", None)):
            width = float(sym.width())
        else:
            width = float(getattr(sym, "width", 1.0) or 1.0)
    except Exception:
        exc_note("path_pen @ ggis/render/pens.py:112")
        width = 1.0
    if kind == "polygon":
        width = max(0.6, min(width, 3.0))
    else:
        width = max(0.8, min(width, 6.0))
    pen = QPen(col, width)
    pen.setCosmetic(True)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def path_brush(sym, kind):
    if kind != "polygon":
        return Qt.BrushStyle.NoBrush
    try:
        col = sym.fill_color()
    except Exception:
        exc_note("path_brush @ ggis/render/pens.py:131")
        col = QColor("#5a97e2")
    if col is None or QColor(col).alpha() == 0:
        return Qt.BrushStyle.NoBrush
    return QBrush(QColor(col))
