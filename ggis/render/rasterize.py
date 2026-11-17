# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import math
import threading

import numpy as np

from ..core.crs import crs_pair_key, crs_transformer, convert_xy

_log = logging.getLogger("gmagis")

__all__ = [
    "flat_coords", "invalidate_flat", "GgsCoverage",
    "sample_segments", "quantize_tolerance", "clip_segments",
    "adjacency_mask", "polygon_diff",
]


def quantize_tolerance(tol: float) -> float:
    if tol is None or tol <= 0:
        return 0.0
    return 2.0 ** math.floor(math.log2(tol))


def _iter_parts(geom, kind):
    gt = geom.geom_type
    if kind == "line":
        if gt == "LineString":
            return [geom]
        if gt == "MultiLineString":
            return list(geom.geoms)
        if gt == "GeometryCollection":
            return [p for p in geom.geoms if p.geom_type == "LineString"]
        return []
    if gt == "Polygon":
        return [geom]
    if gt == "MultiPolygon":
        return list(geom.geoms)
    if gt == "GeometryCollection":
        return [p for p in geom.geoms if p.geom_type == "Polygon"]
    return []


def _ring_arrays(poly_part):
    rings = []
    try:
        rings.append(np.asarray(poly_part.exterior.coords, dtype=np.float64))
    except Exception:
        exc_note("_ring_arrays @ ggis/render/rasterize.py:100")
        return rings
    for interior in getattr(poly_part, "interiors", []):
        try:
            rings.append(np.asarray(interior.coords, dtype=np.float64))
        except Exception:
            exc_note("_ring_arrays @ ggis/render/rasterize.py:105")
            continue
    return rings


def _signed_area(ring) -> float:
    x = ring[:, 0]
    y = ring[:, 1]
    return 0.5 * float(np.dot(x[:-1], y[1:]) - np.dot(x[1:], y[:-1]))


def _reproject_boxes(bb, tf):
    if tf is None or len(bb) == 0:
        return bb
    g = len(bb)
    x0, y0 = bb[:, 1], bb[:, 2]
    x1, y1 = bb[:, 3], bb[:, 4]
    cx = np.concatenate([x0, x0, x1, x1])
    cy = np.concatenate([y0, y1, y0, y1])
    try:
        tx, ty = tf.transform(cx, cy)
    except Exception:
        exc_note("_reproject_boxes @ ggis/render/rasterize.py:132")
        return bb
    tx = np.asarray(tx, dtype=np.float64).reshape(4, g)
    ty = np.asarray(ty, dtype=np.float64).reshape(4, g)
    tx[~np.isfinite(tx)] = np.nan
    ty[~np.isfinite(ty)] = np.nan
    with np.errstate(invalid="ignore"):
        nx0 = np.nanmin(tx, axis=0)
        ny0 = np.nanmin(ty, axis=0)
        nx1 = np.nanmax(tx, axis=0)
        ny1 = np.nanmax(ty, axis=0)
    ok = (np.isfinite(nx0) & np.isfinite(ny0)
          & np.isfinite(nx1) & np.isfinite(ny1))
    out = bb.copy()
    out[ok, 1] = nx0[ok]
    out[ok, 2] = ny0[ok]
    out[ok, 3] = nx1[ok]
    out[ok, 4] = ny1[ok]
    return out


def _build_flat_legacy(layer, tol, kind, dst_crs=None):
    from shapely import get_coordinates
    src_crs = None
    try:
        src_crs = layer.crs()
    except Exception:
        exc_note("_build_flat_legacy @ ggis/render/rasterize.py:163")
        pass
    tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
    geoms = layer.geoms()
    chunks = []
    starts = []
    ends = []
    part_geom = []
    bboxes = []
    n = 0
    for gi, g in enumerate(geoms):
        if g is None:
            continue
        try:
            if g.is_empty:
                continue
        except Exception:
            exc_note("_build_flat_legacy @ ggis/render/rasterize.py:181")
            continue
        gg = g
        if tol > 0:
            try:
                gg = g.simplify(tol, preserve_topology=False)
                if gg is None or gg.is_empty:
                    gg = g
            except Exception:
                exc_note("_build_flat_legacy @ ggis/render/rasterize.py:189")
                gg = g
        parts = _iter_parts(gg, kind)
        gi_added = False
        for part in parts:
            if kind == "line":
                try:
                    c = np.asarray(get_coordinates(part), dtype=np.float64)
                except Exception:
                    exc_note("_build_flat_legacy @ ggis/render/rasterize.py:197")
                    continue
                if c.ndim != 2 or c.shape[0] < 2:
                    continue
                rings = [c[:, :2]]
            else:
                rings = _ring_arrays(part)
                if not rings:
                    continue
            for ri, ring in enumerate(rings):
                if ring.ndim != 2 or ring.shape[0] < 2:
                    continue
                if kind == "polygon":
                    area = _signed_area(ring)
                    if ri == 0 and area < 0:
                        ring = ring[::-1]
                    elif ri > 0 and area > 0:
                        ring = ring[::-1]
                chunks.append(ring)
                starts.append(n)
                n += ring.shape[0]
                ends.append(n)
                part_geom.append(gi)
                gi_added = True
        if gi_added:
            try:
                b = g.bounds
                bboxes.append((gi, b[0], b[1], b[2], b[3]))
            except Exception:
                exc_note("_build_flat_legacy @ ggis/render/rasterize.py:227")
                pass
    if not chunks:
        return {
            "xy": np.zeros((0, 2), dtype=np.float64),
            "part_starts": np.zeros(0, dtype=np.int64),
            "part_ends": np.zeros(0, dtype=np.int64),
            "part_geom": np.zeros(0, dtype=np.int64),
            "geom_bbox": np.zeros((0, 5), dtype=np.float64),
            "kind": kind, "tol": tol,
        }
    xy = np.concatenate(chunks, axis=0)
    bb = np.asarray(bboxes, dtype=np.float64) if bboxes \
        else np.zeros((0, 5), dtype=np.float64)
    if tf is not None:
        xy = convert_xy(xy, tf)
        bb = _reproject_boxes(bb, tf)
    return {
        "xy": xy,
        "part_starts": np.asarray(starts, dtype=np.int64),
        "part_ends": np.asarray(ends, dtype=np.int64),
        "part_geom": np.asarray(part_geom, dtype=np.int64),
        "geom_bbox": bb,
        "kind": kind, "tol": tol,
    }


