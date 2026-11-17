# -*- coding: utf-8 -*-

from ._canvas_cfg import (
    RASTER_FRAME_BUDGET_MS,
    _INTERACT_FINAL_ONLY,
    _LOAD_BUILD_BUDGET_MS,
    _MULTI_WORKER,
    _PARTIAL_HOLD_MS,
    _PARTIAL_INK_GRID,
    _PARTIAL_INK_KEEP,
    _PROC_DEBUG,
    _RENDER_POLL_MS,
    _RequestRef,
    _USE_PROC_RENDER,
    _VEC_RUNS,
    _note_tile_draw_error,
    _note_tile_skip,
)
from .viewport import GgsMapSettings
from ggis.core.crs.extent import GgsRectangle
from .labeling import (LABEL_CANDIDATE_BUDGET_MS, LABEL_CANDIDATE_CAP,
                       LabelEngine, draw_labels, get_label_style,
                       invalidate_label_cache)
from PySide6.QtGui import QColor, QImage, QPainter

from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from .render_task import RenderTask
from ggis.core.app.i18n import tr as _tr
from .renderers import default_renderer, get_renderer, set_renderer
from .symbol import default_symbol
from ggis.common.util.exc_report import exc_note
from .painter import (GgsRasterPainter, GgsVectorPainter, invalidate_caches,
                      selection_symbol, vector_lod_tol)
from .pens import raster_backend
import time


