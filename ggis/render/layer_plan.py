# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from ..core.crs import (convert_bounds, crs_transformer, needs_reproject)
from ggis.core.crs.extent import GgsRectangle

__all__ = ["LayerRenderPlan", "plan_for", "rect_to_pixel_rect",
           "rect_to_pixel_int"]

DEFAULT_MAX_PIXELS = 2048
DEFAULT_TILE_OUT_PX = 384
DEFAULT_MAX_TILE_OUT = 1024


@dataclass(frozen=True)
class LayerRenderPlan:

    layer: Any
    mode: str
    src_crs: Any
    dst_crs: Any
    otf: bool
    read_extent: GgsRectangle
    read_extent_crs: str
    out_size: Optional[Tuple[int, int]]
    rect_extent: GgsRectangle
    dst_rect: Tuple[float, float, float, float]
    dest_grid: bool
    data_extent: GgsRectangle
    reproject_extent: Optional[GgsRectangle]
    out_of_data: bool
    max_pixels: int
    prefer: str = field(default="source")

    @property
    def out_w(self) -> int:
        return 0 if not self.out_size else int(self.out_size[0])

    @property
    def out_h(self) -> int:
        return 0 if not self.out_size else int(self.out_size[1])

    def rect_tuple_i(self) -> Tuple[int, int, int, int]:
        x, y, w, h = self.dst_rect
        return (int(round(x)), int(round(y)), int(round(w)), int(round(h)))


def _scale_xy(settings):
    ex = settings.extent()
    w = float(ex.width())
    h = float(ex.height())
    sx = float(settings.output_width()) / w if w > 0 else 1.0
    sy = float(settings.output_height()) / h if h > 0 else 1.0
    return sx, sy


def rect_to_pixel_rect(settings, rect) -> Tuple[float, float, float, float]:
    if rect is None:
        return (0.0, 0.0, 0.0, 0.0)
    ex = settings.extent()
    sx, sy = _scale_xy(settings)
    x0 = (float(rect.xmin) - float(ex.xmin)) * sx
    x1 = (float(rect.xmax) - float(ex.xmin)) * sx
    y0 = (float(ex.ymax) - float(rect.ymax)) * sy
    y1 = (float(ex.ymax) - float(rect.ymin)) * sy
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return (x0, y0, x1 - x0, y1 - y0)


def _clamp_pixels(v, hi):
    try:
        n = int(round(float(v)))
    except Exception:
        exc_note("_clamp_pixels @ ggis/render/layer_plan.py:131")
        n = 1
    return max(1, min(int(hi), n))


def rect_to_pixel_int(settings, rect):
    x, y, w, h = rect_to_pixel_rect(settings, rect)
    x0, y0 = int(round(x)), int(round(y))
    x1, y1 = int(round(x + w)), int(round(y + h))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def _convert(rect, src_crs, dst_crs):
    if rect is None or src_crs is None or dst_crs is None:
        return rect
    if not needs_reproject(src_crs, dst_crs):
        return rect
    try:
        b = convert_bounds((rect.xmin, rect.ymin, rect.xmax, rect.ymax),
                           crs_transformer(src_crs, dst_crs))
    except Exception:
        exc_note("_convert @ ggis/render/layer_plan.py:166")
        return None
    if b is None:
        return None
    return GgsRectangle(b[0], b[1], b[2], b[3])


def _layer_extent(layer):
    try:
        e = layer.extent()
    except Exception:
        exc_note("_layer_extent @ ggis/render/layer_plan.py:176")
        return None
    if e is None or e.is_empty():
        return None
    return e


def _crs_of(layer):
    try:
        return layer.crs()
    except Exception:
        exc_note("_crs_of @ ggis/render/layer_plan.py:186")
        return None


def _prefer_for(layer):
    try:
        src = layer.source()
    except Exception:
        exc_note("_prefer_for @ ggis/render/layer_plan.py:197")
        return "source"
    if not src:
        return "source"
    try:
        from ..io import raster_pyramid as _pyr
        return "pyramid" if _pyr.read_meta(src) is not None else "quicklook"
    except Exception:
        exc_note("_prefer_for @ ggis/render/layer_plan.py:204")
        return "source"


