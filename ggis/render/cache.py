# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from collections import OrderedDict
from typing import Tuple


class LRU:

    __slots__ = ("_max", "_d", "_hits", "_miss")

    def __init__(self, max_items: int = 16):
        self._max = int(max_items)
        self._d: "OrderedDict[Tuple, object]" = OrderedDict()
        self._hits = 0
        self._miss = 0

    def get(self, key, factory=None):
        if key in self._d:
            self._d.move_to_end(key)
            self._hits += 1
            return self._d[key]
        if factory is None:
            self._miss += 1
            return None
        v = factory()
        if v is None:
            self._miss += 1
            return None
        self._d[key] = v
        self._d.move_to_end(key)
        while len(self._d) > self._max:
            self._d.popitem(last=False)
        self._miss += 1
        return v

    def clear(self):
        self._d.clear()

    def stats(self):
        return {"hits": self._hits, "miss": self._miss,
                "size": len(self._d), "max": self._max}


RASTER_WINDOW_CACHE = LRU(64)

THUMB_CACHE = LRU(4)

LAYER_PAINT_CACHE = LRU(8)

RASTER_FRAME_CACHE = OrderedDict()


def reset_for_tests():
    RASTER_WINDOW_CACHE.clear()
    THUMB_CACHE.clear()
    LAYER_PAINT_CACHE.clear()
    RASTER_FRAME_CACHE.clear()
    RASTER_WINDOW_CACHE._hits = RASTER_WINDOW_CACHE._miss = 0
    THUMB_CACHE._hits = THUMB_CACHE._miss = 0
    LAYER_PAINT_CACHE._hits = LAYER_PAINT_CACHE._miss = 0


def invalidate_caches(layer):
    for attr in ("_ggs_bbox", "_ggs_xy", "_ggs_xy_key", "_ggs_sidx",
                 "_ggs_flat", "_ggs_label_cache"):
        try:
            if hasattr(layer, attr):
                delattr(layer, attr)
        except Exception:
            exc_note("invalidate_caches @ ggis/render/cache.py:102")
            pass
    for c in (RASTER_WINDOW_CACHE, THUMB_CACHE, LAYER_PAINT_CACHE,
              RASTER_FRAME_CACHE):
        try:
            c.clear()
        except Exception:
            exc_note("invalidate_caches @ ggis/render/cache.py:110")
            pass