_GEOM_LINE = 1
_GEOM_POLYGON = 3
_GEOM_MULTILINE = 5
_GEOM_MULTIPOLYGON = 6


def _empty_flat(kind, tol):
    return {
        "xy": np.zeros((0, 2), dtype=np.float64),
        "part_starts": np.zeros(0, dtype=np.int64),
        "part_ends": np.zeros(0, dtype=np.int64),
        "part_geom": np.zeros(0, dtype=np.int64),
        "geom_bbox": np.zeros((0, 5), dtype=np.float64),
        "kind": kind, "tol": tol,
    }


def _ring_signed_area_ref(xy, ref_x, ref_y, ring_starts, ring_ends):
    dx = xy[:, 0] - ref_x
    dy = xy[:, 1] - ref_y
    cross = np.zeros(dx.shape[0], dtype=np.float64)
    if dx.shape[0] > 1:
        cross[:-1] = dx[:-1] * dy[1:] - dx[1:] * dy[:-1]
    csum = np.concatenate((np.zeros(1, dtype=np.float64), np.cumsum(cross)))
    return csum[ring_ends] - csum[ring_starts]


def _ring_signed_area2(xy, ring_starts, ring_ends):
    x = xy[:, 0]
    y = xy[:, 1]
    x0 = np.repeat(x[ring_starts], ring_ends - ring_starts)
    y0 = np.repeat(y[ring_starts], ring_ends - ring_starts)
    return _ring_signed_area_ref(xy, x0, y0, ring_starts, ring_ends)


def _reverse_rings(xy, ring_starts, ring_ends, which):
    if which is None:
        st = ring_starts
        counts = (ring_ends - ring_starts).astype(np.int64)
        total = int(counts.sum())
        if total == 0:
            return xy
        gstart = np.concatenate((np.zeros(1, dtype=np.int64),
                                 np.cumsum(counts)[:-1]))
        off = np.arange(total, dtype=np.int64) - np.repeat(gstart, counts)
        roff = np.repeat(counts - 1, counts) - off
        swap = off < roff
        if not swap.any():
            return xy
        a = (np.repeat(st, counts) + off)[swap]
        b = (np.repeat(st, counts) + roff)[swap]
        tmp = xy[a].copy()
        xy[a] = xy[b]
        xy[b] = tmp
        return xy

    which = np.asarray(which, dtype=np.int64)
    if which.size == 0:
        return xy
    st = ring_starts[which]
    counts = (ring_ends[which] - st).astype(np.int64)
    total = int(counts.sum())
    if total == 0:
        return xy
    gstart = np.concatenate((np.zeros(1, dtype=np.int64),
                             np.cumsum(counts)[:-1]))
    off = np.arange(total, dtype=np.int64) - np.repeat(gstart, counts)
    roff = np.repeat(counts - 1, counts) - off
    base = np.repeat(st, counts)
    xy[base + off] = xy[base + roff]
    return xy


def _normalize_ring_winding(xy, ring_starts, ring_ends, outward):
    nring = int(ring_starts.size)
    if nring == 0:
        return xy
    outward = np.asarray(outward, dtype=bool)
    area2 = _ring_signed_area2(xy, ring_starts, ring_ends)
    want_pos = outward
    sign_pos = area2 > 0
    wrong = np.nonzero(sign_pos != want_pos)[0]
    if wrong.size == 0:
        return xy
    if wrong.size == nring:
        wrong = None
    return _reverse_rings(xy, ring_starts, ring_ends, wrong)


def _pack_ranges(values, owner=None):
    v = np.asarray(values, dtype=np.int64)
    ends = np.cumsum(v)
    starts = np.concatenate((np.zeros(1, dtype=np.int64), ends[:-1]))
    if owner is None:
        return starts, ends
    return starts, ends, np.repeat(np.asarray(owner, dtype=np.int64), v)


_SIMPLIFY_CHUNK = 4000


def _simplify_chunked(geoms, tol, yield_fn=None, parallel=False):
    import shapely
    n = len(geoms)
    if n <= _SIMPLIFY_CHUNK:
        out = shapely.simplify(geoms, tol, preserve_topology=False)
        bad = shapely.is_empty(out)
        return np.where(bad, geoms, out) if bad.any() else out

    def _sim(chunk):
        s = shapely.simplify(chunk, tol, preserve_topology=False)
        bad = shapely.is_empty(s)
        return np.where(bad, chunk, s) if bad.any() else s

    bounds = [(a, min(a + _SIMPLIFY_CHUNK, n))
              for a in range(0, n, _SIMPLIFY_CHUNK)]
    if parallel and len(bounds) > 1:
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(4, len(bounds))) as ex:
                futs = [ex.submit(_sim, geoms[a:b]) for (a, b) in bounds]
                parts = [f.result() for f in futs]
            return np.concatenate(parts)
        except Exception:
            exc_note("_simplify_chunked @ ggis/render/rasterize.py:458")
            pass
    parts = []
    for (a, b) in bounds:
        parts.append(_sim(geoms[a:b]))
        if yield_fn is not None:
            try:
                yield_fn()
            except Exception:
                exc_note("_simplify_chunked @ ggis/render/rasterize.py:466")
                pass
    return np.concatenate(parts)


