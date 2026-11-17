# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import os
import struct
import sys
from ggis.core.app import settings
import threading
from multiprocessing import shared_memory

_log = logging.getLogger("gmagis")

from PySide6.QtCore import QObject, QRectF, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QImage

_POLL_MS = 30

_STEP_BUDGET_MS = 24

_STEP_STALL_MAX = 12

_DEFERRED_WARM_CAP = 12

_PROC_BUILD_BUDGET_MS = 24.0

_CTRL_BYTES = 64


def _load_layer(spec, prefetch_pool=None):
    from ggis.io.raster_io import read_raster
    from ggis.io.vector_io import read_vector

    src = spec.get("source") or ""
    kind = spec.get("type") or ""
    if kind == "tile":
        from ggis.core.model.layer import GgsTileLayer
        from ggis.core.analysis.tile import GgsTileSource
        _ts = GgsTileSource.from_dict(spec.get("tile_source") or {})
        lyr = GgsTileLayer(spec.get("name") or _ts.display_name(), _ts)
    elif kind == "raster":
        lyr = read_raster(src)
    else:
        _mem = spec.get("memory")
        if _mem:
            from ggis.core.model.layer import GgsVectorLayer
            import shapely.wkb as _swkb
            _geoms, _attrs = [], []
            for _w, _a in zip(_mem.get("wkbs") or [], _mem.get("attrs") or []):
                if not _w:
                    continue
                try:
                    _g = _swkb.loads(bytes(_w))
                except Exception:
                    exc_note("_load_layer @ ggis/render/cpu/render_proc.py:146")
                    continue
                _geoms.append(_g)
                _attrs.append(_a)
            _fields = [tuple(f) for f in (_mem.get("fields") or [])]
            lyr = GgsVectorLayer(
                spec.get("name") or "", "", spec.get("crs") or "",
                _mem.get("geom_type") or "", _geoms, _attrs, _fields)
            lyr._valid = True
        else:
            _pf = None
            if prefetch_pool is not None:
                try:
                    _pf = prefetch_pool.pop(str(src), None)
                except Exception:
                    exc_note("_load_layer @ ggis/render/cpu/render_proc.py:162")
                    _pf = None
            if _pf is not None:
                lyr = _pf
            else:
                lyr = read_vector(
                    src, layer=spec.get("layer"),
                    viewport_cull=(_F_VIEWPORT_CULL and _src_is_huge(src)))
    if lyr is None or not hasattr(lyr, "is_vector"):
        raise RuntimeError("读盘没返回图层（src=%r）：%r" % (src, type(lyr)))
    try:
        if spec.get("crs"):
            lyr.setCrs(spec["crs"])
    except Exception as exc:
        _log.warning("子进程图层 CRS 设置失败（src=%r）：%s", src, exc)
    try:
        _log.info("[层装配] src=%r -> %s", src, type(lyr).__name__)
    except Exception:
        pass
    _apply_style(lyr, spec)
    return lyr


import os as _os_dbg
_DBG = bool(_os_dbg.environ.get("GGIS_RPROC_DEBUG"))
_MISS = []

_F_VIEWPORT_CULL = (_os_dbg.environ.get("GGIS_NO_VP_CULL", "") == "")


def _src_is_huge(src):
    try:
        return bool(src) and os.path.isfile(src) \
            and os.path.getsize(src) > 300 * 1024 * 1024
    except Exception:
        exc_note("_src_is_huge @ ggis/render/cpu/render_proc.py:206")
        return False


def _extent_contains(loaded, cur, margin=0.1):
    if not loaded or len(loaded) != 4 or not cur or len(cur) != 4:
        return False
    try:
        lx0, ly0, lx1, ly1 = (float(v) for v in loaded)
        cx0, cy0, cx1, cy1 = (float(v) for v in cur)
    except Exception:
        exc_note("_extent_contains @ ggis/render/cpu/render_proc.py:217")
        return False
    if lx1 <= lx0 or ly1 <= ly0:
        return False
    mx = (lx1 - lx0) * margin
    my = (ly1 - ly0) * margin
    return (cx0 >= lx0 - mx and cy0 >= ly0 - my
            and cx1 <= lx1 + mx and cy1 <= ly1 + my)


_VP_JOB = None
_VP_LOCK = threading.Lock()
_VP_WAKE = threading.Event()
_VP_THREAD = None


def _vp_full_reload(lyr, dst_crs, kind):
    try:
        from ggis.io.vector_io import _read_vector_sync
        _full = _read_vector_sync(lyr.source(), defer_geometry=False)
        if _full is not None and getattr(_full, "is_valid", lambda: False)():
            lyr.set_features(_full.geoms(), _full.attrs())
            lyr._viewport_cull = False
            lyr._loaded_extent = None
    except Exception as exc:
        _log.warning("视口裁剪全量回退失败（将永久空白层，src=%r）：%s",
                     getattr(lyr, "source", lambda: "?")(), exc)


def _vp_worker():
    global _VP_JOB
    while True:
        with _VP_LOCK:
            _job = _VP_JOB
            _VP_JOB = None
        if _job is None:
            _VP_WAKE.wait(0.5)
            _VP_WAKE.clear()
            continue
        lyr, extent, kind, dst_crs, lod_level = _job
        try:
            _ext = tuple(extent)
            try:
                from ggis.render.rasterize import crs_transformer, convert_xy
                import numpy as _np
                _sc = lyr.crs()
                if dst_crs and _sc and str(dst_crs) != str(_sc):
                    _tf = crs_transformer(dst_crs, _sc)
                    if _tf is not None:
                        _xs = _np.array([extent[0], extent[2], extent[0], extent[2]])
                        _ys = _np.array([extent[1], extent[1], extent[3], extent[3]])
                        _p = convert_xy(_np.column_stack([_xs, _ys]), _tf)
                        _ext = (float(_p[:, 0].min()), float(_p[:, 1].min()),
                                float(_p[:, 0].max()), float(_p[:, 1].max()))
                _mx = (_ext[2] - _ext[0]) * 0.05
                _my = (_ext[3] - _ext[1]) * 0.05
                _ext = (_ext[0] - _mx, _ext[1] - _my,
                        _ext[2] + _mx, _ext[3] + _my)
            except Exception:
                exc_note("_vp_worker @ ggis/render/cpu/render_proc.py:287")
                _vp_full_reload(lyr, dst_crs, kind)
                continue
            if not lyr.load_extent(_ext):
                _vp_full_reload(lyr, dst_crs, kind)
                continue
            import time as _tw
            _y = lambda: _tw.sleep(0)
            from ggis.render.rasterize import flat_coords
            _n = 0
            try:
                _n = len(lyr._geoms)
            except Exception:
                exc_note("_vp_worker @ ggis/render/cpu/render_proc.py:312")
                try:
                    _n = int(lyr.feature_count())
                except Exception:
                    exc_note("_vp_worker @ ggis/render/cpu/render_proc.py:315")
                    _n = 0
            _no_simp = _n > 200000
            try:
                flat_coords(lyr, float(lod_level or 0.0), kind=kind,
                            dst_crs=dst_crs, yield_fn=_y, force=True,
                            no_simplify=_no_simp)
            except Exception:
                exc_note("_vp_worker @ ggis/render/cpu/render_proc.py:322")
                pass
        except Exception:
            exc_note("_vp_worker @ ggis/render/cpu/render_proc.py:324")
            try:
                _vp_full_reload(lyr, dst_crs, kind)
            except Exception:
                exc_note("_vp_worker @ ggis/render/cpu/render_proc.py:327")
                pass


def _vp_kick():
    global _VP_THREAD
    _t = _VP_THREAD
    if _t is None or not _t.is_alive():
        _t = threading.Thread(target=_vp_worker, daemon=True,
                             name="ggis-vp-cull")
        _VP_THREAD = _t
        _t.start()
    else:
        _VP_WAKE.set()


def _kick_viewport_reload(lyr, extent, kind, dst_crs, lod_level=0.0):
    global _VP_JOB
    with _VP_LOCK:
        _VP_JOB = (lyr, extent, kind, dst_crs, float(lod_level or 0.0))
    _vp_kick()


def _layer_key(lyr):
    try:
        from ggis.core.model.layer import source_generation, data_version
        gen = source_generation(lyr)
        dv = data_version(lyr)
    except Exception:
        exc_note("_layer_key @ ggis/render/cpu/render_proc.py:376")
        gen = 0
        dv = 0
    base = str(lyr.id())
    if not (lyr.source() if hasattr(lyr, "source") else ""):
        return "%s|m%d" % (base, dv)
    return base if not gen else "%s|%d" % (base, gen)


