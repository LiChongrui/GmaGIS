# -*- coding: utf-8 -*-

import math

import numpy as np
import logging
_log = logging.getLogger("gmagis")

__all__ = [
    "MeasureResult", "METHOD_AUTO", "METHOD_GEODESIC", "METHOD_PLANAR",
    "geod_default", "auto_method", "is_geographic_crs",
    "geodesic_length", "geodesic_area", "geodesic_azimuth",
    "planar_length", "planar_area",
    "measure_length", "measure_area", "measure_perimeter",
    "measure_angle", "segment_lengths", "measure_geometry",
    "format_length", "format_area", "format_angle", "format_azimuth",
    "REF_EQUATORIAL_DEGREE", "REF_MERIDIONAL_DEGREE", "REF_QUARTER_MERIDIAN",
]

METHOD_AUTO = "auto"
METHOD_GEODESIC = "geodesic"
METHOD_PLANAR = "planar"

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
REF_EQUATORIAL_DEGREE = 111319.4907932736
REF_MERIDIONAL_DEGREE = 110574.3885578
REF_QUARTER_MERIDIAN = 10001965.7293

_WGS84_GEOD = None
_GEOD_CACHE = {}
_TRANSFORMER_CACHE = {}


def _pyproj_crs(crs):
    if crs is None:
        return None
    if hasattr(crs, "to_pyproj"):
        try:
            return crs.to_pyproj()
        except Exception:
            _log.exception("silent exception in _pyproj_crs")
            return None
    if hasattr(crs, "is_geographic"):
        return crs
    try:
        from pyproj import CRS
        return CRS.from_user_input(crs)
    except Exception:
        _log.exception("silent exception in _pyproj_crs")
        return None


def is_geographic_crs(crs):
    p = _pyproj_crs(crs)
    if p is None:
        return True
    try:
        return bool(p.is_geographic)
    except Exception:
        _log.exception("silent exception in is_geographic_crs")
        return True


def _is_plain_wgs84(p):
    if p is None:
        return True
    try:
        if not p.is_geographic:
            return False
    except Exception:
        _log.exception("silent exception in _is_plain_wgs84")
        return True
    try:
        return int(p.to_epsg()) == 4326
    except Exception:
        _log.exception("silent exception in _is_plain_wgs84")
        return False


def auto_method(crs):
    return METHOD_GEODESIC if is_geographic_crs(crs) else METHOD_PLANAR


def _resolve_method(method, crs):
    m = str(method or METHOD_AUTO).lower()
    if m not in (METHOD_AUTO, METHOD_GEODESIC, METHOD_PLANAR):
        m = METHOD_AUTO
    return auto_method(crs) if m == METHOD_AUTO else m


def geod_default():
    global _WGS84_GEOD
    if _WGS84_GEOD is None:
        _WGS84_GEOD = geod_for("WGS84")
    return _WGS84_GEOD


def geod_for(ellps):
    key = str(ellps or "WGS84")
    g = _GEOD_CACHE.get(key)
    if g is None:
        from pyproj import Geod
        g = Geod(ellps=key)
        _GEOD_CACHE[key] = g
    return g


def _transformer(p):
    key = p.to_string() if hasattr(p, "to_string") else str(p)
    tf = _TRANSFORMER_CACHE.get(key)
    if tf is None:
        from pyproj import Transformer
        tf = Transformer.from_crs(p, "EPSG:4326", always_xy=True)
        _TRANSFORMER_CACHE[key] = tf
    return tf


def _to_lonlat(xs, ys, crs):
    p = _pyproj_crs(crs)
    if _is_plain_wgs84(p):
        return xs, ys
    try:
        return _transformer(p).transform(xs, ys)
    except Exception:
        _log.exception("silent exception in _to_lonlat")
        return xs, ys


def _meters_per_unit(crs):
    if crs is None:
        return 1.0
    try:
        return float(crs.meters_per_unit())
    except Exception:
        _log.exception("silent exception in _meters_per_unit")
    p = _pyproj_crs(crs)
    if p is None:
        return 1.0
    try:
        if p.is_geographic:
            return 111320.0
    except Exception:
        _log.exception("silent exception in _meters_per_unit")
    try:
        return float(p.axis_info[0].unit_conversion_factor)
    except Exception:
        _log.exception("silent exception in _meters_per_unit")
        return 1.0


class MeasureResult:

    __slots__ = ("kind", "value", "method", "text", "parts")

    def __init__(self, kind, value, method=METHOD_GEODESIC, text="",
                 parts=None):
        self.kind = str(kind)
        self.value = float(value)
        self.method = str(method)
        self.text = text or self._format()
        self.parts = list(parts) if parts else []

    def _format(self):
        if self.kind == "length":
            return format_length(self.value)
        if self.kind == "area":
            return format_area(self.value)
        if self.kind == "angle":
            return format_angle(self.value)
        return "%.2f" % self.value

    def geodesic(self):
        return self.method == METHOD_GEODESIC

    def __repr__(self):
        return "MeasureResult(%s, %.3f, %s)" % (self.kind, self.value,
                                                self.method)


