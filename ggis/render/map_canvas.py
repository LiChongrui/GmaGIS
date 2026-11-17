# -*- coding: utf-8 -*-



from ggis.common.util.exc_report import exc_note

import logging as _logging
import os
import time
import traceback

from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.crs import (GgsCrs, convert_bounds,
                        crs_transformer, needs_reproject)
from ggis.core.crs.extent import GgsRectangle
from ggis.core.model.project import GgsProject
from ggis.core.model.selection import GgsSelection
from ggis.core.app.i18n import tr as _tr
from ggis.core.app import settings
from ggis.core.model.layer import data_version as _dv
from .painter import (GgsRasterPainter, GgsVectorPainter, invalidate_caches,
                      selection_symbol, vector_lod_tol)
from .pens import raster_backend
from .cpu.backend import GgsQcPainter
from .cpu.raster import GgsBuiltinRasterPainter
from .cpu import interaction as _IZ
from .labeling import (LABEL_CANDIDATE_BUDGET_MS, LABEL_CANDIDATE_CAP,
                       LabelEngine, draw_labels, get_label_style,
                       invalidate_label_cache)
from .render_task import RenderTask
from .renderers import default_renderer, get_renderer, set_renderer
from .symbol import default_symbol
from .tiles import GgsTilePainter, tileReadySignal
from .viewport import GgsMapSettings

__all__ = ["GgsMapCanvas"]

from ._canvas_cfg import (
    RASTER_FRAME_BUDGET_MS,
    _BOX_ZOOM,
    _CAUSE_DATA,
    _CAUSE_JUMP,
    _CAUSE_PAN,
    _CAUSE_PAN_END,
    _CAUSE_REDRAW,
    _CAUSE_RESIZE,
    _CAUSE_ZOOM,
    _COV_TO_VIEW_ERR_N,
    _FROZEN_MARGIN,
    _FROZEN_SCALE_THRESHOLD,
    _HOVER_GRAB_CURSOR,
    _INTERACTIVE_CAUSES,
    _INTERACT_FINAL_ONLY,
    _LOAD_BUILD_BUDGET_MS,
    _MIN_BOX_PX,
    _MULTI_WORKER,
    _PARTIAL_HOLD_MS,
    _PARTIAL_INK_GRID,
    _PARTIAL_INK_KEEP,
    _PHASE_IDLE,
    _PHASE_INTERACTING,
    _PHASE_SETTLING,
    _PROC_DEBUG,
    _PROC_PRESPAWN,
    _RENDER_POLL_MS,
    _RESIZE_KEEP_FRAME,
    _TILE_DRAW_ERR_LAST,
    _TILE_REPAINT_MS,
    _TILE_SKIP_LAST,
    _USE_FROZEN_MARGIN,
    _USE_PROC_RENDER,
    _VEC_RUNS,
    _VIEW_CACHE_BYTES,
    _VIEW_CACHE_MAX,
    _WHEEL_PAN_X,
    _ZOOM_IN_BLIT_ONLY,
    _ZOOM_LIMITS,
    _ZOOM_OUT_MAX_FACTOR,
    _ZOOM_RIGHT_DBLCLICK,
    _ZOOM_STEP,
    _log,
)
from ._canvas_cfg import (_FrameRef, _RequestRef,
                         _note_tile_draw_error, _note_tile_skip, _proc_spawn_allowed)
from ._canvas_state import CanvasStateMixin
from ._frame_store import FrameStoreMixin
from ._render_director import RenderDirectorMixin
from ._selection_overlay import SelectionOverlayMixin
from ._tile_push import TilePushMixin


