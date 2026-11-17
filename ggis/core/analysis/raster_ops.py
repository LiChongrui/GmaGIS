# -*- coding: utf-8 -*-

from __future__ import annotations

import math
import time

import numpy as np

try:
    import rasterio
    from rasterio import features as _rio_features
    from rasterio.enums import Resampling as _RResampling
    _HAS_RASTERIO = True
except Exception:
    _log.exception("silent exception")
    rasterio = None
    _rio_features = None
    _RResampling = None
    _HAS_RASTERIO = False

import logging
_log = logging.getLogger("gmagis")
from ggis.exec import guard as _guard

__all__ = [
    "RASTER_OPS", "RASTER_GROUPS", "raster_op_label", "raster_op_spec",
    "raster_op_names", "run_raster_op", "run_raster_job",
    "RasterJobResult", "RasterCancelled",
]


def _p_num(key, label, default=0.0, min=None, max=None, step=None):
    return {"key": key, "type": "number", "label": label,
            "default": default, "min": min, "max": max, "step": step}


def _p_int(key, label, default=1, min=None, max=None):
    return {"key": key, "type": "int", "label": label,
            "default": default, "min": min, "max": max}


def _p_text(key, label, default=""):
    return {"key": key, "type": "text", "label": label, "default": default}


def _p_choice(key, label, choices, default):
    return {"key": key, "type": "choice", "label": label,
            "default": default, "choices": list(choices)}


RASTER_GROUPS = ["地形分析", "栅格处理", "栅格代数"]

RASTER_OPS = {
    "slope": {
        "label": "坡度",
        "group": "地形分析",
        "out_kind": "raster",
        "hint": "",
        "params": [],
    },
    "aspect": {
        "label": "坡向",
        "group": "地形分析",
        "out_kind": "raster",
        "hint": "",
        "params": [],
    },
    "hillshade": {
        "label": "山体阴影",
        "group": "地形分析",
        "out_kind": "raster",
        "hint": "",
        "params": [
            _p_num("altitude", "太阳高度角（度）", 45.0, 0.0, 90.0, 1.0),
            _p_num("azimuth", "太阳方位角（度）", 315.0, 0.0, 360.0, 1.0),
            _p_choice("z_factor", "垂直夸张",
                      [("1", "1（不变）"), ("2", "2"), ("3", "3"),
                       ("5", "5")], "1"),
        ],
    },
    "contour": {
        "label": "等高线",
        "group": "地形分析",
        "out_kind": "vector",
        "hint": "",
        "params": [
            _p_num("interval", "等高距", 100.0, 0.0, None, 10.0),
            _p_num("base", "起始高程", 0.0, None, None, 10.0),
        ],
    },
    "clip": {
        "label": "裁剪栅格",
        "group": "栅格处理",
        "out_kind": "raster",
        "hint": "",
        "needs_mask": True,
        "needs_extent": True,
        "params": [],
    },
    "mosaic": {
        "label": "影像镶嵌",
        "group": "栅格处理",
        "out_kind": "raster",
        "hint": "",
        "needs_layers": True,
        "params": [
            _p_choice("method", "镶嵌方式",
                      [("first", "先到先得（按勾选顺序）"),
                       ("last", "后层覆盖"),
                       ("mean", "均值"),
                       ("max", "最大值")], "first"),
        ],
    },
    "stack_bands": {
        "label": "波段合成",
        "group": "栅格处理",
        "out_kind": "raster",
        "hint": "",
        "needs_layers": True,
        "params": [],
    },
    "resample": {
        "label": "重采样",
        "group": "栅格处理",
        "out_kind": "raster",
        "hint": "",
        "params": [
            _p_num("xres", "X 像元大小（米）", 0.0, 0.0, None, 1.0),
            _p_num("yres", "Y 像元大小（米）", 0.0, 0.0, None, 1.0),
            _p_choice("method", "重采样方法",
                      [("bilinear", "双线性（连续）"),
                       ("nearest", "最近邻（分类）"),
                       ("cubic", "三次卷积"),
                       ("average", "均值（降采样）")], "bilinear"),
        ],
    },
    "extract_band": {
        "label": "波段提取",
        "group": "栅格处理",
        "out_kind": "raster",
        "hint": "",
        "params": [
            _p_int("band", "波段号（从 1 起）", 1, 1, 9999),
        ],
    },
    "raster_calculator": {
        "label": "栅格计算器",
        "group": "栅格代数",
        "out_kind": "raster",
        "hint": "",
        "params": [
            _p_text("expr", "表达式", "b1"),
        ],
    },
    "reclassify": {
        "label": "重分类",
        "group": "栅格代数",
        "out_kind": "raster",
        "hint": "",
        "params": [
            _p_choice("method", "模式",
                      [("manual", "手动区间"), ("equal", "等分区间")], "manual"),
            _p_text("ranges", "区间（手动，lo:hi:val;…）", "0:100:1;100:200:2"),
            _p_int("classes", "类数（等分）", 5, 2, 255),
        ],
    },
    "normalize": {
        "label": "归一化",
        "group": "栅格代数",
        "out_kind": "raster",
        "hint": "",
        "params": [
            _p_choice("clip", "百分位数截断",
                      [("no", "不截断（min-max）"),
                       ("yes", "2%/98% 截断")], "no"),
        ],
    },
    "raster_to_polygons": {
        "label": "栅格转面",
        "group": "栅格代数",
        "out_kind": "vector",
        "hint": "",
        "params": [],
    },
}


