# -*- coding: utf-8 -*-

import os

import numpy as np
import logging

_log = logging.getLogger("gmagis")

try:
    from pyogrio.raw import read as _ogr_read
    from pyogrio.raw import write as _ogr_write
    import pyogrio as _pyogrio
    _HAS_PYOGRIO = True
except Exception:
    _log.exception("silent exception")
    _HAS_PYOGRIO = False

try:
    from shapely import from_wkb as _from_wkb
    from shapely import to_wkb as _to_wkb
    _HAS_SHAPELY = True
except Exception:
    _log.exception("silent exception")
    _HAS_SHAPELY = False

from ..core.crs import GgsCoordinateReferenceSystem as GgsCrs
from ggis.core.model.layer import GgsVectorLayer

from ..exec import guard as _guard

__all__ = ["read_vector", "list_vector_layers", "write_vector",
           "create_vector", "write_layer", "write_layer_atomic",
           "driver_for_path", "is_vector_path", "VECTOR_SUFFIXES",
           "OGR_GEOMETRY_TYPES", "export_layer", "reproject_geoms"]

VECTOR_SUFFIXES = {
    ".shp", ".geojson", ".json", ".gpkg", ".kml", ".kmz", ".gml",
    ".dxf", ".csv", ".gpx", ".fgb", ".mif", ".tab", ".dgn",
    ".gdb", ".osm", ".pbf", ".vrt",
}

_CONTAINER_SUFFIXES = {".gpkg", ".kml", ".kmz", ".gdb", ".gml", ".sqlite"}

_CHUNK = 4000
_OGR_CHUNK = 2000


def is_vector_path(path):
    return os.path.splitext(str(path or ""))[1].lower() in VECTOR_SUFFIXES


def list_vector_layers(path):
    if not _HAS_PYOGRIO:
        return []
    try:
        return [(str(n), str(g)) for n, g in _pyogrio.list_layers(str(path))]
    except Exception:
        _log.exception("silent exception in list_vector_layers")
        return []


def _decode_cell(v, encoding):
    if isinstance(v, bytes):
        for enc in (encoding, "utf-8", "gbk", "latin-1"):
            if not enc:
                continue
            try:
                return v.decode(enc)
            except Exception:
                _log.exception("silent exception in _decode_cell")
                continue
        return v.decode("utf-8", errors="replace")
    return v


def _build_attrs(n, cols, field_names, encoding, yield_hook=None):
    if n == 0 or not cols:
        return [dict() for _ in range(n)]

    def _tovalues(arr, m):
        if arr.dtype != object:
            vals = arr[:m].tolist()
        else:
            sample = arr[:m]
            has_bytes = True
            try:
                frompyfunc = getattr(np, "frompyfunc", None)
                if frompyfunc is not None:
                    has_bytes = bool(
                        frompyfunc(lambda v: isinstance(v, bytes), 1, 1)(
                            sample).any())
            except Exception:
                _log.exception("silent exception in _tovalues")
                has_bytes = True
            vals = ([_decode_cell(v, encoding) for v in sample]
                    if has_bytes else sample.tolist())
        if len(vals) < n:
            vals = vals + [None] * (n - len(vals))
        return vals

    cols_out = []
    names = []
    for ci, col in enumerate(cols):
        cname = field_names[ci] if ci < len(field_names) else "col%d" % ci
        try:
            arr = np.asarray(col)
        except Exception:
            _log.exception("silent exception in _build_attrs")
            continue
        if arr.ndim != 1:
            continue
        m = min(n, int(arr.shape[0]))
        if m <= 0:
            continue
        try:
            cols_out.append(_tovalues(arr, m))
        except Exception:
            _log.exception("silent exception in _build_attrs")
            continue
        names.append(cname)

    if not cols_out:
        return [dict() for _ in range(n)]

    out = []
    rows = zip(*cols_out)
    chunk = 4096
    buf = []
    for row in rows:
        buf.append(dict(zip(names, row)))
        if len(buf) >= chunk:
            out.extend(buf)
            buf = []
            if yield_hook is not None:
                try:
                    yield_hook()
                except Exception:
                    _log.exception("silent exception in _build_attrs")
    out.extend(buf)
    return out


