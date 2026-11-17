# -*- coding: utf-8 -*-

from __future__ import annotations

import math


from ggis.exec import guard as _guard
import logging
_log = logging.getLogger("gmagis")


__all__ = [
    "map_tolerance", "hit_fids", "hit_test_layers", "GgsIdentifyHit",
    "features_in_rect", "features_in_polygon",
    "features_by_expression", "tolerance_rect",
    "SPATIAL_PREDICATES", "PREDICATE_LABELS", "features_by_predicate",
    "to_layer_point", "to_layer_rect", "to_layer_tolerance",
    "to_layer_geometry", "features_intersecting",
    "crs_of",
]

try:
    from shapely.geometry import Point as _Point
    from shapely.geometry import box as _box
    from shapely.prepared import prep as _prep
except Exception:
    _log.exception("silent exception")
    _Point = _box = _prep = None


def map_tolerance(settings, pixels=4.0):
    if settings is None:
        return 0.0
    try:
        mupp = float(settings.map_units_per_pixel())
    except Exception:
        _log.exception("silent exception in map_tolerance")
        return 0.0
    if not math.isfinite(mupp) or mupp <= 0:
        return 0.0
    return float(pixels) * mupp


def tolerance_rect(x, y, tol):
    t = abs(float(tol))
    return (x - t, y - t, x + t, y + t)


class GgsIdentifyHit:

    __slots__ = ("layer", "fid", "attrs", "geom", "kind")

    def __init__(self, layer, fid, attrs=None, geom=None, kind=""):
        self.layer = layer
        self.fid = int(fid)
        self.attrs = attrs if isinstance(attrs, dict) else {}
        self.geom = geom
        self.kind = kind or (layer.base_kind() if layer is not None else "")

    def layer_name(self):
        return self.layer.name() if self.layer is not None else ""

    def label(self):
        if self.kind == "raster":
            px = self.attrs.get("pixel") or (-1, -1)
            try:
                return "(列 %d, 行 %d)" % (int(px[0]), int(px[1]))
            except Exception:
                _log.exception("silent exception in label")
                return ""
        for key in ("name", "Name", "NAME", "title", "id", "ID"):
            v = self.attrs.get(key)
            if v not in (None, ""):
                return str(v)
        return "#%d" % (self.fid + 1,)

    def __repr__(self):
        return "<Hit %s#%d>" % (self.layer_name(), self.fid)


INDEX_MIN_FEATURES = 2000


def _candidates(layer, rect, use_index=True):
    n = layer.feature_count()
    if n == 0:
        return []
    xmin, ymin, xmax, ymax = rect
    if use_index and n >= INDEX_MIN_FEATURES:
        try:
            return [int(i) for i in
                    layer.query_bbox_array(xmin, ymin, xmax, ymax)]
        except Exception:
            _log.exception("silent exception in _candidates")
    ext = layer.extent()
    if not ext.is_empty() and (xmin > ext.xmax or xmax < ext.xmin or
                               ymin > ext.ymax or ymax < ext.ymin):
        return []
    geoms = layer.geoms()
    out = []
    for i in range(min(n, len(geoms))):
        g = geoms[i]
        if g is None or getattr(g, "is_empty", True):
            continue
        try:
            b = g.bounds
        except Exception:
            _log.exception("silent exception in _candidates")
            continue
        if b[2] < xmin or b[0] > xmax or b[3] < ymin or b[1] > ymax:
            continue
        out.append(i)
    return out


def _drop_filtered(layer, cands):
    if not cands:
        return cands
    try:
        sub = layer.subset_fids()
    except Exception:
        _log.exception("silent exception in _drop_filtered")
        sub = None
    if sub is None:
        return cands
    return [int(f) for f in cands if int(f) in sub]


def _exact_hit(geom, x, y, tol, kind):
    if geom is None or getattr(geom, "is_empty", True):
        return False
    try:
        pt = _Point(x, y)
    except Exception:
        _log.exception("silent exception in _exact_hit")
        return False
    if kind == "polygon":
        try:
            if _prep is not None:
                if _prep(geom).contains(pt):
                    return True
            elif geom.contains(pt):
                return True
        except Exception:
            _log.exception("silent exception in _exact_hit")
    if tol <= 0.0:
        try:
            return bool(geom.intersects(pt))
        except Exception:
            _log.exception("silent exception in _exact_hit")
            return False
    try:
        return bool(geom.distance(pt) <= tol)
    except Exception:
        _log.exception("silent exception in _exact_hit")
        return False


