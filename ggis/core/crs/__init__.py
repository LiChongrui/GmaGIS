# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import threading
import logging
_log = logging.getLogger("gmagis")

try:
    from pyproj import CRS as _PyprojCRS
    from pyproj import Transformer as _Transformer
    _HAS_PYPROJ = True
except Exception:
    _log.exception("silent exception")
    _PyprojCRS = None
    _Transformer = None
    _HAS_PYPROJ = False

__all__ = ["GgsCoordinateReferenceSystem", "GgsCrs", "crs_key",
           "crs_pair_key", "needs_reproject", "crs_transformer",
           "convert_xy", "convert_bounds", "crs_scale_factor",
           "crs_proj_string", "crs_wkt_string"]

_AUTHID_MEMO = {}
_AUTHID_MEMO_CAP = 256


class GgsCoordinateReferenceSystem:

    __slots__ = ("_crs", "_authid", "_valid")

    def __init__(self, crs=None, authid=""):
        self._crs = crs
        self._valid = crs is not None
        self._authid = str(authid or "")
        if self._valid and not self._authid:
            self._authid = self._guess_authid()

    @classmethod
    def from_epsg(cls, code):
        if not _HAS_PYPROJ:
            return cls(None, "EPSG:%s" % code)
        try:
            return cls(_PyprojCRS.from_epsg(int(code)), "EPSG:%s" % code)
        except Exception:
            _log.exception("silent exception in from_epsg")
            return cls(None)

    @classmethod
    def from_wkt(cls, wkt):
        if not _HAS_PYPROJ or not wkt:
            return cls(None)
        try:
            return cls(_PyprojCRS.from_wkt(str(wkt)))
        except Exception:
            _log.exception("silent exception in from_wkt")
            return cls(None)

    @classmethod
    def from_user_input(cls, text):
        if text is None or text == "":
            return cls(None)
        if not _HAS_PYPROJ:
            return cls(None, str(text) if str(text).upper().startswith("EPSG")
                       else "")
        try:
            return cls(_PyprojCRS.from_user_input(text))
        except Exception:
            _log.exception("silent exception in from_user_input")
            return cls(None)

    @classmethod
    def from_proj(cls, proj4):
        return cls.from_user_input(proj4)

    def _guess_authid(self):
        try:
            srs = self._crs.srs or ""
        except Exception:
            _log.exception("silent exception in _guess_authid")
            srs = ""
        if srs:
            hit = _AUTHID_MEMO.get(srs)
            if hit is not None:
                return hit
        out = ""
        try:
            code = self._crs.to_epsg()
            if code:
                out = "EPSG:%d" % code
        except Exception:
            _log.exception("silent exception in _guess_authid")
        if not out:
            try:
                a = self._crs.to_authority()
                out = ("%s:%s" % (a[0], a[1])) if a else ""
            except Exception:
                _log.exception("silent exception in _guess_authid")
                out = ""
        if srs:
            if len(_AUTHID_MEMO) >= _AUTHID_MEMO_CAP:
                _AUTHID_MEMO.clear()
            _AUTHID_MEMO[srs] = out
        return out

    def is_valid(self):
        return bool(self._valid)

    def authid(self):
        return self._authid or (self._crs.srs if self._valid else "")

    def auth_code(self):
        a = self.authid() or ""
        return a if self._is_auth_code(a) else ""

    def description(self):
        try:
            return self._crs.name or self.authid()
        except Exception:
            _log.exception("silent exception in description")
            return self.authid()

    @staticmethod
    def _is_auth_code(text):
        s = (text or "").strip()
        if not s or len(s) > 32 or " " in s:
            return False
        head, sep, tail = s.partition(":")
        if not sep or not tail.isdigit():
            return False
        return bool(head) and head.isascii() \
            and head.replace("_", "").isalnum()

    def display_name(self):
        a = (self.authid() or "").strip()
        if self._is_auth_code(a):
            return a
        try:
            n = (self.description() or "").strip()
        except Exception:
            _log.exception("silent exception in display_name")
            n = ""
        if n.lower() in ("unknown", "undefined", "unnamed", "none"):
            n = ""
        return n

    def display_label(self):
        a = (self.authid() or "").strip()
        if self._is_auth_code(a):
            try:
                d = (self.description() or "").strip()
            except Exception:
                _log.exception("silent exception in display_label")
                d = ""
            return ("%s - %s" % (a, d)) if (d and d != a) else a
        return self.display_name()

    def to_epsg(self):
        try:
            return self._crs.to_epsg()
        except Exception:
            _log.exception("silent exception in to_epsg")
            return None

    def is_geographic(self):
        if not self._valid:
            return True
        try:
            return bool(self._crs.is_geographic)
        except Exception:
            _log.exception("silent exception in is_geographic")
            return True

    def is_projected(self):
        return self._valid and not self.is_geographic()

    def map_units(self):
        if not self._valid:
            return "unknown"
        try:
            unit = self._crs.axis_info[0].unit_name.lower()
        except Exception:
            _log.exception("silent exception in map_units")
            unit = ""
        if unit.startswith("degree"):
            return "degrees"
        if unit.startswith("metre") or unit.startswith("meter"):
            return "meters"
        if "foot" in unit or "feet" in unit:
            return "feet"
        return unit or "unknown"

    def unit_abbreviation(self):
        return {"degrees": "°", "meters": "m", "feet": "ft",
                "unknown": ""}.get(self.map_units(), "")

    def meters_per_unit(self):
        u = self.map_units()
        if u == "meters":
            return 1.0
        if u == "feet":
            return 0.3048
        if u == "degrees":
            return 111320.0
        return 1.0

    def to_pyproj(self):
        return self._crs

    def same_as(self, other):
        if not self._valid or other is None or not other.is_valid():
            return False
        ka, kb = crs_key(self), crs_key(other)
        if ka and kb:
            return ka == kb
        try:
            return bool(self._crs.equals(other.to_pyproj()))
        except Exception:
            _log.exception("silent exception in same_as")
            return False

    def __repr__(self):
        return "GgsCoordinateReferenceSystem(%r)" % (self.authid() or
                                                     "invalid")

    def __eq__(self, other):
        if not isinstance(other, GgsCoordinateReferenceSystem):
            return False
        if self.authid() and other.authid():
            return self.authid() == other.authid()
        return (self._crs is other._crs) if self._valid else False

    def __hash__(self):
        return hash(self.authid())

    def __bool__(self):
        return self._valid