def _build_flat_vector(layer, kind, tol, dst_crs=None, yield_fn=None,
                       no_simplify=False):
    import shapely

    def _yield():
        if yield_fn is not None:
            try:
                yield_fn()
            except Exception:
                exc_note("_yield @ ggis/render/rasterize.py:521")
                pass

    g = np.asarray(layer.geoms(), dtype=object)
    _yield()
    if g.size == 0:
        return _empty_flat(kind, tol)

    tid = shapely.get_type_id(g)
    if kind == "line":
        wanted = (tid == _GEOM_LINE) | (tid == _GEOM_MULTILINE)
    else:
        wanted = (tid == _GEOM_POLYGON) | (tid == _GEOM_MULTIPOLYGON)
    alive = wanted & (~shapely.is_empty(g))
    if not alive.any():
        return _empty_flat(kind, tol)
    keep = np.nonzero(alive)[0]
    sub = g[keep]
    _yield()

    if tol > 0 and not no_simplify:
        try:
            import shapely as _sh
            _cov = getattr(_sh, "coverage_simplify", None)
            if kind == "polygon" and _cov is not None:
                try:
                    sub = _cov(sub, tol)
                except Exception:
                    exc_note("_build_flat_vector @ ggis/render/rasterize.py:563")
                    sub = _simplify_chunked(sub, tol, yield_fn)
            else:
                sub = _simplify_chunked(sub, tol, yield_fn, parallel=True)
        except Exception:
            exc_note("_build_flat_vector @ ggis/render/rasterize.py:569")
            pass

    n_parts_feat = shapely.get_num_geometries(sub)
    n_parts_feat = np.maximum(np.asarray(n_parts_feat, dtype=np.int64), 0)
    parts = shapely.get_parts(sub)
    _yield()
    if parts.size == 0:
        return _empty_flat(kind, tol)
    part_geom = np.repeat(keep.astype(np.int64), n_parts_feat)

    xy = np.ascontiguousarray(shapely.get_coordinates(parts),
                              dtype=np.float64)
    _yield()
    if xy.shape[0] == 0:
        return _empty_flat(kind, tol)

    plen = shapely.get_num_coordinates(parts)
    part_starts, part_ends = _pack_ranges(plen)

    if kind == "line":
        ring_starts, ring_ends = part_starts, part_ends
        outward = np.ones(ring_starts.size, dtype=bool)
        ring_geom = part_geom
        nring_part = np.ones(part_starts.size, dtype=np.int64)
    else:
        rings = shapely.get_rings(parts)
        _yield()
        rlen = shapely.get_num_coordinates(rings)
        if rlen.size == 0:
            return _empty_flat(kind, tol)
        ring_starts, ring_ends = _pack_ranges(rlen)
        nring_part = (shapely.get_num_interior_rings(parts) + 1).astype(
            np.int64)
        if int(nring_part.sum()) != int(ring_starts.size):
            raise ValueError("环数与部件数不自洽：%d vs %d"
                             % (int(nring_part.sum()),
                                int(ring_starts.size)))
        ring_geom = np.repeat(part_geom, nring_part)
        off = np.arange(int(ring_starts.size), dtype=np.int64) - np.repeat(
            np.cumsum(nring_part) - nring_part, nring_part)
        outward = (off == 0)
        xy = np.ascontiguousarray(shapely.get_coordinates(rings),
                                  dtype=np.float64)
        _yield()
        xy = _normalize_ring_winding(xy, ring_starts, ring_ends, outward)
        _yield()

    try:
        b = shapely.bounds(parts)
        bb = np.empty((b.shape[0], 5), dtype=np.float64)
        bb[:, 0] = part_geom
        bb[:, 1:5] = b
    except Exception:
        exc_note("_build_flat_vector @ ggis/render/rasterize.py:634")
        bb = np.zeros((0, 5), dtype=np.float64)
    _yield()

    if tol > 0 and no_simplify and xy.shape[0]:
        try:
            xy = np.round(xy / tol) * tol
            _pieces, _ns, _ne, _off = [], [], [], 0
            for _s, _e in zip(ring_starts.tolist(), ring_ends.tolist()):
                _seg = xy[_s:_e]
                _n = _seg.shape[0]
                if _n > 1:
                    _keep = np.concatenate(
                        ([True], np.any(_seg[1:] != _seg[:-1], axis=1)))
                    _seg = _seg[_keep]
                if _seg.shape[0] == 0 and _n > 0:
                    _seg = xy[_s:_s + 1]
                _pieces.append(_seg)
                _ns.append(_off)
                _off += _seg.shape[0]
                _ne.append(_off)
            if _pieces:
                xy = np.concatenate(_pieces, axis=0)
                ring_starts = np.asarray(_ns, dtype=np.int64)
                ring_ends = np.asarray(_ne, dtype=np.int64)
        except Exception:
            exc_note("_build_flat_vector @ ggis/render/rasterize.py:666")
            pass

    src_crs = None
    try:
        src_crs = layer.crs()
    except Exception:
        exc_note("_build_flat_vector @ ggis/render/rasterize.py:673")
        pass
    tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
    if tf is not None and xy.shape[0]:
        xy = convert_xy(xy, tf)
        bb = _reproject_boxes(bb, tf)
        _yield()

    return {
        "xy": xy,
        "part_starts": np.asarray(ring_starts, dtype=np.int64),
        "part_ends": np.asarray(ring_ends, dtype=np.int64),
        "part_geom": np.asarray(ring_geom, dtype=np.int64),
        "geom_bbox": bb,
        "kind": kind, "tol": tol,
    }


