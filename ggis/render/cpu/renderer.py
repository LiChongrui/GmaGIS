# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from collections import OrderedDict

from . import symbol_stack as SS

__all__ = ["category_key", "symbol_stacks", "clear_cache", "cache_stats"]

_CACHE_MAX = 64
_CACHE = OrderedDict()
_STATS = {"hit": 0, "miss": 0}


def category_key(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e15:
            return str(int(value))
        return repr(value)
    try:
        return str(value)
    except Exception:
        exc_note("category_key @ ggis/render/cpu/renderer.py:65")
        return ""


def clear_cache():
    _CACHE.clear()


def cache_stats():
    return dict(_STATS)


def symbol_stacks(layer, kind, symbol=None, clamp=True):
    classes = None
    syms = []
    if symbol is None:
        try:
            from ..renderers import get_renderer
            renderer = get_renderer(layer)
            syms = list(renderer.symbols() or [])
        except Exception:
            exc_note("symbol_stacks @ ggis/render/cpu/renderer.py:95")
            syms = []
            renderer = None
        if not syms:
            try:
                from ..symbol import default_symbol
                syms = [default_symbol(kind, 0)]
            except Exception:
                exc_note("symbol_stacks @ ggis/render/cpu/renderer.py:102")
                syms = []
        if renderer is not None:
            try:
                classes = renderer.class_array(layer)
            except Exception:
                exc_note("symbol_stacks @ ggis/render/cpu/renderer.py:107")
                classes = None
            if classes is None or len(syms) <= 1:
                classes = None
                syms = syms[:1]
    else:
        syms = [symbol]

    if not syms:
        return [], None
    key = (id(layer), _render_version(layer), str(kind), len(syms),
           bool(clamp))
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        _STATS["hit"] += 1
        return hit, classes
    stacks = [SS.symbol_stack_from_ggs_symbol(s, kind, clamp=clamp)
              for s in syms]
    _CACHE[key] = stacks
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    _STATS["miss"] += 1
    return stacks, classes


def _render_version(layer):
    try:
        from ..renderers import render_version
        return int(render_version(layer))
    except Exception:
        exc_note("_render_version @ ggis/render/cpu/renderer.py:138")
        return 0
