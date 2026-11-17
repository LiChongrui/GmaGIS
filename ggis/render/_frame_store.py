# -*- coding: utf-8 -*-

from ._canvas_cfg import (
    _CAUSE_PAN_END,
    _COV_TO_VIEW_ERR_N,
    _FROZEN_MARGIN,
    _FROZEN_SCALE_THRESHOLD,
    _FrameRef,
    _PHASE_SETTLING,
    _USE_FROZEN_MARGIN,
    _VIEW_CACHE_BYTES,
    _VIEW_CACHE_MAX,
    _ZOOM_IN_BLIT_ONLY,
    frame_target_rect,
)
from ggis.core.crs.extent import GgsRectangle
from PySide6.QtGui import QColor, QImage, QPainter

from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from ggis.common.util.exc_report import exc_note
import time


class FrameStoreMixin:


    def paintEvent(self, e):
        self._painting = True
        try:
            self._paint(e)
        finally:
            self._painting = False
        try:
            if getattr(self._proc, "gpu_active", False):
                self._proc.sync_viewport()
        except Exception:
            exc_note("paintEvent @ ggis/render/map_canvas.py:2356")
            pass

    def _paint(self, e):
        self._paint_event(e)
        self._paint_selection_overlay()
        self._paint_tool_overlay()
        self._paint_box_zoom()

    def _paint_phase(self):
        if self._panning and self.frame.usable:
            return "pan_preview"
        if self._is_frozen():
            return "frozen_preview"
        if self._should_paint_cached():
            return "cached"
        return "progressive"

    def _paint_event(self, e):
        self._ensure_render_poll()
        _proc = getattr(self, "_proc", None)
        if (_proc is not None
                and getattr(_proc, "backend_type", "") == "gpu_tile"
                and getattr(_proc, "failed", lambda: False)()):
            self._paint_gpu_error_overlay(
                getattr(_proc, "fail_reason", "") or "GPU 渲染初始化失败")
            return
        if getattr(self, "_proc_failed", False):
            self._paint_gpu_error_overlay("GPU 后端构造异常（详见日志）")
            return
        if self.width() <= 0 or self.height() <= 0:
            return
        phase = self._paint_phase()

        if phase == "pan_preview":
            self._paint_scaled()
            return

        if phase == "frozen_preview":
            self._paint_scaled()
            return

        if phase == "cached":
            self._paint_scaled()
            return

        _delegate = self._proc_vector_delegated()
        _show = (not _delegate) or self._frozen is None \
            or self._frozen.isNull()
        if not _show:
            self._paint_scaled()
        img, _ = self._render_frame(show=_show)
        if img is not None and not img.isNull() and _show:
            self._commit_frame(img, self._extent_snapshot(),
                               self._extent.copy())

    def _has_visible_raster(self):
        try:
            for lyr in self._layer_source():
                try:
                    if lyr.is_raster() and lyr.is_visible():
                        return True
                except Exception:
                    exc_note("_has_visible_raster @ ggis/render/map_canvas.py:2743")
                    continue
        except Exception:
            exc_note("_has_visible_raster @ ggis/render/map_canvas.py:2745")
            return True
        return False

    @property
    def frame(self):
        return _FrameRef(
            getattr(self, "_frozen", None),
            getattr(self, "_frozen_extent", None),
            getattr(self, "_frozen_render_extent", None),
            getattr(self, "_frozen_done", False))

    def _is_frozen(self):
        return (bool(self._dirty)
                and bool(self._interacting)
                and bool(self._frozen_done)
                and self._frozen is not None
                and not self._frozen.isNull())

    def _should_paint_cached(self):
        return (not self._dirty
                and self._frozen_done
                and not (self._raster_pending or self._vector_pending)
                and self._frozen is not None
                and not self._frozen.isNull())

    def _blit(self, img):
        if img is None or img.isNull():
            return
        if not self._painting:
            self.update()
            return
        p = QPainter(self)
        try:
            p.drawImage(0, 0, img)
        finally:
            p.end()

    def _extent_snapshot(self):
        try:
            return None if self._extent.is_empty() else self._extent.copy()
        except Exception:
            exc_note("_extent_snapshot @ ggis/render/map_canvas.py:4382")
            return None

    def _cov_for(self, ext):
        try:
            if not _USE_FROZEN_MARGIN or ext is None or ext.is_empty():
                return ext
            return ext.copy().grow(_FROZEN_MARGIN)
        except Exception:
            exc_note("_cov_for @ ggis/render/map_canvas.py:4394")
            return ext

    def _cov_size_for(self, w, h):
        try:
            if not _USE_FROZEN_MARGIN:
                return int(max(1, round(w))), int(max(1, round(h)))
            f = 1.0 + 2.0 * _FROZEN_MARGIN
            return int(max(1, round(w * f))), int(max(1, round(h * f)))
        except Exception:
            exc_note("_cov_size_for @ ggis/render/map_canvas.py:4405")
            return int(max(1, round(w))), int(max(1, round(h)))

    def _cov_to_view(self, cov):
        try:
            if cov is None or cov.is_empty():
                return cov
            if not _USE_FROZEN_MARGIN:
                return cov.copy()
            cx, cy = cov.x_center(), cov.y_center()
            f = 1.0 + 2.0 * _FROZEN_MARGIN
            vw = max(cov.width() / f, 1e-12)
            vh = max(cov.height() / f, 1e-12)
            return GgsRectangle(cx - vw / 2.0, cy - vh / 2.0,
                                cx + vw / 2.0, cy + vh / 2.0)
        except Exception:
            global _COV_TO_VIEW_ERR_N
            try:
                _COV_TO_VIEW_ERR_N += 1
            except NameError:
                exc_note("_cov_to_view @ ggis/render/map_canvas.py:4443")
                _COV_TO_VIEW_ERR_N = 1
            if _COV_TO_VIEW_ERR_N <= 3:
                try:
                    import logging as _lg
                    _lg.getLogger("gmagis").exception(
                        "[_cov_to_view] 反推视口失败（返回 cov 原样，"
                        "same 判据将恒假）cov=%r", cov)
                except Exception:
                    exc_note("_cov_to_view @ ggis/render/map_canvas.py:4451")
                    pass
            return cov.copy() if cov is not None else None

    @property
    def _frozen_fe(self):
        try:
            re_ = self._frozen_render_extent
            if re_ is not None and not re_.is_empty():
                return re_
        except Exception:
            exc_note("_frozen_fe @ ggis/render/map_canvas.py:4480")
            pass
        return self._cov_for(self._frozen_extent)

    def _frozen_covers(self, ext):
        try:
            if self._frozen is None or self._frozen.isNull():
                return False
            cov, view = self._frozen_fe, self._frozen_extent
            if cov is None or view is None or ext is None or ext.is_empty():
                return False
            if not cov.contains(ext):
                return False
            vw = max(float(view.width()), 1e-12)
            ew = max(float(ext.width()), 1e-12)
            ratio = ew / vw
            if ratio > _FROZEN_SCALE_THRESHOLD \
                    or ratio < (1.0 / _FROZEN_SCALE_THRESHOLD):
                return False
            return True
        except Exception:
            exc_note("_frozen_covers @ ggis/render/map_canvas.py:4506")
            return False

    def _make_scaled(self, buf, fe, ex, transparent=False):
        if buf is None or buf.isNull() or fe is None or ex is None:
            return None
        try:
            if fe.is_empty() or ex.is_empty():
                return None
            dpr = float(buf.devicePixelRatio() or 1.0)
            w, h = max(1, self.width()), max(1, self.height())
            out = QImage(max(1, int(round(w * dpr))),
                         max(1, int(round(h * dpr))),
                         QImage.Format.Format_ARGB32_Premultiplied)
            out.setDevicePixelRatio(dpr)
            out.fill(Qt.GlobalColor.transparent if transparent else self._color)
            x, y, sw, sh = frame_target_rect(fe, ex, w, h)
            p = QPainter(out)
            try:
                p.drawImage(QRectF(float(x), float(y),
                                   float(sw), float(sh)), buf)
            finally:
                p.end()
            return out
        except Exception:
            exc_note("_make_scaled @ ggis/render/map_canvas.py:4557")
            return None

    def _is_zooming_in(self):
        try:
            fe = self._frozen_extent
            if fe is None or fe.is_empty():
                return False
            return float(self._extent.width()) < float(fe.width())
        except Exception:
            exc_note("_is_zooming_in @ ggis/render/map_canvas.py:4572")
            return False

    def _paint_scaled(self):
        if self._frozen is None or self._frozen.isNull():
            return
        if _ZOOM_IN_BLIT_ONLY and self._is_zooming_in():
            self._blit(self._frozen)
            return
        out = self._make_scaled(self._frozen, self._frozen_fe, self._extent)
        if out is not None:
            self._blit(out)
        else:
            self._blit(self._frozen)

    def _freeze_scrolled(self):
        self._cause = _CAUSE_PAN_END
        self._phase = _PHASE_SETTLING
        try:
            if self._frozen_covers(self._extent):
                self._interacting = False
                self._dirty = False
                self.update()
                return
        except Exception:
            exc_note("_freeze_scrolled @ ggis/render/map_canvas.py:4635")
            pass
        self._interacting = False
        self._hold_partial_begin()
        self._dirty = True
        self._arm_render(immediate=True)

    def _frame_identity(self):
        """帧内容身份：决定这一帧画面是什么，不含自激的 tile_gen。

        栅格/瓦片/矢量三类图层的真实内容变化分别经 scene_ver /
        data_gen / geo_gen / extent 汇入这里；在线瓦片像素到达只 bump
        tile_gen（缓存键用），不进身份，因此不会否定已渲染的 final 帧。
        供 _proc_vckey_at_req 与 _proc_settle_held 共用，口径一致。
        """
        try:
            k = self._view_cache_key()
            if k is None:
                return None
            # k = (ext, w, h, dpr, scene_ver, crs, tile_gen, data_gen)
            # 去掉索引 6 的 tile_gen；追加编辑几何世代
            return (k[0], k[1], k[2], k[3], k[4], k[5], k[7],
                    int(getattr(self, "_edit_geo_gen", 0)))
        except Exception:
            exc_note("_frame_identity @ ggis/render/_frame_store.py")
            return None

    def _view_cache_key(self):
        try:
            e = self._extent
            if e is None or e.is_empty():
                return None
            ext = (round(float(e.xmin), 6), round(float(e.ymin), 6),
                   round(float(e.xmax), 6), round(float(e.ymax), 6))
            dpr = self._eff_dpr()
            from ..core.crs import crs_key
            return (ext, int(self.width()), int(self.height()),
                    round(dpr, 3), int(self._scene_ver_now()),
                    str(crs_key(self.effectiveCrs()) or ""),
                    int(getattr(self, "_tile_gen", 0)),
                    int(getattr(self, "_data_gen", 0)))
        except Exception:
            exc_note("_view_cache_key @ ggis/render/map_canvas.py:4847")
            return None

    def _view_cache_get(self):
        if _VIEW_CACHE_MAX <= 0:
            return None
        key = self._view_cache_key()
        if key is None:
            return None
        val = self._view_cache.get(key)
        hit_key = key if val is not None else None
        if val is None:
            hit_key, val = self._view_cache_get_covering(key)
        if val is None or hit_key is None:
            return None
        img, fe = val
        try:
            if img.isNull():
                self._view_cache.pop(hit_key, None)
                return None
        except Exception:
            exc_note("_view_cache_get @ ggis/render/map_canvas.py:4864")
            self._view_cache.pop(hit_key, None)
            return None
        self._view_cache.pop(hit_key, None)
        self._view_cache[hit_key] = val
        return img, fe, (hit_key == key)

    def _view_cache_get_covering(self, key):
        try:
            ext = self._extent
            if ext is None or ext.is_empty():
                return None, None
            rest = key[1:]
            for k in reversed(list(self._view_cache.keys())):
                if k[1:] != rest:
                    continue
                cand = self._view_cache.get(k)
                if not cand:
                    continue
                try:
                    img, fe = cand
                    if img is None or img.isNull():
                        continue
                    if fe is None or fe.is_empty() or not fe.contains(ext):
                        continue
                    kw = max(float(k[0][2]) - float(k[0][0]), 1e-12)
                    ratio = max(float(ext.width()), 1e-12) / kw
                    if (ratio > _FROZEN_SCALE_THRESHOLD
                            or ratio < 1.0 / _FROZEN_SCALE_THRESHOLD):
                        continue
                except Exception:
                    exc_note("_view_cache_get_covering @ _frame_store.py")
                    continue
                return k, cand
        except Exception:
            exc_note("_view_cache_get_covering @ _frame_store.py")
        return None, None

    def _view_cache_put(self, img, fe=None):
        if _VIEW_CACHE_MAX <= 0 or img is None:
            return
        try:
            if img.isNull():
                return
        except Exception:
            exc_note("_view_cache_put @ ggis/render/map_canvas.py:4883")
            return
        key = self._view_cache_key()
        if key is None:
            return
        self._view_cache[key] = (img, fe)
        def _total():
            t = 0
            for im, _fe in self._view_cache.values():
                try:
                    t += int(im.width()) * int(im.height()) * 4
                except Exception:
                    exc_note("_total @ ggis/render/map_canvas.py:4895")
                    pass
            return t
        while self._view_cache and (
                _total() > _VIEW_CACHE_BYTES
                or len(self._view_cache) > _VIEW_CACHE_MAX):
            oldest = next(iter(self._view_cache))
            self._view_cache.pop(oldest, None)

    def _commit_frame(self, img, view_extent, fe_extent):
        self._frozen = img
        self._frozen_extent = view_extent
        self._frozen_render_extent = fe_extent
        self._frozen_done = True

    def _restore_cached_frame(self):
        got = self._view_cache_get()
        if got is None:
            return False
        img, fe, exact = got
        ve = self._extent_snapshot()
        fe_ok = fe if (fe is not None and not fe.is_empty()) \
            else self._cov_for(ve)
        self._commit_frame(img, ve, fe_ok)
        self._dirty = False
        self._interacting = False
        self._hold_partial_frames = False
        self._proc_seq = None
        self._proc_req_seq = None
        self.update()
        # 只有「同视野」缓存帧才是最终画面。覆盖命中（用更大范围的旧帧
        # 拉伸到当前视野）只能当过渡预览：必须让 _kick_render 继续发
        # final 请求，否则停手后会一直停在拉伸的模糊旧帧上。
        return bool(exact)

    def _clear_frozen(self, keep_preview=False):
        if keep_preview:
            self._dirty = False
            self._interacting = False
            if self._frozen is None or self._frozen.isNull():
                keep_preview = False
        if not keep_preview:
            self._frozen = None
            self._frozen_done = False
            self._frozen_extent = None
            self._frozen_render_extent = None
            self._dirty = False
            self._interacting = False
        self._hold_partial_frames = False
        self._render_seq += 1
        try:
            r = self._frame_renderer
            if r:
                r.invalidate()
        except Exception:
            exc_note("_clear_frozen @ ggis/render/map_canvas.py:5076")
            pass
        self._vec_cache = None
        self._view_cache.clear()
        try:
            if getattr(self, "_ras_painter", None) is not None:
                self._ras_painter.invalidate()
        except Exception:
            exc_note("_clear_frozen @ ggis/render/map_canvas.py:5097")
            pass
        try:
            if getattr(self, "_qc_ras_painter", None) is not None:
                self._qc_ras_painter.invalidate()
        except Exception:
            exc_note("_clear_frozen @ ggis/render/map_canvas.py:5106")
            pass
        try:
            if getattr(self, "_bg_ras", None) is not None:
                self._bg_ras.invalidate()
        except Exception:
            exc_note("_clear_frozen @ ggis/render/map_canvas.py:5111")
            pass
