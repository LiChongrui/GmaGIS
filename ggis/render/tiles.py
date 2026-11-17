# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import math
import os
import logging
import threading
import time
import urllib.request

from PySide6.QtCore import QObject, QPointF, QRunnable, QRectF, QThreadPool, Signal
from PySide6.QtGui import QImage, QPainter, QPolygonF, QTransform

from ..app_paths import ensure_dir, tile_cache_dir
from ..core.crs import (GgsCrs, convert_bounds, crs_transformer,
                        needs_reproject)
from ggis.core.crs.extent import GgsRectangle
from .cache import LRU

_log = logging.getLogger("gmagis")

_QUAD_TOL_PX = 1.0
_QUAD_TILES = True
_QUAD_OVERLAP_PX = 2.0

_NL_TOL_PX = 0.6
_NL_MAX_ROWS = 64

_MESH_TOL_PX = 0.5
_MESH_MAX = 32

_CACHE_GEN = 0


def _bump_cache_gen():
    global _CACHE_GEN
    _CACHE_GEN += 1


def tile_cache_gen():
    return _CACHE_GEN

__all__ = ["TileLoader", "GgsTilePainter", "tileReadySignal",
           "clear_tile_cache"]

_TILE_DBG = bool(os.environ.get("GGIS_TILE_DEBUG"))
_MISS_CRS = [0]
_MISS_LOGGED = set()


def _as_crs(v):
    if v is None or not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return None
    try:
        c = GgsCrs.from_user_input(s)
        return c if c.is_valid() else None
    except Exception:
        exc_note("_as_crs @ ggis/render/tiles.py:104")
        return None


_FRAME_LOG_GAP = 1.2
_FRAME_LOG_LAST = [0.0]

_WHY_LOG_GAP = 2.0
_WHY_LOG_LAST = {}


def _note_frame(source, z, rng, dst_crs, drawn=None, miss=None, view_w=None,
                out_w=None, skipped=None, missing=None):
    import time as _t
    now = _t.time()
    if not _TILE_DBG and (now - _FRAME_LOG_LAST[0]) < _FRAME_LOG_GAP:
        return
    _FRAME_LOG_LAST[0] = now
    try:
        x0, y0, x1, y1 = rng
        _msg = ("[瓦片·帧] key=%s z=%d x %d..%d y %d..%d dst=%s"
                % (getattr(source, "key", "?"), int(z), int(x0), int(x1),
                   int(y0), int(y1),
                   getattr(dst_crs, "authid", lambda: dst_crs)()))
        if view_w is not None and out_w is not None:
            _msg += " view_w=%.1f/out_w=%.1f" % (float(view_w), float(out_w))
        if drawn is not None:
            _msg += " 画上 %d 张/缺 %d 张" % (int(drawn), int(miss or 0))
        if skipped is not None:
            try:
                _msg += " 跳过 计划%d/空框%d" % (int(skipped[0]),
                                                int(skipped[1]))
            except Exception:
                exc_note("_note_frame @ ggis/render/tiles.py:146")
                pass
        if missing:
            _msg += " 缺片[%s]" % missing
    except Exception:
        exc_note("_note_frame @ ggis/render/tiles.py:150")
        return
    if _TILE_DBG:
        print(_msg, flush=True)
    if miss or (drawn is not None and int(drawn) == 0):
        try:
            import logging
            logging.getLogger("gmagis").info(_msg)
        except Exception:
            exc_note("_note_frame @ ggis/render/tiles.py:166")
            pass


def _note_why(reason, **kw):
    import time as _t
    now = _t.time()
    if (now - _WHY_LOG_LAST.get(reason, 0.0)) < _WHY_LOG_GAP:
        return
    _WHY_LOG_LAST[reason] = now
    try:
        _msg = "[瓦片·不画] %s" % reason
        for k in sorted(kw):
            _msg += " %s=%s" % (k, kw[k])
    except Exception:
        exc_note("_note_why @ ggis/render/tiles.py:189")
        return
    if _TILE_DBG:
        print(_msg, flush=True)
    try:
        import logging
        logging.getLogger("gmagis").info(_msg)
    except Exception:
        exc_note("_note_why @ ggis/render/tiles.py:196")
        pass


def _note_missing_crs(src_crs, dst_crs):
    _MISS_CRS[0] += 1
    key = (str(src_crs), str(dst_crs))
    first = key not in _MISS_LOGGED
    if first:
        _MISS_LOGGED.add(key)
    if not (_TILE_DBG or first):
        return
    msg = ("[瓦片] ⚠ 缺 CRS ⇒ 按「同一坐标系」处理（视野若不是瓦片坐标系就会错位）"
           "：src=%r dst=%r" % (src_crs, dst_crs))
    print(msg, flush=True)
    if first:
        try:
            import logging
            logging.getLogger("gmagis").warning(msg)
        except Exception:
            exc_note("_note_missing_crs @ ggis/render/tiles.py:230")
            pass

_MEM_TILES = 160
_PREVIEW_LEVELS = 3
_DOWNLOAD_THREADS = 6
_TIMEOUT = 10.0
_FAIL_COOLDOWN = 30.0
_CACHE_LIMIT = 30000
_PRUNE_EVERY = 512

_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) GmaGIS/1.0 "
               "(desktop GIS tile client)")


class _TileEmitter(QObject):
    tileReady = Signal()