_EXTENT_HINT_MIN_BYTES = 2 << 20


def _read_chunked(src, layer, max_features, tick, on_chunk=None):
    limit = None if max_features is None else int(max_features)

    geoms_parts = []
    cols_parts = []
    meta = None
    skip = 0
    while True:
        take = _OGR_CHUNK
        if limit is not None:
            if skip >= limit:
                break
            take = min(take, limit - skip)
        try:
            _m, _i, g, fd = _ogr_read(src, layer=layer,
                                      skip_features=skip, max_features=take)
        except Exception:
            _log.exception("silent exception in _read_chunked")
            if skip == 0:
                meta = None
                break
            break
        if _m is not None and meta is None:
            meta = _m
        if g is None or len(g) == 0:
            break
        geoms_parts.append(g)
        if fd:
            cols_parts.append(list(fd))
        skip += take
        tick("read", skip, limit or 0)
        if on_chunk is not None:
            try:
                on_chunk(meta, g, fd)
            except Exception:
                _log.exception("silent exception in _read_chunked")
        if len(g) < take:
            break

    if geoms_parts:
        return meta, _join_parts(geoms_parts), _join_columns(cols_parts)

    try:
        meta, index, _g, _fd = _ogr_read(
            src, layer=layer, read_geometry=False, return_fids=True)
    except Exception as e:
        _log.exception("silent exception in _read_chunked")
        return "%s: %s" % (type(e).__name__, e)
    try:
        allf = np.asarray(index, dtype=np.int64)
    except Exception:
        _log.exception("silent exception in _read_chunked")
        allf = np.asarray([], dtype=np.int64)
    if allf.size == 0:
        try:
            meta, _i, geometry, field_data = _ogr_read(
                src, layer=layer, max_features=max_features)
        except Exception as e:
            _log.exception("silent exception in _read_chunked")
            return "%s: %s" % (type(e).__name__, e)
        tick("read", 0, 0)
        return meta, geometry, field_data

    if limit is not None:
        allf = allf[:limit]
    total = int(allf.size)
    for a in range(0, total, _OGR_CHUNK):
        block = allf[a:a + _OGR_CHUNK]
        try:
            _m, _i, g, fd = _ogr_read(src, layer=layer, fids=block)
        except Exception as e:
            _log.exception("silent exception in _read_chunked")
            return "%s: %s" % (type(e).__name__, e)
        if g is not None:
            geoms_parts.append(g)
        if fd:
            cols_parts.append(list(fd))
        tick("read", min(a + _OGR_CHUNK, total), total)

    geometry = _join_parts(geoms_parts)
    return meta, geometry, _join_columns(cols_parts)


def _join_parts(parts):
    if not parts:
        return np.asarray([], dtype=object)
    try:
        return np.concatenate(parts)
    except Exception:
        _log.exception("silent exception in _join_parts")
        out = np.empty(sum(len(p) for p in parts), dtype=object)
        i = 0
        for p in parts:
            out[i:i + len(p)] = p
            i += len(p)
        return out


def _join_columns(cols_parts):
    if not cols_parts:
        return []
    ncol = min(len(c) for c in cols_parts)
    out = []
    for ci in range(ncol):
        try:
            out.append(np.concatenate([np.asarray(c[ci]) for c in cols_parts]))
        except Exception:
            _log.exception("silent exception in _join_columns")
            out.append(np.asarray([v for c in cols_parts for v in c[ci]],
                                  dtype=object))
    return out