def _memory_spec(lyr):
    try:
        geoms = list(getattr(lyr, "_geoms", []) or [])
        attrs = list(getattr(lyr, "_attrs", []) or [])
        fields = list(getattr(lyr, "_fields", []) or [])
        wkbs = []
        for g in geoms:
            try:
                wkbs.append(bytes(g.wkb))
            except Exception:
                exc_note("_memory_spec @ ggis/render/cpu/render_proc.py:408")
                wkbs.append(b"")
        ats = []
        for a in attrs:
            try:
                ats.append(dict(a) if a is not None else None)
            except Exception:
                exc_note("_memory_spec @ ggis/render/cpu/render_proc.py:414")
                ats.append(None)
        flds = []
        for f in fields:
            try:
                flds.append((str(getattr(f, "name", "")),
                             str(getattr(f, "type", ""))))
            except Exception:
                exc_note("_memory_spec @ ggis/render/cpu/render_proc.py:421")
                pass
        return {
            "geom_type": str(getattr(lyr, "_geometry_type", "") or ""),
            "wkbs": wkbs,
            "attrs": ats,
            "fields": flds,
        }
    except Exception as exc:
        _log.warning("图层渲染规格构建失败（src=%r）：%s",
                     getattr(lyr, "source", lambda: "?")(), exc)
        return None


def _spec_key(sp):
    k = sp.get("key")
    return k if k else (sp.get("source") or "")


def _apply_style(lyr, spec):
    from ggis.render import labeling as LA
    from ggis.render import renderers as RE

    try:
        lyr.set_visible(bool(spec.get("visible", True)))
        _op = spec.get("opacity", None)
        lyr.set_opacity(1.0 if _op is None else float(_op))
        lyr.set_scale_range(float(spec.get("min_scale", 0.0) or 0.0),
                            float(spec.get("max_scale", 0.0) or 0.0))
    except Exception:
        exc_note("_apply_style @ ggis/render/cpu/render_proc.py:483")
        pass
    try:
        dd = spec.get("display")
        if dd:
            from ggis.core.style import raster_display as _rd
            if _rd.get_display(lyr).to_dict() != dd:
                _rd.set_display(lyr, _rd.GgsRasterDisplay.from_dict(dd))
    except Exception:
        exc_note("_apply_style @ ggis/render/cpu/render_proc.py:498")
        import traceback
        traceback.print_exc()
    if not (hasattr(lyr, "is_vector") and lyr.is_vector()):
        return
    try:
        d = spec.get("renderer")
        if d and RE.get_renderer(lyr).to_dict() != d:
            RE.set_renderer(lyr, RE.GgsFeatureRenderer.from_dict(d))
    except Exception:
        exc_note("_apply_style @ ggis/render/cpu/render_proc.py:507")
        import traceback
        traceback.print_exc()
    try:
        ld = spec.get("label")
        if ld and LA.get_label_style(lyr).to_dict() != ld:
            LA.set_label_style(lyr, LA.LabelStyle.from_dict(ld))
    except Exception:
        exc_note("_apply_style @ ggis/render/cpu/render_proc.py:516")
        import traceback
        traceback.print_exc()
    try:
        expr = spec.get("subset_expr")
        fids = spec.get("subset_fids")
        if expr or fids:
            lyr.set_subset(fids or [], expr or "")
        else:
            lyr.clear_subset()
    except Exception:
        exc_note("_apply_style @ ggis/render/cpu/render_proc.py:527")
        pass


