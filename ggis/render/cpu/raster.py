# -*- coding: utf-8 -*-
from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from collections import OrderedDict
import weakref

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

__all__ = [
    "RESAMPLE_NEAREST", "RESAMPLE_BILINEAR",
    "LIMIT_MINMAX", "LIMIT_STDDEV", "LIMIT_CUT", "DEFAULT_CUT",
    "stretch_limits", "compose_rgba",
    "GgsBuiltinRasterPainter", "clear_cache", "cache_stats",
]

RESAMPLE_NEAREST = "nearest"
RESAMPLE_BILINEAR = "bilinear"

LIMIT_MINMAX = "minmax"
LIMIT_STDDEV = "stddev"
LIMIT_CUT = "cumulative_cut"
DEFAULT_CUT = (2.0, 98.0)
DEFAULT_STDDEV = 2.0

_SAMPLE_MAX = 200_000

_CACHE_MAX = 32
_CACHE = OrderedDict()
_STATS = {"hit": 0, "miss": 0}

_RASTER_FRAME_MARGIN = 0.3
_RASTER_FRAME_SCALE_THRESHOLD = 2.0
_RASTER_FRAME_MAX = 6


def _layer_tag(layer):
    try:
        d = layer.__dict__
    except Exception:
        exc_note("_layer_tag @ ggis/render/cpu/raster.py:104")
        return id(layer)
    r = d.get("_ras_cref")
    if r is None:
        try:
            r = weakref.ref(layer)
        except TypeError:
            exc_note("_layer_tag @ ggis/render/cpu/raster.py:110")
            return id(layer)
        try:
            d["_ras_cref"] = r
        except Exception:
            exc_note("_layer_tag @ ggis/render/cpu/raster.py:114")
            pass
    return r


_LIMITS_CACHE = {}


def clear_limits_cache():
    _LIMITS_CACHE.clear()


def layer_limits(layer, display=None, band=0, method=LIMIT_CUT, nodata=None):
    if display is not None:
        try:
            from ggis.core.style import raster_display as _rd
            st = str(getattr(display, "stretch", "") or "")
            if st == _rd.STRETCH_NONE:
                return None
            if st == _rd.STRETCH_CUSTOM:
                v1 = getattr(display, "vmin", None)
                v2 = getattr(display, "vmax", None)
                if v1 is not None and v2 is not None and float(v1) < float(v2):
                    return (float(v1), float(v2))
                method = LIMIT_MINMAX
            elif st == _rd.STRETCH_MINMAX:
                method = LIMIT_MINMAX
            elif st == _rd.STRETCH_STDDEV:
                method = LIMIT_STDDEV
            elif st in (_rd.STRETCH_HIST_EQ, _rd.STRETCH_HIST_MATCH):
                method = LIMIT_MINMAX
            elif st == _rd.STRETCH_PERCENTILE:
                method = LIMIT_CUT
        except Exception:
            exc_note("layer_limits @ ggis/render/cpu/raster.py:165")
            pass
    key = None
    try:
        from ggis.core.style.raster_display import display_key as _dk
        key = (id(layer), _dk(layer, display), int(band or 0), str(method))
        hit = _LIMITS_CACHE.get(key)
        if hit is not None:
            return hit
    except Exception:
        exc_note("layer_limits @ ggis/render/cpu/raster.py:174")
        key = None
    out = None
    try:
        from ggis.core.style import raster_display as rd
        sample, _sx = rd.sample_array(layer, band=band)
        if sample is not None and getattr(sample, "size", 0):
            _k = DEFAULT_STDDEV
            if display is not None:
                try:
                    _k = float(getattr(display, "stddev_k", DEFAULT_STDDEV)
                              or DEFAULT_STDDEV)
                except Exception:
                    exc_note("layer_limits @ ggis/render/cpu/raster.py:195")
                    _k = DEFAULT_STDDEV
            lo, hi = stretch_limits(sample, nodata, method, stddev=_k)
            out = (float(lo), float(hi))
    except Exception:
        exc_note("layer_limits @ ggis/render/cpu/raster.py:199")
        out = None
    if out is not None and key is not None:
        if len(_LIMITS_CACHE) > 256:
            _LIMITS_CACHE.clear()
        _LIMITS_CACHE[key] = out
    return out


def clear_cache():
    _CACHE.clear()
    _LIMITS_CACHE.clear()
    _STATS.update({"hit": 0, "miss": 0})


def cache_stats():
    return {"size": len(_CACHE), "hit": _STATS["hit"], "miss": _STATS["miss"]}


def _finite(a):
    try:
        if np.asarray(a).dtype.kind == "f":
            return a[np.isfinite(a)]
    except Exception:
        exc_note("_finite @ ggis/render/cpu/raster.py:224")
        pass
    return np.asarray(a).ravel()