def _build_flat(layer, tol, kind, dst_crs=None, yield_fn=None,
               no_simplify=False):
    try:
        return _build_flat_vector(layer, kind, tol, dst_crs, yield_fn,
                                 no_simplify=no_simplify)
    except Exception:
        exc_note("_build_flat @ ggis/render/rasterize.py:700")
        return _build_flat_legacy(layer, tol, kind, dst_crs)


_LOD_CACHE_MAX = 24

_FLAT_LOCK = threading.Lock()


def flat_coords(layer, tol=0.0, kind=None, dst_crs=None, yield_fn=None,
                best_effort=False, force=False, no_simplify=False):
    if kind is None:
        kind = "line" if layer.base_kind() == "line" else "polygon"
    src_crs = None
    try:
        src_crs = layer.crs()
    except Exception:
        exc_note("flat_coords @ ggis/render/rasterize.py:751")
        pass
    tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
    ckey = crs_pair_key(src_crs, dst_crs) if tf is not None else ""
    level = quantize_tolerance(tol)
    if level > 0.0 and _lod_is_fine(layer, level, kind, dst_crs):
        f0 = flat_cached(layer, 0.0, kind, dst_crs)
        if f0 is None:
            f0 = flat_coords(layer, 0.0, kind=kind, dst_crs=dst_crs,
                             yield_fn=yield_fn)
        return f0
    key = (level, ckey)
    cache = layer.__dict__.get("_ggs_flat")
    if cache is None:
        cache = {}
        try:
            layer._ggs_flat = cache
        except Exception:
            exc_note("flat_coords @ ggis/render/rasterize.py:772")
            pass
    hit = cache.get(key)
    if hit is not None and not force:
        return hit
    if level > 0.0 and not force:
        disk = _lod_disk_load(layer, level, ckey, kind)
        if disk is not None:
            with _FLAT_LOCK:
                cache[key] = disk
            return disk
    data = _build_flat(layer, level, kind, dst_crs, yield_fn,
                       no_simplify=no_simplify)
    if best_effort:
        if not _FLAT_LOCK.acquire(False):
            return None
    else:
        _FLAT_LOCK.acquire()
    try:
        existing = cache.get(key)
        if existing is not None:
            return existing
        if len(cache) >= _LOD_CACHE_MAX:
            while len(cache) >= _LOD_CACHE_MAX + 1:
                for k in list(cache.keys()):
                    if k[0] != 0.0:
                        cache.pop(k, None)
                        break
                else:
                    break
        cache[key] = data
        if level > 0.0 and not getattr(layer, "_viewport_cull", False) \
                and not getattr(layer, "_geom_deferred", False):
            try:
                _nsrc = len(getattr(layer, "_geoms", None) or [])
            except Exception:
                exc_note("flat_coords @ ggis/render/rasterize.py:838")
                _nsrc = -1
            try:
                threading.Thread(target=_lod_disk_save,
                                 args=(layer, level, ckey, kind, data,
                                       _nsrc),
                                 daemon=True).start()
            except Exception:
                exc_note("flat_coords @ ggis/render/rasterize.py:821")
                pass
        return data
    finally:
        _FLAT_LOCK.release()


def flat_cached(layer, tol=0.0, kind=None, dst_crs=None):
    if kind is None:
        kind = "line" if layer.base_kind() == "line" else "polygon"
    src_crs = None
    try:
        src_crs = layer.crs()
    except Exception:
        exc_note("flat_cached @ ggis/render/rasterize.py:847")
        pass
    tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
    ckey = crs_pair_key(src_crs, dst_crs) if tf is not None else ""
    key = (quantize_tolerance(tol), ckey)
    try:
        cache = layer.__dict__.get("_ggs_flat")
    except Exception:
        exc_note("flat_cached @ ggis/render/rasterize.py:854")
        return None
    if not isinstance(cache, dict):
        return None
    return cache.get(key)


def nearest_flat_cached(layer, tol, kind=None, dst_crs=None):
    if kind is None:
        kind = "line" if layer.base_kind() == "line" else "polygon"
    src_crs = None
    try:
        src_crs = layer.crs()
    except Exception:
        exc_note("nearest_flat_cached @ ggis/render/rasterize.py:876")
        pass
    tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
    ckey = crs_pair_key(src_crs, dst_crs) if tf is not None else ""
    level = quantize_tolerance(float(tol or 0.0))
    try:
        cache = layer.__dict__.get("_ggs_flat")
    except Exception:
        exc_note("nearest_flat_cached @ ggis/render/rasterize.py:883")
        return None
    if not isinstance(cache, dict) or not cache:
        return None
    hit = cache.get((level, ckey))
    if hit is not None:
        return hit
    import math as _math
    best, best_d = None, None
    try:
        target = _math.log2(float(level)) if level > 0 else None
    except Exception:
        exc_note("nearest_flat_cached @ ggis/render/rasterize.py:894")
        target = None
    if target is None:
        return None
    for (lv, ck), flat in list(cache.items()):
        if ck != ckey or flat is None or not (float(lv) > 0.0):
            continue
        try:
            d = abs(_math.log2(float(lv)) - target)
        except Exception:
            exc_note("nearest_flat_cached @ ggis/render/rasterize.py:903")
            continue
        if best_d is None or d < best_d:
            best, best_d = flat, d
    return best


