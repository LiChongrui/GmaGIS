# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re

from ggis.core.crs.units import (convert as _convert, default_unit as _default_unit,
                    from_px as _from_px, is_known as _is_known,
                    DEFAULT_LINE_WIDTH_PX as _DEFAULT_LINE_WIDTH_PX)
from . import symbol_spec as _spec
import logging
_log = logging.getLogger("gmagis")

__all__ = [
    "CATEGORIES", "CATEGORY_TITLES", "SCHEMA", "BUILTIN", "SETTINGS_KEY",
    "RAMP_STOPS", "RAMP_TITLES", "LEGACY_STOPS", "LEGACY_TITLES",
    "ramp_keys", "ramp_stops", "ramp_title", "schema",
    "builtin_items", "user_items", "items", "find", "make", "add",
    "update", "remove", "rename", "title_of", "export_json", "import_json",
    "reset_user", "validate", "stored_unit",
]


_UNIT_KEY = "style_library_unit"


def _target_unit():
    return _default_unit()


def _stored_unit():
    try:
        v = str(_settings().get(_UNIT_KEY) or "").strip().lower()
    except Exception:
        _log.exception("silent exception in _stored_unit")
        v = ""
    return v if _is_known(v) else "px"


def target_unit():
    return _target_unit()


def stored_unit():
    return _stored_unit()


def _in_unit(px, unit=None):
    return round(_from_px(float(px), unit), 4)


def _px_item_to_unit(it, unit=None):
    d = dict(it)
    for k in ("width", "size"):
        if k in d:
            try:
                d[k] = _in_unit(d[k], unit)
            except Exception:
                _log.exception("silent exception in _px_item_to_unit")
    return d


def _convert_item(it, src, dst):
    d = dict(it)
    for k in ("width", "size"):
        if k in d:
            try:
                d[k] = round(_convert(float(d[k]), src, dst), 4)
            except Exception:
                _log.exception("silent exception in _convert_item")
    return d


def _migrate_items(items, src, dst):
    out = []
    changed = False
    for it in items:
        d = _convert_item(it, src, dst)
        if d != it:
            changed = True
        out.append(d)
    return out, changed


def _unit_is_current():
    return _stored_unit() == _target_unit()


def _persist_items(category, items):
    try:
        st = _settings()
        raw = st.get(SETTINGS_KEY) or {}
        if not isinstance(raw, dict):
            raw = {}
        raw = dict(raw)
        raw[category] = list(items)
        st.set(SETTINGS_KEY, raw)
        st.save()
        return True
    except Exception:
        _log.exception("silent exception in _persist_items")
        return False


def _mark_unit(unit=None):
    try:
        _settings().set(_UNIT_KEY, str(unit or _target_unit()))
        _settings().save()
    except Exception:
        _log.exception("silent exception in _mark_unit")

CATEGORIES = ("symbol", "ramp", "text")

CATEGORY_TITLES = {
    "symbol": "符号",
    "ramp": "色带",
    "label": "标注",
    "text": "文本格式",
}

SETTINGS_KEY = "style_library"

_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


_CHANGE_LISTENERS = []


def on_changed(callback):
    try:
        if callback not in _CHANGE_LISTENERS:
            _CHANGE_LISTENERS.append(callback)
    except Exception:
        _log.exception("silent exception in on_changed")


def off_changed(callback):
    try:
        _CHANGE_LISTENERS.remove(callback)
    except Exception:
        _log.exception("silent exception in off_changed")


def notify_changed():
    for cb in list(_CHANGE_LISTENERS):
        try:
            cb()
        except Exception:
            _log.exception("silent exception in notify_changed")


_SIZE_SPEC_PLACEHOLDER = {"type": "float", "default": 1.0,
                          "min": 0.05, "max": 400.0, "decimals": 2,
                          "suffix": ""}