class _Sub:

    def __init__(self, shm_ctrl, root, req_q=None):
        self._ctrl = shared_memory.SharedMemory(name=shm_ctrl)
        self._req_q = req_q
        self._surf = None
        self._surf_name = None
        self._img = None
        self._wh = (0, 0)
        self._want_scene = None
        self._want_crs = None
        self._layers = {}
        self._layers_pool = {}
        self._prefetched = {}
        self._vec_sig = None
        self._layer_order = []
        self._last_wh = (900, 620)
        self._scene_key = None
        self._cv = None
        self._tiles = {}
        self._tile_provider_on = None
        self._tile_gen = 0
        self._pub = 0

        sys.path.insert(0, root)
        try:
            from ggis.io import async_loader as _al
            _al.prewarm_flat_async = lambda *a, **k: None
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/render_proc.py:582")
            pass
        try:
            from ggis.render import map_canvas as _mcx
            _mcx._USE_PROC_RENDER = False
            _mcx._PROC_PRESPAWN = False
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/render_proc.py:600")
            pass
        try:
            from ggis.render import map_canvas as _mc2

            def _no_frame_renderer(_self):
                return None

            _mc2.GgsMapCanvas._ensure_frame_renderer = _no_frame_renderer
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/render_proc.py:614")
            pass
        try:
            from ggis.render.cpu import backend as _bk
            _bk._UI_BUILD_BUDGET_MS = 40.0
            _bk.set_lod_ctrl_buf(self._ctrl.buf)
        except Exception:
            exc_note("__init__ @ ggis/render/cpu/render_proc.py:626")
            pass
        from PySide6.QtWidgets import QApplication
        self._qapp = QApplication.instance() or QApplication([])

    def run(self):
        from PySide6.QtCore import QTimer
        self._qtimer = QTimer()
        self._qtimer.setInterval(_POLL_MS)
        self._qtimer.timeout.connect(self._drain)
        self._qtimer.start()
        self._qapp.exec()
        try:
            if getattr(self, "_cv", None) is not None:
                try:
                    self._cv.release_buffers()
                except Exception:
                    exc_note("run @ ggis/render/cpu/render_proc.py:660")
                    pass
        except Exception:
            exc_note("run @ ggis/render/cpu/render_proc.py:662")
            pass
        try:
            if self._surf is not None:
                self._surf.close()
        except Exception:
            exc_note("run @ ggis/render/cpu/render_proc.py:667")
            pass

    def _drain(self):
        import queue as _queue
        while True:
            try:
                msg = self._req_q.get_nowait()
            except _queue.Empty:
                return
            except (EOFError, OSError):
                exc_note("_drain @ ggis/render/cpu/render_proc.py:679")
                self._qapp.quit()
                return
            if msg is None:
                self._qapp.quit()
                return
            kind = msg[0]
            try:
                if kind == "surface":
                    self.set_surface(msg[1], msg[2], msg[3])
                elif kind == "scene":
                    self.set_scene(msg[1], msg[2], msg[3])
                    if self._cv is None:
                        self.ensure_canvas(*self._last_wh)
                    self._apply_scene()
                elif kind == "prefetch":
                    self.prefetch(msg[1], msg[2] if len(msg) > 2 else None)
                elif kind == "tiles":
                    self.push_tiles(msg[1])
                elif kind == "set_features":
                    self.apply_features(msg[1], msg[2] if len(msg) > 2 else None,
                                        msg[3] if len(msg) > 3 else None,
                                        msg[4] if len(msg) > 4 else None)
                elif kind == "settings":
                    from ggis.core.app import settings as _st
                    _st.reload()
                elif kind == "render":
                    self.render(msg[1])
            except Exception:
                exc_note("_drain @ ggis/render/cpu/render_proc.py:722")
                import traceback
                traceback.print_exc()
                try:
                    struct.pack_into("q", self._ctrl.buf, 0, -2)
                    if isinstance(msg, tuple) and len(msg) > 1 \
                            and isinstance(msg[1], dict):
                        struct.pack_into("q", self._ctrl.buf, 16,
                                         int(msg[1].get("seq") or 0))
                    else:
                        struct.pack_into("q", self._ctrl.buf, 16, 1 << 60)
                except Exception:
                    exc_note("_drain @ ggis/render/cpu/render_proc.py:737")
                    pass

    def prefetch(self, src, layer_name=None):
        src = str(src or "")
        if not src:
            return
        try:
            from ggis.io.vector_io import read_vector, is_vector_path
            if not is_vector_path(src):
                return
            lyr = read_vector(src, layer=layer_name)
            if lyr is not None \
                    and getattr(lyr, "is_valid", lambda: True)():
                pool = self._prefetched
                pool[src] = lyr
                while len(pool) > 2:
                    pool.pop(next(iter(pool)))
        except Exception:
            exc_note("prefetch @ ggis/render/cpu/render_proc.py:764")
            pass

    def apply_features(self, src, layer_name, wkbs, attrs):
        if wkbs is None:
            return False
        try:
            import numpy as _np
            from shapely import from_wkb as _from_wkb
            geoms = list(_from_wkb(_np.array(wkbs, dtype=object)))
        except Exception:
            exc_note("apply_features @ ggis/render/cpu/render_proc.py:785")
            import traceback
            traceback.print_exc()
            return False
        ats = None
        if attrs is not None:
            try:
                ats = list(attrs)
            except Exception:
                exc_note("apply_features @ ggis/render/cpu/render_proc.py:793")
                ats = None
        src = str(src or "")
        lname = str(layer_name or "")
        for pool in (self._layers, self._layers_pool):
            try:
                for lyr in list(pool.values()):
                    try:
                        if not bool(lyr.is_vector()):
                            continue
                        if src and str(lyr.source() or "") != src:
                            continue
                        if lname and str(lyr.name() or "") != lname:
                            continue
                        lyr.set_features(geoms, ats)
                        return True
                    except Exception:
                        exc_note("apply_features @ ggis/render/cpu/render_proc.py:809")
                        continue
            except Exception:
                exc_note("apply_features @ ggis/render/cpu/render_proc.py:811")
                pass
        return False

    def set_surface(self, name, w_px, h_px):
        w_px, h_px = int(w_px), int(h_px)
        if self._surf_name == name and self._wh == (w_px, h_px):
            return
        if self._surf is not None:
            try:
                self._surf.close()
            except Exception:
                exc_note("set_surface @ ggis/render/cpu/render_proc.py:827")
                pass
            self._surf = None
        if (self._surf is not None and self._surf_name == name
                and w_px * h_px * 4 <= len(self._surf.buf)):
            self._img = QImage(self._surf.buf, w_px, h_px, w_px * 4,
                               QImage.Format.Format_ARGB32_Premultiplied)
            self._wh = (w_px, h_px)
            self._last_wh = (w_px, h_px)
            return
        if self._surf is not None:
            try:
                self._surf.close()
            except Exception:
                exc_note("set_surface @ ggis/render/cpu/render_proc.py:843")
                pass
            self._surf = None
        self._surf = shared_memory.SharedMemory(name=name)
        self._img = QImage(self._surf.buf, w_px, h_px, w_px * 4,
                           QImage.Format.Format_ARGB32_Premultiplied)
        self._surf_name = name
        self._wh = (w_px, h_px)
        self._last_wh = (w_px, h_px)

    def ensure_canvas(self, w=None, h=None, dpr=1.0):
        if self._cv is None:
            from ggis.render.map_canvas import GgsMapCanvas
            self._cv = GgsMapCanvas()
        if w and h:
            self._cv.resize(int(w), int(h))
        try:
            self._cv.set_forced_dpr(float(dpr or 1.0))
        except Exception:
            exc_note("ensure_canvas @ ggis/render/cpu/render_proc.py")
        return self._cv

    def set_scene(self, version, specs, dst_crs=None):
        self._want_crs = _as_crs(dst_crs)
        if self._scene_key == version:
            return
        self._want_scene = (version, specs)

    def _install_tile_provider(self):
        try:
            p = getattr(self._cv, "_tile_painter", None)
            if p is None or p is self._tile_provider_on:
                return
            tiles = self._tiles

            def _get(source, z, x, y):
                try:
                    k = (str(getattr(source, "key", "")), int(z), int(x), int(y))
                    got = tiles.get(k)
                    if _DBG and len(_MISS) < 6:
                        _MISS.append((k if got is None else "hit:" + str(k)))
                    return got
                except Exception:
                    exc_note("_get @ ggis/render/cpu/render_proc.py:916")
                    return None

            p.set_provider(_get)
            try:
                p.set_ext_gen(lambda: self._tile_gen)
            except Exception:
                exc_note("_install_tile_provider @ ggis/render/cpu/render_proc.py:930")
            if _DBG:
                print("[子进程] 装了瓦片 provider（已有 %d 张）" % len(tiles),
                      flush=True)
            self._tile_provider_on = p
        except Exception:
            exc_note("_install_tile_provider @ ggis/render/cpu/render_proc.py:924")
            pass

    def push_tiles(self, records):
        if not records:
            return 0
        n = 0
        for rec in records:
            try:
                sk, z, x, y, w, h, bpl, fmt, data = rec
                img = QImage(data, int(w), int(h), int(bpl),
                             QImage.Format(int(fmt)))
                if img.isNull():
                    continue
                self._tiles[(str(sk), int(z), int(x), int(y))] = img.copy()
                n += 1
            except Exception:
                exc_note("push_tiles @ ggis/render/cpu/render_proc.py:947")
                continue
        self._install_tile_provider()
        if n:
            self._tile_gen += 1
        if _DBG:
            print("[子进程] 收到瓦片 %d 张（累计 %d）" % (n, len(self._tiles)),
                  flush=True)
        return n

    def _apply_scene(self):
        item = self._want_scene
        if item is None:
            return
        version, specs = item
        self._want_scene = None
        cv = self._cv
        proj = cv._project
        specs = list(specs or [])

        want = [_spec_key(sp) for sp in specs]
        reuse = (self._layer_order == want and want)
        if reuse:
            from ggis.core.crs import crs_key
            for sp in specs:
                lyr = self._layers.get(_spec_key(sp))
                if lyr is None:
                    reuse = False
                    break
                try:
                    if (sp.get("crs") or "") != crs_key(lyr.crs()):
                        reuse = False
                        break
                except Exception:
                    exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:987")
                    reuse = False
                    break
        try:
            import logging as _lg
            _lg.getLogger("gmagis").info(
                "[场景落地] ver=%r reuse=%s 层数=%d ｜ %r",
                version, reuse, len(specs),
                [(str(sp.get("source") or "").replace("\\", "/").split("/")[-1],
                  sp.get("visible"), sorted(sp.keys())) for sp in specs])
        except Exception:
            exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1008")
            pass
        try:
            import os as _os
            if _os.environ.get("GGIS_RPROC_DEBUG"):
                print("[子进程] scene ver=%r reuse=%s ｜ want=%r ｜ 现有=%r"
                      % (version, reuse,
                         [str(sp.get("source") or "").split("/")[-1]
                          for sp in specs],
                         [str(getattr(self._layers.get(k), "source",
                                      lambda: k)()).split("/")[-1]
                          for k in self._layer_order]),
                      flush=True)
                print("[子进程] scene 推来的 visible 旗标=%r"
                      % ([sp.get("visible") for sp in specs],), flush=True)
        except Exception:
            exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1008")
            pass
        if reuse:
            self._install_tile_provider()
            for sp in specs:
                try:
                    _apply_style(self._layers[_spec_key(sp)], sp)
                except Exception:
                    exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1015")
                    import traceback
                    traceback.print_exc()
        else:
            try:
                proj.remove_all(close=False)
            except Exception:
                exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1034")
                pass
            new_layers = {}
            for sp, k in zip(specs, want):
                lyr = self._layers.get(k)
                if lyr is None:
                    lyr = self._layers_pool.pop(k, None)
                if lyr is None:
                    try:
                        lyr = _load_layer(sp,
                                          prefetch_pool=self._prefetched)
                    except Exception:
                        exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1045")
                        import traceback
                        traceback.print_exc()
                        continue
                else:
                    try:
                        _apply_style(lyr, sp)
                    except Exception:
                        exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1053")
                        import traceback
                        traceback.print_exc()
                new_layers[k] = lyr
                try:
                    proj.add_layer(lyr)
                except Exception:
                    exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1059")
                    import traceback
                    traceback.print_exc()
            try:
                for k, lyr in self._layers.items():
                    if k not in new_layers:
                        self._layers_pool[k] = lyr
            except Exception:
                exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1068")
                pass
            self._layers = new_layers
            self._layer_order = want
            try:
                while len(self._layers_pool) > 8:
                    self._layers_pool.pop(next(iter(self._layers_pool)))
            except Exception:
                exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1076")
                pass
            self._install_tile_provider()
            try:
                import os as _os2
                if _os2.environ.get("GGIS_RPROC_DEBUG"):
                    print("[子进程] 重建后 proj.layers()=%r"
                          % ([str(l.name()).split("/")[-1]
                              for l in proj.layers()],), flush=True)
            except Exception:
                exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1088")
                pass
        self._scene_key = version
        try:
            _vsig = tuple(
                repr(sp) for sp in specs
                if (sp.get("type") or "") not in ("tile", "raster"))
        except Exception:
            exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1100")
            _vsig = None
        if _vsig != self._vec_sig:
            try:
                cv._vec_cache = None
            except Exception:
                exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1105")
                pass
            self._vec_sig = _vsig
        try:
            from ggis.render.painter import _xy_cache as _xy_warm
            for _lyr in list(self._cv._project.layers()):
                try:
                    if not _lyr.is_vector():
                        continue
                    if getattr(_lyr, "_viewport_cull", False):
                        continue
                    if _lyr.base_kind() != "point":
                        continue
                    _xy_warm(_lyr, self._want_crs)
                except Exception:
                    exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1121")
                    import traceback
                    traceback.print_exc()
        except Exception:
            exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1124")
            import traceback
            traceback.print_exc()
        self._publish(-3)
        try:
            import threading as _th
            _old = getattr(self, "_warm0_th", None)
            if _old is None or not _old.is_alive():
                self._warm0_th = _th.Thread(
                    target=self._warm0_bg, name="ggs-proc-warm0",
                    daemon=True)
                self._warm0_th.start()
        except Exception:
            exc_note("_apply_scene @ ggis/render/cpu/render_proc.py:1156")
            import traceback
            traceback.print_exc()

    def _warm0_bg(self):
        try:
            self._warm(self._want_crs, None)
        except Exception:
            exc_note("_warm0_bg @ ggis/render/cpu/render_proc.py:1172")
            import traceback
            traceback.print_exc()

    def _layer_is_huge(self, lyr):
        try:
            if int(lyr.feature_count()) > 200000:
                return True
        except Exception:
            exc_note("_layer_is_huge @ ggis/render/cpu/render_proc.py:1187")
            pass
        try:
            import os
            src = lyr.source()
            if src and os.path.isfile(src):
                if os.path.getsize(src) > 300 * 1024 * 1024:
                    return True
        except Exception:
            exc_note("_layer_is_huge @ ggis/render/cpu/render_proc.py:1195")
            pass
        return False

    def _warm(self, dst_crs, settings=None):
        from ggis.render.painter import _xy_cache
        from ggis.render.rasterize import flat_cached, flat_coords
        import time as _tw
        _y = lambda: _tw.sleep(0)
        _warmed_0 = False
        for lyr in list(self._cv._project.layers()):
            try:
                if not lyr.is_vector():
                    continue
                _kind = lyr.base_kind()
                if getattr(lyr, "_viewport_cull", False):
                    continue
                if _kind == "point":
                    _xy_cache(lyr, dst_crs)
                    continue
                if not _kind:
                    continue
                kind = "line" if _kind == "line" else "polygon"
                from ggis.render.cpu import backend as _bk
                if not self._layer_is_huge(lyr):
                    if flat_cached(lyr, 0.0, kind, dst_crs) is None:
                        flat_coords(lyr, 0.0, kind=kind, dst_crs=dst_crs,
                                    yield_fn=_y)
                        _warmed_0 = True
                    _fl = flat_cached(lyr, 0.0, kind, dst_crs)
                    if _fl is not None and not _bk.polys_ready(_fl):
                        _bk.prewarm_part_polys(_fl, yield_fn=_y)
                if settings is not None:
                    try:
                        from ggis.render.painter import vector_lod_tol
                        from ggis.render.rasterize import quantize_tolerance
                        _lt = vector_lod_tol(settings, lyr.crs(), dst_crs)
                        _lq = quantize_tolerance(float(_lt or 0.0))
                        pass
                    except Exception:
                        exc_note("_warm @ ggis/render/cpu/render_proc.py:1306")
                        import traceback
                        traceback.print_exc()
            except Exception:
                exc_note("_warm @ ggis/render/cpu/render_proc.py:1309")
                import traceback
                traceback.print_exc()
        if _warmed_0:
            try:
                from ggis.render.cpu import backend as _bk
                _bk._bump_lod_build_seq()
            except Exception:
                exc_note("_warm @ ggis/render/cpu/render_proc.py:1322")
                pass

    def _warm_deferred(self, settings):
        from ggis.render.rasterize import (flat_cached, flat_coords,
                                            _lod_is_fine)
        from ggis.render.painter import vector_lod_tol
        dst = settings.destination_crs() if settings is not None \
            else self._want_crs
        for lyr in list(self._cv._project.layers()):
            try:
                if not lyr.is_vector():
                    continue
                if getattr(lyr, "_viewport_cull", False):
                    continue
                _kind = lyr.base_kind()
                if _kind not in ("line", "polygon"):
                    continue
                kind = "line" if _kind == "line" else "polygon"
                if self._layer_is_huge(lyr):
                    continue
                if flat_cached(lyr, 0.0, kind, dst) is None:
                    _ng = len(lyr.geoms() or []) if hasattr(lyr, "geoms") else -1
                    try:
                        flat_coords(lyr, 0.0, kind=kind, dst_crs=dst,
                                    yield_fn=lambda: None)
                    except Exception:
                        exc_note("_warm_deferred @ ggis/render/cpu/render_proc.py:1374")
                        pass
                try:
                    _lod_tol = float(vector_lod_tol(settings, lyr.crs(),
                                                   dst) or 0.0)
                except Exception:
                    exc_note("_warm_deferred @ ggis/render/cpu/render_proc.py:1380")
                    _lod_tol = 0.0
                if _lod_tol and _lod_tol > 0 \
                        and not _lod_is_fine(lyr, _lod_tol, kind, dst):
                    if flat_cached(lyr, _lod_tol, kind, dst) is None:
                        try:
                            flat_coords(lyr, _lod_tol, kind=kind,
                                        dst_crs=dst, yield_fn=lambda: None)
                        except Exception:
                            exc_note("_warm_deferred @ ggis/render/cpu/render_proc.py:1388")
                            pass
            except Exception:
                exc_note("_warm_deferred @ ggis/render/cpu/render_proc.py:1390")
                pass

    def _render_atlas(self, task):
        from PySide6.QtCore import QRectF, QSize

        from ggis.core.crs.extent import GgsRectangle
        from ggis.render.viewport import GgsMapSettings

        tiles = list(task.get("tiles") or [])
        AW, AH = int(task["size"][0]), int(task["size"][1])
        cv = self.ensure_canvas(AW, AH, 1.0)
        self._apply_scene()

        img = self._img
        if img is None:
            raise RuntimeError("还没收到 surface（主进程要先下发共享内存名）")
        if (img.width(), img.height()) != (AW, AH):
            if (self._surf is not None
                    and AW * AH * 4 <= len(self._surf.buf)):
                img = QImage(self._surf.buf, AW, AH, AW * 4,
                             QImage.Format.Format_ARGB32_Premultiplied)
                self._img = img
                self._wh = (AW, AH)
            else:
                raise RuntimeError(
                    "图集 surface %dx%d 与请求 %dx%d 不符（内存装不下）"
                    % (img.width(), img.height(), AW, AH))
        img.setDevicePixelRatio(1.0)

        seq = int(task["seq"])
        if self._superseded(seq):
            self._publish(seq, finished=True, bump=False)
            return False
        try:
            cv._anti_alias = bool(task.get("aa", True))
        except Exception:
            exc_note("_render_atlas @ ggis/render/cpu/render_proc.py:1447")
            pass
        try:
            le = task.get("labels_enabled", None)
            if le is not None:
                cv._labels_enabled = bool(le)
        except Exception:
            exc_note("_render_atlas @ ggis/render/cpu/render_proc.py:1453")
            pass

        color = QColor(*task.get("color", (255, 255, 255)))
        crs = task.get("crs")
        self._want_crs = _as_crs(crs)
        labels = bool(task.get("labels", True))
        aa = bool(task.get("aa", True))

        img.fill(color)
        p = QPainter(img)
        try:
            if aa:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            warmed = False
            for item in tiles:
                _tid, rect, px, py, tw, th = item
                tw, th = int(tw), int(th)
                s = GgsMapSettings()
                s.set_extent(GgsRectangle(rect[0], rect[1], rect[2], rect[3]))
                s.set_output_size(QSize(tw, th))
                try:
                    s.set_lod_reference_width(
                        int(task.get("lod_ref_width") or 0))
                except Exception:
                    exc_note("_render_atlas @ ggis/render/cpu/render_proc.py:1480")
                    pass
                if crs:
                    s.set_destination_crs(crs)
                try:
                    s.set_dpi(float(task.get("dpi") or 96.0))
                except Exception:
                    exc_note("_render_atlas @ ggis/render/cpu/render_proc.py:1486")
                    pass
                cv.setExtent(s.extent())
                if not warmed:
                    try:
                        from ggis.core.crs import crs_key as _ck
                        from ggis.render.rasterize import quantize_tolerance
                        _mupp = s.map_units_per_pixel()
                        _sq = quantize_tolerance(float(_mupp)) \
                            if _mupp and _mupp > 0 else 0.0
                        _wkey = (self._scene_key,
                                 _ck(self._want_crs) or "", _sq)
                    except Exception:
                        exc_note("_render_atlas @ ggis/render/cpu/render_proc.py:1500")
                        _wkey = (self._scene_key, self._want_crs)
                    if getattr(self, "_warm_key", None) != _wkey:
                        self._warm(self._want_crs, s)
                        self._warm_key = _wkey
                    warmed = True
                p.save()
                p.translate(int(px), int(py))
                p.setClipRect(QRectF(0, 0, tw, th))
                cv._paint_scene(
                    p, s, with_labels=labels, with_selection=False,
                    with_overlay=False, vec_cache=True,
                    build_budget_ms=_PROC_BUILD_BUDGET_MS,
                    label_capped=False)
                p.restore()
        finally:
            p.end()
        self._publish(seq, finished=True, bump=True)
        return True

    def render(self, task):
        if task.get("tiles"):
            return self._render_atlas(task)
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QColor, QPainter

        from ggis.render.viewport import GgsMapSettings

        w, h = task["size"]
        dpr = float(task.get("dpr") or 1.0)
        cv = self.ensure_canvas(w, h, dpr)
        self._want_crs = _as_crs(task.get("crs"))
        self._apply_scene()
        img = self._img
        if img is None:
            raise RuntimeError("还没收到 surface（主进程要先下发共享内存名）")
        _w_px = max(1, int(round(w * dpr)))
        _h_px = max(1, int(round(h * dpr)))
        if (img.width(), img.height()) != (_w_px, _h_px):
            if (self._surf is not None
                    and _w_px * _h_px * 4 <= len(self._surf.buf)):
                img = QImage(self._surf.buf, _w_px, _h_px, _w_px * 4,
                             QImage.Format.Format_ARGB32_Premultiplied)
                self._img = img
                self._wh = (_w_px, _h_px)
            else:
                raise RuntimeError(
                    "surface 尺寸 %dx%d 与请求 %dx%d 不符（内存装不下）"
                    % (img.width(), img.height(), _w_px, _h_px))
        img.setDevicePixelRatio(dpr)

        s = GgsMapSettings()
        e = task["extent"]
        from ggis.core.crs.extent import GgsRectangle
        s.set_extent(GgsRectangle(e[0], e[1], e[2], e[3]))
        s.set_output_size(QSize(int(w), int(h)))
        try:
            s.set_lod_reference_width(int(task.get("lod_ref_width") or 0))
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1583")
            pass
        try:
            import logging as _lg
            _sw = task.get("size") or (None, None)
            _lg.getLogger("gmagis").info(
                "[帧任务] crs=%r extent=%r out=%sx%s dpr=%s",
                task.get("crs"), task.get("extent"),
                _sw[0], _sw[1], task.get("dpr"))
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1596")
            pass
        if task.get("crs"):
            s.set_destination_crs(task["crs"])
        elif task.get("crs") == "":
            _note_no_dst_crs()
        try:
            s.set_dpi(float(task.get("dpi") or 96.0))
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1612")
            pass

        color = QColor(*task.get("color", (255, 255, 255)))
        aa = bool(task.get("aa", True))
        try:
            cv._anti_alias = aa
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1619")
            pass
        try:
            le = task.get("labels_enabled", None)
            if le is not None:
                cv._labels_enabled = bool(le)
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1627")
            pass
        cv.setExtent(s.extent())

        try:
            _seq0 = int(task["seq"])
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1639")
            _seq0 = 0
        if self._superseded(_seq0):
            self._publish(_seq0, finished=True, bump=False)
            return False
        try:
            from ggis.core.crs import crs_key as _ck
            from ggis.render.rasterize import quantize_tolerance
            _mupp = s.map_units_per_pixel()
            _scale_q = quantize_tolerance(float(_mupp)) if _mupp and _mupp > 0 \
                else 0.0
            _wkey = (self._scene_key, _ck(self._want_crs) or "", _scale_q)
        except Exception:
            exc_note("render @ ggis/render/cpu/render_proc.py:1660")
            _wkey = (self._scene_key, self._want_crs)
        if getattr(self, "_warm_key", None) != _wkey:
            self._warm(self._want_crs, s)
            self._warm_key = _wkey

        if _F_VIEWPORT_CULL:
            try:
                from ggis.render.rasterize import quantize_tolerance, flat_cached
                from ggis.render.painter import vector_lod_tol
                _proj = self._cv._project
                for _vl in list(_proj.layers()):
                    if not getattr(_vl, "_viewport_cull", False):
                        continue
                    if not _vl.is_vector():
                        continue
                    _kind = "line" if _vl.base_kind() == "line" else "polygon"
                    _ext = s.extent()
                    _rect = (_ext.xmin, _ext.ymin, _ext.xmax, _ext.ymax)
                    _le = getattr(_vl, "_loaded_extent", None)
                    try:
                        _lt = vector_lod_tol(s, _vl.crs(), self._want_crs)
                        _lq = quantize_tolerance(float(_lt or 0.0))
                    except Exception:
                        exc_note("render @ ggis/render/cpu/render_proc.py:1688")
                        _lq = 0.0
                    _need = False
                    if _le is None or not _extent_contains(_le, _rect):
                        _need = True
                    else:
                        try:
                            if flat_cached(_vl, _lq, _kind,
                                           self._want_crs) is None:
                                _need = True
                        except Exception:
                            exc_note("render @ ggis/render/cpu/render_proc.py:1700")
                            pass
                    if _need:
                        _kick_viewport_reload(_vl, _rect, _kind,
                                             self._want_crs, _lq)
            except Exception:
                exc_note("render @ ggis/render/cpu/render_proc.py:1705")
                pass

        if os.environ.get("GGIS_RPROC_DEBUG"):
            try:
                _l0 = cv._project.layers()
                _e0 = _l0[0].extent() if _l0 else None
                print("[子进程 debug] 渲染前 各层=%r"
                      % ([(str(getattr(l, "name", lambda: "?")()),
                           bool(l.is_visible()), bool(l.is_valid()),
                           ("tile" if l.is_tile() else
                            ("raster" if l.is_raster() else "vec")))
                          for l in _l0],),
                      flush=True)
                print("[子进程 debug] 图层=%d 视野=%r 就绪=%s 出图=%r "
                      "目标CRS=%r 图层CRS=%r 图层范围=%r 相交=%s"
                      % (len(_l0), (s.extent().xmin, s.extent().ymin,
                                    s.extent().xmax, s.extent().ymax),
                         s.is_ready(),
                         (s.output_width(), s.output_height()),
                         task.get("crs"),
                         (task.get("crs"),),
                         (_e0.xmin, _e0.ymin, _e0.xmax, _e0.ymax)
                         if _e0 is not None else None,
                         bool(_e0 is not None
                              and s.extent().intersects(_e0))),
                      flush=True)
            except Exception:
                exc_note("render @ ggis/render/cpu/render_proc.py:1732")
                import traceback
                traceback.print_exc()

        labels = bool(task.get("labels", True))
        sel = bool(task.get("selection", True))
        over = bool(task.get("overlay", True))
        budget = task.get("raster_budget_ms", None)

        steps = 0
        incomplete = False
        seq = int(task["seq"])
        dbg = bool(os.environ.get("GGIS_RPROC_DEBUG"))
        _stall = 0
        _last_adv = None
        _def_warm_calls = 0
        if self._superseded(seq):
            self._publish(seq, finished=True, bump=False)
            return False
        while True:
            img.fill(color)
            p = QPainter(img)
            try:
                if aa:
                    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                incomplete = bool(cv._paint_scene(
                    p, s, with_labels=False, with_selection=False,
                    with_overlay=False, raster_budget_ms=budget,
                    vec_cache=True,
                    build_budget_ms=_PROC_BUILD_BUDGET_MS))
                _vc = cv._vec_cache
                _vc_empty = (not isinstance(_vc, dict)
                             or (not _vc.get("adv") and not _vc.get("tot")))
                done_now = (not incomplete) and (
                    _vc_empty or bool(_vc.get("done")))
            finally:
                p.end()
            steps += 1
            if dbg and (steps <= 3 or steps % 20 == 0):
                print("[子进程 debug] step=%d adv=%r tot=%r done=%s inc=%s"
                      % (steps,
                         getattr(cv._qc_painter, "_ring_adv", None),
                         getattr(cv._qc_painter, "_ring_tot", None),
                         done_now, incomplete), flush=True)
            try:
                self._qapp.processEvents()
            except Exception:
                exc_note("render @ ggis/render/cpu/render_proc.py:1818")
                pass
            if self._superseded(seq):
                self._publish(seq, finished=True, bump=False)
                return False
            if _DBG and _MISS:
                try:
                    _e = s.extent()
                    print("[子进程 debug] 瓦片层级输入：extent=(%.6f,%.6f,%.6f,%.6f)"
                          " 输出宽=%.1f 目标CRS=%r"
                          % (_e.xmin, _e.ymin, _e.xmax, _e.ymax,
                             float(s.output_width()),
                             str(s.destination_crs())), flush=True)
                except Exception as _e2:
                    _log.warning("tile debug probe extent failed",
                                 exc_info=True)
                print("[子进程 debug] 瓦片 provider 被问到的键（最多 6 个）=%r"
                      % (_MISS[:6],), flush=True)
                del _MISS[:]
            _adv = getattr(cv._qc_painter, "_ring_adv", 0)
            _raster_drew = bool(getattr(cv, "_raster_drew", False))
            if _adv in (0, -1):
                _stall = _stall + 1 if _adv == _last_adv else 0
                _last_adv = _adv
            else:
                _stall = 0
                _last_adv = _adv
            if _adv in (0, -1) and not done_now and not incomplete:
                if _raster_drew:
                    self._publish(seq, finished=False)
                if _def_warm_calls < _DEFERRED_WARM_CAP:
                    try:
                        self._warm_deferred(s)
                    except Exception:
                        exc_note("render @ ggis/render/cpu/render_proc.py:1887")
                        pass
                    _def_warm_calls += 1
                continue
            self._publish(seq, finished=False)
            if done_now and not incomplete:
                break
            if _stall >= _STEP_STALL_MAX:
                if _DBG:
                    print("[子进程] 装配连续 %d 步没有推进（adv=%r）"
                          "⇒ 提前收工" % (_stall, _adv), flush=True)
                break
            if steps >= 400:
                break
        if labels or sel or over:
            if self._superseded(seq):
                self._publish(seq, finished=True, bump=False)
                return False
            try:
                p = QPainter(img)
                try:
                    if aa:
                        p.setRenderHint(QPainter.RenderHint.Antialiasing,
                                        True)
                    if labels and bool(getattr(cv, "_labels_enabled", True)):
                        cv._draw_labels(p, s, capped=False, reuse_pan=True)
                    if sel:
                        cv._draw_selection(p, s)
                    if over:
                        cv._draw_tool_overlay(p, s)
                finally:
                    p.end()
            except Exception:
                exc_note("render @ ggis/render/cpu/render_proc.py:1934")
                import traceback
                traceback.print_exc()
        if dbg:
            try:
                from ggis.render.cpu import backend as _B
                from ggis.render.rasterize import flat_cached
                vc = cv._vec_cache or {}
                line = []
                for lyr in cv._project.layers():
                    if not lyr.is_vector():
                        continue
                    kind = "line" if lyr.base_kind() == "line" else "polygon"
                    fl = flat_cached(lyr, 0.0, kind, self._want_crs)
                    if fl is None:
                        line.append("flat=None")
                        continue
                    line.append("want=%d ready=%s" % (
                        getattr(_B, "wanted_count", lambda f: -1)(fl),
                        getattr(_B, "polys_ready", lambda f: False)(fl)))
                print("[子进程 debug] 收尾 steps=%d ring_adv=%r ring_tot=%r "
                      "vc.done=%s vc.adv=%r vc.tot=%r deferred=%r ｜ %s"
                      % (steps,
                         getattr(cv._qc_painter, "_ring_adv", None),
                         getattr(cv._qc_painter, "_ring_tot", None),
                         vc.get("done"), vc.get("adv"), vc.get("tot"),
                         getattr(cv._qc_painter, "stats", {}).get("deferred"),
                         " ｜ ".join(line) or "-"), flush=True)
            except Exception:
                exc_note("render @ ggis/render/cpu/render_proc.py:1966")
                import traceback
                traceback.print_exc()
        self._publish(seq, finished=True)
        return True

    def _publish(self, seq, finished=False, bump=True):
        b = self._ctrl.buf
        if bump:
            self._pub += 1
            struct.pack_into("q", b, 8, int(self._pub))
            struct.pack_into("q", b, 0, int(seq))
        if finished:
            struct.pack_into("q", b, 16, int(seq))
        return True

    def _superseded(self, seq):
        try:
            want = int(struct.unpack_from("q", self._ctrl.buf, 24)[0])
        except Exception:
            exc_note("_superseded @ ggis/render/cpu/render_proc.py:2010")
            return False
        return want > int(seq)