def _drop_nodata(a, nodata):
    v = _finite(a)
    if nodata is None or v.size == 0:
        return v
    try:
        return v[v != nodata]
    except Exception:
        exc_note("_drop_nodata @ ggis/render/cpu/raster.py:235")
        return v


def stretch_limits(arr, nodata=None, method=LIMIT_CUT, cut=DEFAULT_CUT,
                   stddev=DEFAULT_STDDEV, sample_max=_SAMPLE_MAX):
    v = _drop_nodata(arr, nodata)
    if v.size == 0:
        return 0.0, 1.0
    if v.size > sample_max:
        idx = np.linspace(0, v.size - 1, sample_max).astype(np.int64)
        v = v[idx]
    try:
        vals = v.astype(np.float64, copy=False)
    except Exception:
        exc_note("stretch_limits @ ggis/render/cpu/raster.py:268")
        vals = v.astype(np.float64)
    method = str(method or LIMIT_CUT).lower()
    try:
        if method == LIMIT_MINMAX:
            lo, hi = float(np.min(vals)), float(np.max(vals))
        elif method == LIMIT_STDDEV:
            mu = float(np.mean(vals))
            sd = float(np.std(vals))
            k = float(stddev or DEFAULT_STDDEV)
            lo, hi = mu - k * sd, mu + k * sd
            lo = max(lo, float(np.min(vals)))
            hi = min(hi, float(np.max(vals)))
        else:
            lo_p, hi_p = cut if cut else DEFAULT_CUT
            lo = float(np.percentile(vals, float(lo_p)))
            hi = float(np.percentile(vals, float(hi_p)))
    except Exception:
        exc_note("stretch_limits @ ggis/render/cpu/raster.py:285")
        lo, hi = float(np.min(vals)), float(np.max(vals))
    if not np.isfinite(lo) or not np.isfinite(hi):
        lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
    if hi <= lo:
        hi = lo + 1.0
    return lo, hi