SCHEMA = {
    "symbol": {
        "kind": {"type": "choice", "default": "point",
                 "options": ("point", "line", "polygon")},
        "fill": {"type": "color", "default": "#4C9BE8"},
        "stroke": {"type": "color", "default": "#1B2430"},
        "width": _SIZE_SPEC_PLACEHOLDER,
        "size": _SIZE_SPEC_PLACEHOLDER,
        "fill_alpha": {"type": "float", "default": 1.0,
                       "min": 0.0, "max": 1.0, "decimals": 2},
        "line_style": {"type": "choice", "default": "solid",
                       "options": _spec.LINE_STYLES},
        "fill_style": {"type": "choice", "default": "solid",
                       "options": _spec.FILL_STYLES},
        "cap": {"type": "choice", "default": _spec.CAP_DEFAULT,
                "options": _spec.CAPS},
        "join": {"type": "choice", "default": _spec.JOIN_DEFAULT,
                 "options": _spec.JOINS},
    },
    "label": {
        "placement": {"type": "choice", "default": "auto",
                      "options": ("auto", "right", "top", "bottom",
                                  "left", "center")},
        "offset_x": {"type": "float", "default": 0.0,
                     "min": -50.0, "max": 50.0, "suffix": " px"},
        "offset_y": {"type": "float", "default": 0.0,
                     "min": -50.0, "max": 50.0, "suffix": " px"},
        "min_size_px": {"type": "float", "default": 0.0,
                        "min": 0.0, "max": 500.0, "suffix": " px"},
        "repeat_px": {"type": "float", "default": 0.0,
                      "min": 0.0, "max": 2000.0, "suffix": " px"},
        "max_labels": {"type": "int", "default": 0, "min": 0,
                       "max": 1000000},
    },
    "text": {
        "font_family": {"type": "str", "default": ""},
        "font_size": {"type": "float", "default": 9.0,
                      "min": 4.0, "max": 72.0, "suffix": " pt"},
        "bold": {"type": "bool", "default": False},
        "italic": {"type": "bool", "default": False},
        "color": {"type": "color", "default": "#FFFFFF"},
        "halo_color": {"type": "color", "default": "#000000"},
        "halo_width": {"type": "float", "default": 1.6,
                       "min": 0.0, "max": 10.0, "suffix": " px"},
        "buffer": {"type": "float", "default": 2.0,
                   "min": 0.0, "max": 20.0, "suffix": " px"},
    },
    "ramp": {},
}


def _size_spec(px_default, px_min, px_max):
    u = _target_unit()
    return {"type": "float",
            "default": _in_unit(px_default, u),
            "min": _in_unit(px_min, u),
            "max": _in_unit(px_max, u),
            "decimals": 3 if u == "in" else 2,
            "suffix": " " + u}


def schema(category):
    sch = SCHEMA.get(category, {})
    if category == "symbol":
        sch = dict(sch)
        sch["width"] = _size_spec(_DEFAULT_LINE_WIDTH_PX, 0.2, 20.0)
        sch["size"] = _size_spec(4.0, 0.5, 60.0)
    return sch