def scene_specs(project, layers=None):
    from ggis.core.crs import crs_key
    from ggis.render import labeling as LA
    from ggis.render import renderers as RE

    out = []
    try:
        layers = list(layers) if layers is not None else list(project.layers())
    except Exception:
        exc_note("scene_specs @ ggis/render/cpu/render_proc.py:2038")
        return None
    for lyr in layers:
        try:
            if lyr.is_tile():
                _ts = lyr.tile_source()
                if _ts is None or not _ts.is_valid():
                    return None
                out.append({
                    "key": _layer_key(lyr),
                    "source": lyr.source(),
                    "name": lyr.name(),
                    "type": "tile",
                    "crs": crs_key(lyr.crs()),
                    "visible": bool(lyr.is_visible()),
                    "opacity": float(lyr.opacity()),
                    "min_scale": float(lyr.scale_range()[0] or 0.0),
                    "max_scale": float(lyr.scale_range()[1] or 0.0),
                    "tile_source": _ts.to_dict(),
                })
                continue
            spec = {
                "key": _layer_key(lyr),
                "source": lyr.source(),
                "name": lyr.name(),
                "type": ("raster" if lyr.is_raster() else "vector"),
                "crs": crs_key(lyr.crs()),
                "visible": bool(lyr.is_visible()),
                "opacity": float(lyr.opacity()),
                "min_scale": float(lyr.scale_range()[0] or 0.0),
                "max_scale": float(lyr.scale_range()[1] or 0.0),
            }
            if lyr.is_raster():
                try:
                    from ggis.core.style import raster_display as _rd
                    spec["display"] = _rd.get_display(lyr).to_dict()
                except Exception:
                    exc_note("scene_specs @ ggis/render/cpu/render_proc.py:2093")
                    pass
            if lyr.is_vector():
                spec["renderer"] = RE.get_renderer(lyr).to_dict()
                try:
                    from ggis.io.vector_io import _CONTAINER_SUFFIXES as _CS
                    _sfx = os.path.splitext(str(spec["source"]))[1].lower()
                    if _sfx in _CS:
                        _sub = ""
                        try:
                            _sub = str(lyr.sub_layer() or "")
                        except Exception:
                            _log.exception("silent exception in scene_specs")
                        spec["layer"] = _sub or str(lyr.name() or "")
                except Exception:
                    exc_note("scene_specs @ ggis/render/cpu/render_proc.py:2120")
                    pass
                spec["label"] = LA.get_label_style(lyr).to_dict()
                if lyr.is_filtered():
                    spec["subset_expr"] = lyr.subset_expression() or ""
                    spec["subset_fids"] = list(lyr.subset_fids() or [])
                if not spec["source"]:
                    spec["memory"] = _memory_spec(lyr)
            if not spec["source"] and not spec.get("memory"):
                return None
            out.append(spec)
        except Exception:
            exc_note("scene_specs @ ggis/render/cpu/render_proc.py:2141")
            return None
    return out


