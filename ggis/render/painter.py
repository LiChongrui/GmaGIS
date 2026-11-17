# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QPainter, QPainterPath,
                           QPen, QPolygonF)

from ..core.crs import (crs_key, crs_pair_key, crs_scale_factor,
                        crs_transformer, convert_bounds, convert_xy,
                        needs_reproject)
from ggis.core.crs.extent import GgsRectangle
from .viewport import GgsMapSettings
from .symbol import default_symbol, raster_to_rgba
from .cache import (RASTER_WINDOW_CACHE, THUMB_CACHE, RASTER_FRAME_CACHE,
                      invalidate_caches)
from .rasterize import (flat_coords, invalidate_flat, GgsCoverage,
                     sample_segments, clip_segments, adjacency_mask,
                     polygon_diff, estimate_samples)

__all__ = ["GgsVectorPainter", "GgsRasterPainter", "draw_layer",
           "build_lut", "selection_symbol"]

_PIXEL_BUDGET = 8_000_000
_LOD_ESCALATE = 3.0


_SEL_SS = 4

_SEL_QT_AA = True

_SEL_QT_MAX_VERTS = 1 << 62

_SEL_MIN_PEN_PX = 2.0

VAL_STROKE = 254

SELECTION_COLOR = "#4DFFE14D"
SELECTION_LINE = "#FFE14D"


def selection_symbol(kind, renderer=None):
    from ggis.core.crs.units import from_px as _px_to_unit
    from .symbol import GgsSymbol
    fill, line, alpha, w_fix = _selection_style()
    if renderer is None:
        syms = None
    else:
        syms = renderer.symbols()
    base = syms[0] if syms else None
    sym = (base.clone() if base is not None
           and callable(getattr(base, "clone", None))
           else GgsSymbol())
    sym.fill = QColor(line if kind == "line" else fill)
    sym.stroke = QColor(line)
    sym.opacity = 1.0
    sym.fill_alpha = 1.0 if kind == "line" else alpha
    w_px = (float(w_fix) if w_fix > 0
            else max(_SEL_MIN_PEN_PX, float(sym.px_width()) + 1.0))
    if kind != "point":
        sym.width = float(_px_to_unit(w_px, sym.unit))
    return sym


def _selection_style():
    from ggis.core.app import settings as _S

    def _g(k, d):
        v = _S.get(k, d)
        return d if v is None or v == "" else v

    _fc = QColor(str(_g("selection_fill_color", "#4DFFE14D")))
    line = QColor(str(_g("selection_line_color", SELECTION_LINE))).name()
    w = float(_g("selection_line_width", 0.0) or 0.0)
    fa = max(0.0, min(1.0, float(_fc.alphaF())))
    return (_fc.name() or "#FFE14D",
            line or SELECTION_LINE,
            max(0.0, min(1.0, fa)), max(0.0, w))


def _subset_rings(xy, starts, ends, mask):
    k_s = starts[mask]
    k_e = ends[mask]
    if k_s.size == 0:
        empty = np.empty(0, dtype=np.int64)
        return xy[:0], empty, empty
    cnt = (k_e - k_s).astype(np.int64)
    cut = np.cumsum(cnt)
    total = int(cut[-1]) if cut.size else 0
    if total <= 0:
        empty = np.empty(0, dtype=np.int64)
        return xy[:0], empty, empty
    head = np.concatenate(([0], cut[:-1]))
    own = np.repeat(head, cnt)
    seg_first = np.repeat(k_s, cnt)
    seg = seg_first + (np.arange(total, dtype=np.int64) - own)
    return xy[seg], np.concatenate([[0], cut[:-1]]), cut


_MIN_VISIBLE_PX = 1.5


def _cull_tiny_parts(data, ext, sw, sh, ss, pad):
    starts = data.get("part_starts")
    ends = data.get("part_ends")
    bb = data.get("geom_bbox")
    xy = data.get("xy")
    if (xy is None or starts is None or ends is None or bb is None
            or bb.shape[0] != starts.size or starts.size == 0):
        return (data.get("xy"), data.get("part_starts"),
                data.get("part_ends"), data.get("part_geom"), 0)
    min_ss = _MIN_VISIBLE_PX * ss
    try:
        sx0 = (bb[:, 1] - ext.xmin) * (sw * ss) + pad * ss
        sx1 = (bb[:, 3] - ext.xmin) * (sw * ss) + pad * ss
        sy0 = (ext.ymax - bb[:, 4]) * (sh * ss) + pad * ss
        sy1 = (ext.ymax - bb[:, 2]) * (sh * ss) + pad * ss
        tiny = ((sx1 - sx0) < min_ss) & ((sy1 - sy0) < min_ss)
    except Exception:
        exc_note("_cull_tiny_parts @ ggis/render/painter.py:274")
        return (xy, starts, ends, data.get("part_geom"), 0)
    if not tiny.any():
        return (xy, starts, ends, data.get("part_geom"), 0)
    keep = ~tiny
    xy_s, s_s, e_s = _subset_rings(xy, starts, ends, keep)
    pg = data.get("part_geom")
    pg_s = pg[keep] if pg is not None else None
    return xy_s, s_s, e_s, pg_s, int(tiny.sum())


def _build_ring_path(px, py, starts, ends, w=None, h=None, pad=1.0,
                     close_mask=None, clip_rect=None):
    path = QPainterPath()
    moveTo, lineTo, close = path.moveTo, path.lineTo, path.closeSubpath
    if w is not None and h is not None and starts.size:
        span = ends - starts
        keep = span >= 2
        if not keep.all():
            starts, ends = starts[keep], ends[keep]
            if close_mask is not None:
                close_mask = close_mask[keep]
        if starts.size == 0:
            return path, 0
        x0 = np.minimum.reduceat(px, starts)
        x1 = np.maximum.reduceat(px, starts)
        y0 = np.minimum.reduceat(py, starts)
        y1 = np.maximum.reduceat(py, starts)
        vis = ((x1 >= -pad) & (x0 <= w + pad) &
               (y1 >= -pad) & (y0 <= h + pad))
        if not vis.all():
            starts, ends = starts[vis], ends[vis]
            if close_mask is not None:
                close_mask = close_mask[vis]
        if starts.size == 0:
            return path, 0
    n_v = 0
    for k in range(starts.size):
        a = int(starts[k])
        b = int(ends[k])
        if b - a < 2:
            continue
        if clip_rect is not None:
            sx = px[a:b]
            sy = py[a:b]
            cx0, cy0, cx1, cy1, _keep = clip_segments(
                sx[:-1], sy[:-1], sx[1:], sy[1:],
                clip_rect[0], clip_rect[1], clip_rect[2], clip_rect[3])
            for i in range(cx0.shape[0]):
                moveTo(float(cx0[i]), float(cy0[i]))
                lineTo(float(cx1[i]), float(cy1[i]))
            n_v += int(cx0.shape[0]) * 2
            continue
        moveTo(float(px[a]), float(py[a]))
        for i in range(a + 1, b):
            lineTo(float(px[i]), float(py[i]))
        n_v += b - a
        if close_mask is not None and bool(close_mask[k]):
            close()
    return path, n_v


def _rgba4(color):
    return (color.red(), color.green(), color.blue(), color.alpha())


