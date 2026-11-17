# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import ctypes
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DLL_PATH = os.path.join(HERE, "ggs_prims.dll")

_lib = None
_reason = "未加载"
IMPL = {"build_prims": "numpy"}
SPEEDUP = {}


def _bind(lib):
    p_d = ctypes.POINTER(ctypes.c_double)
    p_f = ctypes.POINTER(ctypes.c_float)
    p_i64 = ctypes.POINTER(ctypes.c_int64)
    lib.ggs_prims_version.restype = ctypes.c_int
    lib.ggs_prims_version.argtypes = []

    lib.ggs_build_prims.restype = ctypes.c_int
    lib.ggs_build_prims.argtypes = [
        p_d, p_d, ctypes.c_ssize_t,
        p_i64, p_i64, ctypes.c_ssize_t,
        p_i64,
        ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double,
        ctypes.c_double, ctypes.c_double,
        ctypes.c_double,
        ctypes.c_int64,
        p_f, p_i64, p_i64, p_i64, p_i64,
        p_i64,
    ]
    lib.ggs_decimate_parts.restype = ctypes.c_int64
    lib.ggs_decimate_parts.argtypes = [
        p_f, p_i64, p_i64, ctypes.c_ssize_t, ctypes.c_int, ctypes.c_double,
        p_i64, p_i64]
    return lib


def _try_load():
    global _lib, _reason
    _lib = None
    if not os.path.isfile(DLL_PATH):
        _reason = "未编译（ggs_prims.dll 不存在），纯 Python 回退"
        return None
    try:
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(HERE)
            except Exception:
                exc_note("_try_load @ ggis/render/native/primitives.py:70")
                pass
        lib = ctypes.CDLL(DLL_PATH)
        _lib = _bind(lib)
        _reason = "OK（ABI 版本 %d）" % lib.ggs_prims_version()
        return _lib
    except Exception as e:
        exc_note("_try_load @ ggis/render/native/primitives.py:76")
        _reason = "载入失败：%r，纯 Python 回退" % (e,)
        _lib = None
        return None


def _f(arr):
    if not arr.flags["C_CONTIGUOUS"]:
        raise ValueError("图元内核要求 C 连续数组（先 np.ascontiguousarray）")
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_float))


def _d(arr):
    if not arr.flags["C_CONTIGUOUS"]:
        raise ValueError("图元内核要求 C 连续数组（先 np.ascontiguousarray）")
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_double))


def _q(arr):
    if not arr.flags["C_CONTIGUOUS"]:
        raise ValueError("图元内核要求 C 连续数组（先 np.ascontiguousarray）")
    return arr.ctypes.data_as(ctypes.POINTER(ctypes.c_int64))


def _np_build_prims(xs, ys, starts, ends, classes, sx, sy, x0, y0,
                    clip, pad, nclass):
    px = ((xs - x0) * sx)
    py = ((y0 - ys) * sy)
    out_xy = np.empty((len(xs), 2), dtype=np.float32)
    out_xy[:, 0] = px
    out_xy[:, 1] = py
    n = len(starts)
    idx = np.clip(starts, 0, max(0, len(px) - 1))
    if len(idx) == 0 or len(px) == 0:
        empty = np.empty(0, dtype=np.int64)
        return (out_xy, empty, empty, empty,
                np.zeros(max(1, int(nclass)) + 1, dtype=np.int64))
    bx0 = np.minimum.reduceat(px, idx)
    bx1 = np.maximum.reduceat(px, idx)
    by0 = np.minimum.reduceat(py, idx)
    by1 = np.maximum.reduceat(py, idx)
    e_all = np.asarray(ends, dtype=np.int64)[:n]
    valid = (e_all - np.asarray(starts, dtype=np.int64)[:n]) >= 2
    with np.errstate(invalid="ignore"):
        keep = (valid
                & (bx1 >= clip[0] - pad) & (bx0 <= clip[2] + pad)
                & (by1 >= clip[1] - pad) & (by0 <= clip[3] + pad))
    part = np.nonzero(keep)[0].astype(np.int64)
    cls = (np.asarray(classes, dtype=np.int64)[part] if classes is not None
           else np.zeros(len(part), dtype=np.int64))
    if nclass < 1:
        nclass = 1
    cc = np.clip(cls, 0, nclass - 1)
    order = np.argsort(cc, kind="stable").astype(np.int64)
    indptr = np.zeros(nclass + 1, dtype=np.int64)
    np.cumsum(np.bincount(cc, minlength=nclass), out=indptr[1:])
    return out_xy, part, cls, order, indptr