def _as_crs(v):
    if v is None or not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return None
    try:
        from ...core.crs import GgsCoordinateReferenceSystem
        c = GgsCoordinateReferenceSystem.from_user_input(s)
        return c if c.is_valid() else None
    except Exception:
        exc_note("_as_crs @ ggis/render/cpu/render_proc.py:2186")
        return None


def scene_version(project, layers=None):
    from ggis.render.labeling import label_version
    from ggis.render.renderers import render_version
    try:
        from ggis.core.model.layer import (data_version as _data_version,
                                     source_generation as _src_gen,
                                     subset_generation as _subset_gen)
    except Exception:
        exc_note("scene_version @ ggis/render/cpu/render_proc.py:2210")
        def _data_version(_l):
            return 0
        def _src_gen(_l):
            return 0
        def _subset_gen(_l):
            return 0
    parts = []
    try:
        _lyrs = (list(layers) if layers is not None
                 else list(project.layers()))
    except Exception:
        exc_note("scene_version @ ggis/render/cpu/render_proc.py:2224")
        _lyrs = []
    try:
        for lyr in _lyrs:
            vec = bool(lyr.is_vector())
            parts.append((str(lyr.id()), lyr.source(), lyr.name(),
                          int(_src_gen(lyr)),
                          int(_data_version(lyr)),
                          bool(lyr.is_visible()),
                          round(float(lyr.opacity()), 4),
                          round(float(lyr.scale_range()[0] or 0.0), 4),
                          round(float(lyr.scale_range()[1] or 0.0), 4),
                          render_version(lyr),
                          label_version(lyr) if vec else 0,
                          bool(lyr.is_filtered()) if vec else False,
                          int(_subset_gen(lyr)) if vec else 0))
    except Exception:
        exc_note("scene_version @ ggis/render/cpu/render_proc.py:2275")
        return -1
    try:
        from ggis.core.crs import crs_key
        parts.append(("__dst_crs__", str(crs_key(settings.default_crs()) or "")))
    except Exception:
        exc_note("scene_version @ ggis/render/cpu/render_proc.py:2280")
        pass
    return hash(tuple(parts))