class RasterCancelled(Exception):
    pass


class RasterJobResult:

    def __init__(self):
        self.op = ""
        self.out_kind = "raster"
        self.raster_path = ""
        self.vector_layer = None
        self.crs = None
        self.name = ""
        self.ms = 0.0
        self.warnings = []
        self.cancelled = False


def raster_op_spec(op):
    return RASTER_OPS.get(str(op), {})


def raster_op_label(op):
    return RASTER_OPS.get(str(op), {}).get("label", str(op))


def raster_op_names():
    return list(RASTER_OPS.keys())


def _crs_to_rasterio(crs):
    if crs is None:
        return None
    try:
        epsg = crs.to_epsg() if hasattr(crs, "to_epsg") else None
        if epsg:
            return rasterio.crs.CRS.from_epsg(int(epsg))
    except Exception:
        _log.exception("silent exception in _crs_to_rasterio")
    try:
        pj = crs.to_pyproj() if hasattr(crs, "to_pyproj") else None
        if pj is not None:
            return rasterio.crs.CRS.from_user_input(pj)
    except Exception:
        _log.exception("silent exception in _crs_to_rasterio")
    try:
        auth = crs.authid() if hasattr(crs, "authid") else ""
        if auth:
            return rasterio.crs.CRS.from_user_input(auth)
    except Exception:
        _log.exception("silent exception in _crs_to_rasterio")
    return None


def _read_raster_input(inp):
    if inp is None:
        return None
    if isinstance(inp, str):
        from ggis.io.raster_io import read_raster
        return read_raster(inp)
    return inp


def _read_vector_input(inp):
    if inp is None:
        return None
    if isinstance(inp, str):
        from ggis.io.vector_io import read_vector
        return read_vector(inp)
    return inp


def _read_band(layer, band=1):
    ds = layer.dataset()
    if ds is None:
        raise ValueError("栅格数据集未打开")
    n = int(layer.band_count()) or 1
    b = max(1, min(int(band), n))
    arr = ds.read(b)
    arr = np.asarray(arr)
    nd = layer.nodata()
    if nd is not None and not (isinstance(nd, float) and np.isnan(nd)):
        valid = ~np.isclose(arr.astype(np.float64), float(nd))
    else:
        valid = np.isfinite(arr.astype(np.float64))
    return arr.astype(np.float64), valid, nd, ds.transform, layer.crs()


def _read_all_bands(layer):
    ds = layer.dataset()
    if ds is None:
        raise ValueError("栅格数据集未打开")
    data = ds.read()
    data = np.asarray(data, dtype=np.float64)
    nd = layer.nodata()
    if nd is not None and not (isinstance(nd, float) and np.isnan(nd)):
        valid = ~np.isclose(data, float(nd))
    else:
        valid = np.isfinite(data)
    valid = np.all(valid, axis=0) if valid.ndim == 3 else valid
    return data, valid, nd, ds.transform, layer.crs()


def _write_raster_array(arr, transform, crs, nodata, path,
                        driver="GTiff", compress="DEFLATE",
                        progress=None, cancel=None):
    import os as _os
    from rasterio.transform import Affine

    if not _HAS_RASTERIO:
        raise RuntimeError("缺少 rasterio")
    if _os.path.exists(path):
        try:
            _os.remove(path)
        except Exception:
            _log.exception("silent exception in _write_raster_array")
    count = 1 if arr.ndim == 2 else int(arr.shape[0])
    dtype = "float32" if arr.dtype.kind == "f" else str(arr.dtype)
    profile = {
        "driver": driver,
        "height": int(arr.shape[-2]),
        "width": int(arr.shape[-1]),
        "count": count,
        "dtype": dtype,
        "crs": _crs_to_rasterio(crs),
        "transform": transform,
        "nodata": nodata,
    }
    if driver in ("GTiff", "COG", "HFA"):
        profile["compress"] = compress
    if driver == "GTiff":
        profile["tiled"] = True
        profile["blockxsize"] = 256
        profile["blockysize"] = 256
    if driver == "COG":
        profile.pop("tiled", None)
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
    if isinstance(transform, Affine) is False:
        profile["transform"] = Affine(*list(transform)[0:6])
    with rasterio.open(path, "w", **profile) as dst:
        if arr.ndim == 2:
            dst.write(arr.astype(dtype), 1)
        else:
            for i in range(count):
                dst.write(arr[i].astype(dtype), i + 1)
    if progress is not None:
        try:
            progress(1.0, "写出完成")
        except Exception:
            _log.exception("silent exception in _write_raster_array")
    return path


