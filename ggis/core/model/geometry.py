# -*- coding: utf-8 -*-

try:
    from shapely.geometry.base import BaseGeometry as _BaseGeometry
    _HAS_SHAPELY = True
except Exception:
    _log.exception("silent exception")
    _BaseGeometry = object
    _HAS_SHAPELY = False

import logging
_log = logging.getLogger("gmagis")
from ggis.core.crs.extent import GgsRectangle

__all__ = ["GgsGeometry", "WKB_POINT", "WKB_LINESTRING", "WKB_POLYGON",
           "WKB_MULTIPOINT", "WKB_MULTILINESTRING", "WKB_MULTIPOLYGON",
           "geometry_type_name", "normalize_geometry_type", "base_kind", "is_multi",
           "geom_from_wkb", "geoms_from_wkb", "as_wkb_bytes",
           "explode", "split_geometry", "split_keep_main", "break_line",
           "combine_bounds_center", "nearest_point_on", "align_offset",
           "geoms_bbox_center"]

WKB_POINT = 1
WKB_LINESTRING = 2
WKB_POLYGON = 3
WKB_MULTIPOINT = 4
WKB_MULTILINESTRING = 5
WKB_MULTIPOLYGON = 6
WKB_GEOMETRYCOLLECTION = 7

_TYPE_TABLE = {
    "Point": (WKB_POINT, False, "point"),
    "LineString": (WKB_LINESTRING, False, "line"),
    "LinearRing": (WKB_LINESTRING, False, "line"),
    "Polygon": (WKB_POLYGON, False, "polygon"),
    "MultiPoint": (WKB_MULTIPOINT, True, "point"),
    "MultiLineString": (WKB_MULTILINESTRING, True, "line"),
    "MultiPolygon": (WKB_MULTIPOLYGON, True, "polygon"),
    "GeometryCollection": (WKB_GEOMETRYCOLLECTION, True, "collection"),
}

_DIM_SUFFIXES = (" ZM", " Z", " M")
_DIM_PREFIXES = ("3D ", "2.5D ", "Measured ")
_GDAL_NAME_MAP = {
    "point": "Point",
    "linestring": "LineString", "line string": "LineString",
    "linearring": "LinearRing", "linear ring": "LinearRing",
    "polygon": "Polygon",
    "multipoint": "MultiPoint", "multi point": "MultiPoint",
    "multilinestring": "MultiLineString",
    "multi line string": "MultiLineString",
    "multipolygon": "MultiPolygon", "multi polygon": "MultiPolygon",
    "geometrycollection": "GeometryCollection",
    "geometry collection": "GeometryCollection",
    "unknown": "", "unknown (any)": "", "none": "",
}


def _norm_type_name(name):
    s = str(name or "").strip()
    for _ in range(3):
        low = s.lower()
        hit = False
        for pre in _DIM_PREFIXES:
            if low.startswith(pre.lower()):
                s = s[len(pre):].strip()
                hit = True
                break
        if not hit:
            break
    for _ in range(3):
        low = s.lower()
        hit = False
        for suf in _DIM_SUFFIXES:
            if low.endswith(suf.lower()):
                s = s[:-len(suf)].strip()
                hit = True
                break
        if not hit:
            break
    key = s.lower()
    if key.endswith("25d"):
        s = s[:-3].strip()
        key = s.lower()
    if key in _GDAL_NAME_MAP:
        return _GDAL_NAME_MAP[key]
    return s.replace(" ", "")


def normalize_geometry_type(name):
    s = _norm_type_name(name)
    return s if s in _TYPE_TABLE else ""


def _type_entry(name):
    e = _TYPE_TABLE.get(name)
    if e is not None:
        return e
    return _TYPE_TABLE.get(_norm_type_name(name), (0, False, ""))

_CN_NAMES = {
    "point": "点",
    "line": "线",
    "polygon": "面",
    "collection": "几何集合",
}


def geometry_type_name(geom):
    if geom is None:
        return ""
    try:
        return geom.geom_type
    except Exception:
        _log.exception("silent exception in geometry_type_name")
        return ""


def base_kind(geom_or_name):
    name = (geom_or_name.geom_type
            if hasattr(geom_or_name, "geom_type") else str(geom_or_name))
    return _type_entry(name)[2]


def is_multi(geom_or_name):
    name = (geom_or_name.geom_type
            if hasattr(geom_or_name, "geom_type") else str(geom_or_name))
    return _type_entry(name)[1]


def _to_shapely(obj):
    if obj is None:
        return None
    if _HAS_SHAPELY and isinstance(obj, _BaseGeometry):
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return geom_from_wkb(bytes(obj))
    if isinstance(obj, str):
        try:
            from shapely import wkt as _wkt
            return _wkt.loads(obj)
        except Exception:
            _log.exception("silent exception in _to_shapely")
            return None
    return obj


def as_wkb_bytes(v):
    if v is None or isinstance(v, bytes):
        return v
    if isinstance(v, (bytearray, memoryview)):
        try:
            return bytes(v)
        except Exception:
            _log.exception("silent exception in as_wkb_bytes")
            return v
    return v


def geom_from_wkb(wkb):
    if not _HAS_SHAPELY or wkb is None:
        return None
    data = as_wkb_bytes(wkb)
    if not data:
        return None
    try:
        from shapely import from_wkb
        return from_wkb(data)
    except Exception:
        _log.exception("silent exception in geom_from_wkb")
        return None