def _lod_native_res(layer, kind, dst_crs):
    if kind is None:
        kind = "line" if layer.base_kind() == "line" else "polygon"
    src_crs = None
    try:
        src_crs = layer.crs()
    except Exception:
        exc_note("_lod_native_res @ ggis/render/rasterize.py:925")
        pass
    tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
    ckey = crs_pair_key(src_crs, dst_crs) if tf is not None else ""
    try:
        cache = layer.__dict__.get("_ggs_flat")
    except Exception:
        exc_note("_lod_native_res @ ggis/render/rasterize.py:931")
        return None
    if not isinstance(cache, dict):
        return None
    _res_cache = layer.__dict__.get("_ggs_flat_native_res")
    if not isinstance(_res_cache, dict):
        _res_cache = {}
        try:
            layer._ggs_flat_native_res = _res_cache
        except Exception:
            exc_note("_lod_native_res @ ggis/render/rasterize.py:940")
            pass
    r = _res_cache.get(ckey)
    if r is not None:
        return r
    f0 = cache.get((0.0, ckey))
    if f0 is None:
        return None
    try:
        xy = f0.get("xy")
        starts = f0.get("part_starts")
        ends = f0.get("part_ends")
        if xy is None or starts is None or ends is None:
            return None
        tot = 0.0
        n = int(xy.shape[0])
        for s, e in zip(starts, ends):
            s = int(s)
            e = int(e)
            if e - s < 2:
                continue
            seg = xy[s:e]
            d = np.sqrt(((seg[1:] - seg[:-1]) ** 2).sum(1))
            tot += float(d.sum())
        res = (tot / n) if n > 0 else None
    except Exception:
        exc_note("_lod_native_res @ ggis/render/rasterize.py:965")
        res = None
    if res is not None:
        _res_cache[ckey] = res
    return res


def _lod_is_fine(layer, tol, kind=None, dst_crs=None):
    res = _lod_native_res(layer, kind, dst_crs)
    if res is None:
        return False
    level = quantize_tolerance(float(tol or 0.0))
    return level < res


_LOD_DISK_VER = 1


def _lod_disk_dir():
    import os
    try:
        from .. import app_paths
        d = os.path.join(app_paths.cache_dir(), "lod")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        exc_note("_lod_disk_dir @ ggis/render/rasterize.py:999")
        return None


def _lod_disk_key(layer, level, ckey, kind):
    import hashlib
    import os
    src = ""
    try:
        src = str(layer.source() or "")
    except Exception:
        exc_note("_lod_disk_key @ ggis/render/rasterize.py:1010")
        src = ""
    if not src:
        ident = ""
    else:
        try:
            st = os.stat(src)
            ident = "%s|%d|%d" % (src, int(st.st_mtime), int(st.st_size))
        except Exception:
            exc_note("_lod_disk_key @ ggis/render/rasterize.py:1015")
            ident = src
    try:
        nm = str(layer.name() or "")
    except Exception:
        exc_note("_lod_disk_key @ ggis/render/rasterize.py:1019")
        nm = ""
    raw = "%s|%s|%s|%s|%s" % (ident, nm, ckey, kind, repr(level))
    return hashlib.sha1(
        ("v%d|%s" % (_LOD_DISK_VER, raw)).encode("utf-8")).hexdigest()[:24]


def _lod_disk_path(layer, level, ckey, kind):
    import os
    d = _lod_disk_dir()
    if not d:
        return None
    return os.path.join(d, "lod_%s_%s.npz" % (kind,
                                              _lod_disk_key(layer, level,
                                                            ckey, kind)))


def _lod_disk_load(layer, level, ckey, kind):
    import os
    p = _lod_disk_path(layer, level, ckey, kind)
    if not p:
        return None
    if not os.path.exists(p):
        _log.debug("lod cache miss: %s", os.path.basename(p))
        return None
    try:
        with np.load(p) as z:
            if int(z["ver"]) != _LOD_DISK_VER:
                return None
            xy = z["xy"]
            if xy.ndim != 2 or xy.shape[1] != 2:
                return None
            if "nsrc" not in z.files:
                _log.debug("lod cache stale (no nsrc): %s",
                           os.path.basename(p))
                return None
            try:
                n_now = len(getattr(layer, "_geoms", None) or [])
            except Exception:
                exc_note("_lod_disk_load @ ggis/render/rasterize.py:1105")
                n_now = -1
            if int(z["nsrc"]) != n_now:
                _log.debug("lod cache stale (nsrc %d != %d): %s",
                           int(z["nsrc"]), n_now, os.path.basename(p))
                return None
            return {
                "xy": xy,
                "part_starts": z["part_starts"],
                "part_ends": z["part_ends"],
                "part_geom": z["part_geom"],
                "geom_bbox": z["geom_bbox"],
                "kind": kind,
                "tol": float(z["tol"]),
            }
    except FileNotFoundError:
        _log.debug("lod cache miss (raced): %s", os.path.basename(p))
        return None
    except Exception:
        exc_note("_lod_disk_load @ ggis/render/rasterize.py:1075")
        return None


def _lod_disk_save(layer, level, ckey, kind, flat, nsrc):
    import os
    p = _lod_disk_path(layer, level, ckey, kind)
    if not p or flat is None:
        return
    try:
        tmp = p + ".tmp.npz"
        np.savez_compressed(
            tmp, ver=np.int64(_LOD_DISK_VER), xy=flat["xy"],
            part_starts=flat["part_starts"], part_ends=flat["part_ends"],
            part_geom=flat["part_geom"], geom_bbox=flat["geom_bbox"],
            tol=np.float64(flat.get("tol") or 0.0),
            nsrc=np.int64(nsrc))
        os.replace(tmp, p)
    except Exception:
        exc_note("_lod_disk_save @ ggis/render/rasterize.py:1075")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            exc_note("_lod_disk_save @ ggis/render/rasterize.py:1079")
            pass


def invalidate_flat(layer):
    try:
        del layer.__dict__["_ggs_flat"]
    except Exception:
        exc_note("invalidate_flat @ ggis/render/rasterize.py:1086")
        pass


