# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import math
import time

import numpy as np

import shapely
from shapely.geometry import (GeometryCollection, LineString,
                              MultiLineString, MultiPoint, MultiPolygon,
                              Point, Polygon, box)

from ggis.core.model.measure import _pyproj_crs, is_geographic_crs
from ggis.exec import guard as _guard

_log = logging.getLogger("gmagis")

__all__ = [
    "OP_BUFFER", "OP_INTERSECT", "OP_UNION", "OP_DIFFERENCE",
    "OP_SYM_DIFFERENCE", "OP_IDENTITY", "OP_CLIP", "OP_DISSOLVE",
    "OP_CONVEX_HULL", "OP_BOUNDING_BOX", "OP_CENTROID",
    "OP_FIX_GEOMETRIES", "OP_MULTIPART_TO_SINGLE", "OP_DELETE_DUPLICATES",
    "OP_SIMPLIFY", "OP_DENSIFY", "OP_ROUND_COORDINATES",
    "OPS", "op_spec", "op_label", "op_names",
    "AnalysisParams", "AnalysisResult", "BatchResult", "AnalysisCancelled",
    "CAP_STYLES", "JOIN_STYLES",
    "run_analysis", "run_batch",
    "op_buffer", "op_intersect", "op_union", "op_difference",
    "op_sym_difference", "op_identity", "op_clip", "op_dissolve",
    "op_convex_hull", "op_bounding_box", "op_centroid",
    "op_fix_geometries", "op_multipart_to_singlepart",
    "op_delete_duplicates", "op_simplify", "op_densify",
    "op_round_coordinates", "grid_size_for_decimals",
    "geodesic_buffer", "transform_geometry", "transform_geoms",
    "total_bounds",
    "merge_field_names", "result_to_layer", "write_result",
]

OP_BUFFER = "buffer"
OP_INTERSECT = "intersect"
OP_UNION = "union"
OP_DIFFERENCE = "difference"
OP_SYM_DIFFERENCE = "symmetrical_difference"
OP_IDENTITY = "identity"
OP_CLIP = "clip"
OP_DISSOLVE = "dissolve"
OP_CONVEX_HULL = "convex_hull"
OP_BOUNDING_BOX = "bounding_box"
OP_CENTROID = "centroid"

OP_FIX_GEOMETRIES = "fix_geometries"
OP_MULTIPART_TO_SINGLE = "multipart_to_singlepart"
OP_DELETE_DUPLICATES = "delete_duplicates"
OP_SIMPLIFY = "simplify"
OP_DENSIFY = "densify"
OP_ROUND_COORDINATES = "round_coordinates"

OPS = {
    OP_BUFFER: {
        "label": "缓冲区",
        "needs_overlay": False, "needs_distance": True, "dissolvable": True,
    },
    OP_INTERSECT: {
        "label": "相交",
        "needs_overlay": True, "needs_distance": False, "dissolvable": False,
    },
    OP_UNION: {
        "label": "联合",
        "needs_overlay": True, "needs_distance": False, "dissolvable": False,
    },
    OP_DIFFERENCE: {
        "label": "擦除",
        "needs_overlay": True, "needs_distance": False, "dissolvable": False,
    },
    OP_SYM_DIFFERENCE: {
        "label": "对称差",
        "needs_overlay": True, "needs_distance": False, "dissolvable": False,
    },
    OP_IDENTITY: {
        "label": "标识",
        "needs_overlay": True, "needs_distance": False, "dissolvable": False,
    },
    OP_CLIP: {
        "label": "裁剪",
        "needs_overlay": True, "needs_distance": False, "dissolvable": False,
        "keeps_kind": True,
    },
    OP_DISSOLVE: {
        "label": "融合",
        "needs_overlay": False, "needs_distance": False, "dissolvable": True,
        "by_field": True,
    },
    OP_CONVEX_HULL: {
        "label": "凸包",
        "needs_overlay": False, "needs_distance": False, "dissolvable": True,
    },
    OP_BOUNDING_BOX: {
        "label": "包络矩形",
        "needs_overlay": False, "needs_distance": False, "dissolvable": True,
    },
    OP_CENTROID: {
        "label": "质心",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
    },
    OP_FIX_GEOMETRIES: {
        "label": "修复几何",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
    },
    OP_MULTIPART_TO_SINGLE: {
        "label": "多部件转单部件",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
    },
    OP_DELETE_DUPLICATES: {
        "label": "要素去重",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
        "by_field": True,
    },
    OP_SIMPLIFY: {
        "label": "简化几何",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
        "needs_tolerance": True,
    },
    OP_DENSIFY: {
        "label": "加密几何",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
        "needs_tolerance": True,
    },
    OP_ROUND_COORDINATES: {
        "label": "坐标取整",
        "needs_overlay": False, "needs_distance": False, "dissolvable": False,
        "needs_decimals": True,
    },
}

CAP_STYLES = (("round", "圆头"), ("flat", "平头"), ("square", "方头"))
JOIN_STYLES = (("round", "圆角"), ("mitre", "斜接"), ("bevel", "斜切"))

_CAP_CODES = {"round": 1, "flat": 2, "square": 3, 1: 1, 2: 2, 3: 3}
_JOIN_CODES = {"round": 1, "mitre": 2, "miter": 2, "bevel": 3,
               1: 1, 2: 2, 3: 3}

_KIND_OF_TYPE = {
    "Point": "point", "MultiPoint": "point",
    "LineString": "line", "MultiLineString": "line", "LinearRing": "line",
    "Polygon": "polygon", "MultiPolygon": "polygon",
}

_OUT_KIND_TYPE = {"point": "MultiPoint", "line": "MultiLineString",
                  "polygon": "MultiPolygon"}


def op_spec(op):
    return OPS.get(str(op), {})


def op_label(op):
    return OPS.get(str(op), {}).get("label", str(op))


def op_names():
    return list(OPS.keys())


class AnalysisCancelled(Exception):
    pass


def geom_kind(geom):
    if geom is None:
        return ""
    t = getattr(geom, "geom_type", "")
    if t == "GeometryCollection":
        return "collection"
    return _KIND_OF_TYPE.get(t, "")