def _mask_from_vector(layer, transform, width, height, crs, all_touched=True):
    if layer is None:
        return None
    from shapely.ops import transform as _shp_tr
    try:
        from pyproj import Transformer
    except Exception:
        _log.exception("silent exception in _mask_from_vector")
        Transformer = None
    geoms = list(layer.geoms())
    if not geoms:
        return None
    dst_crs = _crs_to_rasterio(crs)
    src_crs = _crs_to_rasterio(layer.crs())
    tr = None
    if Transformer is not None and dst_crs is not None and src_crs is not None:
        try:
            tr = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
        except Exception:
            _log.exception("silent exception in _mask_from_vector")
            tr = None
    if tr is not None:
        def _f(coords):
            x, y = tr.transform(coords[:, 0], coords[:, 1])
            return np.column_stack([x, y])
        geoms = [_shp_tr(_f, g) for g in geoms]
    shapes = [(g, 1) for g in geoms if g is not None]
    if not shapes:
        return None
    mask = _rio_features.rasterize(
        shapes, out_shape=(int(height), int(width)),
        transform=transform, fill=0, default_value=1,
        all_touched=all_touched).astype(bool)
    return mask


def _report(progress, frac, text):
    if progress is not None:
        try:
            progress(float(frac), str(text))
        except Exception:
            _log.exception("silent exception in _report")


def _check_cancel(cancel):
    if cancel is not None and cancel():
        raise RasterCancelled()


def _horn_gradients(z, valid, xres, yres):
    zp = np.pad(z, 1, mode="edge")
    vp = np.pad(valid, 1, constant_values=False)
    a = zp[0:-2, 0:-2]; b = zp[0:-2, 1:-1]; c = zp[0:-2, 2:]
    d = zp[1:-1, 0:-2];                      f = zp[1:-1, 2:]
    g = zp[2:, 0:-2];    h = zp[2:, 1:-1];   i = zp[2:, 2:]
    va = vp[0:-2, 0:-2]; vb = vp[0:-2, 1:-1]; vc = vp[0:-2, 2:]
    vd = vp[1:-1, 0:-2];                      vf = vp[1:-1, 2:]
    vg = vp[2:, 0:-2];    vh = vp[2:, 1:-1];   vi = vp[2:, 2:]
    dzdx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * xres)
    dzdy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * yres)
    good = va & vb & vc & vd & vf & vg & vh & vi
    bad = ~good
    dzdx[bad] = 0.0
    dzdy[bad] = 0.0
    return dzdx, dzdy, bad


def _op_slope(params, values, progress, cancel):
    z, valid, nd, transform, crs = _read_band(_read_raster_input(params["input"]))
    xres, yres = _res_from_transform(transform)
    _check_cancel(cancel)
    _report(progress, 0.3, "计算坡度")
    dzdx, dzdy, _ = _horn_gradients(z, valid, xres, yres)
    slope = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2)) * 180.0 / math.pi
    out = slope.astype(np.float32)
    out = np.where(valid, out, np.float32(-9999.0))
    return out, -9999.0, transform, crs


def _op_aspect(params, values, progress, cancel):
    z, valid, nd, transform, crs = _read_band(_read_raster_input(params["input"]))
    xres, yres = _res_from_transform(transform)
    _check_cancel(cancel)
    _report(progress, 0.3, "计算坡向")
    dzdx, dzdy, _ = _horn_gradients(z, valid, xres, yres)
    asp = 180.0 - np.degrees(np.arctan2(dzdy, -dzdx))
    asp = asp % 360.0
    flat = (np.abs(dzdx) < 1e-12) & (np.abs(dzdy) < 1e-12)
    asp = np.where(flat, -1.0, asp)
    out = asp.astype(np.float32)
    out = np.where(valid, out, np.float32(-9999.0))
    return out, -9999.0, transform, crs


