# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import hashlib
import json
import math
import os
import threading
import time
import logging
_log = logging.getLogger("gmagis")

FIRST_LEVEL = 3
MAX_LEVEL = 11
MAX_LEVEL_PIXELS = 80_000_000
MAX_LEVEL_EDGE = 16384
THUMB_EDGE = 512
CACHE_LIMIT = 2 << 30

_META = "meta.json"
_THUMB = "thumb.png"
_STRIPE_OUT_ROWS = 32


def _cache_root():
    env = os.environ.get("GMAGIS_PYRAMID_DIR")
    if env:
        return env
    try:
        from .. import app_paths
        return os.path.join(app_paths.cache_dir(), "raster_pyramid")
    except Exception:
        _log.exception("silent exception in _cache_root")
    try:
        from .. import app_paths as rm
        return os.path.join(rm.cache_dir(), "raster_pyramid")
    except Exception:
        _log.exception("silent exception in _cache_root")
        import tempfile
        return os.path.join(tempfile.gettempdir(), "gmagis_pyramid")


def _normalize_path(path):
    try:
        s = str(path or "")
        if not s:
            return ""
        return os.path.normcase(os.path.normpath(os.path.abspath(s)))
    except Exception:
        _log.exception("silent exception in _normalize_path")
        return str(path or "")


def source_key(path):
    norm = _normalize_path(path)
    try:
        st = os.stat(norm)
        size, mtime = int(st.st_size), int(st.st_mtime)
    except Exception:
        _log.exception("silent exception in source_key")
        size, mtime = 0, 0
    h = hashlib.sha1(norm.encode("utf-8", "replace")).hexdigest()[:12]
    return "%s-%d-%d" % (h, size, mtime)


def pyramid_dir(path):
    return os.path.join(_cache_root(), source_key(path))


def level_ext(dtype):
    try:
        return ".png" if str(dtype).lower() == "uint8" else ".npy"
    except Exception:
        _log.exception("silent exception in level_ext")
        return ".npy"


def level_path(dir_, level, band=1, dtype=None):
    ext = level_ext(dtype) if dtype is not None else ".png"
    return os.path.join(dir_, "L%d_b%d%s" % (int(level), int(band), ext))


def find_level_file(dir_, level, band=1, dtype=None):
    if dtype is not None:
        fp = level_path(dir_, level, band, dtype)
        return fp if os.path.isfile(fp) else None
    for ext in (".png", ".npy"):
        fp = os.path.join(dir_, "L%d_b%d%s" % (int(level), int(band), ext))
        if os.path.isfile(fp):
            return fp
    return None


def thumb_path(dir_):
    return os.path.join(dir_, _THUMB)


def thumb_write_path(dir_, arr=None):
    dt = None if arr is None else getattr(arr, "dtype", None)
    if dt is None or str(dt) == "uint8":
        return thumb_path(dir_)
    return os.path.join(dir_, "thumb%s" % level_ext(dt))


def find_thumb_file(dir_):
    for name in (_THUMB, "thumb.npy"):
        fp = os.path.join(dir_, name)
        if os.path.isfile(fp):
            return fp
    return None


def plan_levels(width, height, first=FIRST_LEVEL, last=MAX_LEVEL):
    out = []
    L = int(first)
    while L <= int(last):
        f = 1 << L
        w = max(1, int(math.ceil(width / f)))
        h = max(1, int(math.ceil(height / f)))
        out.append(L)
        if max(w, h) <= 1:
            break
        L += 1
    while out:
        w = int(math.ceil(width / (1 << out[0])))
        h = int(math.ceil(height / (1 << out[0])))
        if max(w, h) <= MAX_LEVEL_EDGE and w * h <= MAX_LEVEL_PIXELS:
            break
        out.pop(0)
    return out


def decimation_for(width, out_width, height, out_height):
    try:
        fx = float(width) / max(1.0, float(out_width))
        fy = float(height) / max(1.0, float(out_height))
    except Exception:
        _log.exception("silent exception in decimation_for")
        return 1.0
    return max(fx, fy)


def pick_level(levels, decimation):
    best = 0
    for L in levels or ():
        try:
            L = int(L)
        except Exception:
            _log.exception("silent exception in pick_level")
            continue
        if (1 << L) <= max(1.0, float(decimation)):
            best = max(best, L)
    return best


