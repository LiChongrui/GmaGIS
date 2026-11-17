# -*- coding: utf-8 -*-

import os
import uuid

import numpy as np

from ggis.core.app import i18n
from ggis.core.crs import GgsCoordinateReferenceSystem as GgsCrs
from ggis.core.crs.extent import GgsRectangle
from .geometry import base_kind, normalize_geometry_type
import logging
_log = logging.getLogger("gmagis")

__all__ = ["GgsMapLayer", "GgsVectorLayer", "GgsRasterLayer", "GgsTileLayer",
           "LAYER_VECTOR", "LAYER_RASTER", "LAYER_TILE",
           "TABLE_LAYER_FORBIDDEN", "layer_allows"]

LAYER_VECTOR = "vector"
LAYER_RASTER = "raster"
LAYER_TILE = "tile"

TABLE_LAYER_FORBIDDEN = frozenset((
    "legend",
    "zoom", "zoom_sel",
    "toggle_labels", "labels",
    "symbol",
    "filter",
    "export_style",
))


def layer_allows(layer, action):
    if layer is None:
        return True
    try:
        if not layer.is_table():
            return True
    except Exception:
        return True
    return action not in TABLE_LAYER_FORBIDDEN


def _rio_resampling(value):
    from ggis.core.analysis import resampling as _RS
    flag = _RS.to_rasterio(value)
    return flag if flag is not None else 0


def _resize_nearest(a, out_h, out_w):
    a = np.asarray(a)
    if a.ndim == 2:
        a = a[None, ...]
    n, h, w = a.shape
    if h == out_h and w == out_w:
        return a
    yi = np.clip((np.arange(out_h) + 0.5) * (h / out_h) - 0.5,
                 0, h - 1).astype(np.intp)
    xi = np.clip((np.arange(out_w) + 0.5) * (w / out_w) - 0.5,
                 0, w - 1).astype(np.intp)
    return a[:, yi][:, :, xi]

_PYR_WINDOW_MIN_PX = 32_000_000

_PYR_PROBE_DIV = 64

_layer_seq = [0]


def _next_layer_id():
    _layer_seq[0] += 1
    return "L%d" % _layer_seq[0]


def reserve_layer_id(lid):
    try:
        num = int(str(lid).strip()[1:])
    except Exception:
        _log.exception("silent exception in reserve_layer_id")
        return
    if num > _layer_seq[0]:
        _layer_seq[0] = num


def assign_layer_id(layer, lid):
    s = str(lid or "").strip()
    if not s or not hasattr(layer, "_id"):
        return
    try:
        layer._id = s
    except Exception:
        _log.exception("silent exception in assign_layer_id")
        return
    reserve_layer_id(s)


def data_version(layer):
    return int(layer.__dict__.get("_data_version", 0))


def bump_data_version(layer):
    try:
        layer._data_version = data_version(layer) + 1
    except Exception:
        _log.exception("silent exception in bump_data_version")


def source_generation(layer):
    return int(layer.__dict__.get("_source_gen", 0))


def bump_source_generation(layer):
    try:
        layer._source_gen = source_generation(layer) + 1
    except Exception:
        _log.exception("silent exception in bump_source_generation")


def subset_generation(layer):
    return int(layer.__dict__.get("_subset_gen", 0))


def bump_subset_generation(layer):
    try:
        layer._subset_gen = subset_generation(layer) + 1
    except Exception:
        _log.exception("silent exception in bump_subset_generation")


def freeze_layer(layer):
    import copy as _copy
    try:
        snap = _copy.copy(layer)
    except Exception:
        _log.exception("silent exception in freeze_layer")
        return layer
    for attr, getter in (("_geoms", "geoms"), ("_attrs", "attrs")):
        if getattr(layer, getter, None) is None:
            continue
        try:
            setattr(snap, attr, list(getattr(layer, getter)()))
        except Exception:
            _log.exception("silent exception in freeze_layer")
    return snap


