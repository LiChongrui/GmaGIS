# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math

from ggis.exec import guard as _guard
import logging
_log = logging.getLogger("gmagis")


__all__ = [
    "FieldStats", "field_stats", "collect_values", "histogram",
    "bins_freedman_diaconis", "bins_sturges", "raster_band_values",
    "raster_band_stats", "stacked_raster_values",
]


def _as_list(values):
    if values is None:
        return []
    if isinstance(values, (list, tuple)):
        return list(values)
    try:
        return [v for v in values]
    except TypeError:
        exc_note("_as_list @ ggis/core/analysis/stats.py:64")
        return []


@_guard.off_ui("core.stats.collect_values")
def collect_values(layer, field):

    values, skipped = [], 0
    if layer is None or not field:
        return values, skipped
    for _fid, attrs, _g in layer.features():
        v = attrs.get(field) if isinstance(attrs, dict) else None
        if v is None or v == "":
            skipped += 1
            continue
        if isinstance(v, bool):
            skipped += 1
            continue
        if isinstance(v, (int, float)):
            fv = float(v)
            if fv != fv:
                skipped += 1
                continue
            values.append(fv)
            continue
        s = str(v).strip()
        try:
            fv = float(s)
        except Exception:
            _log.exception("silent exception in collect_values")
            skipped += 1
            continue
        if fv != fv:
            skipped += 1
            continue
        values.append(fv)
    return values, skipped


class FieldStats:

    __slots__ = ("count", "minimum", "maximum", "mean", "std", "median",
                 "total", "skipped", "field", "unique")

    def __init__(self, values=None, skipped=0, field=""):
        self.field = str(field or "")
        self.skipped = int(skipped)
        self.count = 0
        self.minimum = self.maximum = 0.0
        self.mean = self.std = self.median = self.total = 0.0
        self.unique = 0
        vals = []
        for v in _as_list(values):
            try:
                f = float(v)
            except Exception:
                _log.exception("silent exception in __init__")
                continue
            if f == f and abs(f) != float("inf"):
                vals.append(f)
        self.count = len(vals)
        if not vals:
            return
        import numpy as np

        a = np.asarray(vals, dtype="float64")
        self.minimum = float(a.min())
        self.maximum = float(a.max())
        self.mean = float(a.mean())
        self.std = float(a.std())
        self.median = float(np.median(a))
        self.total = float(a.sum())
        try:
            self.unique = int(np.unique(a).size)
        except Exception:
            _log.exception("silent exception in __init__")
            self.unique = 0

    def as_dict(self):
        return {
            "field": self.field, "count": self.count,
            "min": self.minimum, "max": self.maximum, "mean": self.mean,
            "std": self.std, "median": self.median, "total": self.total,
            "unique": self.unique, "skipped": self.skipped,
        }


@_guard.off_ui("core.stats.field_stats")
def field_stats(layer, field):
    values, skipped = collect_values(layer, field)
    return FieldStats(values, skipped, field)


def bins_sturges(n):
    n = int(n or 0)
    if n <= 1:
        return 1
    return max(1, int(math.ceil(math.log2(n))) + 1)


def bins_freedman_diaconis(values, lo=None, hi=None,
                           lo_bound=5, hi_bound=60):
    import numpy as np

    a = np.asarray(_as_list(values), dtype="float64")
    n = int(a.size)
    if n <= 1:
        return 1
    try:
        q1, q3 = np.percentile(a, [25.0, 75.0])
        iqr = float(q3 - q1)
    except Exception:
        _log.exception("silent exception in bins_freedman_diaconis")
        iqr = 0.0
    if not (iqr > 0):
        return max(lo_bound, min(hi_bound, bins_sturges(n)))
    width = 2.0 * iqr / (n ** (1.0 / 3.0))
    if not (width > 0):
        return max(lo_bound, min(hi_bound, bins_sturges(n)))
    lo = float(a.min()) if lo is None else float(lo)
    hi = float(a.max()) if hi is None else float(hi)
    span = hi - lo
    if not (span > 0):
        return 1
    k = int(math.ceil(span / width))
    k = min(k, max(lo_bound, int(math.ceil(2.0 * math.sqrt(n)))))
    return max(lo_bound, min(hi_bound, max(1, k)))