@_guard.off_ui("io.vector_io.read_vector")
def _read_vector_sync(path, layer=None, max_features=None, on_progress=None,
                      on_partial=None, defer_geometry=False,
                      viewport_cull=False):
    src = str(path or "")
    name = os.path.splitext(os.path.basename(src))[0] or src
    if not _HAS_PYOGRIO:
        return GgsVectorLayer(name, src)._fail("缺少 pyogrio")
    if not _HAS_SHAPELY:
        return GgsVectorLayer(name, src)._fail("缺少 shapely")
    if not os.path.exists(src):
        return GgsVectorLayer(name, src)._fail("文件不存在：%s" % src)

    def _tick(phase, done=0, total=0):
        if on_progress is None:
            return
        try:
            on_progress(phase, done, total)
        except Exception:
            _log.exception("silent exception in _tick")

    def _apply_extent_hint(l):
        if max_features is not None:
            return
        try:
            _big = os.path.getsize(src) > _EXTENT_HINT_MIN_BYTES
        except Exception:
            _log.exception("silent exception in _apply_extent_hint")
            _big = False
        if not _big:
            return
        try:
            _tb = _pyogrio.read_info(src, layer=layer).get("total_bounds")
        except Exception:
            _log.exception("silent exception in _apply_extent_hint")
            _tb = None
        if _tb is not None:
            l.set_extent_hint(_tb)

    if (defer_geometry or viewport_cull) and is_vector_path(src):
        try:
            _meta, _index, _g0, _fd0 = _ogr_read(
                src, layer=layer, read_geometry=False, return_fids=True)
        except Exception as exc:
            _log.exception("silent exception in _read_vector_sync")
            return GgsVectorLayer(name, src)._fail(
                "%s: %s" % (type(exc).__name__, exc))
        _n = int(len(_index)) if _index is not None else 0
        _enc = (_meta or {}).get("encoding") or "utf-8"
        _fm = list(_meta.get("fields")) if _meta.get("fields") is not None else []
        _ot = list(_meta.get("ogr_types")) if _meta.get("ogr_types") is not None else []
        _flds = [(str(f), _ot[i] if i < len(_ot) else "")
                 for i, f in enumerate(_fm)]
        _crs = (_meta or {}).get("crs") or ""
        _crs = GgsCrs.from_user_input(_crs) if _crs else GgsCrs()
        _gt = str((_meta or {}).get("geometry_type") or "")
        _lyr = GgsVectorLayer(
            name, src, _crs, _gt, [],
            _build_attrs(_n, list(_fd0) if _fd0 else [], _fm, _enc), _flds)
        if os.path.splitext(src)[1].lower() in _CONTAINER_SUFFIXES:
            try:
                _lyr.set_sub_layer(str(layer or "") or name)
            except Exception:
                _log.exception("silent exception in _read_vector_sync")
        if _n > 0:
            _apply_extent_hint(_lyr)
            _lyr._feature_count = _n
            if viewport_cull:
                _lyr._viewport_cull = True
            else:
                _lyr._geom_deferred = True
        return _lyr

    _prog = {"lyr": None, "g": [], "a": [], "fields": None, "enc": "utf-8"}

    def _pc(meta_c, g, fd_c):
        if on_partial is None or g is None or len(g) == 0:
            return
        try:
            gl = list(_from_wkb(g))
        except Exception:
            _log.exception("silent exception in _pc")
            return
        if not gl:
            return
        st = _prog
        first = st["lyr"] is None
        if first:
            enc = (meta_c or {}).get("encoding") or "utf-8"
            _f = (meta_c or {}).get("fields")
            fields_meta = list(_f) if _f is not None else []
            _t = (meta_c or {}).get("ogr_types")
            ogr_types = list(_t) if _t is not None else []
            flds = [(str(f), ogr_types[i] if i < len(ogr_types) else "")
                    for i, f in enumerate(fields_meta)]
            crs_text = (meta_c or {}).get("crs") or ""
            crs_c = GgsCrs.from_user_input(crs_text) if crs_text else GgsCrs()
            gt_c = str((meta_c or {}).get("geometry_type") or "")
            nm = name
            if layer is not None or os.path.splitext(src)[1].lower() \
                    in _CONTAINER_SUFFIXES:
                try:
                    info = _pyogrio.read_info(src, layer=layer)
                    ln = str(info.get("layer_name") or "")
                    if ln and ln.lower() != nm.lower():
                        nm = ln
                    gt_c = str(info.get("geometry_type") or gt_c)
                except Exception:
                    _log.exception("silent exception in _pc")
            if not gt_c:
                gt_c = gl[0].geom_type
            attrs_c = _build_attrs(len(gl), list(fd_c) if fd_c else [],
                                   fields_meta, enc)
            st["g"].extend(gl)
            st["a"].extend(attrs_c)
            st["lyr"] = GgsVectorLayer(nm, src, crs_c, gt_c,
                                       gl, attrs_c, flds)
            if os.path.splitext(src)[1].lower() in _CONTAINER_SUFFIXES:
                try:
                    st["lyr"].set_sub_layer(str(layer or "") or nm)
                except Exception:
                    _log.exception("silent exception in _pc")
            st["fields"] = fields_meta
            st["enc"] = enc
        else:
            l2 = st["lyr"]
            attrs_c = _build_attrs(len(gl), list(fd_c) if fd_c else [],
                                   st["fields"], st["enc"])
            st["g"].extend(gl)
            st["a"].extend(attrs_c)
            l2.set_features(st["g"], st["a"])
        try:
            on_partial(st["lyr"], first)
        except Exception:
            _log.exception("silent exception in _pc")

    if on_progress is None:
        try:
            meta, _index, geometry, field_data = _ogr_read(
                src, layer=layer, max_features=max_features)
        except Exception as e:
            _log.exception("silent exception in _read_vector_sync")
            return GgsVectorLayer(name, src)._fail("%s: %s"
                                                   % (type(e).__name__, e))
    else:
        got = _read_chunked(src, layer, max_features, _tick,
                            on_chunk=(_pc if on_partial is not None else None))
        if isinstance(got, str):
            return GgsVectorLayer(name, src)._fail(got)
        meta, geometry, field_data = got
        if _prog["lyr"] is not None:
            _apply_extent_hint(_prog["lyr"])
            return _prog["lyr"]
    _tick("read", 0, 0)

    geoms = []
    if geometry is not None:
        try:
            total = int(geometry.shape[0]) if hasattr(geometry, "shape") else 0
            if on_progress is not None and total > _CHUNK:
                parts = []
                for a in range(0, total, _CHUNK):
                    b = min(a + _CHUNK, total)
                    parts.append(list(_from_wkb(geometry[a:b])))
                    _tick("geometry", b, total)
                geoms = [g for part in parts for g in part]
            else:
                geoms = list(_from_wkb(geometry))
        except Exception:
            _log.exception("silent exception in _read_vector_sync")
            try:
                geoms = [_from_wkb(b) for b in geometry]
            except Exception:
                _log.exception("silent exception in _read_vector_sync")
                geoms = []
    n = len(geoms)
    _tick("geometry", n, n)

    enc = (meta or {}).get("encoding") or "utf-8"
    _f = (meta or {}).get("fields")
    fields_meta = list(_f) if _f is not None else []
    _t = (meta or {}).get("ogr_types")
    ogr_types = list(_t) if _t is not None else []
    fields = [(str(f), ogr_types[i] if i < len(ogr_types) else "")
              for i, f in enumerate(fields_meta)]

    attrs = _build_attrs(n, list(field_data) if field_data else [],
                         fields_meta, enc,
                         yield_hook=(lambda: _tick("attributes", 0, 0))
                         if on_progress is not None else None)
    _tick("attributes", n, n)

    crs_text = (meta or {}).get("crs") or ""
    crs = GgsCrs.from_user_input(crs_text) if crs_text else GgsCrs()

    ext = os.path.splitext(src)[1].lower()
    gtype = str((meta or {}).get("geometry_type") or "")
    if layer is not None or ext in _CONTAINER_SUFFIXES:
        try:
            info = _pyogrio.read_info(src, layer=layer)
            lname = str(info.get("layer_name") or "")
            if lname and lname.lower() != name.lower():
                name = lname
            gtype = str(info.get("geometry_type") or gtype)
        except Exception:
            _log.exception("silent exception in _read_vector_sync")

    if not gtype and geoms:
        gtype = geoms[0].geom_type

    lyr = GgsVectorLayer(name, src, crs, gtype, geoms, attrs, fields)
    if os.path.splitext(src)[1].lower() in _CONTAINER_SUFFIXES:
        try:
            lyr.set_sub_layer(str(layer or "") or name)
        except Exception:
            _log.exception("silent exception in _read_vector_sync")
    if n == 0:
        lyr._valid = True
        lyr._error = "数据源没有要素"
    if n > 0:
        _apply_extent_hint(lyr)
    return lyr