def warm_flat_chunked(layer, tol=0.0, dst_crs=None, should_stop=None,
                      yield_fn=None):
    if layer is None:
        return
    kind = "line" if layer.base_kind() == "line" else "polygon"
    levels = [0.0]
    if tol and tol > 0:
        q = quantize_tolerance(tol)
        if q not in levels:
            levels.append(q)
    for lv in levels:
        if should_stop is not None and should_stop():
            return
        try:
            flat_coords(layer, lv, kind=kind, dst_crs=dst_crs,
                        yield_fn=yield_fn)
        except Exception:
            exc_note("warm_flat_chunked @ ggis/render/rasterize.py:1125")
            pass
        if yield_fn is not None:
            try:
                yield_fn()
            except Exception:
                exc_note("warm_flat_chunked @ ggis/render/rasterize.py:1130")
                pass


_WIDTH_OFFSETS = {}


def clip_segments(x0, y0, x1, y1, xmin, ymin, xmax, ymax):
    n = int(x0.shape[0])
    if n == 0:
        return x0, y0, x1, y1, None
    if (x0.min(initial=0) >= xmin and x1.min(initial=0) >= xmin
            and x0.max(initial=0) <= xmax and x1.max(initial=0) <= xmax
            and y0.min(initial=0) >= ymin and y1.min(initial=0) >= ymin
            and y0.max(initial=0) <= ymax and y1.max(initial=0) <= ymax):
        return x0, y0, x1, y1, None

    dtype = np.float32 if x0.dtype == np.float32 else np.float64
    dx = (x1 - x0).astype(dtype, copy=False)
    dy = (y1 - y0).astype(dtype, copy=False)
    t0 = np.zeros(n, dtype=dtype)
    t1 = np.ones(n, dtype=dtype)
    outside = np.zeros(n, dtype=bool)
    r = np.empty(n, dtype=dtype)
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0),
                 (-dy, y0 - ymin), (dy, ymax - y0)):
        with np.errstate(divide="ignore", invalid="ignore"):
            np.divide(q, p, out=r, where=(p != 0))
        neg = p < 0
        if neg.any():
            m = neg & (r > t0)
            t0[m] = r[m]
        pos = p > 0
        if pos.any():
            m = pos & (r < t1)
            t1[m] = r[m]
        zero = p == 0
        if zero.any():
            outside |= zero & (q < 0)
    ok = (t0 <= t1) & ~outside
    if ok.all():
        return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy, None)
    keep = np.nonzero(ok)[0]
    if keep.size == 0:
        z = x0[:0]
        return z, z, z, z, keep
    x0 = x0[keep]
    y0 = y0[keep]
    t0 = t0[keep]
    t1 = t1[keep]
    dx = dx[keep]
    dy = dy[keep]
    return (x0 + t0 * dx, y0 + t0 * dy, x0 + t1 * dx, y0 + t1 * dy, keep)


def adjacency_mask(n_pts, ends):
    m = np.ones(max(0, n_pts - 1), dtype=bool)
    if m.size and len(ends):
        m[ends[:-1] - 1] = False
    return m