_EMITTER = _TileEmitter()


def tileReadySignal():
    return _EMITTER.tileReady


_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        p = QThreadPool()
        p.setMaxThreadCount(_DOWNLOAD_THREADS)
        _POOL = p
    return _POOL


def shutdown(wait_ms=3000):
    global _POOL
    p = _POOL
    if p is None:
        return
    try:
        p.clear()
    except Exception:
        exc_note("shutdown @ ggis/render/tiles.py:287")
        pass
    try:
        p.waitForDone(int(wait_ms))
    except Exception:
        exc_note("shutdown @ ggis/render/tiles.py:291")
        pass
    _POOL = None


def _http_get(url, headers):
    hdr = {"User-Agent": _USER_AGENT, "Accept": "image/*,*/*;q=0.8"}
    for k, v in (headers or {}).items():
        hdr[str(k)] = str(v)
    req = urllib.request.Request(str(url), headers=hdr)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read()


class _FetchTask(QRunnable):

    def __init__(self, source, z, x, y, key):
        super().__init__()
        self.setAutoDelete(True)
        self._src = source
        self._z = int(z)
        self._x = int(x)
        self._y = int(y)
        self._key = key

    def run(self):
        img = None
        try:
            url = self._src.url_for(self._z, self._x, self._y)
            data = _http_get(url, self._src.headers)
            if data:
                img = QImage.fromData(data)
                if img is None or img.isNull():
                    img = None
                else:
                    TileLoader._store_disk(self._key, data)
        except (urllib.error.URLError, OSError, TimeoutError) as _e:
            _log.warning("tile fetch failed (network): %s", _e)
            img = None
        except Exception:
            exc_note("run @ ggis/render/tiles.py")
            img = None
        try:
            TileLoader._finish(self._key, img)
        except Exception:
            exc_note("run @ ggis/render/tiles.py:333")
            pass
        try:
            _EMITTER.tileReady.emit()
        except Exception:
            exc_note("run @ ggis/render/tiles.py:337")
            pass


