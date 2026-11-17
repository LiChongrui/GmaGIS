# -*- coding: utf-8 -*-

import json
import os
import logging
_log = logging.getLogger("gmagis")

_CONFIG_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "GmaGIS")
PATH = os.path.join(_CONFIG_DIR, "settings.json")

DEFAULTS = {
    "theme": "dark",
    "language": "system",
    "canvas_color": "",
    "project_title": "",
    "distance_unit": "Meters",
    "area_unit": "SquareMeters",
    "coord_precision": 6,
    "default_crs": "",
    "recent_projects": [],
    "browser_favorites": [],
    "recent_algorithms": [],
    "recent_colors": [],
    "user_ramps": {},
    "ramp_show_names": False,
    "crs/recent": [],
    "crs/custom": [],
    "ribbon_collapsed": False,
    "selection_fill_color": "#4DFFE14D",
    "selection_line_color": "#FFE14D",
    "selection_line_width": 2.0,
    "identify_tolerance_px": 5,
    "snap_tolerance_px": 8,
    "show_info_messages": False,
    "show_success_messages": False,
    "show_warning_messages": True,
    "show_critical_messages": True,
    "show_other_messages": True,
    "auto_save_enabled": True,
    "auto_save_interval_min": 1,
    "temp_layer_format": "GPKG",
    "temp_raster_format": "GTiff",
    "log_file": "",
    "measure_show_overlay": False,
    "render_antialias": True,
    "raster_resample_in": "nearest",
    "raster_resample_out": "nearest",
    "symbol_unit": "pt",
    "vector_lod_simplify": True,
    "vector_lod_tolerance_px": 1.2,
    "vector_tile_lod": False,
    "vector_tile_gpu": False,
    "vector_antialias_ss": 2,
    "cache_root": "",
    "render_backend": "gpu_tile",
}

_cache = None

_ephemeral = set()
_touched = set()


def _load():
    global _cache
    if _cache is None:
        _cache = dict(DEFAULTS)
        try:
            with open(PATH, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if k in DEFAULTS:
                        _cache[k] = v
        except Exception:
            _log.exception("silent exception in _load")
    return _cache


def _system_theme():
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion"
                    r"\Themes\Personalize") as k:
                val, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
                return "light" if int(val) else "dark"
        except Exception:
            _log.exception("silent exception in _system_theme")
    return "light"


def get(key, default=None):
    v = _load().get(key, DEFAULTS.get(key, default))
    if key == "theme" and v == "system":
        return _system_theme()
    return v


def default_crs():
    try:
        _auth = str(get("default_crs") or "").strip()
        if not _auth:
            return None
        from ggis.core.crs import GgsCrs
        _c = GgsCrs.from_user_input(_auth)
        return _c if (_c is not None and _c.is_valid()) else None
    except Exception:
        _log.exception("silent exception in settings.default_crs")
        return None


def get_disk(key, default=None):
    v = _read_disk().get(key)
    if v is None:
        return DEFAULTS.get(key, default)
    return v


def get_raw(key, default=None):
    return _load().get(key, DEFAULTS.get(key, default))


def reload():
    global _cache
    keep = {}
    if _cache:
        keep = {k: _cache[k] for k in _ephemeral if k in _cache}
    _cache = None
    d = _load()
    d.update(keep)


def set(key, value, persist=True):
    d = _load()
    d[key] = value
    if persist:
        _ephemeral.discard(key)
        _touched.add(key)
        save()
    else:
        _ephemeral.add(key)


def _read_disk():
    try:
        with open(PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, dict) else {}
    except Exception:
        _log.exception("silent exception in _read_disk")
        return {}


def save(commit_ephemeral=False):
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        d = _load()
        out = _read_disk()
        if commit_ephemeral:
            keys = {k for k in _touched} | {k for k in _ephemeral}
        else:
            keys = {k for k in _touched if k not in _ephemeral}
        if not keys and not out:
            return
        for k in keys:
            if k in d:
                out[k] = d[k]
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        if commit_ephemeral:
            _ephemeral.clear()
    except Exception:
        _log.exception("silent exception in save")


def all_settings():
    return dict(_load())


def reset(persist=True):
    global _cache
    _cache = dict(DEFAULTS)
    if persist:
        save()
