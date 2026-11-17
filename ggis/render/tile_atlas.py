# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

TILE_PX = 256
ATLAS_GAP = 1
ATLAS_MAX_SIDE = 4096
MAX_TILES_PER_VIEW = 2048
MAX_TILES_PER_ATLAS = 32

_LEVEL_MIN, _LEVEL_MAX = -24, 24


def level_of(mupp):
    try:
        m = float(mupp)
    except (TypeError, ValueError):
        exc_note("level_of @ ggis/render/tile_atlas.py:57")
        return 0
    if not (m > 0.0) or not math.isfinite(m):
        return 0
    return max(_LEVEL_MIN, min(_LEVEL_MAX, int(round(math.log2(m)))))


def tile_span(level):
    return float(TILE_PX) * (2.0 ** int(level))


def _rect(e):
    try:
        return (float(e.xmin), float(e.ymin), float(e.xmax), float(e.ymax))
    except AttributeError:
        exc_note("_rect @ ggis/render/tile_atlas.py:72")
        x0, y0, x1, y1 = e
        return float(x0), float(y0), float(x1), float(y1)


def tile_origin(scene_extent):
    x0, _y0, _x1, y1 = _rect(scene_extent)
    return (x0, y1)


def visible_tiles(ext, w, h, mupp, level, origin):
    x0, y0, x1, y1 = _rect(ext)
    ew = (x1 - x0) or 1.0
    eh = (y1 - y0) or 1.0
    sx_ppu = float(w) / ew
    sy_ppu = float(h) / eh
    T = tile_span(level)
    ox, oy = origin
    c0 = int(math.floor((x0 - ox) / T))
    c1 = int(math.floor((x1 - ox) / T))
    r0 = int(math.floor((oy - y1) / T))
    r1 = int(math.floor((oy - y0) / T))
    if (c1 - c0 + 1) * (r1 - r0 + 1) > MAX_TILES_PER_VIEW:
        return []
    out = []
    for col in range(c0, c1 + 1):
        tx0 = ox + col * T
        tx1 = tx0 + T
        for row in range(r0, r1 + 1):
            ty1 = oy - row * T
            ty0 = ty1 - T
            out.append(((int(level), col, row),
                        (tx0, ty0, tx1, ty1),
                        (tx0 - x0) * sx_ppu,
                        (y1 - ty1) * sy_ppu,
                        (tx1 - tx0) * sx_ppu,
                        (ty1 - ty0) * sy_ppu))
    return out


def atlas_layout(tile_px_pairs, dpr=1.0, max_side=ATLAS_MAX_SIDE):
    d = float(dpr or 1.0)
    batches = []
    cur = []
    cw = ch = 0
    row_h = 0
    x = y = 0
    for tid, lw, lh in tile_px_pairs:
        pw = max(1, int(round(float(lw) * d)))
        ph = max(1, int(round(float(lh) * d)))
        if pw + ATLAS_GAP > max_side or ph + ATLAS_GAP > max_side:
            continue
        if x + pw > max_side:
            x = 0
            y = row_h
            row_h = 0
        if y + ph > max_side:
            batches.append((max(1, cw), max(1, ch), cur))
            cur, cw, ch, x, y, row_h = [], 0, 0, 0, 0, 0
        cur.append((tid, x, y, pw, ph))
        x += pw + ATLAS_GAP
        row_h = max(row_h, y + ph + ATLAS_GAP)
        cw = max(cw, x)
        ch = max(ch, row_h)
    batches.append((max(1, cw), max(1, ch), cur))
    return [b for b in batches if b[2]]


def slice_atlas(img, placements, dpr=1.0):
    out = {}
    if img is None or img.isNull():
        return out
    for tid, px, py, pw, ph in placements:
        if px + pw > img.width() or py + ph > img.height():
            continue
        sub = img.copy(QRect(int(px), int(py), int(pw), int(ph)))
        try:
            sub.setDevicePixelRatio(float(dpr or 1.0))
        except Exception:
            exc_note("slice_atlas @ ggis/render/tile_atlas.py:178")
            pass
        out[tid] = sub
    return out


class TileStore:

    def __init__(self, max_bytes=256 * 1024 * 1024, max_items=4096):
        self._d = {}
        self._bytes = 0
        self._max_bytes = int(max_bytes)
        self._max_items = int(max_items)
        self.scene_ver = None
        self.dpr = 1.0
        self.stats = {"put": 0, "hit": 0, "miss": 0, "evict": 0, "clear": 0}

    def _img_bytes(self, img):
        try:
            return int(img.width()) * int(img.height()) * 4
        except Exception:
            exc_note("_img_bytes @ ggis/render/tile_atlas.py:205")
            return 0

    def bind(self, scene_ver, dpr):
        d = float(dpr or 1.0)
        if self.scene_ver != scene_ver or abs(self.dpr - d) > 1e-6:
            self.clear()
            self.scene_ver = scene_ver
            self.dpr = d

    def clear(self):
        self._d.clear()
        self._bytes = 0
        self.stats["clear"] += 1

    def __len__(self):
        return len(self._d)

    @property
    def bytes_used(self):
        return self._bytes

    @property
    def levels(self):
        s = set()
        for (_sv, _dp, tid) in self._d.keys():
            s.add(tid[0])
        return s

    def put(self, tid, img, scene_ver, dpr):
        d = float(dpr or 1.0)
        if self.scene_ver != scene_ver or abs(self.dpr - d) > 1e-6:
            return
        key = (scene_ver, d, tid)
        old = self._d.pop(key, None)
        if old is not None:
            self._bytes -= self._img_bytes(old)
        self._d[key] = img
        self._bytes += self._img_bytes(img)
        self.stats["put"] += 1
        self._evict()

    def get(self, tid, scene_ver, dpr):
        d = float(dpr or 1.0)
        key = (scene_ver, d, tid)
        img = self._d.get(key)
        if img is None:
            self.stats["miss"] += 1
            return None
        self._d.pop(key)
        self._d[key] = img
        self.stats["hit"] += 1
        return img

    def has(self, tid, scene_ver, dpr):
        return (scene_ver, float(dpr or 1.0), tid) in self._d

    def _evict(self):
        while self._d and (self._bytes > self._max_bytes
                           or len(self._d) > self._max_items):
            _k, v = next(iter(self._d.items()))
            self._bytes -= self._img_bytes(v)
            self._d.pop(_k, None)
            self.stats["evict"] += 1

    def missing(self, wanted, scene_ver, dpr):
        d = float(dpr or 1.0)
        out = []
        for item in wanted:
            tid = item[0]
            if not self.has(tid, scene_ver, d):
                out.append(item)
        return out

    def nearest_level(self, level, exclude=None):
        cands = [lv for lv in self.levels if lv != exclude]
        if not cands:
            return None
        return min(cands, key=lambda lv: (abs(lv - int(level)), -lv))
