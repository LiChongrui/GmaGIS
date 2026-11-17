# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import os
import threading
import time
from collections import OrderedDict

_log = logging.getLogger("gmagis")

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPolygonF, QTransform

from ...core.crs import (convert_bounds, crs_key, crs_transformer,
                         needs_reproject)
from ggis.core.crs.extent import GgsRectangle
from ggis.core.model.layer import subset_generation
from ..native import accel, primitives
from . import paint as P
from . import renderer as R
from ..rasterize import quantize_tolerance
from . import symbol_stack as SS
from .context import GgsRenderContext

__all__ = ["GgsQcPainter", "draw_scene", "backend_enabled", "QC_AVAILABLE",
           "clear_cache", "cache_stats", "prewarm_part_polys", "polys_ready"]

CACHE_MAX = 64
_YIELD_POINTS = 20_000
CLIP_PAD = 8.0
POINT_VECTOR_MAX = 20000
AA_SPLIT_POLYGON = True

_POLY_CACHE_MAX_POINTS = 8_000_000

_POLY_LRU_KEEP = (_POLY_CACHE_MAX_POINTS // 4) * 3

QC_AVAILABLE = bool(primitives.available() and accel.available())


def backend_enabled():
    return True


def clear_cache():
    return _clear_all_caches()


def cache_stats():
    return {"size": len(_CACHE), "hit": _STATS["hit"], "miss": _STATS["miss"],
            "built": _STATS["built"], "paths": _STATS["paths"],
            "verts": _STATS["verts"]}


_CACHE = OrderedDict()
_STATS = {"hit": 0, "miss": 0, "built": 0, "paths": 0, "verts": 0,
          "aa": False, "aa_split": False, "parts": 0, "culled": 0,
          "points_fallback": 0}


def _clear_all_caches():
    _CACHE.clear()
    _STATS.update({"hit": 0, "miss": 0, "built": 0, "paths": 0, "verts": 0,
                   "aa": False, "aa_split": False, "parts": 0, "culled": 0,
                   "points_fallback": 0})
    R.clear_cache()
    SS.clear_tile_cache()


_POLY_LOCK = threading.RLock()
_PREWARM_YIELD_POINTS = 50_000

_POLY_BUILD_YIELD_PARTS = 8

_PREWARM_GIL_MS = 8.0

_UI_BUILD_BUDGET_MS = 11.0

_HIT_COST_MS = 0.0008

_PART_ASSY_COST_MS = 0.0218

_VERTEX_ASSY_COST_MS = 7.0e-5

_PART_RASTER_COST_MS = 0.0559

_VERTEX_RASTER_COST_MS = 7.4e-5

_BUILD_COST_MS = 0.764

_PAINT_BUDGET_MS = 7.0

_PAINT_CHUNK_VERTS = 100000

_BUDGET_CHARGE_BATCH = 64

_DBG = bool(os.environ.get("GGIS_DEBUG_BUDGET"))

_LIST_MIN_VIS_RATIO = 0.4


def _cache_put(flat, pi, poly, n):
    cache = flat.get("_polys")
    if cache is None:
        cache = OrderedDict()
        flat["_polys"] = cache
        flat["_polys_n"] = 0
    if int(n) > _POLY_CACHE_MAX_POINTS:
        return False
    cur = int(flat.get("_polys_n", 0))
    old = cache.get(int(pi))
    if old is not None:
        cur -= int(old[1])
        del cache[int(pi)]
    while cur + int(n) > _POLY_CACHE_MAX_POINTS and cache:
        _k, (_p, _old) = cache.popitem(last=False)
        cur -= int(_old)
    cache[int(pi)] = (poly, int(n))
    flat["_polys_n"] = max(0, cur + int(n))
    return True


def polys_ready(flat):
    try:
        if flat.get("_polys_done"):
            return True
        got = int(flat.get("_polys_n", 0))
        need = int(flat.get("_polys_need", 0)) or len(flat.get("xy", ()))
        return got >= min(_POLY_CACHE_MAX_POINTS, need)
    except Exception:
        exc_note("polys_ready @ ggis/render/cpu/backend.py:314")
        return False


def _split_xy_cached(flat, xy):
    try:
        c = flat.get("_xy_split")
        if c is not None and c[0] is xy:
            return c[1], c[2]
    except Exception:
        exc_note("_split_xy_cached @ ggis/render/cpu/backend.py:333")
        c = None
    xs, ys = accel.split_xy(xy)
    try:
        flat["_xy_split"] = (xy, xs, ys)
    except Exception:
        exc_note("_split_xy_cached @ ggis/render/cpu/backend.py:338")
        pass
    return xs, ys


def _iter_parts(starts, ends):
    for pi in range(len(starts)):
        st, en = int(starts[pi]), int(ends[pi])
        if en - st >= 2:
            yield pi, st, en


def _want_parts(flat):
    try:
        w = flat.get("_polys_want")
        if w is None:
            w = set()
            flat["_polys_want"] = w
        return w
    except Exception:
        exc_note("_want_parts @ ggis/render/cpu/backend.py:366")
        return None


def _note_wanted(flat, pi):
    w = _want_parts(flat)
    if w is not None:
        try:
            w.add(int(pi))
        except Exception:
            exc_note("_note_wanted @ ggis/render/cpu/backend.py:376")
            pass


def wanted_count(flat):
    try:
        return len(flat.get("_polys_want") or ())
    except Exception:
        exc_note("wanted_count @ ggis/render/cpu/backend.py:384")
        return 0


def _budget_cursor(flat):
    try:
        c = flat.get("_polys_cursor")
        if c is None:
            c = 0
            flat["_polys_cursor"] = c
        return int(c)
    except Exception:
        exc_note("_budget_cursor @ ggis/render/cpu/backend.py:412")
        return 0


def _set_budget_cursor(flat, k):
    try:
        flat["_polys_cursor"] = int(k)
    except Exception:
        exc_note("_set_budget_cursor @ ggis/render/cpu/backend.py:420")
        pass


def prewarm_part_polys(flat, should_stop=None, yield_fn=None, viewport=None):
    if not flat:
        return 0
    xy = flat.get("xy")
    starts = flat.get("part_starts")
    ends = flat.get("part_ends")
    if xy is None or not len(starts):
        return 0
    if polys_ready(flat) and not wanted_count(flat):
        return 0
    made = 0
    total = 0
    stopped = False

    want = None
    try:
        want = flat.get("_polys_want")
    except Exception:
        exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:479")
        want = None
    if want:
        mid = 0.0
        for pi in sorted(int(x) for x in list(want)):
            if should_stop is not None and should_stop():
                stopped = True
                break
            if pi < 0 or pi >= len(starts):
                continue
            st, en = int(starts[pi]), int(ends[pi])
            if en - st < 2:
                continue
            if pi in (flat.get("_polys") or {}):
                try:
                    want.discard(pi)
                except Exception:
                    exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:495")
                    pass
                continue
            if total + (en - st) > _POLY_CACHE_MAX_POINTS:
                break
            t0 = time.perf_counter()
            try:
                poly = QPolygonF([QPointF(float(a), float(b))
                                  for a, b in xy[st:en].tolist()])
            except Exception:
                exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:504")
                break
            with _POLY_LOCK:
                _cache_put(flat, pi, poly, en - st)
            try:
                want.discard(pi)
            except Exception:
                exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:510")
                pass
            made += 1
            total += en - st
            mid = (time.perf_counter() - t0) * 1000.0
            if mid >= _PREWARM_GIL_MS:
                mid = 0.0
                if yield_fn is not None:
                    try:
                        yield_fn()
                    except Exception:
                        exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:520")
                        pass

    acc_ms = 0.0
    vp = None
    if viewport is not None:
        try:
            vp = (float(viewport[0]), float(viewport[1]),
                  float(viewport[2]), float(viewport[3]))
        except Exception:
            exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:531")
            vp = None
    ring_bb = None
    if vp is not None:
        try:
            ring_bb = flat.get("_ring_bbox")
            if ring_bb is None or len(ring_bb) != len(starts):
                st_a = np.asarray(starts, dtype=np.int64)
                nz = np.asarray(ends, dtype=np.int64) > st_a
                pts = np.asarray(xy, dtype=np.float64)
                bb = np.zeros((len(st_a), 4), dtype=np.float64)
                if nz.any():
                    x, y = pts[:, 0], pts[:, 1]
                    bb[nz, 0] = np.minimum.reduceat(x, st_a[nz])
                    bb[nz, 1] = np.minimum.reduceat(y, st_a[nz])
                    bb[nz, 2] = np.maximum.reduceat(x, st_a[nz])
                    bb[nz, 3] = np.maximum.reduceat(y, st_a[nz])
                ring_bb = bb
                try:
                    flat["_ring_bbox"] = bb
                except Exception:
                    exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:551")
                    pass
        except Exception:
            exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:553")
            ring_bb = None
    for pi, st, en in _iter_parts(starts, ends):
        if should_stop is not None and should_stop():
            stopped = True
            break
        if ring_bb is not None:
            b = ring_bb[pi]
            if (b[2] < vp[0] or b[0] > vp[2]
                    or b[3] < vp[1] or b[1] > vp[3]):
                continue
        n = en - st
        if total + n > _POLY_CACHE_MAX_POINTS:
            break
        with _POLY_LOCK:
            if int(pi) in (flat.get("_polys") or {}):
                continue
        t0 = time.perf_counter()
        try:
            poly = QPolygonF([QPointF(float(a), float(b))
                              for a, b in xy[st:en].tolist()])
        except Exception:
            exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:574")
            break
        with _POLY_LOCK:
            _cache_put(flat, pi, poly, n)
        made += 1
        total += n
        acc_ms += (time.perf_counter() - t0) * 1000.0
        if acc_ms >= _PREWARM_GIL_MS:
            acc_ms = 0.0
            if yield_fn is not None:
                try:
                    yield_fn()
                except Exception:
                    exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:587")
                    pass
    try:
        with _POLY_LOCK:
            allpts = 0
            for _pi, st, en in _iter_parts(starts, ends):
                allpts += en - st
            flat["_polys_need"] = allpts
            if not stopped:
                flat["_polys_done"] = True
    except Exception:
        exc_note("prewarm_part_polys @ ggis/render/cpu/backend.py:599")
        pass
    return made


def _part_poly(flat, xy, st, en, pi, budget=None):
    if budget is not None and budget.spent():
        _note_wanted(flat, pi)
        return None
    try:
        with _POLY_LOCK:
            cache = flat.get("_polys")
            if cache is not None:
                hit = cache.get(pi)
                if hit is not None:
                    if int(flat.get("_polys_n", 0)) >= _POLY_LRU_KEEP:
                        try:
                            cache.move_to_end(pi)
                        except Exception:
                            exc_note("_part_poly @ ggis/render/cpu/backend.py:639")
                            pass
                    if budget is not None:
                        budget.hits += 1
                        if budget.hits >= _BUDGET_CHARGE_BATCH:
                            budget.charge(hit_ms=budget.hits * _HIT_COST_MS)
                            budget.hits = 0
                    return hit[0]
    except Exception:
        exc_note("_part_poly @ ggis/render/cpu/backend.py:656")
        cache = None
    if budget is not None and budget.spent():
        _note_wanted(flat, pi)
        return None
    try:
        seg = xy[st:en]
        poly = QPolygonF([QPointF(float(a), float(b)) for a, b in seg.tolist()])
    except Exception:
        exc_note("_part_poly @ ggis/render/cpu/backend.py:676")
        return None
    if budget is not None:
        budget.charge()
    try:
        with _POLY_LOCK:
            _cache_put(flat, pi, poly, int(en) - int(st))
    except Exception:
        exc_note("_part_poly @ ggis/render/cpu/backend.py:683")
        pass
    return poly


class _FrameBudget:

    __slots__ = ("limit", "used", "n", "hits", "parts", "paint_start")

    def __init__(self, limit_ms=None):
        self.limit = (float(_UI_BUILD_BUDGET_MS) if limit_ms is None
                      else float(limit_ms))
        self.used = 0.0
        self.n = 0
        self.hits = 0
        self.parts = 0
        self.paint_start = 0.0

    def spent(self):
        if self.limit <= 0.0:
            return True
        eff = self.used + self.hits * _HIT_COST_MS
        return self.n > 0 and eff >= self.limit

    def spent_parts(self):
        return self.used + self.hits * _HIT_COST_MS

    def charge(self, ms=None, hit_ms=None):
        if hit_ms is not None:
            self.used += float(hit_ms)
            self.n += 1
            return
        self.used += (float(_BUILD_COST_MS) if ms is None else float(ms))
        self.n += 1


class GgsQcPainter(object):

    def __init__(self, cache=None):
        self._cache = _CACHE if cache is None else cache
        self.stats = {"built": 0, "hit": 0, "miss": 0, "parts": 0,
                      "culled": 0, "paths": 0, "verts": 0, "aa": False,
                      "aa_split": False, "deferred": 0, "deferred_real": 0}
        self._last_real_deferred = 0
        self._paint_cursor = 0
        self._paint_key = None
        self._frame_budget = None
        self._tile_cache = {}
        self._tile_cache_max = 8192
        self._tile_progress = None

    def begin_frame(self, limit_ms=None):
        self._frame_budget = _FrameBudget(limit_ms)
        self.stats["deferred"] = 0
        self.stats["deferred_real"] = 0
        self._last_real_deferred = 0

    def end_frame(self):
        d = 0
        try:
            d = int(getattr(self, "_last_real_deferred", 0) or 0)
        except Exception:
            exc_note("end_frame @ ggis/render/cpu/backend.py:832")
            d = 0
        self._frame_budget = None
        return d

    def draw(self, painter, layer, settings, symbol=None, antialias=True,
             allow_stale=False, allow_async=True, incremental=False,
             painter_stroke=None, reset_ring=False):
        self._ring_adv = 0
        self._ring_tot = 0
        if not QC_AVAILABLE:
            return 0
        if settings is None or layer is None or not layer.is_valid():
            return 0
        try:
            if not settings.is_ready():
                return 0
        except Exception:
            exc_note("draw @ ggis/render/cpu/backend.py:880")
            return 0
        try:
            kind = layer.base_kind()
        except Exception:
            exc_note("draw @ ggis/render/cpu/backend.py:884")
            return 0
        if kind not in ("line", "polygon", "point"):
            return 0

        try:
            w = float(settings.output_width())
            h = float(settings.output_height())
        except Exception:
            exc_note("draw @ ggis/render/cpu/backend.py:892")
            return 0
        ext = settings.extent()
        if w <= 0 or h <= 0 or ext is None or ext.is_empty():
            return 0

        dst_crs = None
        try:
            dst_crs = settings.destination_crs()
        except Exception:
            exc_note("draw @ ggis/render/cpu/backend.py:902")
            pass
        src_crs = None
        try:
            src_crs = layer.crs()
        except Exception:
            exc_note("draw @ ggis/render/cpu/backend.py:907")
            src_crs = None
        if ext is None or ext.is_empty():
            return 0
        otf = needs_reproject(src_crs, dst_crs) if dst_crs is not None else False
        if otf:
            tf = crs_transformer(dst_crs, src_crs)
            try:
                b = convert_bounds((ext.xmin, ext.ymin,
                                    ext.xmax, ext.ymax), tf)
            except Exception:
                exc_note("draw @ ggis/render/cpu/backend.py:926")
                return 0
            if b is None:
                return 0
            qext = GgsRectangle(b[0], b[1], b[2], b[3])
        else:
            qext = ext
        try:
            if not qext.intersects(layer.extent()):
                return 0
        except Exception:
            exc_note("draw @ ggis/render/cpu/backend.py:936")
            pass

        stacks, classes = R.symbol_stacks(layer, kind, symbol=symbol)
        if not stacks:
            return 0

        ctx = GgsRenderContext.from_map_settings(settings, dpi=_dpi_of(settings))
        if not ctx.is_ready():
            return 0

        if self._tile_lod_on(settings) and kind in ("line", "polygon"):
            r = self._draw_tile_lod(painter, layer, settings, ctx, stacks,
                                    classes, kind, dst_crs, ext, w, h,
                                    antialias, incremental=incremental,
                                    painter_stroke=painter_stroke,
                                    reset_ring=reset_ring)
            if int(r) == -1:
                self._ring_adv = self._ring_tot = -1
            return r

        if kind == "point":
            r = self._draw_points(painter, layer, settings, ctx, stacks,
                                  classes, dst_crs, antialias)
            if int(r) == -1:
                self._ring_adv = self._ring_tot = -1
            return r
        r = self._draw_lines_polys(painter, layer, settings, ctx, stacks,
                                   classes, kind, dst_crs, ext, w, h,
                                   antialias, incremental=incremental,
                                   painter_stroke=painter_stroke,
                                   reset_ring=reset_ring)
        return r

    def _tile_lod_on(self, settings):
        try:
            from ggis.core.app import settings as _S
            return bool(_S.get("vector_tile_lod", False))
        except Exception:
            exc_note("_tile_lod_on @ ggis/render/cpu/backend.py:989")
            return False

    def _draw_tile_lod(self, painter, layer, settings, ctx, stacks, classes,
                       kind, dst_crs, ext, w, h, antialias, incremental,
                       painter_stroke, reset_ring):
        try:
            from ..tile_lod import (visible_tiles, tile_lod_key, lod_level,
                                    tile_origin)
            from ..rasterize import flat_cached, flat_coords
            from ..painter import vector_lod_tol
        except Exception:
            exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1014")
            return 0
        lod_tol = 0.0
        try:
            lod_tol = float(vector_lod_tol(settings, layer.crs(), dst_crs) or 0.0)
        except Exception:
            exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1020")
            lod_tol = 0.0
        flat = flat_cached(layer, lod_tol, kind, dst_crs)
        if flat is None:
            if lod_tol and lod_tol > 0:
                try:
                    flat = flat_coords(layer, lod_tol, kind=kind, dst_crs=dst_crs)
                    if flat is not None:
                        try:
                            prewarm_part_polys(flat)
                        except Exception:
                            exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1030")
                            pass
                except Exception:
                    exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1032")
                    flat = None
            if flat is None:
                flat = flat_cached(layer, 0.0, kind, dst_crs)
        if flat is None:
            self._last_real_deferred = max(
                int(getattr(self, "_last_real_deferred", 0) or 0), 1)
            return -1
        if not flat:
            return 0
        xy = flat.get("xy")
        starts = np.asarray(flat.get("part_starts", []), dtype=np.int64)
        ends = np.asarray(flat.get("part_ends", []), dtype=np.int64)
        if xy is None or len(xy) == 0 or len(starts) == 0:
            return 0

        part_class = _part_class(flat, classes, len(starts))
        try:
            _sub = layer.subset_fids()
            if _sub is not None:
                _pg = np.asarray(flat.get("part_geom", []), dtype=np.int64)
                if _pg.size == len(starts):
                    _allowed = set(int(f) for f in _sub)
                    _keep = (np.isin(_pg, np.asarray(list(_allowed),
                                                    dtype=np.int64))
                             if _allowed
                             else np.zeros(_pg.shape, dtype=bool))
                    if part_class is None:
                        part_class = np.where(_keep, 1, 0).astype(np.int64)
                    else:
                        part_class = np.where(_keep, part_class, 0).astype(np.int64)
        except Exception:
            exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1065")
            pass

        sx = w / ext.width()
        sy = h / ext.height()
        rule = _rule_of(stacks)
        nsym = len(stacks)
        lod_q = lod_level(lod_tol)
        mupp = max((ext.width() / w), (ext.height() / h)) if (w and h) else 1.0
        try:
            origin = (tile_origin(layer.extent())
                      if hasattr(layer, "extent") else None)
        except Exception:
            exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1077")
            origin = None
        if origin is None:
            try:
                origin = (float(ext.xMinimum()), float(ext.yMaximum()))
            except Exception:
                exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1082")
                origin = (0.0, 0.0)
        try:
            tiles = visible_tiles(ext, w, h, mupp, lod_q, origin)
        except Exception:
            exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1086")
            return 0
        if not tiles:
            return 0

        if reset_ring:
            self._tile_progress = None
        tseq = list(tiles)
        start_idx = 0
        if self._tile_progress is not None:
            _pid = self._tile_progress
            _found = False
            for i, t in enumerate(tseq):
                if t[0] == _pid:
                    start_idx = i + 1
                    _found = True
                    break
            if not _found:
                start_idx = 0
                self._tile_progress = None

        deadline = self._paint_deadline()
        drawn_total = 0
        last_tid = None
        truncated = False
        for i in range(start_idx, len(tseq)):
            tid, trect, ox_px, oy_px, tw, th = tseq[i]
            last_tid = tid
            key = tile_lod_key(
                id(layer), _render_version(layer), tid,
                (None if classes is None else id(classes)),
                rule, nsym, int(subset_generation(layer)),
                crs_key(dst_crs) or "", int(len(starts)))
            paths = self._tile_cache.get(key)
            if paths is None:
                paths = self._build_tile_paths(
                    flat, xy, starts, ends, part_class, nsym,
                    sx, sy, trect, tw, th, rule)
                if paths is None:
                    continue
                self._tile_cache[key] = paths
                if len(self._tile_cache) > self._tile_cache_max:
                    try:
                        self._tile_cache.popitem(last=False)
                    except Exception:
                        exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1134")
                        pass
            painter.save()
            painter.translate(float(ox_px), float(oy_px))
            pst = painter_stroke
            pst_restore = False
            if pst is not None and pst is not painter:
                pst.save()
                pst.translate(float(ox_px), float(oy_px))
                pst_restore = True
            try:
                n_v = 0
                for _chunks in paths.values():
                    for _p in _chunks:
                        n_v += int(_p.elementCount())
            except Exception:
                exc_note("_draw_tile_lod @ ggis/render/cpu/backend.py:1150")
                n_v = 0
            aa_ok = bool(antialias)
            split = bool(kind == "polygon" and AA_SPLIT_POLYGON)
            aa_edges = aa_ok if split else (aa_ok and n_v <= 1_000_000)
            _d, _, _ = GgsQcPainter._paint_paths(
                painter, paths, stacks, kind, ctx, aa_edges, split,
                deadline=None, cursor=0, painter_stroke=pst)
            painter.restore()
            if pst_restore:
                pst.restore()
            drawn_total += int(_d)
            if deadline is not None and time.perf_counter() >= deadline:
                truncated = True
                break

        if truncated:
            self._tile_progress = last_tid
            self._ring_adv = self._ring_tot = -1
            self._last_real_deferred = max(
                int(getattr(self, "_last_real_deferred", 0) or 0), 1)
            return -1
        self._tile_progress = None
        self._last_real_deferred = 0
        self._ring_adv = 0
        self._ring_tot = 0
        return drawn_total

    def _build_tile_paths(self, flat, xy, starts, ends, part_class, nsym,
                         sx, sy, trect, tw, th, rule):
        try:
            tx0, ty0, tx1, ty1 = trect
            tf = QTransform(float(sx), 0.0, 0.0, -float(sy),
                            -float(tx0) * float(sx), float(ty1) * float(sy))
            xs, ys = _split_xy_cached(flat, xy)
        except Exception:
            exc_note("_build_tile_paths @ ggis/render/cpu/backend.py:1194")
            return None
        pc = (part_class if part_class is not None
              else np.ones(len(starts), dtype=np.int64))
        try:
            _out_xy, part, cls, order, indptr = primitives.build_prims(
                xs, ys, starts, ends, pc, float(sx), float(sy),
                float(tx0), float(ty1),
                (0.0, 0.0, float(tw), float(th)),
                pad=CLIP_PAD, nclass=max(2, nsym + 1))
        except Exception:
            exc_note("_build_tile_paths @ ggis/render/cpu/backend.py:1204")
            return None
        if order is None or indptr is None:
            return None
        paths = {}
        for cid in range(1, min(len(indptr) - 1, nsym + 1)):
            lo, hi = int(indptr[cid]), int(indptr[cid + 1])
            if hi <= lo:
                continue
            path = QPainterPath()
            path.setFillRule(P.fill_rule(rule))
            for _k in range(lo, hi):
                try:
                    pi = int(part[int(order[_k])])
                    st = int(starts[pi])
                    en = int(ends[pi])
                except Exception:
                    exc_note("_build_tile_paths @ ggis/render/cpu/backend.py:1220")
                    continue
                if en - st < 2:
                    continue
                poly = _part_poly(flat, xy, st, en, pi)
                if poly is None:
                    continue
                path.addPolygon(tf.map(poly))
            if path.elementCount() > 0:
                paths[cid] = [path]
        return paths

    _VEC_STATE_LOG = {}

    @staticmethod
    def _vec_state_log(layer, state, detail):
        try:
            key = id(layer)
            now = __import__("time").monotonic()
            prev_ts = GgsQcPainter._VEC_STATE_LOG.get(key)
            if prev_ts is not None:
                prev_state, ts = prev_ts
                if prev_state == state and (now - ts) < 5.0:
                    return
            GgsQcPainter._VEC_STATE_LOG[key] = (state, now)
            if len(GgsQcPainter._VEC_STATE_LOG) > 64:
                GgsQcPainter._VEC_STATE_LOG.clear()
                GgsQcPainter._VEC_STATE_LOG[key] = (state, now)
            _log.info("[矢量·%s] %s ｜ %s", state,
                      getattr(layer, "name", lambda: "?")(), detail)
        except Exception:
            exc_note("_vec_state_log @ ggis/render/cpu/backend.py:1278")
            pass

    def _draw_lines_polys(self, painter, layer, settings, ctx, stacks,
                          classes, kind, dst_crs, ext, w, h, antialias,
                          incremental=False, painter_stroke=None,
                          reset_ring=False):
        self._ring_flat_id = None
        if self._frame_budget is not None:
            try:
                from ..rasterize import flat_cached, flat_coords
                from ..rasterize import nearest_flat_cached
                from ..rasterize import _lod_is_fine
                lod_tol = 0.0
                try:
                    from ..painter import vector_lod_tol
                    lod_tol = float(vector_lod_tol(settings, layer.crs(),
                                                  dst_crs) or 0.0)
                except Exception:
                    exc_note("_draw_lines_polys @ ggis/render/cpu/backend.py:1265")
                    lod_tol = 0.0
                _built_new = False
                flat = flat_cached(layer, lod_tol, kind, dst_crs)
                if flat is None:
                    _built_new = True
                    _fine = _lod_is_fine(layer, lod_tol, kind, dst_crs)
                    if (not _fine) and lod_tol and lod_tol > 0 \
                            and not getattr(layer, "_viewport_cull", False):
                        try:
                            _band = quantize_tolerance(lod_tol)
                            if getattr(self, "_lod_pre_band", None) != _band:
                                self._lod_pre_band = _band
                                spec_prewarm_buckets(layer, [lod_tol],
                                                     kind, dst_crs)
                        except Exception:
                            exc_note("_draw_lines_polys @ ggis/render/cpu/backend.py:1297")
                            pass
                    if _fine:
                        flat = flat_cached(layer, 0.0, kind, dst_crs)
                        if flat is None:
                            flat = nearest_flat_cached(layer, lod_tol,
                                                      kind, dst_crs)
                    else:
                        flat = nearest_flat_cached(layer, lod_tol, kind, dst_crs)
                        if flat is None:
                            flat = flat_cached(layer, 0.0, kind, dst_crs)
            except Exception:
                exc_note("_draw_lines_polys @ ggis/render/cpu/backend.py:1317")
                flat = None
            if flat is None:
                self.stats["deferred"] = int(self.stats.get("deferred", 0)) + 1
                self._vec_state_log(layer, "defer",
                                    "tol=%r kind=%s dst=%s flat/近档全 miss"
                                    "（本帧不画，等后台建档）"
                                    % (lod_tol, kind, dst_crs))
                self._ring_adv = self._ring_tot = -1
                self._last_real_deferred = max(
                    int(getattr(self, "_last_real_deferred", 0) or 0), 1)
                return -1
        else:
            try:
                flat = _flat_of(layer, kind, dst_crs)
            except Exception:
                exc_note("_draw_lines_polys @ ggis/render/cpu/backend.py:1341")
                return 0
        if not flat:
            return 0
        _ps = flat.get("part_starts") if isinstance(flat, dict) else None
        try:
            _n = len(_ps) if _ps is not None else 0
        except Exception:
            _n = -1
        self._vec_state_log(layer, "画",
                            "kind=%s dst=%s 部件数=%s（flat 就位，进入绘制）"
                            % (kind, dst_crs, _n))
        self._ring_flat_id = id(flat)
        if reset_ring:
            flat["_polys_cursor"] = 0
            flat["_ring_start"] = None
        xy = flat.get("xy")
        starts = np.asarray(flat.get("part_starts", []), dtype=np.int64)
        ends = np.asarray(flat.get("part_ends", []), dtype=np.int64)
        if xy is None or len(xy) == 0 or len(starts) == 0:
            self._vec_state_log(layer, "空档",
                                "缓存档无几何 → 0 部件 ｜ flat 键=%s ｜ "
                                "xy=%s(%r) part_starts=%s"
                                % (sorted(flat.keys())
                                   if isinstance(flat, dict) else "?",
                                   type(xy).__name__,
                                   0 if xy is None else len(xy),
                                   type(flat.get("part_starts")).__name__))
            return 0

        part_class = _part_class(flat, classes, len(starts))

        try:
            _sub = layer.subset_fids()
            if _sub is not None:
                _pg = np.asarray(flat.get("part_geom", []), dtype=np.int64)
                if _pg.size == len(starts):
                    _allowed = set(int(f) for f in _sub)
                    _keep = (np.isin(_pg, np.asarray(list(_allowed),
                                                    dtype=np.int64))
                             if _allowed
                             else np.zeros(_pg.shape, dtype=bool))
                    if part_class is None:
                        part_class = np.where(_keep, 1, 0).astype(np.int64)
                    else:
                        part_class = np.where(_keep, part_class, 0).astype(np.int64)
        except Exception:
            exc_note("_draw_lines_polys @ ggis/render/cpu/backend.py:1390")
            pass

        sx = w / ext.width()
        sy = h / ext.height()
        rule = _rule_of(stacks)
        nsym = len(stacks)
        ckey = (id(layer), _render_version(layer), crs_key(dst_crs) or "",
                len(starts), round(sx, 9), round(sy, 9),
                round(ext.xmin, 9), round(ext.ymax, 9), int(w), int(h),
                rule, nsym,
                round(float(flat.get("tol", 0.0)), 6),
                int(subset_generation(layer)),
                None if part_class is None else id(classes))
        hit = None if incremental else self._cache.get(ckey)
        if hit is not None:
            self._cache.move_to_end(ckey)
            self.stats["hit"] += 1
            paths = hit
            self._last_real_deferred = 0
        else:
            if incremental and len(starts) and flat.get("_ring_start") is None:
                flat["_ring_start"] = (int(flat.get("_polys_cursor", 0) or 0)
                                       % len(starts))
            paths = self._build_paths(
                flat, xy, starts, ends, part_class,
                nsym, sx, sy, ext, w, h, rule,
                incremental=incremental,
                cls_sig=((None if classes is None else id(classes)),
                         int(subset_generation(layer))))
            if paths is None:
                return 0
            if (not incremental
                    and not int(getattr(self, "_last_real_deferred", 0) or 0)):
                self._cache[ckey] = paths
                while len(self._cache) > CACHE_MAX:
                    self._cache.popitem(last=False)
            self.stats["built"] += 1
        if not paths:
            if (self._frame_budget is not None
                    and int(getattr(self, "_last_real_deferred", 0) or 0)):
                self._ring_adv = self._ring_tot = -1
                return -1
            return 0

        try:
            n_v = sum(p.elementCount() for chunks in paths.values()
                      for p in chunks)
        except Exception:
            exc_note("_draw_lines_polys @ ggis/render/cpu/backend.py:1483")
            n_v = 0
        aa_ok = bool(antialias)
        split = bool(kind == "polygon" and AA_SPLIT_POLYGON)
        aa_edges = aa_ok if split else (aa_ok and n_v <= 1_000_000)
        self.stats["verts"] = int(n_v)
        self.stats["aa"] = bool(aa_edges)
        self.stats["aa_split"] = bool(split and aa_edges)

        painter.save()
        try:
            if incremental:
                drawn, truncated, _nxt = self._paint_paths(
                    painter, paths, stacks, kind, ctx, aa_edges, split,
                    deadline=None, cursor=0, painter_stroke=painter_stroke)
            else:
                pkey = id(paths)
                if getattr(self, "_paint_key", None) != pkey:
                    self._paint_cursor = 0
                    self._paint_key = pkey
                drawn, truncated, nxt = self._paint_paths(
                    painter, paths, stacks, kind, ctx, aa_edges, split,
                    deadline=self._paint_deadline(), cursor=self._paint_cursor,
                    painter_stroke=painter_stroke)
                self._paint_cursor = nxt
        finally:
            painter.restore()
        if truncated and self._frame_budget is not None:
            self._last_real_deferred = max(
                int(getattr(self, "_last_real_deferred", 0) or 0), 1)
        self.stats["paths"] += drawn
        return drawn

    def _paint_deadline(self):
        b = self._frame_budget
        if b is None:
            return None
        try:
            if not b.paint_start:
                b.paint_start = time.perf_counter()
            return b.paint_start + _PAINT_BUDGET_MS / 1000.0
        except Exception:
            exc_note("_paint_deadline @ ggis/render/cpu/backend.py:1550")
            return None

    def _build_paths(self, flat, xy, starts, ends, part_class, nsym, sx, sy,
                     ext, w, h, rule, incremental=False, cls_sig=None):
        tf = QTransform(float(sx), 0.0, 0.0, -float(sy),
                        -float(ext.xmin) * float(sx), float(ext.ymax) * float(sy))
        try:
            xs, ys = _split_xy_cached(flat, xy)
            bkey = (id(xy), float(sx), float(sy), float(ext.xmin),
                    float(ext.ymax), int(w), int(h), int(nsym), cls_sig)
            bc = flat.get("_prims_cache")
            if bc is not None and bc[0] == bkey:
                v = bc[1]
                _out_xy, part, cls, order, indptr = v[:5]
                order_l = v[5] if len(v) > 5 else None
                part_l = v[6] if len(v) > 6 else None
            else:
                pc = (part_class if part_class is not None
                      else np.ones(len(starts), dtype=np.int64))
                _out_xy, part, cls, order, indptr = primitives.build_prims(
                    xs, ys, starts, ends, pc, sx, sy,
                    ext.xmin, ext.ymax, (0.0, 0.0, w, h),
                    pad=CLIP_PAD, nclass=max(2, nsym + 1))
                try:
                    _n_all = len(starts)
                    _n_vis = 0 if order is None else len(order)
                    _want_lists = bool(_n_all > 0 and _n_vis >= _n_all * _LIST_MIN_VIS_RATIO)
                except Exception:
                    exc_note("_build_paths @ ggis/render/cpu/backend.py:1634")
                    _want_lists = True
                try:
                    if _want_lists:
                        order_l = None if order is None else order.tolist()
                        part_l = None if part is None else part.tolist()
                    else:
                        order_l = part_l = None
                except Exception:
                    exc_note("_build_paths @ ggis/render/cpu/backend.py:1642")
                    order_l = part_l = None
                try:
                    flat["_prims_cache"] = (
                        bkey, (_out_xy, part, cls, order, indptr,
                               order_l, part_l))
                except Exception:
                    exc_note("_build_paths @ ggis/render/cpu/backend.py:1648")
                    pass
            starts_l = ends_l = None
            try:
                _se = flat.get("_se_l")
                if _se is not None and _se[0] == id(xy):
                    starts_l, ends_l = _se[1], _se[2]
            except Exception:
                exc_note("_build_paths @ ggis/render/cpu/backend.py:1662")
                starts_l = ends_l = None
            if starts_l is None and order_l is not None and part_l is not None:
                try:
                    starts_l, ends_l = starts.tolist(), ends.tolist()
                except Exception:
                    exc_note("_build_paths @ ggis/render/cpu/backend.py:1667")
                    starts_l = ends_l = None
                try:
                    flat["_se_l"] = (id(xy), starts_l, ends_l)
                except Exception:
                    exc_note("_build_paths @ ggis/render/cpu/backend.py:1671")
                    pass
            fast = (starts_l is not None and ends_l is not None
                    and order_l is not None and part_l is not None)
        except Exception:
            exc_note("_build_paths @ ggis/render/cpu/backend.py:1678")
            return None
        self.stats["parts"] = int(len(part))
        try:
            self.stats["culled"] = int(len(starts) - len(part))
        except Exception:
            exc_note("_build_paths @ ggis/render/cpu/backend.py:1683")
            pass

        paths = {}
        acc = 0
        built = 0
        budget = self._frame_budget
        deferred = 0
        cursor = _budget_cursor(flat) if budget is not None else 0
        n_order = int(len(order)) if order is not None else 0
        stop_at = None
        real_deferred = 0
        rstart = (flat.get("_ring_start") if incremental else None)
        hit_ring = None
        for cid in range(1, min(len(indptr) - 1, nsym + 1)):
            lo, hi = int(indptr[cid]), int(indptr[cid + 1])
            if hi <= lo:
                continue
            if budget is not None and budget.spent():
                deferred += (hi - lo)
                real_deferred += (hi - lo)
                if stop_at is None:
                    stop_at = lo
                if budget is not None:
                    try:
                        w = _want_parts(flat)
                        if w is not None:
                            if fast:
                                for _k in range(lo, hi):
                                    try:
                                        w.add(part_l[order_l[_k]])
                                    except Exception:
                                        exc_note("_build_paths @ ggis/render/cpu/backend.py:1753")
                                        pass
                            else:
                                part_arr = part
                                for _k in range(lo, hi):
                                    try:
                                        w.add(int(part_arr[int(order[_k])]))
                                    except Exception:
                                        exc_note("_build_paths @ ggis/render/cpu/backend.py:1760")
                                        pass
                    except Exception:
                        exc_note("_build_paths @ ggis/render/cpu/backend.py:1762")
                        pass
                continue
            k_start = cursor if lo <= cursor < hi else lo
            span = hi - lo
            path = QPainterPath()
            path.setFillRule(P.fill_rule(rule))
            chunk_list = []
            chunks_here = 0
            chunk_verts = 0
            n_parts = 0
            n_miss = 0
            for j in range(span):
                k = lo + (k_start - lo + j) % span
                if (hit_ring is None and rstart is not None
                        and int(k) == int(rstart) and int(k) != int(cursor)):
                    stop_at = (int(k) - 1) % n_order
                    hit_ring = k
                    break
                if budget is not None and budget.spent():
                    if stop_at is None:
                        stop_at = k
                    n_miss = span - j
                    break
                if fast:
                    pi = part_l[order_l[k]]
                    st = starts_l[pi]
                    en = ends_l[pi]
                else:
                    pi = int(part[int(order[k])])
                    st = int(starts[pi])
                    en = int(ends[pi])
                if en - st < 2:
                    continue
                poly = _part_poly(flat, xy, st, en, pi, budget=budget)
                if poly is None:
                    if budget is not None and budget.spent():
                        if stop_at is None:
                            stop_at = k
                        n_miss = span - j
                        break
                    return None
                path.addPolygon(tf.map(poly))
                n_parts += 1
                chunks_here += 1
                chunk_verts += int(en) - int(st)
                if budget is not None:
                    budget.parts += 1
                    budget.charge(ms=(en - st) * _VERTEX_ASSY_COST_MS)
                acc += (en - st)
                built += 1
                if budget is not None:
                    stop_at = k
                if chunks_here and chunk_verts >= _PAINT_CHUNK_VERTS:
                    if not path.isEmpty():
                        chunk_list.append(path)
                    path = QPainterPath()
                    path.setFillRule(P.fill_rule(rule))
                    chunks_here = 0
                    chunk_verts = 0
                if built >= _POLY_BUILD_YIELD_PARTS:
                    built = 0
                    acc = 0
                    time.sleep(0)
                elif acc >= _YIELD_POINTS:
                    acc = 0
                    time.sleep(0)
            deferred += n_miss
            real_deferred += n_miss
            if not path.isEmpty():
                chunk_list.append(path)
            if n_parts and chunk_list:
                paths[int(cid)] = chunk_list
            elif not n_miss and hit_ring is None:
                deferred += max(0, hi - lo)
                if budget is not None and hi > lo:
                    stop_at = hi - 1 if stop_at is None else max(stop_at, hi - 1)
            if hit_ring is not None:
                break
        if budget is not None and n_order:
            k_next = ((stop_at + 1) % n_order) if stop_at is not None else cursor
            _set_budget_cursor(flat, k_next)
            self._ring_tot = int(n_order)
            self._ring_adv = int((k_next - cursor) % n_order)
            rstart = flat.get("_ring_start")
            if incremental and rstart is not None:
                steps = (k_next - cursor) % n_order
                off = (int(rstart) - cursor) % n_order
                if 0 < off <= steps:
                    self._ring_adv = int(n_order)
                    self._ring_tot = int(n_order)
                    flat["_ring_start"] = None
            if budget is None or not budget.spent():
                _set_budget_cursor(flat, 0)
                self._ring_adv = int(n_order)
                flat["_ring_start"] = None
        self.stats["deferred"] = int(deferred)
        self.stats["deferred_real"] = int(real_deferred)
        budget_open = not (budget is not None and budget.spent())
        self._last_real_deferred = 0 if budget_open else 1
        if _DBG:
            try:
                print("[_build_paths] parts=%d built=%d path_hit=%d used=%.2f "
                      "n=%d budget.limit=%.2f budget.parts=%d eff=%.2f "
                      "spent=%s deferred=%d real=%d n_order=%d stop_at=%s"
                      % (len(part), built, self.stats.get("hit", 0),
                         (budget.used if budget else -1),
                         (budget.n if budget else -1),
                         (budget.limit if budget else -1),
                         (budget.parts if budget else -1),
                         (budget.spent_parts() if budget else -1),
                         (budget.spent() if budget else None),
                         deferred, real_deferred, n_order, stop_at),
                      flush=True)
            except Exception:
                exc_note("_build_paths @ ggis/render/cpu/backend.py:1956")
                pass
        return paths

    @staticmethod
    def _paint_paths(painter, paths, stacks, kind, ctx, aa_edges, split,
                     deadline=None, cursor=0, painter_stroke=None):
        items = []
        for cid in sorted(paths):
            for chunk in paths[cid]:
                items.append((cid, chunk))
        n = len(items)
        if n == 0:
            return 0, False, 0
        start = int(cursor) % n
        brush_cache = {}

        def _stack_of(cid):
            got = brush_cache.get(cid)
            if got is not None:
                return got
            stack = stacks[cid - 1] if 0 <= cid - 1 < len(stacks) else None
            out = []
            if stack is not None:
                op = stack.opacity()
                for lyr in stack.layers():
                    if getattr(lyr, "kind", "") != "fill":
                        continue
                    br = P.fill_brush(lyr, ctx, op)
                    if br.style() == Qt.BrushStyle.NoBrush:
                        continue
                    out.append((br, P.fill_pen(lyr, ctx, op)))
            got = (stack, out)
            brush_cache[cid] = got
            return got

        drawn = 0
        seq = [items[(start + i) % n] for i in range(n)]
        painted = []

        pst = painter_stroke if painter_stroke is not None else painter

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setPen(Qt.PenStyle.NoPen)
        for cid, chunk in seq:
            stack, fs = _stack_of(cid)
            if stack is None:
                continue
            if fs:
                for br, _pn in fs:
                    painter.setBrush(br)
                    painter.drawPath(chunk)
                painted.append((cid, chunk, stack, fs))
                drawn += 1

        pst.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pst.setBrush(Qt.BrushStyle.NoBrush)
        for cid, chunk, stack, fs in painted:
            for _br, pn in fs:
                pst.setPen(pn)
                pst.drawPath(chunk)

        for cid, chunk in seq:
            stack, fs = _stack_of(cid)
            if stack is None or fs:
                continue
            pst.setRenderHint(QPainter.RenderHint.Antialiasing,
                              bool(aa_edges))
            stack.render(pst,
                         "fill" if kind == "polygon" else "line",
                         ctx, path=chunk)
            drawn += 1
        return drawn, False, 0


    def _draw_points(self, painter, layer, settings, ctx, stacks, classes,
                     dst_crs, antialias):
        try:
            from ..painter import _xy_cache
            xy, _off, rows, _counts = _xy_cache(layer, dst_crs)
        except Exception:
            exc_note("_draw_points @ ggis/render/cpu/backend.py:2097")
            return 0
        if xy is None or len(xy) == 0 or len(rows) == 0:
            return 0
        ext = settings.extent()
        w = float(settings.output_width())
        h = float(settings.output_height())
        sx = w / ext.width()
        sy = h / ext.height()
        px = (xy[rows, 0] - ext.xmin) * sx
        py = (ext.ymax - xy[rows, 1]) * sy
        pad = CLIP_PAD
        vis = ((px >= -pad) & (px <= w + pad)
               & (py >= -pad) & (py <= h + pad))
        n_vis = int(np.count_nonzero(vis))
        if n_vis == 0:
            return 0
        if n_vis > POINT_VECTOR_MAX:
            self.stats["points_fallback"] = n_vis
            return 0

        nfeat = len(rows)
        if classes is not None and len(classes) == nfeat:
            cls_all = np.asarray(classes, dtype=np.int64)
        else:
            cls_all = np.ones(nfeat, dtype=np.int64)

        try:
            _sub = layer.subset_fids()
            if _sub is not None:
                _allowed = set(int(f) for f in _sub)
                _sub_mask = (np.isin(np.asarray(rows, dtype=np.int64),
                                     np.asarray(list(_allowed), dtype=np.int64))
                             if _allowed
                             else np.zeros(len(rows), dtype=bool))
                cls_all = np.where(_sub_mask, cls_all, 0).astype(np.int64)
        except Exception:
            exc_note("_draw_points @ ggis/render/cpu/backend.py:2142")
            pass

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing,
                                  bool(antialias))
            drawn = 0
            for cid in range(1, len(stacks) + 1):
                sel = np.nonzero(vis & (cls_all == cid))[0]
                if len(sel) == 0:
                    continue
                pts = [(float(px[i]), float(py[i])) for i in sel]
                if stacks[cid - 1].render(painter, "marker", ctx, points=pts):
                    drawn += 1
        finally:
            painter.restore()
        return drawn