def _is_empty(geom):
    if geom is None:
        return True
    try:
        return bool(geom.is_empty)
    except Exception:
        _log.exception("silent exception in _is_empty")
        return True


def _iter_parts(geom):
    if geom is None:
        return
    if getattr(geom, "geom_type", "") == "GeometryCollection":
        for g in geom.geoms:
            for sub in _iter_parts(g):
                yield sub
    else:
        yield geom


def extract_kind(geom, kind):
    if kind not in ("point", "line", "polygon"):
        return geom
    if geom_kind(geom) == kind:
        return geom
    keep = [g for g in _iter_parts(geom) if geom_kind(g) == kind]
    if not keep:
        return None
    if len(keep) == 1:
        return keep[0]
    return _collect(keep, kind)


def _collect(parts, kind):
    parts = [p for p in parts if not _is_empty(p)]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if kind == "point":
        return MultiPoint([p for p in parts if geom_kind(p) == "point"])
    if kind == "line":
        return MultiLineString([p for p in parts if geom_kind(p) == "line"])
    return MultiPolygon([p for p in parts if geom_kind(p) == "polygon"])


def union_all(geoms):
    arr = [g for g in geoms if not _is_empty(g)]
    if not arr:
        return None
    fn = getattr(shapely, "union_all", None) or getattr(shapely, "unary_union")
    try:
        return fn(arr)
    except Exception:
        _log.exception("silent exception in union_all")
        out = arr[0]
        for g in arr[1:]:
            out = out.union(g)
        return out


def _hash_geom(geom, digits=9):
    try:
        return shapely.to_wkb(shapely.set_precision(geom, 10.0 ** (-digits)))
    except Exception:
        _log.exception("silent exception in _hash_geom")
        try:
            return shapely.to_wkb(geom)
        except Exception:
            _log.exception("silent exception in _hash_geom")
            return repr(geom)


class _Index:

    def __init__(self, geoms):
        self._geoms = list(geoms)
        self._tree = None
        try:
            from shapely import STRtree as _T
            from shapely import is_empty as _ie
            arr = np.empty(len(self._geoms), dtype=object)
            arr[:] = self._geoms
            bad = np.asarray(_ie(arr), dtype=bool)
            if bad.any():
                arr[bad] = Point()
            self._tree = _T(arr)
            self.backend = "strtree"
        except Exception:
            _log.exception("silent exception in __init__")
            self._tree = None
            self.backend = "linear"

    def query(self, geom):
        n = len(self._geoms)
        if n == 0:
            return np.zeros(0, dtype=np.int64)
        if self._tree is not None:
            try:
                return np.asarray(self._tree.query(geom), dtype=np.int64)
            except Exception:
                _log.exception("silent exception in query")
        return np.arange(n, dtype=np.int64)


_HAS_PYPROJ = True
try:
    from pyproj import CRS as _CRS
    from pyproj import Transformer as _Transformer
except Exception:
    _log.exception("silent exception")
    _CRS = _Transformer = None
    _HAS_PYPROJ = False

_TRANSFORMER_CACHE = {}
_CRS_CACHE = {}


def _crs_key(crs):
    p = _pyproj_crs(crs) if not isinstance(crs, str) else _pyproj_crs(crs)
    if p is None:
        return ""
    try:
        code = p.to_epsg()
        if code:
            return "EPSG:%d" % code
    except Exception:
        _log.exception("silent exception in _crs_key")
    try:
        return p.to_wkt()
    except Exception:
        _log.exception("silent exception in _crs_key")
        return str(p)


def _cached_crs(key, factory):
    c = _CRS_CACHE.get(key)
    if c is None:
        c = factory()
        _CRS_CACHE[key] = c
    return c


def _transformer(src, dst):
    key = (_crs_key(src), _crs_key(dst))
    t = _TRANSFORMER_CACHE.get(key)
    if t is None:
        t = _Transformer.from_crs(src, dst, always_xy=True)
        _TRANSFORMER_CACHE[key] = t
    return t


def transform_geometry(geom, src_crs, dst_crs):
    if geom is None or _CRS is None:
        return geom
    src = _pyproj_crs(src_crs)
    dst = _pyproj_crs(dst_crs)
    if src is None or dst is None or src.equals(dst):
        return geom
    tr = _transformer(src, dst)

    def _f(coords):
        x, y = tr.transform(coords[:, 0], coords[:, 1])
        out = np.array(coords, dtype=np.float64, copy=True)
        out[:, 0] = x
        out[:, 1] = y
        return out

    try:
        return shapely.transform(geom, _f)
    except Exception:
        _log.exception("silent exception in transform_geometry")
        return geom


def _coords_finite(geom):
    if geom is None or getattr(geom, "is_empty", True):
        return True
    try:
        import shapely

        xy = shapely.get_coordinates(geom)
        if xy.size == 0:
            return True
        return bool(np.isfinite(xy).all())
    except Exception:
        _log.exception("silent exception in _coords_finite")
        return True


def transform_geoms(geoms, src_crs, dst_crs, warnings=None, what="图层"):
    out, bad = [], 0
    empty = None
    for g in geoms or []:
        t = transform_geometry(g, src_crs, dst_crs)
        if _coords_finite(t):
            out.append(t)
            continue
        if empty is None:
            from shapely.geometry import GeometryCollection
            empty = GeometryCollection()
        out.append(empty)
        bad += 1
    if bad and warnings is not None:
        warnings.append(
            "%s投影后有 %d 个要素坐标无效：请确认数据与它声明的坐标系"
            "是否一致" % (what, bad))
    return out