_NO_DST_CRS_NOTED = [False]


def _note_no_dst_crs():
    if _NO_DST_CRS_NOTED[0]:
        return
    _NO_DST_CRS_NOTED[0] = True
    msg = ("[渲染子进程] ⚠ 主进程没传来地图坐标系（crs 为空串）⇒ 本次渲染"
           "**不做任何 OTF**：同坐标系的栅格/矢量看着正常，但不同坐标系的"
           "在线瓦片会被按同坐标系摆放（位置错、缩放时会滑动）。")
    print(msg, flush=True)
    try:
        import logging
        logging.getLogger("gmagis").warning(msg)
    except Exception:
        exc_note("_note_no_dst_crs @ ggis/render/cpu/render_proc.py:2306")
        pass


def _worker(shm_ctrl, req_q, root):
    try:
        from ggis.app import setup_child as _setup_child
        _setup_child(console=False)
    except Exception:
        exc_note("_worker @ ggis/render/cpu/render_proc.py:2329")
        pass
    try:
        sh = _Sub(shm_ctrl, root, req_q=req_q)
    except Exception:
        exc_note("_worker @ ggis/render/cpu/render_proc.py:2333")
        import traceback
        traceback.print_exc()
        struct.pack_into("q", shared_memory.SharedMemory(
            name=shm_ctrl).buf, 0, -1)
        return
    print("[渲染子进程] 就绪 pid=%d" % os.getpid(), flush=True)
    sh.run()