RAMP_STOPS = {
    "greys": [
        "#F7F7F7", "#D9D9D9", "#BDBDBD", "#969696",
        "#737373", "#525252", "#252525"
    ],
    "blues": [
        "#EFF3FF", "#C6DBEF", "#9ECAE1", "#6BAED6",
        "#4292C6", "#2171B5", "#084594"
    ],
    "greens": [
        "#EDF8E9", "#C7E9C0", "#A1D99B", "#74C476",
        "#41AB5D", "#238B45", "#005A32"
    ],
    "reds": [
        "#FEE5D9", "#FCBBA1", "#FC9272", "#FB6A4A",
        "#EF3B2C", "#CB181D", "#99000D"
    ],
    "oranges": [
        "#FEEDDE", "#FDD0A2", "#FDAE6B", "#FD8D3C",
        "#F16913", "#D94801", "#8C2D04"
    ],
    "purples": [
        "#F2F0F7", "#DADAEB", "#BCBDDC", "#9E9AC8",
        "#807DBA", "#6A51A3", "#4A1486"
    ],
    "ylgn": [
        "#FFFFCC", "#D9F0A3", "#ADDD8E", "#78C679",
        "#41AB5D", "#238443", "#005A32"
    ],
    "ylgnbu": [
        "#FFFFCC", "#C7E9B4", "#7FCDBB", "#41B6C4",
        "#1D91C0", "#225EA8", "#0C2C84"
    ],
    "ylorrd": [
        "#FFFFB2", "#FED976", "#FEB24C", "#FD8D3C",
        "#FC4E2A", "#E31A1C", "#B10026"
    ],
    "orrd": [
        "#FEF0D9", "#FDD49E", "#FDBB84", "#FC8D59",
        "#EF6548", "#D7301F", "#990000"
    ],
    "bugn": [
        "#EDF8FB", "#CCECE6", "#99D8C9", "#66C2A4",
        "#41AE76", "#238B45", "#005824"
    ],
    "gnbu": [
        "#F0F9E8", "#CCEBC5", "#A8DDB5", "#7BCCC4",
        "#4EB3D3", "#2B8CBE", "#08589E"
    ],
    "bupu": [
        "#EDF8FB", "#BFD3E6", "#9EBCDA", "#8C96C6",
        "#8C6BB1", "#88419D", "#6E016B"
    ],
    "pubu": [
        "#F1EEF6", "#D0D1E6", "#A6BDDB", "#74A9CF",
        "#3690C0", "#0570B0", "#034E7B"
    ],
    "viridis": [
        "#440154", "#414487", "#2A788E", "#22A884",
        "#7AD151", "#FDE725"
    ],
    "magma": [
        "#000004", "#3B0F70", "#8C2981", "#DE4968",
        "#FE9F6D", "#FCFDBF"
    ],
    "inferno": [
        "#000004", "#420A68", "#932667", "#DD513A",
        "#FCA50A", "#FCFFA4"
    ],
    "plasma": [
        "#0D0887", "#6A00A8", "#B12A90", "#E16462",
        "#FCA636", "#F0F921"
    ],
    "cividis": [
        "#00224E", "#35456C", "#666970", "#A59C74",
        "#FEE838"
    ],
    "rdbu": [
        "#B2182B", "#EF8A62", "#FDDBC7", "#F7F7F7",
        "#D1E5F0", "#67A9CF", "#2166AC"
    ],
    "rdylbu": [
        "#D73027", "#FC8D59", "#FEE090", "#FFFFBF",
        "#E0F3F8", "#91BFDB", "#4575B4"
    ],
    "rdylgn": [
        "#D73027", "#FC8D59", "#FEE08B", "#FFFFBF",
        "#D9EF8B", "#91CF60", "#1A9850"
    ],
    "rdgy": [
        "#B2182B", "#EF8A62", "#FDDBC7", "#FFFFFF",
        "#E0E0E0", "#999999", "#4D4D4D"
    ],
    "prgn": [
        "#762A83", "#AF8DC3", "#E7D4E8", "#F7F7F7",
        "#D9F0D3", "#7FBF7B", "#1B7837"
    ],
    "piyg": [
        "#C51B7D", "#E9A3C9", "#FDE0EF", "#F7F7F7",
        "#E6F5D0", "#A1D76A", "#4D9221"
    ],
    "puor": [
        "#B35806", "#F1A340", "#FEE0B6", "#F7F7F7",
        "#D8DAEB", "#998EC3", "#542788"
    ],
    "brbg": [
        "#8C510A", "#D8B365", "#F6E8C3", "#F5F5F5",
        "#C7EAE5", "#5AB4AC", "#01665E"
    ],
    "bwr": [
        "#2166AC", "#67A9CF", "#D1E5F0", "#F7F7F7",
        "#FDDBC7", "#EF8A62", "#B2182B"
    ],
    "terrain": [
        "#006147", "#10824A", "#8CB25A", "#D6C97B",
        "#C4985C", "#966944", "#785C4E", "#FAFAFA"
    ],
    "elevation": ["#00803C", "#D2BE82", "#A06E46", "#FFFFFF"],
    "ndvi": ["#8C5A28", "#DCD278", "#82C85A", "#146E32"],
    "spectral": [
        "#2B5DA8", "#3E9BC4", "#8CCB6B", "#F2E05A",
        "#E89B3C", "#C4423A"
    ],
}


RAMP_TITLES = {
    "greys": "灰阶",
    "blues": "蓝",
    "greens": "绿",
    "reds": "红",
    "oranges": "橙",
    "purples": "紫",
    "ylgn": "黄-绿",
    "ylgnbu": "黄-绿-蓝",
    "ylorrd": "黄-橙-红",
    "orrd": "橙-红",
    "bugn": "蓝-绿",
    "gnbu": "绿-蓝",
    "bupu": "蓝-紫",
    "pubu": "紫-蓝",
    "viridis": "紫-绿-黄",
    "magma": "黑-紫-黄",
    "inferno": "黑-紫-橙",
    "plasma": "蓝-绿-黄",
    "cividis": "蓝-灰-黄",
    "rdbu": "红-白-蓝",
    "rdylbu": "红-黄-蓝",
    "rdylgn": "红-黄-绿",
    "rdgy": "红-白-灰",
    "prgn": "紫-白-绿",
    "piyg": "粉-白-绿",
    "puor": "紫-白-橙",
    "brbg": "褐-白-青",
    "bwr": "蓝-白-红",
    "terrain": "地形",
    "elevation": "高程",
    "ndvi": "植被",
    "spectral": "光谱",
}


