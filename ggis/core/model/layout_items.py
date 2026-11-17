# -*- coding: utf-8 -*-

from __future__ import annotations

import collections
import logging
import math
import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QBrush, QColor, QFontMetricsF, QImage,
                           QPainter, QPainterPath, QPen)

from ggis.core.crs import convert_bounds, crs_key, crs_transformer
from ggis.core.app import settings
from ggis.core.crs.extent import GgsRectangle
from ggis.render import vector_print
from ggis.render.fonts import print_font
from ggis.render.labeling import LabelEngine, get_label_style
from .layout_model import (LayoutItem, LayoutError,
                           nice_floor, nice_number)

__all__ = [
    "MapFrame", "Legend", "ScaleBar", "NorthArrow", "GridFrame",
    "TextItem", "ImageItem", "ITEM_TYPES", "create_item", "item_to_dict",
    "item_from_dict", "draw_symbol_swatch", "symbol_size_mm",
]

TEXT_COLOR = "#1A1A1A"
FRAME_COLOR = "#333333"

_log = logging.getLogger("gmagis")

MAP_CACHE_SLOTS = 3

MAP_CACHE_MAX_PX = 12_000_000


def _color(value, default="#000000"):
    c = QColor(value) if value else QColor(default)
    return c if c.isValid() else QColor(default)


def _fmt_num(v, digits=0):
    try:
        f = float(v)
    except Exception:
        _log.exception("silent exception in _fmt_num")
        return str(v)
    if digits <= 0:
        return "%d" % int(round(f))
    return ("%%.%df" % digits) % f


def symbol_size_mm(symbol, kind, fallback=3.0):
    if symbol is None:
        return float(fallback)
    try:
        if kind == "point":
            px = float(symbol.px_size())
        elif kind == "line":
            px = max(1.0, float(symbol.px_width()) * 2.0)
        else:
            px = max(3.0, float(symbol.px_size()) * 0.0 + 6.0)
    except Exception:
        _log.exception("silent exception in symbol_size_mm")
        px = float(fallback) * 96.0 / 25.4
    return max(0.8, px * 25.4 / 96.0)


def draw_symbol_swatch(painter, rect, symbol, kind, ctx=None, outline=None):
    if symbol is None or rect.isEmpty():
        return
    r = QRectF(rect)
    oc = _color(outline or "#8A8A8A")
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        return _paint_swatch(painter, r, symbol, kind, oc)
    finally:
        painter.restore()


def _paint_swatch(painter, r, symbol, kind, oc):
    from ggis.common.styling.symbol_sample import (_dash_pen, _pattern_brush, _pen_ends)
    if kind == "point":
        d = max(2.0, min(r.width(), r.height()) * 0.62)
        cx, cy = r.center().x(), r.center().y()
        painter.setBrush(QBrush(symbol.fill_color()))
        pen = QPen(symbol.stroke_color(),
                   max(0.8, float(symbol.px_width()) * 0.6))
        _dash_pen(symbol, pen)
        painter.setPen(pen)
        painter.drawEllipse(QPointF(cx, cy), d * 0.5, d * 0.5)
        return
    if kind == "line":
        col = symbol.stroke_color()
        if col.alpha() <= 0:
            col = symbol.fill_color()
        y = r.center().y()
        pen = QPen(col, max(0.6, float(symbol.px_width()) * 0.8))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        _pen_ends(symbol, pen)
        _dash_pen(symbol, pen)
        painter.setPen(pen)
        painter.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        return
    br = _pattern_brush(symbol, symbol.fill_color())
    painter.setBrush(QBrush(symbol.fill_color()) if br is None else br)
    ppen = QPen(symbol.stroke_color(), 0.6)
    _pen_ends(symbol, ppen)
    _dash_pen(symbol, ppen)
    painter.setPen(ppen)
    painter.drawRect(r.adjusted(0.5, 1.5, -0.5, -1.5))
    painter.setPen(QPen(oc, 0.5))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(r.adjusted(0.5, 1.5, -0.5, -1.5))


def draw_flat_swatch(painter, rect, color, outline="#8A8A8A"):
    if rect is None or rect.isEmpty():
        return
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(rect).adjusted(0.5, 1.5, -0.5, -1.5)
        painter.setBrush(QBrush(_color(color)))
        painter.setPen(QPen(_color(outline), 0.5))
        painter.drawRect(r)
    except Exception:
        _log.exception("silent exception in draw_flat_swatch")
    finally:
        painter.restore()


def _visible_layers(project, layer_ids=None, visible_only=True):
    if project is None:
        return []
    out = []
    ids = [str(x) for x in (layer_ids or [])]
    for lyr in project.layers():
        if ids and lyr.id() not in ids:
            continue
        if not lyr.is_valid():
            continue
        if visible_only and not lyr.is_visible():
            continue
        out.append(lyr)
    return out


def _metrics(painter, font):
    dev = painter.device()
    try:
        if dev is not None:
            return QFontMetricsF(font, dev)
    except Exception:
        _log.exception("silent exception in _metrics")
    return QFontMetricsF(font)


def _fit_text(painter, text, font, max_w):
    fm = _metrics(painter, font)
    t = str(text or "")
    if fm.horizontalAdvance(t) <= max_w:
        return t
    ell = "…"
    ew = fm.horizontalAdvance(ell)
    lo, hi = 0, len(t)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fm.horizontalAdvance(t[:mid]) + ew <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return t[:lo] + ell if lo > 0 else ell


def _halo_text(painter, rect, flags, text, color, halo="#FFFFFF",
               width_mm=0.18, k=1.0):
    if not text:
        return
    off = max(0.4, float(width_mm) * float(k))
    old = painter.pen()
    hc = _color(halo, "#FFFFFF")
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                   (1, 1), (1, -1), (-1, 1), (-1, -1)):
        painter.setPen(QPen(hc))
        painter.drawText(rect.translated(dx * off, dy * off), flags, text)
    painter.setPen(QPen(_color(color)))
    painter.drawText(rect, flags, text)
    painter.setPen(old)