class RenderDirectorMixin:

    _PROC_FAIL_COOLDOWN = 60.0


    def _hold_partial_begin(self):
        self._hold_partial_frames = True
        try:
            self._hold_since = time.perf_counter()
        except Exception:
            exc_note("_hold_partial_begin @ ggis/render/map_canvas.py:1529")
            self._hold_since = 0.0

    def _hold_active(self):
        if not self._hold_partial_frames or _PARTIAL_HOLD_MS <= 0:
            return False
        try:
            return ((time.perf_counter() - self._hold_since) * 1000.0
                    < _PARTIAL_HOLD_MS)
        except Exception:
            exc_note("_hold_active @ ggis/render/map_canvas.py:1539")
            return False

    def _frame_ink_ratio(self, img):
        if img is None or img.isNull():
            return 0.0
        try:
            w, h = int(img.width()), int(img.height())
        except Exception:
            exc_note("_frame_ink_ratio @ ggis/render/map_canvas.py:1554")
            return 0.0
        if w <= 0 or h <= 0:
            return 0.0
        try:
            bg = self._color
            br, bgn, bbl = bg.red(), bg.green(), bg.blue()
        except Exception:
            exc_note("_frame_ink_ratio @ ggis/render/map_canvas.py:1561")
            return 0.0
        k = int(_PARTIAL_INK_GRID) or 1
        n = tot = 0
        for iy in range(k):
            y = min(h - 1, int((iy + 0.5) * h / k))
            for ix in range(k):
                x = min(w - 1, int((ix + 0.5) * w / k))
                tot += 1
                try:
                    p = img.pixel(x, y)
                except Exception:
                    exc_note("_frame_ink_ratio @ ggis/render/map_canvas.py:1572")
                    continue
                if (abs(((p >> 16) & 0xFF) - br) > 12
                        or abs(((p >> 8) & 0xFF) - bgn) > 12
                        or abs((p & 0xFF) - bbl) > 12):
                    n += 1
        return n / float(max(1, tot))

    def _screen_ink(self):
        fz = self._frozen
        if fz is None or fz.isNull():
            return 0.0
        key = id(fz)
        if self._ink_key != key:
            self._ink_key = key
            self._ink_val = self._frame_ink_ratio(fz)
        return self._ink_val

    def _would_shrink_screen(self, img):
        try:
            fe = self._frozen_extent
            preview_on = (self._hold_active()
                          or (fe is not None and fe != self._extent))
            if not preview_on:
                return False
            ref = self._screen_ink()
            if ref <= 0.0:
                return False
            cur = self._frame_ink_ratio(img)
            if cur >= ref * float(_PARTIAL_INK_KEEP):
                return False
            if _PROC_DEBUG:
                print("[防闪] 挡掉这帧：屏幕 %.2f%% ＞ 这帧 %.2f%%（%s）"
                      % (ref * 100.0, cur * 100.0,
                         "握持中" if self._hold_active() else "预览在顶"),
                      flush=True)
            return True
        except Exception:
            exc_note("_would_shrink_screen @ ggis/render/map_canvas.py:1659")
            return False

    def refresh(self):
        self._clear_frozen()
        self._kick_render()
        self.update()

    def rerender(self):
        self._clear_frozen()
        self._kick_render()
        self.update()

    def _refresh_lod(self):
        import time as _t
        try:
            if (self._interacting or self._panning
                    or self._dirty):
                return
            _now = _t.monotonic()
            if _now - getattr(self, "_lod_refresh_t", 0.0) < 0.15:
                return
            self._lod_refresh_t = _now
            self._clear_frozen(keep_preview=True)
            try:
                self._view_cache.clear()
            except Exception:
                exc_note("_refresh_lod @ ggis/render/map_canvas.py:1802")
                pass
            self._kick_render()
            self.update()
        except Exception:
            exc_note("_refresh_lod @ ggis/render/map_canvas.py:1806")
            pass

    def stop_render(self):
        self._proc_seq = None
        self._proc_stopped = True
        self._render_seq += 1
        try:
            c = self._proc
            if c is not None:
                c.invalidate()
        except Exception:
            exc_note("stop_render @ ggis/render/map_canvas.py:1832")
            pass
        try:
            r = self._frame_renderer
            if r:
                r.invalidate()
        except Exception:
            exc_note("stop_render @ ggis/render/map_canvas.py:1838")
            pass
        for _n in ("_proc_warm_retry",):
            try:
                t = getattr(self, _n, None)
                if t is not None and t is not False:
                    t.stop()
            except Exception:
                exc_note("stop_render @ ggis/render/map_canvas.py:1845")
                pass

    def set_layer_source(self, func):
        if func is None:
            self._layer_source = lambda: list(self._project.layers())
        else:
            self._layer_source = func
        self._bump_data_gen()

    def render_to_image(self, width, height, dpi=None, with_labels=True,
                        with_selection=True, with_overlay=False, extent=None):
        img = QImage(max(1, int(width)), max(1, int(height)),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(self._color)
        if getattr(self, "_project", None) is None:
            return img
        ext = extent if extent is not None else self._extent_snapshot()
        if ext is None or ext.is_empty():
            return img
        s = GgsMapSettings()
        try:
            s.set_extent(GgsRectangle(ext.xmin, ext.ymin, ext.xmax, ext.ymax))
            s.set_output_size(QSize(max(1, int(width)), max(1, int(height))))
            s.set_lod_reference_width(0)
            s.set_destination_crs(self.effectiveCrs())
            d = 0.0
            try:
                d = float(dpi) if dpi else 0.0
            except Exception:
                exc_note("render_to_image @ ggis/render/map_canvas.py:1916")
                d = 0.0
            if d <= 0:
                try:
                    scr = self.screen()
                    d = float(scr.logicalDotsPerInch()) if scr is not None \
                        else 96.0
                except Exception:
                    exc_note("render_to_image @ ggis/render/map_canvas.py:1923")
                    d = 96.0
            s.set_dpi(d)
        except Exception:
            exc_note("render_to_image @ ggis/render/map_canvas.py:1926")
            pass
        p = QPainter(img)
        try:
            _dpm = int(d / 0.0254)
            img.setDotsPerMeterX(_dpm)
            img.setDotsPerMeterY(_dpm)
        except Exception:
            exc_note("render_to_image @ ggis/render/map_canvas.py:1939")
            pass
        eng = self._label_engine
        _sdev, _sdpi = eng._device, eng._device_dpi
        eng.set_paint_device(img, d)
        try:
            if self._anti_alias:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._paint_scene(p, s,
                              with_labels=bool(with_labels),
                              with_selection=bool(with_selection),
                              with_overlay=bool(with_overlay),
                              raster_budget_ms=None, vec_cache=False,
                              label_capped=False)
        finally:
            p.end()
            eng._device = _sdev
            eng._device_dpi = _sdpi
            try:
                eng._fm_cache.clear()
            except Exception:
                exc_note("render_to_image @ ggis/render/map_canvas.py:1960")
                pass
        return img

    def _ensure_render_poll(self):
        if self._render_poll is None:
            try:
                from PySide6.QtCore import QTimer
                t = QTimer(self)
                t.setInterval(_RENDER_POLL_MS)
                t.timeout.connect(self._poll_render_status)
                self._render_poll = t
            except Exception:
                exc_note("_ensure_render_poll @ ggis/render/map_canvas.py:1982")
                self._render_poll = None
                return
        try:
            if not self._render_poll.isActive():
                self._render_poll.start()
        except Exception:
            exc_note("_ensure_render_poll @ ggis/render/map_canvas.py:1990")
            pass

    def render_status(self):
        parts = []
        try:
            _c = self._proc
            if _c is not None and _c.is_busy():
                parts.append("渲染")
        except Exception:
            exc_note("render_status @ ggis/render/map_canvas.py:2031")
            pass
        try:
            from .tiles import TileLoader
            _n_tile = len(TileLoader._pending)
            if _n_tile > 0:
                parts.append(_tr("瓦片 {0}").format(_n_tile))
        except Exception:
            exc_note("render_status @ ggis/render/map_canvas.py:2046")
            pass
        try:
            if getattr(self, "_raster_pending", False):
                parts.append("渐进")
        except Exception:
            exc_note("render_status @ ggis/render/map_canvas.py:2051")
            pass
        try:
            if getattr(self, "_vector_pending", False):
                parts.append("矢量")
        except Exception:
            exc_note("render_status @ ggis/render/map_canvas.py:2059")
            pass
        try:
            r = self._frame_renderer
            if r is not None and getattr(r, "last_error", ""):
                parts.append("渲染错误")
        except Exception:
            exc_note("render_status @ ggis/render/map_canvas.py:2066")
            pass
        return (bool(parts), "、".join(parts))

    def _poll_render_status(self):
        try:
            busy, text = self.render_status()
        except Exception:
            exc_note("_poll_render_status @ ggis/render/map_canvas.py:2079")
            return
        was = self._render_busy
        if busy == was and text == self._render_text:
            return
        self._render_busy = busy
        self._render_text = text
        try:
            if busy and not was:
                self.renderStarting.emit()
            elif was and not busy:
                self.renderComplete.emit()
            self.renderStatus.emit(text)
        except RuntimeError:
            exc_note("_poll_render_status @ ggis/render/map_canvas.py:2092")
            pass

    def _map_settings(self):
        s = self._settings
        s.set_extent(self._extent)
        s.set_output_size(QSize(max(1, self.width()), max(1, self.height())))
        s.set_lod_reference_width(0)
        s.set_destination_crs(self.effectiveCrs())
        try:
            scr = self.screen()
            if scr is not None:
                s.set_dpi(scr.logicalDotsPerInch())
        except Exception:
            exc_note("_map_settings @ ggis/render/map_canvas.py:2111")
            pass
        return s

    def map_settings(self):
        return self._map_settings()

    def _rebuild_symbols(self):
        dark = self._is_dark_bg()
        self._symbols = {}
        for i, lyr in enumerate(self._layer_source()):
            if not lyr.is_vector():
                continue
            try:
                if lyr.__dict__.get("_renderer") is not None:
                    continue
                set_renderer(lyr, default_renderer(lyr, i))
            except Exception:
                exc_note("_rebuild_symbols @ ggis/render/map_canvas.py:2145")
                continue
            self._symbols[lyr.id()] = default_symbol(lyr.base_kind(), i,
                                                     dark_bg=dark)
        self._sym_seq = len(self._symbols)

    def invalidate_symbol(self, layer):
        self._sel_img = None
        self._sel_key = None
        try:
            self._rebuild_symbols()
        except Exception:
            exc_note("invalidate_symbol @ ggis/render/map_canvas.py:2167")
            pass
        self._refresh_scene(keep_frame=True)

    def refresh_render_settings(self):
        try:
            for _lyr in self._layer_source():
                invalidate_caches(_lyr)
        except Exception:
            exc_note("refresh_render_settings @ ggis/render/map_canvas.py:2214")
            pass
        try:
            c = self._proc
            if c is not None:
                c.push_settings()
        except Exception:
            exc_note("refresh_render_settings @ ggis/render/map_canvas.py:2226")
            pass
        self._sel_img = None
        self._sel_key = None
        self._refresh_scene(keep_frame=False)

    def _schedule_progressive(self):
        if self._progressive_scheduled:
            return
        self._progressive_scheduled = True

        def _go():
            self._progressive_scheduled = False
            if not (self._raster_pending or self._vector_pending):
                return
            if self._vector_pending:
                self.prewarm_flat(force=True)
            self.update()

        try:
            QTimer.singleShot(0, _go)
        except Exception:
            exc_note("_schedule_progressive @ ggis/render/map_canvas.py:2793")
            self._progressive_scheduled = False
            self.update()

    def _ensure_proc(self):
        if self._proc is not None or self._proc_failed:
            return self._proc
        try:
            from .backend import make_backend
            from .cpu.render_proc import _BAND_WORKERS
            multi = bool(_MULTI_WORKER) and int(_BAND_WORKERS) > 1
            kind = "gpu_tile"
            b = make_backend(kind, self, multi)
            _gpu_fail = ""
            if b.failed():
                _gpu_fail = getattr(b, "fail_reason", "") or "未知（构造失败）"
                try:
                    import logging as _lg_f
                    _lg_f.getLogger("gmagis").critical(
                        "[渲染] gpu_tile 构造失败（%s）⇒ 不再回退 CPU，已报错。",
                        _gpu_fail)
                except Exception:
                    exc_note("_ensure_proc @ ggis/render/map_canvas.py:2835")
                    pass
                self._report_gpu_fatal(
                    "GPU 渲染初始化失败",
                    "GPU 渲染后端初始化失败：\n%s\n\n"
                    "程序不会切换回 CPU 渲染。\n"
                    "恢复方式：修复显卡驱动 / OpenGL 后重启程序。"
                    % _gpu_fail)
            _gpu_active = False
            try:
                _ga = getattr(b, "gpu_active", None)
                if callable(_ga):
                    _gpu_active = bool(_ga())
            except Exception:
                exc_note("_ensure_proc @ ggis/render/map_canvas.py:2849")
                _gpu_active = False
            try:
                import logging as _lg_b
                _lg_b.getLogger("gmagis").info(
                    "[渲染] 实际后端=%s | gpu_active=%s | 失败原因=%s",
                    b.backend_type, "1" if _gpu_active else "0",
                    _gpu_fail or "无")
            except Exception:
                exc_note("_ensure_proc @ ggis/render/map_canvas.py:2857")
                pass
            b.rendered.connect(self._on_proc_frame)
            try:
                _rc = getattr(b, "_client", None)
                if _rc is not None:
                    _rc.lod_ready.connect(self._refresh_lod)
            except Exception:
                exc_note("_ensure_proc @ ggis/render/map_canvas.py:2862")
                pass
            self._proc = b
        except Exception:
            exc_note("_ensure_proc @ ggis/render/map_canvas.py:2865")
            import traceback
            traceback.print_exc()
            self._proc_failed = True
            self._proc = None
        return self._proc

    def _report_gpu_fatal(self, title, msg):
        try:
            import logging as _lg
            _lg.getLogger("gmagis").critical("[渲染] %s：%s", title, msg)
        except Exception:
            exc_note("_report_gpu_fatal @ ggis/render/map_canvas.py:2881")
            pass
        try:
            if self._gpu_fatal_shown:
                return
            self._gpu_fatal_shown = True
            from PySide6.QtWidgets import QMessageBox
            _parent = None
            try:
                _parent = self.window()
            except Exception:
                exc_note("_report_gpu_fatal @ ggis/render/map_canvas.py:2891")
                _parent = None
            QMessageBox.critical(_parent, "GmaGIS · " + title, msg)
        except Exception:
            exc_note("_report_gpu_fatal @ ggis/render/map_canvas.py:2894")
            pass

    def _flicker_guard_scene(self):
        try:
            return bool(self._has_visible_raster()
                        or self._has_visible_tile())
        except Exception:
            exc_note("_flicker_guard_scene @ ggis/render/map_canvas.py:2914")
            return True

    def _bump_data_gen(self):
        try:
            self._data_gen += 1
        except Exception:
            exc_note("_bump_data_gen @ ggis/render/map_canvas.py:3071")
            self._data_gen = 1
        self._dirty = True
        try:
            self._view_cache.clear()
        except Exception:
            exc_note("_bump_data_gen @ ggis/render/map_canvas.py:3084")
            pass
        try:
            self.update()
        except Exception:
            exc_note("_bump_data_gen @ ggis/render/map_canvas.py:3088")
            pass

    def _proc_sync_scene(self, c):
        try:
            from .cpu.render_proc import scene_specs
            from ..core.crs import crs_key
            _lyrs = list(self._layer_source())
            ver = self._scene_ver_now()
            _crs = str(crs_key(self.effectiveCrs()) or "")
            _spec_cache = getattr(self, "_proc_specs_cache", None)
            if _spec_cache is not None and _spec_cache[0] == (ver, _crs):
                specs = _spec_cache[1]
            else:
                specs = scene_specs(self._project, _lyrs)
                if specs is None:
                    self._proc_failed = True
                    return False
                self._proc_specs_cache = ((ver, _crs), specs)
            if (ver != self._proc_scene_ver
                    or _crs != getattr(self, "_proc_scene_crs", None)):
                self._proc_scene_ver = ver
                self._proc_scene_crs = _crs
                c.set_scene(ver, specs, _crs)
                c.push_scene()
            return True
        except Exception:
            exc_note("_proc_sync_scene @ ggis/render/map_canvas.py:3138")
            import traceback
            traceback.print_exc()
            self._proc_failed = True
            return False

    def _proc_task(self, seq):
        d = RenderTask.from_canvas(self).proc_dict(seq)
        self._proc_ext = d["extent"]
        return d

    def set_edit_proc_block(self, on):
        on = bool(on)
        if on == self._edit_proc_block:
            return
        self._edit_proc_block = on
        if not on:
            self._edit_synced = {}
            self._edit_sync_failed = False
        if on:
            try:
                _r = self._ensure_frame_renderer()
                if _r is not None:
                    _r.warmup()
                self._bg_painters()
            except Exception:
                exc_note("set_edit_proc_block @ ggis/render/map_canvas.py:3234")
                pass
        try:
            self._refresh_scene(keep_frame=False)
        except Exception:
            exc_note("set_edit_proc_block @ ggis/render/map_canvas.py:3238")
            try:
                self.update()
            except Exception:
                exc_note("set_edit_proc_block @ ggis/render/map_canvas.py:3241")
                pass

    def _proc_usable(self):
        if not _USE_PROC_RENDER:
            return None
        if self._proc_failed:
            _now = time.monotonic()
            try:
                _at = float(getattr(self, "_proc_fail_at", 0.0) or 0.0)
            except Exception:
                exc_note("_proc_usable @ ggis/render/_render_director.py")
                _at = 0.0
            if not _at:
                self._proc_fail_at = _now
                return None
            if (_now - _at) < self._PROC_FAIL_COOLDOWN:
                return None
            self._proc_failed = False
            self._proc_fail_at = 0.0
            self._cool_kick_warn_n = 0
            self._gpu_fatal_shown = False
            self._proc = None
        c = self._ensure_proc()
        if c is None:
            return None
        if c.failed():
            self._proc_failed = True
            return None
        if self._edit_proc_block and getattr(self, "_edit_sync_failed",
                                             False):
            return None
        if not self._proc_sync_scene(c):
            self._proc_failed = True
            return None
        try:
            if not c.is_warm():
                return None
        except Exception:
            exc_note("_proc_usable @ ggis/render/map_canvas.py:3289")
            return None
        return c

    def _settings_for_extent(self, ext4, out=None):
        if out is not None:
            try:
                w, h = max(1, int(out[0])), max(1, int(out[1]))
            except Exception:
                exc_note("_settings_for_extent @ ggis/render/map_canvas.py:3307")
                w, h = max(1, self.width()), max(1, self.height())
        else:
            w, h = max(1, self.width()), max(1, self.height())
        s = GgsMapSettings()
        try:
            if ext4 is not None:
                s.set_extent(GgsRectangle(ext4[0], ext4[1], ext4[2], ext4[3]))
            s.set_output_size(QSize(w, h))
            s.set_lod_reference_width(0)
            s.set_destination_crs(self.effectiveCrs())
            scr = self.screen()
            if scr is not None:
                s.set_dpi(float(scr.logicalDotsPerInch()))
        except Exception:
            exc_note("_settings_for_extent @ ggis/render/map_canvas.py:3307")
            pass
        return s

    @property
    def request(self):
        rs = getattr(self, "_proc_req_seq", None)
        return _RequestRef(
            getattr(self, "_proc_seq", None), rs,
            getattr(self, "_proc_req_since", 0.0))

    def accept_frame(self, img, seq, final):
        if img is None or img.isNull():
            return (False, "empty")
        try:
            if int(seq) != self._proc_seq:
                return (False, "stale_seq")
        except Exception:
            exc_note("accept_frame @ ggis/render/map_canvas.py")
            return (False, "stale_seq")
        if final:
            return (True, "final")
        f = self.frame
        if _INTERACT_FINAL_ONLY and (self._panning or self._is_frozen()):
            return (False, "interact_final_only")
        if (self._proc_vector_delegated() and f.done and f.usable):
            return (False, "vector_delegated")
        if self._hold_active() and f.done:
            try:
                if (f.usable and f.view_extent is not None
                        and f.view_extent == self._extent):
                    return (False, "hold_same_view")
            except Exception:
                exc_note("accept_frame @ ggis/render/map_canvas.py")
        _hold_expired = (bool(getattr(self, "_hold_partial_frames", False))
                         and not self._hold_active())
        if not _hold_expired and self._would_shrink_screen(img):
            return (False, "ink_shrink")
        return (True, "ok")

    def _log_frame_reject(self, reason, seq, final):
        """静默拒帧限流日志：同一原因最多记一条。"""
        try:
            if not getattr(self, "_reject_logged", None):
                self._reject_logged = set()
            if reason in self._reject_logged:
                return
            self._reject_logged.add(reason)
            import logging as _lg_r
            _lg_r.getLogger("gmagis").warning(
                "[渲染] 帧被拒 reason=%s seq=%s final=%s "
                "(同一原因后续不再重复记录)", reason, seq, final)
        except Exception:
            exc_note("_log_frame_reject @ _render_director.py")
            pass

    def on_frame_rejected(self, reason, seq, final):
        self._last_frame_reject = reason
        if reason not in ("empty", "stale_seq"):
            return
        inflight = getattr(self, "_proc_req_seq", None)
        if (inflight is None or seq is None
                or not isinstance(seq, (int, float))
                or not isinstance(inflight, (int, float))
                or int(seq) != int(inflight)):
            return
        self._proc_req_seq = None
        self._schedule_proc_warm_retry()

    def _on_proc_frame(self, img, seq, final=False):
        ok, reason = self.accept_frame(img, seq, final)
        if not ok:
            self.on_frame_rejected(reason, seq, final)
            return
        ext4 = self._proc_ext
        if ext4 is not None:
            try:
                _ve = self._cov_to_view(GgsRectangle(*ext4))
                _fe = GgsRectangle(*ext4)
            except Exception:
                exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3388")
                _ve = self._extent_snapshot()
                _fe = None
            self._commit_frame(img, _ve, _fe)
        else:
            self._frozen = img
            self._frozen_done = True
        if final:
            self._hold_partial_frames = False
            self._proc_req_seq = None
        same = False
        try:
            same = (self._frozen_extent is not None
                    and self._frozen_extent == self._extent)
        except Exception:
            exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3397")
            same = False
        _stale_scene = False
        try:
            _req = getattr(self, "_proc_scene_ver_at_req", None)
            if _req is not None and int(seq) == int(_req[0]):
                _stale_scene = (int(_req[1]) != int(self._proc_scene_ver or 0))
        except Exception:
            exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3413")
            _stale_scene = False
        try:
            _cr = getattr(self, "_proc_crs_at_req", None)
            if _cr is not None and int(seq) == int(_cr[0]):
                from ..core.crs import crs_key
                _now = str(crs_key(self.effectiveCrs()) or "")
                if _now != str(_cr[1] or ""):
                    _stale_scene = True
        except Exception:
            exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3429")
            pass
        _stale_data = False
        try:
            _dg = getattr(self, "_proc_data_gen_at_req", None)
            if _dg is not None and int(seq) == int(_dg[0]):
                _stale_data = (int(_dg[1]) != int(self._data_gen))
        except Exception:
            exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3442")
            _stale_data = False
        if final and not _stale_scene and not _stale_data:
            self._raster_pending = False
            self._vector_pending = False
            try:
                _rq = getattr(self, "_proc_vckey_at_req", None)
                if _rq is not None and int(seq) == int(_rq[0]):
                    self._proc_last_final_key = _rq[1]
            except Exception:
                exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3475")
                pass
        if same and not _stale_scene and not _stale_data:
            try:
                import os as _osd
                if _osd.environ.get("GGIS_RPROC_DEBUG"):
                    _vcx = getattr(self, "_vec_cache", None)
                    print("[主进程 _on_proc_frame 清 _dirty] final=%s same=%s "
                          "seq=%s stale_scene=%s stale_data=%s vc.done=%s "
                          "vec_pending=%s ｜ adv=%s tot=%s"
                          % (final, same, seq, _stale_scene, _stale_data,
                             getattr(_vcx, "get", lambda k: None)("done")
                             if isinstance(_vcx, dict) else None,
                             getattr(self, "_vector_pending", None),
                             getattr(_vcx, "get", lambda k: None)("adv")
                             if isinstance(_vcx, dict) else None,
                             getattr(_vcx, "get", lambda k: None)("tot")
                             if isinstance(_vcx, dict) else None),
                          flush=True)
            except Exception:
                exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3494")
                pass
            self._dirty = False
            self._interacting = False
            if final:
                try:
                    self._view_cache_put(img, self._frozen_render_extent)
                except Exception:
                    exc_note("_on_proc_frame @ ggis/render/map_canvas.py:3504")
                    pass
        self.update()

    def _ensure_frame_renderer(self):
        if _USE_PROC_RENDER and not self._edit_proc_block:
            return None

        if self._frame_renderer is None:
            try:
                from .async_frame import FrameRenderer
                r = FrameRenderer(self, self)
                r.rendered.connect(self._on_frame_rendered)
                self._frame_renderer = r
            except Exception:
                exc_note("_ensure_frame_renderer @ ggis/render/map_canvas.py:3541")
                import traceback
                traceback.print_exc()
                self._frame_renderer = None
        return self._frame_renderer

    def _bg_painters(self):
        if self._bg_qc is None:
            try:
                from .cpu.backend import GgsQcPainter
                self._bg_qc = GgsQcPainter()
            except Exception:
                exc_note("_bg_painters @ ggis/render/map_canvas.py:3557")
                import traceback
                traceback.print_exc()
                self._bg_qc = None
        if self._bg_ras is None:
            try:
                from .cpu.raster import GgsBuiltinRasterPainter
                self._bg_ras = GgsBuiltinRasterPainter()
            except Exception:
                exc_note("_bg_painters @ ggis/render/map_canvas.py:3565")
                import traceback
                traceback.print_exc()
                self._bg_ras = None
        if self._bg_tile is None:
            try:
                from .tiles import GgsTilePainter
                self._bg_tile = GgsTilePainter()
            except Exception:
                exc_note("_bg_painters @ ggis/render/map_canvas.py:3573")
                import traceback
                traceback.print_exc()
                self._bg_tile = None
        return self._bg_qc, self._bg_ras, self._bg_tile

    def _snapshot_for_render(self):
        return RenderTask.from_canvas(self).snapshot_dict()

    def _proc_vector_delegated(self):
        if not _USE_PROC_RENDER or self._proc_failed:
            return False
        if self._edit_proc_block:
            return False
        try:
            return (self._proc is not None and not self._proc.failed())
        except Exception:
            exc_note("_proc_vector_delegated @ ggis/render/map_canvas.py:3688")
            return False

    def _proc_settle_held(self):
        try:
            if not _USE_PROC_RENDER or self._proc_failed:
                return False
            if self._edit_proc_block:
                return False
            c = self._proc
            if c is None or c.failed():
                return False
            key = self._frame_identity()
            if key is None:
                return False
            return (getattr(self, "_proc_last_final_key", None) != key)
        except Exception:
            exc_note("_proc_settle_held @ ggis/render/map_canvas.py:3718")
            return False

    def _schedule_proc_warm_retry(self, in_flight=False):
        if self._proc_failed:
            return
        if self._proc_warm_retry is None:
            try:
                from PySide6.QtCore import QTimer
                t = QTimer(self)
                t.setSingleShot(True)
                t.setInterval(150)
                t.timeout.connect(self._on_proc_warm_retry)
                self._proc_warm_retry = t
            except Exception:
                exc_note("_schedule_proc_warm_retry @ ggis/render/map_canvas.py:3739")
                import traceback
                traceback.print_exc()
                self._proc_warm_retry = False
                return
        if self._proc_warm_retry is False:
            return
        if not in_flight:
            if self._proc_warm_retry_n >= 200:
                return
            self._proc_warm_retry_n += 1
        self._proc_warm_retry.start()

    def _on_proc_warm_retry(self):
        try:
            if getattr(self, "_proc_stopped", False):
                return
            if not (self._dirty
                    or self._vector_pending or self._raster_pending):
                return
            c = None
            try:
                c = self._proc_usable()
            except Exception:
                exc_note("_on_proc_warm_retry @ ggis/render/map_canvas.py:3764")
                c = None
            if c is None:
                if not self._proc_failed:
                    self._schedule_proc_warm_retry()
                return
            _req_seq = getattr(self, "_proc_req_seq", None)
            if _req_seq is not None:
                try:
                    _since = float(getattr(self, "_proc_req_since", 0.0) or 0.0)
                except Exception:
                    exc_note("_on_proc_warm_retry @ ggis/render/map_canvas.py:3790")
                    _since = 0.0
                try:
                    _age = time.monotonic() - _since
                except Exception:
                    exc_note("_on_proc_warm_retry @ ggis/render/map_canvas.py:3795")
                    _age = 0.0
                if _age < 5.0:
                    self._proc_warm_retry_n = 0
                    self._schedule_proc_warm_retry(in_flight=True)
                    return
            self._proc_warm_retry_n = 0
            self._proc_kick_count = int(
                getattr(self, "_proc_kick_count", 0)) + 1
            if self._proc_kick_count >= 40:
                try:
                    import logging as _lg_g
                    _lg_g.getLogger("gmagis").warning(
                        "[渲染] 自动重试 40 次仍未成功，停止补发；"
                        "下次交互将重新发起渲染")
                except Exception:
                    exc_note(
                        "_on_proc_warm_retry @ ggis/render/_render_director.py")
                return
            self._kick_render()
        except Exception:
            exc_note("_on_proc_warm_retry @ ggis/render/map_canvas.py:3772")
            import traceback
            traceback.print_exc()

    def _kick_render(self):
        try:
            if self._restore_cached_frame():
                return
        except Exception:
            exc_note("_kick_render @ ggis/render/map_canvas.py:3791")
            pass
        self._proc_stopped = False
        c = self._proc_usable()
        if c is not None:
            if self._edit_proc_block:
                self._edit_sync_features(c)
            try:
                if self._proc_push_tiles(c):
                    self._tile_gen += 1
            except Exception:
                exc_note("_kick_render @ ggis/render/map_canvas.py:3829")
                pass
            self._render_seq += 1
            seq = self._render_seq
            try:
                task = self._proc_task(seq)
                self._proc_seq = seq
                self._proc_scene_ver_at_req = (int(seq),
                                              int(self._proc_scene_ver or 0))
                self._proc_data_gen_at_req = (int(seq), int(self._data_gen))
                try:
                    from ..core.crs import crs_key
                    self._proc_crs_at_req = (
                        int(seq), str(crs_key(self.effectiveCrs()) or ""))
                except Exception:
                    exc_note("_kick_render @ ggis/render/map_canvas.py:3857")
                    self._proc_crs_at_req = None
                self._proc_vckey_at_req = (int(seq), self._frame_identity())
                if c.request(seq, task):
                    self._proc_warm_retry_n = 0
                    self._proc_kick_count = 0
                    self._warm_hold_logged = False
                    self._proc_req_seq = int(seq)
                    try:
                        self._proc_req_since = time.monotonic()
                    except Exception:
                        exc_note("_kick_render @ ggis/render/map_canvas.py:3910")
                        self._proc_req_since = 0.0
                    return True
            except Exception:
                exc_note("_kick_render @ ggis/render/map_canvas.py:3870")
                import traceback
                traceback.print_exc()
            self._proc_failed = True
            try:
                import logging as _lg_f
                _lg_f.getLogger("gmagis").warning(
                    "[渲染] 渲染请求未受理（子进程不可用），进入 %.0fs 冷却",
                    float(self._PROC_FAIL_COOLDOWN))
            except Exception:
                exc_note("_kick_render @ ggis/render/_render_director.py")
        if not self._edit_proc_block:
            # GPU 唯一后端：子进程未热/请求未受理时挂起渲染意图（dirty），
            # 定时重查子进程，热了自动补发渲染。不回退主线程渲染。
            self._dirty = True
            if self._proc_failed:
                _n = int(getattr(self, "_cool_kick_warn_n", 0)) + 1
                self._cool_kick_warn_n = _n
                if _n <= 3:
                    try:
                        import logging as _lg_c
                        _lg_c.getLogger("gmagis").warning(
                            "[渲染] 子进程冷却中，渲染请求挂起（第 %d 次留痕）",
                            _n)
                    except Exception:
                        exc_note(
                            "_kick_render @ ggis/render/_render_director.py")
            else:
                if not getattr(self, "_warm_hold_logged", False):
                    self._warm_hold_logged = True
                    try:
                        import logging as _lg_w
                        _lg_w.getLogger("gmagis").warning(
                            "[渲染] 子进程未热，渲染请求挂起待自动重试")
                    except Exception:
                        exc_note(
                            "_kick_render @ ggis/render/_render_director.py")
                self._schedule_proc_warm_retry(in_flight=True)

        if self._edit_proc_block:
            _stale = bool(getattr(self, "_bg_stale", False))
            if _stale:
                self._bg_stale = False
            r = None
            if not _stale:
                try:
                    r = self._ensure_frame_renderer()
                except Exception:
                    exc_note("_kick_render @ ggis/render/map_canvas.py:3895")
                    r = None
            if r is not None and not getattr(r, "last_error", ""):
                try:
                    self._render_seq += 1
                    seq = self._render_seq
                    qc, ras, tile = self._bg_painters()
                    task = self._snapshot_for_render()
                    task["qc"] = qc
                    task["ras"] = ras
                    task["qc_ras"] = ras
                    task["tile"] = tile
                    self._bg_task_ext = self._extent_snapshot()
                    self._bg_req_gen = self._edit_geo_gen
                    self._bg_data_gen_at_req = self._data_gen
                    if r.request(seq, task):
                        return True
                except Exception:
                    exc_note("_kick_render @ ggis/render/map_canvas.py:3920")
                    import traceback
                    traceback.print_exc()
        return False

    def _log_bg_error(self, text):
        try:
            import os
            root = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
            p = os.path.join(root, "build", "_async_render.log")
            with open(p, "a", encoding="utf-8") as f:
                f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        except Exception:
            exc_note("_log_bg_error @ ggis/render/map_canvas.py:3980")
            pass

    def _on_frame_rendered(self, img, seq):
        if seq != self._render_seq and not self._edit_proc_block:
            return
        if self._edit_proc_block and getattr(self, "_bg_stale", False):
            return
        if getattr(self, "_bg_req_gen", 0) != self._edit_geo_gen:
            return
        _bdg = getattr(self, "_bg_data_gen_at_req", None)
        if _bdg is not None and int(_bdg) != int(self._data_gen):
            return
        if img is None or img.isNull():
            return
        if self._panning:
            return
        _framed_ext = getattr(self, "_bg_task_ext", None)
        if self._edit_proc_block and _framed_ext is not None:
            self._commit_frame(img, _framed_ext, _framed_ext)
        else:
            self._commit_frame(img, self._extent_snapshot(),
                               self._extent.copy())
        self._dirty = False
        self._raster_pending = False
        self._vector_pending = False
        try:
            if (self._frozen_extent is not None
                    and self._frozen_extent == self._extent):
                self._view_cache_put(img, self._frozen_render_extent)
        except Exception:
            exc_note("_on_frame_rendered @ ggis/render/map_canvas.py:4067")
            pass
        self._blit(img)
        self.update()

    def _arm_render(self, immediate=False):
        if getattr(self, "_proc_stopped", False):
            return
        try:
            self._kick_render()
        except Exception:
            exc_note("_arm_render @ ggis/render/map_canvas.py")
            import traceback
            traceback.print_exc()



    def _scene_done(self):
        vc = self._vec_cache
        if vc is None or not vc.get("done"):
            return False
        return not (self._raster_pending or self._vector_pending)

    def _render_frame(self, show, base=None):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return None, True
        dpr = self._eff_dpr()
        img = QImage(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        if base is not None and not base.isNull():
            pb = QPainter(img)
            try:
                pb.drawImage(0, 0, base)
            finally:
                pb.end()
        else:
            img.fill(self._color)
        p = QPainter(img)
        try:
            if self._anti_alias:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            s = self._map_settings()
            budget = getattr(self, "_raster_budget_ms", None)
            if budget is None:
                budget = RASTER_FRAME_BUDGET_MS
            incomplete = self._paint_scene(p, s, raster_budget_ms=budget,
                                           vec_cache=True, with_overlay=False,
                                           with_selection=False,
                                           with_vector=(
                                               not self._proc_vector_delegated()))
        finally:
            p.end()
        _frame_empty = (self._proc_vector_delegated()
                        and not getattr(self, "_raster_drew", False))
        done = (not incomplete) and (not self._vector_pending)
        _settle_held = bool(done and self._proc_settle_held())
        if done and _settle_held:
            self._log_frame_reject("settle_held", -1, True)
            self._schedule_proc_warm_retry()
        elif done:
            self._raster_pending = False
            self._vector_pending = False
            self._dirty = False
        else:
            self._raster_pending = bool(incomplete)
            self._schedule_progressive()
        if done and not _settle_held and not _frame_empty:
            try:
                self._view_cache_put(img, self._extent.copy())
            except Exception:
                exc_note("_render_frame @ ggis/render/map_canvas.py:4764")
                pass
        if show and not _frame_empty:
            self._blit(img)
        return img, done

    def _scene_ver_now(self):
        try:
            from .cpu.render_proc import scene_version
        except Exception:
            exc_note("_scene_ver_now @ ggis/render/map_canvas.py:4799")
            return -1
        try:
            ver = int(scene_version(self._project,
                                    list(self._layer_source())))
        except Exception:
            exc_note("_scene_ver_now @ ggis/render/map_canvas.py:4804")
            return -1
        try:
            from ..core.crs import crs_key
            import zlib as _zlib
            _crs = str(crs_key(self.effectiveCrs()) or "")
            ver = int(ver) ^ (int(_zlib.crc32(_crs.encode("utf-8"))) << 20
                              | 0x1)
        except Exception:
            exc_note("_scene_ver_now @ ggis/render/map_canvas.py:4812")
            pass
        return ver

    def _vector_runs_plan(self, layers, settings=None):
        runs_key = []
        run_start = []
        run_end = []
        layer_run = [None] * len(layers)
        cur = []
        cur_start = 0
        for j, lyr in enumerate(layers):
            if lyr is None or not lyr.is_visible() or not lyr.is_valid():
                continue
            if settings is not None and not self._in_scale(lyr, settings):
                continue
            if lyr.is_vector():
                if not cur:
                    cur_start = j
                cur.append(str(lyr.id()))
                layer_run[j] = len(runs_key)
                continue
            if cur:
                runs_key.append(tuple(cur))
                run_start.append(cur_start)
                run_end.append(j - 1)
                cur = []
        if cur:
            runs_key.append(tuple(cur))
            run_start.append(cur_start)
            run_end.append(len(layers) - 1)
        return runs_key, run_start, run_end, layer_run

    def _paint_scene(self, p, s, with_labels=True, with_selection=True,
                     with_overlay=False, raster_budget_ms=None,
                     with_vector=True, vec_cache=False,
                     build_budget_ms=None, label_capped=True):
        try:
            ext = s.extent()
        except Exception:
            exc_note("_paint_scene @ ggis/render/map_canvas.py:5224")
            ext = self._extent
        if ext.is_empty():
            hint_rect = None
            try:
                sz = s.output_size()
                hint_rect = QRect(0, 0, int(sz.width()), int(sz.height()))
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5231")
                hint_rect = None
            self._draw_empty_hint(p, hint_rect)
            return
        if not s.is_ready():
            return

        t_raster0 = time.perf_counter() if raster_budget_ms else 0.0
        raster_incomplete = False
        raster_budget_out = False
        vector_deferred = False
        self._raster_drew = False
        use_vec_cache = bool(vec_cache) and with_vector
        vec_done = False
        vc_now = None
        valid = False
        old_flat_ids = {}
        vc_new = False
        runs = []
        run_end = []
        layer_run = []
        lv_layers = list(self._layer_source())
        if use_vec_cache:
            try:
                ext_now = s.extent()
                dpr_now = self._eff_dpr() or 1.0
                w_px = int(round(s.output_width() * dpr_now))
                h_px = int(round(s.output_height() * dpr_now))
                if _VEC_RUNS:
                    key_now, r_start, r_end, l_run = self._vector_runs_plan(
                        lv_layers, s)
                else:
                    ids = tuple(
                        str(l.id()) for l in lv_layers
                        if l is not None and l.is_visible()
                        and l.is_valid() and l.is_vector())
                    _n = len(lv_layers)
                    key_now = [ids] if ids else []
                    r_end = [_n] if ids else []
                    l_run = [
                        (0 if (l is not None and l.is_visible()
                               and l.is_valid() and l.is_vector()) else None)
                        for l in lv_layers]
                vc = self._vec_cache
                if getattr(self, "_vec_cache_dirty", False):
                    vc = None
                    self._vec_cache_dirty = False
                valid = (vc is not None
                         and vc.get("runs_key") == key_now
                         and vc["extent"] == ext_now
                         and abs(vc["dpr"] - dpr_now) <= 1e-6)
                if valid:
                    for _r in (vc.get("runs") or ()):
                        if (_r["img"].width() != w_px
                                or _r["img"].height() != h_px):
                            valid = False
                            break
                if valid:
                    runs = vc["runs"]
                    vc_now = vc
                    vec_done = bool(vc.get("done"))
                    if "flat_id" not in vc:
                        vc["flat_id"] = {}
                    old_flat_ids = vc.get("flat_id") or {}
                else:
                    new_runs = []
                    for _ids in key_now:
                        _img = QImage(
                            w_px, h_px,
                            QImage.Format.Format_ARGB32_Premultiplied)
                        _img.setDevicePixelRatio(dpr_now)
                        _img.fill(0)
                        new_runs.append({"ids": _ids, "img": _img, "p": None,
                                         "adv": {}, "tot": {},
                                         "done_lyr": {}, "done": False})
                    runs = new_runs
                    vc = {"img": (runs[0]["img"] if runs else None),
                          "runs": runs, "runs_key": key_now,
                          "extent": ext_now.copy(), "dpr": dpr_now,
                          "adv": {}, "tot": {}, "done_lyr": {}, "done": False,
                          "flat_id": {}}
                    self._vec_cache = vc
                    vc_new = True
                    vc_now = vc
                run_end, layer_run = r_end, l_run
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5357")
                runs = []
                run_end = []
                layer_run = []
                use_vec_cache = False
                vec_done = False
                vc_now = None
                vc_new = False

        def _blit_run(r):
            pp = r.get("p")
            if pp is not None:
                try:
                    pp.end()
                except Exception:
                    exc_note("_blit_run @ ggis/render/map_canvas.py:5378")
                    pass
                r["p"] = None
            try:
                p.drawImage(0, 0, r["img"])
            except Exception:
                exc_note("_blit_run @ ggis/render/map_canvas.py:5385")
                pass

        comp_next = 0
        for j, lyr in enumerate(lv_layers):
            while comp_next < len(runs) and run_end[comp_next] < j:
                _blit_run(runs[comp_next])
                comp_next += 1
            if (not lyr.is_visible() or not lyr.is_valid()
                    or not self._in_scale(lyr, s)):
                if lyr.is_tile():
                    _why = ("可见性" if not lyr.is_visible()
                            else ("有效性" if not lyr.is_valid()
                                  else "比例尺"))
                    _note_tile_skip(lyr, _why)
                continue
            if lyr.is_tile() or lyr.is_raster():
                if raster_budget_out:
                    raster_incomplete = True
                    continue
                if lyr.is_tile():
                    try:
                        self._tile_painter.draw(p, lyr, s)
                    except Exception:
                        exc_note("_paint_scene @ ggis/render/map_canvas.py:5420")
                        _note_tile_draw_error(lyr)
                else:
                    handled = False
                    if raster_backend() == "builtin":
                        try:
                            if self._qc_ras_painter.draw(p, lyr, s,
                                                         lyr.opacity()):
                                handled = True
                        except Exception:
                            exc_note("_paint_scene @ ggis/render/map_canvas.py:5432")
                            pass
                    if not handled:
                        try:
                            self._ras_painter.draw(p, lyr, s, lyr.opacity())
                        except Exception:
                            exc_note("_paint_scene @ ggis/render/map_canvas.py:5437")
                            pass
                self._raster_drew = True
                if (raster_budget_ms
                        and (time.perf_counter() - t_raster0) * 1000.0
                        >= raster_budget_ms):
                    raster_budget_out = True
                try:
                    import os as _os3
                    if _os3.environ.get("GGIS_RPROC_DEBUG"):
                        _st = getattr(self._qc_ras_painter, "stats", None) or {}
                        print("[绘制] 栅格 %-28r handled=%-5s opacity=%.2f "
                              "｜ 内置painter的why=%r"
                              % (lyr.name(), handled, float(lyr.opacity()),
                                 _st.get("why")), flush=True)
                except Exception:
                    exc_note("_paint_scene @ ggis/render/map_canvas.py:5465")
                    pass
                continue
            if not lyr.is_vector():
                continue
            if not with_vector:
                continue
            _ri = layer_run[j] if j < len(layer_run) else None
            _run = runs[_ri] if (_ri is not None
                                 and 0 <= _ri < len(runs)) else None
            if vec_done or (_run is not None
                            and _run["done_lyr"].get(id(lyr), False)):
                continue
            drawn = 0
            path_failed = False
            try:
                if vec_cache:
                    _bb = build_budget_ms
                    if _bb is None and not self._interacting:
                        _bb = _LOAD_BUILD_BUDGET_MS
                    self._qc_painter.begin_frame(_bb)
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5509")
                pass
            p_tgt = None
            if _run is not None:
                try:
                    p_tgt = _run.get("p")
                    if p_tgt is None:
                        p_tgt = QPainter(_run["img"])
                        _run["p"] = p_tgt
                except Exception:
                    exc_note("_paint_scene @ ggis/render/map_canvas.py:5530")
                    p_tgt = None
                    _run = None
            try:
                drawn = self._qc_painter.draw(
                    p_tgt if p_tgt is not None else p,
                    lyr, s, antialias=bool(self._anti_alias),
                    incremental=(p_tgt is not None),
                    reset_ring=vc_new)
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5540")
                drawn = 0
                path_failed = True
            try:
                _fid = getattr(self._qc_painter, "_ring_flat_id", None)
                if _fid is not None:
                    _lk = id(lyr)
                    if (valid
                            and old_flat_ids.get(_lk) is not None
                            and old_flat_ids.get(_lk) != _fid):
                        self._vec_cache_dirty = True
                        vector_deferred = True
                        if _run is not None:
                            _run["done_lyr"][_lk] = False
                    if vc_now is not None:
                        _fm = vc_now.get("flat_id")
                        if _fm is None:
                            _fm = {}
                            vc_now["flat_id"] = _fm
                        _fm[_lk] = _fid
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5564")
                pass
            deferred = 0
            try:
                deferred = int(self._qc_painter.end_frame())
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5569")
                deferred = 0
            if deferred:
                vector_deferred = True
            if p_tgt is not None and _run is not None:
                try:
                    adv = int(getattr(self._qc_painter, "_ring_adv", 0) or 0)
                    tot = int(getattr(self._qc_painter, "_ring_tot", 0) or 0)
                    key = id(lyr)
                    if tot >= 0:
                        _run["adv"][key] = _run["adv"].get(key, 0) + adv
                        _run["tot"][key] = tot
                        _run["done_lyr"][key] = (
                            _run["adv"][key] >= tot)
                    else:
                        _run["tot"][key] = -1
                        _run["done_lyr"][key] = False
                except Exception:
                    exc_note("_paint_scene @ ggis/render/map_canvas.py:5599")
                    pass
                try:
                    import os as _os4
                    if _os4.environ.get("GGIS_RPROC_DEBUG"):
                        print("[绘制] 矢量 %-24r drawn=%r deferred=%r 段=%r ｜ "
                              "adv=%r tot=%r done_lyr=%r"
                              % (lyr.name(), drawn, deferred,
                                 _run.get("ids"), _run.get("adv"),
                                 _run.get("tot"), _run.get("done_lyr")),
                              flush=True)
                except Exception:
                    exc_note("_paint_scene @ ggis/render/map_canvas.py:5613")
                    pass
            claimed = (drawn != 0) or deferred
            if not claimed and not path_failed:
                path_failed = True
            if not claimed and path_failed:
                try:
                    self._vec_painter.draw(
                        p_tgt if p_tgt is not None else p, lyr, s)
                    if p_tgt is not None and _run is not None:
                        _run["done_lyr"][id(lyr)] = True
                except Exception:
                    exc_note("_paint_scene @ ggis/render/map_canvas.py:5637")
                    continue

        while comp_next < len(runs):
            _blit_run(runs[comp_next])
            comp_next += 1

        if use_vec_cache and vc_now is not None:
            try:
                adv, tot, done_lyr = {}, {}, {}
                for _r in runs:
                    for _k, _v in _r["adv"].items():
                        adv[_k] = adv.get(_k, 0) + _v
                    tot.update(_r["tot"])
                    done_lyr.update(_r["done_lyr"])
                vc_now["adv"] = adv
                vc_now["tot"] = tot
                vc_now["done_lyr"] = done_lyr
                vc_now["done"] = (bool(done_lyr)
                                  and all(done_lyr.values())
                                  and not getattr(self, "_vec_cache_dirty",
                                                 False))
            except Exception:
                exc_note("_paint_scene @ ggis/render/map_canvas.py:5672")
                pass

        if with_labels:
            self._draw_labels(p, s, capped=label_capped)
        if with_selection:
            self._draw_selection(p, s)
        if with_overlay:
            self._draw_tool_overlay(p, s)
        self._vector_pending = bool(vector_deferred)
        return raster_incomplete

    def label_engine(self):
        return self._label_engine

    def labelsEnabled(self):
        return bool(self._labels_enabled)

    def setLabelsEnabled(self, on):
        self._labels_enabled = bool(on)
        self.update()

    def invalidate_edit(self, layer=None):
        if layer is not None:
            try:
                self._label_engine.invalidate(layer)
            except Exception:
                exc_note("invalidate_edit @ ggis/render/map_canvas.py:5719")
                pass
            try:
                invalidate_label_cache(layer)
            except Exception:
                exc_note("invalidate_edit @ ggis/render/map_canvas.py:5723")
                pass
            try:
                invalidate_caches(layer)
            except Exception:
                exc_note("invalidate_edit @ ggis/render/map_canvas.py:5731")
                pass
        self._bg_stale = True
        self._edit_geo_gen += 1
        self._sel_img = None
        self._sel_key = None
        self._refresh_scene(keep_frame=False)

    def invalidate_labels(self, layer=None):
        try:
            self._label_engine.invalidate(layer)
        except Exception:
            exc_note("invalidate_labels @ ggis/render/map_canvas.py:5758")
            pass
        if layer is not None:
            try:
                invalidate_label_cache(layer)
            except Exception:
                exc_note("invalidate_labels @ ggis/render/map_canvas.py:5763")
                pass
        try:
            self._hold_partial_begin()
        except Exception:
            exc_note("invalidate_labels @ ggis/render/map_canvas.py:5771")
            pass
        try:
            self._refresh_scene(keep_frame=True)
        except Exception:
            exc_note("invalidate_labels @ ggis/render/map_canvas.py:5775")
            self.update()

    def _label_jobs(self, settings=None):
        out = []
        for lyr in self._layer_source():
            try:
                if not lyr.is_vector() or not lyr.is_visible():
                    continue
                if settings is not None and not self._in_scale(lyr, settings):
                    continue
                st = get_label_style(lyr)
            except Exception:
                exc_note("_label_jobs @ ggis/render/map_canvas.py:5798")
                continue
            if st is None or not st.enabled or not st.field:
                continue
            out.append((lyr, st))
        return out

    def _draw_labels(self, painter, settings, capped=True, reuse_pan=None):
        if not self._labels_enabled:
            self._label_engine.reset_stats()
            return 0
        jobs = self._label_jobs(settings)
        if not jobs:
            self._label_engine.reset_stats()
            return 0
        try:
            _cap = LABEL_CANDIDATE_CAP if capped else None
            _budget = LABEL_CANDIDATE_BUDGET_MS if capped else None
            placed = self._label_engine.place(
                settings, jobs,
                budget_ms=_budget,
                candidate_cap=_cap,
                pan_reuse=reuse_pan)
        except Exception:
            exc_note("_draw_labels @ ggis/render/map_canvas.py:5831")
            self._label_engine.reset_stats()
            return 0
        if not placed:
            return 0
        try:
            return draw_labels(painter, placed)
        except Exception:
            exc_note("_draw_labels @ ggis/render/map_canvas.py:5838")
            return 0

    def refresh_layers(self):
        self._on_layers_changed()

    def _refresh_scene(self, keep_frame=False):
        if not keep_frame:
            self._clear_frozen(keep_preview=True)
            self.update()
        try:
            self.prewarm_flat()
        except Exception:
            exc_note("_refresh_scene @ ggis/render/map_canvas.py:6256")
            pass
        try:
            self._arm_render(immediate=True)
        except Exception:
            exc_note("_refresh_scene @ ggis/render/map_canvas.py:6260")
            import traceback
            traceback.print_exc()
            self.update()

    def _on_layers_changed(self):
        self._sel_img = None
        self._sel_key = None
        self._bump_data_gen()
        self._rebuild_symbols()
        keep = False
        try:
            now_seq = [id(l) for l in self._layer_source() if l.is_visible()]
            old_seq = self._last_visible_seq
            # keep = 帧可复用 ∧ 旧可见序列仍为新序列的子序列（纯追加图层）。
            # 帧可信度只看 _frozen 本身：CRS/渲染设置变化时 _refresh_scene 已
            # 自行清帧重渲，不需要作废基线——基线只跟图层序列绑定。
            frame_ok = bool(self._frozen is not None
                            and not self._frozen.isNull())
            if (frame_ok and old_seq is not None
                    and len(old_seq) <= len(now_seq)):
                _it = iter(now_seq)
                keep = all(any(x == y for y in _it) for x in old_seq)
            self._last_visible_seq = now_seq
        except Exception:
            exc_note("_on_layers_changed @ ggis/render/map_canvas.py:6294")
            keep = False
        self._refresh_scene(keep_frame=keep)
        try:
            r = self._ensure_frame_renderer()
            if r is not None:
                r.warmup()
        except Exception:
            exc_note("_on_layers_changed @ ggis/render/map_canvas.py:6310")
            pass
        self._emit_scale()

    def release_buffers(self):
        try:
            r = self._frame_renderer
            if r:
                r.stop()
        except Exception:
            exc_note("release_buffers @ ggis/render/map_canvas.py:6461")
            pass
        self._frame_renderer = None
        try:
            c = self._proc
            if c is not None:
                c.stop()
        except Exception:
            exc_note("release_buffers @ ggis/render/map_canvas.py:6470")
            pass
        self._proc = None
        self._clear_frozen()

    def shutdown_render(self):
        try:
            s = self._sel
            if s is not None:
                s.dispose()
        except Exception:
            exc_note("shutdown_render @ ggis/render/map_canvas.py:6487")
            pass
        self.release_buffers()
