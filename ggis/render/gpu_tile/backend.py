# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note
from .._canvas_cfg import frame_target_rect

import logging
import os
import time

from PySide6.QtCore import Qt, QRectF, QPointF, QEvent
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QImage, QSurfaceFormat,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from ..cpu.render_proc import RenderClient
from .. import tile_atlas as TA
from ..backend import RenderBackend


class _TileCompositor(QOpenGLWidget):

    def __init__(self, host, backend):
        super().__init__(host)
        self._host = host
        self._backend = backend
        try:
            fmt = QSurfaceFormat()
            fmt.setVersion(2, 1)
            fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
            fmt.setDepthBufferSize(24)
            fmt.setStencilBufferSize(8)
            fmt.setSamples(0)
            self.setFormat(fmt)
        except Exception:
            exc_note("__init__ @ ggis/render/gpu_tile/backend.py:31")
            pass
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoFillBackground(False)
        self._pm = None
        self._pm_id = None
        self._pm_dpr = 1.0
        self._trace_last = (None, 0.0)

    def _trace(self, state):
        if not os.environ.get("GGIS_GPU_TRACE"):
            return
        now = time.perf_counter()
        if state == self._trace_last[0] and now - self._trace_last[1] < 0.5:
            return
        self._trace_last = (state, now)
        try:
            logging.getLogger("gmagis").info("[GPU] %r", (state,))
        except Exception:
            exc_note("_trace @ ggis/render/gpu_tile/backend.py:94")
            pass

    def paintGL(self):
        host = self._host
        try:
            bg = host._color
        except Exception:
            exc_note("paintGL @ ggis/render/gpu_tile/backend.py:101")
            bg = QColor(255, 255, 255)
        p = QPainter(self)
        try:
            p.fillRect(self.rect(), bg)

            img = host._frozen
            fe = host._frozen_fe
            fe_view = host._frozen_extent
            ex = host._extent
            _steady = False
            if (not host._panning) and ex is not None and fe_view is not None:
                try:
                    _steady = bool(fe_view == ex)
                except Exception:
                    exc_note("paintGL @ ggis/render/gpu_tile/backend.py:125")
                    _steady = False
            if _steady and self._backend._draw_tiles(p, host):
                self._trace(("tiles", host._panning, self._pm_id))
                pass
            elif img is not None and not img.isNull() and fe is not None \
                    and ex is not None and not getattr(ex, "is_empty", lambda: False)():
                fid = id(img)
                if fid != self._pm_id:
                    self._pm = QPixmap.fromImage(img)
                    if self._pm is None or self._pm.isNull():
                        self._pm = None
                        self._trace(("pm-null", fid, img.width(),
                                     img.height()))
                    else:
                        self._pm_id = fid
                    try:
                        self._pm_dpr = float(img.devicePixelRatio() or 1.0)
                    except Exception:
                        exc_note("paintGL @ ggis/render/gpu_tile/backend.py:151")
                        self._pm_dpr = 1.0
                pm = self._pm
                if pm is None:
                    return
                dpr = self._pm_dpr
                lw = max(1, pm.width() / dpr)
                lh = max(1, pm.height() / dpr)
                w = max(1, host.width())
                h = max(1, host.height())
                try:
                    same = bool(fe == ex)
                except Exception:
                    exc_note("paintGL @ ggis/render/gpu_tile/backend.py:164")
                    same = False
                if same or (self._backend._zoom_in_blit
                            and host._is_zooming_in()):
                    p.drawPixmap(QPointF(0.0, 0.0), pm)
                    self._trace(("same", fid, lw, lh))
                else:
                    x, y, sw, sh = frame_target_rect(fe, ex, w, h)
                    p.drawPixmap(QRectF(x, y, sw, sh), pm,
                                 QRectF(0, 0, pm.width(), pm.height()))
                    self._trace(("scaled", fid, round(x), round(y),
                                 round(sw), round(sh)))
            else:
                self._trace(("blank", host._panning,
                             id(host._frozen),
                             None if fe is None else
                             (round(fe.xmin), round(fe.ymin),
                              round(fe.xmax), round(fe.ymax))))

            try:
                s = host._map_settings()
                if not s.is_ready():
                    s = None
            except Exception:
                exc_note("paintGL @ ggis/render/gpu_tile/backend.py:209")
                s = None
            if s is not None:
                _fe = host._frozen_fe
                _ex = host._extent
                _w = max(1, host.width())
                _h = max(1, host.height())
                _fz = host._frozen
                _fz_ok = bool(_fz is not None and not _fz.isNull())
                try:
                    _same = bool(_fe == _ex)
                except Exception:
                    exc_note("paintGL @ ggis/render/gpu_tile/backend.py:227")
                    _same = False
                _in_blit = (_same
                            or (self._backend._zoom_in_blit
                                and host._is_zooming_in()))
                _scaled = (not _in_blit) and _fz_ok
                if _fz_ok and _fe is not None:
                    _sel_ext = _fe
                    _fd = float(_fz.devicePixelRatio() or 1.0) or 1.0
                    _ov_w = max(1, int(round(_fz.width() / _fd)))
                    _ov_h = max(1, int(round(_fz.height() / _fd)))
                else:
                    _sel_ext = host._extent_snapshot()
                    _ov_w, _ov_h = _w, _h
                _sel_ext4 = None
                try:
                    if _sel_ext is not None:
                        _sel_ext4 = _sel_ext.as_tuple()
                except Exception:
                    exc_note("paintGL @ ggis/render/gpu_tile/backend.py:240")
                    _sel_ext4 = None
                try:
                    _ov = None
                    if _sel_ext4 is not None:
                        try:
                            _ov_dpr = float(host.devicePixelRatioF()) or 1.0
                            _ov = host._selection_overlay(
                                _sel_ext4, _ov_w, _ov_h, _ov_dpr)
                        except Exception:
                            import logging as _lg_s
                            import traceback as _tb_s
                            try:
                                _lg_s.getLogger("gmagis").error(
                                    "[GPU] _selection_overlay 异常：\n%s",
                                    _tb_s.format_exc())
                            except Exception:
                                exc_note("paintGL @ ggis/render/gpu_tile/backend.py:264")
                                pass
                            _ov = None
                    if _ov is not None and not _ov.isNull():
                        p.save()
                        try:
                            p.setRenderHint(
                                QPainter.RenderHint.SmoothPixmapTransform,
                                True)
                            if (_scaled and _fe is not None
                                    and _ex is not None):
                                _x, _y, _sw, _sh = frame_target_rect(
                                    _fe, _ex, _w, _h)
                                p.translate(_x, _y)
                                if _w and _h and _sw and _sh:
                                    p.scale(_sw / _w, _sh / _h)
                            p.drawImage(
                                QRectF(0.0, 0.0, float(_w), float(_h)),
                                _ov,
                                QRectF(0.0, 0.0, float(_ov.width()),
                                       float(_ov.height())))
                        finally:
                            p.restore()
                except Exception:
                    import logging as _lg_s
                    import traceback as _tb_s
                    try:
                        _lg_s.getLogger("gmagis").error(
                            "[GPU] 选择高亮贴图异常：\n%s",
                            _tb_s.format_exc())
                    except Exception:
                        exc_note("paintGL @ ggis/render/gpu_tile/backend.py:308")
                        pass
                try:
                    _dpr = 1.0
                    try:
                        _dpr = float(host.devicePixelRatioF()) or 1.0
                    except Exception:
                        exc_note("paintGL @ ggis/render/gpu_tile/backend.py:327")
                        _dpr = 1.0
                    _tw = max(1, int(round(host.width() * _dpr)))
                    _th = max(1, int(round(host.height() * _dpr)))
                    _ti = QImage(_tw, _th,
                                 QImage.Format.Format_ARGB32_Premultiplied)
                    _ti.setDevicePixelRatio(_dpr)
                    _ti.fill(Qt.GlobalColor.transparent)
                    _tp = QPainter(_ti)
                    try:
                        _tp.setRenderHint(
                            QPainter.RenderHint.Antialiasing, True)
                        host._draw_tool_overlay(_tp, s)
                    finally:
                        _tp.end()
                    p.drawImage(0.0, 0.0, _ti)
                except Exception:
                    try:
                        host._draw_tool_overlay(p, s)
                    except Exception:
                        import logging as _lg_t
                        import traceback as _tb_t
                        try:
                            _lg_t.getLogger("gmagis").error(
                                "[GPU] _draw_tool_overlay 异常：\n%s",
                                _tb_t.format_exc())
                        except Exception:
                            exc_note("paintGL @ ggis/render/gpu_tile/backend.py:355")
                            pass

            try:
                if getattr(host, "_box_zoom_on", False) \
                        and host._box_p0 is not None \
                        and host._box_p1 is not None:
                    r = QRectF(QPointF(host._box_p0),
                               QPointF(host._box_p1)).normalized()
                    if r.width() >= 2 and r.height() >= 2:
                        p.setPen(QPen(QColor(40, 120, 220), 1,
                                      Qt.PenStyle.DashLine))
                        p.setBrush(QBrush(QColor(40, 120, 220, 40)))
                        p.drawRect(r)
            except Exception:
                exc_note("paintGL @ ggis/render/gpu_tile/backend.py:370")
                pass
        except Exception:
            import logging as _lg
            import traceback as _tb
            try:
                _lg.getLogger("gmagis").error(
                    "[GPU] paintGL 异常，关闭 GL 合成层退回 2D：\n%s",
                    _tb.format_exc())
            except Exception:
                exc_note("paintGL @ ggis/render/gpu_tile/backend.py:382")
                pass
            try:
                self._backend._disable_gpu()
            except Exception:
                exc_note("paintGL @ ggis/render/gpu_tile/backend.py:386")
                pass
        finally:
            p.end()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.WindowStateChange:
            try:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._backend.sync_viewport)
            except Exception:
                exc_note("changeEvent @ ggis/render/gpu_tile/backend.py:400")
                pass