def hit_fids(layer, x, y, tol=0.0, max_results=None, kinds=None):
    if layer is None or not layer.is_vector():
        return []
    kind = layer.base_kind()
    if kinds and kind not in kinds:
        return []
    cands = _candidates(layer, tolerance_rect(x, y, tol))
    if not cands:
        return []
    sub = None
    try:
        sub = layer.subset_fids()
    except Exception:
        _log.exception("silent exception in hit_fids")
        sub = None
    geoms = layer.geoms()
    scored = []
    for fid in cands:
        if fid < 0 or fid >= len(geoms):
            continue
        if sub is not None and int(fid) not in sub:
            continue
        g = geoms[fid]
        if not _exact_hit(g, x, y, tol, kind):
            continue
        try:
            d = float(g.distance(_Point(x, y)))
        except Exception:
            _log.exception("silent exception in hit_fids")
            d = 0.0
        scored.append((d, fid))
    scored.sort()
    out = [fid for _d, fid in scored]
    if max_results:
        out = out[:int(max_results)]
    return out


def hit_test_layers(layers, x, y, tol=0.0, max_results_layer=8,
                    only_visible=True, kinds=None, source=None,
                    with_raster=False):
    out = []
    for lyr in reversed(list(layers or [])):
        if lyr is None:
            continue
        if only_visible and not lyr.is_visible():
            continue
        lx, ly, lto = x, y, tol
        if source is not None:
            try:
                lx, ly = to_layer_point(lyr, x, y, source)
                lto = to_layer_tolerance(lyr, tol, source)
            except Exception:
                _log.exception("silent exception in hit_test_layers")
                continue
        if with_raster and lyr.is_raster():
            try:
                from ggis.core.style.raster_display import sample_point as _sample
                s = _sample(lyr, lx, ly)
            except Exception:
                _log.exception("silent exception in hit_test_layers")
                s = None
            if s:
                out.append(GgsIdentifyHit(
                    lyr, -1,
                    {"bands": s.get("bands") or [],
                     "values": s.get("values") or [],
                     "pixel": s.get("pixel") or (-1, -1),
                     "point": (lx, ly)},
                    None, kind="raster"))
            continue
        if with_raster and lyr.is_tile():
            try:
                s = _sample_tile(lyr, lx, ly, source)
            except Exception:
                _log.exception("silent exception in hit_test_layers")
                s = None
            if s:
                out.append(GgsIdentifyHit(
                    lyr, -1,
                    {"z": s.get("z"), "tx": s.get("tx"), "ty": s.get("ty"),
                     "r": s.get("r"), "g": s.get("g"), "b": s.get("b"),
                     "point": (lx, ly)},
                    None, kind="tile"))
            continue
        if not lyr.is_vector():
            continue
        try:
            fids = hit_fids(lyr, lx, ly, lto, max_results_layer, kinds)
        except Exception:
            _log.exception("silent exception in hit_test_layers")
            continue
        if not fids:
            continue
        attrs_list = lyr.attrs()
        geoms = lyr.geoms()
        for fid in fids:
            a = attrs_list[fid] if fid < len(attrs_list) else {}
            g = geoms[fid] if fid < len(geoms) else None
            out.append(GgsIdentifyHit(lyr, fid, a, g))
    return out