def plan_for(layer, settings, *, mode="layer",
             dst_crs=None,
             max_pixels=DEFAULT_MAX_PIXELS,
             tile_out_px=DEFAULT_TILE_OUT_PX,
             max_tile_out=DEFAULT_MAX_TILE_OUT,
             tile_span=None,
             force_extent=None,
             force_crs=None,
             force_out_size=None):
    if mode == "layer":
        if layer is None or settings is None:
            return None
        try:
            if not settings.is_ready():
                return None
            view = settings.extent()
        except Exception:
            exc_note("plan_for @ ggis/render/layer_plan.py:249")
            return None
        if view is None or view.is_empty():
            return None
    else:
        view = None

    dst = dst_crs
    if dst is None:
        try:
            dst = settings.destination_crs()
        except Exception:
            exc_note("plan_for @ ggis/render/layer_plan.py:266")
            dst = None
    src = _crs_of(layer) if layer is not None else None
    if isinstance(dst, str):
        try:
            from ..core.crs import GgsCrs as _GgsCrs
            dst = _GgsCrs.from_user_input(dst)
        except Exception:
            exc_note("plan_for @ ggis/render/layer_plan.py:277")
            pass
    try:
        otf = bool(needs_reproject(src, dst))
    except Exception:
        exc_note("plan_for @ ggis/render/layer_plan.py:281")
        otf = False

    if mode == "layer" and (view is None or view.is_empty()):
        return None

    ow = oh = 0
    if mode == "layer":
        try:
            ow = int(settings.output_width())
            oh = int(settings.output_height())
        except Exception:
            exc_note("plan_for @ ggis/render/layer_plan.py:300")
            return None
        if ow <= 0 or oh <= 0:
            return None

    prefer = _prefer_for(layer) if layer is not None else "source"

    if mode == "layer":
        lext = _layer_extent(layer)
        if lext is None:
            return None
        if otf:
            to_src = crs_transformer(dst, src)
            b = convert_bounds((view.xmin, view.ymin, view.xmax, view.ymax),
                               to_src) if to_src is not None else None
            if b is None:
                return None
            target = GgsRectangle(b[0], b[1], b[2], b[3]).intersect(lext)
            read_ext = target
            read_crs = "src"
            to_dst = crs_transformer(src, dst)
            lext_dst = None
            if to_dst is not None:
                b2 = convert_bounds((lext.xmin, lext.ymin,
                                     lext.xmax, lext.ymax), to_dst)
                if b2 is not None:
                    lext_dst = GgsRectangle(b2[0], b2[1], b2[2], b2[3])
            rect_ext = view.intersect(lext_dst) if lext_dst is not None else view
            reproj = rect_ext
            dx_rect = rect_to_pixel_rect(settings, rect_ext)
            out = (_clamp_pixels(dx_rect[2], max_pixels),
                   _clamp_pixels(dx_rect[3], max_pixels))
            dest_grid = True
        else:
            target = view.copy().intersect(lext)
            read_ext = target
            read_crs = "dst"
            dx_rect = rect_to_pixel_rect(settings, target)
            out = (_clamp_pixels(dx_rect[2], max_pixels),
                   _clamp_pixels(dx_rect[3], max_pixels))
            rect_ext = target
            reproj = None
            dest_grid = False
        _empty = target.is_empty()
        return LayerRenderPlan(
            layer=layer, mode=mode, src_crs=src, dst_crs=dst, otf=otf,
            read_extent=read_ext, read_extent_crs=read_crs, out_size=out,
            rect_extent=rect_ext,
            dst_rect=((0.0, 0.0, 0.0, 0.0) if _empty
                      else dx_rect),
            dest_grid=dest_grid, data_extent=target,
            reproject_extent=reproj, out_of_data=_empty,
            max_pixels=int(max_pixels), prefer=prefer)

    if mode == "tile_cell":
        req = force_extent
        if req is None:
            return None
        lext = _layer_extent(layer)
        if otf:
            read_ext = req
            reproj = req
            read_crs = "dst"
        else:
            if lext is None:
                return None
            read_ext = req.copy().intersect(lext)
            reproj = None
            read_crs = "dst"
        if force_out_size is not None:
            try:
                out = (_clamp_pixels(force_out_size[0], max_tile_out),
                       _clamp_pixels(force_out_size[1], max_tile_out))
            except Exception:
                exc_note("plan_for @ ggis/render/layer_plan.py:397")
                out = None
            if out is None:
                force_out_size = None
        if force_out_size is None:
            if tile_span is None:
                out = (max(1, int(tile_out_px)), max(1, int(tile_out_px)))
            else:
                tw, th = float(tile_span[0]), float(tile_span[1])
                if tw <= 0 or th <= 0:
                    out = (max(1, int(tile_out_px)), max(1, int(tile_out_px)))
                else:
                    out = (_clamp_pixels(read_ext.width() / tw * tile_out_px,
                                         max_tile_out),
                           _clamp_pixels(read_ext.height() / th * tile_out_px,
                                         max_tile_out))
        _empty2 = read_ext.is_empty()
        return LayerRenderPlan(
            layer=layer, mode=mode, src_crs=src, dst_crs=dst, otf=otf,
            read_extent=read_ext, read_extent_crs=read_crs, out_size=out,
            rect_extent=read_ext,
            dst_rect=(0.0, 0.0, 0.0, 0.0),
            dest_grid=False, data_extent=read_ext,
            reproject_extent=reproj, out_of_data=_empty2,
            max_pixels=int(max_tile_out), prefer=prefer)

    if mode == "tile_source":
        if force_extent is None:
            return None
        geo = _convert(force_extent, force_crs, dst)
        if geo is None:
            return None
        return LayerRenderPlan(
            layer=layer, mode=mode, src_crs=force_crs, dst_crs=dst,
            otf=bool(needs_reproject(force_crs, dst)),
            read_extent=geo, read_extent_crs="dst", out_size=None,
            rect_extent=geo,
            dst_rect=(0.0, 0.0, 0.0, 0.0),
            dest_grid=False, data_extent=geo,
            reproject_extent=None, out_of_data=geo.is_empty(),
            max_pixels=int(max_pixels), prefer="source")

    return None
