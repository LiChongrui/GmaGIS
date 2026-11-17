# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import ctypes
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DLL_PATH = os.path.join(HERE, "ggs_accel.dll")

_lib = None
_reason = "未加载"

IMPL = {"part_bbox": "numpy", "bucketize": "numpy", "tile_assign": "numpy"}
SPEEDUP = {}


def _bind(lib):
    p_d = ctypes.POINTER(ctypes.c_double)
    p_i64 = ctypes.POINTER(ctypes.c_int64)
    lib.ggs_accel_version.restype = ctypes.c_int
    lib.ggs_accel_version.argtypes = []

    lib.ggs_part_bbox.restype = ctypes.c_int
    lib.ggs_part_bbox.argtypes = [p_d, p_d, ctypes.c_ssize_t, p_i64, p_i64,
                                  ctypes.c_ssize_t, p_d]

    lib.ggs_bucketize.restype = ctypes.c_int
    lib.ggs_bucketize.argtypes = [p_i64, ctypes.c_ssize_t, ctypes.c_int,
                                  p_i64, p_i64, p_i64]

    lib.ggs_tile_assign.restype = ctypes.c_int
    lib.ggs_tile_assign.argtypes = [p_d, p_d, ctypes.c_ssize_t,
                                    ctypes.c_double, ctypes.c_double,
                                    ctypes.c_double, ctypes.c_double,
                                    ctypes.c_int64, ctypes.c_int,
                                    p_i64, p_i64]
    return lib


def _try_load():
    global _lib, _reason
    _lib = None
    if not os.path.isfile(DLL_PATH):
        _reason = "未编译（ggis/render/native/ggs_accel.dll 不存在），纯 Python 回退"
        return None
    try:
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(HERE)
            except Exception:
                exc_note("_try_load @ ggis/render/native/accel.py:88")
                pass
        lib = ctypes.CDLL(DLL_PATH)
        ver = _bind(lib).ggs_accel_version()
        _lib = lib
        _reason = "OK（ABI 版本 %d）" % ver
        return lib
    except Exception as e:
        exc_note("_try_load @ ggis/render/native/accel.py:95")
        _reason = "载入失败：%r，纯 Python 回退" % (e,)
        _lib = None
        return None


def _d(arr):
    if not arr.flags["C_CONTIGUOUS"]:
        raise ValueError("传给原生层的 float64 数组必须 C 连续"
                         "（先 np.ascontiguousarray）")
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))


def _q(arr):
    if not arr.flags["C_CONTIGUOUS"]:
        raise ValueError("传给原生层的 int64 数组必须 C 连续"
                         "（先 np.ascontiguousarray）")
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int64))


def _np_part_bbox(xs, ys, starts, ends):
    s = np.ascontiguousarray(starts, dtype=np.int64)
    out = np.empty((len(s), 4), dtype=np.float64)
    n = len(xs)
    if n == 0 or len(s) == 0:
        return out
    idx = np.clip(s, 0, n - 1)
    out[:, 0] = np.minimum.reduceat(xs, idx)
    out[:, 1] = np.minimum.reduceat(ys, idx)
    out[:, 2] = np.maximum.reduceat(xs, idx)
    out[:, 3] = np.maximum.reduceat(ys, idx)
    e = np.asarray(ends, dtype=np.int64)[:len(s)]
    bad = e <= s
    if bad.any():
        out[bad, 0] = 1.0
        out[bad, 1] = 1.0
        out[bad, 2] = -1.0
        out[bad, 3] = -1.0
    return out


def _np_bucketize(bucket_in, nc):
    nb = int(nc) * int(nc)
    b = np.clip(np.asarray(bucket_in, dtype=np.int64), 0, nb - 1)
    order = np.argsort(b, kind="stable").astype(np.int64)
    counts = np.bincount(b, minlength=nb)
    indptr = np.zeros(nb + 1, dtype=np.int64)
    np.cumsum(counts, out=indptr[1:])
    return np.asarray(bucket_in, dtype=np.int64), order, indptr