class GgsMapLayer:

    def __init__(self, name="", source="", crs=None, layer_type=""):
        self._id = _next_layer_id()
        self._uuid = uuid.uuid4().hex[:8]
        self._name = name or self._name_from_source(source)
        self._source = str(source or "")
        self._crs = crs if isinstance(crs, GgsCrs) else GgsCrs.from_user_input(crs)
        self._layer_type = layer_type
        self._visible = True
        self._opacity = 1.0
        self._valid = True
        self._error = ""
        self._min_scale = 0.0
        self._max_scale = 0.0
        self._sub_layer = ""

    def sub_layer(self):
        return str(getattr(self, "_sub_layer", "") or "")

    def set_sub_layer(self, name):
        self._sub_layer = str(name or "")

    @staticmethod
    def _name_from_source(source):
        if not source:
            return "图层"
        base = os.path.basename(str(source).replace("\\", "/"))
        for sep in ("?", "|"):
            base = base.split(sep)[0]
        return os.path.splitext(base)[0] or base

    def id(self):
        return self._id

    def uuid(self):
        return self._uuid

    def name(self):
        return self._name

    def setName(self, name):
        self._name = str(name or "")

    def source(self):
        return self._source

    def layer_type(self):
        return self._layer_type

    def is_vector(self):
        return self._layer_type == LAYER_VECTOR

    def is_raster(self):
        return self._layer_type == LAYER_RASTER

    def is_tile(self):
        return self._layer_type == LAYER_TILE

    def is_table(self):
        return bool(getattr(self, "_is_table", False))

    def is_valid(self):
        return bool(self._valid)

    def error(self):
        return self._error

    def _fail(self, msg):
        self._valid = False
        self._error = str(msg)
        return self

    def crs(self):
        return self._crs

    def setCrs(self, crs):
        self._crs = crs if isinstance(crs, GgsCrs) else GgsCrs.from_user_input(crs)

    def is_visible(self):
        return bool(self._visible)

    def set_visible(self, on):
        self._visible = bool(on)

    def opacity(self):
        return float(self._opacity)

    def set_opacity(self, v):
        try:
            self._opacity = max(0.0, min(1.0, float(v)))
        except Exception:
            _log.exception("silent exception in set_opacity")

    def has_scale_based_visibility(self):
        return self._min_scale > 0 or self._max_scale > 0

    def scale_range(self):
        return (float(self._min_scale), float(self._max_scale))

    def set_scale_range(self, min_denom, max_denom):
        def _n(v):
            try:
                v = float(v)
            except Exception:
                _log.exception("silent exception in _n")
                return 0.0
            return max(0.0, v)
        a, b = _n(min_denom), _n(max_denom)
        if a and b and a > b:
            a, b = b, a
        self._min_scale = a
        self._max_scale = b

    def is_in_scale_range(self, scale_denom):
        return True

    def invalidate_extent(self):
        self._extent = None

    def setSource(self, source):
        self._source = str(source or "")

    def relink_source(self, source):
        self._source = str(source or "")
        bump_source_generation(self)

    def extent(self):
        return GgsRectangle()

    def type_label(self):
        return ""

    def feature_count(self):
        return 0

    def __repr__(self):
        return "<%s %s %r %s>" % (type(self).__name__, self._id,
                                  self._name,
                                  "ok" if self._valid else "INVALID")