def _op_hillshade(params, values, progress, cancel):
    z, valid, nd, transform, crs = _read_band(_read_raster_input(params["input"]))
    xres, yres = _res_from_transform(transform)
    _check_cancel(cancel)
    dzdx, dzdy, bad = _horn_gradients(z, valid, xres, yres)
    slope = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))
    alt = math.radians(float(values.get("altitude", 45.0)))
    az = math.radians(float(values.get("azimuth", 315.0)))
    zf = float(values.get("z_factor", 1) or 1)
    asp = np.arctan2(dzdy, -dzdx)
    shade = (np.cos(alt) * np.cos(slope)
             + np.sin(alt) * np.sin(slope) * np.cos(az - asp)) * zf
    shade = np.clip(shade, 0.0, 1.0) * 255.0
    out = shade.astype(np.uint8)
    out = np.where(valid, out, np.uint8(0))
    return out, 0, transform, crs


def _op_contour(params, values, progress, cancel):
    from shapely.geometry import shape as _shape, LineString
    z, valid, nd, transform, crs = _read_band(_read_raster_input(params["input"]))
    interval = abs(float(values.get("interval", 100.0)) or 100.0)
    base = float(values.get("base", 0.0) or 0.0)
    if interval < 1e-9:
        raise ValueError("等高距必须大于 0")
    _check_cancel(cancel)
    zmin = float(np.nanmin(np.where(valid, z, np.nan)))
    zmax = float(np.nanmax(np.where(valid, z, np.nan)))
    levels = np.arange(base, zmax + interval * 0.5, interval)
    levels = levels[levels >= zmin - interval * 0.5]
    geoms, attrs, fields = [], [], [("elev", "Real")]
    total = max(1, len(levels))
    for k, lv in enumerate(levels):
        _check_cancel(cancel)
        _report(progress, 0.1 + 0.85 * (k + 1) / total, "提取等高线 %.1f" % lv)
        mask = (valid & (z >= lv)).astype(np.uint8)
        if mask.sum() == 0:
            continue
        for geom, _val in _rio_features.shapes(
                mask, mask=mask.astype(bool), transform=transform):
            try:
                poly = _shape(geom)
            except Exception:
                _log.exception("silent exception in _op_contour")
                continue
            for ring in ([poly.exterior] + list(poly.interiors)):
                if ring is None or len(ring.coords) < 2:
                    continue
                geoms.append(LineString(ring.coords))
                attrs.append({"elev": float(lv)})
    if not geoms:
        raise ValueError("没有生成任何等高线（等高距可能过大）")
    return _make_vector_layer(geoms, attrs, fields, crs, "等高线")


def _res_from_transform(transform):
    try:
        return (abs(float(transform.a)), abs(float(transform.e)))
    except Exception:
        _log.exception("silent exception in _res_from_transform")
        return (1.0, 1.0)


def _clip_window_impl(layer, minx, miny, maxx, maxy):
    ds = layer.dataset()
    transform = ds.transform
    width, height = layer.width(), layer.height()
    from rasterio.windows import from_bounds, Window
    win = from_bounds(minx, miny, maxx, maxy, transform)
    c0 = max(0, int(round(win.col_off)))
    r0 = max(0, int(round(win.row_off)))
    c1 = min(int(width), int(round(win.col_off + win.width)))
    r1 = min(int(height), int(round(win.row_off + win.height)))
    if c1 <= c0 or r1 <= r0:
        raise ValueError("裁剪范围与数据没有交集")
    win = Window(c0, r0, c1 - c0, r1 - r0)
    out_transform = rasterio.windows.transform(win, transform)
    arr = ds.read(window=win)
    arr = np.asarray(arr)
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
    return arr, layer.nodata(), out_transform, layer.crs()


def _op_clip(params, values, progress, cancel):
    layer = _read_raster_input(params["input"])
    mask_lyr = _read_vector_input(params.get("mask"))
    ext = params.get("extent")
    if mask_lyr is not None:
        _check_cancel(cancel)
        ds = layer.dataset()
        transform = ds.transform
        nd = layer.nodata()
        data = ds.read()
        data = np.asarray(data, dtype=np.float64)
        mask = _mask_from_vector(mask_lyr, transform, layer.width(),
                                 layer.height(), layer.crs())
        _check_cancel(cancel)
        if mask is None:
            raise ValueError("没有可用的裁剪掩模（矢量图层为空）")
        out_nd = float(nd) if nd is not None else -9999.0
        out = np.where(mask[np.newaxis, ...], data, out_nd).astype(np.float32)
        if out.ndim == 3 and out.shape[0] == 1:
            out = out[0]
        _report(progress, 0.6, "写出裁剪结果")
        return out, out_nd, transform, layer.crs()
    if ext is not None:
        try:
            minx, miny = float(ext.xmin), float(ext.ymin)
            maxx, maxy = float(ext.xmax), float(ext.ymax)
        except Exception:
            raise ValueError("裁剪范围无效")
        if maxx <= minx or maxy <= miny:
            raise ValueError("裁剪范围无效")
        _check_cancel(cancel)
        _report(progress, 0.4, "读取裁剪窗口")
        arr, nd, tr, crs = _clip_window_impl(layer, minx, miny, maxx, maxy)
        _report(progress, 0.6, "写出裁剪结果")
        return arr, nd, tr, crs
    raise ValueError("请先设置裁剪范围或选择掩模图层")