def _sample_tile(layer, lx, ly, source=None):
    try:
        from ggis.render.tiles import TileLoader
        src = layer.tile_source()
        if src is None or not src.is_valid():
            return None
        matrix = layer.matrix()
        if matrix is None:
            return None
        mupp = 0.0
        try:
            if source is not None and hasattr(source, "mapUnitsPerPixel"):
                mupp = float(source.mapUnitsPerPixel())
        except Exception:
            _log.exception("silent exception in _sample_tile")
            mupp = 0.0
        if mupp > 0:
            z = matrix.zoom_for_resolution(mupp, 0, 24)
        else:
            z = src.max_zoom or 18
        z = src.clamp_zoom(z)
        w = matrix.world()
        n = matrix.tile_count(z)
        if n <= 0:
            return None
        span_x = w.width() / n
        span_y = w.height() / n
        if not (span_x > 0 and span_y > 0):
            return None
        tx = int((lx - w.xmin) / span_x)
        ty = int((w.ymax - ly) / span_y)
        img = TileLoader.cached_image(src, z, tx, ty)
        if img is None or img.isNull():
            return None
        ts = int(matrix.tile_size)
        fx = ((lx - w.xmin) - tx * span_x) / span_x
        fy = ((w.ymax - ly) - ty * span_y) / span_y
        col = max(0, min(ts - 1, int(fx * ts)))
        row = max(0, min(ts - 1, int(fy * ts)))
        c = img.pixelColor(col, row)
        if not c.isValid():
            return None
        return {"z": int(z), "tx": int(tx), "ty": int(ty),
                "r": int(c.red()), "g": int(c.green()), "b": int(c.blue())}
    except Exception:
        _log.exception("silent exception in _sample_tile")
        return None


def _exact_intersects(bg, ids, gl):
    try:
        import numpy as np
        import shapely
    except Exception:
        _log.exception("silent exception in _exact_intersects")
        return None
    try:
        arr = np.asarray(gl, dtype=object)
        mask = shapely.intersects(arr, bg)
    except Exception:
        _log.exception("silent exception in _exact_intersects")
        return None
    try:
        mask = np.asarray(mask, dtype=bool)
    except Exception:
        _log.exception("silent exception in _exact_intersects")
        return None
    if mask.size != len(ids):
        return None
    return [ids[i] for i in np.nonzero(mask)[0]]


def features_in_rect(layer, rect, mode="intersects", use_index=True):
    if layer is None or not layer.is_vector() or rect is None:
        return []
    xmin, ymin, xmax, ymax = rect
    if xmax < xmin:
        xmin, xmax = xmax, xmin
    if ymax < ymin:
        ymin, ymax = ymax, ymin
    cands = _candidates(layer, (xmin, ymin, xmax, ymax), use_index)
    cands = _drop_filtered(layer, cands)
    if not cands:
        return []
    if mode == "intersects":
        if _box is None:
            return [int(f) for f in cands]
        try:
            bg = _box(xmin, ymin, xmax, ymax)
        except Exception:
            _log.exception("silent exception in features_in_rect")
            return [int(f) for f in cands]
        geoms = layer.geoms()
        ids, gl = [], []
        for fid in cands:
            if fid < 0 or fid >= len(geoms):
                continue
            g = geoms[fid]
            if g is None or getattr(g, "is_empty", True):
                continue
            ids.append(int(fid))
            gl.append(g)
        if not ids:
            return []
        out = _exact_intersects(bg, ids, gl)
        if out is not None:
            return out
        out = []
        for fid, g in zip(ids, gl):
            try:
                if bg.intersects(g):
                    out.append(int(fid))
            except Exception:
                _log.exception("silent exception in features_in_rect")
                continue
        return out
    geoms = layer.geoms()
    box = _box(xmin, ymin, xmax, ymax) if _box is not None else None
    out = []
    for fid in cands:
        if fid < 0 or fid >= len(geoms):
            continue
        g = geoms[fid]
        if g is None or getattr(g, "is_empty", True):
            continue
        try:
            if mode == "contains":
                if box is not None and box.contains(g):
                    out.append(int(fid))
            elif mode == "centroid":
                c = g.centroid
                if xmin <= c.x <= xmax and ymin <= c.y <= ymax:
                    out.append(int(fid))
        except Exception:
            _log.exception("silent exception in features_in_rect")
            continue
    return out