def _length_result(value, method, parts=None):
    return MeasureResult("length", value, method, "", parts)


def _area_result(value, method, parts=None):
    return MeasureResult("area", value, method, "", parts)


def _as_xy(coords):
    if coords is None:
        return np.zeros((0, 2), dtype=np.float64)
    if isinstance(coords, np.ndarray):
        a = np.asarray(coords, dtype=np.float64)
        return a.reshape(-1, 2) if a.ndim == 1 else a[:, :2]
    try:
        return np.asarray([(float(p[0]), float(p[1])) for p in coords],
                          dtype=np.float64).reshape(-1, 2)
    except Exception:
        _log.exception("silent exception in _as_xy")
        return np.zeros((0, 2), dtype=np.float64)


def _iter_line_parts(geom):
    if geom is None:
        return
    if isinstance(geom, (list, tuple, np.ndarray)) and not hasattr(
            geom, "geom_type"):
        a = _as_xy(geom)
        if a.shape[0] >= 2:
            yield a
        return
    t = getattr(geom, "geom_type", "")
    if t in ("LineString", "LinearRing"):
        yield np.asarray(geom.coords, dtype=np.float64)[:, :2]
    elif t in ("MultiLineString", "MultiPolygon", "GeometryCollection"):
        for g in geom.geoms:
            yield from _iter_line_parts(g)
    elif t == "Polygon":
        yield np.asarray(geom.exterior.coords, dtype=np.float64)[:, :2]
        for r in geom.interiors:
            yield np.asarray(r.coords, dtype=np.float64)[:, :2]


def _iter_rings(geom):
    if geom is None:
        return
    if isinstance(geom, (list, tuple, np.ndarray)) and not hasattr(
            geom, "geom_type"):
        a = _as_xy(geom)
        if a.shape[0] >= 3:
            yield a, False
        return
    t = getattr(geom, "geom_type", "")
    if t == "Polygon":
        yield np.asarray(geom.exterior.coords, dtype=np.float64)[:, :2], False
        for r in geom.interiors:
            yield np.asarray(r.coords, dtype=np.float64)[:, :2], True
    elif t in ("MultiPolygon", "GeometryCollection"):
        for g in geom.geoms:
            yield from _iter_rings(g)


def geodesic_length(coords, crs=None, geod=None):
    g = geod or geod_default()
    if isinstance(coords, (list, tuple)) and coords and \
            hasattr(coords[0], "geom_type"):
        parts = []
        for c in coords:
            parts.extend(_iter_line_parts(c))
    else:
        parts = list(_iter_line_parts(coords))
    total = 0.0
    for part in parts:
        if part.shape[0] < 2:
            continue
        lons, lats = _to_lonlat(part[:, 0], part[:, 1], crs)
        with np.errstate(invalid="ignore"):
            _az1, _az2, d = g.inv(np.asarray(lons, dtype=np.float64)[:-1],
                                  np.asarray(lats, dtype=np.float64)[:-1],
                                  np.asarray(lons, dtype=np.float64)[1:],
                                  np.asarray(lats, dtype=np.float64)[1:])
        total += float(np.nansum(d))
    return total


def geodesic_area(geom, crs=None, geod=None):
    g = geod or geod_default()
    total = 0.0
    for ring, hole in _iter_rings(geom):
        if ring.shape[0] < 3:
            continue
        lons, lats = _to_lonlat(ring[:, 0], ring[:, 1], crs)
        try:
            a, _p = g.polygon_area_perimeter(
                np.asarray(lons, dtype=np.float64),
                np.asarray(lats, dtype=np.float64))
        except Exception:
            _log.exception("silent exception in geodesic_area")
            continue
        a = abs(float(a))
        total += -a if hole else a
    return abs(total)


def geodesic_azimuth(p1, p2, crs=None, geod=None):
    g = geod or geod_default()
    xs = np.asarray([p1[0], p2[0]], dtype=np.float64)
    ys = np.asarray([p1[1], p2[1]], dtype=np.float64)
    lons, lats = _to_lonlat(xs, ys, crs)
    az, _baz, _d = g.inv(float(lons[0]), float(lats[0]),
                         float(lons[1]), float(lats[1]))
    a = float(az) % 360.0
    return a