def _op_resample(params, values, progress, cancel):
    layer = _read_raster_input(params["input"])
    ds = layer.dataset()
    transform = ds.transform
    xres = float(values.get("xres") or 0.0)
    yres = float(values.get("yres") or 0.0)
    if xres <= 0 or yres <= 0:
        xres = yres = (xres if xres > 0 else yres) or _res_from_transform(transform)[0]
    if xres <= 0:
        raise ValueError("重采样像元大小必须大于 0")
    old_x, old_y = _res_from_transform(transform)
    ext = layer.extent()
    minx, miny, maxx, maxy = ext.xmin, ext.ymin, ext.xmax, ext.ymax
    new_w = max(1, int(round(abs(maxx - minx) / xres)))
    new_h = max(1, int(round(abs(maxy - miny) / yres)))
    method = str(values.get("method", "bilinear") or "bilinear")
    res_map = {
        "bilinear": _RResampling.bilinear,
        "nearest": _RResampling.nearest,
        "cubic": _RResampling.cubic,
        "average": _RResampling.average,
    }
    rio_res = res_map.get(method, _RResampling.bilinear)
    from rasterio.transform import from_origin as _rio_from_origin
    from rasterio.warp import reproject as _rio_reproject
    new_transform = _rio_from_origin(minx, maxy, xres, yres)
    n = int(layer.band_count()) or 1
    out = np.empty((n, new_h, new_w), dtype=np.float32)
    for b in range(1, n + 1):
        _check_cancel(cancel)
        _report(progress, 0.2 + 0.6 * b / n, "重采样波段 %d/%d" % (b, n))
        band = ds.read(b)
        band = np.asarray(band, dtype=np.float32)
        res = _rio_reproject(
            source=band, src_transform=transform, src_crs=_crs_to_rasterio(layer.crs()),
            destination=np.empty((new_h, new_w), dtype=np.float32),
            dst_transform=new_transform,
            dst_crs=_crs_to_rasterio(layer.crs()),
            resampling=rio_res,
        )
        out[b - 1] = np.asarray(res[0], dtype=np.float32)
    nd = layer.nodata()
    out_nd = nd if nd is not None else -9999.0
    return out, out_nd, new_transform, layer.crs()


def _op_extract_band(params, values, progress, cancel):
    layer = _read_raster_input(params["input"])
    ds = layer.dataset()
    n = int(layer.band_count()) or 1
    band = max(1, min(int(values.get("band", 1) or 1), n))
    arr = ds.read(band).astype(np.float32)
    nd = layer.nodata()
    out_nd = nd if nd is not None else -9999.0
    _check_cancel(cancel)
    _report(progress, 0.6, "写出波段")
    return arr, out_nd, ds.transform, layer.crs()


_MOSAIC_PIXEL_CAP = 16_000_000


def _union_grid(layers):
    from rasterio.transform import from_origin as _rio_from_origin
    if not layers:
        raise ValueError("请至少选择一个栅格图层")
    minx = min(float(l.extent().xmin) for l in layers)
    miny = min(float(l.extent().ymin) for l in layers)
    maxx = max(float(l.extent().xmax) for l in layers)
    maxy = max(float(l.extent().ymax) for l in layers)
    res = None
    for l in layers:
        rx, ry = l.resolution()
        if rx > 0 and ry > 0 and (res is None or rx * ry < res[0] * res[1]):
            res = (rx, ry)
    if res is None:
        raise ValueError("图层分辨率无效")
    w = max(1, int(round((maxx - minx) / res[0])))
    h = max(1, int(round((maxy - miny) / res[1])))
    if w * h > _MOSAIC_PIXEL_CAP:
        raise ValueError("合并范围过大（%d×%d 像元），请缩小范围或降低分辨率"
                         % (w, h))
    return (_rio_from_origin(minx, maxy, res[0], res[1]), w, h,
            _crs_to_rasterio(layers[0].crs()))


