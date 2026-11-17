# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
import logging
_log = logging.getLogger("gmagis")

try:
    from rtree import index as _rtree_index
except Exception:
    _log.exception("silent exception")
    _rtree_index = None

try:
    from shapely.geometry import LineString as _LineString
    from shapely.geometry import Point as _Point
except Exception:
    _log.exception("silent exception")
    _LineString = _Point = None


__all__ = ["SnapResult", "GgsSnapper", "SNAP_ENDPOINT", "SNAP_VERTEX",
           "SNAP_INTERSECTION", "SNAP_MIDPOINT", "SNAP_EDGE",
           "ALL_SNAP_KINDS", "SNAP_PRIORITY",
           "MAX_INTERSECTION_SEGMENTS"]

SNAP_ENDPOINT = "endpoint"
SNAP_VERTEX = "vertex"
SNAP_INTERSECTION = "intersection"
SNAP_MIDPOINT = "midpoint"
SNAP_EDGE = "edge"

ALL_SNAP_KINDS = (SNAP_ENDPOINT, SNAP_VERTEX, SNAP_INTERSECTION,
                  SNAP_MIDPOINT, SNAP_EDGE)

SNAP_PRIORITY = {
    SNAP_ENDPOINT: 0,
    SNAP_VERTEX: 1,
    SNAP_INTERSECTION: 2,
    SNAP_MIDPOINT: 3,
    SNAP_EDGE: 4,
}

MAX_INTERSECTION_SEGMENTS = 200


@dataclass(frozen=True)
class SnapResult:

    point: Tuple[float, float]
    kind: str
    layer_id: str
    feature_row: int
    vertex_index: Optional[int] = None
    distance_px: float = 0.0

    other_row: Optional[int] = None


def _iter_parts(geom):
    if geom is None:
        return
    gt = getattr(geom, "geom_type", "")
    if gt == "Point":
        yield 0, 0, [(float(geom.x), float(geom.y))]
        return
    if gt == "MultiPoint":
        for i, g in enumerate(geom.geoms):
            yield i, 0, [(float(g.x), float(g.y))]
        return
    if gt in ("LineString", "LinearRing"):
        c = list(geom.coords)
        if c:
            yield 0, 0, [(float(x), float(y)) for x, y, *_ in c]
        return
    if gt == "MultiLineString":
        for i, g in enumerate(geom.geoms):
            c = list(g.coords)
            if c:
                yield i, 0, [(float(x), float(y)) for x, y, *_ in c]
        return
    if gt == "Polygon":
        rings = [geom.exterior] + list(geom.interiors)
        for r, ring in enumerate(rings):
            if ring is None:
                continue
            c = list(ring.coords)
            if c:
                yield 0, r, [(float(x), float(y)) for x, y, *_ in c]
        return
    if gt == "MultiPolygon":
        for i, g in enumerate(geom.geoms):
            rings = [g.exterior] + list(g.interiors)
            for r, ring in enumerate(rings):
                if ring is None:
                    continue
                c = list(ring.coords)
                if c:
                    yield i, r, [(float(x), float(y)) for x, y, *_ in c]
        return
    if hasattr(geom, "geoms"):
        for sub in geom.geoms:
            for item in _iter_parts(sub):
                yield item


def _segments_of(geom):
    out = []
    for _pi, _ri, coords in _iter_parts(geom):
        if len(coords) < 2:
            continue
        for k in range(len(coords) - 1):
            a, b = coords[k], coords[k + 1]
            if a == b:
                continue
            out.append((a[0], a[1], b[0], b[1]))
    return out


def _seg_intersect(s1, s2):
    x1, y1, x2, y2 = s1
    x3, y3, x4, y4 = s2
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-14:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def _foot_on_segment(seg, mx, my):
    x1, y1, x2, y2 = seg
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 <= 0.0:
        return float(x1), float(y1), 0.0
    t = ((mx - x1) * dx + (my - y1) * dy) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return float(x1 + t * dx), float(y1 + t * dy), float(t)