def _np_tile_assign(x0, y0, gx0, gy0, tw, th, n_axis, factor):
    n_axis = int(n_axis)
    nc = n_axis // int(factor)
    cx = np.clip(((x0 - gx0) / tw).astype(np.int64), 0, n_axis - 1)
    cy = np.clip(((y0 - gy0) / th).astype(np.int64), 0, n_axis - 1)
    assign = cx * n_axis + cy
    cid = (cx // int(factor)) * nc + (cy // int(factor))
    return assign, cid


def available():
    return _lib is not None


def describe():
    if _lib is None:
        return "原生加速层：不可用（%s）" % _reason
    picks = ", ".join("%s=%s" % (k, IMPL[k]) for k in sorted(IMPL))
    sp = ", ".join("%s %.1fx" % (k, SPEEDUP[k]) for k in sorted(SPEEDUP)
                   if SPEEDUP[k] > 1.0)
    return "原生加速层：%s；实现选择 %s；实测加速 %s" % (
        _reason, picks, sp or "（无）")


def reload():
    _try_load()
    _select_impls()
    return _lib is not None


def split_xy(xy):
    a = np.ascontiguousarray(xy, dtype=np.float64)
    if a.ndim != 2 or a.shape[1] < 2:
        flat = np.ascontiguousarray(a.ravel(), dtype=np.float64)
        return flat, flat
    return (np.ascontiguousarray(a[:, 0]), np.ascontiguousarray(a[:, 1]))


def part_bbox(xs, ys, starts, ends):
    xs = np.ascontiguousarray(xs, dtype=np.float64)
    ys = np.ascontiguousarray(ys, dtype=np.float64)
    s = np.ascontiguousarray(starts, dtype=np.int64)
    e = np.ascontiguousarray(ends, dtype=np.int64)
    if _lib is not None and IMPL["part_bbox"] == "c":
        out = np.empty((len(s), 4), dtype=np.float64)
        rc = _lib.ggs_part_bbox(_d(xs), _d(ys), len(xs), _q(s), _q(e), len(s),
                                _d(out))
        if rc == 0:
            return out
    return _np_part_bbox(xs, ys, s, e)


def bucketize(bucket_in, nc):
    b = np.ascontiguousarray(bucket_in, dtype=np.int64)
    if _lib is not None and IMPL["bucketize"] == "c":
        n = len(b)
        nb = int(nc) * int(nc)
        out_b = np.empty(n, dtype=np.int64)
        order = np.empty(n, dtype=np.int64)
        indptr = np.empty(nb + 1, dtype=np.int64)
        rc = _lib.ggs_bucketize(_q(b), n, int(nc), _q(out_b), _q(order),
                                _q(indptr))
        if rc == 0:
            return out_b, order, indptr
    return _np_bucketize(b, nc)


def tile_assign(x0, y0, gx0, gy0, tw, th, n_axis, factor):
    x0 = np.ascontiguousarray(x0, dtype=np.float64)
    y0 = np.ascontiguousarray(y0, dtype=np.float64)
    n = len(x0)
    if n != len(y0):
        raise ValueError("tile_assign: x0 / y0 长度不一致")
    if _lib is not None and IMPL["tile_assign"] == "c":
        a = np.empty(n, dtype=np.int64)
        c = np.empty(n, dtype=np.int64)
        rc = _lib.ggs_tile_assign(_d(x0), _d(y0), n, float(gx0), float(gy0),
                                  float(tw), float(th), int(n_axis),
                                  int(factor), _q(a), _q(c))
        if rc == 0:
            return a, c
    return _np_tile_assign(x0, y0, gx0, gy0, tw, th, n_axis, factor)


def verify(n_part=5000, n_pt=32, seed=7):
    if _lib is None:
        return True, "原生层不可用，跳过（纯 Python 路径）"
    rng = np.random.default_rng(seed)
    starts = (np.arange(n_part, dtype=np.int64) * n_pt)
    ends = starts + n_pt
    xs = rng.random(n_part * n_pt) * 1000.0
    ys = rng.random(n_part * n_pt) * 1000.0
    ends[::97] = starts[::97]
    msgs = []

    bb_c = _c_part_bbox(xs, ys, starts, ends)
    bb_n = _np_part_bbox(xs, ys, starts, ends)
    ok = np.allclose(bb_c, bb_n, rtol=0, atol=0)
    msgs.append("part_bbox %s" % ("OK" if ok else "MISMATCH"))
    if not ok:
        d = np.abs(bb_c - bb_n).max()
        msgs.append("  最大差 %.6g" % d)

    nc = 32
    bid = rng.integers(0, nc * nc, n_part).astype(np.int64)
    bid[::53] = 0
    bid[::71] = nc * nc - 1
    bc, oc, ic = _c_bucketize(bid, nc)
    bn, on, inn = _np_bucketize(bid, nc)
    ok2 = (np.array_equal(bc, bn) and np.array_equal(ic, inn)
           and _csr_equal(oc, ic, on, inn))
    msgs.append("bucketize %s" % ("OK" if ok2 else "MISMATCH"))
    ok = ok and ok2

    vx0, vy0 = float(xs.min()), float(ys.min())
    vx1, vy1 = float(xs.max()), float(ys.max())
    n_axis, factor = 64, 8
    tw = (vx1 - vx0) / n_axis
    th = (vy1 - vy0) / n_axis
    ac, cc = _c_assign(bb_c, vx0 - 5.0, vy0 - 5.0, tw, th, n_axis, factor)
    an, cn = _np_tile_assign(bb_n[:, 0], bb_n[:, 1], vx0 - 5.0, vy0 - 5.0,
                             tw, th, n_axis, factor)
    ok3 = np.array_equal(ac, an) and np.array_equal(cc, cn)
    msgs.append("tile_assign %s" % ("OK" if ok3 else "MISMATCH"))
    ok = ok and ok3

    return ok, "；".join(msgs)


def _csr_equal(order_c, indptr_c, order_n, indptr_n):
    if not np.array_equal(indptr_c, indptr_n):
        return False
    for b in range(len(indptr_c) - 1):
        a = np.sort(order_c[indptr_c[b]:indptr_c[b + 1]])
        c = np.sort(order_n[indptr_n[b]:indptr_n[b + 1]])
        if not np.array_equal(a, c):
            return False
    return True


def _c_part_bbox(xs, ys, starts, ends):
    out = np.empty((len(starts), 4), dtype=np.float64)
    rc = _lib.ggs_part_bbox(_d(xs), _d(ys), len(xs), _q(starts), _q(ends),
                            len(starts), _d(out))
    if rc != 0:
        raise RuntimeError("ggs_part_bbox rc=%d" % rc)
    return out


def _c_assign(bbox, gx0, gy0, tw, th, n_axis, factor):
    n = len(bbox)
    cx_in = np.ascontiguousarray(bbox[:, 0], dtype=np.float64)
    cy_in = np.ascontiguousarray(bbox[:, 1], dtype=np.float64)
    a = np.empty(n, dtype=np.int64)
    c = np.empty(n, dtype=np.int64)
    rc = _lib.ggs_tile_assign(_d(cx_in), _d(cy_in), n, gx0, gy0,
                              tw, th, int(n_axis), int(factor), _q(a), _q(c))
    if rc != 0:
        raise RuntimeError("ggs_tile_assign rc=%d" % rc)
    return a, c


def _c_bucketize(bid, nc):
    n = len(bid)
    out_b = np.empty(n, dtype=np.int64)
    order = np.empty(n, dtype=np.int64)
    indptr = np.empty(int(nc) * int(nc) + 1, dtype=np.int64)
    rc = _lib.ggs_bucketize(_q(bid), n, int(nc), _q(out_b), _q(order),
                            _q(indptr))
    if rc != 0:
        raise RuntimeError("ggs_bucketize rc=%d" % rc)
    return out_b, order, indptr


def _select_impls():
    global IMPL, SPEEDUP
    IMPL = {"part_bbox": "numpy", "bucketize": "numpy", "tile_assign": "numpy"}
    SPEEDUP = {}
    if _lib is None:
        return
    import time
    rng = np.random.default_rng(20260912)

    N_PART, N_PT = 20000, 40
    starts = (np.arange(N_PART, dtype=np.int64) * N_PT)
    ends = starts + N_PT
    xs = np.ascontiguousarray(rng.random(N_PART * N_PT) * 1000.0)
    ys = np.ascontiguousarray(rng.random(N_PART * N_PT) * 1000.0)
    bid = rng.integers(0, 64 * 64, N_PART).astype(np.int64)
    bb = np.empty((N_PART, 4), dtype=np.float64)
    bx0 = xs[starts]
    by0 = ys[starts]
    bb[:, 0] = bx0
    bb[:, 1] = by0
    bb[:, 2] = bx0 + 25.0
    bb[:, 3] = by0 + 25.0
    ax0, ay0, tw, th = 0.0, 0.0, 1000.0 / 256, 1000.0 / 256

    def timeit(fn, reps=8):
        best = None
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
        return best

    try:
        _decide("part_bbox",
                timeit(lambda: _c_part_bbox(xs, ys, starts, ends)),
                timeit(lambda: _np_part_bbox(xs, ys, starts, ends)))
    except Exception:
        exc_note("_select_impls @ ggis/render/native/accel.py:410")
        pass
    try:
        _decide("bucketize", timeit(lambda: _c_bucketize(bid, 64)),
                timeit(lambda: _np_bucketize(bid, 64)))
    except Exception:
        exc_note("_select_impls @ ggis/render/native/accel.py:415")
        pass
    try:
        _decide("tile_assign",
                timeit(lambda: _c_assign(bb, ax0, ay0, tw, th, 256, 8)),
                timeit(lambda: _np_tile_assign(bx0, by0, ax0, ay0, tw, th,
                                               256, 8)))
    except Exception:
        exc_note("_select_impls @ ggis/render/native/accel.py:422")
        pass


def _decide(name, t_c, t_np):
    if t_c is None or t_np is None or t_c <= 0 or t_np <= 0:
        return
    ratio = t_np / t_c
    SPEEDUP[name] = ratio
    IMPL[name] = "c" if ratio >= 1.0 else "numpy"


_try_load()
_select_impls()