def _reproject_to_grid(band, layer, dst_transform, dst_crs, w, h):
    from rasterio.warp import reproject as _rio_reproject
    dst = np.full((h, w), np.nan, dtype=np.float32)
    _rio_reproject(
        source=np.asarray(band, dtype=np.float64),
        src_transform=layer.dataset().transform,
        src_crs=_crs_to_rasterio(layer.crs()),
        src_nodata=(float(layer.nodata())
                    if layer.nodata() is not None else None),
        destination=dst, dst_transform=dst_transform, dst_crs=dst_crs,
        dst_nodata=np.nan,
        resampling=_RResampling.bilinear)
    return dst


def _layer_valid(arr, layer):
    m = np.isfinite(arr)
    nd = layer.nodata()
    if nd is not None:
        m &= ~np.isclose(arr, float(nd))
    return m


def _op_mosaic(params, values, progress, cancel):
    layers = [_read_raster_input(l) for l in (params.get("layers") or [])]
    layers = [l for l in layers if l is not None and l.is_valid()]
    if not layers:
        raise ValueError("请至少选择一个参与镶嵌的栅格图层")
    method = str(values.get("method", "first") or "first")
    transform, w, h, dst_crs = _union_grid(layers)
    nb = max(1, min(int(l.band_count() or 1) for l in layers))
    out = np.full((nb, h, w), np.nan, dtype=np.float32)
    s = (np.zeros((nb, h, w), dtype=np.float64) if method == "mean" else None)
    c = (np.zeros((nb, h, w), dtype=np.float32) if method == "mean" else None)
    total = nb * len(layers)
    done = 0
    for b in range(1, nb + 1):
        cur = out[b - 1]
        for l in layers:
            _check_cancel(cancel)
            arr = _reproject_to_grid(l.dataset().read(b), l, transform,
                                     dst_crs, w, h)
            done += 1
            _report(progress, 0.1 + 0.8 * done / max(1, total),
                    "镶嵌波段 %d/%d" % (b, nb))
            valid = _layer_valid(arr, l)
            if method == "last":
                cur[valid] = arr[valid]
            elif method == "mean":
                s[b - 1][valid] += arr[valid]
                c[b - 1][valid] += 1.0
            elif method == "max":
                np.fmax(cur, np.where(valid, arr, np.nan), out=cur)
            else:
                m = valid & np.isnan(cur)
                cur[m] = arr[m]
    if method == "mean":
        m = c > 0
        out[m] = (s[m] / c[m]).astype(np.float32)
    out32 = np.nan_to_num(out, nan=-9999.0).astype(np.float32)
    _report(progress, 0.95, "写出镶嵌结果")
    return out32, -9999.0, transform, layers[0].crs()


def _op_stack_bands(params, values, progress, cancel):
    layers = [_read_raster_input(l) for l in (params.get("layers") or [])]
    layers = [l for l in layers if l is not None and l.is_valid()]
    if not layers:
        raise ValueError("请至少选择一个参与合成的栅格图层")
    transform, w, h, dst_crs = _union_grid(layers)
    plan = []
    for l in layers:
        for b in range(1, int(l.band_count() or 1) + 1):
            plan.append((l, b))
    if not plan:
        raise ValueError("没有可合成的波段")
    out = np.full((len(plan), h, w), np.nan, dtype=np.float32)
    total = len(plan)
    for k, (l, b) in enumerate(plan):
        _check_cancel(cancel)
        arr = _reproject_to_grid(l.dataset().read(b), l, transform,
                                 dst_crs, w, h)
        arr[~_layer_valid(arr, l)] = np.nan
        out[k] = arr
        _report(progress, 0.1 + 0.8 * (k + 1) / total,
                "合成波段 %d/%d" % (k + 1, total))
    out32 = np.nan_to_num(out, nan=-9999.0).astype(np.float32)
    _report(progress, 0.95, "写出合成结果")
    return out32, -9999.0, transform, layers[0].crs()


def _safe_eval_expr(expr, arrays):
    ns = {}
    for i, a in enumerate(arrays, start=1):
        ns["b%d" % i] = a
    allowed = {
        "np": np,
        "sin": np.sin, "cos": np.cos, "tan": np.tan,
        "arcsin": np.arcsin, "arccos": np.arccos, "arctan": np.arctan,
        "arctan2": np.arctan2,
        "sqrt": np.sqrt, "abs": np.abs, "exp": np.exp, "log": np.log,
        "log10": np.log10, "power": np.power, "minimum": np.minimum,
        "maximum": np.maximum, "where": np.where, "floor": np.floor,
        "ceil": np.ceil, "round": np.round, "mean": np.mean, "median": np.median,
        "std": np.std, "clip": np.clip, "nan_to_num": np.nan_to_num,
        "deg2rad": np.deg2rad, "rad2deg": np.rad2deg,
        "pi": np.pi, "e": np.e,
    }
    try:
        return eval(expr, {"__builtins__": {}}, {**ns, **allowed})
    except Exception as e:
        raise ValueError("表达式错误：%s（%s）" % (expr, e))