@_guard.off_ui("core.query.features_in_polygon")
def features_in_polygon(layer, poly, mode="intersects", use_index=True):
    if layer is None or not layer.is_vector() or poly is None:
        return []
    try:
        b = poly.bounds
    except Exception:
        _log.exception("silent exception in features_in_polygon")
        return []
    cands = _candidates(layer, b, use_index)
    cands = _drop_filtered(layer, cands)
    if not cands:
        return []
    geoms = layer.geoms()
    prepared = None
    if mode == "intersects" and _prep is not None:
        try:
            prepared = _prep(poly)
        except Exception:
            _log.exception("silent exception in features_in_polygon")
            prepared = None
    out = []
    for fid in cands:
        if fid < 0 or fid >= len(geoms):
            continue
        g = geoms[fid]
        if g is None or getattr(g, "is_empty", True):
            continue
        try:
            if mode == "contains":
                hit = poly.contains(g)
            else:
                hit = (prepared.intersects(g) if prepared is not None
                       else poly.intersects(g))
        except Exception:
            _log.exception("silent exception in features_in_polygon")
            hit = False
        if hit:
            out.append(int(fid))
    return out


def features_by_expression(layer, node, invert=False, errors=None):
    if layer is None or not layer.is_vector():
        return []
    import numpy as np
    from .expression import select_mask
    attrs = layer.attrs()
    mask = select_mask(node, attrs, errors=errors)
    if invert:
        mask = ~mask
    geoms = layer.geoms()
    n = min(len(mask), len(geoms))
    if n <= 0:
        return []
    geoms = geoms[:n]
    cand = np.nonzero(np.asarray(mask[:n], dtype=bool))[0]
    out = [int(i) for i in cand
           if geoms[i] is not None
           and not getattr(geoms[i], "is_empty", True)]
    return out




SPATIAL_PREDICATES = (
    "intersects",
    "contains",
    "within",
    "touches",
    "overlaps",
    "crosses",
    "distance",
)

PREDICATE_LABELS = {
    "intersects": "相交",
    "contains": "包含",
    "within": "位于其中",
    "touches": "接触",
    "overlaps": "重叠",
    "crosses": "穿过",
    "distance": "距离内",
}

_PREDICATE_METHOD = {
    "intersects": "intersects",
    "contains": "contains",
    "within": "within",
    "touches": "touches",
    "overlaps": "overlaps",
    "crosses": "crosses",
}


@_guard.off_ui("core.query.features_by_predicate")
def features_by_predicate(layer, geom, predicate="intersects", distance=0.0,
                          use_index=True):
    if layer is None or not layer.is_vector() or geom is None:
        return []
    if predicate not in SPATIAL_PREDICATES:
        predicate = "intersects"
    try:
        b = geom.bounds
    except Exception:
        _log.exception("silent exception in features_by_predicate")
        return []
    if not b or len(b) < 4:
        return []
    if predicate == "distance":
        d = abs(float(distance or 0.0))
        b = (b[0] - d, b[1] - d, b[2] + d, b[3] + d)
    cands = _candidates(layer, b, use_index)
    cands = _drop_filtered(layer, cands)
    if not cands:
        return []

    geoms = layer.geoms()
    out = []
    if predicate == "distance":
        for fid in cands:
            if fid < 0 or fid >= len(geoms):
                continue
            g = geoms[fid]
            if g is None or getattr(g, "is_empty", True):
                continue
            try:
                if float(g.distance(geom)) <= d:
                    out.append(int(fid))
            except Exception:
                _log.exception("silent exception in features_by_predicate")
                continue
        return out

    name = _PREDICATE_METHOD.get(predicate, "intersects")
    prepared = None
    if predicate == "intersects" and _prep is not None:
        try:
            prepared = _prep(geom)
        except Exception:
            _log.exception("silent exception in features_by_predicate")
            prepared = None
    for fid in cands:
        if fid < 0 or fid >= len(geoms):
            continue
        g = geoms[fid]
        if g is None or getattr(g, "is_empty", True):
            continue
        try:
            if prepared is not None:
                hit = bool(prepared.intersects(g))
            else:
                hit = bool(getattr(g, name)(geom))
        except Exception:
            _log.exception("silent exception in features_by_predicate")
            hit = False
        if hit:
            out.append(int(fid))
    return out