def _read_extent_geoms(src, extent, layer=None):
    if not _HAS_PYOGRIO or not _HAS_SHAPELY:
        return None, None
    if not extent or len(extent) != 4:
        return None, None
    try:
        _m, _i, g, fd = _ogr_read(src, layer=layer,
                                  bbox=tuple(extent), return_fids=True)
    except Exception:
        _log.exception("silent exception in _read_extent_geoms")
        return None, None
    if g is None or len(g) == 0:
        return [], []
    try:
        geoms = list(_from_wkb(g))
    except Exception:
        _log.exception("silent exception in _read_extent_geoms")
        return None, None
    if not geoms:
        return [], []
    enc = (_m or {}).get("encoding") or "utf-8"
    _flds_raw = (_m or {}).get("fields")
    flds = list(_flds_raw) if _flds_raw is not None else []
    attrs = _build_attrs(len(geoms), list(fd) if fd else [], flds, enc)
    return geoms, attrs


@_guard.offloaded("io.vector_io.read_vector", kind="io", name="读取矢量")
def read_vector(path, layer=None, max_features=None, on_progress=None,
                defer_geometry=False, viewport_cull=False):
    return _read_vector_sync(path, layer=layer, max_features=max_features,
                             on_progress=on_progress,
                             defer_geometry=defer_geometry,
                             viewport_cull=viewport_cull)