class TileLoader:

    _mem = LRU(_MEM_TILES)
    _lock = threading.RLock()
    _pending = set()
    _failed = {}
    _writes = 0
    _stats = {"hit_mem": 0, "hit_disk": 0, "miss": 0, "failed": 0,
              "fetched": 0}

    @staticmethod
    def _key(source, z, x, y):
        return (source.key, int(z), int(x), int(y))

    @staticmethod
    def _disk_path(key):
        sk, z, x, y = key
        return os.path.join(tile_cache_dir(), sk, str(z), str(x),
                            "%d.bin" % y)

    @staticmethod
    def image(source, z, x, y):
        if source is None or not source.is_valid():
            return None
        z = source.clamp_zoom(z)
        if z < 0 or x < 0 or y < 0 or x >= (1 << z) or y >= (1 << z):
            return None
        return TileLoader._get(source, z, x, y, schedule=True)

    @staticmethod
    def cached_image(source, z, x, y):
        if source is None or not source.is_valid():
            return None
        z = int(z)
        if z < 0 or x < 0 or y < 0 or x >= (1 << z) or y >= (1 << z):
            return None
        return TileLoader._get(source, z, x, y, schedule=False)

    @staticmethod
    def _get(source, z, x, y, schedule):
        key = TileLoader._key(source, z, x, y)
        with TileLoader._lock:
            img = TileLoader._mem.get(key)
            if img is not None:
                TileLoader._stats["hit_mem"] += 1
                return img
        img = TileLoader._read_disk(key)
        if img is not None:
            with TileLoader._lock:
                TileLoader._mem.get(key, lambda: img)
                TileLoader._stats["hit_disk"] += 1
            return img
        with TileLoader._lock:
            TileLoader._stats["miss"] += 1
            if not schedule:
                return None
            t = TileLoader._failed.get(key)
            if t is not None and (time.time() - t) < _FAIL_COOLDOWN:
                return None
            if key in TileLoader._pending:
                return None
            TileLoader._pending.add(key)
        try:
            _pool().start(_FetchTask(source, z, x, y, key))
        except Exception:
            exc_note("_get @ ggis/render/tiles.py:414")
            with TileLoader._lock:
                TileLoader._pending.discard(key)
        return None

    @staticmethod
    def _finish(key, img):
        with TileLoader._lock:
            TileLoader._pending.discard(key)
            if img is None:
                TileLoader._failed[key] = time.time()
                TileLoader._stats["failed"] += 1
                return
            TileLoader._failed.pop(key, None)
            TileLoader._mem.get(key, lambda: img)
            TileLoader._stats["fetched"] += 1
            _bump_cache_gen()

    @staticmethod
    def _read_disk(key):
        try:
            path = TileLoader._disk_path(key)
            if not os.path.exists(path):
                return None
            with open(path, "rb") as f:
                data = f.read()
            img = QImage.fromData(data) if data else None
            return img if (img is not None and not img.isNull()) else None
        except Exception:
            exc_note("_read_disk @ ggis/render/tiles.py:443")
            return None

    @staticmethod
    def _store_disk(key, data):
        path = TileLoader._disk_path(key)
        ensure_dir(os.path.dirname(path))
        # 临时文件名带 pid+线程号：主进程与渲染子进程并发写同一缓存目录，
        # 固定 ".part" 名会互相覆盖、互撞。
        tmp = "%s.%d.%d.part" % (path, os.getpid(), threading.get_ident())
        try:
            with open(tmp, "wb") as f:
                f.write(data)
        except Exception:
            exc_note("_store_disk tmp @ ggis/render/tiles.py")
            try:
                os.unlink(tmp)
            except OSError:
                exc_note("_store_disk tmp-unlink @ ggis/render/tiles.py")
            return
        # Windows：os.replace 需要目标文件未被任何句柄占用；目标正被
        # 读句柄打开（另一线程/渲染子进程/杀软扫描）时报 PermissionError，
        # 属瞬时竞争，短暂重试是标准处理。重试耗尽仍失败则留痕放弃——
        # 该瓦片已在内存缓存，只损失下次加载速度，不影响显示。
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 4:
                    _log.warning("瓦片缓存落盘被占用，放弃：%s", path)
                    try:
                        os.unlink(tmp)
                    except OSError:
                        exc_note("_store_disk unlink @ ggis/render/tiles.py")
                    return
                time.sleep(0.02 * (attempt + 1))
            except Exception:
                exc_note("_store_disk replace @ ggis/render/tiles.py")
                try:
                    os.unlink(tmp)
                except OSError:
                    exc_note("_store_disk unlink @ ggis/render/tiles.py")
                return
        with TileLoader._lock:
            TileLoader._writes += 1
            due = (TileLoader._writes % _PRUNE_EVERY) == 0
        if due:
            TileLoader._prune()

    @staticmethod
    def _prune():
        root = tile_cache_dir()
        try:
            files = []
            for dirpath, _dirs, names in os.walk(root):
                for n in names:
                    if not n.endswith(".bin"):
                        continue
                    p = os.path.join(dirpath, n)
                    try:
                        files.append((os.path.getmtime(p), p))
                    except Exception:
                        exc_note("_prune @ ggis/render/tiles.py:476")
                        continue
            if len(files) <= _CACHE_LIMIT:
                return
            files.sort()
            for _t, p in files[:len(files) - _CACHE_LIMIT // 2]:
                try:
                    os.remove(p)
                except Exception:
                    exc_note("_prune @ ggis/render/tiles.py:484")
                    pass
        except Exception:
            exc_note("_prune @ ggis/render/tiles.py:486")
            pass

    @staticmethod
    def stats():
        with TileLoader._lock:
            d = dict(TileLoader._stats)
            d["pending"] = len(TileLoader._pending)
            d["failed_keys"] = len(TileLoader._failed)
            d["mem"] = TileLoader._mem.stats()
        return d

    @staticmethod
    def clear_memory():
        with TileLoader._lock:
            TileLoader._mem.clear()
        _bump_cache_gen()

    @staticmethod
    def clear_disk():
        root = tile_cache_dir()
        try:
            for dirpath, _dirs, names in os.walk(root, topdown=False):
                for n in names:
                    try:
                        os.remove(os.path.join(dirpath, n))
                    except Exception:
                        exc_note("clear_disk @ ggis/render/tiles.py:512")
                        pass
        except Exception:
            exc_note("clear_disk @ ggis/render/tiles.py:514")
            pass
        TileLoader.clear_memory()


def clear_tile_cache(disk=True):
    TileLoader.clear_memory()
    if disk:
        TileLoader.clear_disk()


class GgsTilePainter:

    MAX_TILES = 600

    def __init__(self):
        self._tile_crs = {}
        self._provider = None
        self._ext_gen = None
        self._warp = {}
        self._warp_view = None

    def set_provider(self, fn):
        self._provider = fn

    def clear_provider(self):
        self._provider = None

    def set_ext_gen(self, fn):
        self._ext_gen = fn

    def _image(self, source, z, x, y):
        if self._provider is not None:
            try:
                return self._provider(source, z, x, y)
            except Exception:
                exc_note("_image @ ggis/render/tiles.py:566")
                return None
        return TileLoader.image(source, z, x, y)

    def _cached(self, source, z, x, y):
        if self._provider is not None:
            try:
                return self._provider(source, z, x, y)
            except Exception:
                exc_note("_cached @ ggis/render/tiles.py:575")
                return None
        return TileLoader.cached_image(source, z, x, y)


    def _view_grid(self, layer, settings):
        if settings is None or not settings.is_ready():
            _note_why("settings未就绪")
            return None
        source = layer.tile_source() if layer is not None else None
        if source is None or not source.is_valid():
            _note_why("瓦片源无效", key=(getattr(source, "key", None) or "?"))
            return None
        tile_crs = self._crs_object(source)
        matrix = source.matrix()
        dst_crs = _as_crs(settings.destination_crs())
        if dst_crs is None:
            _note_missing_crs(dst_crs, tile_crs)
            _note_why("地图CRS缺失",
                      tile=getattr(tile_crs, "authid", lambda: "?")())
            return None
        view = self._to_tile_crs(settings.extent(), dst_crs, tile_crs)
        if view is None or view.is_empty():
            _note_why("视野换算到瓦片CRS失败",
                      dst=getattr(dst_crs, "authid", lambda: "?")(),
                      tile=getattr(tile_crs, "authid", lambda: "?")(),
                      ext="(%.6g,%.6g,%.6g,%.6g)" % (settings.extent().xmin,
                                                     settings.extent().ymin,
                                                     settings.extent().xmax,
                                                     settings.extent().ymax))
            return None
        view = view.intersect(matrix.world())
        if view is None or view.is_empty():
            _note_why("视野与瓦片世界无交集",
                      dst=getattr(dst_crs, "authid", lambda: "?")(),
                      world="(%.6g,%.6g,%.6g,%.6g)" % (matrix.world().xmin,
                                                       matrix.world().ymin,
                                                       matrix.world().xmax,
                                                       matrix.world().ymax))
            return None
        out_w = max(1.0, settings.output_width())
        z = matrix.zoom_for_resolution(view.width() / out_w,
                                       source.min_zoom, source.max_zoom)
        x0, y0, x1, y1 = matrix.tile_range(z, view)
        if x1 < x0 or y1 < y0:
            _note_why("行列范围为空", z=int(z),
                      view_w="%.6g" % view.width(), out_w="%.1f" % out_w)
            return None
        if (x1 - x0 + 1) * (y1 - y0 + 1) > self.MAX_TILES:
            _note_why("瓦片数超过上限", z=int(z),
                      n=(x1 - x0 + 1) * (y1 - y0 + 1), 上限=int(self.MAX_TILES))
            return None
        if _TILE_DBG:
            _who = "子进程画" if self._provider is not None else "主进程要"
            _msg = ("[瓦片·选格 %s] key=%s z=%d x %d..%d y %d..%d "
                    "tile_crs=%s dst=%s view_w=%.6f out_w=%.1f"
                    % (_who, source.key, z, x0, x1, y0, y1,
                       getattr(tile_crs, "authid", lambda: tile_crs)(),
                       getattr(dst_crs, "authid", lambda: dst_crs)(),
                       view.width(), out_w))
            print(_msg, flush=True)
            try:
                import logging
                logging.getLogger("gmagis").info(_msg)
            except Exception:
                exc_note("_view_grid @ ggis/render/tiles.py:674")
                pass
        if _TILE_DBG:
            _note_frame(source, z, (x0, y0, x1, y1), dst_crs,
                        view_w=view.width(), out_w=out_w)
        return (source, matrix, tile_crs, dst_crs, z, x0, y0, x1, y1)

    def needed_tiles(self, layer, settings):
        got = self._view_grid(layer, settings)
        if got is None:
            return None
        source, _m, _tc, _dc, z, x0, y0, x1, y1 = got
        keys = []
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                keys.append((z, tx, ty))
        return source, keys

    def _crs_object(self, source):
        got = self._tile_crs.get(source.key)
        if got is not None:
            return got
        got = _as_crs(getattr(source, "crs", None))
        if got is not None:
            self._tile_crs[source.key] = got
        return got

    @staticmethod
    def _convert(rect, src_crs, dst_crs):
        if rect is None:
            return rect
        if src_crs is None or dst_crs is None:
            _note_missing_crs(src_crs, dst_crs)
            return rect
        if not needs_reproject(src_crs, dst_crs):
            return rect
        b = convert_bounds((rect.xmin, rect.ymin, rect.xmax, rect.ymax),
                           crs_transformer(src_crs, dst_crs))
        if b is None:
            return None
        return GgsRectangle(b[0], b[1], b[2], b[3])

    def _to_tile_crs(self, rect, dst_crs, tile_crs):
        if dst_crs is None or tile_crs is None:
            return None
        if not needs_reproject(dst_crs, tile_crs):
            return rect
        tf = crs_transformer(dst_crs, tile_crs)
        if tf is None:
            return None
        back = crs_transformer(tile_crs, dst_crs)
        if back is None:
            return None
        try:
            nx = ny = 32
            xs, ys = [], []
            for i in range(nx + 1):
                for j in range(ny + 1):
                    xs.append(rect.xmin
                              + (rect.xmax - rect.xmin) * (i / nx))
                    ys.append(rect.ymin
                              + (rect.ymax - rect.ymin) * (j / ny))
            px, py = tf.transform(xs, ys)
            try:
                bx, by = back.transform(px, py)
            except Exception:
                exc_note("_to_tile_crs @ ggis/render/tiles.py:792")
                return None
            _span = max(abs(rect.xmax - rect.xmin),
                        abs(rect.ymax - rect.ymin), 1.0)
            _tol = _span * 1e-6
            fx, fy = [], []
            for _i in range(len(xs)):
                _a, _b = px[_i], py[_i]
                if not (math.isfinite(_a) and math.isfinite(_b)):
                    continue
                if not (math.isfinite(bx[_i]) and math.isfinite(by[_i])):
                    continue
                if (abs(float(bx[_i]) - xs[_i]) > _tol
                        or abs(float(by[_i]) - ys[_i]) > _tol):
                    continue
                fx.append(_a); fy.append(_b)
            if not fx:
                return None
            return GgsRectangle(min(fx), min(fy), max(fx), max(fy))
        except Exception:
            exc_note("_to_tile_crs @ ggis/render/tiles.py:811")
            return None

    def _from_tile_crs(self, rect, dst_crs, tile_crs):
        return self._convert(rect, tile_crs, dst_crs)

    def draw(self, painter, layer, settings, opacity=None):
        got = self._view_grid(layer, settings)
        if got is None:
            return False
        (source, matrix, tile_crs, dst_crs,
         z, x0, y0, x1, y1) = got

        op = layer.opacity() if opacity is None else opacity
        try:
            op = max(0.0, min(1.0, float(op)))
        except Exception:
            exc_note("draw @ ggis/render/tiles.py:838")
            op = 1.0

        try:
            _dpr = self._painter_dpr(painter)
        except Exception:
            exc_note("draw @ ggis/render/tiles.py:844")
            _dpr = 1.0
        _sz = settings.output_size()
        _w_dev = max(1, int(round(float(_sz.width()) * _dpr)))
        _h_dev = max(1, int(round(float(_sz.height()) * _dpr)))
        try:
            from ..core.crs import crs_key as _crs_key
            _e = settings.extent()
            _vsig = (str(_crs_key(dst_crs) if dst_crs is not None else ""),
                     round(float(_e.xmin), 6), round(float(_e.ymin), 6),
                     round(float(_e.xmax), 6), round(float(_e.ymax), 6),
                     int(_sz.width()), int(_sz.height()), round(_dpr, 3))
        except Exception:
            exc_note("draw @ ggis/render/tiles.py:856")
            _vsig = None
        try:
            _tgen = int(self._ext_gen()) if self._ext_gen is not None \
                else _CACHE_GEN
        except Exception:
            _log.warning("ggs-tiles: ext tile gen query failed",
                       exc_info=True)
            _tgen = 0
        _ckey = (str(source), int(z), _vsig, int(round(op * 1000)), _tgen)
        if _vsig is not None and self._warp_view != _vsig:
            self._warp = {}
            self._warp_view = _vsig
        _hit = (_vsig is not None and _ckey in self._warp)
        _off = self._warp[_ckey][0] if _hit else None

        drawn = 0
        tried = 0
        skip_plan = 0
        skip_rect = 0
        miss_keys = []
        total = max(0, (x1 - x0 + 1) * (y1 - y0 + 1))
        if _off is None:
            _off = QImage(_w_dev, _h_dev,
                          QImage.Format.Format_ARGB32_Premultiplied)
            _off.setDevicePixelRatio(_dpr)
            _off.fill(0)
            qp = QPainter(_off)
            try:
                qp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                                 False)
                if op < 1.0:
                    qp.setOpacity(op)
                for ty in range(y0, y1 + 1):
                    for tx in range(x0, x1 + 1):
                        from .layer_plan import plan_for as _plan_for
                        _tb = matrix.tile_bounds(z, tx, ty)
                        _pl = _plan_for(None, settings, mode="tile_source",
                                        force_extent=_tb,
                                        force_crs=tile_crs)
                        if _pl is None or _pl.out_of_data:
                            skip_plan += 1
                            continue
                        rect = settings.map_to_pixel_rect(_pl.rect_extent)
                        if rect.isEmpty():
                            skip_rect += 1
                            continue
                        rect = self._snap_rect(qp, rect)
                        if rect.isEmpty():
                            skip_rect += 1
                            continue
                        quad = self._tile_quad(settings, _tb, tile_crs, dst_crs)
                        if quad is None and needs_reproject(tile_crs, dst_crs):
                            continue
                        rows = None
                        _use_quad = (bool(_QUAD_TILES) and quad is not None
                                     and self._quad_deviation(quad, rect)
                                     > _QUAD_TOL_PX)
                        if not _use_quad:
                            _n, rows = self._warp_rows(settings, _tb, tile_crs,
                                                      dst_crs, rect, dpr=_dpr)
                        tried += 1
                        if _use_quad:
                            _ok = self._draw_one_mesh(
                                qp, source, z, tx, ty, _tb, tile_crs,
                                dst_crs, settings, rect, quad)
                        else:
                            _ok = self._draw_one(qp, source, z, tx, ty,
                                                 rect, quad, rows)
                        if _ok:
                            drawn += 1
                        elif len(miss_keys) < 8:
                            miss_keys.append("%d/%d/%d"
                                             % (int(z), int(tx), int(ty)))
            finally:
                qp.end()
            if _vsig is not None:
                self._warp[_ckey] = (_off, drawn, list(miss_keys),
                                     skip_plan, skip_rect)
        else:
            _off, drawn, miss_keys, skip_plan, skip_rect = self._warp[_ckey]
            miss_keys = list(miss_keys)
        try:
            painter.drawImage(0, 0, _off)
        except Exception:
            exc_note("draw @ ggis/render/tiles.py:967")
            pass
        _note_frame(source, z, (x0, y0, x1, y1), dst_crs,
                    drawn=drawn, miss=max(0, total - drawn),
                    skipped=(skip_plan, skip_rect),
                    missing=",".join(miss_keys))
        return (drawn > 0) or _hit

    def _tile_quad(self, settings, tile_bounds, tile_crs, dst_crs):
        tf = crs_transformer(tile_crs, dst_crs)
        if tf is None:
            return None
        xs = [tile_bounds.xmin, tile_bounds.xmax,
              tile_bounds.xmax, tile_bounds.xmin]
        ys = [tile_bounds.ymax, tile_bounds.ymax,
              tile_bounds.ymin, tile_bounds.ymin]
        try:
            px, py = tf.transform(xs, ys)
        except Exception:
            exc_note("_tile_quad @ ggis/render/tiles.py:1004")
            return None
        try:
            back_tf = crs_transformer(dst_crs, tile_crs)
            if back_tf is not None:
                bx, by = back_tf.transform(px, py)
                fx, fy = tf.transform(bx, by)
                _sx = max(1.0, abs(float(max(px)) - float(min(px))))
                _sy = max(1.0, abs(float(max(py)) - float(min(py))))
                for i in range(4):
                    if not (math.isfinite(fx[i]) and math.isfinite(fy[i])):
                        return None
                    if (abs(float(fx[i]) - float(px[i])) > _sx * 1e-4
                            or abs(float(fy[i]) - float(py[i])) > _sy * 1e-4):
                        return None
        except Exception:
            exc_note("_tile_quad @ ggis/render/tiles.py:1025")
            return None
        pts = []
        for _x, _y in zip(px, py):
            try:
                _xf, _yf = float(_x), float(_y)
            except Exception:
                exc_note("_tile_quad @ ggis/render/tiles.py:1031")
                return None
            if not (math.isfinite(_xf) and math.isfinite(_yf)):
                return None
            d = settings.map_to_pixel(_xf, _yf)
            pts.append(QPointF(float(d.x()), float(d.y())))
        return pts

    @staticmethod
    def _quad_deviation(quad, rect):
        x0, y0 = rect.x(), rect.y()
        x1, y1 = x0 + rect.width(), y0 + rect.height()
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        worst = 0.0
        for q, c in zip(quad, corners):
            worst = max(worst, math.hypot(q.x() - c[0], q.y() - c[1]))
        return worst

    @staticmethod
    def _painter_dpr(painter):
        try:
            td = painter.deviceTransform()
            if abs(td.m12()) > 1e-9 or abs(td.m21()) > 1e-9:
                return 1.0
            s = float(td.m22())
            if not math.isfinite(s) or s <= 0.0:
                return 1.0
            return s
        except Exception:
            exc_note("_painter_dpr @ ggis/render/tiles.py:1069")
            return 1.0

    @staticmethod
    def _snap_rect(painter, rect):
        try:
            td = painter.deviceTransform()
            if abs(td.m12()) > 1e-9 or abs(td.m21()) > 1e-9:
                return rect
            sx, sy = float(td.m11()), float(td.m22())
            tx, ty = float(td.m31()), float(td.m32())
            if not all(math.isfinite(v) for v in (sx, sy, tx, ty)):
                return rect
            if sx <= 0.0 or sy <= 0.0:
                return rect
            x0 = round(rect.left() * sx + tx)
            x1 = round(rect.right() * sx + tx)
            y0 = round(rect.top() * sy + ty)
            y1 = round(rect.bottom() * sy + ty)
            if x1 <= x0 or y1 <= y0:
                return rect
            return QRectF((x0 - tx) / sx, (y0 - ty) / sy,
                          (x1 - x0) / sx, (y1 - y0) / sy)
        except Exception:
            exc_note("_snap_rect @ ggis/render/tiles.py:1109")
            return rect

    def _warp_rows(self, settings, tile_bounds, tile_crs, dst_crs, rect,
                   dpr=1.0):
        tf = crs_transformer(tile_crs, dst_crs)
        if tf is None or rect is None:
            return 0, None
        try:
            h = float(tile_bounds.height())
            mid_x = (tile_bounds.xmin + tile_bounds.xmax) / 2.0
        except Exception:
            exc_note("_warp_rows @ ggis/render/tiles.py:1143")
            return 0, None
        if not (h > 0):
            return 0, None
        dev = 0.0
        fs = (0.25, 0.5, 0.75)
        try:
            _px, _py = tf.transform([mid_x] * len(fs),
                                    [tile_bounds.ymax - f * h for f in fs])
        except Exception:
            exc_note("_warp_rows @ ggis/render/tiles.py:1154")
            return 0, None
        for f, _x, _y in zip(fs, _px, _py):
            try:
                d = settings.map_to_pixel(float(_x), float(_y))
            except Exception:
                exc_note("_warp_rows @ ggis/render/tiles.py:1159")
                return 0, None
            if not (math.isfinite(d.x()) and math.isfinite(d.y())):
                return 0, None
            dev = max(dev, abs(d.y() - (rect.top() + f * rect.height())))
        if dev <= _NL_TOL_PX:
            return 0, None
        need = max(4, int(math.ceil(dev / _NL_TOL_PX)) * 2)
        n = 4
        while n < need and n < _NL_MAX_ROWS:
            n *= 2
        try:
            _bx, _by = tf.transform([mid_x] * (n + 1),
                                    [tile_bounds.ymax - (i / float(n)) * h
                                     for i in range(n + 1)])
        except Exception:
            exc_note("_warp_rows @ ggis/render/tiles.py:1186")
            return 0, None
        dp = float(dpr) if (dpr and math.isfinite(float(dpr))
                            and float(dpr) > 0.0) else 1.0
        dev = []
        for i in range(n + 1):
            try:
                ey = settings.map_to_pixel(float(_bx[i]), float(_by[i])).y()
            except Exception:
                exc_note("_warp_rows @ ggis/render/tiles.py:1194")
                return 0, None
            if not math.isfinite(ey):
                return 0, None
            dev.append(int(round(ey * dp)))
        for i in range(1, n + 1):
            if dev[i] < dev[i - 1]:
                dev[i] = dev[i - 1]
        rows = []
        start_f = 0.0
        for i in range(n):
            if dev[i + 1] <= dev[i]:
                continue
            rows.append((start_f, (i + 1) / float(n),
                         dev[i] / dp, dev[i + 1] / dp))
            start_f = (i + 1) / float(n)
        return (len(rows), rows) if rows else (0, None)

    def _blit_rows(self, painter, img, sub, rect, rows):
        if sub is None:
            sx0, sy0 = 0.0, 0.0
            sw, sh = float(img.width()), float(img.height())
        else:
            sx0, sy0 = float(sub.x()), float(sub.y())
            sw, sh = float(sub.width()), float(sub.height())
        dx0, dx1 = float(rect.left()), float(rect.right())
        for (f0, f1, dy0, dy1) in rows:
            if dy1 <= dy0:
                continue
            src = QRectF(sx0, sy0 + f0 * sh, sw, max(0.001, (f1 - f0) * sh))
            dst = QRectF(dx0, dy0, max(0.001, dx1 - dx0), dy1 - dy0)
            painter.drawImage(dst, img, src)

    def _blit(self, painter, img, sub, rect, quad, force_quad=False):
        use_quad = (bool(_QUAD_TILES) and quad is not None
                    and (force_quad
                         or self._quad_deviation(quad, rect) > _QUAD_TOL_PX))
        if not use_quad:
            rect = self._snap_rect(painter, rect)
            if sub is None:
                painter.drawImage(rect, img)
            else:
                painter.drawImage(rect, img, sub)
            return
        if sub is None:
            src = QRectF(0.0, 0.0, float(img.width()), float(img.height()))
        else:
            src = sub
        if _QUAD_OVERLAP_PX > 0:
            _cx = sum(_p.x() for _p in quad) / 4.0
            _cy = sum(_p.y() for _p in quad) / 4.0
            _grown = []
            for _p in quad:
                _dx, _dy = _p.x() - _cx, _p.y() - _cy
                _len = math.hypot(_dx, _dy) or 1.0
                _k = (_len + _QUAD_OVERLAP_PX) / _len
                _grown.append(QPointF(_cx + _dx * _k, _cy + _dy * _k))
            quad = _grown
        srcq = QPolygonF([QPointF(src.x(), src.y()),
                          QPointF(src.x() + src.width(), src.y()),
                          QPointF(src.x() + src.width(), src.y() + src.height()),
                          QPointF(src.x(), src.y() + src.height())])
        try:
            tf = QTransform.quadToQuad(srcq, QPolygonF(quad))
        except Exception:
            exc_note("_blit @ ggis/render/tiles.py:1274")
            tf = None
        if tf is None:
            if sub is None:
                painter.drawImage(rect, img)
            else:
                painter.drawImage(rect, img, sub)
            return
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                                  True)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setTransform(tf, False)
            painter.setClipRect(src)
            painter.drawImage(QPointF(0.0, 0.0), img)
        finally:
            painter.restore()

    def _mesh_steps(self, settings, tb, tile_crs, dst_crs, quad,
                    tol_px=_MESH_TOL_PX):
        tf = crs_transformer(tile_crs, dst_crs)
        if tf is None or quad is None or len(quad) != 4:
            return 1, 1
        try:
            tw = float(tb.xmax - tb.xmin)
            th = float(tb.ymax - tb.ymin)
            if not (tw > 0.0 and th > 0.0):
                return 1, 1
            mx = (tb.xmin + tb.xmax) / 2.0
            my = (tb.ymin + tb.ymax) / 2.0
            pts = [(mx, tb.ymax), (mx, tb.ymin),
                   (tb.xmin, my), (tb.xmax, my), (mx, my)]
            ex, ey = tf.transform([p[0] for p in pts], [p[1] for p in pts])
            P = []
            for i in range(5):
                d = settings.map_to_pixel(float(ex[i]), float(ey[i]))
                if not (math.isfinite(d.x()) and math.isfinite(d.y())):
                    return 1, 1
                P.append((d.x(), d.y()))
        except Exception:
            exc_note("_mesh_steps @ ggis/render/tiles.py:1339")
            return 1, 1

        q = [(p.x(), p.y()) for p in quad]

        def _d(p, a, b):
            return math.hypot(p[0] - (a[0] + b[0]) / 2.0,
                              p[1] - (a[1] + b[1]) / 2.0)

        dev_x = max(_d(P[0], q[0], q[1]), _d(P[1], q[3], q[2]))
        dev_y = max(_d(P[2], q[0], q[3]), _d(P[3], q[1], q[2]),
                    _d(P[4], P[0], P[1]))

        def _n(dev):
            if dev <= tol_px:
                return 1
            return max(1, min(_MESH_MAX,
                              int(math.ceil(math.sqrt(dev / tol_px)))))

        return _n(dev_x), _n(dev_y)

    def _mesh_quads(self, settings, tb, tile_crs, dst_crs, nx, ny):
        tf = crs_transformer(tile_crs, dst_crs)
        if tf is None:
            return None
        back = crs_transformer(dst_crs, tile_crs)
        tw = float(tb.xmax - tb.xmin)
        th = float(tb.ymax - tb.ymin)
        if not (tw > 0.0 and th > 0.0):
            return None
        xs = []
        ys = []
        grid = []
        for j in range(ny):
            cy1 = tb.ymax - th * (j / float(ny))
            cy0 = tb.ymax - th * ((j + 1) / float(ny))
            for i in range(nx):
                cx0 = tb.xmin + tw * (i / float(nx))
                cx1 = tb.xmin + tw * ((i + 1) / float(nx))
                xs.extend((cx0, cx1, cx1, cx0))
                ys.extend((cy1, cy1, cy0, cy0))
                grid.append((cx0, cy0, cx1, cy1))
        try:
            px, py = tf.transform(xs, ys)
        except Exception:
            exc_note("_mesh_quads @ ggis/render/tiles.py:1394")
            return None
        fx = fy = None
        if back is not None:
            try:
                bx, by = back.transform(px, py)
                fx, fy = tf.transform(bx, by)
            except Exception:
                exc_note("_mesh_quads @ ggis/render/tiles.py:1406")
                fx = fy = None
        _sx = max(1.0, abs(float(max(px)) - float(min(px))))
        _sy = max(1.0, abs(float(max(py)) - float(min(py))))
        out = []
        for k in range(nx * ny):
            q = []
            bad = False
            for m in range(4):
                idx = k * 4 + m
                _x, _y = px[idx], py[idx]
                if not (math.isfinite(_x) and math.isfinite(_y)):
                    bad = True
                    break
                if fx is not None:
                    if not (math.isfinite(fx[idx]) and math.isfinite(fy[idx])):
                        bad = True
                        break
                    if (abs(float(fx[idx]) - float(_x)) > _sx * 1e-4
                            or abs(float(fy[idx]) - float(_y)) > _sy * 1e-4):
                        bad = True
                        break
                d = settings.map_to_pixel(float(_x), float(_y))
                if not (math.isfinite(d.x()) and math.isfinite(d.y())):
                    bad = True
                    break
                q.append(QPointF(float(d.x()), float(d.y())))
            out.append((grid[k], q if (q and not bad) else None))
        return out

    def _blit_mesh(self, painter, img, tb, tile_crs, dst_crs, settings,
                   quad, rect):
        nx, ny = self._mesh_steps(settings, tb, tile_crs, dst_crs, quad)
        if nx <= 1 and ny <= 1:
            self._blit(painter, img, None, rect, quad, force_quad=True)
            return
        cells = self._mesh_quads(settings, tb, tile_crs, dst_crs, nx, ny)
        if not cells:
            self._blit(painter, img, None, rect, quad, force_quad=True)
            return
        iw = float(img.width())
        ih = float(img.height())
        tw = float(tb.xmax - tb.xmin)
        th = float(tb.ymax - tb.ymin)
        for (cx0, cy0, cx1, cy1), q in cells:
            if q is None:
                continue
            sub = QRectF((cx0 - tb.xmin) / tw * iw,
                         (tb.ymax - cy1) / th * ih,
                         (cx1 - cx0) / tw * iw,
                         (cy1 - cy0) / th * ih)
            rx0 = min(p.x() for p in q)
            ry0 = min(p.y() for p in q)
            rx1 = max(p.x() for p in q)
            ry1 = max(p.y() for p in q)
            if rx1 - rx0 < 0.01 or ry1 - ry0 < 0.01:
                continue
            self._blit(painter, img, sub,
                       QRectF(rx0, ry0, rx1 - rx0, ry1 - ry0), q,
                       force_quad=True)

    def _draw_one_mesh(self, painter, source, z, tx, ty, tb, tile_crs,
                       dst_crs, settings, rect, quad):
        img = self._image(source, z, tx, ty)
        if img is not None and not img.isNull():
            self._blit_mesh(painter, img, tb, tile_crs, dst_crs, settings,
                            quad, rect)
            return True
        self._schedule_backdrop(source, z, tx, ty)
        return self._draw_preview(painter, source, z, tx, ty, rect, quad,
                                  None)

    def _draw_one(self, painter, source, z, tx, ty, rect, quad=None, rows=None):
        img = self._image(source, z, tx, ty)
        if img is not None and not img.isNull():
            if rows:
                self._blit_rows(painter, img, None, rect, rows)
            else:
                self._blit(painter, img, None, rect, quad)
            return True
        self._schedule_backdrop(source, z, tx, ty)
        return self._draw_preview(painter, source, z, tx, ty, rect, quad, rows)

    def _schedule_backdrop(self, source, z, tx, ty):
        if self._provider is not None:
            return
        pz = z - 2
        if pz < max(0, source.min_zoom):
            return
        if TileLoader.cached_image(source, pz, tx >> 2, ty >> 2) is not None:
            return
        TileLoader.image(source, pz, tx >> 2, ty >> 2)

    def _draw_preview(self, painter, source, z, tx, ty, rect, quad=None,
                      rows=None):
        for up in range(1, _PREVIEW_LEVELS + 1):
            pz = z - up
            if pz < max(0, source.min_zoom):
                break
            pimg = self._cached(source, pz, tx >> up, ty >> up)
            if pimg is None or pimg.isNull():
                continue
            k = 1 << up
            iw = float(pimg.width())
            ih = float(pimg.height())
            sx = tx & (k - 1)
            sy = ty & (k - 1)
            sub = QRectF(sx * iw / k, sy * ih / k, iw / k, ih / k)
            if rows:
                self._blit_rows(painter, pimg, sub, rect, rows)
            else:
                self._blit(painter, pimg, sub, rect, quad)
            return True
        return False