_PAINTER = GgsQcPainter()


def draw_scene(painter, pairs, settings, antialias=True):
    n = 0
    for layer, _kind in list(pairs or []):
        try:
            if _PAINTER.draw(painter, layer, settings, antialias=antialias):
                n += 1
        except Exception as exc:
            _log.warning("图层绘制失败（已跳过，其余层继续）：%s", exc)
            continue
    return n


def _dpi_of(settings):
    try:
        return float(settings.dpi())
    except Exception:
        exc_note("_dpi_of @ ggis/render/cpu/backend.py:2193")
        return 96.0


def _render_version(layer):
    try:
        from ..renderers import render_version
        return int(render_version(layer))
    except Exception:
        exc_note("_render_version @ ggis/render/cpu/backend.py:2201")
        return 0


def _flat_of(layer, kind, dst_crs):
    from ..rasterize import flat_coords
    return flat_coords(layer, 0.0, kind, dst_crs)


def _part_class(flat, classes, n_parts):
    if classes is None:
        return None
    try:
        ca = np.asarray(classes)
        pg = np.asarray(flat.get("part_geom", []), dtype=np.int64)
        if ca.size and pg.size == n_parts:
            pg = np.clip(pg, 0, ca.size - 1)
            return ca[pg].astype(np.int64)
    except Exception:
        exc_note("_part_class @ ggis/render/cpu/backend.py:2220")
        pass
    return None