class _LayerVertexIndex:

    def __init__(self, layer):
        self.layer = layer
        self.lid = str(layer.id())
        self.verts: Dict[int, Tuple[int, int, int, int, float, float]] = {}
        self.endpoints: Set[int] = set()
        self._idx = self._end = None
        self._stale = True
        self._next_key = 0

    def _make(self):
        if _rtree_index is None:
            return None
        try:
            props = _rtree_index.Property()
            props.dimension = 2
            return _rtree_index.Index(properties=props)
        except Exception:
            _log.exception("silent exception in _make")
            return None

    def rebuild(self):
        self.verts.clear()
        self.endpoints.clear()
        self._idx = self._make()
        self._end = self._make()
        geoms = self.layer.geoms()
        key = 0
        for fid, geom in enumerate(geoms):
            key = self._add_vertices(fid, geom, key)
        self._next_key = key
        self._stale = False

    def _add_vertices(self, fid, geom, key):
        for part, ring, coords in _iter_parts(geom) or ():
            if not coords:
                continue
            last = len(coords) - 1
            closed = (len(coords) > 2 and coords[0] == coords[-1])
            for vi, (x, y) in enumerate(coords):
                if closed and vi == last:
                    continue
                self.verts[key] = (int(fid), part, ring, vi, float(x),
                                   float(y))
                self._insert(self._idx, key, x, y)
                if vi == 0 or (not closed and vi == last):
                    self.endpoints.add(key)
                    self._insert(self._end, key, x, y)
                key += 1
        return key

    @staticmethod
    def _insert(idx, key, x, y):
        if idx is None:
            return
        try:
            idx.insert(int(key), (float(x), float(y), float(x), float(y)))
        except Exception:
            _log.exception("silent exception in _insert")

    @staticmethod
    def _delete(idx, key, x, y):
        if idx is None:
            return
        try:
            idx.delete(int(key), (float(x), float(y), float(x), float(y)))
        except Exception:
            _log.exception("silent exception in _delete")

    def invalidate(self):
        self._stale = True

    def ensure(self):
        if self._stale or self._idx is None:
            self.rebuild()

    def update_feature(self, fid, geom):
        self.ensure()
        fid = int(fid)
        for k in [k for k, v in self.verts.items() if v[0] == fid]:
            _f, _p, _r, _vi, x, y = self.verts.pop(k)
            self._delete(self._idx, k, x, y)
            if k in self.endpoints:
                self._delete(self._end, k, x, y)
                self.endpoints.discard(k)
        self._next_key = self._add_vertices(fid, geom, self._next_key)

    def nearby(self, x, y, tol, want_endpoints):
        li = self._end if want_endpoints else self._idx
        if li is None:
            return
        box = (x - tol, y - tol, x + tol, y + tol)
        try:
            hits = li.intersection(box)
        except Exception:
            _log.exception("silent exception in nearby")
            self._stale = True
            return
        pool = self.endpoints if want_endpoints else None
        for k in hits:
            k = int(k)
            if pool is not None and k not in pool:
                continue
            info = self.verts.get(k)
            if info is None:
                continue
            yield k, info