class MapFrame(LayoutItem):

    type_name = "map_frame"
    label = "地图框"

    def __init__(self, rect_mm=None, layer_ids=None, mode="scale",
                 scale=50000.0, center=None, extent=None, z=0,
                 item_id="", background="#FFFFFF", show_frame=True,
                 frame_width_mm=0.3, visible_only=True, name="",
                 fit_mode="expand", grid=None):
        super().__init__(rect_mm, z, item_id)
        self.layer_ids = [str(x) for x in (layer_ids or [])]
        self.mode = str(mode or "scale")
        self.scale = float(scale or 50000.0)
        self.center = list(center or [0.0, 0.0])
        self.extent = list(extent or [0.0, 0.0, 0.0, 0.0])
        self.background = str(background or "#FFFFFF")
        self.show_frame = bool(show_frame)
        self.frame_width_mm = float(frame_width_mm)
        self.visible_only = bool(visible_only)
        self.fit_mode = str(fit_mode or "expand")
        self.name = str(name or "")
        self.grid = grid
        self.last_extent = None
        self.last_settings = None
        self.last_scale = 0.0
        self._map_cache = {}

    def crs(self, project):
        try:
            c = settings.default_crs()
            if c is not None and c.is_valid():
                return c
        except Exception:
            _log.exception("silent exception in crs")
        for lyr in _visible_layers(project, self.layer_ids):
            try:
                c = lyr.crs()
                if c is not None and c.is_valid():
                    return c
            except Exception:
                _log.exception("silent exception in crs")
                continue
        return None

    def compute_extent(self, project, ctx=None):
        if self.mode == "extent":
            e = GgsRectangle(*[float(x) for x in self.extent])
            if not e.is_empty():
                e.normalize()
                return self._fit_aspect(e)
        if self.mode == "full":
            if project is not None:
                e = project.full_extent(visible_only=self.visible_only,
                                        dst_crs=self.crs(project))
                if not e.is_empty():
                    return self._fit_aspect(e, project)
        if self.mode == "layer":
            e = self._selected_extent(project)
            if e is not None and not e.is_empty():
                return self._fit_aspect(e, project)
        w_mm = float(self.rect_mm.width())
        h_mm = float(self.rect_mm.height())
        scale = max(1e-6, float(self.scale))
        crs = self.crs(project)
        mpu = 1.0
        if crs is not None:
            try:
                mpu = abs(float(crs.meters_per_unit()))
            except Exception:
                _log.exception("silent exception in compute_extent")
                mpu = 1.0
            if mpu <= 0:
                mpu = 1.0
        per_mm = scale / 1000.0
        w_units = w_mm * per_mm
        h_units = h_mm * per_mm
        cx, cy = float(self.center[0]), float(self.center[1])
        e = GgsRectangle(cx - w_units * 0.5, cy - h_units * 0.5,
                         cx + w_units * 0.5, cy + h_units * 0.5)
        if crs is not None and crs.is_geographic() and ctx is not None:
            ctx.warn("地理坐标系下按比例尺定位只能近似（经线收敛）")
        return e

    def _selected_extent(self, project):
        if project is None:
            return None
        dst = self.crs(project)
        r = GgsRectangle()
        got = False
        for lyr in _visible_layers(project, self.layer_ids,
                                   visible_only=False):
            try:
                e = lyr.extent()
            except Exception:
                _log.exception("silent exception in _selected_extent")
                continue
            if e is None or e.is_empty():
                continue
            if dst is not None:
                try:
                    b = convert_bounds((e.xmin, e.ymin, e.xmax, e.ymax),
                                       crs_transformer(lyr.crs(), dst))
                except Exception:
                    _log.exception("silent exception in _selected_extent")
                    b = None
                if b is None:
                    continue
                e = GgsRectangle(b[0], b[1], b[2], b[3])
            r.combine_extent_with(e)
            got = True
        return r if got else None

    def _cos_lat(self, extent, project=None):
        cosk = 1.0
        crs = self.crs(project)
        if crs is not None:
            try:
                if crs.is_geographic():
                    lat = (float(extent.ymin) + float(extent.ymax)) * 0.5
                    cosk = max(0.05, abs(math.cos(math.radians(lat))))
            except Exception:
                _log.exception("silent exception in _cos_lat")
        return cosk

    def _fit_aspect(self, extent, project=None):
        if extent is None or extent.is_empty():
            return extent
        w_mm = float(self.rect_mm.width())
        h_mm = float(self.rect_mm.height())
        if w_mm <= 0 or h_mm <= 0:
            return extent
        target = w_mm / h_mm
        fill = str(getattr(self, "fit_mode", "expand") or "expand") == "fill"
        cur = extent.width() / max(extent.height(), 1e-12)
        if fill:
            tgt = target / self._cos_lat(extent, project)
            if cur <= 0 or abs(cur - tgt) <= 1e-9:
                return extent
            if cur > tgt:
                half = extent.height() * tgt * 0.5
                cx = (extent.xmin + extent.xmax) * 0.5
                extent.xmin, extent.xmax = cx - half, cx + half
            else:
                half = extent.width() / tgt * 0.5
                cy = (extent.ymin + extent.ymax) * 0.5
                extent.ymin, extent.ymax = cy - half, cy + half
            return extent
        if cur <= 0 or abs(cur - target) <= 1e-9:
            return extent
        if cur < target:
            half = extent.height() * target * 0.5
            cx = (extent.xmin + extent.xmax) * 0.5
            extent.xmin, extent.xmax = cx - half, cx + half
        else:
            half = extent.width() / target * 0.5
            cy = (extent.ymin + extent.ymax) * 0.5
            extent.ymin, extent.ymax = cy - half, cy + half
        return extent

    def meters_per_unit(self, project, extent=None):
        crs = self.crs(project)
        mpu = 1.0
        if crs is not None:
            try:
                mpu = abs(float(crs.meters_per_unit())) or 1.0
            except Exception:
                _log.exception("silent exception in meters_per_unit")
                mpu = 1.0
            try:
                if crs.is_geographic():
                    e = extent if extent is not None else self.last_extent
                    lat = 0.0
                    if e is not None and not e.is_empty():
                        lat = (e.ymin + e.ymax) * 0.5
                    mpu *= max(0.05, math.cos(math.radians(lat)))
            except Exception:
                _log.exception("silent exception in meters_per_unit")
        return mpu

    def scale_denominator(self, extent, project):
        w_mm = max(1e-6, float(self.rect_mm.width()))
        if extent is None or extent.is_empty():
            return float(self.scale)
        return (float(extent.width()) * self.meters_per_unit(project, extent)
                / w_mm * 1000.0)

    def visible_layer_count(self, project):
        return len(_visible_layers(project, self.layer_ids))

    def draw(self, painter, ctx):
        from ggis.render.viewport import GgsMapSettings

        rect = ctx.rect_px(self.rect_mm)
        if rect.width() < 1 or rect.height() < 1:
            return
        if self.background:
            painter.fillRect(rect, _color(self.background, "#FFFFFF"))

        project = ctx.project
        extent = self.compute_extent(project, ctx)
        self.last_extent = extent
        if extent is None or extent.is_empty():
            ctx.warn("图框「%s」没有可用范围（工程里没有图层？）"
                     % (self.name or self.id))
            self._draw_empty(painter, ctx, rect)
            self._draw_frame(painter, ctx, rect)
            return

        settings = GgsMapSettings(
            extent=extent,
            size=QSize(max(1, int(round(rect.width()))),
                       max(1, int(round(rect.height())))),
            dpi=float(ctx.dpi))
        try:
            settings.set_destination_crs(self.crs(project))
        except Exception:
            _log.exception("布局：地图框目标坐标系设置失败"
                           "（跨坐标系图层会画不出来）")
        self.last_settings = settings
        self.last_scale = self.scale_denominator(extent, project)

        layers = _visible_layers(project, self.layer_ids, self.visible_only)

        w_px = max(1, int(round(rect.width())))
        h_px = max(1, int(round(rect.height())))
        img = self._layers_image(ctx, settings, layers, w_px, h_px)

        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.x(), rect.y())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if img is not None:
            painter.drawImage(QPointF(0.0, 0.0), img)
        else:
            _log.warning("布局：地图框「%s」图层位图为空（画不出内容）",
                         self.name or self.id)
        painter.restore()

        painter.save()
        painter.setClipRect(rect)
        painter.translate(rect.x(), rect.y())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._draw_labels(painter, ctx, settings, layers, rect)
        painter.restore()

        self._draw_frame(painter, ctx, rect)
        ctx.map_frames.append(self)
        ctx.register_link("map_frame#%d" % (len(ctx.map_frames) - 1), self)

        if self.grid is not None:
            try:
                self.grid.set_rect_mm(QRectF(self.rect_mm))
                self.grid.draw(painter, ctx, frame=self)
            except Exception:
                _log.exception("布局：地图框「%s」的格网绘制失败",
                               self.name or self.id)

    def render_plan(self, project, dpi):
        if project is None or dpi is None or float(dpi) <= 0:
            return None
        try:
            extent = self.compute_extent(project)
        except Exception:
            _log.exception("布局：地图框范围计算失败（跳过子进程渲染）")
            return None
        if extent is None or extent.is_empty():
            return None
        rect = QRectF(self.rect_mm)
        if rect.width() < 1.0 or rect.height() < 1.0:
            return None
        k = float(dpi) / 25.4
        w_px = max(1, int(round(rect.width() * k)))
        h_px = max(1, int(round(rect.height() * k)))
        if w_px * h_px > int(MAP_CACHE_MAX_PX):
            return None
        layers = _visible_layers(project, self.layer_ids, self.visible_only)
        try:
            crs = self.crs(project)
        except Exception:
            _log.exception("silent exception in render_plan")
            crs = None
        try:
            key = self._layers_key(None, extent, layers, w_px, h_px, crs=crs)
        except Exception:
            _log.exception("silent exception in render_plan")
            return None
        return {"key": key, "extent": extent, "w_px": w_px, "h_px": h_px,
                "crs": crs, "dpi": float(dpi)}

    def store_layers_image(self, key, img):
        if img is None or key is None:
            return False
        try:
            c = collections.OrderedDict(self._map_cache or {})
            c[key] = img
            c.move_to_end(key)
            tot = sum(v.width() * v.height() for v in c.values())
            while len(c) > 1 and (len(c) > int(MAP_CACHE_SLOTS)
                                  or tot > int(MAP_CACHE_MAX_PX)):
                _k, v = c.popitem(last=False)
                tot -= v.width() * v.height()
            self._map_cache = c
            return True
        except Exception:
            _log.exception("布局：地图框缓存写入失败")
            return False

    def _layers_key(self, ctx, extent, layers, w_px, h_px, crs=None):
        try:
            ext = tuple(round(float(v), 6) for v in extent.as_tuple())
        except Exception:
            _log.exception("silent exception in _layers_key")
            ext = repr(extent)
        try:
            from .layer import data_version as _dv
            from ggis.render.renderers import render_version as _rv
        except Exception:
            _log.exception("silent exception in _layers_key")
            _dv = _rv = None
        lk = []
        for lyr in layers:
            try:
                lk.append((lyr.id(),
                           int(_dv(lyr)) if _dv is not None else 0,
                           int(_rv(lyr)) if _rv is not None else 0))
            except Exception:
                _log.exception("silent exception in _layers_key")
                lk.append((repr(lyr), -1, -1))
        try:
            ck = str(crs_key(crs) or "")
        except Exception:
            _log.exception("silent exception in _layers_key")
            ck = ""
        return (str(self.mode), str(self.fit_mode), bool(self.visible_only),
                str(self.background), int(w_px), int(h_px), ext, ck, tuple(lk))

    def _layers_image(self, ctx, settings, layers, w_px, h_px):
        key = None
        if w_px * h_px <= int(MAP_CACHE_MAX_PX):
            try:
                key = self._layers_key(ctx, self.last_extent, layers,
                                       w_px, h_px,
                                       crs=settings.destination_crs())
                hit = self._map_cache.get(key)
                if hit is not None:
                    return hit
            except Exception:
                _log.exception("布局：地图框缓存键计算失败（退化为不缓存）")
                key = None
        else:
            self._map_cache = {}
        img = self._paint_layers(ctx, settings, layers, w_px, h_px)
        if img is not None and key is not None:
            try:
                c = collections.OrderedDict(self._map_cache or {})
                c[key] = img
                c.move_to_end(key)
                tot = sum(v.width() * v.height() for v in c.values())
                while len(c) > 1 and (len(c) > int(MAP_CACHE_SLOTS)
                                      or tot > int(MAP_CACHE_MAX_PX)):
                    _k, v = c.popitem(last=False)
                    tot -= v.width() * v.height()
                self._map_cache = c
            except Exception:
                _log.exception("silent exception in _layers_image")
        return img

    def _paint_layers(self, ctx, settings, layers, w_px, h_px):
        try:
            img = QImage(w_px, h_px, QImage.Format.Format_ARGB32)
            img.fill(_color(self.background or "#FFFFFF", "#FFFFFF"))
            p = QPainter(img)
        except Exception:
            _log.exception("布局：地图框位图创建失败")
            return None
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for lyr in layers:
                if not lyr.is_raster():
                    continue
                try:
                    vector_print.draw_layer_vector(p, lyr, settings)
                except Exception as exc:
                    _log.exception("silent exception in _paint_layers")
                    ctx.warn("栅格图层「%s」绘制失败：%s" % (lyr.name(), exc))
            for lyr in layers:
                if not lyr.is_vector():
                    continue
                try:
                    vector_print.draw_layer_vector(p, lyr, settings)
                except Exception as exc:
                    _log.exception("silent exception in _paint_layers")
                    ctx.warn("图层「%s」绘制失败：%s" % (lyr.name(), exc))
        finally:
            p.end()
        return img

    def _draw_empty(self, painter, ctx, rect):
        font = print_font(9.0, family=ctx.font_family)
        painter.setFont(font)
        painter.setPen(QPen(_color("#9A9A9A")))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                         "（图框内没有可显示的图层）")

    def _draw_labels(self, painter, ctx, settings, layers, rect):
        jobs = []
        for lyr in layers:
            if not lyr.is_vector():
                continue
            try:
                st = get_label_style(lyr)
            except Exception:
                _log.exception("silent exception in _draw_labels")
                st = None
            if st is None or not st.enabled or not st.field:
                continue
            jobs.append((lyr, st))
        if not jobs:
            return
        engine = LabelEngine()
        if ctx.font_family:
            try:
                engine.set_font_family(ctx.font_family)
            except Exception:
                _log.exception("silent exception in _draw_labels")
        try:
            engine.set_paint_device(painter.device(), settings.dpi())
        except Exception:
            _log.exception("silent exception in _draw_labels")
        obstacles = []
        k = ctx.dpi / 25.4
        fx, fy = self.rect_mm.x(), self.rect_mm.y()
        for obs in ctx.obstacles_mm:
            try:
                if not obs.intersects(self.rect_mm):
                    continue
                obstacles.append(((obs.x() - fx) * k, (obs.y() - fy) * k,
                                  (obs.right() - fx) * k,
                                  (obs.bottom() - fy) * k))
            except Exception:
                _log.exception("silent exception in _draw_labels")
                continue
        try:
            placed = engine.place(settings, jobs, obstacles=obstacles or None)
        except Exception as exc:
            _log.exception("silent exception in _draw_labels")
            ctx.warn("标注放置失败：%s" % exc)
            return
        if placed:
            try:
                from ggis.render.labeling import draw_labels
                draw_labels(painter, placed, font_family=ctx.font_family)
                painter.setFont(print_font(9.0, family=ctx.font_family))
            except Exception as exc:
                _log.exception("silent exception in _draw_labels")
                ctx.warn("标注绘制失败：%s" % exc)

    def _draw_frame(self, painter, ctx, rect):
        if not self.show_frame:
            return
        w = max(0.1, self.frame_width_mm) * ctx.dpi / 25.4
        painter.setPen(QPen(_color(FRAME_COLOR), w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect.adjusted(w * 0.5, w * 0.5, -w * 0.5, -w * 0.5))

    def to_dict(self):
        d = super().to_dict()
        d.update({"layer_ids": list(self.layer_ids), "mode": self.mode,
                  "scale": self.scale, "center": list(self.center),
                  "extent": list(self.extent),
                  "background": self.background,
                  "show_frame": self.show_frame,
                  "frame_width_mm": self.frame_width_mm,
                  "visible_only": self.visible_only, "name": self.name,
                  "fit_mode": self.fit_mode,
                  "grid": (self.grid.to_dict()
                           if self.grid is not None else None)})
        return d

    @staticmethod
    def _load(d):
        it = MapFrame(layer_ids=d.get("layer_ids") or [],
                      mode=d.get("mode") or "scale",
                      scale=d.get("scale") or 50000.0,
                      center=d.get("center") or [0.0, 0.0],
                      extent=d.get("extent") or [0.0, 0.0, 0.0, 0.0],
                      background=d.get("background") or "#FFFFFF",
                      show_frame=bool(d.get("show_frame", True)),
                      frame_width_mm=d.get("frame_width_mm") or 0.3,
                      visible_only=bool(d.get("visible_only", True)),
                      name=d.get("name") or "",
                      fit_mode=d.get("fit_mode") or "expand")
        it = it._load_base(d)
        raw = d.get("grid")
        if isinstance(raw, dict):
            try:
                g = GridFrame._load(raw)
                g.set_rect_mm(QRectF(it.rect_mm))
                it.grid = g
            except Exception:
                _log.exception("silent exception in _load")
                it.grid = None
        return it

    def preview_text(self):
        if self.mode == "scale":
            return "1:%s" % _fmt_num(self.scale)
        return {"extent": "指定范围", "full": "全图"}.get(self.mode, self.mode)


class Legend(LayoutItem):

    type_name = "legend"
    label = "图例"
    reserves_space = True

    def __init__(self, rect_mm=None, layer_ids=None, title="图例", z=0,
                 item_id="", font_size_pt=8.0, title_size_pt=9.5,
                 columns=1, show_title=True, show_layer_name=True,
                 background="#FFFFFF", text_color=TEXT_COLOR,
                 row_gap_mm=0.8, swatch_w_mm=7.0, indent_mm=3.0,
                 fit_height=True):
        super().__init__(rect_mm, z, item_id)
        self.layer_ids = [str(x) for x in (layer_ids or [])]
        self.title = str(title or "图例")
        self.font_size_pt = float(font_size_pt)
        self.title_size_pt = float(title_size_pt)
        self.columns = max(1, int(columns))
        self.show_title = bool(show_title)
        self.show_layer_name = bool(show_layer_name)
        self.background = str(background or "#FFFFFF")
        self.text_color = str(text_color or TEXT_COLOR)
        self.row_gap_mm = float(row_gap_mm)
        self.swatch_w_mm = float(swatch_w_mm)
        self.indent_mm = float(indent_mm)
        self.fit_height = bool(fit_height)
        self.last_rows = 0

    def entries(self, project):
        from ggis.render.renderers import get_renderer
        out = []
        for lyr in _visible_layers(project, self.layer_ids):
            if lyr.is_raster():
                out.append(("raster", lyr.name(), lyr))
                continue
            try:
                renderer = get_renderer(lyr)
                items = renderer.legend_items(lyr)
            except Exception:
                _log.exception("silent exception in entries")
                items = []
            if not items:
                out.append((lyr.base_kind(), lyr.name(), None))
                continue
            multi = len(items) > 1
            if self.show_layer_name or not multi:
                out.append((lyr.base_kind(), lyr.name(), None))
            for label, sym in items:
                out.append((lyr.base_kind(), str(label), sym))
        return out

    def row_height_px(self, dpi):
        return max(self.font_size_pt, self.font_size_pt * 1.35) * \
            dpi / 72.0 * 1.35

    def needed_height_mm(self, project, scale=1.0):
        rows = len(self.entries(project))
        k = max(0.05, float(scale or 1.0))
        line_mm = max(3.4, self.font_size_pt * k * 1.35 * 25.4 / 72.0 * 1.4)
        per_col = int(math.ceil(rows / float(self.columns)))
        h = per_col * (line_mm + self.row_gap_mm * k)
        if self.show_title and self.title:
            h += self.title_size_pt * k * 1.5 * 25.4 / 72.0 + 1.5
        return h + 3.0

    def draw(self, painter, ctx):
        rect = ctx.rect_px(self.rect_mm)
        if rect.width() < 2 or rect.height() < 2:
            return
        cs = self.content_scale()
        if self.fit_height:
            need = ctx.mm_to_px(self.needed_height_mm(ctx.project, cs))
            if need < rect.height():
                rect.setHeight(need)
        if self.background:
            painter.setBrush(QBrush(_color(self.background, "#FFFFFF")))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)

        pad = ctx.mm_to_px(1.6)
        x0 = rect.x() + pad
        inner_w = rect.width() - pad * 2
        y = rect.y() + pad

        if self.show_title and self.title:
            tf = print_font(self.title_size_pt * cs, bold=True,
                            family=ctx.font_family)
            painter.setFont(tf)
            painter.setPen(QPen(_color(self.text_color)))
            fm = _metrics(painter, tf)
            y += fm.ascent()
            painter.drawText(QPointF(x0, y), _fit_text(painter, self.title,
                                                       tf, inner_w))
            y += fm.descent() + ctx.mm_to_px(1.2)

        rows = self.entries(ctx.project)
        self.last_rows = len(rows)
        if not rows:
            f = print_font(self.font_size_pt * cs, family=ctx.font_family)
            painter.setFont(f)
            painter.setPen(QPen(_color("#9A9A9A")))
            painter.drawText(QRectF(rect.x(), y, rect.width(),
                                    rect.bottom() - y),
                             Qt.AlignmentFlag.AlignCenter, "（无可见图层）")
            return

        f = print_font(self.font_size_pt * cs, family=ctx.font_family)
        painter.setFont(f)
        fm = _metrics(painter, f)
        line_mm = max(3.4, self.font_size_pt * cs * 1.35 * 25.4 / 72.0 * 1.4)
        line_px = ctx.mm_to_px(line_mm)
        gap = ctx.mm_to_px(self.row_gap_mm * cs)
        sw = ctx.mm_to_px(self.swatch_w_mm * cs)
        n_col = max(1, int(self.columns))
        per_col = int(math.ceil(len(rows) / float(n_col)))
        col_w = inner_w / n_col
        bottom = rect.bottom() - pad

        for i, (kind, label, sym) in enumerate(rows):
            c = min(n_col - 1, i // per_col)
            r = i % per_col
            cy_top = y + r * (line_px + gap)
            if cy_top + line_px > bottom + 1:
                continue
            cx = x0 + c * col_w
            show_swatch = sym is not None or kind == "raster"
            if show_swatch:
                srect = QRectF(cx, cy_top + line_px * 0.18, sw,
                               line_px * 0.64)
                if kind == "raster":
                    self._swatch_raster(painter, srect, sym)
                else:
                    draw_symbol_swatch(painter, srect, sym, kind, ctx)
            tx = cx + (sw + ctx.mm_to_px(1.2) if show_swatch else 0.0)
            avail = cx + col_w - tx - ctx.mm_to_px(0.5)
            if avail <= 1:
                continue
            bold = self.show_layer_name and sym is None
            ff = print_font(self.font_size_pt, bold=bold,
                            family=ctx.font_family)
            painter.setFont(ff)
            painter.setPen(QPen(_color(self.text_color)))
            fm2 = _metrics(painter, ff)
            base = cy_top + (line_px + fm2.ascent() - fm2.descent()) * 0.5
            painter.drawText(QPointF(tx, base),
                             _fit_text(painter, label, ff, avail))
        painter.setFont(print_font(9.0, family=ctx.font_family))

    def _swatch_raster(self, painter, rect, layer=None):
        if layer is not None:
            try:
                from ggis.core.style import raster_display as rd
                d = rd.get_display(layer)
                keys, cmap = rd.legend_palette(layer, d)
                if keys and cmap:
                    n = max(1, len(keys))
                    bw = float(rect.width()) / float(n)
                    for i, kk in enumerate(keys):
                        c = cmap.get(kk)
                        if not c:
                            continue
                        r, g, b = int(c[0]), int(c[1]), int(c[2])
                        a = int(c[3]) if len(c) > 3 else 255
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QBrush(QColor(r, g, b, a)))
                        painter.drawRect(QRectF(rect.x() + i * bw, rect.y(),
                                                bw + 0.6, rect.height()))
                    return
            except Exception:
                _log.exception("silent exception in _swatch_raster")
        painter.setBrush(QBrush(_color("#8A8A8A")))
        painter.setPen(QPen(_color("#5A5A5A"), 0.5))
        painter.drawRect(rect)

    def to_dict(self):
        d = super().to_dict()
        d.update({"layer_ids": list(self.layer_ids), "title": self.title,
                  "font_size_pt": self.font_size_pt,
                  "title_size_pt": self.title_size_pt,
                  "columns": self.columns,
                  "show_title": self.show_title,
                  "show_layer_name": self.show_layer_name,
                  "background": self.background,
                  "text_color": self.text_color,
                  "row_gap_mm": self.row_gap_mm,
                  "swatch_w_mm": self.swatch_w_mm,
                  "indent_mm": self.indent_mm,
                  "fit_height": self.fit_height})
        return d

    @staticmethod
    def _load(d):
        it = Legend(layer_ids=d.get("layer_ids") or [],
                    title=d.get("title") or "图例",
                    font_size_pt=d.get("font_size_pt") or 8.0,
                    title_size_pt=d.get("title_size_pt") or 9.5,
                    columns=d.get("columns") or 1,
                    show_title=bool(d.get("show_title", True)),
                    show_layer_name=bool(d.get("show_layer_name", True)),
                    background=d.get("background") or "#FFFFFF",
                    text_color=d.get("text_color") or TEXT_COLOR,
                    row_gap_mm=d.get("row_gap_mm") or 0.8,
                    swatch_w_mm=d.get("swatch_w_mm") or 7.0,
                    indent_mm=d.get("indent_mm") or 3.0,
                    fit_height=bool(d.get("fit_height", True)))
        return it._load_base(d)

    def preview_text(self):
        return "图例（%d 层）" % len(self.layer_ids) if self.layer_ids \
            else "图例（全部可见图层）"