class GgsVectorLayer(GgsMapLayer):

    def __init__(self, name="", source="", crs=None, geometry_type="",
                 geoms=None, attrs=None, fields=None, table=False):
        super().__init__(name, source, crs, LAYER_VECTOR)
        self._is_table = bool(table)
        self._geometry_type = str(geometry_type or "")
        self._kind_hint = ""
        self._geoms = list(geoms) if geoms is not None else []
        self._attrs = list(attrs) if attrs is not None else []
        self._feature_count = None
        self._geom_deferred = False
        self._geom_loaded = False
        self._viewport_cull = False
        self._loaded_extent = None
        self._fields = list(fields) if fields is not None else []
        self._extent = None
        self._index = None
        self._subset = None
        self._subset_expr = ""
        if not self._geometry_type and self._geoms:
            self._geometry_type = self._infer_geometry_type()

    def set_features(self, geoms, attrs=None):
        self._geoms = list(geoms or [])
        al = list(attrs) if attrs is not None else []
        if len(al) < len(self._geoms):
            al = al + [{} for _ in range(len(self._geoms) - len(al))]
        self._attrs = al[:len(self._geoms)]
        if not self._geometry_type and self._geoms:
            self._geometry_type = self._infer_geometry_type()
        self._extent = None
        self._index = None
        try:
            self._ggs_flat = None
        except Exception:
            _log.exception("silent exception in set_features")
        try:
            self._ggs_xy = None
        except Exception:
            _log.exception("silent exception in set_features")
        try:
            sidx = self.__dict__.get("_ggs_sidx")
            if sidx is not None and hasattr(sidx, "mark_dirty"):
                sidx.mark_dirty()
        except Exception:
            _log.exception("silent exception in set_features")

    def set_subset(self, fids, expression=""):
        if fids is None:
            self.clear_subset()
            return
        self._subset = set(int(f) for f in fids)
        self._subset_expr = str(expression or "")
        bump_subset_generation(self)

    def clear_subset(self):
        self._subset = None
        self._subset_expr = ""
        bump_subset_generation(self)

    def is_filtered(self):
        return self._subset is not None

    def subset_expression(self):
        return self._subset_expr

    def subset_fids(self):
        return self._subset

    def visible_count(self):
        if self._subset is None:
            return len(self._geoms)
        return len(self._subset & set(range(len(self._geoms))))

    def feature_visible(self, fid):
        if self._subset is None:
            return True
        try:
            return int(fid) in self._subset
        except Exception:
            _log.exception("silent exception in feature_visible")
            return True

    def filter_fids(self, fids):
        sub = self._subset
        if sub is None or fids is None:
            return fids
        try:
            import numpy as np
            if isinstance(fids, np.ndarray):
                if fids.size == 0:
                    return fids
                return fids[np.isin(fids, np.fromiter(sub, dtype=fids.dtype,
                                                      count=len(sub)))]
        except Exception:
            _log.exception("silent exception in filter_fids")
        return [int(f) for f in fids if int(f) in sub]

    def geometry_type(self):
        return self._geometry_type

    def base_kind(self):
        hint = getattr(self, "_kind_hint", "")
        if hint:
            return hint
        k = ""
        if self._geometry_type:
            k = base_kind(self._geometry_type)
        if not k:
            for g in (self._geoms or ())[:64]:
                try:
                    if g is None or bool(g.is_empty):
                        continue
                    k = base_kind(g)
                    if k and k != "collection":
                        break
                    k = ""
                except Exception:
                    _log.exception("silent exception in base_kind")
                    k = ""
        if k and k != "collection":
            self._kind_hint = k
        return k

    def geometry_type_display(self):
        n = normalize_geometry_type(self._geometry_type)
        if n:
            return n
        return self._infer_geometry_type()

    def _infer_geometry_type(self):
        for g in (self._geoms or ())[:64]:
            try:
                if g is None or bool(g.is_empty):
                    continue
                t = str(getattr(g, "geom_type", "") or "")
                if t and t != "GeometryCollection":
                    return t
            except Exception:
                _log.exception("silent exception in _infer_geometry_type")
        return ""

    def geoms(self):
        if getattr(self, "_viewport_cull", False):
            return self._geoms
        self._ensure_geom_loaded()
        return self._geoms

    def attrs(self):
        return self._attrs

    def fields(self):
        return self._fields

    def feature_count(self):
        if self._feature_count is not None:
            return self._feature_count
        if self.is_table():
            return len(self._attrs)
        return len(self._geoms)

    def feature(self, fid):
        self._ensure_geom_loaded()
        try:
            if self.is_table():
                return self._attrs[fid], None
            return self._attrs[fid], self._geoms[fid]
        except Exception:
            _log.exception("silent exception in feature")
            return None, None

    def features(self):
        self._ensure_geom_loaded()
        for i in range(len(self._geoms)):
            yield i, (self._attrs[i] if i < len(self._attrs) else {}), \
                self._geoms[i]

    def _ensure_geom_loaded(self):
        if not getattr(self, "_geom_deferred", False):
            return
        if getattr(self, "_geom_loaded", False):
            return
        self._geom_loaded = True
        try:
            self._load_geom_from_source()
        except Exception:
            _log.exception("silent exception in _ensure_geom_loaded")
            self._geom_loaded = False

    def _load_geom_from_source(self):
        from ggis.io.vector_io import _read_chunked, _from_wkb
        got = _read_chunked(self._source, None, None,
                           lambda *_a: None, on_chunk=None)
        if isinstance(got, str):
            return
        _meta, geometry, _fd = got
        if geometry is None or not hasattr(geometry, "shape") \
                or int(geometry.shape[0]) == 0:
            return
        self._geoms = list(_from_wkb(geometry))
        if self._feature_count is None:
            self._feature_count = len(self._geoms)
        self._geom_deferred = False

    def load_extent(self, extent):
        if not extent or len(extent) != 4:
            return False
        from ggis.io.vector_io import _read_extent_geoms
        try:
            geoms, attrs = _read_extent_geoms(self._source, tuple(extent),
                                              None)
        except Exception:
            _log.exception("silent exception in load_extent")
            return False
        if geoms is None:
            return False
        self._geoms = geoms
        self._attrs = attrs
        self._loaded_extent = tuple(extent)
        self._extent = None
        self.__dict__.pop("_ggs_flat", None)
        return True

    def query_bbox(self, xmin, ymin, xmax, ymax):
        from ggis.core.analysis.spatial import GgsSpatialIndex
        return GgsSpatialIndex.for_layer(self).query(
            xmin, ymin, xmax, ymax)

    def query_bbox_array(self, xmin, ymin, xmax, ymax):
        from ggis.core.analysis.spatial import GgsSpatialIndex
        return GgsSpatialIndex.for_layer(self).query_array(
            xmin, ymin, xmax, ymax)

    def set_data(self, geoms, attrs=None, fields=None, geometry_type=None):
        self._geoms = list(geoms)
        self._attrs = list(attrs) if attrs is not None else \
            [{} for _ in self._geoms]
        if fields is not None:
            self._fields = list(fields)
        self._extent = None
        if geometry_type is not None:
            self._geometry_type = str(geometry_type or "")
        elif self._geoms and not self._geometry_type:
            self._geometry_type = self._infer_geometry_type()
        self._kind_hint = ""
        try:
            if hasattr(self, "_ggs_sidx"):
                delattr(self, "_ggs_sidx")
        except Exception:
            _log.exception("silent exception in set_data")
        try:
            from ggis.render.cache import invalidate_caches
            invalidate_caches(self)
        except Exception:
            _log.exception("silent exception in set_data")
        bump_data_version(self)

    def extent(self):
        if self._extent is not None:
            return self._extent.copy()
        xs, ys = [], []
        for g in self._geoms:
            if g is None or getattr(g, "is_empty", True):
                continue
            try:
                b = g.bounds
            except Exception:
                _log.exception("silent exception in extent")
                continue
            xs.append(b[0])
            xs.append(b[2])
            ys.append(b[1])
            ys.append(b[3])
        r = GgsRectangle.from_points(xs, ys)
        if xs and ys:
            r.ensure_minimum(force=True)
        self._extent = r
        return r.copy()

    def set_extent_hint(self, rect):
        self._extent = None
        if rect is None:
            return
        try:
            xmin, ymin, xmax, ymax = (float(rect[0]), float(rect[1]),
                                      float(rect[2]), float(rect[3]))
        except Exception:
            _log.exception("silent exception in set_extent_hint")
            return
        import math
        if not all(math.isfinite(v) for v in (xmin, ymin, xmax, ymax)):
            return
        if xmax <= xmin and ymax <= ymin:
            return
        r = GgsRectangle(xmin, ymin, xmax, ymax)
        r.ensure_minimum(force=True)
        self._extent = r

    def type_label(self):
        if self.is_table():
            return i18n.tr("表格图层")
        from .geometry import _CN_NAMES
        return i18n.tr(_CN_NAMES.get(self.base_kind(),
                                     self._geometry_type or "矢量"))