LEGACY_STOPS = {
    "黄蓝": [
        "#F7F7B8", "#C9E4A4", "#8FCDA4", "#5AA6C2",
        "#2C6BA8", "#20386E"
    ],
    "蓝绿": [
        "#EAF6F2", "#BEE3D4", "#7FC7B0", "#3E9C8C",
        "#1C6B70"
    ],
    "橙红": [
        "#FFF3E0", "#FDD49E", "#FC8D59", "#D94801",
        "#7F2704"
    ],
    "灰阶": [
        "#F2F2F2", "#C4C4C4", "#969696", "#616161",
        "#2B2B2B"
    ],
    "红蓝": [
        "#B2182B", "#EF8A62", "#F7F7F7", "#67A9CF",
        "#2166AC"
    ],
    "紫绿": [
        "#762A83", "#AF8DC3", "#E7D4E8", "#D9F0D3",
        "#7FBF7B", "#1B7837"
    ],
}

LEGACY_TITLES = {
    "黄蓝": "黄蓝渐变",
    "蓝绿": "蓝绿渐变",
    "橙红": "橙红渐变",
    "灰阶": "灰阶",
    "红蓝": "红蓝分歧",
    "紫绿": "紫绿分歧",
}



def ramp_keys():
    return list(RAMP_STOPS)


def ramp_stops(key):
    key = str(key or "")
    return list(RAMP_STOPS.get(key) or LEGACY_STOPS.get(key) or ())


def ramp_title(key):
    key = str(key or "")
    return RAMP_TITLES.get(key) or LEGACY_TITLES.get(key) or key


def _s(key, title, kind, fill, stroke, width, size, alpha):
    return {"key": key, "title": title, "kind": kind, "fill": fill,
            "stroke": stroke, "width": float(width), "size": float(size),
            "fill_alpha": alpha}


_SYMBOL_BUILTIN = [
    _s("point_standard", "标准点", "point", "#4C9BE8", "#10305A", 1.0, 6.0, 1.0),
    _s("point_small", "小点", "point", "#4C9BE8", "#10305A", 1.0, 3.5, 1.0),
    _s("point_emphasis", "强调点", "point", "#E86A6A", "#5A1010", 1.4, 8.0, 1.0),
    _s("point_muted", "淡灰点", "point", "#8E9BAF", "#3A4350", 1.0, 5.0, 0.9),
    _s("line_standard", "标准线", "line", "#4C9BE8", "#4C9BE8", 1.6, 4.0, 1.0),
    _s("line_main", "主线", "line", "#1B2430", "#1B2430", 2.4, 4.0, 1.0),
    _s("line_hair", "细辅助线", "line", "#8E9BAF", "#8E9BAF", 1.0, 4.0, 1.0),
    _s("line_emphasis", "强调线", "line", "#E86A6A", "#E86A6A", 2.0, 4.0, 1.0),
    _s("polygon_standard", "标准面", "polygon", "#4C9BE8", "#10305A", 1.0, 4.0, 0.45),
    _s("polygon_light", "淡填充面", "polygon", "#5FBF6A", "#1E4A26", 1.0, 4.0, 0.25),
    _s("polygon_solid", "实色面", "polygon", "#C08A5E", "#4A3220", 1.0, 4.0, 0.60),
    _s("polygon_highlight", "高亮面", "polygon", "#F2A03D", "#5A3200", 1.4, 4.0, 0.35),
]

_LABEL_BUILTIN = [
    {"key": "label_auto", "title": "自动放置", "placement": "auto",
     "offset_x": 0.0, "offset_y": 0.0, "min_size_px": 0.0,
     "repeat_px": 0.0, "max_labels": 0},
    {"key": "label_point_right", "title": "点右侧", "placement": "right",
     "offset_x": 4.0, "offset_y": 0.0, "min_size_px": 0.0,
     "repeat_px": 0.0, "max_labels": 0},
    {"key": "label_point_top", "title": "点上方", "placement": "top",
     "offset_x": 0.0, "offset_y": -4.0, "min_size_px": 0.0,
     "repeat_px": 0.0, "max_labels": 0},
    {"key": "label_line_follow", "title": "沿线重复", "placement": "center",
     "offset_x": 0.0, "offset_y": 0.0, "min_size_px": 0.0,
     "repeat_px": 120.0, "max_labels": 0},
    {"key": "label_big_polygon", "title": "大面标注（≥40px）",
     "placement": "center", "offset_x": 0.0, "offset_y": 0.0,
     "min_size_px": 40.0, "repeat_px": 0.0, "max_labels": 0},
    {"key": "label_capped", "title": "每层最多 200 个", "placement": "auto",
     "offset_x": 0.0, "offset_y": 0.0, "min_size_px": 0.0,
     "repeat_px": 0.0, "max_labels": 200},
]