GgsCrs = GgsCoordinateReferenceSystem


_TRANSFORMER_CACHE = {}
_TRANSFORMER_MAX = 64
_TRANSFORMER_LOCK = threading.Lock()


def _as_crs_obj(v):
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            c = GgsCrs.from_user_input(s)
        except Exception:
            _log.exception("silent exception in _as_crs_obj")
            return v
        return c if c is not None and c.is_valid() else v
    return v


def crs_key(crs):
    crs = _as_crs_obj(crs)
    if crs is None or not getattr(crs, "is_valid", lambda: False)():
        return ""
    a = crs.authid()
    if a:
        return a
    try:
        wkt = crs.to_pyproj().to_wkt()
    except Exception:
        _log.exception("silent exception in crs_key")
        return ""
    return "WKT:%d:%s" % (len(wkt), wkt[:160])


def crs_pair_key(src, dst):
    ks, kd = crs_key(src), crs_key(dst)
    if not ks or not kd or ks == kd:
        return ""
    return "%s>%s" % (ks, kd)


_PROJ4_WARNING_HINT = "PROJ string"


def crs_proj_string(crs):
    if crs is None or not getattr(crs, "is_valid", lambda: False)():
        return ""
    try:
        p = crs.to_pyproj()
    except Exception:
        _log.exception("silent exception in crs_proj_string")
        return ""
    if p is None:
        return ""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=".*%s.*" % _PROJ4_WARNING_HINT,
                category=UserWarning)
            return str(p.to_proj4() or "")
    except Exception:
        _log.exception("silent exception in crs_proj_string")
        return ""


def crs_wkt_string(crs, version=None):
    if crs is None or not getattr(crs, "is_valid", lambda: False)():
        return ""
    try:
        p = crs.to_pyproj()
    except Exception:
        _log.exception("silent exception in crs_wkt_string")
        return ""
    if p is None:
        return ""
    try:
        if version:
            return str(p.to_wkt(version=version) or "")
        return str(p.to_wkt() or "")
    except Exception:
        _log.exception("silent exception in crs_wkt_string")
        return ""


def needs_reproject(src, dst):
    ks, kd = crs_key(src), crs_key(dst)
    if not ks or not kd:
        return False
    return ks != kd


def crs_transformer(src, dst):
    src = _as_crs_obj(src)
    dst = _as_crs_obj(dst)
    if not needs_reproject(src, dst):
        return None
    key = (crs_key(src), crs_key(dst))
    hit = _TRANSFORMER_CACHE.get(key)
    if hit is not None:
        return hit
    if not _HAS_PYPROJ:
        return None
    try:
        tf = _Transformer.from_crs(src.to_pyproj(), dst.to_pyproj(),
                                   always_xy=True)
    except Exception:
        _log.exception("silent exception in crs_transformer")
        return None
    with _TRANSFORMER_LOCK:
        if len(_TRANSFORMER_CACHE) >= _TRANSFORMER_MAX:
            _TRANSFORMER_CACHE.clear()
        _TRANSFORMER_CACHE[key] = tf
    return tf