def histogram(values, bins=None, lo=None, hi=None):
    import numpy as np

    a = np.asarray(_as_list(values), dtype="float64")
    a = a[np.isfinite(a)]
    if a.size == 0:
        return [], []
    lo = float(a.min()) if lo is None else float(lo)
    hi = float(a.max()) if hi is None else float(hi)
    if not (hi > lo):
        eps = abs(lo) * 1e-6 or 1e-6
        lo, hi = lo - eps, hi + eps
    k = int(bins) if bins else bins_freedman_diaconis(a, lo, hi)
    k = max(1, min(512, k))
    counts, edges = np.histogram(a, bins=k, range=(lo, hi))
    return [int(c) for c in counts], [float(e) for e in edges]


def _read_band_array(layer, band=1, max_pixels=4_000_000, decimation=None):
    import numpy as np

    ds = None
    if layer is not None and getattr(layer, "is_raster", None) \
            and layer.is_raster():
        try:
            ds = layer.dataset()
        except Exception:
            _log.exception("silent exception in _read_band_array")
            ds = None
    if ds is None:
        return None
    band = max(1, min(int(band or 1), int(ds.count or 1)))
    h, w = int(ds.height), int(ds.width)
    total = h * w
    step = max(1, int(decimation)) if decimation else 1
    if not decimation and total > max_pixels:
        step = int(math.ceil(math.sqrt(total / float(max_pixels))))

    try:
        if step > 1 and total > max_pixels:
            oh = max(1, h // step)
            ow = max(1, w // step)
            from rasterio.enums import Resampling
            arr = ds.read(band, out_shape=(1, oh, ow),
                          resampling=Resampling.nearest)
            arr = arr[0]
        else:
            arr = ds.read(band)
            if step > 1:
                arr = arr[::step, ::step]
    except Exception:
        _log.exception("silent exception in _read_band_array")
        return None
    arr = np.asarray(arr)
    nodata = ds.nodata
    mask = np.isfinite(arr) if arr.dtype.kind == "f" else None
    if nodata is not None:
        try:
            nod = np.isclose(arr, nodata) if arr.dtype.kind == "f" \
                else (arr == nodata)
            mask = nod if mask is None else (mask & ~nod)
        except Exception:
            _log.exception("silent exception in _read_band_array")
    if mask is not None:
        arr = arr[mask]
    else:
        arr = arr.ravel()
    return arr


@_guard.off_ui("core.stats.raster_band_values")
def raster_band_values(layer, band=1, max_samples=200_000, decimation=None):
    import numpy as np

    arr = _read_band_array(layer, band, decimation=decimation)
    if arr is None or arr.size == 0:
        return []
    if arr.size > max_samples:
        step = int(math.ceil(arr.size / float(max_samples)))
        arr = arr[::step]
    return [float(v) for v in np.asarray(arr, dtype="float64")]


@_guard.off_ui("core.stats.stacked_raster_values")
def stacked_raster_values(layer, max_pixels=4_000_000):
    return raster_band_values(layer, 1)


@_guard.off_ui("core.stats.raster_band_stats")
def raster_band_stats(layer, band=1, decimation=None):
    import numpy as np

    arr = _read_band_array(layer, band, decimation=decimation)
    st = FieldStats([], 0, "band %d" % int(band or 1))
    if arr is None or arr.size == 0:
        return st
    a = np.asarray(arr, dtype="float64")
    a = a[np.isfinite(a)]
    if a.size == 0:
        return st
    st.count = int(a.size)
    st.minimum = float(a.min())
    st.maximum = float(a.max())
    st.mean = float(a.mean())
    st.std = float(a.std())
    st.median = float(np.median(a))
    st.total = float(a.sum())
    try:
        st.unique = int(np.unique(a).size)
    except Exception:
        _log.exception("silent exception in raster_band_stats")
        st.unique = 0
    return st