class RenderClient(QObject):

    rendered = Signal(object, int, bool)
    lod_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ctx = None
        self._proc = None
        self._req_q = None
        self._shm_ctrl = None
        self._shm_img = None
        self._shm_bytes = 0
        self._img = None
        self._ww = (0, 0)

        self._want = None
        self._inflight = 0
        self._fin = 0
        self._pub = 0
        self.frames_delivered = 0
        self._scene_ver = -1
        self._scene_sent = -1
        self._scene_specs = None
        self._scene_crs = None
        self._surf_sent = None
        self._scene_ready = False
        self._tile_sent = set()
        self._want_scene_push = False
        self._want_settings = False
        self._fail_n = 0
        self.last_error = ""
        self._lod_build_seen = 0

        self._timer = QTimer(self)
        self._timer.setInterval(_POLL_MS)
        self._timer.timeout.connect(self._poll)

    def is_available(self):
        return self._proc is not None and self._proc.is_alive()

    def start(self):
        if self.is_available():
            return True
        import multiprocessing as mp
        # 渲染子进程本身是 daemon，不允许再派生子进程。子进程内在渲染瓦片 /
        # 加载图层时仍可能误走到这里（如 _ensure_proc → make_backend），
        # 直接返回失败，避免 "daemonic processes are not allowed to have children"。
        if getattr(mp.current_process(), "daemon", False):
            return False
        try:
            ctx = mp.get_context("spawn")
            self._ctx = ctx
            self._req_q = ctx.Queue()
            self._shm_ctrl = shared_memory.SharedMemory(create=True,
                                                        size=_CTRL_BYTES)
            struct.pack_into("q", self._shm_ctrl.buf, 0, 0)
            root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            _rexe = os.path.join(os.path.dirname(sys.executable),
                                 "GmaGISRender.exe")
            _use_rexe = os.path.isfile(_rexe)
            if _use_rexe:
                import multiprocessing.spawn as _mpspawn
                _prev_exe = _mpspawn.get_executable()
                _mpspawn.set_executable(_rexe)
            try:
                self._proc = ctx.Process(
                    target=_worker,
                    args=(self._shm_ctrl.name, self._req_q, root),
                    daemon=True)
                if os.environ.get("GGIS_RPROC_DEBUG"):
                    import multiprocessing as _mp
                    _cp = _mp.current_process()
                    print("[start] pid=%d name=%s daemon=%s alive=%s exe=%s"
                          % (os.getpid(), _cp.name, _cp.daemon,
                             self._proc.is_alive(),
                             _rexe if _use_rexe else sys.executable),
                          flush=True)
                self._proc.start()
            finally:
                if _use_rexe:
                    try:
                        _mpspawn.set_executable(_prev_exe)
                    except Exception:
                        exc_note("start @ ggis/render/cpu/render_proc.py:2464")
                        pass
            self._timer.start()
            self.last_error = ""
            self._surf_sent = None
            self._scene_sent = -1
            self._scene_ready = False
            self._inflight = self._fin = 0
            self._pub = 0
            self.frames_delivered = 0
            struct.pack_into("q", self._shm_ctrl.buf, 0, 0)
            struct.pack_into("q", self._shm_ctrl.buf, 8, 0)
            struct.pack_into("q", self._shm_ctrl.buf, 16, 0)
            struct.pack_into("q", self._shm_ctrl.buf, 24, 0)
            struct.pack_into("q", self._shm_ctrl.buf, 32, 0)
            self._lod_build_seen = 0
            return True
        except Exception as e:
            exc_note("start @ ggis/render/cpu/render_proc.py:2482")
            import traceback
            traceback.print_exc()
            self.last_error = "子进程启动失败: %r" % (e,)
            self._fail_n += 1
            return False

    def stop(self):
        self._timer.stop()
        try:
            if self._req_q is not None:
                self._req_q.put(None)
        except Exception:
            exc_note("stop @ ggis/render/cpu/render_proc.py:2494")
            pass
        try:
            if self._proc is not None:
                self._proc.join(0)
                if self._proc.is_alive():
                    self._proc.terminate()
        except Exception:
            exc_note("stop @ ggis/render/cpu/render_proc.py:2507")
            pass
        self._proc = None
        for attr in ("_shm_ctrl", "_shm_img"):
            shm = getattr(self, attr)
            try:
                if shm is not None:
                    shm.close()
                    shm.unlink()
            except Exception:
                exc_note("stop @ ggis/render/cpu/render_proc.py:2516")
                pass
            setattr(self, attr, None)
        self._img = None
        self._ww = (0, 0)
        self._surf_sent = None
        self._scene_sent = -1
        self._scene_ready = False
        self._inflight = self._fin = 0
        self._pub = 0

    def failed(self):
        return bool(self.last_error)

    def set_scene(self, version, specs, dst_crs=None):
        self._scene_ver = int(version)
        self._scene_specs = specs
        self._scene_crs = dst_crs

    def push_scene(self):
        if not self.is_available():
            self.start()
        self._want_scene_push = True

    def push_settings(self):
        if not self.is_available():
            self.start()
        self._want_settings = True

    def prefetch(self, src, layer=None):
        try:
            if not self.is_available():
                if not self.start():
                    return False
            self._req_q.put(("prefetch", str(src or ""), layer))
            return True
        except Exception:
            exc_note("prefetch @ ggis/render/cpu/render_proc.py:2585")
            return False

    def push_features(self, src, layer_name, wkbs, attrs):
        try:
            if not self.is_available():
                return False
            self._req_q.put(("set_features", str(src or ""),
                             str(layer_name or ""),
                             list(wkbs) if wkbs is not None else None,
                             list(attrs) if attrs is not None else None))
            return True
        except Exception:
            exc_note("push_features @ ggis/render/cpu/render_proc.py:2604")
            return False

    def push_tiles(self, records):
        if not records or not self.is_available():
            return 0
        fresh = []
        for rec in records:
            try:
                k = (rec[0], int(rec[1]), int(rec[2]), int(rec[3]))
            except Exception:
                exc_note("push_tiles @ ggis/render/cpu/render_proc.py:2618")
                continue
            if k in self._tile_sent:
                continue
            self._tile_sent.add(k)
            fresh.append(rec)
        if not fresh:
            return 0
        try:
            if len(self._tile_sent) > 40000:
                self._tile_sent.clear()
            self._req_q.put(("tiles", fresh))
        except Exception:
            exc_note("push_tiles @ ggis/render/cpu/render_proc.py:2630")
            return 0
        return len(fresh)

    def is_warm(self):
        return bool(self._scene_ready) and self.is_available()

    def request(self, seq, task):
        self._want = (int(seq), task)
        if not self.is_available():
            if not self.start():
                return False
        try:
            struct.pack_into("q", self._shm_ctrl.buf, 24, int(seq))
        except Exception:
            exc_note("request @ ggis/render/cpu/render_proc.py:2661")
            pass
        return True

    def invalidate(self):
        self._want = None

    def is_busy(self):
        return self._inflight > self._fin

    def warmup(self):
        return self.start()

    def _ensure_surface(self, task):
        w, h = task["size"]
        dpr = float(task.get("dpr") or 1.0)
        w_px = max(1, int(round(w * dpr)))
        h_px = max(1, int(round(h * dpr)))
        if self._img is not None and self._ww == (w_px, h_px):
            return False
        if self._shm_img is not None and w_px * h_px * 4 <= self._shm_bytes:
            self._wrap_surface(w_px, h_px, dpr)
            return False
        old = self._shm_img
        try:
            shm = shared_memory.SharedMemory(
                create=True, size=max(w_px * h_px * 4, 1 << 20))
        except Exception as e:
            exc_note("_ensure_surface @ ggis/render/cpu/render_proc.py:2705")
            self.last_error = "共享内存分配失败: %r" % (e,)
            return False
        self._shm_img = shm
        self._shm_bytes = int(shm.size)
        self._img = None
        self._ww = (0, 0)
        if old is not None:
            try:
                old.close()
                old.unlink()
            except Exception:
                exc_note("_ensure_surface @ ggis/render/cpu/render_proc.py:2716")
                pass
        self._wrap_surface(w_px, h_px, dpr)
        return True

    def _wrap_surface(self, w_px, h_px, dpr):
        try:
            self._img = QImage(self._shm_img.buf, int(w_px), int(h_px),
                               int(w_px) * 4,
                               QImage.Format.Format_ARGB32_Premultiplied)
            self._img.setDevicePixelRatio(float(dpr or 1.0))
            self._ww = (int(w_px), int(h_px))
        except Exception as e:
            exc_note("_wrap_surface @ ggis/render/cpu/render_proc.py:2734")
            self._img = None
            self._ww = (0, 0)
            self.last_error = "包装共享内存失败: %r" % (e,)

    def _poll(self):
        if self._shm_ctrl is None:
            return
        buf = self._shm_ctrl.buf
        try:
            seq = int(struct.unpack_from("q", buf, 0)[0])
            pub = int(struct.unpack_from("q", buf, 8)[0])
            fin = int(struct.unpack_from("q", buf, 16)[0])
        except Exception:
            exc_note("_poll @ ggis/render/cpu/render_proc.py:2752")
            return
        if seq == -1:
            self.last_error = "渲染子进程启动失败（见子进程输出的堆栈）"
            self._fail_n += 1
            self._timer.stop()
            return
        self._fin = fin
        try:
            _lod = int(struct.unpack_from("q", buf, 32)[0])
            if _lod != self._lod_build_seen:
                self._lod_build_seen = _lod
                self.lod_ready.emit()
        except Exception:
            exc_note("_poll @ ggis/render/cpu/render_proc.py:2766")
            pass
        is_final = (fin >= seq > 0)
        if seq == -3:
            self._scene_ready = True
            self._pub = pub
            try:
                self.lod_ready.emit()
            except Exception:
                exc_note("_poll @ ggis/render/cpu/render_proc.py:2789")
                pass
        elif seq == -2:
            self.last_error = "渲染子进程抛异常（见子进程输出的堆栈）"
            self._fail_n += 1
        elif pub > self._pub:
            self._pub = pub
            img = self._read_image()
            if img is not None:
                self.frames_delivered += 1
                try:
                    self.rendered.emit(img, seq, bool(is_final))
                except Exception:
                    exc_note("_poll @ ggis/render/cpu/render_proc.py:2802")
                    pass
        if self._inflight > self._fin:
            return
        if self._want_settings and self.is_available():
            self._want_settings = False
            try:
                self._req_q.put(("settings",))
            except Exception:
                exc_note("_poll @ ggis/render/cpu/render_proc.py:2815")
                self._want_settings = True
        if (self._want_scene_push and self._want is None
                and self._scene_ver != self._scene_sent
                and self.is_available()):
            self._want_scene_push = False
            try:
                self._req_q.put(("scene", self._scene_ver,
                                 self._scene_specs or [],
                                 self._scene_crs))
                self._scene_sent = self._scene_ver
                self._tile_sent.clear()
            except Exception:
                exc_note("_poll @ ggis/render/cpu/render_proc.py:2828")
                import traceback
                traceback.print_exc()
            return
        if self._scene_ver != self._scene_sent and self._want is not None:
            try:
                self._req_q.put(("scene", self._scene_ver,
                                 self._scene_specs or [],
                                 self._scene_crs))
                self._scene_sent = self._scene_ver
                self._tile_sent.clear()
            except Exception:
                exc_note("_poll @ ggis/render/cpu/render_proc.py:2839")
                import traceback
                traceback.print_exc()
                return
        if self._want is None:
            return
        seq_w, task = self._want
        self._want = None
        new_surf = self._ensure_surface(task)
        if self._img is None:
            self.last_error = self.last_error or "共享内存不可用"
            return
        try:
            _st = (self._shm_img.name, int(self._ww[0]), int(self._ww[1]))
            if new_surf or self._surf_sent != _st:
                self._req_q.put(("surface", _st[0], _st[1], _st[2]))
                self._surf_sent = _st
            self._req_q.put(("render", task))
        except Exception:
            exc_note("_poll @ ggis/render/cpu/render_proc.py:2862")
            import traceback
            traceback.print_exc()
            return
        self._inflight = seq_w

    def _read_image(self):
        if self._img is None or self._ww == (0, 0):
            return None
        try:
            return self._img.copy()
        except Exception:
            exc_note("_read_image @ ggis/render/cpu/render_proc.py:2881")
            return None