def _width_offsets(width: int):
    w = max(1, int(width))
    hit = _WIDTH_OFFSETS.get(w)
    if hit is not None:
        return hit
    lo = -(w // 2)
    hi = lo + w
    offs = [(dx, dy) for dy in range(lo, hi) for dx in range(lo, hi)]
    arr = np.asarray(offs, dtype=np.int32)
    _WIDTH_OFFSETS[w] = arr
    return arr


_ROUND_OFFSETS: dict = {}


def _round_offsets(width):
    w = max(1, int(width))
    hit = _ROUND_OFFSETS.get(w)
    if hit is not None:
        return hit
    rad = w / 2.0
    lim = rad * rad
    r = int(rad)
    offs = [(dx, dy) for dy in range(-r, r + 1)
            for dx in range(-r, r + 1) if dx * dx + dy * dy <= lim]
    if not offs:
        offs = [(0, 0)]
    arr = np.asarray(offs, dtype=np.int32)
    if len(_ROUND_OFFSETS) > 24:
        _ROUND_OFFSETS.clear()
    _ROUND_OFFSETS[w] = arr
    return arr


def estimate_samples(x0, y0, x1, y1):
    if x0.size == 0:
        return 0
    k = np.maximum(np.abs(x1 - x0), np.abs(y1 - y0))
    return int(np.ceil(k).astype(np.int64).sum()) + int(x0.size)


def sample_segments(x0, y0, x1, y1, values=None, chunk=1_200_000, dash=None):
    n = int(x0.shape[0])
    empty = (np.zeros(0, dtype=np.int32), np.zeros(0, dtype=np.int32))
    if n == 0:
        return (empty + (np.zeros(0, dtype=np.uint8),)) if values is not None \
            else empty

    x0 = np.asarray(x0, dtype=np.float32)
    y0 = np.asarray(y0, dtype=np.float32)
    x1 = np.asarray(x1, dtype=np.float32)
    y1 = np.asarray(y1, dtype=np.float32)
    dx = x1 - x0
    dy = y1 - y0
    kk = np.ceil(np.maximum(np.abs(dx), np.abs(dy))).astype(np.int64) + 1
    cum = np.cumsum(kk)
    total = int(cum[-1])
    if total <= 0:
        return (empty + (np.zeros(0, dtype=np.uint8),)) if values is not None \
            else empty

    if values is not None:
        values = np.asarray(values, dtype=np.uint8)

    dash_cum = None
    period = 0.0
    s0 = None
    seg_len = None
    if dash is not None:
        try:
            pat = [float(v) for v in dash]
        except Exception:
            exc_note("sample_segments @ ggis/render/rasterize.py:1315")
            pat = []
        pat = [v for v in pat if v > 0.0]
        if len(pat) >= 2 and len(pat) % 2 == 0:
            dash_cum = np.cumsum(np.asarray(pat, dtype=np.float64))
            period = float(dash_cum[-1])
            seg_len = np.sqrt(dx.astype(np.float64) ** 2
                              + dy.astype(np.float64) ** 2)
            starts = np.ones(n, dtype=bool)
            if n > 1:
                starts[1:] = (x0[1:] != x1[:-1]) | (y0[1:] != y1[:-1])
            cs = np.cumsum(seg_len)
            head = np.flatnonzero(starts)
            base = np.zeros(head.size, dtype=np.float64)
            if head.size > 1:
                base[1:] = cs[head[1:] - 1]
            s0 = cs - seg_len - base[np.cumsum(starts) - 1]

    xs_out = []
    ys_out = []
    vs_out = [] if values is not None else None
    start_seg = 0
    base_cum = 0
    while start_seg < n:
        end_seg = int(np.searchsorted(cum, base_cum + chunk,
                                      side="right"))
        if end_seg <= start_seg:
            end_seg = start_seg + 1
        end_seg = min(end_seg, n)
        km = kk[start_seg:end_seg]
        reps = int(km.sum())
        seg_rel = np.repeat(np.arange(end_seg - start_seg, dtype=np.int64),
                            km)
        base = np.repeat(cum[start_seg:end_seg] - km, km)
        pos = np.arange(base_cum, base_cum + reps, dtype=np.int64)
        t = (pos - base).astype(np.float32)
        inv = np.reciprocal(np.maximum(km - 1, 1).astype(np.float32))
        t *= inv[seg_rel]
        ax = x0[start_seg:end_seg][seg_rel]
        ay = y0[start_seg:end_seg][seg_rel]
        xs = ax
        xs += dx[start_seg:end_seg][seg_rel] * t
        ys = ay
        ys += dy[start_seg:end_seg][seg_rel] * t
        vs = values[start_seg:end_seg][seg_rel] if vs_out is not None else None
        if dash_cum is not None:
            mile = s0[start_seg:end_seg][seg_rel] \
                + t.astype(np.float64) * seg_len[start_seg:end_seg][seg_rel]
            idx = np.searchsorted(dash_cum,
                                  np.mod(mile, period), side="right")
            on = (idx % 2) == 0
            if not on.all():
                xs = xs[on]
                ys = ys[on]
                if vs is not None:
                    vs = vs[on]
        xs_out.append(np.rint(xs).astype(np.int32))
        ys_out.append(np.rint(ys).astype(np.int32))
        if vs_out is not None:
            vs_out.append(vs)
        base_cum = int(cum[end_seg - 1])
        start_seg = end_seg
    if vs_out is None:
        return (np.concatenate(xs_out), np.concatenate(ys_out))
    return (np.concatenate(xs_out), np.concatenate(ys_out),
            np.concatenate(vs_out))


def polygon_diff(xy, starts, ends, sx, sy, xmin, ymax, w, h, pad):
    shape = (h + 2 * pad, w + 2 * pad + 1)
    diff = np.zeros(shape, dtype=np.int32)
    if xy.shape[0] == 0 or len(starts) == 0:
        return diff

    px = (xy[:, 0] - xmin) * sx + pad
    py = (ymax - xy[:, 1]) * sy + pad
    idx = np.nonzero(adjacency_mask(xy.shape[0], ends))[0]
    a = idx
    b = idx + 1
    ax = px[a]
    ay = py[a]
    bx = px[b]
    by = py[b]

    nonh = ay != by
    ax, ay, bx, by = ax[nonh], ay[nonh], bx[nonh], by[nonh]
    if ax.size == 0:
        return diff

    lo = np.minimum(ay, by)
    hi = np.maximum(ay, by)
    r0 = np.ceil(lo - 0.5).astype(np.int64)
    r1 = np.floor(hi - 0.5).astype(np.int64)
    cnt = r1 - r0 + 1
    keep = cnt > 0
    ax, ay, bx, by = ax[keep], ay[keep], bx[keep], by[keep]
    r0, cnt = r0[keep], cnt[keep]
    if ax.size == 0:
        return diff

    total = int(cnt.sum())
    rows = np.repeat(r0, cnt)
    rows += np.arange(total, dtype=np.int64) - np.repeat(
        np.cumsum(cnt) - cnt, cnt)
    edge = np.repeat(np.arange(ax.size, dtype=np.int64), cnt)
    dy = (by - ay)[edge]
    dy_safe = np.where(dy == 0, 1.0, dy)
    xint = ax[edge] + (rows + 0.5 - ay[edge]) * (bx - ax)[edge] / dy_safe
    xi = np.rint(xint).astype(np.int64)
    sign = np.where(dy > 0, 1, -1).astype(np.int64)

    valid = (rows >= 0) & (rows < shape[0])
    rows = rows[valid]
    xi = xi[valid]
    sign = sign[valid]
    if rows.size == 0:
        return diff
    np.clip(xi, 0, shape[1] - 1, out=xi)

    flat = rows * shape[1] + xi
    counts = np.bincount(flat, weights=sign, minlength=shape[0] * shape[1])
    diff += np.rint(counts).astype(np.int32).reshape(shape)
    return diff


_PATTERN_CACHE: dict = {}
_PATTERN_CACHE_MAX = 3
_PATTERN_CACHE_PIXELS = 6_000_000


def _pattern_mask(shape, pad2, kind, spacing, width):
    key = (int(shape[0]), int(shape[1]), int(pad2), str(kind),
           round(float(spacing), 2), round(float(width), 2))
    hit = _PATTERN_CACHE.get(key)
    if hit is not None:
        return hit
    h, w = int(shape[0]), int(shape[1])
    yy = (np.arange(h, dtype=np.float32) - float(pad2))[:, None]
    xx = (np.arange(w, dtype=np.float32) - float(pad2))[None, :]
    s = max(2.0, float(spacing))
    t = max(1.0, float(width))
    k = str(kind)
    if k == "horizontal":
        mask = np.mod(yy, s) < t
    elif k == "vertical":
        mask = np.mod(xx, s) < t
    elif k == "diagonal":
        mask = np.mod(xx + yy, s) < t
    elif k == "back_diagonal":
        mask = np.mod(xx - yy, s) < t
    elif k == "cross":
        mask = (np.mod(yy, s) < t) | (np.mod(xx, s) < t)
    elif k == "diagonal_cross":
        mask = ((np.mod(xx + yy, s) < t) | (np.mod(xx - yy, s) < t))
    else:
        return None
    mask = np.ascontiguousarray(mask)
    if mask.size <= _PATTERN_CACHE_PIXELS:
        if len(_PATTERN_CACHE) >= _PATTERN_CACHE_MAX:
            _PATTERN_CACHE.clear()
        _PATTERN_CACHE[key] = mask
    return mask


class GgsCoverage:

    __slots__ = ("w", "h", "pad", "cov", "_last", "ss", "w2", "h2", "pad2",
                 "_fill_pattern")

    def __init__(self, w, h, pad=1, ss=1):
        self.w = int(w)
        self.h = int(h)
        self.pad = int(pad)
        self.ss = max(1, int(ss))
        self.w2 = self.w * self.ss
        self.h2 = self.h * self.ss
        self.pad2 = self.pad * self.ss
        self.cov = np.zeros((self.h2 + 2 * self.pad2,
                             self.w2 + 2 * self.pad2), dtype=np.uint8)
        self._last = None
        self._fill_pattern = None

    def set_fill_pattern(self, kind, spacing=8.0, width=1.0):
        try:
            k = str(kind or "solid")
            if k == "solid":
                self._fill_pattern = None
                return
            self._fill_pattern = _pattern_mask(self.cov.shape, self.pad2,
                                               k, spacing, width)
        except Exception:
            exc_note("set_fill_pattern @ ggis/render/rasterize.py:1560")
            self._fill_pattern = None

    def stamp(self, xi, yi, value=1):
        if xi.size == 0:
            return
        np.clip(xi, 0, self.cov.shape[1] - 1, out=xi)
        np.clip(yi, 0, self.cov.shape[0] - 1, out=yi)
        self.cov[yi, xi] = value

    def stroke_pixels(self, xi, yi, value, width=1, round_cap=False):
        if xi.size == 0:
            return
        lim = self.cov.shape[1] - 1
        limy = self.cov.shape[0] - 1
        if width <= 1:
            np.clip(xi, 0, lim, out=xi)
            np.clip(yi, 0, limy, out=yi)
            self.cov[yi, xi] = value
            return
        offs = _round_offsets(width) if round_cap else _width_offsets(width)
        for dx, dy in offs:
            xs = xi if dx == 0 else xi + dx
            ys = yi if dy == 0 else yi + dy
            if dx:
                np.clip(xs, 0, lim, out=xs)
            if dy:
                np.clip(ys, 0, limy, out=ys)
            self.cov[ys, xs] = value

    def fill_from_diff(self, diff, value=1, only_where_zero=False):
        winding = np.cumsum(diff, axis=1)[:, :self.cov.shape[1]]
        mask = winding != 0
        if self._fill_pattern is not None:
            mask &= self._fill_pattern
        if only_where_zero:
            mask &= (self.cov == 0)
        self.cov[mask] = value
        return int(mask.sum())

    def lut_image(self, colors=None, lut=None):
        from PySide6.QtGui import QImage
        if lut is None:
            lut = np.zeros((256, 4), dtype=np.uint8)
            for i, c in enumerate(colors or ()):
                if i < 256:
                    lut[i] = c
        sub = self.cov[self.pad2:self.pad2 + self.h2,
                       self.pad2:self.pad2 + self.w2]
        if self.ss <= 1:
            rgba = np.ascontiguousarray(lut[sub])
            self._last = rgba
            img = QImage(rgba.data, self.w, self.h, self.w * 4,
                         QImage.Format.Format_RGBA8888)
            return img, rgba

        blk = sub.reshape(self.h, self.ss, self.w, self.ss)
        v = blk.swapaxes(1, 2).reshape(self.h, self.w,
                                       self.ss * self.ss)
        cnt = (v != 0).sum(axis=2)
        main = v.max(axis=2)
        rgba = lut[main]
        a = rgba[:, :, 3].astype(np.uint16) * cnt
        rgba[:, :, 3] = (a // (self.ss * self.ss)).astype(np.uint8)
        rgba = np.ascontiguousarray(rgba)
        self._last = rgba
        img = QImage(rgba.data, self.w, self.h, self.w * 4,
                     QImage.Format.Format_RGBA8888)
        return img, rgba

    def stroke_pixels_v(self, xi, yi, vi, width=1, round_cap=False):
        if xi.size == 0:
            return
        lim = self.cov.shape[1] - 1
        limy = self.cov.shape[0] - 1
        if width <= 1:
            np.clip(xi, 0, lim, out=xi)
            np.clip(yi, 0, limy, out=yi)
            self.cov[yi, xi] = vi
            return
        for dx, dy in (_round_offsets(width) if round_cap
                       else _width_offsets(width)):
            xs = xi if dx == 0 else xi + dx
            ys = yi if dy == 0 else yi + dy
            if dx:
                np.clip(xs, 0, lim, out=xs)
            if dy:
                np.clip(ys, 0, limy, out=ys)
            self.cov[ys, xs] = vi
