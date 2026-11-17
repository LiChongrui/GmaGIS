# -*- coding: utf-8 -*-


from .raster_io import is_raster_path, read_raster
from .vector_io import is_vector_path, _read_vector_sync
from .table_io import is_table_path, read_table, TABLE_SUFFIXES

__all__ = ["load_file", "is_supported", "supported_suffixes",
           "load_files"]


def supported_suffixes():
    from .raster_io import RASTER_SUFFIXES
    from .vector_io import VECTOR_SUFFIXES
    return sorted(RASTER_SUFFIXES | VECTOR_SUFFIXES | TABLE_SUFFIXES)


def is_supported(path):
    return (is_table_path(path) or is_vector_path(path)
            or is_raster_path(path))


def load_file(path, layer=None):
    p = str(path or "")
    if not p:
        return None
    if is_table_path(p):
        return read_table(p)
    if is_raster_path(p):
        return read_raster(p)
    if is_vector_path(p):
        return _read_vector_sync(p, layer=layer)
    return None


def load_files(paths):
    ok, bad = [], []
    for p in paths or []:
        lyr = load_file(p)
        if lyr is None:
            bad.append((str(p), "不支持的文件类型"))
        elif not lyr.is_valid():
            bad.append((str(p), lyr.error()))
        else:
            ok.append(lyr)
    return ok, bad