class GgsSnapper:

    def __init__(self, tolerance_px: float = 8.0):
        self.tolerance_px = float(tolerance_px)
        self.kinds: Set[str] = set(ALL_SNAP_KINDS)
        self._layers: Dict[str, _LayerVertexIndex] = {}
        self.last: Optional[SnapResult] = None

    def register_layer(self, layer):
        if layer is None:
            return
        lid = str(layer.id())
        if lid in self._layers and self._layers[lid].layer is layer:
            return
        self._layers[lid] = _LayerVertexIndex(layer)

    def unregister_layer(self, layer):
        self._layers.pop(str(getattr(layer, "id", lambda: layer)()), None)

    def clear(self):
        self._layers.clear()
        self.last = None

    def layers(self):
        return [v.layer for v in self._layers.values()]

    def rebuild(self, layer_id=None, rows=None):
        for lid, li in self._layers.items():
            if layer_id is not None and lid != str(layer_id):
                continue
            if rows is None:
                li.invalidate()
                continue
            geoms = li.layer.geoms()
            for fid in rows:
                fid = int(fid)
                if 0 <= fid < len(geoms):
                    li.update_feature(fid, geoms[fid])

    def invalidate(self, layer=None):
        for lid, li in self._layers.items():
            if layer is None or lid == str(layer.id()):
                li.invalidate()

    def snap(self, map_pos, scale, kinds=None, exclude_layer=None,
             exclude_vertex=None):
        kinds = set(kinds if kinds is not None else self.kinds)
        if not kinds or map_pos is None:
            return None
        mx, my = float(map_pos[0]), float(map_pos[1])
        tol = max(1e-12, float(self.tolerance_px) * float(scale))

        best = None
        do_vertex = bool(kinds & {SNAP_ENDPOINT, SNAP_VERTEX})
        for lid, li in self._layers.items():
            if exclude_layer is not None and lid == str(exclude_layer.id()):
                continue
            if not do_vertex:
                break
            li.ensure()
            for bucket, kind, prio in ((True, SNAP_ENDPOINT, 0),
                                       (False, SNAP_VERTEX, 1)):
                if kind not in kinds:
                    continue
                for _k, info in li.nearby(mx, my, tol, bucket):
                    _fid, _part, _ring, vi, px, py = info
                    if exclude_vertex is not None:
                        _el, _ef, _ev = exclude_vertex
                        if (str(_el) == lid and int(_ef) == int(_fid)
                                and int(_ev) == int(vi)):
                            continue
                    d = math.hypot(px - mx, py - my)
                    if d > tol:
                        continue
                    cand = SnapResult(
                        point=(float(px), float(py)), kind=kind,
                        layer_id=lid, feature_row=int(_fid),
                        vertex_index=int(vi), distance_px=d / float(scale))
                    if best is None or (prio, cand.distance_px) < \
                            (best[0], best[1].distance_px):
                        best = (prio, cand)

        if best is not None:
            self.last = best[1]
            return best[1]

        if SNAP_INTERSECTION in kinds:
            res = self._snap_intersection(mx, my, tol, scale, exclude_layer)
            if res is not None:
                self.last = res
                return res

        if SNAP_MIDPOINT in kinds:
            res = self._snap_midpoint(mx, my, tol, scale, exclude_layer)
            if res is not None:
                self.last = res
                return res

        if SNAP_EDGE in kinds:
            res = self._snap_edge(mx, my, tol, scale, exclude_layer)
            self.last = res
            return res

        self.last = None
        return None

    def _segments_near(self, mx, my, tol, exclude_layer):
        pool = []
        box = (mx - tol, my - tol, mx + tol, my + tol)
        for lid, li in self._layers.items():
            if exclude_layer is not None and lid == str(exclude_layer.id()):
                continue
            layer = li.layer
            geoms = layer.geoms()
            try:
                fids = layer.query_bbox(box[0], box[1], box[2], box[3])
            except Exception:
                _log.exception("silent exception in _segments_near")
                continue
            for fid in fids:
                fid = int(fid)
                if not (0 <= fid < len(geoms)):
                    continue
                for seg in _segments_of(geoms[fid]):
                    pool.append((lid, fid, seg))
                    if len(pool) > MAX_INTERSECTION_SEGMENTS:
                        return pool
        return pool

    def _best_segment_candidate(self, mx, my, tol, exclude_layer, pick):
        best = None
        for lid, fid, seg in self._segments_near(mx, my, tol, exclude_layer):
            px, py = pick(seg, mx, my)
            d = math.hypot(px - mx, py - my)
            if d > tol:
                continue
            if best is None or d < best[0]:
                best = (d, px, py, lid, fid)
        return best

    @staticmethod
    def _seg_midpoint(seg, _mx, _my):
        x1, y1, x2, y2 = seg
        return (x1 + x2) / 2.0, (y1 + y2) / 2.0

    def _snap_midpoint(self, mx, my, tol, scale, exclude_layer):
        best = self._best_segment_candidate(mx, my, tol, exclude_layer,
                                            self._seg_midpoint)
        if best is None:
            return None
        d, px, py, lid, fid = best
        return SnapResult(point=(float(px), float(py)), kind=SNAP_MIDPOINT,
                          layer_id=lid, feature_row=int(fid),
                          vertex_index=None,
                          distance_px=d / float(scale))

    def _snap_edge(self, mx, my, tol, scale, exclude_layer):
        best = self._best_segment_candidate(
            mx, my, tol, exclude_layer,
            lambda seg, x, y: _foot_on_segment(seg, x, y)[:2])
        if best is None:
            return None
        d, px, py, lid, fid = best
        return SnapResult(point=(float(px), float(py)), kind=SNAP_EDGE,
                          layer_id=lid, feature_row=int(fid),
                          vertex_index=None,
                          distance_px=d / float(scale))

    def _snap_intersection(self, mx, my, tol, scale, exclude_layer):
        pool = self._segments_near(mx, my, tol, exclude_layer)
        if len(pool) < 2 or len(pool) > MAX_INTERSECTION_SEGMENTS:
            return None
        best_pt = None
        best_d = None
        best_pair = (None, None)
        n = len(pool)
        for i in range(n):
            for j in range(i + 1, n):
                li_i, fid_i, s_i = pool[i]
                li_j, fid_j, s_j = pool[j]
                if fid_i == fid_j and li_i == li_j:
                    continue
                pt = _seg_intersect(s_i, s_j)
                if pt is None:
                    continue
                d = math.hypot(pt[0] - mx, pt[1] - my)
                if d > tol:
                    continue
                if best_d is None or d < best_d:
                    best_d = d
                    best_pt = pt
                    best_pair = ((li_i, fid_i), (li_j, fid_j))
        if best_pt is None:
            return None
        (lid, fid), (_lid2, fid2) = best_pair
        return SnapResult(point=(float(best_pt[0]), float(best_pt[1])),
                          kind=SNAP_INTERSECTION, layer_id=lid,
                          feature_row=int(fid), vertex_index=None,
                          distance_px=best_d / float(scale),
                          other_row=int(fid2))
