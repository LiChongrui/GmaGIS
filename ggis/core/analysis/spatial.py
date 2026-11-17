# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List, Sequence, Tuple

import numpy as np

from ggis.exec import guard as _guard
import logging
_log = logging.getLogger("gmagis")


try:
    from shapely import STRtree as _STRtree
    from shapely import is_empty as _shp_is_empty
    from shapely.geometry import box as _shp_box
    from shapely.geometry import Point as _shp_point
except Exception:
    _log.exception("silent exception")
    _STRtree = _shp_box = _shp_point = _shp_is_empty = None

try:
    from rtree import index as _rtree_index
except Exception:
    _log.exception("silent exception")
    _rtree_index = None



__all__ = ["GgsSpatialIndex", "GgsEditableIndex", "install_editable_index",
           "simplify_geom", "simplify_coords"]


def _bulk_bounds(geoms):
    n = len(geoms)
    if n == 0:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 4))
    try:
        from shapely import bounds as _shp_bounds
        arr = np.empty(n, dtype=object)
        arr[:] = geoms
        b = np.asarray(_shp_bounds(arr), dtype=np.float64).reshape(-1, 4)
    except Exception:
        _log.exception("silent exception in _bulk_bounds")
        b = np.empty((n, 4), dtype=np.float64)
        for i, g in enumerate(geoms):
            try:
                bb = g.bounds
            except Exception:
                _log.exception("silent exception in _bulk_bounds")
                bb = (np.nan, np.nan, np.nan, np.nan)
            b[i] = bb if len(bb) == 4 else (np.nan, np.nan, np.nan, np.nan)
    if b.shape[0] != n:
        return np.zeros(0, dtype=np.int64), np.zeros((0, 4))
    ok = np.isfinite(b).all(axis=1)
    ids = np.nonzero(ok)[0].astype(np.int64)
    return ids, b[ok]


class GgsSpatialIndex:

    @staticmethod
    def for_layer(layer):
        cached = getattr(layer, "_ggs_sidx", None)
        if cached is not None and cached._matches(layer):
            return cached
        cached = GgsSpatialIndex(layer)
        try:
            layer._ggs_sidx = cached
        except Exception:
            _log.exception("silent exception in for_layer")
        return cached

    def __init__(self, layer):
        self._layer = layer
        self._tree = None
        self._idx = None
        self._ids = np.zeros(0, dtype=np.int64)
        self._n = 0
        self.backend = "none"
        self._build()

    def _matches(self, layer):
        try:
            return self._n == layer.feature_count()
        except Exception:
            _log.exception("silent exception in _matches")
            return False

    def _build(self):
        geoms = self._layer.geoms()
        n = len(geoms)
        if n == 0:
            return
        self._n = n
        if _STRtree is not None:
            if self._build_strtree(geoms, n):
                return
        if self._build_rtree(geoms, n):
            return
        self._ids = np.arange(n, dtype=np.int64)
        self.backend = "linear"

    def _build_strtree(self, geoms, n):
        try:
            arr = np.empty(n, dtype=object)
            arr[:] = geoms
            if _shp_is_empty is not None and _shp_point is not None:
                bad = np.asarray(_shp_is_empty(arr), dtype=bool)
                bad |= np.fromiter((g is None for g in arr),
                                   dtype=bool, count=n)
                if bad.any():
                    arr[bad] = _shp_point()
            self._tree = _STRtree(arr)
            self._ids = np.arange(n, dtype=np.int64)
            self.backend = "strtree"
            return True
        except Exception:
            _log.exception("silent exception in _build_strtree")
            self._tree = None
            return False

    def _build_rtree(self, geoms, n):
        if _rtree_index is None:
            return False
        ids, boxes = _bulk_bounds(geoms)
        if ids.size == 0:
            return False
        try:
            props = _rtree_index.Property()
            props.dimension = 2
            self._idx = _rtree_index.Index(properties=props)
            for f, b in zip(ids, boxes):
                self._idx.insert(int(f), (float(b[0]), float(b[1]),
                                          float(b[2]), float(b[3])))
        except Exception:
            _log.exception("silent exception in _build_rtree")
            self._idx = None
            return False
        self._ids = ids
        self._n = n
        self.backend = "rtree"
        return True

    def _raw_query(self, xmin, ymin, xmax, ymax):
        if self._tree is not None:
            q = _shp_box(xmin, ymin, xmax, ymax)
            return np.asarray(self._tree.query(q), dtype=np.int64)
        if self._idx is not None:
            hits = self._idx.intersection((xmin, ymin, xmax, ymax))
            if isinstance(hits, np.ndarray):
                return hits.astype(np.int64, copy=False)
            return np.fromiter(hits, dtype=np.int64)
        return self._ids

    def query_array(self, xmin, ymin, xmax, ymax) -> np.ndarray:
        if self._tree is None and self._idx is None:
            return self._ids
        try:
            out = self._raw_query(xmin, ymin, xmax, ymax)
        except Exception:
            _log.exception("silent exception in query_array")
            return self._ids
        out.sort()
        return out

    def query(self, xmin, ymin, xmax, ymax) -> List[int]:
        return self.query_array(xmin, ymin, xmax, ymax).tolist()