def _dash_pattern(symbol, width_px, ss):
    try:
        pat = symbol.line_pattern()
    except Exception:
        exc_note("_dash_pattern @ ggis/render/painter.py:382")
        return None
    if not pat:
        return None
    try:
        k = max(1.0, float(width_px)) * max(1, int(ss))
        out = [float(v) * k for v in pat]
    except Exception:
        exc_note("_dash_pattern @ ggis/render/painter.py:389")
        return None
    return out if len(out) >= 2 and len(out) % 2 == 0 else None


def build_lut(symbols, kind, single=True, stroke_color=None):
    lut = np.zeros((256, 4), dtype=np.uint8)
    if not symbols:
        return lut
    sym0 = symbols[0]
    if single:
        if kind == "point":
            lut[1] = _rgba4(sym0.stroke_color())
            lut[2] = _rgba4(sym0.fill_color())
        elif kind == "polygon":
            lut[1] = _rgba4(sym0.fill_color())
            lut[2] = _rgba4(sym0.stroke_color())
        else:
            lut[1] = _rgba4(sym0.fill_color())
        return lut
    for i, s in enumerate(symbols[:253], start=1):
        if kind == "polygon":
            lut[i] = _rgba4(s.fill_color())
        else:
            lut[i] = _rgba4(s.fill_color())
    lut[VAL_STROKE] = _rgba4(stroke_color or sym0.stroke_color())
    return lut

_MAX_VERTS = 5000

_POINT_TEMPLATE: dict = {}


def _point_sprite(r: int):
    cached = _POINT_TEMPLATE.get(r)
    if cached is not None:
        return cached
    def disk(rad):
        if rad <= 0:
            return [(0, 0)]
        lim = rad * rad + rad * 0.5
        out = []
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if dx * dx + dy * dy <= lim:
                    out.append((dx, dy))
        return out

    core = disk(max(0, r - 1))
    core_set = set(core)
    ring = [p for p in disk(r) if p not in core_set]
    trip = (np.asarray(ring, dtype=np.int32),
            np.asarray(core, dtype=np.int32),
            np.asarray(core + ring, dtype=np.int32))
    _POINT_TEMPLATE[r] = trip
    return trip


def _as_fid_array(fids) -> np.ndarray:
    if isinstance(fids, np.ndarray):
        return fids.astype(np.int64, copy=False)
    if isinstance(fids, range):
        return np.arange(fids.start, fids.stop, fids.step, dtype=np.int64)
    return np.fromiter(fids, dtype=np.int64, count=len(fids))


def vector_lod_tol(settings, src_crs=None, dst_crs=None):
    try:
        from ggis.core.app import settings as _S
        if not _S.get("vector_lod_simplify", False):
            return 0.0
        px = float(_S.get("vector_lod_tolerance_px", 1.2))
        if not (px > 0):
            px = 1.2
    except Exception:
        exc_note("vector_lod_tol @ ggis/render/painter.py:516")
        return 0.0
    try:
        mupp = settings.map_units_per_pixel()
        if not (mupp > 0):
            return 0.0
        tol = px * mupp
        if dst_crs is not None:
            tol *= crs_scale_factor(src_crs, dst_crs)
        return float(tol)
    except Exception:
        exc_note("vector_lod_tol @ ggis/render/painter.py:526")
        return 0.0


def _xy_cache(layer, dst_crs=None):
    tf = crs_transformer(layer.crs(), dst_crs) if dst_crs is not None else None
    key = crs_pair_key(layer.crs(), dst_crs) if tf is not None else ""
    cached = getattr(layer, "_ggs_xy", None)
    if (cached is not None and len(cached[1]) == layer.feature_count() + 1
            and getattr(layer, "_ggs_xy_key", "") == key):
        return cached
    from shapely import get_coordinates
    chunks, offsets = [], [0]
    n = 0
    for g in layer.geoms():
        if g is None or getattr(g, "is_empty", True):
            chunks.append(np.zeros((0, 2), dtype=np.float64))
        else:
            try:
                c = np.asarray(get_coordinates(g), dtype=np.float64)
                if c.ndim == 1:
                    c = c.reshape(-1, 2)
                chunks.append(c[:, :2])
            except Exception:
                exc_note("_xy_cache @ ggis/render/painter.py:575")
                chunks.append(np.zeros((0, 2), dtype=np.float64))
        n += chunks[-1].shape[0]
        offsets.append(n)
    xy = np.vstack(chunks) if chunks else np.zeros((0, 2))
    if tf is not None:
        xy = convert_xy(xy, tf)
    off = np.asarray(offsets, dtype=np.int64)
    out = (xy, off, off[:-1].copy(), (off[1:] - off[:-1]).copy())
    try:
        layer._ggs_xy = out
        layer._ggs_xy_key = key
    except Exception:
        exc_note("_xy_cache @ ggis/render/painter.py:587")
        pass
    return out


def invalidate_cache(layer):
    invalidate_caches(layer)
    invalidate_flat(layer)