@_guard.off_ui("io.vector_io.write_vector")
def _write_geometry_type(gtype):
    s = str(gtype or "").strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("measured "):
        s = s[len("measured "):]
        low = s.lower()
    if low.startswith("3d ") or low.startswith("2.5d "):
        s = s.split(" ", 1)[1] + " Z"
        low = s.lower()
    if s.endswith(" ZM") or s.endswith(" zm"):
        s = s[:-1]
    elif s.endswith(" M") or s.endswith(" m"):
        s = s[:-2]
    return s


def _write_vector_sync(path, geoms, attrs=None, fields=None, crs="EPSG:4326",
                       geometry_type=None, driver=None, encoding="UTF-8",
                       layer=None, creation_options=None):
    if not _HAS_PYOGRIO:
        raise RuntimeError("缺少 pyogrio")
    geoms = list(geoms or [])
    if not geoms:
        raise ValueError("没有几何可写")
    gtype = _write_geometry_type(geometry_type or geoms[0].geom_type)
    wkb = _to_wkb(np.array(geoms, dtype=object))

    if crs is not None and not isinstance(crs, str):
        authid = ""
        try:
            authid = crs.authid()
        except Exception:
            _log.exception("silent exception in _write_vector_sync")
            authid = ""
        crs = authid or str(crs)

    attrs = list(attrs or [])
    names = []
    if fields:
        for f in fields:
            if isinstance(f, (tuple, list)):
                if f:
                    names.append(str(f[0]))
            else:
                names.append(str(f))
    if not names and attrs and isinstance(attrs[0], dict):
        names = list(attrs[0].keys())
    field_data = []
    for name in names:
        col = []
        for i in range(len(geoms)):
            v = attrs[i].get(name) if i < len(attrs) and \
                isinstance(attrs[i], dict) else None
            col.append(v)
        try:
            field_data.append(np.array(col))
        except Exception:
            _log.exception("silent exception in _write_vector_sync")
            field_data.append(np.array(col, dtype=object))

    kwargs = dict(field_data=field_data or None,
                  fields=np.array(names) if names else None,
                  geometry_type=gtype, crs=crs, driver=driver,
                  encoding=encoding)
    if layer and (driver or "").upper() in ("GPKG", "GML", "KML", "SQLITE"):
        kwargs["layer"] = str(layer)
    _apply_creation_options(kwargs, creation_options)
    _ogr_write(str(path), wkb, **kwargs)
    return str(path)


@_guard.offloaded("io.vector_io.write_vector", kind="io", name="写矢量")
def write_vector(path, geoms, attrs=None, fields=None, crs="EPSG:4326",
                 geometry_type=None, driver=None, encoding="UTF-8",
                 layer=None, creation_options=None):
    return _write_vector_sync(path, geoms, attrs=attrs, fields=fields,
                              crs=crs, geometry_type=geometry_type,
                              driver=driver, encoding=encoding, layer=layer,
                              creation_options=creation_options)