def planar_length(coords, crs=None):
    total = 0.0
    for part in _iter_line_parts(coords):
        if part.shape[0] < 2:
            continue
        d = np.hypot(np.diff(part[:, 0]), np.diff(part[:, 1]))
        total += float(np.nansum(d))
    return total * _meters_per_unit(crs)


def planar_area(geom, crs=None):
    total = 0.0
    for ring, hole in _iter_rings(geom):
        if ring.shape[0] < 3:
            continue
        x = ring[:, 0]
        y = ring[:, 1]
        a = 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
        total += -a if hole else a
    m = _meters_per_unit(crs)
    return abs(total) * m * m


def measure_length(geom, crs=None, method=METHOD_AUTO, geod=None,
                   with_parts=False):
    m = _resolve_method(method, crs)
    if m == METHOD_GEODESIC:
        parts = [geodesic_length(p, crs, geod)
                 for p in _iter_line_parts(geom)]
        value = float(sum(parts))
    else:
        parts = [planar_length(p, crs) for p in _iter_line_parts(geom)]
        value = float(sum(parts))
    return _length_result(value, m, parts if with_parts else None)


def measure_area(geom, crs=None, method=METHOD_AUTO, geod=None,
                 with_parts=False):
    m = _resolve_method(method, crs)
    if m == METHOD_GEODESIC:
        value = geodesic_area(geom, crs, geod)
        parts = None
    else:
        value = planar_area(geom, crs)
        parts = None
    return _area_result(value, m, parts if with_parts else None)


def measure_perimeter(geom, crs=None, method=METHOD_AUTO, geod=None):
    return measure_length(geom, crs, method, geod)


def segment_lengths(coords, crs=None, method=METHOD_AUTO, geod=None):
    m = _resolve_method(method, crs)
    a = _as_xy(coords)
    out = []
    if a.shape[0] < 2:
        return out
    if m == METHOD_GEODESIC:
        lons, lats = _to_lonlat(a[:, 0], a[:, 1], crs)
        g = geod or geod_default()
        _az1, _az2, d = g.inv(np.asarray(lons, float)[:-1],
                              np.asarray(lats, float)[:-1],
                              np.asarray(lons, float)[1:],
                              np.asarray(lats, float)[1:])
        for v in np.asarray(d, dtype=np.float64).ravel():
            out.append(_length_result(float(v), m))
    else:
        d = np.hypot(np.diff(a[:, 0]), np.diff(a[:, 1]))
        mul = _meters_per_unit(crs)
        for v in d:
            out.append(_length_result(float(v) * mul, m))
    return out


def measure_angle(p1, p2, p3, crs=None, method=METHOD_AUTO, geod=None):
    m = _resolve_method(method, crs)
    if m == METHOD_GEODESIC:
        g = geod or geod_default()
        az1 = geodesic_azimuth(p2, p1, crs, g)
        az2 = geodesic_azimuth(p2, p3, crs, g)
        d = (az2 - az1 + 180.0) % 360.0 - 180.0
        return MeasureResult("angle", abs(float(d)), m)
    v1 = (float(p1[0]) - float(p2[0]), float(p1[1]) - float(p2[1]))
    v2 = (float(p3[0]) - float(p2[0]), float(p3[1]) - float(p2[1]))
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 <= 0 or n2 <= 0:
        return MeasureResult("angle", 0.0, m)
    c = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    c = max(-1.0, min(1.0, c))
    return MeasureResult("angle", math.degrees(math.acos(c)), m)


def measure_geometry(geom, crs=None, method=METHOD_AUTO, geod=None):
    t = getattr(geom, "geom_type", "") or ""
    kind = "polygon" if ("Polygon" in t) else \
        ("line" if ("Line" in t or "Ring" in t) else "point")
    out = {"kind": kind, "length": None, "area": None}
    m = _resolve_method(method, crs)
    if kind == "polygon":
        out["length"] = measure_length(geom, crs, m, geod)
        out["area"] = measure_area(geom, crs, m, geod)
    elif kind == "line":
        out["length"] = measure_length(geom, crs, m, geod)
    return out


def format_length(meters, decimals=2):
    v = float(meters)
    if not math.isfinite(v):
        return "—"
    if abs(v) < 1000.0:
        return "%.*f m" % (decimals, v)
    return "%.*f km" % (decimals, v / 1000.0)


def format_area(square_meters, decimals=2):
    v = float(square_meters)
    if not math.isfinite(v):
        return "—"
    if abs(v) < 1e6:
        return "%.*f m²" % (decimals, v)
    return "%.*f km²" % (decimals, v / 1e6)


def format_angle(degrees, decimals=3):
    v = float(degrees)
    if not math.isfinite(v):
        return "—"
    return "%.*f°" % (decimals, v)


def format_azimuth(degrees, decimals=2):
    return "%.*f°" % (decimals, float(degrees) % 360.0)