class GgsVectorPainter:

    def __init__(self):
        self._last_rgba = None

    @staticmethod
    def _ss():
        try:
            from ggis.core.app import settings as app_settings
            raw = app_settings.get("vector_antialias_ss", None)
            if raw is None:
                raw = 2 if app_settings.get("render_antialias", True) else 1
            ss = int(round(float(raw)))
        except Exception:
            exc_note("_ss @ ggis/render/painter.py:637")
            ss = 2
        if ss < 1:
            ss = 1
        elif ss > 4:
            ss = 4
        return ss

    def draw(self, painter, layer, settings, symbol=None):
        if not settings.is_ready() or layer is None:
            return 0
        kind = layer.base_kind()

        classes = None
        symbols = None
        if symbol is None:
            from .renderers import get_renderer
            renderer = get_renderer(layer)
            try:
                syms = renderer.symbols()
            except Exception:
                exc_note("draw @ ggis/render/painter.py:660")
                syms = []
            if not syms:
                syms = [default_symbol(kind, 0)]
            try:
                cls = renderer.class_array(layer)
            except Exception:
                exc_note("draw @ ggis/render/painter.py:666")
                cls = None
            if cls is None or len(syms) <= 1:
                symbol = syms[0]
            else:
                symbol = syms[0]
                symbols = syms
                classes = cls
        ext = settings.extent()
        dst_crs = settings.destination_crs()
        try:
            src_crs = layer.crs()
        except Exception:
            exc_note("draw @ ggis/render/painter.py:678")
            src_crs = None

        if ext is None or ext.is_empty():
            return 0

        to_layer = crs_transformer(dst_crs, src_crs) \
            if dst_crs is not None else None
        if to_layer is None:
            qext = ext
        else:
            b = convert_bounds((ext.xmin, ext.ymin,
                                ext.xmax, ext.ymax),
                               to_layer)
            if b is None:
                return 0
            qext = GgsRectangle(b[0], b[1], b[2], b[3])

        if not qext.intersects(layer.extent()):
            return 0

        n_total = layer.feature_count()
        layer_ext = layer.extent()
        if n_total < 2000 or qext.contains(layer_ext):
            fids = range(n_total)
        else:
            fids = layer.query_bbox_array(
                qext.xmin, qext.ymin, qext.xmax, qext.ymax)

        fids = layer.filter_fids(fids)
        if fids is not None and len(fids) == 0:
            return 0

        lod_tol = vector_lod_tol(settings, src_crs, dst_crs)

        if kind == "point":
            return self._draw_points(painter, layer, settings, symbol,
                                     fids, lod_tol, classes, symbols)
        if kind == "line":
            return self._draw_lines(painter, layer, settings, symbol, ext,
                                    fids, lod_tol, classes, symbols)
        if kind == "polygon":
            return self._draw_polygons(painter, layer, settings, symbol,
                                       ext, fids, lod_tol, classes, symbols)
        return self._draw_generic(painter, layer, settings, symbol, ext,
                                  fids, lod_tol, classes, symbols)

    def _draw_points(self, painter, layer, settings, symbol, fids, lod_tol,
                     classes=None, symbols=None):
        xy, offsets, rows, counts = _xy_cache(layer,
                                              settings.destination_crs())
        if xy.shape[0] == 0 or not len(fids):
            return 0

        fid_arr = _as_fid_array(fids)
        if fid_arr.size == 0:
            return 0
        cnt = counts[fid_arr]
        total = int(cnt.sum())
        if total == 0:
            return 0
        starts = rows[fid_arr]
        idx = np.repeat(starts, cnt)
        if total != fid_arr.size:
            grp = np.arange(total, dtype=np.int64) - \
                np.repeat(np.cumsum(cnt) - cnt, cnt)
            idx = idx + grp
        sel = xy[idx]

        cls_v = None
        if classes is not None:
            vert_fid = np.repeat(fid_arr, cnt) if total != fid_arr.size \
                else fid_arr
            try:
                cls_v = np.asarray(classes, dtype=np.uint8)[vert_fid]
            except Exception:
                exc_note("_draw_points @ ggis/render/painter.py:793")
                cls_v = None

        ext = settings.extent()
        sx = settings.scale_x()
        sy = settings.scale_y()
        px = (sel[:, 0].astype(np.float32) - np.float32(ext.xmin))
        px *= np.float32(sx)
        py = (np.float32(ext.ymax) - sel[:, 1].astype(np.float32))
        py *= np.float32(sy)
        w, h = int(settings.output_width()), int(settings.output_height())
        m = 2.0
        keep = ((px >= -m) & (px <= w + m) & (py >= -m) & (py <= h + m))
        px = px[keep]
        py = py[keep]
        if cls_v is not None:
            cls_v = cls_v[keep]
        n = int(px.shape[0])
        if n == 0:
            return 0

        radius = max(1.0, symbol.px_size())
        multi = symbols is not None and len(symbols) > 1
        if radius <= 6.0 and symbol.px_width() <= 1.5:
            return self._draw_points_fast(painter, px, py, w, h,
                                          symbol, radius, symbols, cls_v,
                                          multi)
        return self._draw_points_slow(painter, px, py, n, symbol,
                                      symbols, cls_v)

    def _draw_points_fast(self, painter, px, py, w, h, symbol, radius,
                          symbols=None, cls_v=None, multi=False):
        n = int(px.shape[0])
        if n == 0:
            return 0
        xi = np.rint(px).astype(np.int32)
        yi = np.rint(py).astype(np.int32)
        np.clip(xi, 0, w - 1, out=xi)
        np.clip(yi, 0, h - 1, out=yi)

        lut = build_lut(symbols or [symbol], "point", single=not multi)

        r = int(round(radius))
        if r <= 1:
            pad = 1
            cov = np.zeros((h + 2 * pad, w + 2 * pad), dtype=np.uint8)
            cov[yi + pad, xi + pad] = (cls_v if cls_v is not None else 2)
        else:
            pad = r
            cov = np.zeros((h + 2 * pad, w + 2 * pad), dtype=np.uint8)
            X = xi + pad
            Y = yi + pad
            if multi and cls_v is not None:
                for dx, dy in _point_sprite(r)[2]:
                    cov[Y + dy, X + dx] = cls_v
            else:
                ring, core, _disk = _point_sprite(r)
                for dx, dy in ring:
                    cov[Y + dy, X + dx] = 1
                for dx, dy in core:
                    cov[Y + dy, X + dx] = 2

        rgba = np.ascontiguousarray(cov[pad:pad + h, pad:pad + w])
        rgba = lut[rgba]
        img = QImage(rgba.data, w, h, w * 4,
                     QImage.Format.Format_RGBA8888)
        self._last_rgba = rgba
        painter.drawImage(0, 0, img)
        return n


    def _draw_points_slow(self, painter, px, py, n, symbol, symbols=None,
                          cls_v=None):
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        groups = [(None, symbol)]
        if symbols and cls_v is not None:
            groups = []
            for k in np.unique(cls_v):
                if k == 0:
                    continue
                s = symbols[int(k) - 1] if int(k) - 1 < len(symbols) \
                    else symbol
                groups.append((int(k), s))
        for k, sym in groups:
            if k is None:
                sxp, syp = px, py
                cnt = n
            else:
                m = cls_v == k
                sxp = px[m]
                syp = py[m]
                cnt = int(sxp.shape[0])
            if cnt == 0:
                continue
            poly = QPolygonF()
            poly.reserve(cnt)
            ap = poly.append
            for i in range(cnt):
                ap(QPointF(float(sxp[i]), float(syp[i])))
            pen = QPen(sym.stroke_color(),
                       max(1.0, sym.px_size() + sym.px_width()))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(poly)
            pen = QPen(sym.fill_color(), max(1.0, sym.px_size()))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(poly)
        painter.restore()
        return n

    @staticmethod
    def _prepare_segments(data, n_geom, fids, ext, settings, pad, ss=1):
        xy = data["xy"]
        starts = data["part_starts"]
        ends = data["part_ends"]
        if xy.shape[0] < 2 or starts.size == 0:
            return None
        sw, sh = settings.scale_x(), settings.scale_y()
        xmin, ymax = ext.xmin, ext.ymax
        W = settings.output_width() * ss + 2 * pad * ss
        H = settings.output_height() * ss + 2 * pad * ss
        px = (xy[:, 0].astype(np.float32) - np.float32(xmin))
        px *= np.float32(sw * ss)
        px += np.float32(pad * ss)
        py = (np.float32(ymax) - xy[:, 1].astype(np.float32))
        py *= np.float32(sh * ss)
        py += np.float32(pad * ss)
        same = adjacency_mask(xy.shape[0], ends)
        if len(fids) < n_geom:
            pg = data["part_geom"]
            pg_hi = int(pg.max()) + 1 if pg.size else 0
            keep_geom = np.zeros(max(int(n_geom), pg_hi), dtype=bool)
            fa = _as_fid_array(fids)
            keep_geom[fa[fa < n_geom]] = True
            vert_part = np.repeat(np.arange(starts.size, dtype=np.int64),
                                  ends - starts)
            part_ok = keep_geom[pg]
            vert_ok = part_ok[vert_part]
            same &= vert_ok[:-1]
        idx = np.nonzero(same)[0]
        if idx.size == 0:
            return None
        ax = px[idx]
        ay = py[idx]
        bx = px[idx + 1]
        by = py[idx + 1]
        keep = ~((np.minimum(ax, bx) > W - 1) |
                 (np.maximum(ax, bx) < 0) |
                 (np.minimum(ay, by) > H - 1) |
                 (np.maximum(ay, by) < 0))
        pa = data["part_geom"]
        part_starts = starts
        part_ends = ends
        vert_part = np.repeat(np.arange(part_starts.size, dtype=np.int64),
                              part_ends - part_starts)
        seg_geom = pa[vert_part[idx[keep]]]
        return ax[keep], ay[keep], bx[keep], by[keep], seg_geom

    @staticmethod
    def _class_of_seg(classes, seg_geom):
        if classes is None or seg_geom is None:
            return None
        try:
            arr = np.asarray(classes, dtype=np.uint8)
            return arr[seg_geom]
        except Exception:
            exc_note("_class_of_seg @ ggis/render/painter.py:994")
            return None

    def _draw_lines(self, painter, layer, settings, symbol, ext, fids,
                    lod_tol, classes=None, symbols=None):
        w, h = int(settings.output_width()), int(settings.output_height())
        if w <= 0 or h <= 0:
            return 0
        n_geom = layer.feature_count()
        multi = symbols is not None and len(symbols) > 1
        width = max(1, int(round(symbol.px_width())))
        pad = max(2, width + 1)
        ss = self._ss()
        sw, sh = settings.scale_x(), settings.scale_y()
        xmin, ymax = ext.xmin, ext.ymax

        tol = lod_tol
        segs = None
        for attempt in range(3):
            if attempt == 1:
                ss = 1
            elif attempt == 2:
                tol = max(tol, 0.5) * _LOD_ESCALATE
                ss = 1
            data = flat_coords(layer, tol, kind="line",
                                dst_crs=settings.destination_crs())
            _xy, _st, _en, _pg, _ = _cull_tiny_parts(
                data, ext, sw, sh, ss, pad)
            _d2 = {"xy": _xy, "part_starts": _st,
                   "part_ends": _en, "part_geom": _pg}
            segs = self._prepare_segments(_d2, n_geom, fids, ext, settings,
                                          pad, ss)
            if segs is None:
                return 0
            if (estimate_samples(*segs[:4]) * (width * ss) ** 2
                    <= _PIXEL_BUDGET):
                break
        ax, ay, bx, by, seg_geom = segs
        if ax.size == 0:
            return 0
        W, H = w * ss + 2 * pad * ss, h * ss + 2 * pad * ss
        ax, ay, bx, by, keep = clip_segments(ax, ay, bx, by, 0.0, 0.0,
                                             float(W - 1), float(H - 1))
        if ax.size == 0:
            return 0
        seg_cls = None
        if multi:
            all_cls = self._class_of_seg(classes, seg_geom)
            if all_cls is not None:
                seg_cls = all_cls if keep is None else all_cls[keep]

        cov = GgsCoverage(w, h, pad=pad, ss=ss)
        dash = _dash_pattern(symbol, width, ss)
        round_cap = (str(getattr(symbol, "cap", "flat") or "flat") == "round")
        lut = build_lut(symbols or [symbol], "line", single=not multi)
        if seg_cls is not None:
            xi, yi, vi = sample_segments(ax, ay, bx, by, seg_cls, dash=dash)
            cov.stroke_pixels_v(xi, yi, vi, width * ss, round_cap=round_cap)
        else:
            xi, yi = sample_segments(ax, ay, bx, by, dash=dash)
            cov.stroke_pixels(xi, yi, 1, width * ss, round_cap=round_cap)
        img, rgba = cov.lut_image(lut=lut)
        self._last_rgba = rgba
        painter.drawImage(0, 0, img)
        return int(ax.size)

    def _draw_polygons(self, painter, layer, settings, symbol, ext, fids,
                       lod_tol, classes=None, symbols=None):
        w, h = int(settings.output_width()), int(settings.output_height())
        if w <= 0 or h <= 0:
            return 0
        n_geom = layer.feature_count()
        width = max(1, int(round(symbol.px_width())))
        pad = max(2, width + 1)
        sw, sh = settings.scale_x(), settings.scale_y()
        xmin, ymax = ext.xmin, ext.ymax
        ss = self._ss()

        tol = lod_tol
        multi = symbols is not None and len(symbols) > 1
        fill = symbol.fill_color()
        stroke = symbol.stroke_color()

        data = None
        segs = None
        for attempt in range(3):
            if attempt == 1:
                ss = 1
            elif attempt == 2:
                tol = max(tol, 0.5) * _LOD_ESCALATE
                ss = 1
            data = flat_coords(layer, tol, kind="polygon",
                                dst_crs=settings.destination_crs())
            if data["xy"].shape[0] < 3 or data["part_starts"].size == 0:
                return 0
            xy, starts, ends, part_geom, _ = _cull_tiny_parts(
                data, ext, sw, sh, ss, pad)
            d2 = {"xy": xy, "part_starts": starts,
                  "part_ends": ends, "part_geom": part_geom}
            segs = self._prepare_segments(d2, n_geom, fids, ext,
                                          settings, pad, ss)
            if segs is None:
                break
            stroke_cost = estimate_samples(*segs[:4]) * (width * ss) ** 2
            if fill.alpha() > 0 and stroke.alpha() > 0:
                n_parts = starts.size
                fill_scale = min(1.0, n_parts / 64.0)
                frame_cost = stroke_cost + w * h * (ss * ss) * fill_scale
            else:
                frame_cost = stroke_cost
            if frame_cost <= _PIXEL_BUDGET:
                break

        cov = GgsCoverage(w, h, pad=pad, ss=ss)
        w2, h2, pad2 = w * ss, h * ss, pad * ss
        sw2, sh2 = sw * ss, sh * ss
        drawn = 0
        if fill.alpha() > 0 and symbol.has_fill_pattern():
            cov.set_fill_pattern(symbol.fill_style,
                                 symbol.px_fill_spacing() * ss,
                                 symbol.px_fill_width() * ss)

        if multi and fill.alpha() > 0:
            part_cls = self._part_classes(d2, classes)
            if part_cls is not None:
                present = np.unique(part_cls)
                for k in present:
                    if k == 0:
                        continue
                    sel = part_cls == k
                    xx, ss_, ee = _subset_rings(xy, starts, ends, sel)
                    diff = polygon_diff(xx, ss_, ee,
                                        sw2, sh2, xmin, ymax, w2, h2, pad2)
                    cov.fill_from_diff(diff, int(k))
                drawn = int(present.size)
            else:
                diff = polygon_diff(xy, starts, ends, sw2, sh2,
                                    xmin, ymax, w2, h2, pad2)
                cov.fill_from_diff(diff, 1)
        elif fill.alpha() > 0:
            diff = polygon_diff(xy, starts, ends, sw2, sh2,
                                xmin, ymax, w2, h2, pad2)
            cov.fill_from_diff(diff, 1)

        stroke = symbol.stroke_color()
        if stroke.alpha() > 0 and segs is not None:
            ax, ay, bx, by = segs[:4]
            if ax.size:
                W2, H2 = w2 + 2 * pad2, h2 + 2 * pad2
                ax, ay, bx, by, keep = clip_segments(
                    ax, ay, bx, by, 0.0, 0.0, float(W2 - 1), float(H2 - 1))
                if ax.size:
                    xi, yi = sample_segments(ax, ay, bx, by,
                                             dash=_dash_pattern(symbol, width,
                                                                ss))
                    cov.stroke_pixels(xi, yi,
                                      VAL_STROKE if multi else 2, width * ss)
                    drawn = max(drawn, int(ax.size))

        lut = build_lut(symbols or [symbol], "polygon", single=not multi)
        img, rgba = cov.lut_image(lut=lut)
        self._last_rgba = rgba
        painter.drawImage(0, 0, img)
        return drawn

    @staticmethod
    def _part_classes(data, classes):
        if classes is None:
            return None
        try:
            c = np.asarray(classes, dtype=np.uint8)
            return c[data["part_geom"]]
        except Exception:
            exc_note("_part_classes @ ggis/render/painter.py:1224")
            return None

    def draw_selection(self, painter, layer, settings, fids, symbol=None,
                       ext=None, lod_tol=0.0):
        if not settings.is_ready() or layer is None:
            return 0
        fa = _as_fid_array(fids) if not isinstance(fids, np.ndarray) else fids
        if fa.size == 0:
            return 0
        kind = layer.base_kind()
        if ext is None:
            ext = settings.extent()
        sym = symbol or selection_symbol(kind, getattr(layer, "_renderer", None))
        w, h = int(settings.output_width()), int(settings.output_height())
        if w <= 0 or h <= 0:
            return 0

        if _SEL_QT_AA:
            if kind == "point":
                n = self._select_points_qt(painter, layer, settings,
                                           fa, sym, w, h)
            elif kind == "polygon":
                n = self._select_polygons_qt(painter, layer, settings,
                                             fa, sym, ext, lod_tol, w, h)
            else:
                n = self._select_lines_qt(painter, layer, settings,
                                          fa, sym, ext, lod_tol, w, h)
            if n >= 0:
                return n

        if kind == "point":
            return self._select_points(painter, layer, settings, fa, sym, w, h)
        if kind == "polygon":
            return self._select_polygons(painter, layer, settings, fa, sym,
                                         ext, lod_tol, w, h)
        return self._select_lines(painter, layer, settings, fa, sym, ext,
                                  lod_tol, w, h)


    def _select_points_qt(self, painter, layer, settings, fa, sym, w, h):
        xy, _off, rows, counts = _xy_cache(layer,
                                           settings.destination_crs())
        n = layer.feature_count()
        fa = fa[(fa >= 0) & (fa < min(n, rows.size))]
        if fa.size == 0:
            return -1
        single = bool(counts.size) and int(counts[fa].max()) == 1
        if single:
            px = xy[rows[fa], 0]
            py = xy[rows[fa], 1]
        else:
            verts = np.repeat(rows[fa], counts[fa])
            px = xy[verts, 0]
            py = xy[verts, 1]
        if px.size > _SEL_QT_MAX_VERTS:
            return -1
        sw, sh = settings.scale_x(), settings.scale_y()
        ext = settings.extent()
        sx = (px - float(ext.xmin)) * sw
        sy = (float(ext.ymax) - py) * sh
        m = max(1.0, float(sym.px_size())) / 2.0 + 3.0
        inside = ((sx >= -m) & (sx <= w - 1 + m) &
                  (sy >= -m) & (sy <= h - 1 + m))
        if not inside.all():
            sx = sx[inside]
            sy = sy[inside]
        if sx.size == 0:
            return 0
        return self._paint_selected_points(painter, sx, sy, sym)

    @staticmethod
    def _paint_selected_points(painter, sx, sy, sym):
        d = max(1.0, float(sym.px_size()))
        sw = max(0.0, float(sym.px_width()))
        outer = d + sw
        w = max(_SEL_MIN_PEN_PX, float(_selection_style()[3]))
        fill = sym.fill_color()
        stroke = sym.stroke_color()
        poly = QPolygonF()
        poly.reserve(int(sx.size))
        ap = poly.append
        for i in range(int(sx.size)):
            ap(QPointF(float(sx[i]), float(sy[i])))
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if fill.alpha() <= 0:
                rr = max(0.5, (outer - w) / 2.0)
                ring = QPainterPath()
                add = ring.addEllipse
                for i in range(poly.size()):
                    add(poly.at(i), rr, rr)
                pen = QPen(stroke, w)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(ring)
                return int(sx.size)
            pen_out = QPen(stroke, outer)
            pen_out.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_out)
            painter.drawPoints(poly)
            pen_in = QPen(fill, max(0.1, outer - 2.0 * w))
            pen_in.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_in)
            painter.drawPoints(poly)
        finally:
            painter.restore()
        return int(sx.size)

    def _select_lines_qt(self, painter, layer, settings, fa, sym, ext,
                         lod_tol, w, h):
        n_geom = layer.feature_count()
        data = flat_coords(layer, lod_tol, kind="line",
                           dst_crs=settings.destination_crs())
        xy = data["xy"]
        starts = data["part_starts"]
        ends = data["part_ends"]
        if xy.shape[0] < 2 or starts.size == 0:
            return -1
        ok = fa[(fa >= 0) & (fa < n_geom)]
        if ok.size == 0:
            return -1
        pg = data["part_geom"]
        pg_hi = int(pg.max()) + 1 if pg.size else 0
        sel = np.zeros(max(int(n_geom), pg_hi), dtype=bool)
        sel[ok] = True
        parts = np.nonzero(sel[pg])[0]
        if parts.size == 0:
            return 0
        if int((ends[parts] - starts[parts]).sum()) > _SEL_QT_MAX_VERTS:
            return -1
        sw, sh = settings.scale_x(), settings.scale_y()
        xmin, ymax = float(ext.xmin), float(ext.ymax)
        px = (xy[:, 0] - xmin) * sw
        py = (ymax - xy[:, 1]) * sh
        k_s = starts[parts]
        k_e = ends[parts]
        ok_seg = (k_e - k_s) >= 2
        closed = np.zeros(k_s.size, dtype=bool)
        if ok_seg.size:
            _k = np.nonzero(ok_seg)[0]
            closed[_k] = ((px[k_s[_k]] == px[k_e[_k] - 1]) &
                          (py[k_s[_k]] == py[k_e[_k] - 1]))
        path, _nv = _build_ring_path(px, py, k_s, k_e, w, h,
                                     close_mask=closed,
                                     clip_rect=(-2.0, -2.0,
                                                float(w) + 2.0,
                                                float(h) + 2.0))
        if path.elementCount() == 0:
            return 0
        pen = QPen(sym.fill_color(),
                   max(_SEL_MIN_PEN_PX, float(sym.px_width())))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pen)
            painter.drawPath(path)
        finally:
            painter.restore()
        return int(parts.size)

    def _select_polygons_qt(self, painter, layer, settings, fa, sym, ext,
                            lod_tol, w, h):
        n_geom = layer.feature_count()
        data = flat_coords(layer, lod_tol, kind="polygon",
                           dst_crs=settings.destination_crs())
        xy = data["xy"]
        starts = data["part_starts"]
        ends = data["part_ends"]
        if xy.shape[0] < 3 or starts.size == 0:
            return -1
        ok = fa[(fa >= 0) & (fa < n_geom)]
        if ok.size == 0:
            return -1
        pg = data["part_geom"]
        pg_hi = int(pg.max()) + 1 if pg.size else 0
        sel = np.zeros(max(int(n_geom), pg_hi), dtype=bool)
        sel[ok] = True
        part_sel = sel[pg]
        if not part_sel.any():
            return 0
        xx, r_starts, r_ends = _subset_rings(xy, starts, ends, part_sel)
        if r_ends.size == 0:
            return 0
        if int(r_ends[-1]) > _SEL_QT_MAX_VERTS:
            return -1
        sw, sh = settings.scale_x(), settings.scale_y()
        xmin, ymax = float(ext.xmin), float(ext.ymax)
        px = (xx[:, 0] - xmin) * sw
        py = (ymax - xx[:, 1]) * sh
        _rs = r_starts
        _re = r_ends
        _good = (_re - _rs) >= 3
        if not _good.all():
            _rs, _re = _rs[_good], _re[_good]
        if _rs.size == 0:
            return 0
        path, _nv = _build_ring_path(px, py, _rs, _re, w, h, close_mask=None)
        path.setFillRule(Qt.FillRule.WindingFill)
        if path.elementCount() == 0:
            return 0
        fill = sym.fill_color()
        stroke = sym.stroke_color()
        pen = QPen(stroke, max(_SEL_MIN_PEN_PX, float(sym.px_width())))
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QBrush(fill) if fill.alpha() > 0
                             else Qt.BrushStyle.NoBrush)
            painter.setPen(pen if stroke.alpha() > 0 else Qt.PenStyle.NoPen)
            painter.drawPath(path)
        finally:
            painter.restore()
        return int(part_sel.sum())

    def _select_points(self, painter, layer, settings, fa, sym, w, h):
        xy, _off, rows, counts = _xy_cache(layer,
                                           settings.destination_crs())
        n = layer.feature_count()
        fa = fa[(fa >= 0) & (fa < min(n, rows.size))]
        if fa.size == 0:
            return 0
        single = bool(counts.size) and int(counts[fa].max()) == 1
        if single:
            px = xy[rows[fa], 0].astype(np.float32)
            py = xy[rows[fa], 1].astype(np.float32)
        else:
            verts = np.repeat(rows[fa], counts[fa])
            px = xy[verts, 0].astype(np.float32)
            py = xy[verts, 1].astype(np.float32)
        sw, sh = settings.scale_x(), settings.scale_y()
        ext = settings.extent()
        sx = (px - np.float32(ext.xmin)) * np.float32(sw)
        sy = (np.float32(ext.ymax) - py) * np.float32(sh)
        m = max(1.0, float(sym.px_size())) / 2.0 + 3.0
        inside = ((sx >= -m) & (sx <= w - 1 + m) &
                  (sy >= -m) & (sy <= h - 1 + m))
        if not inside.all():
            sx = sx[inside]
            sy = sy[inside]
        if sx.size == 0:
            return 0
        return self._paint_selected_points(painter, sx, sy, sym)

    def _select_lines(self, painter, layer, settings, fa, sym, ext, lod_tol,
                      w, h):
        n_geom = layer.feature_count()
        data = flat_coords(layer, lod_tol, kind="line",
                                   dst_crs=settings.destination_crs())
        if data["xy"].shape[0] < 2 or data["part_starts"].size == 0:
            return 0
        width = max(1, int(round(sym.px_width())))
        pad = max(2, width + 1)
        ss = max(int(_SEL_SS), int(self._ss() or 1))
        segs = self._prepare_segments(data, n_geom, fa, ext, settings, pad,
                                      ss)
        if segs is None:
            return 0
        ax, ay, bx, by, _sg = segs
        if ax.size == 0:
            return 0
        W, H = w * ss + 2 * pad * ss, h * ss + 2 * pad * ss
        ax, ay, bx, by, _keep = clip_segments(ax, ay, bx, by, 0.0, 0.0,
                                              float(W - 1), float(H - 1))
        if ax.size == 0:
            return 0
        cov = GgsCoverage(w, h, pad=pad, ss=ss)
        xi, yi = sample_segments(ax, ay, bx, by)
        cov.stroke_pixels(xi, yi, 1, width * ss)
        img, rgba = cov.lut_image(lut=build_lut([sym], "line", single=True))
        self._last_rgba = rgba
        painter.drawImage(0, 0, img)
        return int(ax.size)

    def _select_polygons(self, painter, layer, settings, fa, sym, ext,
                         lod_tol, w, h):
        n_geom = layer.feature_count()
        data = flat_coords(layer, lod_tol, kind="polygon",
                                   dst_crs=settings.destination_crs())
        xy = data["xy"]
        starts = data["part_starts"]
        ends = data["part_ends"]
        if xy.shape[0] < 3 or starts.size == 0:
            return 0
        width = max(1, int(round(sym.px_width())))
        pad = max(2, width + 1)
        sw, sh = settings.scale_x(), settings.scale_y()
        xmin, ymax = ext.xmin, ext.ymax
        ss = max(int(_SEL_SS), int(self._ss() or 1))
        w2, h2, pad2 = w * ss, h * ss, pad * ss

        ok = fa[(fa >= 0) & (fa < n_geom)]
        pg = data["part_geom"]
        pg_hi = int(pg.max()) + 1 if pg.size else 0
        sel = np.zeros(max(int(n_geom), pg_hi), dtype=bool)
        sel[ok] = True
        part_sel = sel[pg]
        cov = GgsCoverage(w, h, pad=pad, ss=ss)
        fill = sym.fill_color()
        if part_sel.any() and fill.alpha() > 0:
            xx, ss_, ee = _subset_rings(xy, starts, ends, part_sel)
            if ee.size:
                diff = polygon_diff(xx, ss_, ee,
                                    sw * ss, sh * ss, xmin, ymax, w2, h2,
                                    pad2)
                cov.fill_from_diff(diff, 1)

        segs = self._prepare_segments(data, n_geom, fa, ext, settings, pad,
                                      ss)
        stroke = sym.stroke_color()
        if segs is not None and stroke.alpha() > 0:
            ax, ay, bx, by = segs[:4]
            if ax.size:
                W2, H2 = w2 + 2 * pad2, h2 + 2 * pad2
                ax, ay, bx, by, _k = clip_segments(
                    ax, ay, bx, by, 0.0, 0.0, float(W2 - 1), float(H2 - 1))
                if ax.size:
                    xi, yi = sample_segments(ax, ay, bx, by)
                    cov.stroke_pixels(xi, yi, 2, width * ss)
        img, rgba = cov.lut_image(lut=build_lut([sym], "polygon",
                                                single=True))
        self._last_rgba = rgba
        painter.drawImage(0, 0, img)
        return int(part_sel.sum())

    def _draw_generic(self, painter, layer, settings, symbol, ext, fids,
                      lod_tol, classes=None, symbols=None):
        return self._draw_lines(painter, layer, settings, symbol, ext,
                                fids, lod_tol, classes, symbols)