class GgsMapCanvas(CanvasStateMixin, FrameStoreMixin, RenderDirectorMixin, SelectionOverlayMixin, TilePushMixin,
                  QWidget):

    scaleChanged = Signal(float)
    xyCoordinates = Signal(object)
    mapToolSet = Signal(object)
    renderStarting = Signal()
    renderComplete = Signal()
    renderStatus = Signal(str)
    extentChanged = Signal()
    crsChanged = Signal()

    def __init__(self, parent=None, prespawn=None):
        super().__init__(parent)
        self._prespawn = prespawn
        self._forced_dpr = 0.0
        self.setObjectName("GgsMapCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self._project = GgsProject.instance()
        self._layer_source = lambda: list(self._project.layers())
        self._settings = GgsMapSettings()
        self._extent = GgsRectangle()
        self._prev_canvas_w = 0
        self._prev_canvas_h = 0
        self._prev_canvas_x = None
        self._prev_canvas_y = None
        self._prev_mainw_size = None
        self._color = QColor("#1E242C")
        self._crs = ""
        self._scale_locked = False
        self._crs_obj = None
        self._extent_crs = None
        self._crs_explicit = False
        self._anti_alias = True
        self._tool = None
        self._tool_name = ""
        self._frame_shape = 0

        self._qc_ras_painter = GgsBuiltinRasterPainter()
        self._vec_painter = GgsVectorPainter()
        self._ras_painter = GgsRasterPainter()
        self._qc_painter = GgsQcPainter()
        self._tile_painter = GgsTilePainter()
        self._label_engine = LabelEngine()
        self._labels_enabled = True
        self._symbols = {}
        self._sym_seq = 0

        self._panning = False
        self._last_pos = QPoint()
        self._press_pos = QPoint()
        self._rubber = QRect()

        self._frozen = None
        self._last_visible_seq = None
        self._frozen_done = False
        self._interacting = False
        self._phase = _PHASE_IDLE
        self._cause = None
        self._dirty = False
        self._frozen_extent = None
        self._frozen_render_extent = None
        self._frame_renderer = None
        self._proc = None
        self._sel = GgsSelection()
        GgsSelection.set_active(self._sel)
        self._proc_scene_ver = None
        self._data_gen = 0
        self._proc_seq = 0
        self._proc_stopped = False
        self._proc_data_gen_at_req = None
        self._bg_data_gen_at_req = None
        self._proc_ext = None
        self._proc_failed = False
        self._proc_warm_retry = None
        self._proc_warm_retry_n = 0
        self._proc_kick_count = 0
        self._proc_vckey_at_req = None
        self._proc_last_final_key = None
        self._gpu_fatal_shown = False
        self._edit_proc_block = False
        self._bg_task_ext = None
        self._bg_stale = False
        self._edit_geo_gen = 0
        self._bg_req_gen = 0
        self._painting = False
        self._view_cache = {}
        self._tile_gen = 0
        self._hold_partial_frames = False
        self._hold_since = 0.0
        self._ink_key = None
        self._ink_val = 0.0
        self._render_seq = 0
        self._bg_qc = None
        self._bg_ras = None
        self._bg_tile = None
        self._last_wheel_t = None
        self._box_zoom_on = False
        self._box_p0 = None
        self._box_p1 = None
        self._sel_img = None
        self._sel_key = None
        self._raster_pending = False
        self._vector_pending = False
        self._progressive_scheduled = False
        self._vec_cache = None
        self._render_poll = None
        self._render_busy = False
        self._render_text = ""

        try:
            self._project.layersChanged.connect(self._on_layers_changed)
            self.crsChanged.connect(self._on_crs_changed)
            self._project.layerVisibilityChanged.connect(
                self._on_layers_changed)
        except Exception:
            exc_note("__init__ @ ggis/render/map_canvas.py:760")
            pass
        try:
            self._sel.changed.connect(self.refresh_selection)
        except Exception:
            exc_note("__init__ @ ggis/render/map_canvas.py:770")
            pass
        try:
            self._tile_tick = QTimer(self)
            self._tile_tick.setSingleShot(True)
            self._tile_tick.setInterval(_TILE_REPAINT_MS)
            self._tile_tick.timeout.connect(self._on_tile_tick)
            tileReadySignal().connect(self._on_tile_ready)
        except Exception:
            exc_note("__init__ @ ggis/render/map_canvas.py:785")
            pass

        _do_prespawn = (_PROC_PRESPAWN if self._prespawn is None
                        else bool(self._prespawn))
        if _do_prespawn and _proc_spawn_allowed():
            try:
                _c = self._ensure_proc()
                if _c is not None:
                    _c.warmup()
            except Exception:
                exc_note("__init__ @ ggis/render/map_canvas.py:808")
                import traceback
                traceback.print_exc()