class ScaleBar(LayoutItem):

    type_name = "scale_bar"
    label = "比例尺"
    reserves_space = True
    fixed_ratio = True

    UNITS = ("map", "metric", "imperial")

    def __init__(self, rect_mm=None, link="", units="map", divisions=4,
                 style="double", z=0, item_id="", font_size_pt=7.5,
                 bar_height_mm=2.2, show_units=True, show_scale_text=True,
                 text_color=TEXT_COLOR, fill_a="#FFFFFF", fill_b="#2B2B2B"):
        super().__init__(rect_mm, z, item_id)
        self.link = str(link or "")
        self.units = str(units or "map")
        self.divisions = max(1, int(divisions))
        self.style = str(style or "double")
        self.font_size_pt = float(font_size_pt)
        self.bar_height_mm = float(bar_height_mm)
        self.show_units = bool(show_units)
        self.show_scale_text = bool(show_scale_text)
        self.text_color = str(text_color or TEXT_COLOR)
        self.fill_a = str(fill_a or "#FFFFFF")
        self.fill_b = str(fill_b or "#2B2B2B")

    def units_per_mm(self, frame, project):
        if frame is None:
            return 0.0
        denom = float(getattr(frame, "last_scale", 0.0) or 0.0)
        if frame.mode == "scale":
            denom = float(frame.scale)
        if denom <= 0:
            return 0.0
        meters = denom / 1000.0
        if self.units == "imperial":
            return meters / 0.3048
        if self.units == "metric":
            return meters
        mpu = 1.0
        try:
            mpu = float(frame.meters_per_unit(project,
                                              frame.last_extent)) or 1.0
        except Exception:
            _log.exception("silent exception in units_per_mm")
            mpu = 1.0
        return meters / abs(mpu)

    def unit_label(self, project, frame=None):
        if self.units == "metric":
            return "m"
        if self.units == "imperial":
            return "ft"
        crs = frame.crs(project) if frame is not None else None
        if crs is not None:
            try:
                u = crs.unit_abbreviation()
                if u:
                    return u
            except Exception:
                _log.exception("silent exception in unit_label")
        return ""

    def layout_of(self, frame, project, width_mm):
        upm = self.units_per_mm(frame, project)
        if upm <= 0:
            return 0.0, 0.0, 0.0, ""
        target = max(1.0, float(width_mm)) * upm
        total = nice_floor(target)
        if total <= 0:
            total = target
        return (total / upm, total, total / self.divisions,
                self.unit_label(project, frame))

    def _measure(self, painter, ctx, rect, frame, cs):
        k = ctx.dpi / 25.4
        font = print_font(self.font_size_pt * cs, family=ctx.font_family)
        painter.setFont(font)
        fm = _metrics(painter, font)
        text_h = fm.height()
        gap = k * 0.8
        unit = self.unit_label(ctx.project, frame)
        unit_w = (fm.horizontalAdvance(unit) + gap) if self.show_units else 0.0
        upm = self.units_per_mm(frame, ctx.project)
        est_v = max(1.0, self.rect_mm.width()) * upm if upm > 0 else 1.0
        est_lab_w = fm.horizontalAdvance(self._num(est_v, unit))
        pad_mm = (est_lab_w + unit_w) / k
        bar_room_mm = max(1.0, self.rect_mm.width() - pad_mm)
        total_mm, total_v, seg_v, unit = self.layout_of(
            frame, ctx.project, bar_room_mm)
        if total_mm <= 0:
            return None
        bar_h = self.bar_height_mm * cs * k
        lead = (text_h * 1.05) if self.show_scale_text else 0.0
        content_h = lead + bar_h + text_h
        top = rect.y() + max(0.0, (rect.height() - content_h) * 0.5)
        y0 = top + lead
        bar_w = total_mm * k
        x0 = rect.x()
        seg = bar_w / self.divisions
        all_lab = [self._num(seg_v * i, unit)
                   for i in range(self.divisions + 1)]
        max_lab = max([fm.horizontalAdvance(t) for t in all_lab] or [0.0])
        step_k = 1
        if seg > 0 and max_lab > 0:
            step_k = max(1, int(math.ceil(max_lab * 1.25 / seg)))
        idxs = list(range(0, self.divisions + 1, step_k))
        if idxs[-1] != self.divisions:
            idxs.append(self.divisions)
        if len(idxs) > 1:
            last = idxs[-1]
            need = fm.horizontalAdvance(all_lab[last]) + max_lab * 0.6
            if (last - idxs[-2]) * seg < need:
                idxs.pop(-2)
        return {"k": k, "font": font, "fm": fm, "text_h": text_h, "gap": gap,
                "unit": unit, "unit_w": unit_w, "total_mm": total_mm,
                "total_v": total_v, "seg_v": seg_v, "bar_h": bar_h,
                "lead": lead, "top": top, "content_h": content_h,
                "y0": y0, "bar_w": bar_w, "x0": x0, "seg": seg,
                "all_lab": all_lab, "max_lab": max_lab, "idxs": idxs}

    def _fit_factor(self, m):
        k = max(1e-9, float(m["k"]))
        f = 1.0
        seg_mm = m["seg"] / k
        lab_mm = m["max_lab"] / k
        if lab_mm > 1e-6 and seg_mm > 1e-6:
            f = min(f, (seg_mm * 0.78) / lab_mm)
        need_h_mm = (m["lead"] + m["bar_h"] + m["text_h"]) / k
        h_mm = max(1e-6, float(self.rect_mm.height()))
        if need_h_mm > 1e-6:
            f = min(f, h_mm / need_h_mm)
        return max(0.05, min(1.0, f))

    def draw(self, painter, ctx):
        rect = ctx.rect_px(self.rect_mm)
        if rect.width() < 4 or rect.height() < 2:
            return
        frame = ctx.linked(self.link) or ctx.layout.resolve_link(self.link)

        cs = self.content_scale()
        m = self._measure(painter, ctx, rect, frame, cs)
        if cs > 1.0:
            for _ in range(3):
                if m is None:
                    break
                f = self._fit_factor(m)
                if f >= 0.995:
                    break
                cs *= f
                m2 = self._measure(painter, ctx, rect, frame, cs)
                if m2 is None:
                    break
                m = m2
        if m is None:
            ctx.warn("比例尺无法定位地图框或地图范围，已跳过")
            return
        k = m["k"]
        fm = m["fm"]
        text_h = m["text_h"]
        gap = m["gap"]
        unit = m["unit"]
        unit_w = m["unit_w"]
        bar_h = m["bar_h"]
        y0 = m["y0"]
        bar_w = m["bar_w"]
        x0 = m["x0"]
        seg = m["seg"]
        all_lab = m["all_lab"]
        idxs = m["idxs"]
        painter.setFont(m["font"])

        pen = QPen(_color("#2B2B2B"), max(0.5, k * 0.15))
        for i in range(self.divisions):
            r = QRectF(x0 + i * seg, y0, seg, bar_h)
            painter.setBrush(QBrush(_color(self.fill_b if i % 2 == 0
                                           else self.fill_a)))
            painter.setPen(pen)
            painter.drawRect(r)

        painter.setPen(QPen(_color(self.text_color)))
        box_l = rect.x()
        box_r = rect.x() + rect.width()
        for i in idxs:
            cx = x0 + i * seg
            t = all_lab[i]
            if i == self.divisions:
                w = fm.horizontalAdvance(t)
                x = min(cx - w, box_r - w)
            else:
                w = max(fm.horizontalAdvance(t), seg)
                x = max(box_l, min(cx - w * 0.5, box_r - w))
            _halo_text(painter, QRectF(x, y0 + bar_h, w, text_h),
                       Qt.AlignmentFlag.AlignHCenter
                       | Qt.AlignmentFlag.AlignTop,
                       t, self.text_color, k=k)

        if self.show_units and unit:
            _halo_text(painter,
                       QRectF(x0 + bar_w + gap, y0 + bar_h * 0.5, unit_w,
                              text_h),
                       Qt.AlignmentFlag.AlignLeft
                       | Qt.AlignmentFlag.AlignVCenter,
                       unit, self.text_color, k=k)

        if self.show_scale_text:
            _halo_text(painter,
                       QRectF(rect.x(), m["top"], rect.width(), text_h),
                       Qt.AlignmentFlag.AlignHCenter
                       | Qt.AlignmentFlag.AlignTop,
                       self._scale_text(frame, ctx), self.text_color, k=k)

    def _scale_text(self, frame, ctx):
        d = 0.0
        try:
            d = float(getattr(frame, "last_scale", 0.0))
        except Exception:
            _log.exception("silent exception in _scale_text")
            d = 0.0
        if d <= 0 and frame is not None and frame.mode == "scale":
            d = float(frame.scale)
        if d <= 0:
            return ""
        return "1:%s" % ("{:,.0f}".format(d),)

    @staticmethod
    def _num(v, unit):
        if unit == "ft" or v >= 100:
            return _fmt_num(v)
        return _fmt_num(v, 0 if abs(v - round(v)) < 1e-6 else 2)

    def to_dict(self):
        d = super().to_dict()
        d.update({"link": self.link, "units": self.units,
                  "divisions": self.divisions, "style": self.style,
                  "font_size_pt": self.font_size_pt,
                  "bar_height_mm": self.bar_height_mm,
                  "show_units": self.show_units,
                  "show_scale_text": self.show_scale_text,
                  "text_color": self.text_color, "fill_a": self.fill_a,
                  "fill_b": self.fill_b})
        return d

    @staticmethod
    def _load(d):
        it = ScaleBar(link=d.get("link") or "",
                      units=d.get("units") or "map",
                      divisions=d.get("divisions") or 4,
                      style=d.get("style") or "double",
                      font_size_pt=d.get("font_size_pt") or 7.5,
                      bar_height_mm=d.get("bar_height_mm") or 2.2,
                      show_units=bool(d.get("show_units", True)),
                      show_scale_text=bool(d.get("show_scale_text", True)),
                      text_color=d.get("text_color") or TEXT_COLOR,
                      fill_a=d.get("fill_a") or "#FFFFFF",
                      fill_b=d.get("fill_b") or "#2B2B2B")
        return it._load_base(d)

    def preview_text(self):
        return "比例尺 · %s" % {"map": "图面单位", "metric": "公制",
                                "imperial": "英制"}.get(self.units,
                                                        self.units)