def _limits_for(layer, display, arr):
    from ggis.core.style import raster_display as rd
    n = arr.shape[0] if getattr(arr, "ndim", 2) == 3 else 1
    b = int(getattr(display, "band", 0) or 0)
    if b or n <= 1:
        return rd.layer_limits(layer, display, band=b or 1)
    return rd.layer_limits_multi(layer, display, count=n)


def _raster_covers_full_view(layer, settings, dst_crs, src_crs, otf):
    try:
        lext = layer.extent()
        view = settings.extent()
        if lext is None or view is None or lext.is_empty() or view.is_empty():
            return False
        eps = 1e-6 * max(float(lext.width()), float(lext.height()), 1.0)
        if otf:
            tf = crs_transformer(dst_crs, src_crs)
            if tf is None:
                return False
            b = convert_bounds((view.xmin, view.ymin,
                                view.xmax, view.ymax), tf)
            if b is None:
                return False
            vsrc = GgsRectangle(b[0], b[1], b[2], b[3])
            return (vsrc.xmin >= lext.xmin - eps and vsrc.xmax <= lext.xmax + eps
                    and vsrc.ymin >= lext.ymin - eps
                    and vsrc.ymax <= lext.ymax + eps)
        return (view.xmin >= lext.xmin - eps and view.xmax <= lext.xmax + eps
                and view.ymin >= lext.ymin - eps
                and view.ymax <= lext.ymax + eps)
    except Exception:
        exc_note("_raster_covers_full_view @ ggis/render/painter.py:1651")
        return False