class GpuTileBackend(RenderBackend):

    backend_type = "gpu_tile"

    def __init__(self, host, multi_worker=False):
        super().__init__()
        self._host = host
        self._failed = False
        self._fail_reason = ""
        self._gpu_ok = False
        self._client = None
        self._gl = None
        self._zoom_in_blit = False
        self._last_key = None
        self._show_pending = False
        self._pending_geo = None
        self._store = TA.TileStore()
        self._atlas = {}
        self._pmc = {}
        self._pmc_gen = -1
        self._tiles_drawn = 0
        try:
            import importlib
            _mod = importlib.import_module(type(host).__module__)
            self._zoom_in_blit = bool(
                getattr(_mod, "_ZOOM_IN_BLIT_ONLY", False))
        except Exception:
            exc_note("__init__ @ ggis/render/gpu_tile/backend.py:449")
            self._zoom_in_blit = False

        try:
            self._client = RenderClient(host)
            self._client.rendered.connect(
                self._on_client_frame, Qt.QueuedConnection)
        except Exception:
            exc_note("__init__ @ ggis/render/gpu_tile/backend.py:462")
            import traceback
            traceback.print_exc()
            self._failed = True
            self._fail_reason = "RenderClient 子进程客户端初始化异常"
            return

        try:
            gl = _TileCompositor(host, self)
            _aw, _ah = self._gl_geo(host.width(), host.height())
            gl.setGeometry(0, 0, _aw, _ah)
            self._gl = gl
            self._gpu_ok = True
        except Exception:
            exc_note("__init__ @ ggis/render/gpu_tile/backend.py:478")
            import traceback
            traceback.print_exc()
            self._failed = True
            self._fail_reason = "QOpenGLWidget 合成层创建失败（GL 上下文不可用？）"
            self._gpu_ok = False
            self._gl = None


    def _tile_gpu_on(self):
        try:
            from ggis.core.app import settings as _S
            return bool(_S.get("vector_tile_gpu", False))
        except Exception:
            exc_note("_tile_gpu_on @ ggis/render/gpu_tile/backend.py:501")
            return False

    def _scene_ver(self):
        try:
            return int(getattr(self._client, "_scene_ver", 0) or 0)
        except Exception:
            exc_note("_scene_ver @ ggis/render/gpu_tile/backend.py:508")
            return 0

    def _viewport_tiles(self, task, margin=0.35):
        ext = task["extent"]
        w = float(task["size"][0])
        h = float(task["size"][1])
        x0, y0, x1, y1 = (float(ext[0]), float(ext[1]),
                          float(ext[2]), float(ext[3]))
        ew = (x1 - x0) or 1.0
        eh = (y1 - y0) or 1.0
        m = float(margin)
        mx, my = ew * m, eh * m
        e2 = (x0 - mx, y0 - my, x1 + mx, y1 + my)
        mupp = max(ew / (w or 1.0), eh / (h or 1.0))
        lvl = TA.level_of(mupp)
        want = TA.visible_tiles(e2, w * (1.0 + 2.0 * m),
                                h * (1.0 + 2.0 * m), mupp, lvl, (0.0, 0.0))
        sx_ppu = w / ew
        sy_ppu = h / eh
        out = []
        for tid, tr, _a, _b, _c, _d in want:
            tx0, ty0, tx1, ty1 = tr
            out.append((tid, tr,
                        (tx0 - x0) * sx_ppu, (y1 - ty1) * sy_ppu,
                        (tx1 - tx0) * sx_ppu, (ty1 - ty0) * sy_ppu))
        return lvl, out

    def request(self, seq, task):
        if not self._tile_gpu_on():
            return self._client.request(seq, task)
        return self._request_tiled(seq, task)

    def _request_tiled(self, seq, task):
        try:
            dpr = float(task.get("dpr") or 1.0)
            sv = self._scene_ver()
            self._store.bind(sv, dpr)
            _lvl, want = self._viewport_tiles(task)
            if not want or len(want) > TA.MAX_TILES_PER_VIEW:
                return self._client.request(seq, task)
            miss = self._store.missing(want, sv, dpr)
            if not miss:
                self._emit_composed(seq, task, dpr)
                return True
            if len(miss) > TA.MAX_TILES_PER_ATLAS:
                return self._client.request(seq, task)
            pairs = [(t[0], TA.TILE_PX, TA.TILE_PX) for t in miss]
            batches = TA.atlas_layout(pairs, 1.0)
            if not batches:
                return self._client.request(seq, task)
            AW, AH, places = batches[0]
            by_tid = {t[0]: t[1] for t in want}
            tiles = []
            for tid, px, py, pw, ph in places:
                tr = by_tid.get(tid)
                if tr is None:
                    continue
                tiles.append((tid, tr, px, py, pw, ph))
            if not tiles:
                return self._client.request(seq, task)
            at = dict(task)
            at["size"] = (int(AW), int(AH))
            at["dpr"] = 1.0
            at["tiles"] = tiles
            self._atlas[int(seq)] = {"seq": int(seq), "dpr": 1.0,
                                     "places": [(t[0], t[2], t[3], t[4], t[5])
                                                for t in tiles],
                                     "orig": task}
            return self._client.request(seq, at)
        except Exception:
            exc_note("_request_tiled @ ggis/render/gpu_tile/backend.py:604")
            import traceback
            traceback.print_exc()
            self._atlas.pop(int(seq), None)
            return self._client.request(seq, task)

    def _emit_composed(self, seq, task, dpr, sv=None):
        from PySide6.QtCore import QRectF, QTimer
        from PySide6.QtGui import QColor, QImage, QPainter

        def _do():
            try:
                w = float(task["size"][0])
                h = float(task["size"][1])
                d = float(dpr or 1.0)
                W = max(1, int(round(w * d)))
                H = max(1, int(round(h * d)))
                out = QImage(W, H,
                             QImage.Format.Format_ARGB32_Premultiplied)
                try:
                    out.setDevicePixelRatio(d)
                except Exception:
                    exc_note("_do @ ggis/render/gpu_tile/backend.py:637")
                    pass
                col = task.get("color")
                try:
                    out.fill(QColor(col))
                except Exception:
                    exc_note("_do @ ggis/render/gpu_tile/backend.py:642")
                    out.fill(QColor(255, 255, 255))
                sv = self._scene_ver() if sv is None else int(sv or 0)
                _lvl, wt = self._viewport_tiles(task)
                p = QPainter(out)
                n = 0
                try:
                    for tid, _tr, sx, sy, sw, sh in wt:
                        ti = self._store.get(tid, sv, d)
                        if ti is None:
                            continue
                        p.drawImage(QRectF(sx * d, sy * d, sw * d, sh * d),
                                    ti)
                        n += 1
                finally:
                    p.end()
                self._tiles_drawn = n
                self.rendered.emit(out, int(seq), True)
            except Exception:
                exc_note("_do @ ggis/render/gpu_tile/backend.py:660")
                import traceback
                traceback.print_exc()

        QTimer.singleShot(0, _do)

    def _pm_of(self, tid, img):
        gen = self._store.stats["clear"]
        if self._pmc_gen != gen:
            self._pmc = {}
            self._pmc_gen = gen
        pm = self._pmc.get(tid)
        if pm is None:
            try:
                from PySide6.QtGui import QPixmap
                pm = QPixmap.fromImage(img)
                self._pmc[tid] = pm
            except Exception:
                exc_note("_pm_of @ ggis/render/gpu_tile/backend.py:679")
                return None
        return pm

    def _draw_tiles(self, p, host):
        if not self._tile_gpu_on():
            return False
        try:
            from PySide6.QtCore import QRectF
            ex = host._extent
            if ex is None:
                return False
            w = float(host.width())
            h = float(host.height())
            if w <= 0 or h <= 0:
                return False
            x0 = float(ex.xmin)
            y0 = float(ex.ymin)
            x1 = float(ex.xmax)
            y1 = float(ex.ymax)
            ew = (x1 - x0) or 1.0
            eh = (y1 - y0) or 1.0
            mupp = max(ew / w, eh / h)
            if not (mupp > 0.0) or not (mupp < float("inf")):
                return False
            dpr = float(getattr(host, "_dpr", 1.0) or 1.0)
            sv = self._scene_ver()
            lvl = TA.level_of(mupp)
            want = TA.visible_tiles((x0, y0, x1, y1), w, h, mupp, lvl,
                                    (0.0, 0.0))
            if not want or len(want) > TA.MAX_TILES_PER_VIEW:
                return False
            if self._store.missing(want, sv, dpr):
                alt = self._store.nearest_level(lvl)
                if alt is None:
                    return False
                want = TA.visible_tiles((x0, y0, x1, y1), w, h, mupp, alt,
                                        (0.0, 0.0))
                if self._store.missing(want, sv, dpr):
                    return False
            for tid, _tr, sx, sy, sw, sh in want:
                ti = self._store.get(tid, sv, dpr)
                if ti is None:
                    return False
                pm = self._pm_of(tid, ti)
                if pm is None:
                    return False
                p.drawPixmap(QRectF(sx, sy, sw, sh), pm,
                             QRectF(0, 0, pm.width(), pm.height()))
            return True
        except Exception:
            exc_note("_draw_tiles @ ggis/render/gpu_tile/backend.py:733")
            return False

    @property
    def gpu_active(self):
        return bool(self._gpu_ok) and not self._failed

    @property
    def fail_reason(self):
        return getattr(self, "_fail_reason", "") or ""

    def _disable_gpu(self):
        self._gpu_ok = False
        self._fail_reason = "运行中 GL 异常 ⇒ GPU 渲染已停用（不再静默回退 CPU）"
        try:
            import logging as _lg
            _lg.getLogger("gmagis").critical(
                "[渲染] 运行中 GL 异常 ⇒ GPU 合成层已停用（不再静默回退 CPU）。"
                " 失败原因：%s", self._fail_reason)
        except Exception:
            exc_note("_disable_gpu @ ggis/render/gpu_tile/backend.py:766")
            pass
        try:
            if self._gl is not None and self._gl.isVisible():
                self._gl.hide()
        except Exception:
            exc_note("_disable_gpu @ ggis/render/gpu_tile/backend.py:771")
            pass

    def _gl_geo(self, w, h):
        try:
            dpr = float(self._host.devicePixelRatioF() or 1.0)
        except Exception:
            exc_note("_gl_geo @ ggis/render/gpu_tile/backend.py:804")
            dpr = 1.0
        if dpr <= 0:
            dpr = 1.0
        if abs(dpr - 1.0) < 1e-6:
            return max(1, int(w)), max(1, int(h))

        def _fit(v):
            lv = int(int(v * dpr) / dpr)
            for _ in range(8):
                if lv <= 1:
                    break
                if abs(lv * dpr - round(lv * dpr)) <= 1e-6:
                    break
                lv -= 1
            return max(1, lv)

        return _fit(w), _fit(h)

    def sync_viewport(self):
        gl = self._gl
        if gl is None:
            return
        if not self._gpu_ok:
            if gl.isVisible():
                try:
                    gl.hide()
                except Exception:
                    exc_note("sync_viewport @ ggis/render/gpu_tile/backend.py:840")
                    pass
            return
        host = self._host
        w, h = host.width(), host.height()
        tw, th = self._gl_geo(w, h)
        if gl.width() != tw or gl.height() != th:
            self._pending_geo = (tw, th)
            try:
                gl.hide()
            except Exception:
                exc_note("sync_viewport @ ggis/render/gpu_tile/backend.py:865")
                pass
            try:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._apply_geo)
            except Exception:
                exc_note("sync_viewport @ ggis/render/gpu_tile/backend.py:870")
                self._pending_geo = None
                try:
                    gl.setGeometry(0, 0, tw, th)
                except Exception:
                    exc_note("sync_viewport @ ggis/render/gpu_tile/backend.py:874")
                    pass
        if not gl.isVisible():
            if not self._show_pending:
                self._show_pending = True
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._do_show)
            return
        try:
            ext_key = (host._extent.as_tuple()
                       if host._extent is not None else None)
        except Exception:
            exc_note("sync_viewport @ ggis/render/gpu_tile/backend.py:894")
            ext_key = None
        try:
            fe_id = id(host._frozen_extent)
        except Exception:
            exc_note("sync_viewport @ ggis/render/gpu_tile/backend.py:898")
            fe_id = None
        key = (w, h, host._panning, ext_key, fe_id, id(host._frozen),
               getattr(host, "_overlay_version", 0))
        if key == self._last_key:
            return
        self._last_key = key
        gl.update()

    def _apply_geo(self):
        geo = self._pending_geo
        self._pending_geo = None
        if geo is None:
            return
        gl = self._gl
        if gl is None or not self._gpu_ok:
            return
        try:
            gl.setGeometry(0, 0, geo[0], geo[1])
        except Exception:
            exc_note("_apply_geo @ ggis/render/gpu_tile/backend.py:923")
            pass
        try:
            if not gl.isVisible():
                gl.show()
                gl.raise_()
        except Exception:
            exc_note("_apply_geo @ ggis/render/gpu_tile/backend.py:931")
            pass
        try:
            gl.update()
        except Exception:
            exc_note("_apply_geo @ ggis/render/gpu_tile/backend.py:936")
            pass

    def _do_show(self):
        self._show_pending = False
        gl = self._gl
        if gl is None or not self._gpu_ok:
            return
        try:
            gl.show()
            gl.raise_()
        except Exception:
            exc_note("_do_show @ ggis/render/gpu_tile/backend.py:949")
            self._gpu_ok = False
            try:
                gl.hide()
            except Exception:
                exc_note("_do_show @ ggis/render/gpu_tile/backend.py:953")
                pass

    def _on_client_frame(self, img, seq, final):
        at = self._atlas.get(int(seq))
        if at is not None and int(at.get("seq", -1)) == int(seq):
            self._atlas.pop(int(seq), None)
            try:
                sv = self._scene_ver()
                dpr = float(at.get("dpr") or 1.0)
                self._store.bind(sv, dpr)
                got = TA.slice_atlas(img, at.get("places") or [], 1.0)
                for tid, sub in got.items():
                    self._store.put(tid, sub, sv, dpr)
                self._emit_composed(seq, at.get("orig"), dpr, sv)
            except Exception:
                exc_note("_on_client_frame @ ggis/render/gpu_tile/backend.py:972")
                import traceback
                traceback.print_exc()
                try:
                    self.rendered.emit(img, seq, final)
                except Exception:
                    exc_note("_on_client_frame @ ggis/render/gpu_tile/backend.py:979")
                    pass
            if self._gl is not None and self._gpu_ok:
                try:
                    self._gl.update()
                except Exception:
                    exc_note("_on_client_frame @ ggis/render/gpu_tile/backend.py:984")
                    pass
            return
        self.rendered.emit(img, seq, final)
        if self._gl is not None and self._gpu_ok:
            try:
                self._gl.update()
            except Exception:
                exc_note("_on_client_frame @ ggis/render/gpu_tile/backend.py:992")
                pass

    def set_scene(self, version, specs, dst_crs=None):
        return self._client.set_scene(version, specs, dst_crs)

    def push_scene(self):
        return self._client.push_scene()


    def invalidate(self):
        try:
            self._atlas.clear()
        except Exception:
            exc_note("invalidate @ ggis/render/gpu_tile/backend.py:1011")
            pass
        return self._client.invalidate()

    def is_warm(self):
        return self._client.is_warm()

    def failed(self):
        return bool(self._failed)

    def is_busy(self):
        return self._client.is_busy()

    def push_settings(self):
        return self._client.push_settings()

    def push_tiles(self, recs):
        return self._client.push_tiles(recs)

    def push_features(self, src, layer_name, wkbs, attrs):
        return self._client.push_features(src, layer_name, wkbs, attrs)

    def prefetch(self, src, layer=None):
        return self._client.prefetch(src, layer)

    def warmup(self):
        return self._client.warmup()

    def stop(self):
        try:
            self._atlas.clear()
        except Exception:
            exc_note("stop @ ggis/render/gpu_tile/backend.py:1039")
            pass
        try:
            if self._client is not None:
                self._client.stop()
        except Exception:
            exc_note("stop @ ggis/render/gpu_tile/backend.py:1044")
            pass
        try:
            if self._gl is not None:
                self._gl.hide()
                self._gl.deleteLater()
                self._gl = None
        except Exception:
            exc_note("stop @ ggis/render/gpu_tile/backend.py:1051")
            pass