def convert_xy(xy, transformer):
    if transformer is None or xy is None:
        return xy
    try:
        n = len(xy)
    except TypeError:
        exc_note("convert_xy @ ggis/core/crs/__init__.py:537")
        return xy
    if n == 0:
        return xy
    import numpy as np
    a = np.asarray(xy, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] < 2:
        return xy
    try:
        tx, ty = transformer.transform(a[:, 0], a[:, 1])
    except Exception:
        _log.exception("silent exception in convert_xy")
        return xy
    out = a.copy()
    out[:, 0] = tx
    out[:, 1] = ty
    return out


BOUNDS_POINTS = 441

_BOUNDS_CACHE = {}
_BOUNDS_CACHE_MAX = 512

_BOUNDS_MISS = ("__miss__",)


def clear_bounds_cache():
    _BOUNDS_CACHE.clear()


def convert_bounds(bounds, transformer, points=BOUNDS_POINTS):
    if transformer is None or bounds is None:
        return bounds
    try:
        x0, y0, x1, y1 = (float(bounds[0]), float(bounds[1]),
                          float(bounds[2]), float(bounds[3]))
    except Exception:
        _log.exception("silent exception in convert_bounds")
        return bounds
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    key = (id(transformer),
           round(x0, 9), round(y0, 9), round(x1, 9), round(y1, 9),
           int(points))
    hit = _BOUNDS_CACHE.get(key)
    if hit is not None:
        return None if hit == _BOUNDS_MISS else hit
    out = _convert_bounds_uncached((x0, y0, x1, y1), transformer, points)
    if len(_BOUNDS_CACHE) >= _BOUNDS_CACHE_MAX:
        _BOUNDS_CACHE.clear()
    _BOUNDS_CACHE[key] = out if out is not None else _BOUNDS_MISS
    return out


def _convert_bounds_uncached(bounds, transformer, points=BOUNDS_POINTS):
    import numpy as np
    x0, y0, x1, y1 = bounds
    try:
        n = int(points)
    except Exception:
        _log.exception("silent exception in _convert_bounds_uncached")
        n = BOUNDS_POINTS
    k = max(2, int(round(np.sqrt(max(4, n)))))
    xs = np.linspace(x0, x1, k)
    ys = np.linspace(y0, y1, k)
    gx, gy = np.meshgrid(xs, ys)
    try:
        tx, ty = transformer.transform(gx.ravel(), gy.ravel())
    except Exception:
        _log.exception("silent exception in _convert_bounds_uncached")
        return bounds
    tx = np.asarray(tx, dtype=np.float64)
    ty = np.asarray(ty, dtype=np.float64)
    ok = np.isfinite(tx) & np.isfinite(ty)
    if not ok.any():
        return None
    tx = tx[ok]
    ty = ty[ok]
    return (float(tx.min()), float(ty.min()),
            float(tx.max()), float(ty.max()))


def crs_scale_factor(src, dst):
    if src is None or dst is None:
        return 1.0
    try:
        sm = float(src.meters_per_unit())
        dm = float(dst.meters_per_unit())
    except Exception:
        _log.exception("silent exception in crs_scale_factor")
        return 1.0
    if sm <= 0.0 or dm <= 0.0:
        return 1.0
    return dm / sm


_GEO_CRS = None


def _geo_crs():
    global _GEO_CRS
    if _GEO_CRS is None:
        _GEO_CRS = GgsCrs.from_epsg(4326)
    return _GEO_CRS


def crs_valid_extent(crs):
    if crs is None or not getattr(crs, "is_valid", lambda: False)():
        return None
    try:
        aou = crs.to_pyproj().area_of_use
    except Exception:
        _log.exception("silent exception in crs_valid_extent")
        return None
    if aou is None:
        return None
    try:
        w, s, e, n = aou.bounds
        return (float(w), float(s), float(e), float(n))
    except Exception:
        _log.exception("silent exception in crs_valid_extent")
        return None


def clip_rect_to_valid_extent(rect, crs):
    if rect is None or rect.is_empty():
        return rect
    if crs is None or not getattr(crs, "is_valid", lambda: False)():
        return rect
    ve = crs_valid_extent(crs)
    if ve is None:
        return rect
    w, s, e, n = ve
    try:
        from .extent import GgsRectangle
        if crs.is_geographic():
            valid = GgsRectangle(w, s, e, n)
        else:
            tf = crs_transformer(_geo_crs(), crs)
            if tf is None:
                return rect
            b = convert_bounds((w, s, e, n), tf)
            if b is None:
                return rect
            valid = GgsRectangle(b[0], b[1], b[2], b[3])
        out = rect.intersect(valid)
        return out if out is not None else rect
    except Exception:
        _log.exception("silent exception in clip_rect_to_valid_extent")
        return rect


