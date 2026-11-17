# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from ggis.core.crs.extent import GgsRectangle
import logging
_log = logging.getLogger("gmagis")

try:
    import rasterio
    from rasterio.transform import Affine
    _HAS_RASTERIO = True
except Exception:
    _log.exception("silent exception")
    rasterio = None
    Affine = None
    _HAS_RASTERIO = False

try:
    from PIL import Image
    _HAS_PIL = True
except Exception:
    _log.exception("silent exception")
    Image = None
    _HAS_PIL = False

_MAX_TILES = 80000
_MAX_DIM = 30000

_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) GmaGIS/1.0 "
               "(desktop GIS tile client)")
_TIMEOUT = 15.0
_WORKERS = 6


def _http_get(url, headers):
    hdr = {"User-Agent": _USER_AGENT, "Accept": "image/*,*/*;q=0.8"}
    for k, v in (headers or {}).items():
        hdr[str(k)] = str(v)
    req = urllib.request.Request(str(url), headers=hdr)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read()


def _decode(data):
    if not data:
        return None
    img = Image.open(io.BytesIO(data)).convert("RGBA")
    import numpy as np
    return np.asarray(img, dtype="uint8")


def estimate(source, extent_in_source_crs, zoom):
    if source is None or not source.is_valid():
        return (0, 0, 0, True)
    m = source.matrix()
    if extent_in_source_crs is None or extent_in_source_crs.is_empty():
        return (0, 0, 0, True)
    z = source.clamp_zoom(int(zoom))
    x0, y0, x1, y1 = m.tile_range(z, extent_in_source_crs)
    if x1 < x0 or y1 < y0:
        return (0, 0, 0, True)
    n = (x1 - x0 + 1) * (y1 - y0 + 1)
    ts = int(source.tile_size)
    w = (x1 - x0 + 1) * ts
    h = (y1 - y0 + 1) * ts
    over = (n > _MAX_TILES) or (w > _MAX_DIM) or (h > _MAX_DIM)
    return (n, w, h, over)


def _output_crs(source):
    try:
        from rasterio.crs import CRS
        return CRS.from_user_input(str(source.crs or "EPSG:3857"))
    except Exception:
        _log.exception("silent exception in _output_crs")
        return None


def _bands_for(driver, eight_bit):
    if driver in ("JPEG", "BMP"):
        return 3
    return 4


def download_tiles_to_raster(source, extent_in_source_crs, zoom, driver, path,
                             progress=None, cancel=None):
    if not _HAS_RASTERIO:
        raise RuntimeError("缺少 rasterio，无法导出瓦片图层")
    if not _HAS_PIL:
        raise RuntimeError("缺少 Pillow，无法解码瓦片图像")
    if source is None or not source.is_valid():
        raise ValueError("瓦片源无效")
    if extent_in_source_crs is None or extent_in_source_crs.is_empty():
        raise ValueError("导出范围为空")

    m = source.matrix()
    z = source.clamp_zoom(int(zoom))
    x0, y0, x1, y1 = m.tile_range(z, extent_in_source_crs)
    if x1 < x0 or y1 < y0:
        raise ValueError("当前范围在瓦片金字塔之外，没有可下载的瓦片")

    n = (x1 - x0 + 1) * (y1 - y0 + 1)
    if n == 0:
        raise ValueError("当前范围没有覆盖到任何瓦片")
    if n > _MAX_TILES:
        raise ValueError(
            "瓦片数量过多（约 {0} 张），请缩小范围或降低层级后再下载".format(n))
    ts = int(source.tile_size)
    W = (x1 - x0 + 1) * ts
    H = (y1 - y0 + 1) * ts
    if W > _MAX_DIM or H > _MAX_DIM:
        raise ValueError(
            "拼接尺寸过大（{0} × {1}），请缩小范围或降低层级后再下载"
            .format(W, H))

    import numpy as np

    tl = m.tile_bounds(z, x0, y0)
    br = m.tile_bounds(z, x1, y1)
    left = tl.xmin
    top = tl.ymax
    right = br.xmax
    bottom = br.ymin
    res_x = (right - left) / float(W)
    res_y = (bottom - top) / float(H)
    transform = Affine(res_x, 0.0, left, 0.0, res_y, top)

    count = _bands_for(str(driver), False)
    mosaic = np.zeros((H, W, 4), dtype="uint8")

    def _need_cancel():
        try:
            return bool(cancel()) if callable(cancel) else False
        except Exception:
            _log.exception("silent exception in _need_cancel")
            return False

    jobs = []
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            jobs.append((tx, ty, source.url_for(z, tx, ty)))

    failed = 0
    done = 0

    def _fetch(job):
        tx, ty, url = job
        try:
            data = _http_get(url, source.headers)
        except Exception:
            _log.exception("silent exception in _fetch")
            return (tx, ty, None)
        return (tx, ty, data)

    with ThreadPoolExecutor(max_workers=_WORKERS) as ex:
        futs = [ex.submit(_fetch, j) for j in jobs]
        for fut in as_completed(futs):
            if _need_cancel():
                try:
                    ex.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    _log.exception("silent exception in download_tiles_to_raster")
                return None, 0
            tx, ty, data = fut.result()
            done += 1
            if data is None:
                failed += 1
            else:
                arr = _decode(data)
                if arr is not None and arr.shape[0] == ts and arr.shape[1] == ts:
                    row = (ty - y0) * ts
                    col = (tx - x0) * ts
                    mosaic[row:row + ts, col:col + ts, :] = arr
                else:
                    failed += 1
            if progress is not None:
                try:
                    progress(done / float(n),
                             "正在下载瓦片… ({0}/{1})".format(done, n))
                except Exception:
                    _log.exception("silent exception in download_tiles_to_raster")

    if count == 3:
        band_data = mosaic[:, :, :3].transpose(2, 0, 1).copy()
    else:
        band_data = mosaic.transpose(2, 0, 1).copy()

    out = str(path or "")
    if not out:
        raise ValueError("未指定输出路径")
    out_dir = os.path.dirname(os.path.abspath(out))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    crs = _output_crs(source)
    with rasterio.open(
        out, "w", driver=str(driver), height=H, width=W,
        count=count, dtype="uint8", crs=crs, transform=transform,
    ) as ds:
        ds.write(band_data)
        if str(driver) == "GTiff" and min(W, H) >= 512:
            try:
                from rasterio.enums import Resampling
                factors = []
                f = 2
                while f * 2 <= max(W, H) // 256 and len(factors) < 8:
                    factors.append(f)
                    f *= 2
                if factors:
                    ds.build_overviews(factors, Resampling.average)
                    ds.update_tags(ns="rio_overview", resampling="average")
            except Exception:
                _log.exception("silent exception in download_tiles_to_raster")

    if failed:
        import logging
        logging.getLogger("gmagis").warning(
            "瓦片导出：{0}/{1} 张下载失败（缺图处留空/黑块）".format(failed, n))
    return out, failed