_BAND_WORKERS = min(3, max(1, (os.cpu_count() or 2) - 1))

_BAND_OVERLAP_PX = 8


class RenderPool(QObject):

    rendered = Signal(object, int, bool)
    lod_ready = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._k = max(1, int(_BAND_WORKERS))
        self._clients = []
        for i in range(self._k):
            c = RenderClient(self)
            c.rendered.connect(
                lambda img, seq, fin, _i=i: self._on_band(_i, img, seq, fin))
            c.lod_ready.connect(self._on_band_lod_ready)
            self._clients.append(c)
        self._seq = 0
        self._cur = {}
        self._ys = None
        self._geo = None
        self.frames_delivered = 0

    def is_available(self):
        return all(c.is_available() for c in self._clients)

    def start(self):
        ok = True
        for c in self._clients:
            ok = bool(c.start()) and ok
        return ok

    def warmup(self):
        return self.start()

    def stop(self):
        for c in self._clients:
            c.stop()

    def set_scene(self, version, specs, dst_crs=None):
        for c in self._clients:
            c.set_scene(version, specs, dst_crs)

    def push_scene(self):
        for c in self._clients:
            c.push_scene()

    def push_settings(self):
        for c in self._clients:
            c.push_settings()

    def push_tiles(self, records):
        n = 0
        for c in self._clients:
            n = max(n, int(c.push_tiles(records) or 0))
        return n

    def invalidate(self):
        for c in self._clients:
            c.invalidate()
        self._cur = {}

    @staticmethod
    def _split(task, k):
        w, h = int(task["size"][0]), int(task["size"][1])
        e = task["extent"]
        x0, y_min, x1, y_max = (float(e[0]), float(e[1]),
                                float(e[2]), float(e[3]))
        gh = (y_max - y_min) or 1.0
        base = h // k
        ys = []
        tasks = []
        for i in range(k):
            s0 = i * base
            s1 = (i + 1) * base if i < k - 1 else h
            o_top = 0 if i == 0 else _BAND_OVERLAP_PX
            o_bot = 0 if i == k - 1 else _BAND_OVERLAP_PX
            r0 = max(0, s0 - o_top)
            r1 = min(h, s1 + o_bot)
            if r1 - r0 < 1:
                r0, r1 = min(s0, h - 1), min(s0 + 1, h)
                o_top = s0 - r0
            top = y_max - (r0 / float(h)) * gh
            bot = y_max - (r1 / float(h)) * gh
            t = dict(task)
            t["size"] = (w, r1 - r0)
            t["extent"] = (x0, bot, x1, top)
            tasks.append(t)
            ys.append((s0, s1 - s0, s0 - r0))
        return tasks, ys

    def request(self, seq, task):
        seq = int(seq)
        tasks, ys = self._split(task, self._k)
        self._seq = seq
        self._cur = {}
        self._ys = ys
        w, h = int(task["size"][0]), int(task["size"][1])
        self._geo = (w, h, float(task.get("dpr") or 1.0),
                     tuple(task.get("color") or (255, 255, 255)))
        ok = True
        for c, t in zip(self._clients, tasks):
            ok = bool(c.request(seq, t)) and ok
        return ok

    def is_busy(self):
        return any(c.is_busy() for c in self._clients)

    def is_warm(self):
        return all(c.is_warm() for c in self._clients)

    def failed(self):
        return any(c.failed() for c in self._clients)

    @property
    def last_error(self):
        for c in self._clients:
            if c.failed() and c.last_error:
                return c.last_error
        return ""

    def _on_band(self, i, img, seq, fin):
        seq = int(seq)
        if seq <= 0 or seq != self._seq:
            return
        d = self._cur.setdefault(seq, {})
        d[i] = (img, bool(fin))
        if len(d) < self._k:
            return
        self._emit(seq)

    def _on_band_lod_ready(self):
        try:
            self.lod_ready.emit()
        except Exception:
            exc_note("_on_band_lod_ready @ ggis/render/cpu/render_proc.py:3075")
            pass

    def _emit(self, seq):
        d = self._cur.get(seq) or {}
        w, h, dpr, color = self._geo
        full = QImage(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))),
                      QImage.Format.Format_ARGB32_Premultiplied)
        full.setDevicePixelRatio(dpr)
        full.fill(QColor(*color))
        p = QPainter(full)
        try:
            for i in range(self._k):
                it = d.get(i)
                if it is None or it[0] is None:
                    continue
                paste_y, paste_h, skip = self._ys[i]
                src = QRectF(0.0, skip * dpr, w * dpr, paste_h * dpr)
                tgt = QRectF(0.0, float(paste_y), float(w), float(paste_h))
                p.drawImage(tgt, it[0], src)
        finally:
            p.end()
        final = all(bool(d.get(i, (None, False))[1]) for i in range(self._k))
        self.frames_delivered += 1
        try:
            self.rendered.emit(full, seq, final)
        except Exception:
            exc_note("_emit @ ggis/render/cpu/render_proc.py:3105")
            pass
