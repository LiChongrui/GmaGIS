# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math


_TILE_PX = 256.0
_MUPP_K_MIN, _MUPP_K_MAX = -12, 12


def _rect(e):
    try:
        return (float(e.xmin), float(e.ymin), float(e.xmax), float(e.ymax))
    except AttributeError:
        exc_note("_rect @ ggis/render/tile_lod.py:39")
        x0, y0, x1, y1 = e
        return float(x0), float(y0), float(x1), float(y1)


def _snap_mupp(mupp):
    if mupp is None or mupp <= 0:
        return 1.0
    k = round(math.log2(float(mupp)))
    k = max(_MUPP_K_MIN, min(_MUPP_K_MAX, k))
    return 2.0 ** k


def tile_size(mupp):
    return _TILE_PX * _snap_mupp(mupp)


def lod_level(tol):
    from .rasterize import quantize_tolerance
    return quantize_tolerance(float(tol or 0.0))


def tile_origin(layer_extent):
    x0, _y0, _x1, y1 = _rect(layer_extent)
    return (x0, y1)


def visible_tiles(ext, w, h, mupp, level, origin):
    x0, y0, x1, y1 = _rect(ext)
    ew = (x1 - x0) or 1.0
    eh = (y1 - y0) or 1.0
    sx = float(w) / ew
    sy = float(h) / eh
    T = tile_size(mupp)
    ox, oy = origin
    c0 = int(math.floor((x0 - ox) / T))
    c1 = int(math.floor((x1 - ox) / T))
    r0 = int(math.floor((oy - y1) / T))
    r1 = int(math.floor((oy - y0) / T))
    out = []
    for col in range(c0, c1 + 1):
        tx0 = ox + col * T
        tx1 = ox + (col + 1) * T
        for row in range(r0, r1 + 1):
            ty1t = oy - row * T
            ty0t = oy - (row + 1) * T
            ox_px = (tx0 - x0) * sx
            oy_px = (y1 - ty1t) * sy
            tw = (tx1 - tx0) * sx
            th = (ty1t - ty0t) * sy
            out.append(((level, col, row),
                        (tx0, ty0t, tx1, ty1t),
                        ox_px, oy_px, tw, th))
    return out


def tile_lod_key(layer_id, rv, tid, cls_id, rule, nsym, subset_gen, crs,
                 n_parts):
    return (layer_id, rv, tid, cls_id, rule, nsym, subset_gen, crs, n_parts)
