# -*- coding: utf-8 -*-

import os

try:
    import rasterio
    _HAS_RASTERIO = True
except Exception:
    _log.exception("silent exception")
    rasterio = None
    _HAS_RASTERIO = False

from ..core.crs import GgsCoordinateReferenceSystem as GgsCrs
from ggis.core.model.layer import GgsRasterLayer

from ..exec import guard as _guard

__all__ = ["read_raster", "is_raster_path", "RASTER_SUFFIXES",
           "write_raster", "driver_for_raster", "RASTER_DRIVERS"]

RASTER_SUFFIXES = {
    ".tif", ".tiff", ".img", ".asc", ".vrt", ".jp2", ".png", ".jpg",
    ".jpeg", ".bmp", ".gif", ".sid", ".ecw", ".hgt", ".dem", ".bt",
    ".bil", ".nc", ".xyz", ".ers", ".rst", ".sdat", ".webp",
    ".grib", ".grb", ".grb2",
}


def is_raster_path(path):
    return os.path.splitext(str(path or ""))[1].lower() in RASTER_SUFFIXES


def _crs_from_rasterio(ds):
    try:
        c = ds.crs
        if c is None:
            return GgsCrs()
        epsg = c.to_epsg()
        if epsg:
            return GgsCrs.from_epsg(epsg)
        return GgsCrs.from_wkt(c.to_wkt())
    except Exception:
        _log.exception("silent exception in _crs_from_rasterio")
        return GgsCrs()


def read_raster(path):
    src = str(path or "")
    name = os.path.splitext(os.path.basename(src))[0] or src
    if not _HAS_RASTERIO:
        return GgsRasterLayer(name, src)._fail("缺少 rasterio")
    if not os.path.exists(src):
        return GgsRasterLayer(name, src)._fail("文件不存在：%s" % src)

    try:
        ds = rasterio.open(src, "r")
    except Exception as e:
        _log.exception("silent exception in read_raster")
        return GgsRasterLayer(name, src)._fail("%s: %s"
                                               % (type(e).__name__, e))

    try:
        bands = [1]
        if ds.count >= 3:
            bands = [1, 2, 3]
        transform, bounds = _north_up(ds)
        lyr = GgsRasterLayer(
            name=name, source=src, crs=_crs_from_rasterio(ds),
            dataset=ds, bands=bands, width=ds.width, height=ds.height,
            dtype=str(ds.dtypes[0] if ds.dtypes else ""),
            nodata=ds.nodata, transform=transform,
            bounds=tuple(bounds), band_count=ds.count)
        return lyr
    except Exception as e:
        _log.exception("silent exception in read_raster")
        try:
            ds.close()
        except Exception:
            _log.exception("silent exception in read_raster")
        return GgsRasterLayer(name, src)._fail("%s: %s"
                                               % (type(e).__name__, e))


def _north_up(ds):
    t = ds.transform
    try:
        if (float(getattr(t, "e", 0.0)) > 0.0
                and abs(float(getattr(t, "b", 0.0))) <= 1e-12
                and abs(float(getattr(t, "d", 0.0))) <= 1e-12):
            _aff = type(t)
            _t2 = _aff(float(t.a), float(t.b), float(t.c),
                       float(t.d), -float(t.e),
                       float(t.f) + float(t.e) * int(ds.height))
            try:
                from rasterio.transform import array_bounds as _ab
                return _t2, tuple(_ab(int(ds.height), int(ds.width), _t2))
            except Exception:
                _log.exception("silent exception in _north_up")
                return _t2, (float(t.c), float(t.f),
                             float(t.c) + float(t.a) * int(ds.width),
                             float(t.f) + float(t.e) * int(ds.height))
    except Exception:
        _log.exception("silent exception in _north_up")
    return t, tuple(ds.bounds)


import logging
_log = logging.getLogger("gmagis")
from .formats import RASTER_WRITE_FORMATS as _RASTER_WRITE_ROWS

RASTER_DRIVERS = {}
for _suf, _drv, _n, _f, _e in _RASTER_WRITE_ROWS:
    RASTER_DRIVERS.setdefault(_suf, _drv)
RASTER_DRIVERS.update({
    ".tiff": "GTiff",
    ".jpeg": "JPEG",
})


def driver_for_raster(path, prefer_cog=False):
    if prefer_cog:
        return "COG"
    import os as _os
    return RASTER_DRIVERS.get(_os.path.splitext(str(path))[1].lower())