class GgsRasterLayer(GgsMapLayer):

    def __init__(self, name="", source="", crs=None, dataset=None,
                 bands=None, width=0, height=0, dtype="", nodata=None,
                 transform=None, bounds=None, band_count=0):
        super().__init__(name, source, crs, LAYER_RASTER)
        self._ds = dataset
        self._bands = list(bands) if bands else [1]
        self._width = int(width)
        self._height = int(height)
        self._dtype = str(dtype or "")
        self._nodata = nodata
        self._transform = transform
        self._band_count = int(band_count) or len(self._bands)
        if bounds:
            self._bounds = GgsRectangle(bounds[0], bounds[1],
                                        bounds[2], bounds[3])
        else:
            self._bounds = GgsRectangle()

    def dataset(self):
        return self._ds

    def is_valid(self):
        return bool(self._valid and self._ds is not None)

    def band_count(self):
        return self._band_count

    def width(self):
        return self._width

    def height(self):
        return self._height

    def dtype(self):
        return self._dtype

    def nodata(self):
        return self._nodata

    def transform(self):
        return self._transform

    def resolution(self):
        t = self._transform
        if t is None:
            return (0.0, 0.0)
        try:
            return (abs(float(t.a)), abs(float(t.e)))
        except Exception:
            _log.exception("silent exception in resolution")
            return (0.0, 0.0)

    def extent(self):
        return self._bounds.copy()

    def overview_factors(self):
        if self._ds is None:
            return []
        out = set()
        try:
            n = self._band_count if self._band_count > 0 else 1
            for b in range(1, n + 1):
                for o in self._ds.overviews(b):
                    o = int(o)
                    if o > 1:
                        out.add(o)
        except Exception:
            _log.exception("silent exception in overview_factors")
            return []
        return sorted(out)

    def pick_overview(self, decimation):
        best = 1
        for f in self.overview_factors():
            if f <= decimation:
                best = f
        return best

    def read_window(self, extent, out_size, resample=0, bands=None):
        if self._ds is None or extent is None or extent.is_empty():
            return None, None
        ow, oh = int(out_size[0]), int(out_size[1])
        if ow <= 0 or oh <= 0:
            return None, None
        try:
            from rasterio.windows import from_bounds
            win = from_bounds(extent.xmin, extent.ymin,
                              extent.xmax, extent.ymax,
                              self._transform)
            rs = _rio_resampling(resample)
            if bands:
                sel = [int(b) for b in bands]
                n = max(1, int(self._band_count) or 1)
                sel = [b for b in sel if 1 <= b <= max(n, len(self._bands))]
                bands = sel or self._bands[:1]
            else:
                bands = self._bands[:3] if self._band_count >= 3 \
                    else self._bands
            arr = self._ds.read(bands, window=win,
                                out_shape=(len(bands), oh, ow),
                                resampling=rs,
                                boundless=True,
                                fill_value=self._nodata)
            if arr.shape[0] == 1:
                arr = arr[0]
            return arr, extent.copy()
        except Exception:
            _log.exception("silent exception in read_window")
            return None, None

    def read_window_reprojected(self, extent, out_size, dst_crs,
                                resample=0, bands=None, src=None,
                                src_extent=None):
        if extent is None or extent.is_empty():
            return None, None, None
        ow, oh = int(out_size[0]), int(out_size[1])
        if ow <= 0 or oh <= 0:
            return None, None, None
        from ggis.core.crs import crs_transformer, convert_bounds
        to_layer = crs_transformer(dst_crs, self._crs) \
            if dst_crs is not None else None
        if to_layer is None:
            if src is not None:
                a = src if src.ndim == 3 else src[None, ...]
                return (a[0] if a.shape[0] == 1 else a), None, (
                    src_extent.copy() if src_extent is not None else extent.copy())
            if self._ds is None:
                return None, None, None
            arr, ext = self.read_window(extent, out_size,
                                        resample=resample, bands=bands)
            return arr, None, ext
        if self._ds is None:
            return None, None, None
        try:
            from rasterio.transform import from_bounds as rio_from_bounds
            from rasterio.windows import (from_bounds as rio_window,
                                          transform as window_transform,
                                          Window as _Window)

            b = convert_bounds((extent.xmin, extent.ymin,
                                extent.xmax, extent.ymax), to_layer)
            if b is None:
                return None, None, None
            _full = GgsRectangle(b[0], b[1], b[2], b[3])
            win_ext = _full
            try:
                _le = self.extent()
            except Exception:
                _log.exception("silent exception in read_window_reprojected")
                _le = None
            if _le is not None and not _le.is_empty():
                _c = _full.intersect(_le)
                if _c is None or _c.is_empty():
                    return None, None, None
                win_ext = _c
            try:
                win = rio_window(win_ext.xmin, win_ext.ymin,
                                 win_ext.xmax, win_ext.ymax, self._transform)
            except Exception:
                _log.exception("silent exception in read_window_reprojected")
                _t = self._transform
                _col = (win_ext.xmin - _t.c) / _t.a
                _row = (win_ext.ymax - _t.f) / _t.e
                _w = abs((win_ext.xmax - win_ext.xmin) / _t.a)
                _h = abs((win_ext.ymax - win_ext.ymin) / _t.e)
                win = _Window(_col, _row, _w, _h)

            _fx = win_ext.width() / max(1e-12, _full.width())
            _fy = win_ext.height() / max(1e-12, _full.height())
            est_w = int(min(4096, max(1, round(ow * min(1.0, _fx)))))
            est_h = int(min(4096, max(1, round(oh * min(1.0, _fy)))))
            rs = _rio_resampling(resample)
            if bands:
                sel = [int(x) for x in bands]
                n = max(1, int(self._band_count) or 1)
                sel = [x for x in sel if 1 <= x <= max(n, len(self._bands))]
                bands_sel = sel[:3] if sel else self._bands[:1]
            else:
                bands_sel = self._bands[:3] if self._band_count >= 3 \
                    else self._bands
            if src is not None and src_extent is not None:
                a = np.asarray(src)
                if a.ndim == 2:
                    a = a[None, ...]
                if a.shape[0] == 1 and len(bands_sel) == 1:
                    pass
                elif a.shape[0] != len(bands_sel):
                    a = None
                if a is not None:
                    if a.shape[1] != est_h or a.shape[2] != est_w:
                        a = _resize_nearest(a, est_h, est_w)
                    src = a
                    src_t = rio_from_bounds(
                        src_extent.xmin, src_extent.ymin,
                        src_extent.xmax, src_extent.ymax, est_w, est_h)
                    return self._finish_reproject(
                        src, src_t, extent, dst_crs, bands_sel, ow, oh, rs)
            src = None
            try:
                _win_px = float(win.width) * float(win.height)
            except Exception:
                _log.exception("silent exception in read_window_reprojected")
                _win_px = 0.0
            if (win_ext.width() > 0 and win_ext.height() > 0
                    and _win_px >= _PYR_WINDOW_MIN_PX / _PYR_PROBE_DIV
                    and len(bands_sel) < 3):
                try:
                    from ggis.io import raster_pyramid as _pyr
                    _a, _ok = _pyr.read_overview(self.source(), win_ext,
                                                 (est_w, est_h),
                                                 bands=list(bands_sel),
                                                 max_upscale=16.0)
                    if _ok and _a is not None and getattr(_a, "size", 0):
                        src = _a if _a.ndim == 3 else _a[None, ...]
                except Exception:
                    _log.exception("silent exception in read_window_reprojected")
                    src = None
            if src is None:
                src = self._ds.read(bands_sel, window=win,
                                    out_shape=(len(bands_sel), est_h, est_w),
                                    resampling=rs,
                                    boundless=True,
                                    fill_value=self._nodata)
                src_t = window_transform(win, self._transform)
                try:
                    from rasterio import Affine as _Affine
                    sw_, sh_ = float(win.width) / est_w, float(win.height) / est_h
                    if sw_ > 0 and sh_ > 0:
                        src_t = src_t * _Affine.scale(sw_, sh_)
                except Exception:
                    _log.exception("silent exception in read_window_reprojected")
            else:
                from rasterio.transform import from_bounds as _rio_fb
                src_t = _rio_fb(win_ext.xmin, win_ext.ymin,
                                win_ext.xmax, win_ext.ymax, est_w, est_h)

            return self._finish_reproject(src, src_t, extent, dst_crs,
                                          bands_sel, ow, oh, rs)
        except Exception:
            _log.exception("silent exception in read_window_reprojected")
            import os as _os
            if _os.environ.get("GGIS_DEBUG_OTF"):
                import traceback as _tb
                _tb.print_exc()
            arr, ext = self.read_window(extent, out_size,
                                        resample=resample, bands=bands)
            return arr, None, ext

    def _finish_reproject(self, src, src_t, extent, dst_crs, bands_sel,
                          ow, oh, rs=0):
        from rasterio.warp import reproject
        from rasterio.crs import CRS as RioCRS
        from rasterio.transform import from_bounds as rio_from_bounds
        dst = np.zeros((len(bands_sel), oh, ow), dtype=src.dtype)
        src_rio = RioCRS.from_wkt(self._crs.to_pyproj().to_wkt())
        dst_rio = RioCRS.from_wkt(dst_crs.to_pyproj().to_wkt())
        dst_tf = rio_from_bounds(extent.xmin, extent.ymin,
                                 extent.xmax, extent.ymax, ow, oh)
        nd = self._nodata
        reproject(src, dst,
                  src_transform=src_t, src_crs=src_rio,
                  src_nodata=nd,
                  dst_transform=dst_tf, dst_crs=dst_rio,
                  dst_nodata=nd,
                  resampling=rs)
        est_h, est_w = src.shape[1], src.shape[2]
        ones = np.ones((est_h, est_w), dtype=np.uint8)
        valid_u8 = np.zeros((oh, ow), dtype=np.uint8)
        reproject(ones, valid_u8,
                  src_transform=src_t, src_crs=src_rio,
                  dst_transform=dst_tf, dst_crs=dst_rio,
                  resampling=rs,
                  dst_nodata=0)
        valid = valid_u8.astype(bool)
        if dst.shape[0] == 1:
            dst = dst[0]
        return dst, valid, extent.copy()

    def thumbnail(self, max_size=(256, 256)):
        if self._ds is None:
            return None
        try:
            from rasterio.enums import Resampling
            mw, mh = max_size
            ratio = min(mw / max(1, self._width), mh / max(1, self._height))
            oh = max(1, int(self._height * ratio))
            ow = max(1, int(self._width * ratio))
            bands = self._bands[:3] if self._band_count >= 3 else self._bands
            arr = self._ds.read(bands, out_shape=(len(bands), oh, ow),
                                resampling=Resampling.average)
            return arr[0] if arr.shape[0] == 1 else arr
        except Exception:
            _log.exception("silent exception in thumbnail")
            return None

    def type_label(self):
        return i18n.tr("影像" if self._band_count >= 3 else "栅格")

    def feature_count(self):
        return 0

    def close(self):
        try:
            if self._ds is not None:
                self._ds.close()
        except Exception:
            _log.exception("silent exception in close")
        self._ds = None

    def replace_dataset(self, other):
        if other is None or not other.is_raster():
            return False
        self.close()
        self._ds = other.dataset()
        self._bands = list(other._bands)
        self._width = int(other._width)
        self._height = int(other._height)
        self._dtype = str(other._dtype or "")
        self._nodata = other._nodata
        self._transform = other._transform
        self._band_count = int(other._band_count) or len(self._bands)
        try:
            self._bounds = other._bounds.copy()
        except Exception:
            _log.exception("silent exception in replace_dataset")
            self._bounds = GgsRectangle()
        self._crs = other._crs
        self._valid = True
        self._error = ""
        try:
            other._ds = None
        except Exception:
            _log.exception("silent exception in replace_dataset")
        try:
            from ggis.render.cache import invalidate_caches
            invalidate_caches(self)
        except Exception:
            _log.exception("silent exception in replace_dataset")
        bump_data_version(self)
        return True


class GgsTileLayer(GgsMapLayer):

    def __init__(self, name="", source_obj=None, crs=None):
        src = source_obj
        url = src.url if src is not None else ""
        super().__init__(name or (src.display_name() if src else ""),
                         url, crs or (src.crs if src else None), LAYER_TILE)
        self._tile_source = src
        self._extent = None

    def is_valid(self):
        return bool(self._valid and self._tile_source is not None
                    and self._tile_source.is_valid())

    def tile_source(self):
        return self._tile_source

    def set_tile_source(self, src):
        self._tile_source = src
        self._source = src.url if src is not None else ""
        self._extent = None

    def matrix(self):
        return self._tile_source.matrix() if self._tile_source else None

    def extent(self):
        if self._extent is not None:
            return self._extent.copy()
        m = self.matrix()
        self._extent = m.world() if m is not None else GgsRectangle()
        return self._extent.copy()

    def type_label(self):
        return i18n.tr("在线瓦片")

    def feature_count(self):
        return 0

    def attribution(self):
        return self._tile_source.attribution if self._tile_source else ""

    def __repr__(self):
        return "<GgsTileLayer %s %r %s>" % (
            self._id, self._name, "ok" if self.is_valid() else "INVALID")