_RASTER_FRAME_MAX = 6
_RASTER_FRAME_MARGIN = 0.3
_RASTER_FRAME_SCALE_THRESHOLD = 2.0


def _raster_source_key(layer):
    try:
        from ..io.raster_pyramid import source_key as _sk
        s = layer.source() if hasattr(layer, "source") else None
        if s:
            return _sk(s)
    except Exception:
        exc_note("_raster_source_key @ ggis/render/painter.py:1672")
        pass
    return id(layer)


def _raster_render_plan(layer, settings, base_plan, max_pixels):
    try:
        ext = base_plan.rect_extent
        if ext is None or ext.is_empty():
            return base_plan
        grown = ext.copy().grow(_RASTER_FRAME_MARGIN)
        rs = GgsMapSettings(extent=grown, size=settings.output_size(),
                            destination_crs=settings.destination_crs())
        try:
            rs.set_lod_reference_width(settings.lod_reference_width())
        except Exception:
            exc_note("_raster_render_plan @ ggis/render/painter.py:1691")
            pass
        from .layer_plan import plan_for as _pf
        rp = _pf(layer, rs, mode="layer", max_pixels=max_pixels)
        if rp is None or rp.out_of_data:
            return base_plan
        return rp
    except Exception:
        exc_note("_raster_render_plan @ ggis/render/painter.py:1698")
        return base_plan