@_guard.off_ui("io.raster_io.write_raster")
class _RasterExportCancelled(Exception):
    pass


def _write_raster_sync(layer, path, driver=None, extent=None, bands=None,
                       compression=None, tiled=None, overwrite=True,
                       progress=None, cancel=None):
    import os as _os

    if not _HAS_RASTERIO:
        raise RuntimeError("缺少 rasterio")
    src_ds = layer.dataset()
    if src_ds is None:
        raise ValueError("图层没有打开的数据集")

    target = str(path or "")
    if not target:
        raise ValueError("没有输出路径")
    if _os.path.exists(target) and not overwrite:
        raise FileExistsError(target)

    drv = driver or driver_for_raster(target) or "GTiff"

    if extent is not None and not extent.is_empty():
        from rasterio.windows import Window, from_bounds, transform as _wtransform
        win = from_bounds(extent.xmin, extent.ymin, extent.xmax, extent.ymax,
                          src_ds.transform)
        c0 = max(0, int(round(win.col_off)))
        r0 = max(0, int(round(win.row_off)))
        c1 = min(int(src_ds.width), int(round(win.col_off + win.width)))
        r1 = min(int(src_ds.height), int(round(win.row_off + win.height)))
        if c1 <= c0 or r1 <= r0:
            raise ValueError("导出范围与数据没有交集")
        win = Window(c0, r0, c1 - c0, r1 - r0)
        out_transform = _wtransform(win, src_ds.transform)
        out_w, out_h = int(win.width), int(win.height)
    else:
        win = None
        out_transform = src_ds.transform
        out_w, out_h = int(src_ds.width), int(src_ds.height)

    if bands is None:
        band_list = list(range(1, int(src_ds.count) + 1))
    elif isinstance(bands, (list, tuple, set)):
        band_list = [int(b) for b in bands]
    else:
        band_list = [int(bands)]
    band_list = [b for b in band_list if 1 <= b <= int(src_ds.count)]
    if not band_list:
        raise ValueError("没有可导出的波段")
    if progress is not None:
        try:
            progress(0.10, "准备导出栅格…")
        except Exception:
            _log.exception("silent exception in _write_raster_sync")

    profile = {
        "driver": drv,
        "width": out_w,
        "height": out_h,
        "count": len(band_list),
        "dtype": str(src_ds.dtypes[band_list[0] - 1]),
        "crs": src_ds.crs,
        "transform": out_transform,
        "nodata": src_ds.nodata,
    }
    if compression and drv in ("GTiff", "COG", "HFA"):
        profile["compress"] = str(compression)
    if tiled and drv in ("GTiff", "COG"):
        profile["tiled"] = True
        profile["blockxsize"] = 256
        profile["blockysize"] = 256
    if drv == "COG":
        profile.pop("tiled", None)
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)

    with rasterio.open(target, "w", **profile) as dst:
        nb = len(band_list)
        for i, b in enumerate(band_list, start=1):
            if cancel is not None:
                try:
                    if cancel():
                        raise _RasterExportCancelled()
                except _RasterExportCancelled:
                    raise
                except Exception:
                    _log.exception("silent exception in _write_raster_sync")
            if win is not None:
                data = src_ds.read(b, window=win, boundless=True,
                                   fill_value=src_ds.nodata)
            else:
                data = src_ds.read(b)
            dst.write(data, i)
            if progress is not None:
                try:
                    progress(0.10 + 0.80 * (i / nb),
                             "正在写入波段 %d/%d" % (i, nb))
                except Exception:
                    _log.exception("silent exception in _write_raster_sync")
        try:
            dst.set_band_description(
                1, src_ds.descriptions[band_list[0] - 1] or "")
        except Exception:
            _log.exception("silent exception in _write_raster_sync")

    if progress is not None:
        try:
            progress(1.0, "导出完成")
        except Exception:
            _log.exception("silent exception in _write_raster_sync")

    return target


@_guard.offloaded("io.raster_io.write_raster", kind="io", name="写栅格")
def write_raster(layer, path, driver=None, extent=None, bands=None,
                 compression=None, tiled=None, overwrite=True,
                 progress=None, cancel=None):
    return _write_raster_sync(layer, path, driver=driver, extent=extent,
                              bands=bands, compression=compression,
                              tiled=tiled, overwrite=overwrite,
                              progress=progress, cancel=cancel)
