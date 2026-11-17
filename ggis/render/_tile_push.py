# -*- coding: utf-8 -*-

from ._canvas_cfg import _PROC_DEBUG
from ggis.core.model.layer import data_version as _dv
from ggis.core.app.i18n import tr as _tr
from ggis.common.util.exc_report import exc_note


class TilePushMixin:


    def tile_renderable(self, lyr):
        if lyr is None or not getattr(lyr, "is_tile", lambda: False)():
            return True
        if self.extent().is_empty():
            return True
        try:
            s = self._map_settings()
        except Exception:
            exc_note("tile_renderable @ ggis/render/map_canvas.py:960")
            return True
        try:
            got = self._tile_painter.needed_tiles(lyr, s)
        except Exception:
            exc_note("tile_renderable @ ggis/render/map_canvas.py:964")
            return False
        return got is not None

    def _prune_unrenderable_tiles(self):
        if self.extent().is_empty():
            return
        proj = getattr(self, "_project", None)
        if proj is None:
            return
        try:
            s = self._map_settings()
        except Exception:
            exc_note("_prune_unrenderable_tiles @ ggis/render/map_canvas.py:1015")
            return
        failed = []
        for lyr in self._layer_source():
            try:
                if not (lyr.is_tile() and lyr.is_visible()):
                    continue
                if self._tile_painter.needed_tiles(lyr, s) is None:
                    failed.append(lyr)
            except Exception:
                exc_note("_prune_unrenderable_tiles @ ggis/render/map_canvas.py:1024")
                continue
        if not failed:
            return
        names = [lyr.name() for lyr in failed if lyr.name()]
        if not names:
            return
        try:
            crs = self.effectiveCrs()
            auth = crs.authid() if crs else "?"
            self._notify(_tr(
                "以下在线瓦片在当前坐标系 {0} 下无法投影，已停止渲染"
                "（图层已保留）：\n{1}"
            ).format(auth, "\n".join(names)), "Warning")
        except Exception:
            exc_note("_prune_unrenderable_tiles @ ggis/render/map_canvas.py:1041")
            pass

    def _has_visible_tile(self):
        try:
            for lyr in self._layer_source():
                if lyr.is_tile() and lyr.is_visible():
                    return True
        except Exception:
            exc_note("_has_visible_tile @ ggis/render/map_canvas.py:2923")
            pass
        return False

    @staticmethod
    def _tile_record(source, sk, z, x, y):
        try:
            from .tiles import TileLoader
            img = TileLoader.cached_image(source, z, x, y)
            if img is None or img.isNull():
                TileLoader.image(source, z, x, y)
                return None
            w, h = int(img.width()), int(img.height())
            bpl = int(img.bytesPerLine())
            data = bytes(img.constBits())[: bpl * h]
            _fmt = img.format()
            fmt = int(getattr(_fmt, "value", _fmt))
            return (sk, int(z), int(x), int(y), w, h, bpl, fmt, data)
        except Exception as e:
            exc_note("_tile_record @ ggis/render/map_canvas.py:3247")
            if _PROC_DEBUG:
                print("[画布] `_tile_record` 打包失败 %r" % (e,), flush=True)
            return None

    def _proc_push_tiles(self, c):
        if c is None or not self._has_visible_tile():
            return 0
        try:
            s = self._map_settings()
        except Exception:
            exc_note("_proc_push_tiles @ ggis/render/map_canvas.py:2972")
            return 0
        if not s.is_ready():
            return 0
        recs = []
        for lyr in self._layer_source():
            try:
                if not (lyr.is_tile() and lyr.is_visible()):
                    continue
                if not self._in_scale(lyr, s):
                    continue
                got = self._tile_painter.needed_tiles(lyr, s)
            except Exception:
                exc_note("_proc_push_tiles @ ggis/render/map_canvas.py:2991")
                continue
            if got is None:
                continue
            source, keys = got
            sk = str(getattr(source, "key", "") or "")
            for (z, tx, ty) in keys:
                rec = self._tile_record(source, sk, z, tx, ty)
                if rec is not None:
                    recs.append(rec)
        if not recs:
            return 0
        try:
            return int(c.push_tiles(recs) or 0)
        except Exception:
            exc_note("_proc_push_tiles @ ggis/render/map_canvas.py:3005")
            return 0

    def _on_tile_ready(self, *a):
        try:
            if self._panning:
                return
            t = getattr(self, "_tile_tick", None)
            if t is None:
                self.update()
                return
            if not t.isActive():
                t.start()
        except Exception:
            exc_note("_on_tile_ready @ ggis/render/map_canvas.py:3029")
            self.update()

    def _on_tile_tick(self):
        try:
            if self._has_visible_tile():
                c = self._proc_usable()
                if c is not None:
                    n = self._proc_push_tiles(c)
                    if n:
                        self._tile_gen += 1
                        self._arm_render(immediate=True)
                        return
        except Exception:
            exc_note("_on_tile_tick @ ggis/render/map_canvas.py:3049")
            pass
        self.update()

    def prefetch_source(self, src, layer_name=None):
        try:
            b = self._ensure_proc()
            if b is None:
                return False
            return bool(b.prefetch(str(src or ""), layer_name))
        except Exception:
            exc_note("prefetch_source @ ggis/render/map_canvas.py:3257")
            return False

    def _edit_sync_features(self, c):
        try:
            from ggis.core.model.layer import data_version
        except Exception:
            exc_note("_edit_sync_features @ ggis/render/map_canvas.py:3594")
            return
        try:
            sync = getattr(self, "_edit_synced", None)
            if sync is None:
                sync = self._edit_synced = {}
            for lyr in self._layer_source():
                try:
                    if not lyr.is_vector():
                        continue
                    dv = int(_dv(lyr))
                    key = str(lyr.id())
                    if sync.get(key) == dv:
                        continue
                    try:
                        import numpy as _np
                        from shapely import to_wkb as _to_wkb
                        wkbs = _to_wkb(_np.array(list(lyr.geoms() or []),
                                                 dtype=object))
                        wkbs = [bytes(w) for w in wkbs]
                    except Exception:
                        exc_note("_edit_sync_features @ ggis/render/map_canvas.py:3615")
                        continue
                    attrs = list(lyr.attrs() or [])
                    if c.push_features(str(lyr.source() or ""),
                                       str(lyr.name() or ""),
                                       wkbs, attrs):
                        sync[key] = dv
                        self._edit_sync_failed = False
                    else:
                        self._edit_sync_failed = True
                        return
                except Exception:
                    exc_note("_edit_sync_features @ ggis/render/map_canvas.py:3627")
                    continue
        except Exception:
            exc_note("_edit_sync_features @ ggis/render/map_canvas.py:3629")
            import traceback
            traceback.print_exc()

    def prewarm_flat(self, force=False):
        from ..io import async_loader as async_io
        try:
            _p = self._proc
            _skip = bool(_p is not None and not _p.failed()
                         and getattr(_p, "builds_flat_in_subprocess", False))
        except Exception:
            exc_note("prewarm_flat @ ggis/render/map_canvas.py:6409")
            _skip = False
        if _skip:
            return
        for lyr in self._layer_source():
            try:
                if not lyr.is_vector() or not lyr.is_valid():
                    continue
                d = lyr.__dict__.get("_ggs_flat")
                if isinstance(d, dict) and d and not force:
                    continue
                if force and isinstance(d, dict) and d:
                    from ..render.cpu import backend as _B
                    from ..render.rasterize import flat_coords
                    kind = ("line" if lyr.base_kind() == "line"
                            else "polygon")
                    flat = flat_coords(lyr, 0.0, kind=kind,
                                       dst_crs=self.effectiveCrs())
                    if not flat:
                        continue
                    if not _B.wanted_count(flat) and _B.polys_ready(flat):
                        continue
            except Exception:
                exc_note("prewarm_flat @ ggis/render/map_canvas.py:6441")
                continue
            try:
                async_io.prewarm_flat_async(lyr, dst_crs=self.effectiveCrs())
            except Exception:
                exc_note("prewarm_flat @ ggis/render/map_canvas.py:6445")
                pass