def _rule_of(stacks):
    try:
        for st in stacks:
            for lyr in st.layers():
                r = getattr(lyr, "fill_rule", None)
                if r:
                    return r
    except Exception:
        exc_note("_rule_of @ ggis/render/cpu/backend.py:2233")
        pass
    return P.WINDING




def _spec_yields():
    import time as _time
    return lambda: _time.sleep(0)


_LOD_CTRL_BUF = None
_LOD_BUILD_SEQ = 0


def set_lod_ctrl_buf(buf):
    global _LOD_CTRL_BUF
    _LOD_CTRL_BUF = buf


def _bump_lod_build_seq():
    global _LOD_BUILD_SEQ, _LOD_CTRL_BUF
    _LOD_BUILD_SEQ += 1
    if _LOD_CTRL_BUF is not None:
        try:
            import struct as _st
            _st.pack_into("q", _LOD_CTRL_BUF, 32, int(_LOD_BUILD_SEQ))
        except Exception:
            exc_note("_bump_lod_build_seq @ ggis/render/cpu/backend.py:2279")
            pass


_SPEC_LOCK = threading.Lock()
_SPEC_QUEUE = []
_SPEC_WAKE = threading.Event()
_SPEC_THREAD = None


def _spec_worker():
    from ggis.render.rasterize import flat_cached, flat_coords
    while True:
        with _SPEC_LOCK:
            job = _SPEC_QUEUE.pop(0) if _SPEC_QUEUE else None
        if job is None:
            _SPEC_WAKE.wait(0.5)
            _SPEC_WAKE.clear()
            continue
        layer, tol, kind, dst_crs = job
        try:
            if flat_cached(layer, tol, kind, dst_crs) is None:
                _y = _spec_yields()
                f = flat_coords(layer, tol, kind=kind, dst_crs=dst_crs,
                                best_effort=True, yield_fn=_y)
                if f is not None:
                    try:
                        prewarm_part_polys(f, yield_fn=_y)
                    except Exception:
                        exc_note("_spec_worker @ ggis/render/cpu/backend.py:2318")
                        pass
                    _bump_lod_build_seq()
        except Exception:
            exc_note("_spec_worker @ ggis/render/cpu/backend.py:2322")
            pass


def _spec_kick():
    global _SPEC_THREAD
    t = _SPEC_THREAD
    if t is None or not t.is_alive():
        t = threading.Thread(target=_spec_worker, daemon=True,
                             name="ggis-lod-builder")
        _SPEC_THREAD = t
        t.start()
    else:
        _SPEC_WAKE.set()


def _spec_enqueue_key(layer, tol, kind, dst_crs):
    from ggis.core.crs import crs_key as _ck
    return (id(layer), round(float(tol), 9), kind, _ck(dst_crs) or "")


def spec_prewarm_buckets(layer, tols, kind, dst_crs):
    global _SPEC_QUEUE
    kicked = False
    for t in tols:
        try:
            t = float(t)
        except Exception:
            exc_note("spec_prewarm_buckets @ ggis/render/cpu/backend.py:2365")
            continue
        if not (t > 0.0):
            continue
        key = _spec_enqueue_key(layer, t, kind, dst_crs)
        with _SPEC_LOCK:
            if any(_spec_enqueue_key(l, tt, kk, dd) == key
                   for (l, tt, kk, dd) in _SPEC_QUEUE):
                continue
            _SPEC_QUEUE.append((layer, t, kind, dst_crs))
        kicked = True
    if kicked:
        _spec_kick()
