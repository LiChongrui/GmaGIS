# -*- coding: utf-8 -*-

from __future__ import annotations

import math

import numpy as np

__all__ = ["sample_index", "take_exact", "pixel_range"]


def pixel_range(off, span, pad=0):
    i0 = int(math.floor(float(off))) - int(pad)
    i1 = int(math.ceil(float(off) + float(span))) + int(pad)
    if i1 <= i0:
        i1 = i0 + 1
    return i0, i1


def sample_index(out_len, off, span, pad0, limit):
    n = int(max(1, out_len))
    if limit <= 0:
        return np.zeros(n, dtype=np.int64)
    k = np.arange(n, dtype=np.float64)
    pos = float(off) + (k + 0.5) * (float(span) / n)
    idx = np.floor(pos - float(pad0)).astype(np.int64)
    return np.clip(idx, 0, int(limit) - 1)


def take_exact(arr, ci, ri):
    if arr is None:
        return None
    if arr.ndim == 3:
        return arr[:, ri, :][:, :, ci]
    return arr[ri][:, ci]