def finest_level(levels):
    best = 0
    for L in levels or ():
        try:
            L = int(L)
        except Exception:
            _log.exception("silent exception in finest_level")
            continue
        best = L if best == 0 else min(best, L)
    return best


def pick_level_or_finest(levels, decimation, max_upscale=2.0):
    L = pick_level(levels, decimation)
    if L > 0:
        return L
    f = finest_level(levels)
    if f > 0:
        try:
            need = max(1.0, float(decimation))
        except Exception:
            _log.exception("silent exception in pick_level_or_finest")
            need = 1.0
        if (1 << f) <= need * float(max_upscale):
            return f
    return 0


def _meta_from_dataset(ds, path):
    t = ds.transform
    levels = plan_levels(ds.width, ds.height)
    lv = {}
    for L in levels:
        f = 1 << L
        lv[str(L)] = {
            "factor": f,
            "width": max(1, int(math.ceil(ds.width / f))),
            "height": max(1, int(math.ceil(ds.height / f))),
            "transform": [t.a * f, t.b, t.c, t.d, t.e * f, t.f],
        }
    try:
        size = int(os.path.getsize(str(path)))
        mtime = int(os.path.getmtime(str(path)))
    except Exception:
        _log.exception("silent exception in _meta_from_dataset")
        size, mtime = 0, 0
    return {
        "version": 6,
        "source": os.path.abspath(str(path)),
        "source_size": size,
        "source_mtime": mtime,
        "width": int(ds.width), "height": int(ds.height),
        "count": max(1, int(ds.count)),
        "dtype": ds.dtypes[0] if ds.dtypes else "uint8",
        "nodata": None if ds.nodata is None else float(ds.nodata),
        "crs": ds.crs.to_wkt() if ds.crs is not None else "",
        "bounds": list(ds.bounds),
        "levels": lv,
        "created": int(time.time()),
    }


_META_CACHE = {}


def read_meta(path):
    if not path:
        return None
    try:
        st = os.stat(str(path))
        sig = (int(st.st_size), int(st.st_mtime))
    except Exception:
        _log.exception("silent exception in read_meta")
        sig = None
    ck = (str(path), sig)
    if ck in _META_CACHE:
        return _META_CACHE[ck]
    meta = _read_meta_uncached(path)
    _META_CACHE[ck] = meta
    return meta