class NorthArrow(LayoutItem):

    type_name = "north_arrow"
    label = "指北针"
    reserves_space = True
    fixed_ratio = True

    STYLES = ("arrow", "compass", "rose", "letter")

    def __init__(self, rect_mm=None, style="compass", angle=0.0, z=0,
                 item_id="", color="#333333", fill="#FFFFFF",
                 label_size_pt=10.0, show_label=True):
        super().__init__(rect_mm, z, item_id)
        self.style = str(style or "compass")
        self.angle = float(angle or 0.0)
        self.color = str(color or "#333333")
        self.fill = str(fill or "#FFFFFF")
        self.label_size_pt = float(label_size_pt)
        self.show_label = bool(show_label)

    def draw(self, painter, ctx):
        rect = ctx.rect_px(self.rect_mm)
        if rect.width() < 3 or rect.height() < 3:
            return
        r = QRectF(rect)
        cs = self.content_scale()
        lab_h = 0.0
        if self.show_label:
            f = print_font(self.label_size_pt * cs, bold=True,
                           family=ctx.font_family)
            painter.setFont(f)
            fm = _metrics(painter, f)
            lab_h = fm.height() * 1.35
            r.setBottom(r.bottom() - lab_h)
        side = min(r.width(), r.height()) * 0.78
        size = max(2.0, side)
        cx = r.x() + r.width() * 0.5
        cy = r.y() + r.height() * 0.5
        s = size / 100.0
        c = _color(self.color, "#333333")
        light = _color(self.fill, "#FFFFFF")
        stroke = max(1.0, 100.0 / max(size, 1.0))

        def needle(ang_deg, length, half_w):
            a = math.radians(ang_deg)
            a1 = a - math.pi / 2
            p = QPainterPath()
            p.moveTo(0, 0)
            p.lineTo(length * math.cos(a), length * math.sin(a))
            p.lineTo(half_w * math.cos(a1), half_w * math.sin(a1))
            p.closeSubpath()
            return p

        painter.save()
        painter.translate(cx, cy)
        if self.angle:
            painter.rotate(float(self.angle))
        painter.scale(s, s)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.style == "letter":
            path = QPainterPath()
            path.moveTo(0, -50)
            path.lineTo(22, 34)
            path.lineTo(-22, 34)
            path.closeSubpath()
            painter.setPen(QPen(c, stroke))
            painter.setBrush(QBrush(c))
            painter.drawPath(path)
        elif self.style in ("compass", "rose"):
            n = 4 if self.style == "compass" else 8
            for i in range(n):
                a = -90 + i * (360.0 / n)
                L = 50.0 if i % 2 == 0 else (32.0 if n == 8 else 34.0)
                w = 13.0 if i % 2 == 0 else 8.0
                painter.setPen(QPen(c, stroke))
                painter.setBrush(QBrush(c if i % 2 == 0 else light))
                painter.drawPath(needle(a, L, w))
            r = 7.0
            painter.setPen(QPen(c, stroke))
            painter.setBrush(QBrush(light))
            painter.drawEllipse(QPointF(0, 0), r, r)
        else:
            painter.setPen(QPen(c, stroke))
            painter.setBrush(QBrush(c))
            painter.drawPath(needle(-90, 50, 15))
            painter.setBrush(QBrush(light))
            painter.drawPath(needle(90, 38, 12))
        painter.restore()

        if self.show_label:
            f = print_font(self.label_size_pt * cs, bold=True,
                           family=ctx.font_family)
            painter.setFont(f)
            painter.setPen(QPen(_color(self.color, "#333333")))
            painter.drawText(QRectF(rect.x(), rect.bottom() - lab_h,
                                    rect.width(), lab_h),
                             Qt.AlignmentFlag.AlignHCenter
                             | Qt.AlignmentFlag.AlignVCenter, "北")

    def to_dict(self):
        d = super().to_dict()
        d.update({"style": self.style, "angle": self.angle,
                  "color": self.color, "fill": self.fill,
                  "label_size_pt": self.label_size_pt,
                  "show_label": self.show_label})
        return d

    @staticmethod
    def _load(d):
        it = NorthArrow(style=d.get("style") or "compass",
                        angle=d.get("angle") or 0.0,
                        color=d.get("color") or "#333333",
                        fill=d.get("fill") or "#FFFFFF",
                        label_size_pt=d.get("label_size_pt") or 10.0,
                        show_label=bool(d.get("show_label", True)))
        return it._load_base(d)

    def preview_text(self):
        return "指北针 · %s" % {"arrow": "箭头", "compass": "罗盘",
                                "rose": "玫瑰", "letter": "北字"}.get(
                                    self.style, self.style)


