# -*- coding: utf-8 -*-

from __future__ import annotations

from ggis.core.app import i18n
from ggis.core.model.layout_model import DEFAULT_UNIT, unit_factor

_tr = i18n.tr

PAGE_UNIT_ITEMS = (
    ("mm", _tr("毫米")),
    ("cm", _tr("厘米")),
    ("in", _tr("英寸")),
)


def unit_name(code):
    c = str(code or DEFAULT_UNIT)
    for k, label in PAGE_UNIT_ITEMS:
        if k == c:
            return label
    for k, label in PAGE_UNIT_ITEMS:
        if k == DEFAULT_UNIT:
            return label
    return str(c)


def fmt_len(code, mm, digits=2):
    f = unit_factor(code) or 1.0
    v = float(mm) / f
    if str(code or DEFAULT_UNIT) == "in":
        return ("%%.%df" % int(digits)) % v
    if abs(v - round(v)) < 1e-6:
        return "%d" % int(round(v))
    return "%.1f" % v
