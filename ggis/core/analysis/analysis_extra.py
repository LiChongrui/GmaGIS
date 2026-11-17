# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math

import shapely
from shapely.geometry import (
                              GeometryCollection,
                              MultiLineString,
                              MultiPoint,
                              MultiPolygon,
                              Point,
                              box,
)
import logging
_log = logging.getLogger("gmagis")

__all__ = ["EXTRA_OPS"]

_WRAP_MULTI = {"point": MultiPoint, "line": MultiLineString,
               "polygon": MultiPolygon}


def _flat_parts(g):
    t = getattr(g, "geom_type", "")
    if t == "GeometryCollection" or t.startswith("Multi"):
        for sub in g.geoms:
            for s in _flat_parts(sub):
                yield s
    else:
        yield g


def _p_num(key, label, default, mn=None, mx=None, step=None):
    return {"key": key, "type": "number", "label": label,
            "default": default, "min": mn, "max": mx, "step": step}


def _p_int(key, label, default, mn=None, mx=None, step=1):
    return {"key": key, "type": "int", "label": label,
            "default": default, "min": mn, "max": mx, "step": step}


def _p_text(key, label, default):
    return {"key": key, "type": "text", "label": label, "default": default}


def _p_choice(key, label, default, choices):
    return {"key": key, "type": "choice", "label": label,
            "default": default, "choices": list(choices)}


def _p_unit(key, label):
    return _p_choice(key, label, "map",
                     [("map", "地图单位"), ("meters", "米（按椭球换算）")])


def _p_checks(key, label, items):
    return {"key": key, "type": "checklist", "label": label,
            "default": ",".join(it[0] for it in items),
            "options": [(it[0], it[3]) for it in items]}


def _extra(params):
    e = getattr(params, "extra", None)
    return e if isinstance(e, dict) else {}


def _pg(params):
    return getattr(params, "_progress", None)


def _cancelled(params):
    c = getattr(params, "_cancel", None)
    try:
        return bool(c and c())
    except Exception:
        _log.exception("silent exception in _cancelled")
        return False