def available():
    return _lib is not None


def describe():
    if _lib is None:
        return "图元内核：不可用（%s）" % _reason
    sp = ", ".join("%s %.1fx" % (k, SPEEDUP[k]) for k in sorted(SPEEDUP)
                   if SPEEDUP[k] > 1.0)
    return "图元内核：%s；实现 %s；实测 %s" % (
        _reason, IMPL["build_prims"], sp or "（未测）")


def reload():
    _try_load()
    _select_impl()
    return _lib is not None


def build_prims(xs, ys, starts, ends, classes, sx, sy, x0, y0, clip,
                pad=2.0, nclass=1):
    xs = np.ascontiguousarray(xs, dtype=np.float64)
    ys = np.ascontiguousarray(ys, dtype=np.float64)
    starts = np.ascontiguousarray(starts, dtype=np.int64)
    ends = np.ascontiguousarray(ends, dtype=np.int64)
    nparts = len(starts)
    nclass = max(1, int(nclass))
    cl = (float(clip[0]), float(clip[1]), float(clip[2]), float(clip[3]))
    if _lib is not None and IMPL["build_prims"] == "c":
        out_xy = np.empty((len(xs), 2), dtype=np.float32)
        part = np.empty(nparts, dtype=np.int64)
        cls = np.empty(nparts, dtype=np.int64)
        order = np.empty(nparts, dtype=np.int64)
        indptr = np.empty(nclass + 1, dtype=np.int64)
        n_out = ctypes.c_int64(0)
        ca = (None if classes is None
              else np.ascontiguousarray(classes, dtype=np.int64))
        rc = _lib.ggs_build_prims(
            _d(xs), _d(ys), len(xs), _q(starts), _q(ends), nparts,
            (_q(ca) if ca is not None else None),
            float(sx), float(sy), float(x0), float(y0),
            cl[0], cl[1], cl[2], cl[3], float(pad), nclass,
            _f(out_xy), _q(part), _q(cls), _q(order), _q(indptr),
            ctypes.byref(n_out))
        if rc == 0:
            m = int(n_out.value)
            return out_xy, part[:m], cls[:m], order[:m], indptr
    return _np_build_prims(xs, ys, starts, ends, classes, sx, sy, x0, y0,
                           cl, float(pad), nclass)


def decimate_parts(xy, starts, ends, keep_min=3, min_dist=1.2):
    if _lib is None:
        return np.asarray(starts), np.asarray(ends)
    a = np.ascontiguousarray(xy, dtype=np.float32)
    if not a.flags.writeable:
        a = a.copy()
    s = np.ascontiguousarray(starts, dtype=np.int64)
    e = np.ascontiguousarray(ends, dtype=np.int64)
    os_ = np.empty(len(s), dtype=np.int64)
    oe = np.empty(len(s), dtype=np.int64)
    rc = _lib.ggs_decimate_parts(_f(a), _q(s), _q(e), len(s),
                                 int(keep_min), float(min_dist),
                                 _q(os_), _q(oe))
    if rc != 0:
        return s, e
    return os_, oe