class GridFrame(LayoutItem):

    type_name = "grid"
    label = "格网"

    def __init__(self, rect_mm=None, link="", kind="grid",
                 interval=1000.0, interval_deg=0.01, z=0, item_id="",
                 show_labels=True, font_size_pt=6.5, color="#7A7A7A",
                 width_mm=0.12, label_color=TEXT_COLOR,
                 label_margin_mm=0.6):
        super().__init__(rect_mm, z, item_id)
        self.link = str(link or "")
        self.kind = str(kind or "grid")
        self.interval = float(interval or 1000.0)
        self.interval_deg = float(interval_deg or 0.01)
        self.show_labels = bool(show_labels)
        self.font_size_pt = float(font_size_pt)
        self.color = str(color or "#7A7A7A")
        self.width_mm = float(width_mm)
        self.label_color = str(label_color or TEXT_COLOR)
        self.label_margin_mm = float(label_margin_mm)

    def _grid_values(self, extent, frame, project):
        if extent is None or extent.is_empty():
            return [], [], None, None, 1, 1
        w_mm = max(1e-6, float(self.rect_mm.width()))
        h_mm = max(1e-6, float(self.rect_mm.height()))
        min_line = 5.0
        min_label = 20.0

        if self.kind == "graticule":
            deg = max(1e-9, float(self.interval_deg))
            span_x = max(1e-9, extent.width())
            span_y = max(1e-9, extent.height())
            need_x = min_line / w_mm * span_x
            need_y = min_line / h_mm * span_y
            kx = max(1, int(math.ceil(need_x / deg)))
            ky = max(1, int(math.ceil(need_y / deg)))
            xs = self._range(extent.xmin, extent.xmax, deg * kx)
            ys = self._range(extent.ymin, extent.ymax, deg * ky)
            lx = max(1, int(math.ceil(min_label / w_mm * span_x
                                     / (deg * kx))))
            ly = max(1, int(math.ceil(min_label / h_mm * span_y
                                     / (deg * ky))))
            fmt = self._deg_label
            return xs, ys, fmt, fmt, lx, ly

        span_x = max(1e-12, extent.width())
        span_y = max(1e-12, extent.height())
        sx = float(self.interval or 0.0)
        if sx <= 0 or sx > span_x * 0.5:
            sx = nice_number(span_x / max(2.0, w_mm / 25.0))
        sy = sx
        if sy <= 0 or sy > span_y * 0.5:
            sy = nice_number(span_y / max(2.0, h_mm / 25.0))
        sx = max(sx, min_line / w_mm * span_x)
        sy = max(sy, min_line / h_mm * span_y)
        xs = self._range(extent.xmin, extent.xmax, sx)
        ys = self._range(extent.ymin, extent.ymax, sy)
        lx = max(1, int(math.ceil(min_label / w_mm * span_x / sx)))
        ly = max(1, int(math.ceil(min_label / h_mm * span_y / sy)))
        crs = frame.crs(project) if frame is not None else None
        fmt = (self._deg_label if (crs is not None and crs.is_geographic())
               else _fmt_num)
        return xs, ys, fmt, fmt, lx, ly

    @staticmethod
    def _range(a0, a1, step):
        lo, hi = min(a0, a1), max(a0, a1)
        v = math.ceil(lo / step) * step
        out = []
        while v <= hi + step * 1e-6 and len(out) < 5000:
            out.append(v)
            v += step
        return out

    @staticmethod
    def _deg_label(v):
        t = _fmt_num(abs(float(v)), 4).rstrip("0").rstrip(".")
        return "%s°" % (t or "0")

    def draw(self, painter, ctx, frame=None):
        rect = ctx.rect_px(self.rect_mm)
        if rect.width() < 4 or rect.height() < 4:
            return
        frame = frame or ctx.linked(self.link) \
            or ctx.layout.resolve_link(self.link)
        if frame is None or frame.last_extent is None:
            ctx.warn("格网没有可链接的地图框，已跳过")
            return
        extent = frame.last_extent
        if extent.is_empty():
            return
        xs, ys, fx, fy, lx, ly = self._grid_values(extent, frame,
                                                   ctx.project)
        if not xs and not ys:
            return
        if fx is None or fy is None:
            return

        k = ctx.dpi / 25.4
        w = max(0.05, self.width_mm) * k
        painter.setPen(QPen(_color(self.color, "#7A7A7A"), w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        sx = rect.width() / max(extent.width(), 1e-12)
        sy = rect.height() / max(extent.height(), 1e-12)
        for x in xs:
            px = rect.x() + (x - extent.xmin) * sx
            if rect.x() - 0.5 <= px <= rect.right() + 0.5:
                painter.drawLine(QPointF(px, rect.y()),
                                 QPointF(px, rect.bottom()))
        for y in ys:
            py = rect.y() + (extent.ymax - y) * sy
            if rect.y() - 0.5 <= py <= rect.bottom() + 0.5:
                painter.drawLine(QPointF(rect.x(), py),
                                 QPointF(rect.right(), py))

        if self.show_labels:
            f = print_font(self.font_size_pt, family=ctx.font_family)
            painter.setFont(f)
            fm = _metrics(painter, f)
            m = max(0.2, self.label_margin_mm) * k
            painter.setPen(QPen(_color(self.label_color)))
            for i, x in enumerate(xs):
                if i % lx:
                    continue
                px = rect.x() + (x - extent.xmin) * sx
                if px < rect.x() - 0.5 or px > rect.right() + 0.5:
                    continue
                painter.drawText(QRectF(px - 200, rect.bottom() + m,
                                        400, fm.height()),
                                 Qt.AlignmentFlag.AlignHCenter
                                 | Qt.AlignmentFlag.AlignTop, fx(x))
            for i, y in enumerate(ys):
                if i % ly:
                    continue
                py = rect.y() + (extent.ymax - y) * sy
                if py < rect.y() - 0.5 or py > rect.bottom() + 0.5:
                    continue
                painter.drawText(QRectF(rect.x() - 200 - m, py -
                                        fm.height() * 0.5, 200,
                                        fm.height()),
                                 Qt.AlignmentFlag.AlignRight
                                 | Qt.AlignmentFlag.AlignVCenter, fy(y))
            painter.setFont(print_font(9.0, family=ctx.font_family))

    def to_dict(self):
        d = super().to_dict()
        d.update({"link": self.link, "kind": self.kind,
                  "interval": self.interval,
                  "interval_deg": self.interval_deg,
                  "show_labels": self.show_labels,
                  "font_size_pt": self.font_size_pt, "color": self.color,
                  "width_mm": self.width_mm,
                  "label_color": self.label_color,
                  "label_margin_mm": self.label_margin_mm})
        return d

    @staticmethod
    def _load(d):
        it = GridFrame(link=d.get("link") or "",
                       kind=d.get("kind") or "grid",
                       interval=d.get("interval") or 1000.0,
                       interval_deg=d.get("interval_deg") or 0.01,
                       show_labels=bool(d.get("show_labels", True)),
                       font_size_pt=d.get("font_size_pt") or 6.5,
                       color=d.get("color") or "#7A7A7A",
                       width_mm=d.get("width_mm") or 0.12,
                       label_color=d.get("label_color") or TEXT_COLOR,
                       label_margin_mm=d.get("label_margin_mm") or 0.6)
        return it._load_base(d)

    def preview_text(self):
        return {"grid": "方里网", "graticule": "经纬网"}.get(self.kind,
                                                            self.kind)


class TextItem(LayoutItem):

    type_name = "text"
    label = "文字"
    reserves_space = True

    ALIGNS = ("left", "center", "right")

    def __init__(self, rect_mm=None, content="", z=0, item_id="",
                 font_size_pt=14.0, bold=False, italic=False,
                 color=TEXT_COLOR, align="center", valign="middle",
                 background="", border=False, word_wrap=True,
                 font_family=""):
        super().__init__(rect_mm, z, item_id)
        self.content = str(content or "")
        self.font_size_pt = float(font_size_pt)
        self.bold = bool(bold)
        self.italic = bool(italic)
        self.font_family = str(font_family or "")
        self.color = str(color or TEXT_COLOR)
        self.align = str(align or "center")
        self.valign = str(valign or "middle")
        self.background = str(background or "")
        self.border = bool(border)
        self.word_wrap = bool(word_wrap)

    def _flags(self):
        h = {"left": Qt.AlignmentFlag.AlignLeft,
             "center": Qt.AlignmentFlag.AlignHCenter,
             "right": Qt.AlignmentFlag.AlignRight}.get(
                 self.align, Qt.AlignmentFlag.AlignHCenter)
        v = {"top": Qt.AlignmentFlag.AlignTop,
             "middle": Qt.AlignmentFlag.AlignVCenter,
             "bottom": Qt.AlignmentFlag.AlignBottom}.get(
                 self.valign, Qt.AlignmentFlag.AlignVCenter)
        return h | v

    def draw(self, painter, ctx):
        rect = ctx.rect_px(self.rect_mm)
        if rect.width() < 1 or rect.height() < 1:
            return
        if self.background:
            painter.fillRect(rect, _color(self.background, "#FFFFFF"))
        if self.border:
            painter.setPen(QPen(_color("#4A4A4A"), max(0.4,
                                                       ctx.dpi / 400.0)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect)
        f = print_font(self.font_size_pt * self.content_scale(), bold=self.bold,
                       italic=self.italic,
                       family=(self.font_family or ctx.font_family))
        painter.setFont(f)
        painter.setPen(QPen(_color(self.color)))
        area = QRectF(rect).adjusted(ctx.mm_to_px(0.6),
                                     ctx.mm_to_px(0.4),
                                     -ctx.mm_to_px(0.6),
                                     -ctx.mm_to_px(0.4))
        text = self.content
        if not self.word_wrap:
            text = _fit_text(painter, text, area.width())
        painter.drawText(area, self._flags(), text)
        painter.setFont(print_font(9.0, family=ctx.font_family))

    def to_dict(self):
        d = super().to_dict()
        d.update({"content": self.content,
                  "font_size_pt": self.font_size_pt, "bold": self.bold,
                  "italic": self.italic, "color": self.color,
                  "font_family": self.font_family,
                  "align": self.align, "valign": self.valign,
                  "background": self.background, "border": self.border,
                  "word_wrap": self.word_wrap})
        return d

    @staticmethod
    def _load(d):
        it = TextItem(content=d.get("content") or "",
                      font_size_pt=d.get("font_size_pt") or 14.0,
                      bold=bool(d.get("bold", False)),
                      italic=bool(d.get("italic", False)),
                      color=d.get("color") or TEXT_COLOR,
                      align=d.get("align") or "center",
                      valign=d.get("valign") or "middle",
                      background=d.get("background") or "",
                      border=bool(d.get("border", False)),
                      word_wrap=bool(d.get("word_wrap", True)),
                      font_family=d.get("font_family") or "")
        return it._load_base(d)

    def preview_text(self):
        t = self.content.replace("\n", " ")
        return t[:18] + ("…" if len(t) > 18 else "")


class ImageItem(LayoutItem):

    type_name = "image"
    label = "图片"
    reserves_space = True

    @property
    def fixed_ratio(self):
        return bool(getattr(self, "keep_aspect", True))

    def __init__(self, rect_mm=None, path="", z=0, item_id="",
                 keep_aspect=True, opacity=1.0):
        super().__init__(rect_mm, z, item_id)
        self.path = str(path or "")
        self.keep_aspect = bool(keep_aspect)
        self.opacity = float(opacity)
        self._img = None
        self._img_path = None

    def image(self):
        if not self.path or not os.path.isfile(self.path):
            return None
        if self._img is not None and self._img_path == self.path:
            return self._img
        img = QImage(self.path)
        if img.isNull():
            return None
        self._img = img
        self._img_path = self.path
        return img

    def draw(self, painter, ctx):
        rect = ctx.rect_px(self.rect_mm)
        img = self.image()
        if img is None:
            if self.path:
                ctx.warn("图片「%s」读不出来" % os.path.basename(self.path))
            return
        target = QRectF(rect)
        if self.keep_aspect:
            iw, ih = img.width(), img.height()
            if iw > 0 and ih > 0:
                k = min(target.width() / iw, target.height() / ih)
                w, h = iw * k, ih * k
                target = QRectF(target.center().x() - w * 0.5,
                                target.center().y() - h * 0.5, w, h)
        painter.save()
        if self.opacity < 1.0:
            painter.setOpacity(max(0.0, min(1.0, self.opacity)))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,
                             True)
        painter.drawImage(target, img)
        painter.restore()

    def to_dict(self):
        d = super().to_dict()
        d.update({"path": self.path, "keep_aspect": self.keep_aspect,
                  "opacity": self.opacity})
        return d

    @staticmethod
    def _load(d):
        it = ImageItem(path=d.get("path") or "",
                       keep_aspect=bool(d.get("keep_aspect", True)),
                       opacity=d.get("opacity") or 1.0)
        return it._load_base(d)

    def preview_text(self):
        return os.path.basename(self.path) if self.path else "（未指定图片）"


ITEM_TYPES = {
    "map_frame": (MapFrame, "地图框"),
    "legend": (Legend, "图例"),
    "scale_bar": (ScaleBar, "比例尺"),
    "north_arrow": (NorthArrow, "指北针"),
    "grid": (GridFrame, "格网"),
    "text": (TextItem, "文字"),
    "image": (ImageItem, "图片"),
}

DEFAULT_SIZES = {
    "map_frame": (120.0, 90.0),
    "legend": (45.0, 60.0),
    "scale_bar": (45.0, 10.0),
    "north_arrow": (14.0, 22.0),
    "grid": (120.0, 90.0),
    "text": (120.0, 10.0),
    "image": (30.0, 30.0),
}


def item_to_dict(item):
    try:
        d = dict(item.to_dict())
    except Exception:
        _log.exception("silent exception in item_to_dict")
        d = dict(LayoutItem.to_dict(item))
    try:
        d["name"] = str(getattr(item, "name", "") or "")
    except Exception:
        _log.exception("silent exception in item_to_dict")
    try:
        d["visible"] = bool(getattr(item, "visible", True))
    except Exception:
        _log.exception("silent exception in item_to_dict")
    try:
        d["link"] = str(getattr(item, "link", "") or "")
    except Exception:
        _log.exception("silent exception in item_to_dict")
    return d


def item_from_dict(d):
    d = d or {}
    entry = ITEM_TYPES.get(str(d.get("type") or ""))
    if entry is None:
        return None
    it = entry[0]._load(d)
    try:
        if it is not None:
            it.name = str(d.get("name") or "")
    except Exception:
        _log.exception("silent exception in item_from_dict")
    try:
        if it is not None:
            it.visible = bool(d.get("visible", True))
    except Exception:
        _log.exception("silent exception in item_from_dict")
    try:
        if it is not None and "link" in d:
            it.link = str(d.get("link") or "")
    except Exception:
        _log.exception("silent exception in item_from_dict")
    return it


def create_item(type_name, rect_mm=None, **kw):
    entry = ITEM_TYPES.get(str(type_name or ""))
    if entry is None:
        raise LayoutError("未知的页面元素类型：%s" % type_name)
    cls = entry[0]
    if rect_mm is None:
        w, h = DEFAULT_SIZES.get(cls.type_name, (40.0, 20.0))
        rect_mm = QRectF(10.0, 10.0, w, h)
    return cls(rect_mm=rect_mm, **kw)