class GgsEditableIndex:

    def __init__(self, layer):
        self._layer = layer
        self._idx = None
        self._n = 0
        self._stale = True
        self.backend = "editable"
        self._boxes = {}

    def _matches(self, layer):
        return layer is self._layer

    def _ensure(self):
        if self._stale or self._idx is None:
            self._build()

    def _build(self):
        self._idx = None
        self._boxes = {}
        if _rtree_index is None:
            self.backend = "editable-linear"
            self._stale = False
            return
        try:
            props = _rtree_index.Property()
            props.dimension = 2
            idx = _rtree_index.Index(properties=props)
        except Exception:
            _log.exception("silent exception in _build")
            self.backend = "editable-linear"
            self._stale = False
            return
        geoms = self._layer.geoms()
        ids, boxes = _bulk_bounds(geoms)
        for k in range(ids.size):
            f = int(ids[k])
            b = boxes[k]
            box = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
            try:
                idx.insert(f, box)
            except Exception:
                _log.exception("silent exception in _build")
                continue
            self._boxes[f] = box
        self._idx = idx
        self._n = len(geoms)
        self._stale = False
        self.backend = "editable-rtree"

    def _bounds_of(self, geom):
        try:
            b = geom.bounds
        except Exception:
            _log.exception("silent exception in _bounds_of")
            return None
        if b is None or len(b) != 4:
            return None
        try:
            box = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
        except Exception:
            _log.exception("silent exception in _bounds_of")
            return None
        if any(v != v for v in box):
            return None
        return box

    def update(self, fid, geom):
        fid = int(fid)
        self._n = max(self._n, fid + 1)
        self._ensure()
        if self._idx is None:
            return
        old = self._boxes.pop(fid, None)
        if old is not None:
            try:
                self._idx.delete(fid, old)
            except Exception:
                _log.exception("silent exception in update")
                self._stale = True
        box = self._bounds_of(geom)
        if box is not None:
            try:
                self._idx.insert(fid, box)
                self._boxes[fid] = box
            except Exception:
                _log.exception("silent exception in update")
                self._stale = True

    def append(self, fid, geom):
        self.update(fid, geom)

    def mark_dirty(self):
        self._stale = True

    def detach(self):
        try:
            if getattr(self._layer, "_ggs_sidx", None) is self:
                delattr(self._layer, "_ggs_sidx")
        except Exception:
            _log.exception("silent exception in detach")

    def query_array(self, xmin, ymin, xmax, ymax) -> np.ndarray:
        self._ensure()
        if self._idx is None:
            return np.arange(len(self._layer.geoms()), dtype=np.int64)
        try:
            hits = self._idx.intersection((xmin, ymin, xmax, ymax))
            out = (hits.astype(np.int64, copy=False)
                   if isinstance(hits, np.ndarray)
                   else np.fromiter(hits, dtype=np.int64))
        except Exception:
            _log.exception("silent exception in query_array")
            self._stale = True
            self._ensure()
            if self._idx is None:
                return np.arange(len(self._layer.geoms()), dtype=np.int64)
            try:
                hits = self._idx.intersection((xmin, ymin, xmax, ymax))
                out = np.fromiter(hits, dtype=np.int64)
            except Exception:
                _log.exception("silent exception in query_array")
                return np.arange(len(self._layer.geoms()), dtype=np.int64)
        out.sort()
        return out

    def query(self, xmin, ymin, xmax, ymax) -> List[int]:
        return self.query_array(xmin, ymin, xmax, ymax).tolist()


def install_editable_index(layer):
    idx = GgsEditableIndex(layer)
    try:
        layer._ggs_sidx = idx
    except Exception:
        _log.exception("silent exception in install_editable_index")
    idx._ensure()
    return idx


@_guard.off_ui("core.spatial.simplify_coords")
def simplify_coords(coords: Sequence[Tuple[float, float]],
                    tolerance: float) -> List[Tuple[float, float]]:
    n = len(coords)
    if n <= 2 or tolerance <= 0:
        return list(coords)
    coords_arr = np.asarray(coords, dtype=np.float64)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    _dp_recurse(coords_arr, 0, n - 1, tolerance, keep)
    return [tuple(c) for i, c in enumerate(coords_arr) if keep[i]]


def _dp_recurse(arr, lo, hi, tol, keep):
    if hi <= lo + 1:
        return
    a = arr[lo]
    b = arr[hi]
    seg = b - a
    seg_len = float(np.hypot(seg[0], seg[1]))
    if seg_len <= 0:
        d = np.hypot(arr[lo + 1:hi, 0] - a[0], arr[lo + 1:hi, 1] - a[1])
    else:
        cross = np.abs(seg[0] * (arr[lo + 1:hi, 1] - a[1]) -
                       seg[1] * (arr[lo + 1:hi, 0] - a[0]))
        d = cross / seg_len
    if d.size == 0:
        return
    idx_max = int(np.argmax(d))
    if d[idx_max] > tol:
        k = lo + 1 + idx_max
        keep[k] = True
        _dp_recurse(arr, lo, k, tol, keep)
        _dp_recurse(arr, k, hi, tol, keep)


@_guard.off_ui("core.spatial.simplify_geom")
def simplify_geom(geom, tolerance: float):
    if geom is None or getattr(geom, "is_empty", True):
        return geom
    if tolerance <= 0:
        return geom
    try:
        return geom.simplify(tolerance, preserve_topology=False)
    except Exception:
        _log.exception("silent exception in simplify_geom")
        return geom