def _op_raster_calculator(params, values, progress, cancel):
    data, valid, nd, transform, crs = _read_all_bands(
        _read_raster_input(params["input"]))
    _check_cancel(cancel)
    expr = str(values.get("expr", "b1") or "b1").strip()
    if not expr:
        raise ValueError("表达式不能为空")
    _report(progress, 0.4, "计算表达式")
    work = data.copy()
    if valid is not None:
        work[:, ~valid] = np.nan
    res = _safe_eval_expr(expr, [work[i] for i in range(data.shape[0])])
    res = np.asarray(res, dtype=np.float64)
    if res.ndim == 0:
        res = np.full((data.shape[1], data.shape[2]), float(res))
    elif res.ndim == 1:
        res = np.broadcast_to(res.reshape(-1, 1),
                              (data.shape[1], data.shape[2])).copy()
    res = np.nan_to_num(res, nan=-9999.0)
    out = res.astype(np.float32)
    out = np.where(valid if valid is not None else np.ones_like(out, bool),
                   out, np.float32(-9999.0))
    _report(progress, 0.8, "写出结果")
    return out, -9999.0, transform, crs


def _op_reclassify(params, values, progress, cancel):
    data, valid, nd, transform, crs = _read_all_bands(
        _read_raster_input(params["input"]))
    arr = data[0] if data.shape[0] > 1 else data
    arr = arr.copy()
    method = str(values.get("method", "manual") or "manual")
    _check_cancel(cancel)
    out = np.full_like(arr, np.nan)
    if method == "equal":
        classes = max(2, int(values.get("classes", 5) or 5))
        vmin = np.nanmin(np.where(valid, arr, np.nan))
        vmax = np.nanmax(np.where(valid, arr, np.nan))
        if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
            raise ValueError("无法计算等分区间（数据无效）")
        edges = np.linspace(vmin, vmax, classes + 1)
        for k in range(classes):
            lo, hi = edges[k], edges[k + 1]
            m = valid & (arr >= lo) & (arr < hi if k < classes - 1 else arr <= hi)
            out[m] = float(k + 1)
        _report(progress, 0.6, "写出重分类结果")
    else:
        raw = str(values.get("ranges", "") or "")
        rules = []
        for part in raw.split(";"):
            part = part.strip()
            if not part:
                continue
            segs = part.split(":")
            if len(segs) != 3:
                continue
            try:
                lo = float(segs[0]); hi = float(segs[1]); val = float(segs[2])
            except Exception:
                _log.exception("silent exception in _op_reclassify")
                continue
            rules.append((lo, hi, val))
        if not rules:
            raise ValueError("未解析到任何区间（格式应为 lo:hi:val;…）")
        for lo, hi, val in rules:
            out[(valid & (arr >= lo) & (arr < hi))] = val
        _report(progress, 0.6, "写出重分类结果")
    out = np.where(valid, out, np.nan)
    out32 = np.nan_to_num(out, nan=-9999.0).astype(np.float32)
    return out32, -9999.0, transform, crs


def _op_normalize(params, values, progress, cancel):
    data, valid, nd, transform, crs = _read_all_bands(
        _read_raster_input(params["input"]))
    arr = data[0] if data.shape[0] > 1 else data
    clip = str(values.get("clip", "no") or "no") == "yes"
    _check_cancel(cancel)
    v = np.where(valid, arr, np.nan)
    if clip:
        lo = np.nanpercentile(v, 2)
        hi = np.nanpercentile(v, 98)
    else:
        lo = np.nanmin(v)
        hi = np.nanmax(v)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        raise ValueError("归一化失败（数据范围无效）")
    norm = (arr - lo) / (hi - lo)
    norm = np.clip(norm, 0.0, 1.0)
    norm = np.where(valid, norm, np.nan)
    out = np.nan_to_num(norm, nan=-9999.0).astype(np.float32)
    _report(progress, 0.6, "写出归一化结果")
    return out, -9999.0, transform, crs


def _make_vector_layer(geoms, attrs, fields, crs, name):
    from ggis.core.model.layer import GgsVectorLayer
    lyr = GgsVectorLayer(name, crs=crs, geometry_type="MultiLineString"
                         if fields and False else _geom_type_of(geoms),
                         geoms=geoms, attrs=attrs, fields=fields)
    lyr.set_visible(True)
    return lyr