def verify(n_parts=400, n_pt=10, seed=17):
    if _lib is None:
        return True, "图元内核不可用，跳过（纯 Python 路径）"
    rng = np.random.default_rng(seed)
    rng2 = np.random.default_rng(seed)
    starts = (np.arange(n_parts, dtype=np.int64) * n_pt)
    ends = starts + n_pt
    xs = np.ascontiguousarray(rng.random(n_parts * n_pt) * 1000.0)
    ys = np.ascontiguousarray(rng.random(n_parts * n_pt) * 1000.0)
    classes = np.ascontiguousarray(
        rng2.integers(0, 4, n_parts).astype(np.int64))
    sx, sy = 0.7, -0.7
    x0, y0 = 100.0, 400.0
    clip = (0.0, 0.0, 600.0, 400.0)
    pad = 2.0
    nclass = 4

    old = IMPL["build_prims"]
    IMPL["build_prims"] = "c"
    c_xy, c_part, c_cls, c_order, c_indptr = build_prims(
        xs, ys, starts, ends, classes, sx, sy, x0, y0, clip, pad, nclass)
    IMPL["build_prims"] = old
    n_xy, n_part, n_cls, _n_order, n_indptr = _np_build_prims(
        xs, ys, starts, ends, classes, sx, sy, x0, y0, clip, pad, nclass)

    msgs = []
    ok = np.array_equal(c_part, n_part)
    msgs.append("裁剪 %s（C %d / np %d）" % (
        "OK" if ok else "MISMATCH", len(c_part), len(n_part)))
    ok2 = np.array_equal(c_cls, n_cls)
    msgs.append("类别 %s" % ("OK" if ok2 else "MISMATCH"))
    ok3 = np.allclose(c_xy, n_xy, rtol=0, atol=1e-3)
    msgs.append("屏幕坐标 %s" % ("OK" if ok3 else "MISMATCH"))
    ok4 = np.array_equal(c_indptr, n_indptr)
    msgs.append("类别分桶 %s" % ("OK" if ok4 else "MISMATCH"))
    if ok4:
        for k in range(nclass):
            lo, hi = int(c_indptr[k]), int(c_indptr[k + 1])
            if hi <= lo:
                continue
            got = np.sort(c_part[c_order[lo:hi]])
            want = np.sort(n_part[n_cls == k])
            if not np.array_equal(got, want):
                ok4 = False
                msgs.append("  第 %d 类成员不符" % k)
                break
    return bool(ok and ok2 and ok3 and ok4), "；".join(msgs)


def _select_impl():
    global IMPL, SPEEDUP
    IMPL = {"build_prims": "numpy"}
    SPEEDUP = {}
    if _lib is None:
        return
    import time
    rng = np.random.default_rng(20260912)
    n_parts, n_pt = 20000, 40
    starts = (np.arange(n_parts, dtype=np.int64) * n_pt)
    ends = starts + n_pt
    xs = np.ascontiguousarray(rng.random(n_parts * n_pt) * 1000.0)
    ys = np.ascontiguousarray(rng.random(n_parts * n_pt) * 1000.0)
    classes = np.ascontiguousarray(
        rng.integers(0, 8, n_parts).astype(np.int64))
    clip = (0.0, 0.0, 600.0, 400.0)

    def timeit(fn, reps=5):
        best = None
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            dt = time.perf_counter() - t0
            best = dt if best is None else min(best, dt)
        return best

    def c_run():
        old = IMPL["build_prims"]
        IMPL["build_prims"] = "c"
        try:
            build_prims(xs, ys, starts, ends, classes, 0.7, -0.7, 100.0,
                        400.0, clip, 2.0, 8)
        finally:
            IMPL["build_prims"] = old

    try:
        t_c = timeit(c_run)
        t_np = timeit(lambda: _np_build_prims(
            xs, ys, starts, ends, classes, 0.7, -0.7, 100.0, 400.0, clip,
            2.0, 8))
        if t_c > 0 and t_np > 0:
            SPEEDUP["build_prims"] = t_np / t_c
            IMPL["build_prims"] = "c" if t_np / t_c >= 1.0 else "numpy"
    except Exception:
        exc_note("_select_impl @ ggis/render/native/primitives.py:332")
        pass


_try_load()
_select_impl()
