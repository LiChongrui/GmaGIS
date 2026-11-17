# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math

from ggis.exec import guard as _guard
import logging
_log = logging.getLogger("gmagis")


__all__ = ["GgsField", "FIELDS_FROM_LAYER", "infer_type", "infer_field",
           "build_fields", "numeric_array", "TYPE_LABELS",
           "normalize_ogr_type", "fields_from_layer"]

TYPE_LABELS = {
    "integer": "整数",
    "real": "实数",
    "string": "文本",
    "date": "日期",
    "datetime": "日期时间",
    "bool": "布尔",
    "binary": "二进制",
    "unknown": "未知",
}

_OGR_MAP = {
    "integer": "integer",
    "integer64": "integer",
    "int8": "integer",
    "int16": "integer",
    "int32": "integer",
    "int": "integer",
    "int64": "integer",
    "real": "real",
    "float": "real",
    "float32": "real",
    "float64": "real",
    "double": "real",
    "string": "string",
    "widestring": "string",
    "str": "string",
    "date": "date",
    "time": "datetime",
    "datetime": "datetime",
    "binary": "binary",
    "bool": "bool",
    "boolean": "bool",
    "object": "string",
    "o": "string",
    "u": "integer",
    "i": "integer",
    "f": "real",
    "b": "bool",
    "m8": "datetime",
}

_OGR_PREFIXES = ("oft", "ogr", "wkb")


def normalize_ogr_type(ogr_type):
    key = str(ogr_type or "").strip().lower()
    key = key.split("(")[0].strip()
    for p in _OGR_PREFIXES:
        if key.startswith(p) and len(key) > len(p):
            key = key[len(p):].strip()
    return key


class GgsField:

    __slots__ = ("name", "type", "width", "precision", "ogr_type")

    def __init__(self, name, type="string", width=0, precision=0,
                 ogr_type=""):
        self.name = str(name)
        self.type = type if type in TYPE_LABELS else "unknown"
        self.width = int(width or 0)
        self.precision = int(precision or 0)
        self.ogr_type = str(ogr_type or "")

    @classmethod
    def from_ogr(cls, name, ogr_type=""):
        key = normalize_ogr_type(ogr_type)
        t = _OGR_MAP.get(key)
        if t is None:
            for probe, mapped in (("integer", "integer"), ("int", "integer"),
                                  ("real", "real"), ("float", "real"),
                                  ("double", "real"), ("char", "string"),
                                  ("string", "string"), ("text", "string"),
                                  ("datetime", "datetime"),
                                  ("date", "date"), ("bool", "bool")):
                if probe in key:
                    t = mapped
                    break
        return cls(name, t or "unknown", ogr_type=ogr_type)

    def is_numeric(self):
        return self.type in ("integer", "real")

    def display(self, value):
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isnan(value):
                return ""
            if self.type == "real" and self.precision > 0:
                return "%.*f" % (self.precision, value)
            if value == int(value) and abs(value) < 1e15:
                return str(int(value))
            return "%.6g" % value
        return str(value)

    def display_full(self, value):
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isnan(value):
                return ""
            if self.type == "real" and self.precision > 0:
                return "%.*f" % (self.precision, value)
            if value == int(value) and abs(value) < 1e15:
                return str(int(value))
            return repr(value)
        return str(value)

    def coerce(self, value):
        if value is None or value == "":
            return None
        try:
            if self.type == "integer":
                return int(float(value))
            if self.type == "real":
                return float(value)
            if self.type == "bool":
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in ("1", "true", "yes",
                                                      "是", "y", "t")
        except (TypeError, ValueError):
            exc_note("coerce @ ggis/core/model/field.py:173")
            return value
        return value

    def sort_key(self, value):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return (1, 0 if self.is_numeric() else "")
        if self.is_numeric():
            try:
                return (0, float(value))
            except (TypeError, ValueError):
                exc_note("sort_key @ ggis/core/model/field.py:184")
                return (1, 0)
        return (0, str(value))

    def to_dict(self):
        return {"name": self.name, "type": self.type, "width": self.width,
                "precision": self.precision, "ogr_type": self.ogr_type}

    def __repr__(self):
        return "GgsField(%s, %s)" % (self.name, self.type)


def infer_type(values):
    import numbers
    seen_num = seen_int = seen_str = seen_bool = seen_date = False
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool) or isinstance(v, np_bool_type()):
            seen_bool = True
        elif isinstance(v, numbers.Integral):
            seen_int = True
        elif isinstance(v, numbers.Real):
            fv = float(v)
            if math.isnan(fv):
                continue
            seen_num = True
        elif isinstance(v, str):
            seen_str = True
        else:
            seen_date = True
    if seen_str or seen_date:
        return "string"
    if seen_num:
        return "real"
    if seen_int:
        return "integer"
    if seen_bool:
        return "bool"
    return "string"


def np_bool_type():
    try:
        import numpy as np
        return np.bool_
    except Exception:
        _log.exception("silent exception in np_bool_type")
        return type(None)


def infer_field(name, values):
    values = list(values)
    t = infer_type(values)
    width = 0
    precision = 0
    if t == "real":
        for v in values:
            if isinstance(v, float) and not math.isnan(v):
                s = repr(v)
                if "." in s:
                    precision = max(precision,
                                    min(6, len(s.split(".")[1])))
    elif t == "string":
        for v in values:
            if isinstance(v, str):
                width = max(width, len(v))
        width = min(max(width, 8), 255)
    return GgsField(name, t, width, precision)


def build_fields(names, attrs):
    out = []
    n = len(attrs)
    for name in names:
        col = [attrs[i].get(name) if i < n and isinstance(attrs[i], dict)
               else None for i in range(n)]
        out.append(infer_field(name, col))
    return out


def fields_from_layer(layer):
    raw = layer.fields() or []
    out = []
    for item in raw:
        if isinstance(item, GgsField):
            out.append(item)
        elif isinstance(item, (tuple, list)):
            out.append(GgsField.from_ogr(item[0],
                                         item[1] if len(item) > 1 else ""))
        else:
            out.append(GgsField(str(item)))
    if not out:
        attrs = layer.attrs() or []
        names = []
        for a in attrs:
            if isinstance(a, dict):
                for k in a.keys():
                    if k not in names:
                        names.append(k)
        out = build_fields(names, attrs)
    return out


FIELDS_FROM_LAYER = fields_from_layer


@_guard.off_ui("core.field.numeric_array")
def numeric_array(layer, field_name):
    import numpy as np
    n = layer.feature_count()
    out = np.full(n, np.nan, dtype=np.float64)
    attrs = layer.attrs()
    for i in range(min(n, len(attrs))):
        a = attrs[i]
        if not isinstance(a, dict):
            continue
        v = a.get(field_name)
        if v is None or isinstance(v, bool):
            continue
        try:
            out[i] = float(v)
        except (TypeError, ValueError):
            exc_note("numeric_array @ ggis/core/model/field.py:322")
            continue
    return out