_TEXT_BUILTIN = [
    {"key": "text_halo_white", "title": "白字黑晕", "font_family": "",
     "font_size": 9.0, "bold": False, "italic": False, "color": "#FFFFFF",
     "halo_color": "#000000", "halo_width": 1.6, "buffer": 2.0},
    {"key": "text_dark", "title": "深色字（浅底）", "font_family": "",
     "font_size": 9.0, "bold": False, "italic": False, "color": "#1B2430",
     "halo_color": "#FFFFFF", "halo_width": 1.6, "buffer": 2.0},
    {"key": "text_bold", "title": "粗体白字", "font_family": "",
     "font_size": 10.0, "bold": True, "italic": False, "color": "#FFFFFF",
     "halo_color": "#000000", "halo_width": 2.0, "buffer": 2.5},
    {"key": "text_emphasis", "title": "强调橙字", "font_family": "",
     "font_size": 11.0, "bold": True, "italic": False, "color": "#F2A03D",
     "halo_color": "#2A1A00", "halo_width": 2.0, "buffer": 2.0},
    {"key": "text_italic", "title": "斜体标注", "font_family": "",
     "font_size": 9.0, "bold": False, "italic": True, "color": "#EAF2FF",
     "halo_color": "#000000", "halo_width": 1.4, "buffer": 2.0},
    {"key": "text_serif", "title": "衬线字体", "font_family": "Times New Roman",
     "font_size": 10.0, "bold": False, "italic": False, "color": "#FFFFFF",
     "halo_color": "#000000", "halo_width": 1.6, "buffer": 2.0},
]


def _ramp_builtin():
    out = []
    for k in ramp_keys():
        out.append({"key": k, "title": RAMP_TITLES.get(k, k)})
    return out


def builtin_items(category):
    if category == "symbol":
        src = _SYMBOL_BUILTIN
    elif category == "label":
        src = _LABEL_BUILTIN
    elif category == "text":
        src = _TEXT_BUILTIN
    elif category == "ramp":
        src = _ramp_builtin()
    else:
        return []
    out = []
    for it in src:
        d = dict(it)
        if category == "symbol":
            d = _px_item_to_unit(d, _target_unit())
        d["builtin"] = True
        out.append(d)
    return out


def _builtin_map():
    return {c: builtin_items(c) for c in CATEGORIES}


BUILTIN = _builtin_map()


def validate(category, item, partial=False):
    sch = schema(category)
    out = {}
    if not partial:
        for name, spec in sch.items():
            out[name] = spec["default"]
    for name, spec in sch.items():
        if name not in item:
            continue
        v = item[name]
        t = spec["type"]
        try:
            if t == "color":
                s = str(v).strip()
                if not _HEX_RE.match(s):
                    raise ValueError("颜色必须是 #RRGGBB")
                if len(s) == 4:
                    s = "#" + "".join(c * 2 for c in s[1:])
                out[name] = s.upper()
            elif t == "float":
                f = float(v)
                if f != f:
                    raise ValueError
                out[name] = round(min(max(f, spec["min"]),
                                      spec["max"]), 4)
            elif t == "int":
                out[name] = int(min(max(int(v), spec["min"]), spec["max"]))
            elif t == "bool":
                out[name] = bool(v)
            elif t == "choice":
                s = str(v)
                out[name] = s if s in spec["options"] \
                    else spec["default"]
            else:
                out[name] = str(v)
        except Exception:
            _log.exception("silent exception in validate")
            if not partial:
                out[name] = spec["default"]
            else:
                out.pop(name, None)
    return out


def make(category, key="", title="", **params):
    if category not in CATEGORIES:
        raise ValueError("未知分类：%s" % category)
    d = validate(category, params)
    d["key"] = str(key or _auto_key(category))
    d["title"] = str(title or CATEGORY_TITLES.get(category, category))
    d["builtin"] = False
    return d


def _auto_key(category):
    n = 1
    used = {it["key"] for it in items(category)}
    while True:
        k = "%s_user_%d" % (category, n)
        if k not in used:
            return k
        n += 1


def title_of(category, key):
    for it in items(category):
        if it["key"] == key:
            return it["title"]
    return key