def geoms_from_wkb(array):
    if not _HAS_SHAPELY or array is None:
        return []
    items = [as_wkb_bytes(b) for b in array]
    try:
        from shapely import from_wkb
        return from_wkb(items)
    except Exception:
        _log.exception("silent exception in geoms_from_wkb")
        return [geom_from_wkb(b) for b in items]


class GgsGeometry:

    __slots__ = ("_geom",)

    def __init__(self, geom=None):
        self._geom = _to_shapely(geom)

    @property
    def geom(self):
        return self._geom

    def as_shapely(self):
        return self._geom

    def is_empty(self):
        return self._geom is None or bool(getattr(self._geom, "is_empty",
                                                  True))

    def is_valid(self):
        return self._geom is not None

    def type_name(self):
        return geometry_type_name(self._geom)

    def base_kind(self):
        return base_kind(self._geom) if self._geom is not None else ""

    def is_multi(self):
        return is_multi(self._geom) if self._geom is not None else False

    def wkb_type(self):
        name = self.type_name()
        return _type_entry(name)[0]

    def extent(self):
        return GgsRectangle.from_shapely(self._geom)

    def parts(self):
        if self._geom is None:
            return iter(())
        if is_multi(self._geom):
            try:
                return iter(list(self._geom.geoms))
            except Exception:
                _log.exception("silent exception in parts")
                return iter(())
        return iter((self._geom,))

    def area(self):
        try:
            return float(self._geom.area)
        except Exception:
            _log.exception("silent exception in area")
            return 0.0

    def length(self):
        try:
            return float(self._geom.length)
        except Exception:
            _log.exception("silent exception in length")
            return 0.0

    def wkt(self):
        try:
            return self._geom.wkt
        except Exception:
            _log.exception("silent exception in wkt")
            return ""

    def __repr__(self):
        return "GgsGeometry(%s)" % (self.type_name() or "null")

    def __bool__(self):
        return not self.is_empty()



def explode(geom):
    if geom is None:
        return []
    if isinstance(geom, (list, tuple, set, frozenset)):
        out = []
        for g in geom:
            out.extend(explode(g))
        return out
    out = []
    gtype = str(getattr(geom, "geom_type", "") or "")
    if gtype.startswith("GeometryCollection"):
        try:
            for g in geom.geoms:
                out.extend(explode(g))
            return out
        except Exception:
            _log.exception("silent exception in explode")
            return []
    if getattr(geom, "is_empty", False):
        return []
    out.append(geom)
    return out


def split_geometry(geom, splitter):
    if geom is None or splitter is None:
        return []
    try:
        from shapely.ops import split as _split
    except Exception:
        _log.exception("silent exception in split_geometry")
        return [geom]
    try:
        res = _split(geom, splitter)
    except Exception:
        _log.exception("silent exception in split_geometry")
        return [geom]
    parts = explode(res)
    return parts or [geom]


def _largest(parts):
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    best, best_key = None, -1.0
    for g in parts:
        try:
            k = float(getattr(g, "area", 0.0) or 0.0)
            if k <= 0:
                k = float(getattr(g, "length", 0.0) or 0.0)
        except Exception:
            _log.exception("silent exception in _largest")
            k = 0.0
        if k > best_key:
            best, best_key = g, k
    return best


def split_keep_main(geom, splitter):
    parts = split_geometry(geom, splitter)
    if len(parts) <= 1:
        return parts
    try:
        c = geom.representative_point()
    except Exception:
        _log.exception("silent exception in split_keep_main")
        try:
            c = geom.centroid
        except Exception:
            _log.exception("silent exception in split_keep_main")
            c = None
    if c is not None:
        for g in parts:
            try:
                if g.covers(c) or g.intersects(c):
                    return [g]
            except Exception:
                _log.exception("silent exception in split_keep_main")
                continue
    main = _largest(parts)
    return [main] if main is not None else parts


def break_line(geom, splitter):
    gtype = str(getattr(geom, "geom_type", "") or "")
    if "Line" not in gtype and "Ring" not in gtype:
        return [geom]
    return split_geometry(geom, splitter)


def geoms_bbox_center(geoms):
    xs0 = ys0 = xs1 = ys1 = None
    for g in geoms or []:
        if g is None or getattr(g, "is_empty", False):
            continue
        try:
            b = g.bounds
        except Exception:
            _log.exception("silent exception in geoms_bbox_center")
            continue
        if not b or len(b) < 4:
            continue
        if xs0 is None:
            xs0, ys0, xs1, ys1 = b[0], b[1], b[2], b[3]
        else:
            xs0, ys0 = min(xs0, b[0]), min(ys0, b[1])
            xs1, ys1 = max(xs1, b[2]), max(ys1, b[3])
    if xs0 is None:
        return None
    return ((xs0 + xs1) / 2.0, (ys0 + ys1) / 2.0)


def combine_bounds_center(geoms):
    return geoms_bbox_center(geoms)


def nearest_point_on(point, line):
    if point is None or line is None:
        return None
    try:
        from shapely.geometry import Point

        p = point if hasattr(point, "geom_type") else Point(point)
        if getattr(line, "is_empty", True):
            return None
        d = line.distance(p)
        if d != d:
            return None
        dist = line.project(p)
        q = line.interpolate(dist)
        return (float(q.x), float(q.y))
    except Exception:
        _log.exception("silent exception in nearest_point_on")
        return None


def align_offset(geoms, line):
    c = geoms_bbox_center(geoms)
    if c is None:
        return None
    target = nearest_point_on(c, line)
    if target is None:
        return None
    dx, dy = target[0] - c[0], target[1] - c[1]
    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return (0.0, 0.0)
    return (dx, dy)