def _raster_try_reuse(painter, key, visible_ext, op, settings):
    f = RASTER_FRAME_CACHE.get(key)
    if not f:
        return False
    img = f.get("img")
    world = f.get("world")
    if img is None or world is None:
        return False
    try:
        eff = float(img.width()) / max(float(world.width()), 1e-12)
        cur = (float(settings.output_width())
               / max(float(visible_ext.width()), 1e-12))
        if not (eff / _RASTER_FRAME_SCALE_THRESHOLD <= cur
                <= eff * _RASTER_FRAME_SCALE_THRESHOLD):
            return False
        if not world.contains(visible_ext):
            return False
    except Exception:
        exc_note("_raster_try_reuse @ ggis/render/painter.py:1723")
        return False
    try:
        from PySide6.QtGui import QPainter
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if op < 1.0:
            painter.setOpacity(op)
        painter.drawImage(settings.map_to_pixel_rect(world), img)
        painter.restore()
        return True
    except Exception:
        exc_note("_raster_try_reuse @ ggis/render/painter.py:1734")
        return False


def _raster_store_frame(key, img, world):
    try:
        RASTER_FRAME_CACHE[key] = {"img": img, "world": world}
        while len(RASTER_FRAME_CACHE) > _RASTER_FRAME_MAX:
            RASTER_FRAME_CACHE.popitem(last=False)
    except Exception:
        exc_note("_raster_store_frame @ ggis/render/painter.py:1744")
        pass