def _geom_type_of(geoms):
    from shapely.geometry import LineString, Polygon, MultiPolygon, Point
    for g in geoms:
        t = getattr(g, "geom_type", "")
        if t in ("Polygon", "MultiPolygon"):
            return "MultiPolygon"
        if t == "LineString":
            return "MultiLineString"
        if t == "Point":
            return "MultiPoint"
    return "GeometryCollection"


def _op_raster_to_polygons(params, values, progress, cancel):
    from shapely.geometry import shape as _shape
    data, valid, nd, transform, crs = _read_band(
        _read_raster_input(params["input"]))
    _check_cancel(cancel)
    src = data.astype(np.float32)
    geoms, attrs, fields = [], [], [("value", "Real")]
    total = int(src.shape[0] * src.shape[1])
    done = 0
    for geom, val in _rio_features.shapes(
            src, mask=valid, transform=transform):
        done += 1
        if done % 5000 == 0:
            _check_cancel(cancel)
            _report(progress, 0.1 + 0.85 * done / max(1, total), "栅格转面")
        try:
            g = _shape(geom)
        except Exception:
            _log.exception("silent exception in _op_raster_to_polygons")
            continue
        if g is None or g.is_empty:
            continue
        geoms.append(g)
        attrs.append({"value": float(val)})
    if not geoms:
        raise ValueError("栅格转面没有生成任何面")
    _report(progress, 0.95, "写出面")
    return _make_vector_layer(geoms, attrs, fields, crs, "栅格转面")


RUNNERS = {
    "slope": _op_slope,
    "aspect": _op_aspect,
    "hillshade": _op_hillshade,
    "contour": _op_contour,
    "clip": _op_clip,
    "resample": _op_resample,
    "extract_band": _op_extract_band,
    "mosaic": _op_mosaic,
    "stack_bands": _op_stack_bands,
    "raster_calculator": _op_raster_calculator,
    "reclassify": _op_reclassify,
    "normalize": _op_normalize,
    "raster_to_polygons": _op_raster_to_polygons,
}


@_guard.off_ui("core.raster_ops.run_raster_op")
def run_raster_op(op, params, progress=None, cancel=None):
    runner = RUNNERS.get(str(op))
    if runner is None:
        raise ValueError("未知栅格操作：%s" % op)
    spec = raster_op_spec(op)
    values = dict(params.get("values") or {})
    _report(progress, 0.1, "读取输入")
    result = runner(params, values, progress, cancel)
    return spec.get("out_kind", "raster"), result


def run_raster_job(op, params, to_file=False, path="", driver="",
                   creation_options=None, result_name="", progress=None,
                   cancel=None):
    res = RasterJobResult()
    res.op = str(op)
    spec = raster_op_spec(op)
    res.out_kind = spec.get("out_kind", "raster")
    res.name = ((params.get("output_name") if isinstance(params, dict) else "")
                or result_name or spec.get("label", op))
    t0 = time.perf_counter()
    try:
        kind, payload = run_raster_op(op, params, progress=progress,
                                     cancel=cancel)
        if kind == "vector":
            lyr = payload
            res.crs = lyr.crs() if hasattr(lyr, "crs") else None
            if to_file and path:
                _write_vector_result(lyr, path, driver)
            res.vector_layer = lyr
        else:
            arr, nodata, transform, crs = payload
            res.crs = crs
            drv = driver or "GTiff"
            if not path:
                import os as _os
                import tempfile as _tf
                path = _os.path.join(
                    _tf.gettempdir(),
                    "gmagis_raster_%d.tif" % int(time.perf_counter() * 1e6))
            _write_raster_array(arr, transform, crs, nodata, path,
                                driver=drv, progress=progress, cancel=cancel)
            res.raster_path = path
        if progress is not None:
            _report(progress, 1.0, "完成")
    except RasterCancelled:
        res.cancelled = True
        raise
    except Exception:
        raise
    res.ms = (time.perf_counter() - t0) * 1000.0
    return res


def _write_vector_result(lyr, path, driver):
    from ggis.io.vector_io import _write_vector_sync
    suffix = (str(path).lower().rsplit(".", 1)[-1] if "." in str(path) else "")
    drv = driver or ("GPKG" if suffix == "gpkg" else "")
    _write_vector_sync(
        path, lyr.geoms(), attrs=lyr.attrs(), fields=lyr.fields(),
        crs=lyr.crs(), driver=drv or None,
        geometry_type=lyr.geometry_type())