def _step(n):
    return max(1, (n or 1) // 50)


def _num(params, key, default):
    try:
        return float(_extra(params).get(key, default))
    except (TypeError, ValueError):
        exc_note("_num @ ggis/core/analysis/analysis_extra.py:160")
        return float(default)


def _choice(params, key, default):
    v = _extra(params).get(key, default)
    return str(v if v not in (None, "") else default)


def _text(params, key, default):
    v = _extra(params).get(key, default)
    return str(v if v not in (None, "") else default)


def _attr(attrs, i):
    return dict(attrs[i]) if i < len(attrs) and attrs[i] else {}


def _overlay(params):
    ov = getattr(params, "_overlay", None)
    if not ov:
        return [], []
    return list(ov[0] or []), list(ov[1] or [])


def _is_empty(g):
    if g is None:
        return True
    try:
        return bool(g.is_empty)
    except Exception:
        _log.exception("silent exception in _is_empty")
        return True


def _index(geoms):
    if not geoms:
        return None
    try:
        import numpy as np
        from shapely import STRtree
        arr = np.empty(len(geoms), dtype=object)
        arr[:] = list(geoms)
        return STRtree(arr)
    except Exception:
        _log.exception("silent exception in _index")
        return None


def _new_field(params, fields, default):
    want = _text(params, "field", default).strip() or default
    taken = set()
    for f in (fields or []):
        try:
            taken.add(str(f[0]).lower())
        except Exception:
            _log.exception("silent exception in _new_field")
            taken.add(str(f).lower())
    name, k = want, 2
    while name.lower() in taken:
        name = "%s_%d" % (want, k)
        k += 1
    return name


extra_new_field = _new_field


def _metric(geoms, params):
    if _choice(params, "unit", "map") != "meters" or not geoms:
        return list(geoms)
    crs = getattr(params, "crs", None)
    if crs is None:
        return list(geoms)
    from . import (_local_meter_crs, total_bounds,
                           is_geographic_crs, transform_geoms)
    if not is_geographic_crs(crs):
        return list(geoms)
    local, fwd, _inv = _local_meter_crs(total_bounds(geoms), crs)
    if local is None or fwd is None:
        return list(geoms)
    return transform_geoms(geoms, crs, local)


def _meter_ctx(geoms, params):
    if _choice(params, "unit", "map") != "meters" or not geoms:
        return None
    crs = getattr(params, "crs", None)
    if crs is None:
        return None
    from . import (_local_meter_crs, total_bounds,
                           is_geographic_crs)
    if not is_geographic_crs(crs):
        return None
    local, fwd, inv = _local_meter_crs(total_bounds(geoms), crs)
    if local is None or fwd is None:
        return None
    return (local, fwd, inv)


def _add_field_runner(setup, value, default_field, ftype):

    def runner(geoms, attrs, fields, params):
        name = _new_field(params, fields, default_field)
        ctx = setup(geoms, params)
        n = len(geoms)
        pg = _pg(params)
        step = _step(n)
        out_a = []
        for i in range(n):
            a = _attr(attrs, i)
            try:
                a[name] = value(geoms[i], i, ctx, params)
            except Exception:
                _log.exception("silent exception in runner")
                a[name] = None
            out_a.append(a)
            if pg is not None and (i % step == 0 or i == n - 1):
                pg(float(i + 1) / max(1, n), "正在计算 %d/%d" % (i + 1, n))
        return list(geoms), out_a

    return runner


_MEASURE_ITEMS = (
    ("area", "area", "Real", "面积"),
    ("length", "length", "Real", "长度"),
    ("perimeter", "perim", "Real", "周长"),
    ("npoints", "npoints", "Integer", "顶点数"),
    ("ngeoms", "ngeoms", "Integer", "部件数"),
    ("nrings", "nrings", "Integer", "环数"),
    ("clearance", "clearance", "Real", "最小间隙"),
    ("circularity", "circ", "Real", "圆度"),
)

_RELATION_ITEMS = (
    ("intersects", "intersects", "Integer", "相交"),
    ("contains", "contains", "Integer", "包含"),
    ("within", "within", "Integer", "内含于"),
    ("touches", "touches", "Integer", "相接"),
    ("overlaps", "overlaps", "Integer", "叠置"),
    ("crosses", "crosses", "Integer", "穿越"),
    ("disjoint", "disjoint", "Integer", "分离"),
    ("equals", "equals", "Integer", "相等"),
    ("covers", "covers", "Integer", "覆盖"),
    ("coveredby", "coveredby", "Integer", "被覆盖"),
    ("dwithin", "dwithin", "Integer", "距离内"),
    ("distance", "distance", "Real", "最近距离"),
)


def _checked_keys(params, items):
    raw = _text(params, "methods", "")
    valid = {it[0] for it in items}
    return [k for k in (s.strip() for s in raw.split(",")) if k in valid]


def _multi_result_fields(params, fields, items):
    checked = [it for it in items if it[0] in _checked_keys(params, items)]
    if not checked:
        return list(fields or [])
    taken = set()
    for f in (fields or []):
        taken.add(str(f[0]).lower()
                  if isinstance(f, (list, tuple)) else str(f).lower())
    out = []
    for _key, fname, ftype, _lbl in checked:
        name, k = fname, 2
        while name.lower() in taken:
            name = "%s_%d" % (fname, k)
            k += 1
        taken.add(name.lower())
        out.append((name, ftype))
    return list(fields or []) + out


def _multi_field_runner(items, setup, values):

    def runner(geoms, attrs, fields, params):
        checked = [it for it in items if it[0] in _checked_keys(params, items)]
        if not checked:
            raise ValueError("请至少勾选一个要计算的字段")
        ctxs = {}
        for key in (it[0] for it in checked):
            if key not in ctxs:
                ctxs[key] = setup(key, geoms, params)
        names = _multi_result_fields(params, fields, items)[len(fields or []):]
        n = len(geoms)
        pg = _pg(params)
        step = _step(n)
        out_a = []
        for i in range(n):
            a = _attr(attrs, i)
            for (key, _fname, _ftype, _lbl), (nm, _ft) in zip(checked, names):
                try:
                    a[nm] = values[key](geoms[i], i, ctxs[key], params)
                except Exception:
                    _log.exception("silent exception in runner")
                    a[nm] = None
            out_a.append(a)
            if pg is not None and (i % step == 0 or i == n - 1):
                pg(float(i + 1) / max(1, n), "正在计算 %d/%d" % (i + 1, n))
        return list(geoms), out_a

    return runner


def _measure_setup(key, geoms, params):
    return _metric(geoms, params)


def _relation_setup(key, geoms, params):
    if key in ("dwithin", "distance"):
        return _rel_setup(geoms, params)
    return _pred_setup(geoms, params)


def op_point_on_surface(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            p = shapely.point_on_surface(g)
        except Exception:
            _log.exception("silent exception in op_point_on_surface")
            p = None
        if _is_empty(p):
            continue
        out_g.append(p)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_concave_hull(geoms, attrs, fields, params):
    ratio = _num(params, "ratio", 0.3)
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            h = shapely.concave_hull(g, ratio=ratio)
        except Exception:
            _log.exception("silent exception in op_concave_hull")
            h = None
        if _is_empty(h):
            continue
        out_g.append(h)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_oriented_envelope(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            e = shapely.oriented_envelope(g)
        except Exception:
            _log.exception("silent exception in op_oriented_envelope")
            e = None
        if _is_empty(e):
            continue
        out_g.append(e)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_minimum_bounding_circle(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            c = shapely.minimum_bounding_circle(g)
        except Exception:
            _log.exception("silent exception in op_minimum_bounding_circle")
            c = None
        if _is_empty(c):
            continue
        out_g.append(c)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_maximum_inscribed_circle(geoms, attrs, fields, params):
    tol = _num(params, "tolerance", 0.01)
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            mic = shapely.maximum_inscribed_circle(g, tolerance=tol)
            coords = shapely.get_coordinates(mic)
            if len(coords) < 2:
                continue
            r = float(Point(coords[0]).distance(Point(coords[1])))
            if not (r > 0.0) or not math.isfinite(r):
                continue
            c = Point(coords[0]).buffer(r)
        except Exception:
            _log.exception("silent exception in op_maximum_inscribed_circle")
            continue
        if _is_empty(c):
            continue
        out_g.append(c)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_boundary(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            b = shapely.boundary(g)
        except Exception:
            _log.exception("silent exception in op_boundary")
            b = None
        if _is_empty(b):
            continue
        out_g.append(b)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_exterior_ring(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            r = shapely.get_exterior_ring(g)
        except Exception:
            _log.exception("silent exception in op_exterior_ring")
            r = None
        if _is_empty(r):
            continue
        out_g.append(r)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_extract_by_type(geoms, attrs, fields, params):
    kind = _choice(params, "kind", "polygon")
    from . import geom_kind, _collect
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        parts = [p for p in _flat_parts(g) if geom_kind(p) == kind]
        picked = _collect(parts, kind)
        if _is_empty(picked):
            continue
        out_g.append(picked)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_to_multipart(geoms, attrs, fields, params):
    from . import geom_kind
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        gt = getattr(g, "geom_type", "")
        if gt.startswith("Multi"):
            out = g
        elif gt == "GeometryCollection":
            groups = []
            for kind in ("point", "line", "polygon"):
                parts = [p for p in _flat_parts(g) if geom_kind(p) == kind]
                if parts:
                    groups.append(_WRAP_MULTI[kind](parts))
            out = (groups[0] if len(groups) == 1
                   else (GeometryCollection(groups) if groups else None))
        else:
            out = _WRAP_MULTI[geom_kind(g)]([g])
        if _is_empty(out):
            continue
        out_g.append(out)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_shortest_line(geoms, attrs, fields, params):
    o_geoms, _o_attrs = _overlay(params)
    if not o_geoms:
        params._note = "叠加图层没有要素，未生成最短线"
        return [], []
    tree = _index(o_geoms)
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        line = None
        if tree is not None:
            try:
                j = tree.nearest(g)
            except Exception:
                _log.exception("silent exception in op_shortest_line")
                j = None
            if j is not None:
                try:
                    line = shapely.shortest_line(g, o_geoms[int(j)])
                except Exception:
                    _log.exception("silent exception in op_shortest_line")
                    line = None
        else:
            best, bd = None, None
            for og in o_geoms:
                if _is_empty(og):
                    continue
                try:
                    d = g.distance(og)
                except Exception:
                    _log.exception("silent exception in op_shortest_line")
                    continue
                if bd is None or d < bd:
                    best, bd = og, d
            if best is not None:
                try:
                    line = shapely.shortest_line(g, best)
                except Exception:
                    _log.exception("silent exception in op_shortest_line")
                    line = None
        if _is_empty(line):
            continue
        out_g.append(line)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_remove_repeated_points(geoms, attrs, fields, params):
    tol = _num(params, "tolerance", 0.0)
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            r = shapely.remove_repeated_points(g, tolerance=tol)
        except Exception:
            _log.exception("silent exception in op_remove_repeated_points")
            r = None
        if _is_empty(r):
            continue
        out_g.append(r)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_snap(geoms, attrs, fields, params):
    tol = _num(params, "tolerance", 0.0)
    if tol <= 0.0:
        params._note = "吸附容差为 0，等价于不吸附"
        return list(geoms), [_attr(attrs, i) for i in range(len(geoms))]
    o_geoms, _o_attrs = _overlay(params)
    if not o_geoms:
        params._note = "叠加图层没有要素，未做吸附"
        return list(geoms), [_attr(attrs, i) for i in range(len(geoms))]
    from . import (union_all, transform_geoms, _local_meter_crs,
                           total_bounds, is_geographic_crs)
    ref = union_all(o_geoms)
    if _is_empty(ref):
        params._note = "叠加图层没有有效几何，未做吸附"
        return list(geoms), [_attr(attrs, i) for i in range(len(geoms))]
    ctx = _meter_ctx(geoms, params)
    work = geoms
    work_ref = ref
    crs = getattr(params, "crs", None)
    if ctx is not None and crs is not None:
        local, fwd, inv = ctx
        work = transform_geoms(geoms, crs, local)
        work_ref = transform_geoms([ref], crs, local)[0]
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(work):
        if _is_empty(g):
            continue
        try:
            s = shapely.snap(g, work_ref, tolerance=tol)
        except Exception:
            _log.exception("silent exception in op_snap")
            s = None
        if _is_empty(s):
            continue
        out_g.append(s)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    if ctx is not None and crs is not None and out_g:
        local, fwd, inv = ctx
        out_g = transform_geoms(out_g, local, crs)
    return out_g, out_a


def op_offset_curve(geoms, attrs, fields, params):
    d = _num(params, "distance", 10.0)
    qs = int(_num(params, "quad_segs", 8)) or 8
    js = _choice(params, "join_style", "round")
    ml = _num(params, "mitre_limit", 5.0)
    work = geoms
    ctx = _meter_ctx(geoms, params)
    crs = getattr(params, "crs", None)
    if ctx is not None and crs is not None:
        from . import transform_geoms
        local, fwd, inv = ctx
        work = transform_geoms(geoms, crs, local)
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(work):
        if _is_empty(g):
            continue
        try:
            r = shapely.offset_curve(g, distance=d, quad_segs=qs,
                                     join_style=js, mitre_limit=ml)
        except Exception:
            _log.exception("silent exception in op_offset_curve")
            r = None
        if _is_empty(r):
            continue
        out_g.append(r)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    if ctx is not None and crs is not None and out_g:
        from . import transform_geoms
        local, fwd, inv = ctx
        out_g = transform_geoms(out_g, local, crs)
    return out_g, out_a


def op_translate(geoms, attrs, fields, params):
    dx = _num(params, "dx", 0.0)
    dy = _num(params, "dy", 0.0)
    from shapely import affinity
    out_g = []
    for g in geoms:
        if _is_empty(g):
            out_g.append(g)
            continue
        try:
            out_g.append(affinity.translate(g, xoff=dx, yoff=dy))
        except Exception:
            _log.exception("silent exception in op_translate")
            out_g.append(g)
    return out_g, [_attr(attrs, i) for i in range(len(geoms))]


def op_scale(geoms, attrs, fields, params):
    xf = _num(params, "xfact", 1.0)
    yf = _num(params, "yfact", 1.0)
    from shapely import affinity
    out_g = []
    for g in geoms:
        if _is_empty(g):
            out_g.append(g)
            continue
        try:
            out_g.append(affinity.scale(g, xfact=xf, yfact=yf,
                                        origin="centroid"))
        except Exception:
            _log.exception("silent exception in op_scale")
            out_g.append(g)
    return out_g, [_attr(attrs, i) for i in range(len(geoms))]


def op_rotate(geoms, attrs, fields, params):
    ang = _num(params, "angle", 0.0)
    org = _choice(params, "origin", "centroid")
    from shapely import affinity
    out_g = []
    for g in geoms:
        if _is_empty(g):
            out_g.append(g)
            continue
        try:
            out_g.append(affinity.rotate(g, ang, origin=org))
        except Exception:
            _log.exception("silent exception in op_rotate")
            out_g.append(g)
    return out_g, [_attr(attrs, i) for i in range(len(geoms))]


def op_reverse(geoms, attrs, fields, params):
    out_g = []
    for g in geoms:
        if _is_empty(g):
            out_g.append(g)
            continue
        try:
            out_g.append(shapely.reverse(g))
        except Exception:
            _log.exception("silent exception in op_reverse")
            out_g.append(g)
    return out_g, [_attr(attrs, i) for i in range(len(geoms))]


def op_orient_polygons(geoms, attrs, fields, params):
    cw = _choice(params, "cw", "ccw") == "cw"
    out_g = []
    for g in geoms:
        if _is_empty(g):
            out_g.append(g)
            continue
        try:
            out_g.append(shapely.orient_polygons(g, exterior_cw=cw))
        except Exception:
            _log.exception("silent exception in op_orient_polygons")
            out_g.append(g)
    return out_g, [_attr(attrs, i) for i in range(len(geoms))]


def op_line_merge(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            m = shapely.line_merge(g)
        except Exception:
            _log.exception("silent exception in op_line_merge")
            m = None
        if _is_empty(m):
            continue
        out_g.append(m)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_build_area(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            a = shapely.build_area(g)
        except Exception:
            _log.exception("silent exception in op_build_area")
            a = None
        if _is_empty(a):
            continue
        out_g.append(a)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def op_node(geoms, attrs, fields, params):
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            nn = shapely.node(g)
        except Exception:
            _log.exception("silent exception in op_node")
            nn = None
        if _is_empty(nn):
            continue
        out_g.append(nn)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def _clip_rect_valid(params):
    x0 = _num(params, "minx", 0.0)
    y0 = _num(params, "miny", 0.0)
    x1 = _num(params, "maxx", 0.0)
    y1 = _num(params, "maxy", 0.0)
    if not (x1 > x0 and y1 > y0):
        return "裁剪矩形无效：右下角必须大于左上角（X: %g…%g，Y: %g…%g）" % (
            x0, x1, y0, y1)
    return ""


def op_clip_by_rect(geoms, attrs, fields, params):
    x0 = _num(params, "minx", 0.0)
    y0 = _num(params, "miny", 0.0)
    x1 = _num(params, "maxx", 0.0)
    y1 = _num(params, "maxy", 0.0)
    if not (x1 > x0 and y1 > y0):
        params._note = "裁剪矩形无效（右下角须大于左上角），本次未做裁剪"
        return list(geoms), [_attr(attrs, i) for i in range(len(geoms))]
    out_g, out_a = [], []
    n = len(geoms)
    pg = _pg(params)
    step = _step(n)
    for i, g in enumerate(geoms):
        if _is_empty(g):
            continue
        try:
            c = shapely.clip_by_rect(g, x0, y0, x1, y1)
        except Exception:
            _log.exception("silent exception in op_clip_by_rect")
            c = None
        if _is_empty(c):
            continue
        out_g.append(c)
        out_a.append(_attr(attrs, i))
        if pg is not None and (i % step == 0 or i == n - 1):
            pg(float(i + 1) / max(1, n), "正在执行 %d/%d" % (i + 1, n))
    return out_g, out_a


def _v_area(g, i, ctx, params):
    if _is_empty(g):
        return 0.0
    try:
        return round(float(ctx[i].area), 6)
    except Exception:
        _log.exception("silent exception in _v_area")
        return None


def _v_length(g, i, ctx, params):
    if _is_empty(g):
        return 0.0
    try:
        return round(float(ctx[i].length), 6)
    except Exception:
        _log.exception("silent exception in _v_length")
        return None


def _v_perimeter(g, i, ctx, params):
    if _is_empty(g):
        return 0.0
    gg = ctx[i]
    try:
        if getattr(gg, "geom_type", "") in ("Polygon", "MultiPolygon"):
            return round(float(shapely.boundary(gg).length), 6)
        return round(float(gg.length), 6)
    except Exception:
        _log.exception("silent exception in _v_perimeter")
        return None


def _v_npoints(g, i, ctx, params):
    if _is_empty(g):
        return 0
    try:
        return int(shapely.get_num_coordinates(g))
    except Exception:
        _log.exception("silent exception in _v_npoints")
        return None


def _v_ngeoms(g, i, ctx, params):
    if _is_empty(g):
        return 0
    try:
        return int(shapely.get_num_geometries(g))
    except Exception:
        _log.exception("silent exception in _v_ngeoms")
        return None


def _v_nrings(g, i, ctx, params):
    if _is_empty(g):
        return 0
    gg = ctx[i]
    try:
        t = getattr(gg, "geom_type", "")
        if t == "Polygon":
            return 1 + int(shapely.get_num_interior_rings(gg))
        if t == "MultiPolygon":
            return int(sum(1 + int(shapely.get_num_interior_rings(p))
                           for p in gg.geoms))
        return 0
    except Exception:
        _log.exception("silent exception in _v_nrings")
        return None


def _v_clearance(g, i, ctx, params):
    if _is_empty(g):
        return None
    try:
        v = float(shapely.minimum_clearance(ctx[i]))
    except Exception:
        _log.exception("silent exception in _v_clearance")
        return None
    if not math.isfinite(v):
        return None
    return round(v, 9)


def _v_circularity(g, i, ctx, params):
    if _is_empty(g):
        return None
    gg = ctx[i]
    try:
        if getattr(gg, "geom_type", "") not in ("Polygon", "MultiPolygon"):
            return None
        per = float(shapely.boundary(gg).length)
        if per <= 0.0:
            return None
        return round(4.0 * math.pi * float(gg.area) / (per * per), 6)
    except Exception:
        _log.exception("silent exception in _v_circularity")
        return None


def _pred_setup(geoms, params):
    o_geoms, _o_attrs = _overlay(params)
    return (o_geoms, _index(o_geoms))


def _rel_setup(geoms, params):
    o_geoms, _o_attrs = _overlay(params)
    if (_choice(params, "unit", "map") != "meters" or not o_geoms
            or not geoms):
        return list(geoms), list(o_geoms), _index(o_geoms)
    crs = getattr(params, "crs", None)
    if crs is None:
        return list(geoms), list(o_geoms), _index(o_geoms)
    from . import (transform_geoms, _local_meter_crs,
                           total_bounds, is_geographic_crs)
    if not is_geographic_crs(crs):
        return list(geoms), list(o_geoms), _index(o_geoms)
    local, fwd, inv = _local_meter_crs(
        total_bounds(list(geoms) + list(o_geoms)), crs)
    if local is None or fwd is None:
        return list(geoms), list(o_geoms), _index(o_geoms)
    p_in = transform_geoms(geoms, crs, local)
    p_out = transform_geoms(o_geoms, crs, local)
    return p_in, p_out, _index(p_out)


def _pred_value(pred):
    fn = getattr(shapely, pred)

    def value(g, i, ctx, params):
        if _is_empty(g):
            return 0
        o_geoms, tree = ctx
        if not o_geoms:
            return 0
        if tree is not None:
            try:
                cand = tree.query(g)
            except Exception:
                _log.exception("silent exception in value")
                cand = None
            if cand is None:
                cand = range(len(o_geoms))
            for j in cand:
                og = o_geoms[int(j)]
                if _is_empty(og):
                    continue
                try:
                    if fn(g, og):
                        return 1
                except Exception:
                    _log.exception("silent exception in value")
                    continue
            return 0
        for og in o_geoms:
            if _is_empty(og):
                continue
            try:
                if fn(g, og):
                    return 1
            except Exception:
                _log.exception("silent exception in value")
                continue
        return 0

    return value


def _v_dwithin(g, i, ctx, params):
    d = _num(params, "distance", 0.0)
    if d < 0.0:
        d = 0.0
    if _is_empty(g):
        return 0
    p_in, p_out, tree = ctx
    if not p_out:
        return 0
    gg = p_in[i] if i < len(p_in) else g
    if _is_empty(gg):
        return 0
    if tree is not None:
        try:
            hit = tree.query(gg, predicate="dwithin", distance=d)
        except Exception:
            _log.exception("silent exception in _v_dwithin")
            hit = None
        if hit is not None:
            return 1 if len(hit) else 0
    for og in p_out:
        if _is_empty(og):
            continue
        try:
            if shapely.dwithin(gg, og, d):
                return 1
        except Exception:
            _log.exception("silent exception in _v_dwithin")
            continue
    return 0


def _v_distance(g, i, ctx, params):
    if _is_empty(g):
        return None
    p_in, p_out, tree = ctx
    if not p_out:
        return None
    gg = p_in[i] if i < len(p_in) else g
    if _is_empty(gg):
        return None
    best = None
    if tree is not None:
        try:
            j = tree.nearest(gg)
        except Exception:
            _log.exception("silent exception in _v_distance")
            j = None
        if j is not None:
            try:
                best = float(gg.distance(p_out[int(j)]))
            except Exception:
                _log.exception("silent exception in _v_distance")
                best = None
    if best is None:
        for og in p_out:
            if _is_empty(og):
                continue
            try:
                dd = float(gg.distance(og))
            except Exception:
                _log.exception("silent exception in _v_distance")
                continue
            if best is None or dd < best:
                best = dd
    if best is None:
        return None
    return round(best, 6)


def op_union_layer(geoms, attrs, fields, params):
    from . import union_all
    pg = _pg(params)
    if pg is not None:
        pg(0.3, "正在合并结果")
    u = union_all(geoms)
    if pg is not None:
        pg(1.0, "正在合并结果")
    if _is_empty(u):
        return [], []
    return [u], [{}]


def op_collect(geoms, attrs, fields, params):
    from . import geom_kind, _collect
    parts = []
    for g in geoms:
        if _is_empty(g):
            continue
        parts.extend(_flat_parts(g))
    if not parts:
        return [], []
    kinds = []
    for kind in ("point", "line", "polygon"):
        picked = _collect([p for p in parts if geom_kind(p) == kind], kind)
        if not _is_empty(picked):
            kinds.append(picked)
    if not kinds:
        return [], []
    out = kinds[0] if len(kinds) == 1 else GeometryCollection(kinds)
    return [out], [{}]


def op_extent_layer(geoms, attrs, fields, params):
    from . import total_bounds
    b = total_bounds(geoms)
    if not b:
        return [], []
    return [box(b[0], b[1], b[2], b[3])], [{}]


def op_coverage_union(geoms, attrs, fields, params):
    from . import union_all
    pg = _pg(params)
    if pg is not None:
        pg(0.3, "正在合并结果")
    out = None
    try:
        out = shapely.coverage_union_all(list(geoms))
    except Exception:
        _log.exception("silent exception in op_coverage_union")
        out = None
    if _is_empty(out):
        out = union_all(geoms)
    if pg is not None:
        pg(1.0, "正在合并结果")
    if _is_empty(out):
        return [], []
    return [out], [{}]


EXTRA_OPS = {
    "point_on_surface": {
        "label": "内点",
        "group": "几何派生",
        "hint": "",
        "runner": op_point_on_surface,
        "out_kind": "point",
    },
    "concave_hull": {
        "label": "凹包",
        "group": "几何派生",
        "hint": "",
        "runner": op_concave_hull,
        "params": [_p_num("ratio", "贴合阈值（0 最凹，1 即凸包）", 0.3,
                          0.0, 1.0, 0.05)],
        "validate": lambda p: ("" if 0.0 <= _num(p, "ratio", 0.3) <= 1.0
                               else "贴合阈值须在 0 到 1 之间"),
    },
    "oriented_envelope": {
        "label": "最小外接矩形",
        "group": "几何派生",
        "hint": "",
        "runner": op_oriented_envelope,
    },
    "minimum_bounding_circle": {
        "label": "最小外接圆",
        "group": "几何派生",
        "hint": "",
        "runner": op_minimum_bounding_circle,
    },
    "maximum_inscribed_circle": {
        "label": "最大内切圆",
        "group": "几何派生",
        "hint": "",
        "runner": op_maximum_inscribed_circle,
        "out_kind": "polygon",
        "params": [_p_num("tolerance", "求解容差（地图单位）", 0.01,
                          0.0001, 1e6, 0.01)],
    },
    "boundary": {
        "label": "边界",
        "group": "几何派生",
        "hint": "",
        "runner": op_boundary,
    },
    "exterior_ring": {
        "label": "外环",
        "group": "几何派生",
        "hint": "",
        "runner": op_exterior_ring,
    },
    "extract_by_type": {
        "label": "按类型提取",
        "group": "几何派生",
        "hint": "",
        "runner": op_extract_by_type,
        "params": [_p_choice("kind", "目标类型", "polygon",
                             [("point", "点"), ("line", "线"),
                              ("polygon", "面")])],
    },
    "to_multipart": {
        "label": "转多部件",
        "group": "几何派生",
        "hint": "",
        "runner": op_to_multipart,
    },
    "shortest_line": {
        "label": "最短线",
        "group": "几何派生",
        "hint": "",
        "runner": op_shortest_line,
        "out_kind": "line",
        "needs_overlay": True,
    },
    "remove_repeated_points": {
        "label": "去重复点",
        "group": "几何编辑",
        "hint": "",
        "runner": op_remove_repeated_points,
        "params": [_p_num("tolerance", "容差（地图单位）", 0.0, 0.0, 1e9, 0.001)],
    },
    "snap": {
        "label": "吸附",
        "group": "几何编辑",
        "hint": "",
        "runner": op_snap,
        "needs_overlay": True,
        "params": [_p_num("tolerance", "吸附容差", 1.0, 0.000001, 1e9, 0.1),
                   _p_unit("unit", "容差单位")],
    },
    "offset_curve": {
        "label": "曲线偏移",
        "group": "几何编辑",
        "hint": "",
        "runner": op_offset_curve,
        "out_kind": "line",
        "params": [_p_num("distance", "偏移距离", 10.0, -1e9, 1e9, 1.0),
                   _p_unit("unit", "距离单位"),
                   _p_int("quad_segs", "圆弧分段（每 1/4 圆）", 8, 1, 200),
                   _p_choice("join_style", "拐角样式", "round",
                             [("round", "圆角"), ("mitre", "斜接"),
                              ("bevel", "斜切")]),
                   _p_num("mitre_limit", "斜接限制", 5.0, 1.0, 1e6, 0.5)],
    },
    "translate": {
        "label": "平移",
        "group": "几何编辑",
        "hint": "",
        "runner": op_translate,
        "params": [_p_num("dx", "X 偏移", 0.0, -1e9, 1e9, 1.0),
                   _p_num("dy", "Y 偏移", 0.0, -1e9, 1e9, 1.0)],
    },
    "scale": {
        "label": "缩放",
        "group": "几何编辑",
        "hint": "",
        "runner": op_scale,
        "params": [_p_num("xfact", "X 倍率", 1.0, -1e6, 1e6, 0.1),
                   _p_num("yfact", "Y 倍率", 1.0, -1e6, 1e6, 0.1)],
    },
    "rotate": {
        "label": "旋转",
        "group": "几何编辑",
        "hint": "",
        "runner": op_rotate,
        "params": [_p_num("angle", "旋转角度（度）", 0.0, -3600.0, 3600.0, 1.0),
                   _p_choice("origin", "旋转中心", "centroid",
                             [("centroid", "质心"), ("center", "包围盒中心")])],
    },
    "reverse": {
        "label": "反向",
        "group": "几何编辑",
        "hint": "",
        "runner": op_reverse,
    },
    "orient_polygons": {
        "label": "环向标准化",
        "group": "几何编辑",
        "hint": "",
        "runner": op_orient_polygons,
        "params": [_p_choice("cw", "外环方向", "ccw",
                             [("ccw", "逆时针（CCW）"), ("cw", "顺时针（CW）")])],
    },
    "line_merge": {
        "label": "合并线",
        "group": "几何编辑",
        "hint": "",
        "runner": op_line_merge,
    },
    "build_area": {
        "label": "面构建",
        "group": "几何编辑",
        "hint": "",
        "runner": op_build_area,
    },
    "node": {
        "label": "节点打散",
        "group": "几何编辑",
        "hint": "",
        "runner": op_node,
    },
    "clip_by_rect": {
        "label": "矩形裁剪",
        "group": "几何编辑",
        "hint": "",
        "runner": op_clip_by_rect,
        "params": [_p_num("minx", "左上 X", 0.0, -1e12, 1e12, 1.0),
                   _p_num("miny", "左上 Y", 0.0, -1e12, 1e12, 1.0),
                   _p_num("maxx", "右下 X", 0.0, -1e12, 1e12, 1.0),
                   _p_num("maxy", "右下 Y", 0.0, -1e12, 1e12, 1.0)],
        "validate": _clip_rect_valid,
    },
    "measure_fields": {
        "label": "度量字段",
        "group": "度量",
        "hint": "",
        "runner": _multi_field_runner(
            _MEASURE_ITEMS, _measure_setup,
            {"area": _v_area, "length": _v_length, "perimeter": _v_perimeter,
             "npoints": _v_npoints, "ngeoms": _v_ngeoms, "nrings": _v_nrings,
             "clearance": _v_clearance, "circularity": _v_circularity}),
        "fields": "add_dynamic",
        "fields_fn": lambda p, f: _multi_result_fields(p, f, _MEASURE_ITEMS),
        "params": [_p_checks("methods", "要计算的字段", _MEASURE_ITEMS),
                   _p_unit("unit", "度量单位")],
    },
    "relation_fields": {
        "label": "空间关系字段",
        "group": "空间关系",
        "hint": "",
        "runner": _multi_field_runner(
            _RELATION_ITEMS, _relation_setup,
            {"intersects": _pred_value("intersects"),
             "contains": _pred_value("contains"),
             "within": _pred_value("within"),
             "touches": _pred_value("touches"),
             "overlaps": _pred_value("overlaps"),
             "crosses": _pred_value("crosses"),
             "disjoint": _pred_value("disjoint"),
             "equals": _pred_value("equals"),
             "covers": _pred_value("covers"),
             "coveredby": _pred_value("covered_by"),
             "dwithin": _v_dwithin, "distance": _v_distance}),
        "fields": "add_dynamic",
        "fields_fn": lambda p, f: _multi_result_fields(p, f, _RELATION_ITEMS),
        "needs_overlay": True,
        "params": [_p_checks("methods", "要计算的字段", _RELATION_ITEMS),
                   _p_num("distance", "距离", 100.0, 0.0, 1e12, 1.0),
                   _p_unit("unit", "距离单位")],
    },
    "union_layer": {
        "label": "全层合并",
        "group": "聚合",
        "hint": "",
        "runner": op_union_layer,
        "fields": "drop",
    },
    "collect": {
        "label": "收集为集合",
        "group": "聚合",
        "hint": "",
        "runner": op_collect,
        "fields": "drop",
    },
    "extent_layer": {
        "label": "全层范围",
        "group": "聚合",
        "hint": "",
        "runner": op_extent_layer,
        "out_kind": "polygon",
        "fields": "drop",
    },
    "coverage_union": {
        "label": "覆盖区合并",
        "group": "聚合",
        "hint": "",
        "runner": op_coverage_union,
        "fields": "drop",
    },
}