def _read_meta_uncached(path):
    d = pyramid_dir(path)
    fp = os.path.join(d, _META)
    if not os.path.isfile(fp):
        return None
    try:
        with open(fp, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        _log.exception("silent exception in _read_meta_uncached")
        return None
    if int(meta.get("version", 0)) != 6:
        return None
    try:
        st = os.stat(str(path))
        if (int(meta.get("source_size", -1)) != int(st.st_size)
                or int(meta.get("source_mtime", -1)) != int(st.st_mtime)):
            return None
    except Exception:
        _log.exception("silent exception in _read_meta_uncached")
        return None
    n = max(1, int(meta.get("count", 1)))
    raw_levels = dict(meta.get("levels", {}))
    valid_levels = {}
    for L, info in raw_levels.items():
        ok = True
        for b in range(1, n + 1):
            if not find_level_file(d, int(L), b):
                ok = False
                break
        if ok:
            valid_levels[L] = info
    if not valid_levels:
        return None
    meta = dict(meta)
    meta["levels"] = valid_levels
    return meta


def has_pyramid(path):
    return read_meta(path) is not None


def level_info(meta, level):
    return (meta or {}).get("levels", {}).get(str(int(level)))


def read_array_file(fp):
    if not fp or not os.path.isfile(fp):
        return None
    try:
        import numpy as np
        from PIL import Image
        with Image.open(fp) as im:
            return np.asarray(im)
    except Exception:
        _log.exception("silent exception in read_array_file")
    try:
        import numpy as np
        with open(fp, "rb") as f:
            return np.load(f)
    except Exception:
        _log.exception("silent exception in read_array_file")
        return None


def read_thumbnail(path, meta=None):
    meta = meta or read_meta(path)
    if not meta:
        return None
    return read_array_file(find_thumb_file(pyramid_dir(path)))


def build_pyramid(path, progress=None, cancel=None, first=FIRST_LEVEL,
                  partial_callback=None):
    import rasterio
    try:
        d = pyramid_dir(path)
        os.makedirs(d, exist_ok=True)
    except Exception:
        _log.exception("silent exception in build_pyramid")
        return None

    try:
        ds = rasterio.open(str(path))
    except Exception:
        _log.exception("silent exception in build_pyramid")
        return None

    try:
        dt = str(ds.dtypes[0]) if ds.dtypes else ""
        if not dt:
            return None
        levels = sorted(plan_levels(ds.width, ds.height, first=first))
        if not levels:
            return None
        n = max(1, int(ds.count))
        meta = _meta_from_dataset(ds, path)

        total = len(levels) + 1
        try:
            _th = thumb_from_blocks(ds, n)
            if _th is not None:
                _write_level_arr(thumb_write_path(d, _th), _th)
                if progress is not None:
                    try:
                        progress(0, total, "缩略图")
                    except Exception:
                        _log.exception("silent exception in build_pyramid")
        except Exception:
            _log.exception("silent exception in build_pyramid")
        prev = None
        thumb_done = False
        for i, L in enumerate(levels):
            if cancel is not None and cancel():
                return None
            f = 1 << int(L)
            info = meta["levels"][str(L)]
            ow, oh = int(info["width"]), int(info["height"])
            if prev is None:
                arr = _decimate_from_source(ds, n, ow, oh, f, progress,
                                            cancel, i, total)
                if arr is None:
                    return None
            else:
                arr = _decimate_from_array(prev, ow, oh)
            _write_level(d, L, arr, n, dtype=dt)
            prev = arr
            if progress is not None:
                try:
                    progress(i + 1, total, "1/%d" % (1 << L))
                except Exception:
                    _log.exception("silent exception in build_pyramid")

            if not thumb_done:
                thumb_done = True
                if cancel is not None and cancel():
                    return None
                try:
                    if not find_thumb_file(d):
                        thumb = _make_thumb(arr, n)
                        if thumb is not None:
                            _write_level_arr(thumb_write_path(d, thumb),
                                             thumb)
                except Exception:
                    _log.exception("silent exception in build_pyramid")
                tmp = os.path.join(d, _META + ".tmp")
                with open(tmp, "w", encoding="utf-8") as fp:
                    json.dump(meta, fp, ensure_ascii=False)
                os.replace(tmp, os.path.join(d, _META))
                try:
                    sig = (int(os.stat(str(path)).st_size),
                           int(os.stat(str(path)).st_mtime))
                    _META_CACHE.pop((str(path), sig), None)
                except Exception:
                    _log.exception("silent exception in build_pyramid")
                    _META_CACHE.clear()
            if partial_callback is not None:
                try:
                    partial_callback(str(path), int(L), meta)
                except Exception:
                    _log.exception("silent exception in build_pyramid")

        if progress is not None:
            try:
                progress(total, total, "完成")
            except Exception:
                _log.exception("silent exception in build_pyramid")

        tmp = os.path.join(d, _META + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(meta, fp, ensure_ascii=False)
        os.replace(tmp, os.path.join(d, _META))
        return meta
    except Exception:
        _log.exception("silent exception in build_pyramid")
        return None
    finally:
        try:
            ds.close()
        except Exception:
            _log.exception("silent exception in build_pyramid")


def _src_dtype(ds):
    try:
        import numpy as np
        dt = str(ds.dtypes[0])
        return np.dtype(dt)
    except Exception:
        _log.exception("silent exception in _src_dtype")
        import numpy as np
        return np.dtype("float32")


def _fill_value(ds, dt):
    try:
        if ds.nodata is not None:
            return dt.type(ds.nodata)
    except Exception:
        _log.exception("silent exception in _fill_value")
    try:
        return dt.type(0)
    except Exception:
        _log.exception("silent exception in _fill_value")
        return 0


def _read_resampling(ds):
    from rasterio.enums import Resampling
    try:
        if ds.nodata is not None:
            return Resampling.nearest
    except Exception:
        _log.exception("silent exception in _read_resampling")
    return Resampling.average


def _decimate_from_source(ds, n, ow, oh, factor, progress, cancel, level_i,
                          total):
    import numpy as np
    import time as _time
    dt = _src_dtype(ds)
    out = np.zeros((n, oh, ow), dtype=dt)
    fill = _fill_value(ds, dt)
    if fill != 0:
        out[...] = fill
    W, H = int(ds.width), int(ds.height)
    bands = list(range(1, n + 1))
    y_out = 0
    while y_out < oh:
        if cancel is not None and cancel():
            return None
        rows_out = min(_STRIPE_OUT_ROWS, oh - y_out)
        y_src0 = y_out * factor
        y_src1 = min(H, y_src0 + rows_out * factor)
        try:
            from rasterio.windows import Window
            win = Window(0, y_src0, W, max(1, y_src1 - y_src0))
            blk = ds.read(bands, window=win, out_shape=(n, rows_out, ow),
                          resampling=_nearest())
        except Exception:
            _log.exception("silent exception in _decimate_from_source")
            return None
        out[:, y_out:y_out + rows_out, :] = blk
        y_out += rows_out
        try:
            _time.sleep(0)
        except Exception:
            _log.exception("silent exception in _decimate_from_source")
        if progress is not None:
            try:
                progress(level_i + float(y_out) / max(1, oh), total,
                         "%d%%" % int(100 * y_out / max(1, oh)))
            except Exception:
                _log.exception("silent exception in _decimate_from_source")
    return out


def _nearest():
    from rasterio.enums import Resampling
    return Resampling.nearest


def _decimate_from_array(prev, ow, oh):
    import numpy as np
    ph, pw = prev.shape[1], prev.shape[2]
    ys = np.minimum((np.arange(oh, dtype=np.int64) * ph) // max(1, oh),
                    max(0, ph - 1))
    xs = np.minimum((np.arange(ow, dtype=np.int64) * pw) // max(1, ow),
                    max(0, pw - 1))
    return prev[:, ys][:, :, xs].copy()


def _make_thumb(arr, n):
    try:
        h, w = arr.shape[1], arr.shape[2]
        if h <= 0 or w <= 0:
            return None
        k = float(THUMB_EDGE) / max(h, w)
        oh = max(1, int(round(h * k)))
        ow = max(1, int(round(w * k)))
        import numpy as np
        ys = np.minimum((np.arange(oh, dtype=np.int64) * h) // oh, h - 1)
        xs = np.minimum((np.arange(ow, dtype=np.int64) * w) // ow, w - 1)
        small = arr[:, ys][:, :, xs]
        return small[0] if n == 1 else small
    except Exception:
        _log.exception("silent exception in _make_thumb")
        return None


_QUICK = None
_QUICK_MAX = 6


def _quick_cache():
    global _QUICK
    if _QUICK is None:
        _QUICK = _LRU(_QUICK_MAX)
    return _QUICK


class _LRU:

    def __init__(self, n):
        from collections import OrderedDict
        self._n = int(n)
        self._d = OrderedDict()

    def get(self, k):
        v = self._d.get(k)
        if v is not None:
            self._d.move_to_end(k)
        return v

    def put(self, k, v):
        self._d[k] = v
        self._d.move_to_end(k)
        while len(self._d) > self._n:
            self._d.popitem(last=False)

    def clear(self):
        self._d.clear()


def clear_quicklook(path=None):
    try:
        q = _quick_cache()
        if path is None:
            q.clear()
            return
        try:
            sk = source_key(path)
        except Exception:
            _log.exception("silent exception in clear_quicklook")
            return
        for k in [k for k in list(q._d.keys()) if k and k[0] == sk]:
            q._d.pop(k, None)
    except Exception:
        _log.exception("silent exception in clear_quicklook")


def quicklook(path, size, bands=None, samples=8):
    import numpy as np
    if not path or not os.path.isfile(str(path)):
        return None
    try:
        ow, oh = max(1, int(size[0])), max(1, int(size[1]))
    except Exception:
        _log.exception("silent exception in quicklook")
        return None
    bsel = tuple(sorted(int(b) for b in bands)) if bands else ()
    ck = (source_key(path), ow, oh, bsel)
    hit = _quick_cache().get(ck)
    if hit is not None:
        return hit

    import rasterio
    from rasterio.windows import Window
    a = None
    try:
        with rasterio.open(str(path)) as ds:
            if not ds.dtypes:
                return None
            n = max(1, int(ds.count))
            sel = [b for b in (bsel or tuple(range(1, n + 1))) if 1 <= b <= n]
            if not sel:
                return None
            try:
                bw, bh = int(ds.block_shapes[0][0]), int(ds.block_shapes[0][1])
            except Exception:
                _log.exception("silent exception in quicklook")
                bw = bh = 256
            bw, bh = max(16, bw), max(16, bh)
            W, H = int(ds.width), int(ds.height)
            nbx = max(1, int(math.ceil(W / float(bw))))
            nby = max(1, int(math.ceil(H / float(bh))))
            sx = max(1, int(math.ceil(nbx / float(max(1, samples)))))
            sy = max(1, int(math.ceil(nby / float(max(1, samples)))))
            cols = list(range(0, nbx, sx))
            rows = list(range(0, nby, sy))
            bs = 96
            dt = _src_dtype(ds)
            mosaic = np.zeros((len(sel), len(rows) * bs, len(cols) * bs),
                              dtype=dt)
            any_read = False
            for j, by in enumerate(rows):
                for i, bx in enumerate(cols):
                    r0, c0 = by * bh, bx * bw
                    h = min(bh, H - r0)
                    w = min(bw, W - c0)
                    if h <= 0 or w <= 0:
                        continue
                    try:
                        blk = ds.read(sel, window=Window(c0, r0, w, h),
                                      out_shape=(len(sel), bs, bs),
                                      resampling=rasterio.enums.
                                      Resampling.nearest)
                    except Exception:
                        _log.exception("silent exception in quicklook")
                        continue
                    mosaic[:, j * bs:(j + 1) * bs, i * bs:(i + 1) * bs] = blk
                    any_read = True
            if not any_read:
                return None
            ys = np.minimum((np.arange(oh) * mosaic.shape[1]) // oh,
                            mosaic.shape[1] - 1)
            xs = np.minimum((np.arange(ow) * mosaic.shape[2]) // ow,
                            mosaic.shape[2] - 1)
            small = mosaic[:, ys][:, :, xs]
            a = np.ascontiguousarray(small[0]) if len(sel) == 1 \
                else np.ascontiguousarray(small)
    except Exception:
        _log.exception("silent exception in quicklook")
        return None
    if a is None or not getattr(a, "size", 0):
        return None
    _quick_cache().put(ck, a)
    return a


def thumb_from_blocks(ds, n=1, edge=THUMB_EDGE, samples=8):
    import numpy as np
    from PIL import Image
    from rasterio.windows import Window
    if int(n) != 1:
        return None
    try:
        bw, bh = int(ds.block_shapes[0][0]), int(ds.block_shapes[0][1])
    except Exception:
        _log.exception("silent exception in thumb_from_blocks")
        bw = bh = 256
    bw = max(16, bw)
    bh = max(16, bh)
    try:
        W, H = int(ds.width), int(ds.height)
    except Exception:
        _log.exception("silent exception in thumb_from_blocks")
        return None
    if W <= 0 or H <= 0:
        return None
    nbx = max(1, int(math.ceil(W / float(bw))))
    nby = max(1, int(math.ceil(H / float(bh))))
    sx = max(1, int(math.ceil(nbx / float(max(1, samples)))))
    sy = max(1, int(math.ceil(nby / float(max(1, samples)))))
    cols = list(range(0, nbx, sx))
    rows = list(range(0, nby, sy))
    bs = 128
    dt = _src_dtype(ds)
    mosaic = np.zeros((len(rows) * bs, len(cols) * bs), dtype=dt)
    fill = _fill_value(ds, dt)
    if fill != 0:
        mosaic[...] = fill
    rs = _read_resampling(ds)
    read_any = False
    for j, by in enumerate(rows):
        for i, bx in enumerate(cols):
            r0, c0 = by * bh, bx * bw
            h = min(bh, H - r0)
            w = min(bw, W - c0)
            if h <= 0 or w <= 0:
                continue
            try:
                a = ds.read(1, window=Window(c0, r0, w, h),
                            out_shape=(bs, bs), resampling=rs)
            except Exception:
                _log.exception("silent exception in thumb_from_blocks")
                continue
            mosaic[j * bs:(j + 1) * bs, i * bs:(i + 1) * bs] = a
            read_any = True
    if not read_any:
        return None
    hh, ww = mosaic.shape
    k = float(edge) / max(1, max(hh, ww))
    oh = max(1, int(round(hh * k)))
    ow = max(1, int(round(ww * k)))
    if str(mosaic.dtype) == "uint8":
        try:
            return np.asarray(Image.fromarray(mosaic).resize((ow, oh),
                                                            Image.NEAREST))
        except Exception:
            _log.exception("silent exception in thumb_from_blocks")
            return None
    try:
        ys = np.minimum((np.arange(oh, dtype=np.int64) * hh) // oh, hh - 1)
        xs = np.minimum((np.arange(ow, dtype=np.int64) * ww) // ow, ww - 1)
        return np.ascontiguousarray(mosaic[ys][:, xs])
    except Exception:
        _log.exception("silent exception in thumb_from_blocks")
        return None


def _write_level_arr(fp, arr):
    tmp = fp + ".tmp"
    try:
        import numpy as np
        want_png = str(getattr(arr, "dtype", "")) == "uint8"
        if want_png:
            try:
                from PIL import Image
                Image.fromarray(arr).save(tmp, format="PNG", compress_level=6)
                os.replace(tmp, fp)
                return True
            except Exception:
                _log.exception("silent exception in _write_level_arr")
        with open(tmp, "wb") as f:
            np.save(f, np.ascontiguousarray(arr))
        os.replace(tmp, fp)
        return True
    except Exception:
        _log.exception("silent exception in _write_level_arr")
        return False


def _write_level(d, level, arr, n, dtype=None):
    ok = True
    for b in range(n):
        sub = arr[b] if arr.ndim == 3 else arr
        dt = dtype if dtype is not None else getattr(sub, "dtype", None)
        ok = _write_level_arr(level_path(d, level, b + 1, dt), sub) and ok
    return ok


_ARR_CACHE = {}
_ARR_LRU = []
_ARR_MAX = 6


def _load_level_array(d, level, band=1):
    key = (d, int(level), int(band))
    hit = _ARR_CACHE.get(key)
    if hit is not None:
        try:
            _ARR_LRU.remove(key)
        except ValueError:
            exc_note("_load_level_array @ ggis/io/raster_pyramid.py:1077")
            pass
        _ARR_LRU.append(key)
        return hit
    fp = find_level_file(d, int(level), band)
    if not fp:
        return None
    arr = read_array_file(fp)
    if arr is None:
        return None
    _ARR_CACHE[key] = arr
    _ARR_LRU.append(key)
    while len(_ARR_LRU) > _ARR_MAX:
        old = _ARR_LRU.pop(0)
        _ARR_CACHE.pop(old, None)
    return arr


def _edges(ext):
    for names in (("xmin", "ymin", "xmax", "ymax"),
                  ("left", "bottom", "right", "top")):
        try:
            return tuple(float(getattr(ext, n)) for n in names)
        except Exception:
            _log.exception("silent exception in _edges")
            continue
    raise TypeError("不是一个矩形：%r" % (ext,))


def invalidate(path=None):
    if path is None:
        _ARR_CACHE.clear()
        del _ARR_LRU[:]
        return
    d = pyramid_dir(path)
    for k in [k for k in _ARR_CACHE if k[0] == d]:
        _ARR_CACHE.pop(k, None)
        try:
            _ARR_LRU.remove(k)
        except ValueError:
            exc_note("invalidate @ ggis/io/raster_pyramid.py:1124")
            pass


def read_overview(path, extent, out_size, meta=None, bands=None,
                  max_upscale=2.0):
    import numpy as np
    meta = meta or read_meta(path)
    if not meta:
        return None, False
    try:
        ow, oh = int(out_size[0]), int(out_size[1])
    except Exception:
        _log.exception("silent exception in read_overview")
        return None, False
    if ow <= 0 or oh <= 0:
        return None, False

    xmin, ymin, xmax, ymax = _edges(extent)
    try:
        bx = meta.get("bounds") or [0.0, 0.0, 0.0, 0.0]
        su = float(meta["width"]) / max(1e-12, float(bx[2]) - float(bx[0]))
        sv = float(meta["height"]) / max(1e-12, float(bx[3]) - float(bx[1]))
    except Exception:
        _log.exception("silent exception in read_overview")
        su = sv = 0.0
    if su > 0 and sv > 0:
        dec = max((xmax - xmin) * su / ow, (ymax - ymin) * sv / oh)
    else:
        dec = decimation_for(int(meta["width"]), ow, int(meta["height"]), oh)
    L = pick_level_or_finest(list(meta.get("levels", {}).keys()), dec,
                             max_upscale=max_upscale)
    if L <= 0:
        return None, False
    info = level_info(meta, L)
    if not info:
        return None, False

    n = max(1, int(meta.get("count", 1)))
    sel = [int(b) for b in (bands or range(1, n + 1))]
    sel = [b for b in sel if 1 <= b <= n] or [1]

    d = pyramid_dir(path)
    subs = []
    for b in sel:
        arr = _load_level_array(d, L, b)
        if arr is None:
            return None, False
        subs.append(arr)
    if not subs:
        return None, False

    try:
        t = info["transform"]
        lw, lh = int(info["width"]), int(info["height"])
        if abs(float(t[1])) > 1e-12 or abs(float(t[3])) > 1e-12:
            return None, False
        pw = abs(float(t[0])) or 1.0
        ph = abs(float(t[4])) or 1.0
        fx0 = (xmin - float(t[2])) / pw
        fx1 = (xmax - float(t[2])) / pw
        fy0 = (float(t[5]) - ymax) / ph
        fy1 = (float(t[5]) - ymin) / ph
        x0 = max(0, int(math.floor(fx0)))
        x1 = min(lw, int(math.ceil(fx1)))
        y0 = max(0, int(math.floor(fy0)))
        y1 = min(lh, int(math.ceil(fy1)))
        if x1 - x0 < 1 or y1 - y0 < 1:
            return None, False
    except Exception:
        _log.exception("silent exception in read_overview")
        return None, False

    span_x = (fx1 - fx0) or 1.0
    span_y = (fy1 - fy0) or 1.0
    ox0 = min(max(0, int(round((x0 - fx0) / span_x * ow))), ow - 1)
    ox1 = min(max(ox0 + 1, int(round((x1 - fx0) / span_x * ow))), ow)
    oy0 = min(max(0, int(round((y0 - fy0) / span_y * oh))), oh - 1)
    oy1 = min(max(oy0 + 1, int(round((y1 - fy0) / span_y * oh))), oh)
    step_x = span_x / max(1, ow)
    step_y = span_y / max(1, oh)

    from . import raster_resample as _rrs
    n_x = max(1, ox1 - ox0)
    n_y = max(1, oy1 - oy0)
    xi = _rrs.sample_index(n_x, fx0 + ox0 * step_x, n_x * step_x,
                           x0, x1 - x0)
    yi = _rrs.sample_index(n_y, fy0 + oy0 * step_y, n_y * step_y,
                           y0, y1 - y0)

    res = []
    for c in subs:
        crop = c[y0:y1, x0:x1]
        out = np.zeros((oh, ow), dtype=crop.dtype)
        if crop.shape[0] and crop.shape[1]:
            out[oy0:oy1, ox0:ox1] = _rrs.take_exact(crop, xi, yi)
        res.append(out)
    if len(res) == 1:
        return np.ascontiguousarray(res[0]), True
    return np.ascontiguousarray(np.stack(res, axis=0)), True


try:
    from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
except Exception:
    _log.exception("silent exception")
    QObject = None


if QObject is not None:
    class _PyrEmitter(QObject):
        progress = Signal(object)
        finished = Signal(object)
        partial = Signal(object)

    _EMITTER = _PyrEmitter()
    _POOL = None
    _POOL_LOCK = threading.Lock()
    _BUILDING = set()

    def pyramidProgressSignal():
        return _EMITTER.progress

    def pyramidFinishedSignal():
        return _EMITTER.finished

    def pyramidPartialSignal():
        return _EMITTER.partial

    class _PyrTask(QRunnable):
        def __init__(self, path):
            super().__init__()
            self.setAutoDelete(True)
            self._path = path
            self._cancel = threading.Event()

        def cancel(self):
            self._cancel.set()

        def run(self):
            try:
                def _on_partial(path_str, level, meta):
                    try:
                        _EMITTER.partial.emit(
                            {"path": path_str, "level": int(level),
                             "meta": meta})
                    except Exception:
                        _log.exception("silent exception in _on_partial")

                meta = build_pyramid(
                    self._path,
                    progress=lambda d, t, tx: _EMITTER.progress.emit(
                        {"path": self._path, "done": d, "total": t,
                         "text": tx}),
                    cancel=self._cancel.is_set,
                    partial_callback=_on_partial)
            except Exception:
                _log.exception("silent exception in run")
                meta = None
            finally:
                with _POOL_LOCK:
                    _BUILDING.discard(self._path)
            try:
                _EMITTER.finished.emit({"path": self._path, "meta": meta})
            except Exception:
                _log.exception("silent exception in run")

    def _pool():
        global _POOL
        if _POOL is None:
            with _POOL_LOCK:
                if _POOL is None:
                    p = QThreadPool()
                    p.setMaxThreadCount(1)
                    _POOL = p
        return _POOL

    def build_async(path):
        try:
            if not path:
                return False
            if has_pyramid(path):
                return False
            with _POOL_LOCK:
                if path in _BUILDING:
                    return False
                _BUILDING.add(path)
            _pool().start(_PyrTask(str(path)))
            return True
        except Exception:
            _log.exception("silent exception in build_async")
            with _POOL_LOCK:
                _BUILDING.discard(path)
            return False

    def is_building(path):
        with _POOL_LOCK:
            return path in _BUILDING

    def needs_pyramid(path, min_pixels=32_000_000):
        try:
            if not path or not os.path.isfile(str(path)):
                return False
            if has_pyramid(path) or is_building(path):
                return False
            import rasterio
            with rasterio.open(str(path)) as ds:
                try:
                    if ds.overviews(1):
                        return False
                except Exception:
                    _log.exception("silent exception in needs_pyramid")
                return int(ds.width) * int(ds.height) >= int(min_pixels)
        except Exception:
            _log.exception("silent exception in needs_pyramid")
            return False
else:
    def pyramidProgressSignal():
        return None

    def pyramidFinishedSignal():
        return None

    def build_async(path):
        return False

    def is_building(path):
        return False

    def needs_pyramid(path, min_pixels=32_000_000):
        return False


def cache_size():
    total = 0
    for dirpath, _dn, fn in os.walk(_cache_root()):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except Exception:
                _log.exception("silent exception in cache_size")
    return total


def prune_stale(limit=CACHE_LIMIT):
    root = _cache_root()
    if not os.path.isdir(root):
        return 0
    entries = []
    total = 0
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if not os.path.isdir(p):
            continue
        sz, mt = 0, 0.0
        for dirpath, _dn, fn in os.walk(p):
            for f in fn:
                try:
                    st = os.stat(os.path.join(dirpath, f))
                    sz += st.st_size
                    mt = max(mt, st.st_mtime)
                except Exception:
                    _log.exception("silent exception in prune_stale")
        entries.append((mt, p, sz))
        total += sz
    if total <= limit:
        return 0
    freed = 0
    for _mt, p, sz in sorted(entries):
        if total - freed <= limit:
            break
        if _rmtree(p):
            freed += sz
    return freed


def _rmtree(p):
    ok = True
    try:
        for dirpath, _dn, fn in os.walk(p, topdown=False):
            for f in fn:
                try:
                    os.remove(os.path.join(dirpath, f))
                except Exception:
                    _log.exception("silent exception in _rmtree")
                    ok = False
            try:
                os.rmdir(dirpath)
            except Exception:
                _log.exception("silent exception in _rmtree")
                ok = False
    except Exception:
        _log.exception("silent exception in _rmtree")
        ok = False
    return ok