def total_bounds(geoms):
    if not geoms:
        return None
    try:
        arr = np.empty(len(geoms), dtype=object)
        arr[:] = list(geoms)
        b = np.asarray(shapely.total_bounds(arr), dtype=np.float64)
        if b.shape == (4,) and bool(np.isfinite(b).all()):
            return (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    except Exception:
        _log.exception("silent exception in total_bounds")
    xs, ys = [], []
    for g in geoms:
        if _is_empty(g):
            continue
        try:
            b = g.bounds
        except Exception:
            _log.exception("silent exception in total_bounds")
            continue
        if len(b) == 4 and all(v == v for v in b):
            xs.extend((b[0], b[2]))
            ys.extend((b[1], b[3]))
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _local_meter_crs(bounds, crs):
    if _CRS is None:
        return None, None, None
    p = _pyproj_crs(crs)
    if p is not None and not p.is_geographic:
        try:
            if abs(p.axis_info[0].unit_conversion_factor - 1.0) < 1e-9:
                return p, None, None
        except Exception:
            _log.exception("silent exception in _local_meter_crs")
            return p, None, None
    if bounds is None:
        return None, None, None
    src = p or _CRS.from_epsg(4326)
    wgs = _cached_crs("EPSG:4326", lambda: _CRS.from_epsg(4326))
    if _crs_key(src) == "EPSG:4326":
        lons = [bounds[0], bounds[2], bounds[0], bounds[2]]
        lats = [bounds[1], bounds[1], bounds[3], bounds[3]]
    else:
        tr = _transformer(src, wgs)
        lons, lats = tr.transform(
            [bounds[0], bounds[2], bounds[0], bounds[2]],
            [bounds[1], bounds[1], bounds[3], bounds[3]])
    lons = [float(v) for v in lons if v is not None]
    lats = [float(v) for v in lats if v is not None]
    if not lons or not lats:
        return None, None, None
    lon_span = max(lons) - min(lons)
    lat = max(-89.9, min(89.9, (min(lats) + max(lats)) * 0.5))
    lon = (min(lons) + max(lons)) * 0.5
    if abs(lat) <= 84.0 and lon_span < 6.0:
        zone = max(1, min(60, int(math.floor((lon + 180.0) / 6.0)) + 1))
        epsg = (32600 if lat >= 0 else 32700) + zone
        key = "EPSG:%d" % epsg
        local = _cached_crs(key, lambda k=epsg: _CRS.from_epsg(k))
    else:
        proj = ("+proj=aeqd +lat_0=%.6f +lon_0=%.6f +datum=WGS84 "
                "+units=m +no_defs" % (lat, lon))
        local = _cached_crs(proj, lambda s=proj: _CRS.from_proj4(s))
    if local is None:
        return None, None, None
    return local, _transformer(src, local), _transformer(local, src)


def geodesic_buffer(geom, meters, crs=None, segments=8,
                    cap_style="round", join_style="round", ctx=None):
    local, fwd, inv = ctx if ctx is not None else \
        _local_meter_crs(geom.bounds if not _is_empty(geom) else None, crs)
    if local is None or fwd is None:
        try:
            return geom.buffer(float(meters), quad_segs=int(segments),
                               cap_style=_CAP_CODES.get(cap_style, 1),
                               join_style=_JOIN_CODES.get(join_style, 1))
        except Exception:
            _log.exception("silent exception in geodesic_buffer")
            return geom

    def _f(coords):
        x, y = fwd.transform(coords[:, 0], coords[:, 1])
        out = np.array(coords, dtype=np.float64, copy=True)
        out[:, 0] = x
        out[:, 1] = y
        return out

    def _g(coords):
        x, y = inv.transform(coords[:, 0], coords[:, 1])
        out = np.array(coords, dtype=np.float64, copy=True)
        out[:, 0] = x
        out[:, 1] = y
        return out

    try:
        local_geom = shapely.transform(geom, _f)
        buf = local_geom.buffer(float(meters), quad_segs=int(segments),
                                cap_style=_CAP_CODES.get(cap_style, 1),
                                join_style=_JOIN_CODES.get(join_style, 1))
        if _is_empty(buf):
            return buf
        return shapely.transform(buf, _g)
    except Exception:
        _log.exception("silent exception in geodesic_buffer")
        return geom


def merge_field_names(a_fields, b_fields, prefix="ov_"):
    taken = set(str(n) for n, _t in (a_fields or []))
    rename = {}
    used = set()
    for name, _typ in (b_fields or []):
        name = str(name)
        new = name
        if new in taken or new in used:
            new = prefix + name
            while new in taken or new in used:
                new = prefix + new
        rename[name] = new
        used.add(new)
    return rename


def merged_fields(a_fields, b_fields, rename=None):
    out = [(str(n), str(t)) for n, t in (a_fields or [])]
    rename = rename if rename is not None else merge_field_names(
        a_fields, b_fields)
    for n, t in (b_fields or []):
        out.append((rename.get(str(n), str(n)), str(t)))
    return out


def _merge_attrs(a, b, rename):
    out = dict(a or {})
    for k, v in (b or {}).items():
        out[rename.get(str(k), str(k))] = v
    return out


def _buffer_one(g, params):
    d = float(params.distance)
    seg = int(params.segments) or 8
    if params.distance_unit == "meters" and is_geographic_crs(params.crs):
        return geodesic_buffer(g, d, params.crs, seg,
                               params.cap_style, params.join_style,
                               ctx=params._meter)
    try:
        return g.buffer(d, quad_segs=seg,
                        cap_style=_CAP_CODES.get(params.cap_style, 1),
                        join_style=_JOIN_CODES.get(params.join_style, 1))
    except Exception:
        _log.exception("silent exception in _buffer_one")
        return None


def op_buffer(geoms, attrs, params):
    out_g, out_a = [], []
    keep = []
    pg = getattr(params, "_progress", None)
    n = len(geoms) or 1
    step = max(1, n // 50)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        b = _buffer_one(g, params)
        if _is_empty(b):
            continue
        keep.append(b)
        out_g.append(b)
        out_a.append(dict(attrs[i] if i < len(attrs) else {}))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / n, "正在执行 %d/%d" % (i + 1, n))
    if not params.dissolve:
        return out_g, out_a
    if pg is not None:
        pg(0.98, "正在合并结果")
    merged = union_all(keep)
    if merged is None:
        return [], []
    return [merged], [{}]


def op_intersect(geoms, attrs, o_geoms, o_attrs, params):
    kind = params.clip_kind or _dominant_kind(geoms)
    idx = _Index(o_geoms)
    rename = params._b_rename
    out_g, out_a = [], []
    src_a, src_b = [], []
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        for j in idx.query(g):
            j = int(j)
            og = o_geoms[j]
            if _is_empty(og):
                continue
            try:
                if not g.intersects(og):
                    continue
                inter = g.intersection(og)
            except Exception:
                _log.exception("silent exception in op_intersect")
                continue
            if _is_empty(inter):
                continue
            if params.keep_input_kind:
                inter = extract_kind(inter, kind)
                if inter is None or _is_empty(inter):
                    continue
            out_g.append(inter)
            out_a.append(_merge_attrs(
                attrs[i] if i < len(attrs) else {},
                o_attrs[j] if j < len(o_attrs) else {}, rename))
            src_a.append(i)
            src_b.append(j)
    return out_g, out_a, src_a, src_b


def op_clip(geoms, attrs, o_geoms, o_attrs, params):
    kind = params.clip_kind or _dominant_kind(geoms)
    idx = _Index(o_geoms)
    out_g, out_a = [], []
    src_a, src_b = [], []
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        parts = []
        hit_b = []
        for j in idx.query(g):
            j = int(j)
            og = o_geoms[j]
            if _is_empty(og):
                continue
            try:
                if not g.intersects(og):
                    continue
                piece = g.intersection(og)
            except Exception:
                _log.exception("silent exception in op_clip")
                continue
            piece = extract_kind(piece, kind)
            if piece is None or _is_empty(piece):
                continue
            parts.append(piece)
            hit_b.append(j)
        if not parts:
            continue
        out_g.append(_collect(parts, kind))
        out_a.append(dict(attrs[i] if i < len(attrs) else {}))
        src_a.append(i)
        src_b.append(hit_b)
    return out_g, out_a, src_a, src_b


def op_difference(geoms, attrs, o_geoms, o_attrs, params):
    cut = union_all(o_geoms)
    out_g, out_a = [], []
    src_a = []
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        if cut is None:
            piece = g
        else:
            try:
                piece = g.difference(cut)
            except Exception:
                _log.exception("silent exception in op_difference")
                continue
        if _is_empty(piece):
            continue
        out_g.append(piece)
        out_a.append(dict(attrs[i] if i < len(attrs) else {}))
        src_a.append(i)
    return out_g, out_a, src_a


def op_sym_difference(geoms, attrs, o_geoms, o_attrs, params):
    ga, aa, _sa = op_difference(geoms, attrs, o_geoms, o_attrs, params)
    gb, ab, _sb = op_difference(o_geoms, o_attrs, geoms, attrs, params)
    return ga + gb, aa + ab


def _partition(geoms, attrs, o_geoms, o_attrs, params):
    rename = params._b_rename
    idx_b = _Index(o_geoms)
    idx_a = _Index(geoms)
    a_only, a_inter, b_only = [], [], []
    seen = set()

    def _add(bucket, geom, attr):
        if _is_empty(geom):
            return
        key = _hash_geom(geom)
        if key in seen:
            return
        seen.add(key)
        bucket.append((geom, attr))

    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        ga = attrs[i] if i < len(attrs) else {}
        rest = g
        for j in idx_b.query(g):
            j = int(j)
            og = o_geoms[j]
            if _is_empty(og) or not g.intersects(og):
                continue
            gb = o_attrs[j] if j < len(o_attrs) else {}
            try:
                inter = g.intersection(og)
            except Exception:
                _log.exception("silent exception in _partition")
                inter = None
            _add(a_inter, inter, _merge_attrs(ga, gb, rename))
            try:
                rest = rest.difference(og)
            except Exception:
                _log.exception("silent exception in _partition")
            if _is_empty(rest):
                break
        _add(a_only, rest, dict(ga))
    for j, og in enumerate(o_geoms):
        if _is_empty(og):
            continue
        gb = o_attrs[j] if j < len(o_attrs) else {}
        rest = og
        for i in idx_a.query(og):
            i = int(i)
            g = geoms[i]
            if _is_empty(g) or not og.intersects(g):
                continue
            try:
                rest = rest.difference(g)
            except Exception:
                _log.exception("silent exception in _partition")
            if _is_empty(rest):
                break
        _add(b_only, rest, _merge_attrs({}, gb, rename))
    return a_only, a_inter, b_only


def op_union(geoms, attrs, o_geoms, o_attrs, params):
    a_only, a_inter, b_only = _partition(geoms, attrs, o_geoms, o_attrs,
                                         params)
    out_g, out_a = [], []
    for bucket in (a_only, a_inter, b_only):
        for g, a in bucket:
            out_g.append(g)
            out_a.append(a)
    return out_g, out_a


def op_identity(geoms, attrs, o_geoms, o_attrs, params):
    a_only, a_inter, _b = _partition(geoms, attrs, o_geoms, o_attrs, params)
    out_g, out_a = [], []
    for bucket in (a_inter, a_only):
        for g, a in bucket:
            out_g.append(g)
            out_a.append(a)
    return out_g, out_a


def op_dissolve(geoms, attrs, params):
    fld = params.by_field or ""
    if not fld:
        merged = union_all(geoms)
        if merged is None:
            return [], []
        return [merged], [{}]
    groups = {}
    order = []
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        a = attrs[i] if i < len(attrs) else {}
        key = a.get(fld, None)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(g)
    out_g, out_a = [], []
    for key in order:
        merged = union_all(groups[key])
        if merged is None:
            continue
        out_g.append(merged)
        out_a.append({fld: key})
    return out_g, out_a


def op_convex_hull(geoms, attrs, params):
    merged = union_all(geoms)
    if merged is None:
        return [], []
    try:
        return [merged.convex_hull], [{}]
    except Exception:
        _log.exception("silent exception in op_convex_hull")
        return [], []


def op_bounding_box(geoms, attrs, params):
    merged = union_all(geoms)
    if merged is None:
        return [], []
    b = merged.bounds
    return [box(b[0], b[1], b[2], b[3])], [{}]


def op_centroid(geoms, attrs, params):
    out_g, out_a = [], []
    src = []
    inside = bool(params.centroid_inside)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            c = (g.representative_point() if inside and geom_kind(g) == "polygon"
                 else g.centroid)
        except Exception:
            _log.exception("silent exception in op_centroid")
            continue
        if _is_empty(c):
            continue
        out_g.append(c)
        out_a.append(dict(attrs[i] if i < len(attrs) else {}))
        src.append(i)
    return out_g, out_a, src


def _dominant_kind(geoms):
    for kind in ("polygon", "line", "point"):
        for g in geoms:
            if geom_kind(g) == kind:
                return kind
    return ""


def grid_size_for_decimals(decimals):
    return 10.0 ** (-max(0, int(decimals)))


def _copy_attrs(attrs, i):
    return dict(attrs[i]) if i < len(attrs) and attrs[i] else {}


def _single_parts(geom):
    if geom is None:
        return
    t = getattr(geom, "geom_type", "")
    if t == "GeometryCollection" or t.startswith("Multi"):
        try:
            children = list(geom.geoms)
        except Exception:
            _log.exception("silent exception in _single_parts")
            children = []
        if not children:
            return
        for c in children:
            for sub in _single_parts(c):
                yield sub
        return
    yield geom


def _dup_key(geom, digits=9):
    try:
        geom = shapely.normalize(geom)
    except Exception:
        _log.exception("silent exception in _dup_key")
    return _hash_geom(geom, digits)


def op_fix_geometries(geoms, attrs, params):
    out_g, out_a = [], []
    fixed = 0
    for i, g in enumerate(geoms):
        if g is None:
            continue
        ng = g
        try:
            if not bool(shapely.is_valid(g)):
                ng = shapely.make_valid(g)
                fixed += 1
        except Exception:
            _log.exception("silent exception in op_fix_geometries")
            try:
                ng = g.buffer(0)
                fixed += 1
            except Exception:
                _log.exception("silent exception in op_fix_geometries")
                continue
        kind = geom_kind(g)
        if kind in ("point", "line", "polygon"):
            ng = extract_kind(ng, kind)
        if ng is None or _is_empty(ng):
            continue
        out_g.append(ng)
        out_a.append(_copy_attrs(attrs, i))
    if fixed:
        params._note = "修复了 %d 个无效几何" % fixed
    return out_g, out_a


def op_multipart_to_singlepart(geoms, attrs, params):
    out_g, out_a = [], []
    split = 0
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        a = _copy_attrs(attrs, i)
        parts = [p for p in _single_parts(g) if not _is_empty(p)]
        if not parts:
            continue
        if len(parts) == 1:
            out_g.append(parts[0])
            out_a.append(a)
            continue
        split += 1
        for p in parts:
            out_g.append(p)
            out_a.append(dict(a))
    if split:
        params._note = "%d 个多部件要素被拆开" % split
    return out_g, out_a


def op_delete_duplicates(geoms, attrs, params):
    fld = str(params.by_field or "")
    seen = set()
    out_g, out_a = [], []
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        a = _copy_attrs(attrs, i)
        if fld:
            try:
                key = ("f", repr(a.get(fld, None)))
            except Exception:
                _log.exception("silent exception in op_delete_duplicates")
                key = ("f", str(a.get(fld, None)))
        else:
            key = ("g", _dup_key(g))
        if key in seen:
            continue
        seen.add(key)
        out_g.append(g)
        out_a.append(a)
    dropped = len([1 for g in geoms if not _is_empty(g)]) - len(out_g)
    if dropped > 0:
        params._note = "去掉了 %d 个重复要素" % dropped
    return out_g, out_a


def op_simplify(geoms, attrs, params):
    tol = abs(float(params.tolerance or 0.0))
    out_g, out_a = [], []
    dropped = 0
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            ng = shapely.simplify(g, tol, preserve_topology=True)
        except Exception:
            _log.exception("silent exception in op_simplify")
            continue
        kind = geom_kind(g)
        if kind in ("point", "line", "polygon"):
            ng = extract_kind(ng, kind)
        if ng is None or _is_empty(ng):
            dropped += 1
            continue
        out_g.append(ng)
        out_a.append(_copy_attrs(attrs, i))
    if dropped:
        params._note = "%d 个要素简化后为空，已丢弃" % dropped
    return out_g, out_a


def op_densify(geoms, attrs, params):
    step = abs(float(params.tolerance or 0.0))
    out_g, out_a = [], []
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            ng = shapely.segmentize(g, step)
        except Exception:
            _log.exception("silent exception in op_densify")
            continue
        if ng is None or _is_empty(ng):
            continue
        out_g.append(ng)
        out_a.append(_copy_attrs(attrs, i))
    return out_g, out_a


def op_round_coordinates(geoms, attrs, params):
    grid = grid_size_for_decimals(params.decimals)
    out_g, out_a = [], []
    dropped = 0
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            ng = shapely.set_precision(g, grid)
        except Exception:
            _log.exception("silent exception in op_round_coordinates")
            continue
        if ng is None or _is_empty(ng):
            dropped += 1
            continue
        out_g.append(ng)
        out_a.append(_copy_attrs(attrs, i))
    if dropped:
        params._note = ("%d 个要素小于取整网格（%g），已丢弃"
                        % (dropped, grid))
    return out_g, out_a


class AnalysisParams:

    __slots__ = ("op", "input_layer", "overlay_layer", "distance",
                 "segments", "cap_style", "join_style", "dissolve",
                 "by_field", "distance_unit", "keep_input_kind",
                 "centroid_inside", "selected_only", "fids",
                 "output_name", "output_path", "output_driver",
                 "output_crs", "grid_size", "tolerance", "decimals",
                 "_b_rename", "clip_kind", "crs",
                 "_meter", "_note", "_progress",
                 "extra", "_overlay", "_cancel")

    def __init__(self, op=OP_BUFFER, input_layer=None, overlay_layer=None,
                 distance=0.0, segments=8, cap_style="round",
                 join_style="round", dissolve=False, by_field="",
                 distance_unit="map", keep_input_kind=True,
                 centroid_inside=False, selected_only=False, fids=None,
                 output_name="", output_path="", output_driver="",
                 output_crs=None, grid_size=None, tolerance=0.0,
                 decimals=6, clip_kind="", extra=None):
        self.op = str(op)
        self.input_layer = input_layer
        self.overlay_layer = overlay_layer
        self.distance = float(distance)
        self.segments = int(segments)
        self.cap_style = cap_style
        self.join_style = join_style
        self.dissolve = bool(dissolve)
        self.by_field = str(by_field or "")
        self.distance_unit = str(distance_unit or "map")
        self.keep_input_kind = bool(keep_input_kind)
        self.centroid_inside = bool(centroid_inside)
        self.selected_only = bool(selected_only)
        self.fids = None if fids is None else set(int(f) for f in fids)
        self.output_name = str(output_name or "")
        self.output_path = str(output_path or "")
        self.output_driver = str(output_driver or "")
        self.output_crs = output_crs
        self.grid_size = grid_size
        self.tolerance = float(tolerance or 0.0)
        self.decimals = int(decimals)
        self.clip_kind = str(clip_kind or "")
        self.crs = None
        self._meter = None
        self._b_rename = {}
        self._note = ""
        self._progress = None
        self.extra = dict(extra) if extra else {}
        self._overlay = None
        self._cancel = None

    def spec(self):
        return op_spec(self.op)

    def needs_overlay(self):
        return bool(self.spec().get("needs_overlay"))

    def needs_distance(self):
        return bool(self.spec().get("needs_distance"))

    def validate(self):
        if self.op not in OPS:
            return "未知操作：%s" % self.op
        if self.input_layer is None:
            return "未选择输入图层"
        if self.needs_overlay() and self.overlay_layer is None:
            return "「%s」需要选择叠加图层" % op_label(self.op)
        if self.needs_distance() and self.op == OP_BUFFER and \
                abs(self.distance) < 1e-12:
            return "缓冲距离不能为 0"
        if self.dissolve and self.op not in (OP_BUFFER, OP_DISSOLVE):
            return "「%s」不支持融合" % op_label(self.op)
        if self.spec().get("needs_tolerance") and \
                abs(self.tolerance) < 1e-12:
            return "「%s」需要大于 0 的容差" % op_label(self.op)
        v = self.spec().get("validate")
        if v is not None:
            try:
                m = v(self)
            except Exception:
                _log.exception("silent exception in validate")
                m = ""
            if m:
                return m
        return ""

    def __repr__(self):
        return "<AnalysisParams %s dist=%g overlay=%s>" % (
            self.op, self.distance,
            bool(self.overlay_layer))


class AnalysisResult:

    __slots__ = ("op", "geoms", "attrs", "fields", "crs", "ms",
                 "warnings", "src_a", "src_b", "input_count",
                 "geometry_type", "name", "source")

    def __init__(self, op="", geoms=None, attrs=None, fields=None, crs=None,
                 name="", source=""):
        self.op = str(op)
        self.geoms = list(geoms or [])
        self.attrs = list(attrs or [])
        self.fields = list(fields or [])
        self.crs = crs
        self.ms = 0.0
        self.warnings = []
        self.src_a = []
        self.src_b = []
        self.input_count = 0
        self.geometry_type = ""
        self.name = str(name or "")
        self.source = str(source or "")

    def count(self):
        return len(self.geoms)

    def is_empty(self):
        return not self.geoms

    def __len__(self):
        return len(self.geoms)

    def __iter__(self):
        for i in range(len(self.geoms)):
            yield (self.attrs[i] if i < len(self.attrs) else {},
                   self.geoms[i])

    def extent(self):
        from ggis.core.crs.extent import GgsRectangle
        xs, ys = [], []
        for g in self.geoms:
            if _is_empty(g):
                continue
            try:
                b = g.bounds
            except Exception:
                _log.exception("silent exception in extent")
                continue
            if len(b) == 4 and all(v == v for v in b):
                xs.append(b[0])
                xs.append(b[2])
                ys.append(b[1])
                ys.append(b[3])
        if not xs:
            return GgsRectangle()
        return GgsRectangle.from_points(xs, ys)

    def area(self):
        tot = 0.0
        for g in self.geoms:
            try:
                if geom_kind(g) == "polygon":
                    tot += float(g.area)
            except Exception:
                _log.exception("silent exception in area")
        return tot

    def summary(self):
        s = self.spec() if self.op in OPS else {}
        return "%s：%d 个要素，%.1f ms" % (s.get("label", self.op),
                                           self.count(), self.ms)

    def spec(self):
        return op_spec(self.op)

    def to_layer(self, name=None):
        from ggis.core.model.layer import GgsVectorLayer
        nm = name or self.name or self.spec().get("label", self.op)
        gt = self.geometry_type
        if not gt:
            for g in self.geoms:
                k = geom_kind(g)
                if k:
                    gt = {"point": "Point", "line": "LineString",
                          "polygon": "Polygon"}[k]
                    break
        lyr = GgsVectorLayer(nm, crs=self.crs, geometry_type=gt,
                             geoms=self.geoms, attrs=self.attrs,
                             fields=self.fields)
        lyr.set_visible(True)
        return lyr


class BatchResult:

    __slots__ = ("results", "errors", "ms", "cancelled", "total")

    def __init__(self):
        self.results = []
        self.errors = []
        self.ms = 0.0
        self.cancelled = False
        self.total = 0

    def ok_count(self):
        return len(self.results)

    def merged(self, name="批处理结果", crs=None):
        out = AnalysisResult(op="batch", crs=crs, name=name)
        fields_seen = []
        for r in self.results:
            for g, a in zip(r.geoms, r.attrs):
                out.geoms.append(g)
                out.attrs.append(dict(a))
            for f in r.fields:
                if f not in fields_seen:
                    fields_seen.append(f)
            for w in r.warnings:
                if w not in out.warnings:
                    out.warnings.append(w)
        out.fields = fields_seen
        out.input_count = sum(r.input_count for r in self.results)
        out.ms = self.ms
        return out

    def summary(self):
        return "批处理：%d/%d 个作业成功，合计 %d 个要素，%.1f ms" % (
            self.ok_count(), self.total,
            sum(r.count() for r in self.results), self.ms)


def _resolve_source(spec, need_crs=True):
    if spec is None:
        return [], [], [], None
    if isinstance(spec, (tuple, list)):
        geoms = list(spec[0]) if len(spec) > 0 else []
        attrs = list(spec[1]) if len(spec) > 1 else []
        fields = list(spec[2]) if len(spec) > 2 else []
        crs = spec[3] if len(spec) > 3 else None
        return geoms, attrs, fields, crs
    geoms = list(spec.geoms())
    attrs = list(spec.attrs())
    fields = list(spec.fields())
    crs = spec.crs() if need_crs else None
    return geoms, attrs, fields, crs


def _select(geoms, attrs, fids):
    if fids is None:
        return geoms, attrs, list(range(len(geoms)))
    keep = [i for i in range(len(geoms)) if i in fids]
    return ([geoms[i] for i in keep],
            [attrs[i] if i < len(attrs) else {} for i in keep], keep)


def _check_cancel(cancel):
    if cancel is not None and cancel():
        raise AnalysisCancelled()


def _report(progress, frac, text):
    if progress is not None:
        try:
            progress(float(frac), str(text))
        except Exception:
            _log.exception("silent exception in _report")


@_guard.off_ui("core.analysis.run_analysis")
def run_analysis(params, progress=None, cancel=None):
    from ggis.core.model.layer import GgsVectorLayer
    t0 = time.perf_counter()
    err = params.validate()
    if err:
        raise ValueError(err)

    geoms, attrs, fields, crs = _resolve_source(params.input_layer)
    params.crs = crs
    if isinstance(params.input_layer, GgsVectorLayer):
        src_name = params.input_layer.name()
    else:
        src_name = ""
    fids = params.fids if params.selected_only else None
    geoms, attrs, selected = _select(geoms, attrs, fids)
    _check_cancel(cancel)
    _report(progress, 0.05, "读取输入图层")

    result = AnalysisResult(op=params.op, crs=crs,
                            name=params.output_name, source=src_name)
    result.input_count = len(geoms)
    result.geometry_type = _input_geom_type(params.input_layer, geoms)

    o_geoms = o_attrs = o_fields = None
    if params.needs_overlay():
        o_geoms, o_attrs, o_fields, o_crs = _resolve_source(
            params.overlay_layer)
        if o_crs is not None and crs is not None and \
                not _same_crs(o_crs, crs):
            o_geoms = transform_geoms(o_geoms, o_crs, crs,
                                      result.warnings, "叠加图层")
            result.warnings.append(
                "叠加图层 CRS（%s）与输入图层（%s）不同，已临时投影到输入层 CRS"
                % (_crs_text(o_crs), _crs_text(crs)))
        params._b_rename = merge_field_names(fields, o_fields or [])
        result.fields = merged_fields(fields, o_fields or [],
                                     params._b_rename)
    else:
        params._b_rename = {}
        result.fields = list(fields)
    params._overlay = (o_geoms, o_attrs) if params.needs_overlay() else None

    op = params.op
    _CALC_LO, _CALC_HI = 0.20, 0.90

    def _calc_progress(frac, text):
        try:
            f = max(0.0, min(1.0, float(frac)))
        except Exception:
            _log.exception("silent exception in _calc_progress")
            return
        _report(progress, _CALC_LO + (_CALC_HI - _CALC_LO) * f, text)
        _check_cancel(cancel)

    params._progress = _calc_progress
    params._cancel = cancel
    _report(progress, 0.20, "正在执行")

    spec = op_spec(op)
    runner = spec.get("runner")
    if runner is not None:
        f_mode = spec.get("fields", "keep")
        out_g, out_a = runner(geoms, attrs, fields, params)
        if f_mode == "add":
            from .analysis_extra import extra_new_field
            nm = extra_new_field(params, fields,
                                 spec.get("field", "value"))
            result.fields = list(fields) + [
                (nm, str(spec.get("field_type", "String")))]
        elif f_mode == "add_dynamic":
            fn = spec.get("fields_fn")
            result.fields = (fn(params, list(fields))
                             if callable(fn) else list(fields))
        elif f_mode == "drop":
            result.fields = []
            result.src_a = list(range(len(geoms)))
        else:
            result.fields = list(fields)
    elif op == OP_BUFFER:
        if params.distance_unit == "meters" and is_geographic_crs(crs) \
                and geoms:
            params._meter = _local_meter_crs(total_bounds(geoms), crs)
        out_g, out_a = op_buffer(geoms, attrs, params)
        result.fields = _buffer_fields(params, fields)
    elif op == OP_DISSOLVE:
        out_g, out_a = op_dissolve(geoms, attrs, params)
        result.fields = _dissolve_fields(params, fields)
    elif op == OP_CONVEX_HULL:
        out_g, out_a = op_convex_hull(geoms, attrs, params)
        result.fields = []
    elif op == OP_BOUNDING_BOX:
        out_g, out_a = op_bounding_box(geoms, attrs, params)
        result.fields = []
    elif op == OP_CENTROID:
        out_g, out_a, src = op_centroid(geoms, attrs, params)
        result.src_a = [selected[i] if i < len(selected) else i for i in src]
    elif op == OP_INTERSECT:
        out_g, out_a, sa, sb = op_intersect(geoms, attrs, o_geoms, o_attrs,
                                            params)
        result.src_a = [selected[i] if i < len(selected) else i for i in sa]
        result.src_b = sb
    elif op == OP_CLIP:
        out_g, out_a, sa, sb = op_clip(geoms, attrs, o_geoms, o_attrs, params)
        result.fields = list(fields)
        result.src_a = [selected[i] if i < len(selected) else i for i in sa]
        result.src_b = sb
    elif op == OP_DIFFERENCE:
        out_g, out_a, sa = op_difference(geoms, attrs, o_geoms, o_attrs,
                                         params)
        result.fields = list(fields)
        result.src_a = [selected[i] if i < len(selected) else i for i in sa]
    elif op == OP_SYM_DIFFERENCE:
        out_g, out_a = op_sym_difference(geoms, attrs, o_geoms, o_attrs,
                                        params)
    elif op == OP_UNION:
        out_g, out_a = op_union(geoms, attrs, o_geoms, o_attrs, params)
    elif op == OP_IDENTITY:
        out_g, out_a = op_identity(geoms, attrs, o_geoms, o_attrs, params)
    elif op == OP_FIX_GEOMETRIES:
        out_g, out_a = op_fix_geometries(geoms, attrs, params)
        result.fields = list(fields)
    elif op == OP_MULTIPART_TO_SINGLE:
        out_g, out_a = op_multipart_to_singlepart(geoms, attrs, params)
        result.fields = list(fields)
    elif op == OP_DELETE_DUPLICATES:
        out_g, out_a = op_delete_duplicates(geoms, attrs, params)
        result.fields = list(fields)
    elif op == OP_SIMPLIFY:
        out_g, out_a = op_simplify(geoms, attrs, params)
        result.fields = list(fields)
    elif op == OP_DENSIFY:
        out_g, out_a = op_densify(geoms, attrs, params)
        result.fields = list(fields)
    elif op == OP_ROUND_COORDINATES:
        out_g, out_a = op_round_coordinates(geoms, attrs, params)
        result.fields = list(fields)
    else:
        raise ValueError("未知操作：%s" % op)

    if params._note:
        result.warnings.append(params._note)

    _check_cancel(cancel)
    _report(progress, 0.90, "整理输出")

    if params.grid_size:
        try:
            gs = float(params.grid_size)
            out_g = [shapely.set_precision(g, gs) if not _is_empty(g) else g
                     for g in out_g]
        except Exception:
            _log.exception("silent exception in run_analysis")

    result.geoms = out_g
    result.attrs = out_a
    result.ms = (time.perf_counter() - t0) * 1000.0

    ok = op_spec(params.op).get("out_kind")
    if ok in _OUT_KIND_TYPE:
        result.geometry_type = _OUT_KIND_TYPE[ok]
    elif params.op in (OP_CLIP, OP_BUFFER) and result.geometry_type:
        result.geometry_type = _keep_type_for(result.geometry_type,
                                              params.op)
    elif params.op == OP_MULTIPART_TO_SINGLE:
        result.geometry_type = _infer_single_type(out_g) or \
            result.geometry_type
    else:
        result.geometry_type = _infer_multi_type(out_g) or \
            result.geometry_type
    _report(progress, 1.0, "完成")
    return result


def _buffer_fields(params, fields):
    return [] if params.dissolve else list(fields or [])


def _dissolve_fields(params, fields):
    if not params.by_field:
        return []
    for n, t in (fields or []):
        if str(n) == params.by_field:
            return [(str(n), str(t))]
    return [(params.by_field, "String")]


def _keep_type_for(geom_type, op):
    if op == OP_BUFFER:
        return "MultiPolygon"
    return geom_type


def _input_geom_type(layer, geoms):
    try:
        gt = layer.geometry_type()
        if gt:
            return gt
    except Exception:
        _log.exception("silent exception in _input_geom_type")
    for g in geoms:
        t = getattr(g, "geom_type", "")
        if t:
            return t
    return ""


def _infer_multi_type(geoms):
    kinds = set()
    for g in geoms[:200]:
        k = geom_kind(g)
        if k:
            kinds.add(k)
    if len(kinds) == 1:
        k = kinds.pop()
        return {"point": "MultiPoint", "line": "MultiLineString",
                "polygon": "MultiPolygon"}[k]
    if len(kinds) > 1:
        return "GeometryCollection"
    return ""


def _infer_single_type(geoms):
    kinds = set()
    for g in geoms[:200]:
        k = geom_kind(g)
        if k:
            kinds.add(k)
    if len(kinds) == 1:
        return {"point": "Point", "line": "LineString",
                "polygon": "Polygon"}[kinds.pop()]
    if len(kinds) > 1:
        return "GeometryCollection"
    return ""


def _same_crs(a, b):
    pa, pb = _pyproj_crs(a), _pyproj_crs(b)
    if pa is None or pb is None:
        return True
    try:
        return bool(pa.equals(pb))
    except Exception:
        _log.exception("silent exception in _same_crs")
        return True


def _crs_text(crs):
    try:
        return crs.display_name()
    except Exception:
        _log.exception("silent exception in _crs_text")
        return str(crs)


@_guard.off_ui("core.analysis.run_batch")
def run_batch(jobs, progress=None, cancel=None, stop_on_error=False):
    jobs = list(jobs or [])
    out = BatchResult()
    out.total = len(jobs)
    t0 = time.perf_counter()
    for i, job in enumerate(jobs):
        if cancel is not None and cancel():
            out.cancelled = True
            break
        _report(progress, float(i) / max(1, len(jobs)),
                "作业 %d/%d" % (i + 1, len(jobs)))
        try:
            r = run_analysis(job, progress=None, cancel=cancel)
            out.results.append(r)
        except AnalysisCancelled:
            exc_note("run_batch @ ggis/core/analysis/__init__.py:1866")
            out.cancelled = True
            break
        except Exception as e:
            out.errors.append((i, "%s: %s" % (type(e).__name__, e)))
            if stop_on_error:
                break
    out.ms = (time.perf_counter() - t0) * 1000.0
    _report(progress, 1.0, "批处理完成")
    return out


def result_to_layer(result, name=None):
    return result.to_layer(name)


@_guard.off_ui("core.analysis.write_result")
def write_result(result, path, driver="", fields=None, creation_options=None):
    from ggis.io.vector_io import _write_vector_sync
    if result.is_empty():
        raise ValueError("分析结果为空，没有要素可写")
    return _write_vector_sync(path, result.geoms,
                              attrs=result.attrs if result.attrs else None,
                              fields=(fields if fields is not None
                                      else result.fields),
                              crs=result.crs, driver=driver or None,
                              geometry_type=result.geometry_type or None,
                              creation_options=creation_options or None)


from .analysis_extra import EXTRA_OPS as _EXTRA_OPS

OPS.update(_EXTRA_OPS)