def crs_of(obj):
    if obj is None:
        return None
    fn = getattr(obj, "effectiveCrs", None)
    if fn is not None:
        try:
            return fn()
        except Exception:
            _log.exception("silent exception in crs_of")
            return None
    fn = getattr(obj, "destinationCrs", None)
    if fn is not None:
        try:
            c = fn()
        except Exception:
            _log.exception("silent exception in crs_of")
            c = None
        if c is not None and not hasattr(c, "is_valid"):
            from ggis.core.crs import GgsCrs
            return GgsCrs.from_user_input(c)
        return c
    fn = getattr(obj, "crs", None)
    if fn is not None:
        try:
            return fn()
        except Exception:
            _log.exception("silent exception in crs_of")
            return None
    return None


def to_layer_point(layer, x, y, source):
    if layer is None:
        return (x, y)
    src = source if hasattr(source, "is_valid") else crs_of(source)
    from ggis.core.crs import crs_transformer
    tf = crs_transformer(src, crs_of(layer))
    if tf is None:
        return (x, y)
    try:
        tx, ty = tf.transform(float(x), float(y))
    except Exception:
        _log.exception("silent exception in to_layer_point")
        return (x, y)
    if not (math.isfinite(tx) and math.isfinite(ty)):
        return (x, y)
    return (float(tx), float(ty))


def to_layer_rect(layer, rect, source):
    if layer is None or rect is None:
        return rect
    src = source if hasattr(source, "is_valid") else crs_of(source)
    from ggis.core.crs import convert_bounds, crs_transformer
    tf = crs_transformer(src, crs_of(layer))
    if tf is None:
        return rect
    b = convert_bounds(rect, tf)
    return b if b is not None else rect


def to_layer_tolerance(layer, tol, source):
    if layer is None or tol is None:
        return tol
    src = source if hasattr(source, "is_valid") else crs_of(source)
    from ggis.core.crs import crs_scale_factor
    f = crs_scale_factor(crs_of(layer), src)
    if f <= 1e-12:
        return tol
    return float(tol) * f


def to_layer_geometry(layer, geom, source):
    if layer is None or geom is None:
        return geom
    src = source if hasattr(source, "is_valid") else crs_of(source)
    from ggis.core.crs import crs_transformer
    tf = crs_transformer(src, crs_of(layer))
    if tf is None:
        return geom
    try:
        from shapely.ops import transform as _shp_transform
    except Exception:
        _log.exception("silent exception in to_layer_geometry")
        return geom

    def _f(x, y, z=None):
        try:
            import numpy as _np
            xs = _np.asarray(x, dtype=float)
            ys = _np.asarray(y, dtype=float)
            tx, ty = tf.transform(xs, ys)
            tx = _np.asarray(tx, dtype=float)
            ty = _np.asarray(ty, dtype=float)
            bad = ~(_np.isfinite(tx) & _np.isfinite(ty))
            if bad.any():
                tx = _np.where(bad, xs, tx)
                ty = _np.where(bad, ys, ty)
            if tx.ndim == 0:
                return (float(tx), float(ty))
            return (tx, ty)
        except Exception:
            _log.exception("silent exception in _f")
            return (x, y)

    try:
        out = _shp_transform(_f, geom)
    except Exception:
        _log.exception("silent exception in to_layer_geometry")
        return geom
    if out is None or getattr(out, "is_empty", True):
        return geom
    return out


def features_intersecting(layer, geom, use_index=True):
    if layer is None or not layer.is_vector() or geom is None:
        return []
    try:
        b = geom.bounds
    except Exception:
        _log.exception("silent exception in features_intersecting")
        return []
    cands = _candidates(layer, b, use_index)
    cands = _drop_filtered(layer, cands)
    if not cands:
        return []
    geoms = layer.geoms()
    prepared = None
    if _prep is not None:
        try:
            prepared = _prep(geom)
        except Exception:
            _log.exception("silent exception in features_intersecting")
            prepared = None
    out = []
    for fid in cands:
        if fid < 0 or fid >= len(geoms):
            continue
        g = geoms[fid]
        if g is None or getattr(g, "is_empty", True):
            continue
        try:
            hit = (prepared.intersects(g) if prepared is not None
                   else geom.intersects(g))
        except Exception:
            _log.exception("silent exception in features_intersecting")
            hit = False
        if hit:
            out.append(int(fid))
    return out