def _apply_creation_options(kwargs, creation_options):
    co = creation_options or {}
    if not any(k in co for k in ("dataset", "layer", "encoding")):
        co = {"dataset": co}
    ds = {str(k).lower(): str(v) for k, v in (co.get("dataset") or {}).items()
          if v not in (None, "")}
    ly = {str(k).lower(): str(v) for k, v in (co.get("layer") or {}).items()
          if v not in (None, "")}
    enc = str(co.get("encoding") or "")
    if ds:
        kwargs["dataset_options"] = ds
    if ly:
        kwargs["layer_options"] = ly
    if enc:
        kwargs["encoding"] = enc


from .formats import VECTOR_WRITE_FORMATS as _VECTOR_WRITE_ROWS

_DRIVER_BY_SUFFIX = {suffix: driver
                     for suffix, driver, _n, _f in _VECTOR_WRITE_ROWS}
_DRIVER_BY_SUFFIX.update({".json": "GeoJSON", ".vrt": "VRT",
                          ".gpx": "GPX"})

_SHAPEFILE_SIDECARS = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix",
                       ".shp.xml", ".sbn", ".sbx", ".idm", ".ind")


def driver_for_path(path):
    return _DRIVER_BY_SUFFIX.get(os.path.splitext(str(path))[1].lower())


OGR_GEOMETRY_TYPES = ("Point", "LineString", "Polygon",
                      "MultiPoint", "MultiLineString", "MultiPolygon")


def create_vector(path, geometry_type="Point", crs="EPSG:4326",
                  driver=None, layer=None, fields=None):
    if not _HAS_PYOGRIO:
        raise RuntimeError("缺少 pyogrio")
    target = str(path or "")
    if not target:
        raise ValueError("没有指定文件路径")
    gtype = str(geometry_type or "Point")
    if gtype not in OGR_GEOMETRY_TYPES:
        raise ValueError("不支持的几何类型：%s" % gtype)

    ext = os.path.splitext(target)[1].lower()
    drv = driver or driver_for_path(target)
    if not drv:
        raise ValueError("不知道 %s 该用什么驱动" % (ext or "该后缀"))

    crs_text = ""
    if crs is not None:
        try:
            crs_text = crs.authid() if not isinstance(crs, str) else crs
        except Exception:
            _log.exception("silent exception in create_vector")
            crs_text = str(crs)

    names = [str(f[0]) for f in (fields or [])]
    types = [str(f[1]) if len(f) > 1 else "str" for f in (fields or [])]

    parent = os.path.dirname(os.path.abspath(target))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    _ogr_write(target, geometry=np.array([], dtype=object),
               field_data=[np.array([], dtype=object) for _ in names],
               fields=names, layer=layer or os.path.splitext(
                   os.path.basename(target))[0],
               driver=drv, geometry_type=gtype,
               crs=crs_text or None,
               field_types=types if names else None)
    return target


def write_layer(layer, path=None, driver=None):
    target = str(path or layer.source() or "")
    if not target:
        raise ValueError("图层没有数据源路径")
    fields = [str(f[0]) for f in (layer.fields() or [])]
    return _write_vector_sync(target, layer.geoms(), layer.attrs(),
                        fields=fields or None,
                        crs=(layer.crs().authid()
                             if layer.crs() is not None else "EPSG:4326"),
                        geometry_type=layer.geometry_type() or None,
                        driver=driver or driver_for_path(target),
                        layer=layer.name())


def write_layer_atomic(layer, path=None):
    import tempfile
    import shutil

    target = str(path or layer.source() or "")
    if not target:
        raise ValueError("图层没有数据源路径")
    suffix = os.path.splitext(target)[1].lower()

    if suffix == ".shp":
        base_dir = os.path.dirname(os.path.abspath(target)) or "."
        stem = os.path.splitext(os.path.basename(target))[0]
        tmp_dir = tempfile.mkdtemp(prefix=".gmagis_edit_", dir=base_dir)
        try:
            tmp_path = os.path.join(tmp_dir, stem + ".shp")
            write_layer(layer, tmp_path, driver="ESRI Shapefile")
            written = set()
            for ext in _SHAPEFILE_SIDECARS:
                src = os.path.join(tmp_dir, stem + ext)
                if os.path.isfile(src):
                    shutil.copyfile(src, os.path.join(base_dir, stem + ext))
                    written.add(ext)
            if ".shp" not in written:
                raise IOError("Shapefile 写入失败：没有生成 .shp")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return target

    d = os.path.dirname(os.path.abspath(target)) or "."
    tmp = os.path.join(d, "gmagis_edit_%d%s" % (os.getpid(), suffix))
    n = 0
    while os.path.exists(tmp):
        n += 1
        tmp = os.path.join(d, "gmagis_edit_%d_%d%s" % (os.getpid(), n,
                                                       suffix))
    try:
        write_layer(layer, tmp, driver=driver_for_path(target))
        os.replace(tmp, target)
    except Exception:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except Exception:
            _log.exception("silent exception in write_layer_atomic")
        raise
    return target


