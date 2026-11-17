# -*- coding: utf-8 -*-


import logging as _logging
from ggis.common.util.exc_report import exc_note
import os

_COV_TO_VIEW_ERR_N = 0


_log = _logging.getLogger("gmagis")

_PROC_DEBUG = bool(os.environ.get("GGIS_RPROC_DEBUG"))

RASTER_FRAME_BUDGET_MS = 24.0

_ZOOM_STEP = 1.5

_ZOOM_IN_BLIT_ONLY = False

_RESIZE_KEEP_FRAME = True

_FROZEN_MARGIN = 0.3
_FROZEN_SCALE_THRESHOLD = 2.0
_USE_FROZEN_MARGIN = True

_ZOOM_RIGHT_DBLCLICK = True
_BOX_ZOOM = True
_WHEEL_PAN_X = True
_HOVER_GRAB_CURSOR = True
_ZOOM_LIMITS = True
_PARTIAL_HOLD_MS = 1200.0
_PARTIAL_INK_GRID = 12
_PARTIAL_INK_KEEP = 0.9
_INTERACT_FINAL_ONLY = True
_VIEW_CACHE_MAX = 64
_VIEW_CACHE_BYTES = 1024 * 1024 * 1024
_MIN_BOX_PX = 8
_MULTI_WORKER = False
_LOAD_BUILD_BUDGET_MS = 33.0
_ZOOM_OUT_MAX_FACTOR = 8.0

_PHASE_IDLE = "idle"
_PHASE_INTERACTING = "interacting"
_PHASE_SETTLING = "settling"

_CAUSE_ZOOM = "zoom"
_CAUSE_PAN = "pan"
_CAUSE_PAN_END = "pan_end"
_CAUSE_RESIZE = "resize"
_CAUSE_JUMP = "jump"
_CAUSE_DATA = "data"
_CAUSE_REDRAW = "redraw"
_INTERACTIVE_CAUSES = frozenset(
    (_CAUSE_ZOOM, _CAUSE_PAN, _CAUSE_PAN_END, _CAUSE_RESIZE))


class _FrameRef:

    __slots__ = ("image", "view_extent", "render_extent", "done")

    def __init__(self, image, view_extent, render_extent, done):
        self.image = image
        self.view_extent = view_extent
        self.render_extent = render_extent
        self.done = bool(done)

    @property
    def usable(self):
        return self.image is not None and not self.image.isNull()


class _RequestRef:

    __slots__ = ("seq", "req_seq", "since", "in_flight")

    def __init__(self, seq, req_seq, since):
        self.seq = seq
        self.req_seq = req_seq
        self.since = float(since or 0.0)
        self.in_flight = req_seq is not None




_USE_PROC_RENDER = True
_PROC_PRESPAWN = True

_VEC_RUNS = True


def _proc_spawn_allowed():
    try:
        import multiprocessing as _mp
        return not bool(_mp.current_process().daemon)
    except Exception:
        exc_note("_proc_spawn_allowed @ ggis/render/map_canvas.py:302")
        return False

_TILE_REPAINT_MS = 100

_RENDER_POLL_MS = 120

_TILE_DRAW_ERR_LAST = {}

_TILE_SKIP_LAST = {}


def _note_tile_draw_error(lyr):
    import time as _tm
    import traceback as _tb
    try:
        _k = str(getattr(lyr, "name", lambda: "?")())
    except Exception:
        exc_note("_note_tile_draw_error @ ggis/render/map_canvas.py:341")
        _k = "?"
    _now = _tm.time()
    if _now - _TILE_DRAW_ERR_LAST.get(_k, 0.0) < 3.0:
        return
    _TILE_DRAW_ERR_LAST[_k] = _now
    try:
        import logging as _lg
        _lg.getLogger("gmagis").error("[瓦片·异常] 图层=%s\n%s",
                                      _k, _tb.format_exc())
    except Exception:
        exc_note("_note_tile_draw_error @ ggis/render/map_canvas.py:351")
        pass


def _note_tile_skip(lyr, reason):
    import time as _tm
    try:
        _k = str(getattr(lyr, "name", lambda: "?")())
    except Exception:
        exc_note("_note_tile_skip @ ggis/render/map_canvas.py:365")
        _k = "?"
    _now = _tm.time()
    if _now - _TILE_SKIP_LAST.get(_k, 0.0) < 3.0:
        return
    _TILE_SKIP_LAST[_k] = _now
    try:
        import logging as _lg
        _lg.getLogger("gmagis").info("[瓦片·跳过] 图层=%s 原因=%s",
                                     _k, reason)
    except Exception:
        exc_note("_note_tile_skip @ ggis/render/map_canvas.py:375")
        pass


def frame_target_rect(fe, ex, w, h):
    exw = ex.width() or 1.0
    exh = ex.height() or 1.0
    return ((fe.xmin - ex.xmin) / exw * w,
            (ex.ymax - fe.ymax) / exh * h,
            fe.width() / exw * w,
            fe.height() / exh * h)