def _settings():
    from ggis.core.app import settings
    return settings


def _raw():
    try:
        d = _settings().get(SETTINGS_KEY, None)
    except Exception:
        _log.exception("silent exception in _raw")
        d = None
    if not isinstance(d, dict):
        return {}
    out = {}
    for c, lst in d.items():
        if isinstance(lst, list):
            out[c] = [x for x in lst if isinstance(x, dict)]
    return out


def user_items(category):
    out = []
    raw_list = _raw().get(category, [])
    if category == "symbol" and not _unit_is_current():
        src, dst = _stored_unit(), _target_unit()
        if src == "px":
            raw_list = [_px_item_to_unit(it, dst) for it in raw_list]
            changed = raw_list != list(_raw().get(category, []))
        else:
            raw_list, changed = _migrate_items(raw_list, src, dst)
        if changed and _persist_items(category, raw_list):
            _mark_unit(dst)
    for it in raw_list:
        key = str(it.get("key") or "")
        if not key:
            continue
        d = validate(category, it)
        d["key"] = key
        d["title"] = str(it.get("title") or key)
        d["builtin"] = False
        out.append(d)
    return out


def items(category):
    out = builtin_items(category)
    index = {it["key"]: i for i, it in enumerate(out)}
    for it in user_items(category):
        if it["key"] in index:
            merged = dict(out[index[it["key"]]])
            merged.update(it)
            merged["builtin"] = False
            out[index[it["key"]]] = merged
        else:
            out.append(it)
    return out


def find(category, key):
    for it in items(category):
        if it["key"] == key:
            return it
    return None


def _write_raw(raw):
    try:
        _settings().set(SETTINGS_KEY, raw)
        _settings().save()
    except Exception:
        _log.exception("silent exception in _write_raw")
        return False
    notify_changed()
    return True


def add(category, item):
    d = dict(item)
    d["builtin"] = False
    _mark_unit()
    raw = _raw()
    lst = list(raw.get(category, []))
    key = d["key"]
    for i, old in enumerate(lst):
        if str(old.get("key")) == key:
            lst[i] = d
            break
    else:
        lst.append(d)
    raw[category] = lst
    _write_raw(raw)
    return d


def update(category, key, **params):
    cur = find(category, key)
    if cur is None:
        return None
    cur = dict(cur)
    if "title" in params:
        cur["title"] = str(params.pop("title"))
    cur.update(validate(category, params, partial=True))
    cur["builtin"] = False
    return add(category, cur)


def remove(category, key):
    raw = _raw()
    lst = list(raw.get(category, []))
    keep = [x for x in lst if str(x.get("key")) != key]
    if len(keep) == len(lst):
        return False
    raw[category] = keep
    return _write_raw(raw)


def rename(category, key, title):
    cur = find(category, key)
    if cur is None:
        return None
    cur = dict(cur)
    cur["title"] = str(title)
    cur["builtin"] = False
    return add(category, cur)


def reset_user(category=None):
    raw = _raw()
    if category is None:
        raw = {}
    else:
        raw.pop(category, None)
    return _write_raw(raw)


def export_json(categories=None, include_builtin=False):
    cats = list(categories or CATEGORIES)
    data = {}
    for c in cats:
        lst = items(c) if include_builtin else user_items(c)
        if lst:
            data[c] = lst
    return json.dumps({"version": 2, "styles": data},
                      ensure_ascii=False, indent=2)


def import_json(text, merge=True):
    try:
        obj = json.loads(text)
    except Exception as e:
        raise ValueError("不是合法的 JSON：%s" % e)
    if not isinstance(obj, dict):
        raise ValueError("JSON 顶层必须是对象")
    styles = obj.get("styles", obj)
    if not isinstance(styles, dict):
        raise ValueError("缺少 styles 字段")
    try:
        _ver = int(obj.get("version") or 1)
    except Exception:
        _log.exception("silent exception in import_json")
        _ver = 1
    if not merge:
        reset_user()
    n = 0
    for c in CATEGORIES:
        lst = styles.get(c)
        if not isinstance(lst, list):
            continue
        for it in lst:
            if not isinstance(it, dict):
                continue
            if c == "symbol" and _ver < 2:
                it = _px_item_to_unit(it)
            d = validate(c, it)
            key = str(it.get("key") or "")
            d["key"] = key or _auto_key(c)
            d["title"] = str(it.get("title") or d["key"])
            d["builtin"] = False
            add(c, d)
            n += 1
    return n