def reproject_geoms(geoms, src_crs, dst_crs):
    from pyproj import Transformer
    from shapely.ops import transform as _shp_transform

    src = str(src_crs or "").strip() or "EPSG:4326"
    dst = str(dst_crs or "").strip() or "EPSG:4326"
    t = Transformer.from_crs(src, dst, always_xy=True)

    def _f(x, y, z=None):
        return t.transform(x, y)

    out = []
    for g in geoms:
        if g is None or getattr(g, "is_empty", True):
            out.append(g)
            continue
        try:
            out.append(_shp_transform(_f, g))
        except Exception:
            _log.exception("silent exception in reproject_geoms")
            out.append(g)
    return out


class _ExportCancelled(Exception):
    pass


@_guard.offloaded("io.vector_io.export_layer", kind="io", name="导出矢量")
def export_layer(layer, path, driver=None, fields=None, fid_filter=None,
                 target_crs="", src_crs=None, progress=None, cancel=None):
    def _report(frac, text):
        if cancel is not None:
            try:
                if cancel():
                    raise _ExportCancelled()
            except _ExportCancelled:
                raise
            except Exception:
                _log.exception("silent exception in _report")
        if progress is not None:
            try:
                progress(float(frac), str(text))
            except Exception:
                _log.exception("silent exception in _report")

    _report(0.0, "正在读取要素…")
    all_geoms = list(layer.geoms() or [])
    all_attrs = list(layer.attrs() or [])
    n = len(all_geoms)

    fids = set(range(n))
    sub = None
    try:
        sub = layer.subset_fids()
    except Exception:
        _log.exception("silent exception in export_layer")
        sub = None
    if sub is not None:
        fids &= set(int(f) for f in sub)
    if fid_filter is not None:
        fids &= set(int(f) for f in fid_filter)
    keep = sorted(fids)
    if not keep:
        raise ValueError("没有要素可导出")

    _report(0.15, "正在筛选要素…")
    geoms = [all_geoms[i] for i in keep]
    attrs = [all_attrs[i] if i < len(all_attrs) else {} for i in keep]

    names = None
    if fields is not None:
        names = [str(f) for f in fields]
        if not names:
            attrs = [{} for _ in keep]
    elif layer.fields():
        names = []
        for f in layer.fields():
            names.append(str(f[0]) if isinstance(f, (tuple, list))
                         else str(f))

    src = src_crs
    if src is None:
        try:
            src = layer.crs().authid() if layer.crs() is not None else ""
        except Exception:
            _log.exception("silent exception in export_layer")
            src = ""
    crs_out = src or "EPSG:4326"
    if target_crs and str(target_crs).strip():
        dst = str(target_crs).strip()
        if dst.upper() != str(src or "").upper():
            _report(0.30, "正在重投影…")
            geoms = reproject_geoms(geoms, src or "EPSG:4326", dst)
            crs_out = dst
            _report(0.65, "重投影完成")

    if names is not None:
        _report(0.70, "正在整理属性…")
        attrs = [{k: (a.get(k) if isinstance(a, dict) else None)
                  for k in names} for a in attrs]

    _report(0.85, "正在写入文件…")
    out = _write_vector_sync(
        str(path), geoms, attrs=attrs, fields=names,
        crs=crs_out, geometry_type=layer.geometry_type() or None,
        driver=driver or driver_for_path(path),
        layer=str(layer.name() or ""))
    _report(1.0, "导出完成")
    return out