class GgsRasterPainter:

    MAX_PIXELS = 2048

    _PIXEL_QUANT = 1.0

    @staticmethod
    def _quantize_bounds(target, settings):
        try:
            ow = float(settings.output_width())
            oh = float(settings.output_height())
            bw = float(target.width())
            bh = float(target.height())
            if bw <= 0 or bh <= 0 or ow <= 0 or oh <= 0:
                raise ZeroDivisionError
            ppu_x = ow / bw
            ppu_y = oh / bh
            qx = GgsRasterPainter._PIXEL_QUANT / ppu_x
            qy = GgsRasterPainter._PIXEL_QUANT / ppu_y
            eps = 1e-9
            return (int(target.xmin / qx + eps) * qx,
                    int(target.ymin / qy + eps) * qy,
                    int(target.xmax / qx + eps) * qx,
                    int(target.ymax / qy + eps) * qy)
        except Exception:
            exc_note("_quantize_bounds @ ggis/render/painter.py:1818")
            return (round(target.xmin, 9), round(target.ymin, 9),
                    round(target.xmax, 9), round(target.ymax, 9))

    def __init__(self):
        self._last_qimage = None
        self._last_rect = None
        self._last_layer_id = None
        self._last_color_key = None
        self._last_covers_full = None
        self._last_view = None

    def invalidate(self, layer_id=None):
        if layer_id is None:
            self._last_qimage = None
            self._last_rect = None
            self._last_layer_id = None
            self._last_color_key = None
            self._last_covers_full = None
            self._last_view = None
            return
        if self._last_layer_id == layer_id:
            self._last_qimage = None
            self._last_rect = None
            self._last_layer_id = None
            self._last_color_key = None
            self._last_covers_full = None
            self._last_view = None

    def _can_blit(self, layer, rect_tuple, color_key, covers_full=False,
                  view=None):
        if self._last_qimage is None or self._last_rect is None:
            return False
        if self._last_layer_id != id(layer):
            return False
        if self._last_color_key != color_key:
            return False
        if not (bool(self._last_covers_full) and bool(covers_full)):
            return False
        if not self._view_is_pure_pan(view):
            return False
        lx, ly, lw, lh = self._last_rect
        x, y, w, h = rect_tuple
        if lw != w or lh != h:
            return False
        dx = x - lx
        dy = y - ly
        return abs(dx) <= max(w, 1) and abs(dy) <= max(h, 1)

    def _view_is_pure_pan(self, view):
        pv = self._last_view
        if pv is None or view is None or pv.is_empty() or view.is_empty():
            return False
        _e = 1e-6
        return (abs(view.width() - pv.width())
                <= _e * max(abs(view.width()), 1.0)
                and abs(view.height() - pv.height())
                <= _e * max(abs(view.height()), 1.0))

    def _draw_from_backbuffer(self, painter, rect_tuple, disp):
        x, y, w, h = rect_tuple
        op = max(0.0, min(1.0, float(disp.opacity)))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                              False)
        if op < 1.0:
            painter.setOpacity(op)
        painter.drawImage(int(round(x)), int(round(y)), self._last_qimage)
        painter.restore()

    def draw(self, painter, layer, settings, opacity=1.0):
        if not settings.is_ready() or layer is None or not layer.is_valid():
            return False
        dst_crs = settings.destination_crs()
        try:
            src_crs = layer.crs()
        except Exception:
            exc_note("draw @ ggis/render/painter.py:1942")
            src_crs = None
        otf = needs_reproject(src_crs, dst_crs)
        from .layer_plan import plan_for as _plan_for
        _plan = _plan_for(layer, settings, mode="layer",
                          max_pixels=self.MAX_PIXELS)
        if _plan is None or _plan.out_of_data:
            return False
        target = _plan.read_extent
        reproj_ext = _plan.reproject_extent or target

        from ggis.core.style import raster_display as rd
        disp = rd.get_display(layer)
        if opacity is not None:
            try:
                disp.opacity = min(1.0, max(0.0, float(opacity)))
            except Exception:
                exc_note("draw @ ggis/render/painter.py:1965")
                pass
        op = max(0.0, min(1.0, float(disp.opacity)))

        _frame_key = (_raster_source_key(layer),
                      rd.display_key(layer, disp),
                      crs_key(dst_crs) if otf else "")
        if _raster_try_reuse(painter, _frame_key, settings.extent(), op,
                              settings):
            return True

        w, h = _plan.out_w, _plan.out_h

        from PySide6.QtCore import QRectF as _QRectF
        rect_obj = _QRectF(*_plan.dst_rect)
        if rect_obj.isEmpty():
            return False
        rect_tuple = (rect_obj.x(), rect_obj.y(),
                      rect_obj.width(), rect_obj.height())
        color_key = (rd.display_key(layer, disp),
                     crs_key(dst_crs) if otf else "",
                     bool(otf))
        _covers = _raster_covers_full_view(layer, settings, dst_crs,
                                           src_crs, otf)
        _view = settings.extent()
        if self._can_blit(layer, rect_tuple, color_key, _covers, _view):
            self._draw_from_backbuffer(painter, rect_tuple, disp)
            self._last_rect = rect_tuple
            return True

        _gplan = _raster_render_plan(layer, settings, _plan, self.MAX_PIXELS)
        if _gplan is not None and not _gplan.out_of_data:
            target = _gplan.read_extent
            reproj_ext = _gplan.reproject_extent or target
            _frame_world = _gplan.rect_extent
            try:
                _ow = float(settings.output_width())
                _oh = float(settings.output_height())
                _vw = max(float(settings.extent().width()), 1e-12)
                _vh = max(float(settings.extent().height()), 1e-12)
                w = int(min(self.MAX_PIXELS,
                            max(1, _frame_world.width() * _ow / _vw)))
                h = int(min(self.MAX_PIXELS,
                            max(1, _frame_world.height() * _oh / _vh)))
            except Exception:
                exc_note("draw @ ggis/render/painter.py:2030")
                w, h = _gplan.out_w, _gplan.out_h
            rect_obj = settings.map_to_pixel_rect(_frame_world)
            if rect_obj.isEmpty():
                return False
            rect_tuple = (rect_obj.x(), rect_obj.y(),
                          rect_obj.width(), rect_obj.height())
        else:
            _gplan = _plan
            _frame_world = _plan.rect_extent
            rect_obj = _QRectF(*_plan.dst_rect)
            if rect_obj.isEmpty():
                return False
            rect_tuple = (rect_obj.x(), rect_obj.y(),
                          rect_obj.width(), rect_obj.height())

        sel_band = int(disp.band or 0)
        _rgb = None
        if not sel_band:
            try:
                rb = getattr(disp, "rgb_bands", None)
                _rgb = [int(b) for b in rb] if rb else None
            except Exception:
                exc_note("draw @ ggis/render/painter.py:2055")
                _rgb = None
        read_bands = [sel_band] if sel_band else _rgb
        try:
            from ..io.raster_pyramid import source_key as _src_key
            _layer_key = _src_key(layer.source())
        except Exception:
            exc_note("draw @ ggis/render/painter.py:2070")
            _layer_key = id(layer)
        q_bounds = self._quantize_bounds(target, settings)
        key = (_layer_key,
               q_bounds[0], q_bounds[1], q_bounds[2], q_bounds[3],
               w, h,
               rd.display_key(layer, disp),
               crs_key(dst_crs) if otf else "")

        def _load():
            arr, valid = None, None
            if not otf:
                try:
                    from ..io import raster_pyramid as _pyr
                    _a, _ok = _pyr.read_overview(
                        layer.source(), target, (w, h), bands=read_bands)
                    if _ok:
                        arr = _a
                except Exception:
                    exc_note("_load @ ggis/render/painter.py:2099")
                    arr = None
            if arr is None and not otf:
                _pyr_ready = True
                try:
                    from ..io import raster_pyramid as _pyr
                    _pyr_ready = _pyr.read_meta(layer.source()) is not None
                except Exception:
                    exc_note("_load @ ggis/render/painter.py:2115")
                    _pyr_ready = False
                if not _pyr_ready:
                    try:
                        from ..io import raster_pyramid as _pyr
                        _src_key = _pyr.source_key(layer.source())
                        _disp_key = rd.display_key(layer, disp)
                        _tkey = (_src_key, _disp_key)

                        def _load_thumb():
                            return _pyr.read_thumbnail(layer.source())

                        arr = THUMB_CACHE.get(_tkey, _load_thumb)
                    except Exception:
                        exc_note("_load @ ggis/render/painter.py:2128")
                        arr = None
                if arr is None and not _pyr_ready and _view_covers_big(target,
                                                                       layer):
                    try:
                        from ..io import raster_pyramid as _pyr
                        arr = _pyr.quicklook(layer.source(), (w, h),
                                             bands=read_bands)
                    except Exception:
                        exc_note("_load @ ggis/render/painter.py:2143")
                        arr = None
            if arr is None:
                from ggis.core.analysis import resampling as _RS
                from ggis.core.app import settings as _S
                _rs = _RS.for_display(
                    layer, reproj_ext if otf else target, w, h,
                    default_in=_S.get("raster_resample_in", _RS.NEAREST),
                    default_out=_S.get("raster_resample_out", _RS.NEAREST))
                if otf:
                    arr, valid, _ext = layer.read_window_reprojected(
                        reproj_ext, (w, h), dst_crs, bands=read_bands,
                        resample=_rs)
                else:
                    arr, _ext2 = layer.read_window(target, (w, h),
                                                   bands=read_bands,
                                                   resample=_rs)
                    valid = None
            if arr is None:
                return None
            try:
                cmap = rd.render_palette(layer, disp)
                hist = None
                try:
                    if str(getattr(disp, "stretch", "") or "") in (
                            rd.STRETCH_HIST_EQ, rd.STRETCH_HIST_MATCH):
                        _b = int(getattr(disp, "band", 0) or 0)
                        if _b:
                            hist = rd.layer_hist_map(layer, disp, band=_b)
                        else:
                            hist = [rd.layer_hist_map(layer, disp, band=i)
                                    for i in (1, 2, 3)]
                except Exception:
                    exc_note("_load @ ggis/render/painter.py:2191")
                    hist = None
                rgba = raster_to_rgba(
                    arr, layer.nodata(), 1.0, display=disp,
                    limits=_limits_for(layer, disp, arr), palette=cmap,
                    valid_mask=valid, hist=hist)
            except Exception:
                exc_note("_load @ ggis/render/painter.py:2197")
                return None
            if rgba is None:
                return None
            hh, ww = rgba.shape[0], rgba.shape[1]
            img = QImage(rgba.data, ww, hh, ww * 4,
                         QImage.Format.Format_RGBA8888)
            return img.copy()

        img = RASTER_WINDOW_CACHE.get(key, _load)
        if img is None:
            return False

        op = max(0.0, min(1.0, float(disp.opacity)))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                              False)
        if op < 1.0:
            painter.setOpacity(op)
        painter.drawImage(rect_obj, img)
        painter.restore()
        try:
            self._last_qimage = img.copy()
            self._last_rect = rect_tuple
            self._last_layer_id = id(layer)
            self._last_color_key = color_key
            self._last_covers_full = _covers
            self._last_view = _view
            _raster_store_frame(_frame_key, img.copy(), _frame_world)
        except Exception:
            exc_note("draw @ ggis/render/painter.py:2233")
            self._last_qimage = None
            self._last_rect = None
            self._last_covers_full = None
        return True


_QUICKLOOK_MIN_COVER = 0.35


def _view_covers_big(target, layer):
    if target is None:
        return False
    try:
        le = layer.extent()
        lw = float(le.width())
        lh = float(le.height())
        if lw <= 0 or lh <= 0:
            return False
        cover = max(float(target.width()) / lw, float(target.height()) / lh)
    except Exception:
        exc_note("_view_covers_big @ ggis/render/painter.py:2261")
        return False
    return cover >= _QUICKLOOK_MIN_COVER


def draw_layer(painter, layer, settings, symbol=None, opacity=None):
    if layer is None or not layer.is_visible() or not layer.is_valid():
        return 0
    if layer.is_raster():
        p = GgsRasterPainter()
        return 1 if p.draw(painter, layer, settings,
                           layer.opacity() if opacity is None else opacity) \
            else 0
    p = GgsVectorPainter()
    return p.draw(painter, layer, settings, symbol)