def _stretch_band(band, nodata, limits):
    a = np.asarray(band)
    lo32 = np.float32(min(max(float(limits[0]), -3.0e38), 3.0e38))
    hi32 = np.float32(min(max(float(limits[1]), -3.0e38), 3.0e38))
    span = max(hi32 - lo32, np.float32(1e-9))
    out = np.clip(a, lo32, hi32).astype(np.float32, copy=False)
    out -= lo32
    out *= (np.float32(255.0) / span)
    np.clip(out, 0, 255, out=out)
    if out.dtype.kind == "f":
        np.nan_to_num(out, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
    return out.astype(np.uint8)


def _to_u8(band, nodata, limits, hist=None):
    if hist is not None:
        try:
            from ggis.core.style import raster_display as _rd
            g = _rd.hist_map(band, hist[0], hist[1])
            if g is not None:
                return g
        except Exception:
            exc_note("_to_u8 @ ggis/render/cpu/raster.py:338")
            pass
    return _stretch_band(band, nodata, limits)


def _to_u8_direct(band):
    a = np.asarray(band)
    if a.dtype == np.uint8:
        return a.astype(np.uint8, copy=False)
    lo = hi = None
    try:
        _info = np.iinfo(a.dtype)
        lo, hi = np.float32(_info.min), np.float32(_info.max)
    except (ValueError, TypeError):
        exc_note("_to_u8_direct @ ggis/render/cpu/raster.py:361")
        try:
            _fin = np.finfo(a.dtype)
            lo, hi = np.float32(_fin.min), np.float32(_fin.max)
        except (ValueError, TypeError):
            exc_note("_to_u8_direct @ ggis/render/cpu/raster.py:365")
            lo = hi = None
    if lo is None or hi is None:
        if a.size:
            return _stretch_band(a, None,
                                 (float(np.nanmin(a)), float(np.nanmax(a))))
        return np.zeros(a.shape[-2:] if a.ndim >= 2 else a.shape,
                        np.uint8)
    span = max(hi - lo, np.float32(1e-9))
    out = np.clip(a, lo, hi).astype(np.float32, copy=False)
    out -= lo
    out *= (np.float32(255.0) / span)
    np.clip(out, 0, 255, out=out)
    if out.dtype.kind == "f":
        np.nan_to_num(out, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
    return out.astype(np.uint8)


def _transparent_mask(a, nodata, valid_mask=None):
    mask = None
    try:
        if np.asarray(a).dtype.kind == "f":
            mask = ~np.isfinite(a)
    except Exception:
        exc_note("_transparent_mask @ ggis/render/cpu/raster.py:394")
        mask = None
    if nodata is not None:
        try:
            m = (a == nodata)
            mask = m if mask is None else (mask | m)
        except Exception:
            exc_note("_transparent_mask @ ggis/render/cpu/raster.py:400")
            pass
    if valid_mask is not None:
        try:
            vm = np.asarray(valid_mask, dtype=bool)
            inv = ~vm
            mask = inv if mask is None else (mask | inv)
        except Exception:
            exc_note("_transparent_mask @ ggis/render/cpu/raster.py:407")
            pass
    return mask


def _bg_mask(a, bg):
    if bg is None:
        return None
    try:
        m = (np.asarray(a) == bg)
        if m.ndim == 3:
            m = m.any(axis=0)
        return m
    except Exception:
        exc_note("_bg_mask @ ggis/render/cpu/raster.py:425")
        return None


def _gamma_lut(gamma):
    try:
        g = float(gamma or 1.0)
    except Exception:
        exc_note("_gamma_lut @ ggis/render/cpu/raster.py:433")
        return None
    if abs(g - 1.0) < 1e-6:
        return None
    x = np.arange(256, dtype=np.float64) / 255.0
    return (np.power(x, 1.0 / max(0.05, g)) * 255.0).astype(np.uint8)


def _apply_alpha_band(rgba, arr, display):
    if rgba is None or display is None:
        return rgba
    try:
        ab = int(getattr(display, "alpha_band", 0) or 0)
    except Exception:
        exc_note("_apply_alpha_band @ ggis/render/cpu/raster.py:464")
        return rgba
    if ab <= 0:
        return rgba
    try:
        a = np.asarray(arr)
        if a.ndim != 3 or a.shape[0] < 2:
            return rgba
        if getattr(display, "rgb_bands", None):
            layer = a[3] if a.shape[0] > 3 else None
        else:
            layer = a[ab - 1] if a.shape[0] >= ab else None
        if layer is None or tuple(layer.shape[:2]) != tuple(rgba.shape[:2]):
            return rgba
        v = layer.astype("float64")
        lo = float(np.nanmin(v))
        hi = float(np.nanmax(v))
        if not (hi > lo):
            u = np.full(v.shape, 255, dtype=np.uint8)
        else:
            u = np.clip((v - lo) / (hi - lo) * 255.0,
                        0.0, 255.0).astype(np.uint8)
        out = rgba.copy()
        out[..., 3] = ((out[..., 3].astype(np.uint16)
                        * u.astype(np.uint16)) // 255).astype(np.uint8)
        return out
    except Exception:
        exc_note("_apply_alpha_band @ ggis/render/cpu/raster.py:490")
        return rgba


def compose_rgba(arr, display=None, nodata=None, opacity=1.0,
                 valid_mask=None, method=LIMIT_CUT, limits=None, palette=None,
                 hist=None):
    return _apply_alpha_band(
        _compose_rgba_core(arr, display, nodata, opacity, valid_mask,
                           method, limits, palette, hist),
        arr, display)


def _compose_rgba_core(arr, display=None, nodata=None, opacity=1.0,
                       valid_mask=None, method=LIMIT_CUT, limits=None,
                       palette=None, hist=None):
    a = np.asarray(arr)
    if a.ndim not in (2, 3) or a.size == 0:
        return None
    if a.ndim == 3 and a.shape[0] == 1:
        a = a[0]

    nd = nodata
    gamma = None
    ramp = ""
    band = 0
    nd_rgba = None
    bg = None
    bg_rgba = None
    if display is not None:
        if not getattr(display, "use_nodata", False):
            nd = None
        elif getattr(display, "nodata", None) is not None:
            nd = display.nodata
        try:
            from ggis.core.style import raster_display as _rd
            nd_rgba = _rd.nodata_rgba(display)
        except Exception:
            exc_note("_compose_rgba_core @ ggis/render/cpu/raster.py:560")
            nd_rgba = None
        try:
            bg = _rd.bg_value(display)
            if bg is not None:
                bg_rgba = _rd.bg_rgba(display)
        except Exception:
            exc_note("_compose_rgba_core @ ggis/render/cpu/raster.py:566")
            bg = None
            bg_rgba = None
        gamma = _gamma_lut(getattr(display, "gamma", 1.0))
        ramp = str(getattr(display, "ramp", "") or "")
        band = int(getattr(display, "band", 0) or 0)
        if band and a.ndim == 3:
            i = band - 1
            a = a[i] if 0 <= i < a.shape[0] else a[0]

    alpha_v = int(round(255 * max(0.0, min(1.0, float(opacity or 0.0)))))
    alpha_v = max(0, min(255, alpha_v))

    def _hist_at(i):
        if hist is None:
            return None
        try:
            if isinstance(hist, (list, tuple)) and hist \
                    and isinstance(hist[0], (list, tuple)):
                return hist[i] if i < len(hist) else hist[-1]
        except Exception:
            exc_note("_hist_at @ ggis/render/cpu/raster.py:592")
            pass
        return hist

    if palette and a.ndim == 2:
        rgb = _palette_rgb(a, palette)
        if rgb is not None:
            mask = _transparent_mask(a, nd, valid_mask)
            bg_mask = _bg_mask(a, bg)
            return _pack(rgb, mask, alpha_v, None, nd_rgba, bg_rgba, bg_mask)

    if a.ndim == 2:
        try:
            from ggis.core.style import raster_display as _rd
            rgb = _rd.class_rgb(a, display, _limits_at(limits, 0))
        except Exception:
            exc_note("_compose_rgba_core @ ggis/render/cpu/raster.py:618")
            rgb = None
        if rgb is not None:
            mask = _transparent_mask(a, nd, valid_mask)
            bg_mask = _bg_mask(a, bg)
            return _pack(rgb, mask, alpha_v, None, nd_rgba, bg_rgba, bg_mask)

    _no_stretch = False
    try:
        from ggis.core.style import raster_display as _rd
        _no_stretch = (display is not None
                       and str(getattr(display, "stretch", "") or "")
                       == _rd.STRETCH_NONE)
    except Exception:
        exc_note("_compose_rgba_core @ ggis/render/cpu/raster.py:641")
        _no_stretch = False

    if ramp and ramp != "none" and a.ndim == 2:
        if _no_stretch:
            g = _to_u8_direct(a)
        else:
            _lim = _limits_at(limits, 0)
            if _lim is None:
                _lim = stretch_limits(a, nd, method)
            g = _to_u8(a, nd, _lim, _hist_at(0))
        rgb = _ramp_rgb(g, display)
        if rgb is not None:
            mask = _transparent_mask(a, nd, valid_mask)
            bg_mask = _bg_mask(a, bg)
            return _pack(rgb, mask, alpha_v, gamma, nd_rgba, bg_rgba, bg_mask)

    if a.ndim == 3:
        n = a.shape[0]
        out = []
        for i in range(min(3, n)):
            if _no_stretch:
                out.append(_to_u8_direct(a[i]))
            else:
                lim = _limits_at(limits, i)
                if lim is None:
                    lim = stretch_limits(a[i], nd, method)
                out.append(_to_u8(a[i], nd, lim, _hist_at(i)))
        while len(out) < 3:
            out.append(out[-1] if out else np.zeros(a.shape[-2:], np.uint8))
        rgb = np.dstack(out[:3])
        mask = _transparent_mask(a[:3], nd, valid_mask)
        bg_mask = _bg_mask(a[:3], bg)
        if mask is not None and mask.ndim == 3:
            mask = mask.any(axis=0)
    else:
        if _no_stretch:
            g = _to_u8_direct(a)
        else:
            lim = _limits_at(limits, 0) or stretch_limits(a, nd, method)
            g = _to_u8(a, nd, lim, _hist_at(0))
        rgb = _ramp_rgb(g, display)
        if rgb is None:
            rgb = np.dstack([g, g, g])
        mask = _transparent_mask(a, nd, valid_mask)
        bg_mask = _bg_mask(a, bg)

    return _pack(rgb, mask, alpha_v, gamma, nd_rgba, bg_rgba, bg_mask)


def _limits_at(limits, i):
    if limits is None:
        return None
    if isinstance(limits, (list, tuple)) and limits \
            and isinstance(limits[0], (list, tuple)):
        return limits[i] if i < len(limits) else limits[-1]
    return limits


def _ramp_rgb(gray, display):
    if display is None:
        return None
    code = str(getattr(display, "ramp", "") or "")
    if not code or code == "none":
        return None
    try:
        from ggis.core.style import raster_display as rd
        lut = rd.ramp_lut(code, 256, steps=rd.class_steps(display))
        if lut is None:
            return None
        if getattr(display, "invert_ramp", False):
            lut = lut[::-1].copy()
        lut = rd.apply_class_colors(lut, rd.class_steps(display),
                                    rd.class_colors_of(display))
        return lut[np.asarray(gray)]
    except Exception:
        exc_note("_ramp_rgb @ ggis/render/cpu/raster.py:732")
        return None


def _palette_rgb(values, palette):
    if not palette:
        return None
    try:
        from ..symbol import _apply_palette
        return _apply_palette(values, palette)
    except Exception:
        exc_note("_palette_rgb @ ggis/render/cpu/raster.py:748")
        return None


def _pack(rgb, mask, alpha_v, gamma, nd_rgba=None, bg_rgba=None, bg_mask=None):
    rgb = np.asarray(rgb)
    if gamma is not None:
        try:
            rgb = gamma[rgb]
        except Exception:
            exc_note("_pack @ ggis/render/cpu/raster.py:767")
            pass
    h, w = rgb.shape[0], rgb.shape[1]
    alpha = np.full((h, w), alpha_v, dtype=np.uint8)
    if mask is not None:
        try:
            m = np.asarray(mask, dtype=bool)
            if nd_rgba is None:
                alpha = np.where(m, 0, alpha)
            else:
                rgb = rgb.copy()
                rgb[m] = np.asarray(nd_rgba[:3], dtype=np.uint8)
                if int(nd_rgba[3]) < 255:
                    alpha = np.where(m, int(nd_rgba[3]), alpha)
        except Exception:
            exc_note("_pack @ ggis/render/cpu/raster.py:781")
            pass
    if bg_mask is not None:
        try:
            bm = np.asarray(bg_mask, dtype=bool)
            if bg_rgba is None:
                alpha = np.where(bm, 0, alpha)
            else:
                if not rgb.flags.writeable:
                    rgb = rgb.copy()
                rgb[bm] = np.asarray(bg_rgba[:3], dtype=np.uint8)
                if int(bg_rgba[3]) < 255:
                    alpha = np.where(bm, int(bg_rgba[3]), alpha)
        except Exception:
            exc_note("_pack @ ggis/render/cpu/raster.py:794")
            pass
    return np.dstack([rgb, alpha]).astype(np.uint8)


def _to_qimage(rgba):
    a = np.ascontiguousarray(rgba)
    h, w = a.shape[0], a.shape[1]
    img = QImage(a.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    return img.copy()


class GgsBuiltinRasterPainter(object):

    MAX_PIXELS = 2048

    def __init__(self):
        self.stats = {"read": 0, "pyr": 0, "pyr_probe": 0,
                      "compose": 0, "fallback": 0}
        self.stats["why"] = {}
        self._frame_cache = {}

    def invalidate(self):
        try:
            self._frame_cache.clear()
        except Exception:
            exc_note("invalidate @ ggis/render/cpu/raster.py:839")
            pass

    def draw(self, painter, layer, settings, opacity=1.0):
        def _no(reason):
            try:
                import os as _o
                if _o.environ.get("GGIS_RPROC_DEBUG"):
                    _n = None
                    try:
                        _n = layer.name()
                    except Exception:
                        exc_note("_no @ ggis/render/cpu/raster.py:854")
                        pass
                    print("[内置栅格] 未认领 %r ｜ 原因：%s" % (_n, reason),
                          flush=True)
            except Exception:
                exc_note("_no @ ggis/render/cpu/raster.py:858")
                pass
            return False

        if settings is None or layer is None or not layer.is_valid():
            return _no("layer=None / settings=None / layer.is_valid()=False")
        try:
            if not settings.is_ready():
                return _no("settings.is_ready()=False")
        except Exception as e:
            exc_note("draw @ ggis/render/cpu/raster.py:867")
            return _no("settings.is_ready() 抛异常 %r" % (e,))
        from ..layer_plan import plan_for as _plan_for
        try:
            plan = _plan_for(layer, settings, mode="layer",
                             max_pixels=self.MAX_PIXELS)
        except Exception as e:
            exc_note("draw @ ggis/render/cpu/raster.py:873")
            return _no("plan_for 抛异常 %r" % (e,))
        if plan is None or plan.out_of_data:
            _d = "plan=None"
            if plan is not None:
                try:
                    _d = ("otf=%s src=%r dst=%r" % (plan.otf,
                                                   str(plan.src_crs),
                                                   str(plan.dst_crs)))
                    _d += (" ｜ read_ext=%s ｜ rect_ext=%s"
                           % (plan.read_extent, plan.rect_extent))
                except Exception as e:
                    exc_note("draw @ ggis/render/cpu/raster.py:884")
                    _d = "取字段失败 %r" % (e,)
            return _no("out_of_data=%s ｜ %s"
                       % (None if plan is None else plan.out_of_data, _d))
        try:
            rect = QRectF(*plan.dst_rect)
        except Exception as e:
            exc_note("draw @ ggis/render/cpu/raster.py:890")
            return _no("dst_rect 建 QRectF 抛异常 %r" % (e,))
        if rect.isEmpty():
            return _no("dst_rect 是空的 %r" % (tuple(plan.dst_rect),))

        from ggis.core.style import raster_display as rd
        try:
            disp = rd.get_display(layer)
        except Exception:
            exc_note("draw @ ggis/render/cpu/raster.py:898")
            disp = None
        if disp is not None and opacity is not None:
            try:
                disp.opacity = min(1.0, max(0.0, float(opacity)))
            except Exception:
                exc_note("draw @ ggis/render/cpu/raster.py:903")
                pass
        op = 1.0
        try:
            _v = getattr(disp, "opacity", None)
            op = 1.0 if _v is None else float(_v)
        except Exception:
            exc_note("draw @ ggis/render/cpu/raster.py:913")
            op = 1.0

        _fk = self._raster_frame_key(layer, plan.dst_crs, disp)
        _view = settings.extent()
        if _view is not None and self._raster_try_reuse(painter, _fk,
                                                        _view, rect, op):
            return True

        w, h = int(plan.out_w), int(plan.out_h)
        if w <= 0 or h <= 0:
            return False

        key = self._cache_key(layer, plan, disp, w, h)
        img = _CACHE.get(key)
        if img is not None:
            _CACHE.move_to_end(key)
            _STATS["hit"] += 1
        else:
            img = self._render(layer, plan, disp, w, h)
            if img is None:
                self.stats["fallback"] += 1
                return False
            _CACHE[key] = img
            while len(_CACHE) > _CACHE_MAX:
                _CACHE.popitem(last=False)
            _STATS["miss"] += 1

        painter.save()
        try:
            painter.setOpacity(max(0.0, min(1.0, op)))
            painter.drawImage(rect, img)
        finally:
            painter.restore()
        self._raster_fill_buffer(_fk, layer, settings, disp, img, _view, rect)
        return True

    def _raster_frame_key(self, layer, dst_crs, disp):
        try:
            from ggis.core.style.raster_display import display_key
            dk = display_key(layer, disp)
        except Exception:
            exc_note("_raster_frame_key @ ggis/render/cpu/raster.py:968")
            dk = None
        try:
            from ...core.crs import crs_key as _ck
            dcr = _ck(dst_crs)
        except Exception:
            exc_note("_raster_frame_key @ ggis/render/cpu/raster.py:973")
            dcr = None
        return (_layer_tag(layer), dk, dcr)

    @staticmethod
    def _raster_src_rect(buf, world, view):
        try:
            fw = float(buf.width())
            fh = float(buf.height())
            if fw <= 0 or fh <= 0:
                return None
            ww = max(float(world.width()), 1e-12)
            wh = max(float(world.height()), 1e-12)
            sx = (float(view.xmin) - float(world.xmin)) / ww * fw
            sy = (float(world.ymax) - float(view.ymax)) / wh * fh
            sw = float(view.width()) / ww * fw
            sh = float(view.height()) / wh * fh
            sx = max(0.0, min(sx, fw - 1.0))
            sy = max(0.0, min(sy, fh - 1.0))
            sw = max(1.0, min(sw, fw - sx))
            sh = max(1.0, min(sh, fh - sy))
            return QRectF(sx, sy, sw, sh)
        except Exception:
            exc_note("_raster_src_rect @ ggis/render/cpu/raster.py:1003")
            return None

    @staticmethod
    def _raster_covered(src, valid_rects):
        try:
            todo = [src]
            for r in valid_rects:
                nxt = []
                for t in todo:
                    cx0 = max(t.x(), r.x())
                    cy0 = max(t.y(), r.y())
                    cx1 = min(t.x() + t.width(), r.x() + r.width())
                    cy1 = min(t.y() + t.height(), r.y() + r.height())
                    if cx1 <= cx0 or cy1 <= cy0:
                        nxt.append(t)
                        continue
                    if t.x() < cx0:
                        nxt.append(QRectF(t.x(), t.y(),
                                          cx0 - t.x(), t.height()))
                    if cx1 < t.x() + t.width():
                        nxt.append(QRectF(cx1, t.y(),
                                          t.x() + t.width() - cx1, t.height()))
                    if t.y() < cy0:
                        nxt.append(QRectF(t.x(), t.y(),
                                          t.width(), cy0 - t.y()))
                    if cy1 < t.y() + t.height():
                        nxt.append(QRectF(t.x(), cy1,
                                          t.width(), t.y() + t.height() - cy1))
                todo = nxt
                if not todo:
                    return True
            return not todo
        except Exception:
            exc_note("_raster_covered @ ggis/render/cpu/raster.py:1042")
            return False

    def _raster_try_reuse(self, painter, key, view, rect, op):
        f = self._frame_cache.get(key)
        if not f:
            return False
        buf = f.get("buf")
        world = f.get("world")
        valid = f.get("valid")
        if buf is None or world is None or buf.isNull() or not valid:
            return False
        try:
            cur_ppu = (rect.width() / max(float(view.width()), 1e-12)) \
                if rect.width() > 0 else 0.0
            stored_ppu = float(f.get("ppu", 0.0) or 0.0)
            if stored_ppu <= 0 or cur_ppu <= 0:
                return False
            ratio = cur_ppu / stored_ppu
            if abs(ratio - 1.0) > 0.01:
                return False
            if not world.contains(view):
                return False
            src = self._raster_src_rect(buf, world, view)
            if src is None or src.isEmpty():
                return False
            if not self._raster_covered(src, valid):
                return False
        except Exception:
            exc_note("_raster_try_reuse @ ggis/render/cpu/raster.py:1088")
            return False
        try:
            ix = int(round(src.x())); iy = int(round(src.y()))
            iw = int(round(src.width())); ih = int(round(src.height()))
            if iw <= 0 or ih <= 0:
                return False
            sub = buf.copy(ix, iy, iw, ih)
            painter.save()
            try:
                if op < 1.0:
                    painter.setOpacity(op)
                painter.drawImage(rect, sub)
            finally:
                painter.restore()
            return True
        except Exception:
            exc_note("_raster_try_reuse @ ggis/render/cpu/raster.py:1106")
            return False

    def _raster_fill_buffer(self, key, layer, settings, disp, img, view, rect):
        try:
            if img is None or img.isNull() or rect.isEmpty() or view is None:
                return
            real_w = settings.output_width()
            real_h = settings.output_height()
            if real_w <= 0 or real_h <= 0:
                return
            ppu_x = real_w / max(float(view.width()), 1e-12)
            ppu_y = real_h / max(float(view.height()), 1e-12)
            world = view.copy().grow(_RASTER_FRAME_MARGIN)
            fw = max(1, int(round(float(world.width()) * ppu_x)))
            fh = max(1, int(round(float(world.height()) * ppu_y)))
            f = self._frame_cache.get(key)
            need_new = True
            if f is not None:
                bw = f.get("buf")
                stored_ppu = float(f.get("ppu", 0.0) or 0.0)
                if (bw is not None and not bw.isNull()
                        and bw.width() == fw and bw.height() == fh
                        and stored_ppu > 0
                        and abs(stored_ppu - ppu_x) / stored_ppu < 0.25):
                    need_new = False
                if not f.get("world", view).contains(view):
                    need_new = True
            if need_new:
                buf = QImage(fw, fh, QImage.Format.Format_ARGB32_Premultiplied)
                buf.fill(0)
                f = {"buf": buf, "world": world, "ppu": float(ppu_x),
                     "valid": []}
                self._frame_cache[key] = f
                while len(self._frame_cache) > _RASTER_FRAME_MAX:
                    self._frame_cache.popitem(last=False)
            else:
                buf = f["buf"]
            src = self._raster_src_rect(buf, f["world"], view)
            if src is None or src.isEmpty():
                return
            ix = int(round(src.x())); iy = int(round(src.y()))
            iw = img.width(); ih = img.height()
            if ix < 0 or iy < 0 or ix + iw > buf.width() \
                    or iy + ih > buf.height():
                return
            bp = QPainter(buf)
            try:
                bp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                                 False)
                bp.drawImage(QRectF(ix, iy, iw, ih), img)
            finally:
                bp.end()
            f["valid"].append(QRectF(ix, iy, iw, ih))
        except Exception:
            exc_note("_raster_fill_buffer @ ggis/render/cpu/raster.py:1171")
            return

    @staticmethod
    def _cache_key(layer, plan, disp, w, h):
        try:
            from ggis.core.style.raster_display import display_key
            dk = display_key(layer, disp)
        except Exception:
            exc_note("_cache_key @ ggis/render/cpu/raster.py:1180")
            dk = None
        r = plan.dst_rect
        try:
            re_ = plan.read_extent
            rex = (round(float(re_.xmin), 6), round(float(re_.ymin), 6),
                   round(float(re_.xmax), 6), round(float(re_.ymax), 6))
        except Exception:
            exc_note("_cache_key @ ggis/render/cpu/raster.py:1204")
            rex = None
        try:
            _ve = plan.reproject_extent or plan.rect_extent
            vex = (round(float(_ve.xmin), 6), round(float(_ve.ymin), 6),
                   round(float(_ve.xmax), 6), round(float(_ve.ymax), 6))
        except Exception:
            exc_note("_cache_key @ ggis/render/cpu/raster.py:1231")
            vex = None
        try:
            from ...core.crs import crs_key as _crs_key
            dcr = _crs_key(plan.dst_crs)
        except Exception:
            exc_note("_cache_key @ ggis/render/cpu/raster.py:1236")
            dcr = None
        return (_layer_tag(layer),
                round(r[0], 2), round(r[1], 2), int(w), int(h),
                dk, rex, vex, dcr)

    def _render(self, layer, plan, disp, w, h):
        target = plan.read_extent
        band = int(getattr(disp, "band", 0) or 0) if disp is not None else 0
        rgb_bands = None
        if not band and disp is not None:
            try:
                rb = getattr(disp, "rgb_bands", None)
                rgb_bands = [int(b) for b in rb] if rb else None
            except Exception:
                exc_note("_render @ ggis/render/cpu/raster.py:1257")
                rgb_bands = None
        alpha_band = 0
        if not band and disp is not None:
            try:
                alpha_band = max(0, int(getattr(disp, "alpha_band", 0) or 0))
            except Exception:
                exc_note("_render @ ggis/render/cpu/raster.py:1267")
                alpha_band = 0
        bands = [band] if band else (
            (list(rgb_bands) + [alpha_band]) if (rgb_bands and alpha_band)
            else rgb_bands)
        arr, valid = None, None
        why = None
        _pyr_arr, _pyr_ok = None, False
        try:
            from ...io import raster_pyramid as _pyr
            _pyr_arr, _pyr_ok = _pyr.read_overview(
                layer.source(), target, (w, h), bands=bands)
        except Exception:
            exc_note("_render @ ggis/render/cpu/raster.py:1297")
            _pyr_arr, _pyr_ok = None, False
        if _pyr_ok and _pyr_arr is not None and getattr(_pyr_arr, "size", 0):
            if not plan.otf:
                arr = _pyr_arr
                self.stats["pyr"] += 1
            else:
                self.stats["pyr"] += 1
        rs_flag = self._resample_for(layer, plan, disp, w, h)
        if arr is None:
            try:
                if plan.otf:
                    arr, valid, _ext = layer.read_window_reprojected(
                        plan.reproject_extent or target, (w, h),
                        plan.dst_crs, resample=rs_flag, bands=bands,
                        src=_pyr_arr, src_extent=target)
                else:
                    arr, _ext = layer.read_window(
                        target, (w, h), resample=rs_flag,
                        bands=bands)
            except Exception as _e:
                exc_note("_render @ ggis/render/cpu/raster.py:1351")
                why = "read-exc:%s:%s" % (type(_e).__name__, _e)
                import os as _os
                if _os.environ.get("GGIS_DEBUG_OTF"):
                    import traceback as _tb
                    _tb.print_exc()
                self.stats.setdefault("why", {})
                self.stats["why"][why] = self.stats["why"].get(why, 0) + 1
                return None
            if arr is None:
                why = "read-none:extent=%s" % (
                    (plan.reproject_extent if plan.otf else target),)
                self.stats.setdefault("why", {})
                self.stats["why"][why] = self.stats["why"].get(why, 0) + 1
                return None
            self.stats["read"] += 1
        nd = None
        try:
            from ggis.core.style import raster_display as rd
            nd = rd.effective_nodata(layer, disp)
        except Exception:
            exc_note("_render @ ggis/render/cpu/raster.py:1372")
            nd = None
        method = LIMIT_CUT
        try:
            st = str(getattr(disp, "stretch", "") or "").lower()
            if "minmax" in st or "min-max" in st:
                method = LIMIT_MINMAX
            elif "std" in st:
                method = LIMIT_STDDEV
        except Exception:
            exc_note("_render @ ggis/render/cpu/raster.py:1381")
            method = LIMIT_CUT
        band = int(getattr(disp, "band", 0) or 0)
        if band:
            lim = layer_limits(layer, disp, band=band, method=method, nodata=nd)
            limits = [lim] if lim is not None else None
        else:
            limits = None
            try:
                _ml = [layer_limits(layer, disp, band=b,
                                    method=method, nodata=nd)
                       for b in (1, 2, 3)]
                if any(x is not None for x in _ml):
                    limits = _ml
            except Exception:
                exc_note("_render @ ggis/render/cpu/raster.py:1407")
                limits = None
        cmap = None
        try:
            from ggis.core.style import raster_display as _rd
            cmap = _rd.render_palette(layer, disp)
        except Exception:
            exc_note("_render @ ggis/render/cpu/raster.py:1416")
            cmap = None
        hist = None
        try:
            from ggis.core.style import raster_display as _rd
            if str(getattr(disp, "stretch", "") or "") in (
                    _rd.STRETCH_HIST_EQ, _rd.STRETCH_HIST_MATCH):
                if band:
                    hist = _rd.layer_hist_map(layer, disp, band=band)
                else:
                    hist = [_rd.layer_hist_map(layer, disp, band=i)
                            for i in (1, 2, 3)]
        except Exception:
            exc_note("_render @ ggis/render/cpu/raster.py:1431")
            hist = None
        rgba = compose_rgba(arr, disp, nodata=nd, opacity=1.0,
                            valid_mask=valid, method=method, limits=limits,
                            palette=cmap, hist=hist)
        if rgba is None:
            self.stats.setdefault("why", {})
            k = "compose-none:shape=%s" % (getattr(arr, "shape", None),)
            self.stats["why"][k] = self.stats["why"].get(k, 0) + 1
            return None
        self.stats["compose"] += 1
        return _to_qimage(rgba)

    @staticmethod
    def _resample_for(layer, plan, disp, w, h):
        try:
            from ggis.core.analysis import resampling as RS
            from ggis.core.app import settings as S
            ext = plan.reproject_extent if plan.otf else plan.read_extent
            return RS.for_display(
                layer, ext, w, h,
                default_in=S.get("raster_resample_in", RS.NEAREST),
                default_out=S.get("raster_resample_out", RS.NEAREST))
        except Exception:
            exc_note("_resample_for @ ggis/render/cpu/raster.py:1472")
            return 0
