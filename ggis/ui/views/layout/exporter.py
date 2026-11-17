# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import os
import time

from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF
from PySide6.QtGui import (QColor, QImage, QPageSize, QPainter, QPdfWriter)
from PySide6.QtSvg import QSvgGenerator

from ggis.render import fonts
from ggis.core.app import settings
from ggis.core.model.layout_model import mm_to_px

_log = logging.getLogger("gmagis")

__all__ = ["FORMATS", "ExportResult", "render_layout", "export_layout",
           "export_pdf", "export_svg", "export_image", "print_layout",
           "preview_image", "MAX_IMAGE_PIXELS", "freeze_snapshot"]


from ggis.core.model.layer import freeze_layer as _freeze_layer

class _FrozenProject(object):

    def __init__(self, project, layers):
        self._src = project
        self._layers = list(layers)
        self._crs = None
        self._ext = {}
        try:
            self._crs = settings.default_crs()
        except Exception:
            exc_note("__init__ @ ggis/ui/views/layout/exporter.py:61")
            self._crs = None

    def layers(self):
        return list(self._layers)

    def visible_layers(self):
        return [l for l in self._layers if _is_visible(l)]

    def layer_by_id(self, layer_id):
        for lyr in self._layers:
            try:
                if lyr.id() == layer_id:
                    return lyr
            except Exception:
                exc_note("layer_by_id @ ggis/ui/views/layout/exporter.py:77")
                continue
        return None

    def crs(self):
        return self._crs

    def full_extent(self, visible_only=False, dst_crs=None):
        key = (bool(visible_only), str(dst_crs) if dst_crs else "")
        if key not in self._ext:
            try:
                self._ext[key] = self._src.full_extent(
                    visible_only=visible_only, dst_crs=dst_crs)
            except Exception:
                exc_note("full_extent @ ggis/ui/views/layout/exporter.py:92")
                self._ext[key] = None
        return self._ext[key]

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_src"), name)


def _is_visible(layer):
    try:
        return bool(layer.is_visible())
    except Exception:
        exc_note("_is_visible @ ggis/ui/views/layout/exporter.py:103")
        return True


class _FrozenLayout(object):

    def __init__(self, layout, items):
        self._src = layout
        self._items = list(items)

    def items_in_draw_order(self):
        return list(self._items)

    @property
    def items(self):
        return list(self._items)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_src"), name)


def freeze_snapshot(layout, project):
    items = []
    try:
        items = [it for it in layout.items_in_draw_order()
                 if getattr(it, "visible", True)]
    except Exception:
        exc_note("freeze_snapshot @ ggis/ui/views/layout/exporter.py:133")
        items = []
    fl = _FrozenLayout(layout, items)
    if project is None:
        return fl, None
    layers = []
    try:
        for lyr in project.layers():
            layers.append(_freeze_layer(lyr))
    except Exception:
        exc_note("freeze_snapshot @ ggis/ui/views/layout/exporter.py:142")
        pass
    return fl, _FrozenProject(project, layers)


FORMATS = {
    "pdf": ("PDF（矢量，文字可选中）", "pdf"),
    "svg": ("SVG（矢量，可二次编辑）", "svg"),
    "png": ("PNG 图片", "image"),
    "jpg": ("JPG 图片", "image"),
    "jpeg": ("JPG 图片", "image"),
    "bmp": ("BMP 图片", "image"),
    "tif": ("TIFF 图片", "image"),
    "tiff": ("TIFF 图片", "image"),
}

MAX_IMAGE_PIXELS = 120_000_000


class ExportResult:

    def __init__(self, path="", fmt="", dpi=300.0):
        self.path = str(path or "")
        self.fmt = str(fmt or "")
        self.dpi = float(dpi or 0.0)
        self.ok = False
        self.error = ""
        self.bytes = 0
        self.ms = 0.0
        self.pages = 0
        self.warnings = []
        self.width_px = 0
        self.height_px = 0

    def summary(self):
        if not self.ok:
            return "出图失败：%s" % (self.error or "未知原因")
        return "%s · %d×%d px · %.0f dpi · %.1f KB · %.0f ms" % (
            os.path.basename(self.path), self.width_px, self.height_px,
            self.dpi, self.bytes / 1024.0, self.ms)

    def to_dict(self):
        return {"path": self.path, "format": self.fmt, "dpi": self.dpi,
                "ok": self.ok, "error": self.error, "bytes": self.bytes,
                "ms": round(self.ms, 1), "pages": self.pages,
                "width_px": self.width_px, "height_px": self.height_px,
                "warnings": list(self.warnings)}

    def __repr__(self):
        return "ExportResult(%s)" % self.summary()


def _reserve_obstacles(layout, ctx):
    page = layout.page_rect_mm()
    page_area = max(1e-6, page.width() * page.height())
    frames = layout.map_frames()
    for it in layout.items:
        if not getattr(it, "visible", True):
            continue
        if not getattr(it, "reserves_space", False):
            continue
        r = it.rect_mm
        if r.width() * r.height() >= page_area * 0.6:
            continue
        if any(r.contains(f.rect_mm) for f in frames):
            continue
        ctx.reserve(r)


def render_layout(painter, layout, ctx):
    if ctx.font_family == "":
        ctx.font_family = fonts.print_family()
    w_mm, h_mm = layout.page_mm()
    w_px = mm_to_px(w_mm, ctx.dpi)
    h_px = mm_to_px(h_mm, ctx.dpi)

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    if ctx.background:
        painter.fillRect(QRectF(0, 0, w_px, h_px),
                         QColor(ctx.background))

    _reserve_obstacles(layout, ctx)
    n = 0
    for item in layout.items_in_draw_order():
        if not getattr(item, "visible", True):
            continue
        try:
            item.draw(painter, ctx)
            n += 1
        except Exception as exc:
            exc_note("render_layout @ ggis/ui/views/layout/exporter.py:250")
            ctx.warn("元素「%s」绘制失败：%s" % (
                getattr(item, "label", item.type_name), exc))
    ctx.items_drawn = n
    return n


def _prepare(layout, project, dpi, font_family=None):
    from ggis.core.model.layout_model import ExportContext
    ctx = ExportContext(layout, project=project, dpi=dpi)
    ctx.font_family = str(font_family) if font_family is not None \
        else fonts.print_family()
    return ctx


def _page_size(layout):
    w_mm, h_mm = layout.page_mm()
    return QPageSize(QSizeF(w_mm, h_mm), QPageSize.Unit.Millimeter,
                     layout.name or "GmaGIS")


def export_pdf(layout, path, project=None, dpi=300.0, font_family=None,
               title="", result=None):
    r = result or ExportResult(path, "pdf", dpi)
    r.fmt = "pdf"
    try:
        w = QPdfWriter(path)
        w.setPageSize(_page_size(layout))
        w.setResolution(int(round(dpi)))
        w.setPageMargins(QMarginsF(0.0, 0.0, 0.0, 0.0))
        try:
            w.setTitle(title or layout.name or "GmaGIS 出图")
            w.setCreator("GmaGIS")
        except Exception:
            exc_note("export_pdf @ ggis/ui/views/layout/exporter.py:291")
            pass
        ctx = _prepare(layout, project, dpi, font_family)
        ctx.device = w
        painter = QPainter(w)
        try:
            render_layout(painter, layout, ctx)
        finally:
            painter.end()
        r.width_px = int(round(mm_to_px(layout.page_mm()[0], dpi)))
        r.height_px = int(round(mm_to_px(layout.page_mm()[1], dpi)))
        r.pages = 1
        r.warnings = list(ctx.warnings)
        r.ok = os.path.isfile(path) and os.path.getsize(path) > 0
        if not r.ok:
            r.error = "PDF 没有产生内容"
        return r
    except Exception as exc:
        r.error = "%s: %s" % (type(exc).__name__, exc)
        r.ok = False
        return r


def export_svg(layout, path, project=None, dpi=300.0, font_family=None,
               result=None):
    r = result or ExportResult(path, "svg", dpi)
    r.fmt = "svg"
    try:
        w_mm, h_mm = layout.page_mm()
        w_px = int(round(mm_to_px(w_mm, dpi)))
        h_px = int(round(mm_to_px(h_mm, dpi)))
        g = QSvgGenerator()
        g.setFileName(path)
        g.setSize(QSize(w_px, h_px))
        g.setViewBox(QRectF(0, 0, w_px, h_px))
        g.setResolution(int(round(dpi)))
        try:
            g.setTitle(layout.name or "GmaGIS 出图")
            g.setDescription("由 GmaGIS 生成")
        except Exception:
            exc_note("export_svg @ ggis/ui/views/layout/exporter.py:330")
            pass
        ctx = _prepare(layout, project, dpi, font_family)
        ctx.device = g
        painter = QPainter(g)
        try:
            render_layout(painter, layout, ctx)
        finally:
            painter.end()
        r.width_px, r.height_px = w_px, h_px
        r.pages = 1
        r.warnings = list(ctx.warnings)
        r.ok = os.path.isfile(path) and os.path.getsize(path) > 0
        if not r.ok:
            r.error = "SVG 没有产生内容"
        return r
    except Exception as exc:
        r.error = "%s: %s" % (type(exc).__name__, exc)
        r.ok = False
        return r


def export_image(layout, path, project=None, dpi=300.0, font_family=None,
                 background="#FFFFFF", result=None):
    r = result or ExportResult(path, "image", dpi)
    try:
        w_mm, h_mm = layout.page_mm()
        w_px = int(round(mm_to_px(w_mm, dpi)))
        h_px = int(round(mm_to_px(h_mm, dpi)))
        if w_px * h_px > MAX_IMAGE_PIXELS:
            k = (MAX_IMAGE_PIXELS / float(w_px * h_px)) ** 0.5
            dpi = max(72.0, dpi * k)
            w_px = int(round(mm_to_px(w_mm, dpi)))
            h_px = int(round(mm_to_px(h_mm, dpi)))
            r.dpi = float(dpi)
            r.warnings.append("位图过大，DPI 已自动降到 %.0f" % dpi)
        img = QImage(max(1, w_px), max(1, h_px),
                     QImage.Format.Format_ARGB32)
        if img.isNull():
            r.error = ("位图分配失败（%d×%d，约 %.0f MB），请降低 DPI"
                       % (w_px, h_px, w_px * h_px * 4.0 / 1048576.0))
            r.ok = False
            return r
        img.fill(QColor(background or "#FFFFFF"))
        try:
            dpm = int(round(float(dpi) / 25.4 * 1000.0))
            img.setDotsPerMeterX(dpm)
            img.setDotsPerMeterY(dpm)
        except Exception:
            exc_note("export_image @ ggis/ui/views/layout/exporter.py:380")
            pass
        ctx = _prepare(layout, project, dpi, font_family)
        ctx.background = background or "#FFFFFF"
        ctx.device = img
        painter = QPainter(img)
        try:
            render_layout(painter, layout, ctx)
        finally:
            painter.end()
        ok = img.save(path)
        r.width_px, r.height_px = w_px, h_px
        r.pages = 1
        r.warnings = list(ctx.warnings) + r.warnings
        r.ok = bool(ok)
        if not ok:
            r.error = "图片保存失败（后缀不支持？）"
        return r
    except Exception as exc:
        r.error = "%s: %s" % (type(exc).__name__, exc)
        r.ok = False
        return r


def _export_now(layout, path, project, use_dpi, ext, kind, font_family,
                title, background):
    t0 = time.perf_counter()
    r = ExportResult(path, ext, use_dpi)
    if kind == "pdf":
        export_pdf(layout, path, project, use_dpi, font_family, title, r)
    elif kind == "svg":
        export_svg(layout, path, project, use_dpi, font_family, r)
    else:
        export_image(layout, path, project, use_dpi, font_family,
                     background, r)
    r.ms = (time.perf_counter() - t0) * 1000.0
    try:
        r.bytes = os.path.getsize(path) if os.path.isfile(path) else 0
    except Exception:
        exc_note("_export_now @ ggis/ui/views/layout/exporter.py:419")
        r.bytes = 0
    return r


def export_layout(layout, path, project=None, dpi=None, fmt="",
                  font_family=None, title="", background="#FFFFFF"):
    ext = str(fmt or os.path.splitext(str(path))[1].lstrip(".")).lower()
    if ext not in FORMATS:
        r = ExportResult(path, ext, dpi or 0.0)
        r.error = "不支持的输出格式：%s" % (ext or "（空）")
        return r
    use_dpi = float(dpi or layout.dpi or 300.0)
    kind = FORMATS[ext][1]
    snap_layout, snap_project = freeze_snapshot(layout, project)
    args = (snap_layout, path, snap_project, use_dpi, ext, kind,
            font_family, title, background)
    from ggis.exec import guard as _g
    if not (_g.ui_mode() and _g.on_ui_thread()):
        return _export_now(*args)
    from ggis.exec import task as _et
    return _et.submit(_export_now, *args, name="export-" + ext, kind="cpu")


def print_layout(layout, project=None, printer=None, dpi=300.0,
                 font_family=None, background="#FFFFFF"):
    r = ExportResult(getattr(printer, "outputFileName", lambda: "")
                     if printer else "", "print", dpi)
    if printer is None:
        r.error = "没有可用的打印机"
        return r
    t0 = time.perf_counter()
    try:
        w_mm, h_mm = layout.page_mm()
        w_px = int(round(mm_to_px(w_mm, dpi)))
        h_px = int(round(mm_to_px(h_mm, dpi)))
        ctx = _prepare(layout, project, dpi, font_family)
        ctx.background = background or "#FFFFFF"
        ctx.device = printer
        painter = QPainter(printer)
        try:
            render_layout(painter, layout, ctx)
        finally:
            painter.end()
        r.width_px, r.height_px = w_px, h_px
        r.pages = 1
        r.warnings = list(ctx.warnings)
        r.ok = True
        try:
            if r.path and os.path.isfile(r.path):
                r.bytes = os.path.getsize(r.path)
        except Exception:
            exc_note("print_layout @ ggis/ui/views/layout/exporter.py:494")
            pass
    except Exception as exc:
        r.error = "%s: %s" % (type(exc).__name__, exc)
        r.ok = False
    r.ms = (time.perf_counter() - t0) * 1000.0
    return r


def preview_image(layout, project=None, width_px=760, dpi=None,
                  font_family=None, background="#FFFFFF"):
    w_mm, h_mm = layout.page_mm()
    if w_mm <= 0 or h_mm <= 0:
        return QImage()
    use_dpi = float(dpi or 96.0)
    w = max(64, int(width_px))
    h = max(64, int(round(w * h_mm / w_mm)))
    scale = w / max(1e-9, mm_to_px(w_mm, use_dpi))
    use_dpi = (w / w_mm) * 25.4
    ctx = _prepare(layout, project, use_dpi, font_family)
    ctx.background = background or "#FFFFFF"
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(background or "#FFFFFF"))
    try:
        _dpm = max(1, int(round(float(use_dpi) * 1000.0 / 25.4)))
        img.setDotsPerMeterX(_dpm)
        img.setDotsPerMeterY(_dpm)
    except Exception:
        exc_note("preview_image @ ggis/ui/views/layout/exporter.py:538")
        pass
    ctx.device = img
    painter = QPainter(img)
    try:
        render_layout(painter, layout, ctx)
    except Exception:
        exc_note("preview_image @ ggis/ui/views/layout/exporter.py:544")
        pass
    finally:
        painter.end()
    del scale
    return img


def preview_region(layout, rect_mm, project=None, width_px=600,
                   font_family=None, background="#FFFFFF", exclude=None,
                   dpi=None):
    r = QRectF(rect_mm)
    if r.width() <= 0 or r.height() <= 0:
        return QImage()
    if exclude is not None:
        try:
            items = [it for it in layout.items_in_draw_order()
                     if it is not exclude]
            layout = _FrozenLayout(layout, items)
        except Exception:
            exc_note("preview_region @ ggis/ui/views/layout/exporter.py:578")
            pass
    w = max(16, int(width_px))
    h = max(16, int(round(w * r.height() / r.width())))
    use_dpi = float(dpi) if dpi else (w / r.width()) * 25.4
    ctx = _prepare(layout, project, use_dpi, font_family)
    ctx.background = ""
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor("#00000000"))
    try:
        _dpm = max(1, int(round(float(use_dpi) * 1000.0 / 25.4)))
        img.setDotsPerMeterX(_dpm)
        img.setDotsPerMeterY(_dpm)
    except Exception:
        exc_note("preview_region @ ggis/ui/views/layout/exporter.py:599")
        pass
    ctx.device = img
    painter = QPainter(img)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        px = ctx.rect_px(r)
        try:
            w_mm, h_mm = layout.page_mm()
            pr = ctx.rect_px(QRectF(0.0, 0.0, float(w_mm), float(h_mm)))
            paper = QRectF(float(pr.x() - px.x()), float(pr.y() - px.y()),
                           float(pr.width()), float(pr.height()))
            paper = paper.intersected(QRectF(0.0, 0.0, w, h))
            if paper.width() >= 1.0 and paper.height() >= 1.0:
                painter.fillRect(paper, QColor(background or "#FFFFFF"))
        except Exception:
            _log.exception("布局：区域渲染铺纸失败（退回整块铺）")
            painter.fillRect(QRectF(0.0, 0.0, w, h), QColor(background or
                                                             "#FFFFFF"))
        painter.translate(-px.x(), -px.y())
        render_layout(painter, layout, ctx)
    except Exception:
        exc_note("preview_region @ ggis/ui/views/layout/exporter.py:625")
        pass
    finally:
        painter.end()
    return img


def preview_item(layout, item, project=None, width_px=600,
                 font_family=None, background="#FFFFFF", pad_mm=0.0):
    r = QRectF(item.rect_mm)
    if r.width() <= 0 or r.height() <= 0:
        return QImage()
    pad = max(0.0, float(pad_mm or 0.0))
    rr = r.adjusted(-pad, -pad, pad, pad) if pad > 0 else QRectF(r)
    w = max(24, int(width_px))
    h = max(24, int(round(w * rr.height() / max(1e-9, rr.width()))))
    use_dpi = (w / rr.width()) * 25.4
    ctx = _prepare(layout, project, use_dpi, font_family)
    ctx.background = ""
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(background or "#FFFFFF"))
    try:
        _dpm = max(1, int(round(float(use_dpi) * 1000.0 / 25.4)))
        img.setDotsPerMeterX(_dpm)
        img.setDotsPerMeterY(_dpm)
    except Exception:
        exc_note("preview_item @ ggis/ui/views/layout/exporter.py:671")
        pass
    ctx.device = img
    painter = QPainter(img)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        try:
            _reserve_obstacles(layout, ctx)
        except Exception:
            exc_note("preview_item @ ggis/ui/views/layout/exporter.py:680")
            pass
        px = ctx.rect_px(rr)
        painter.translate(-px.x(), -px.y())
        item.draw(painter, ctx)
    except Exception:
        exc_note("preview_item @ ggis/ui/views/layout/exporter.py:686")
        pass
    finally:
        painter.end()
    return img


def pdf_report(path):
    import re
    import zlib
    rep = {"bytes": 0, "fonts": 0, "images": 0, "text_objects": 0,
           "text_shows": 0, "paths": 0, "strokes": 0, "fills": 0,
           "has_tounicode": False, "error": ""}
    try:
        raw = open(path, "rb").read()
    except Exception as exc:
        exc_note("pdf_report @ ggis/ui/views/layout/exporter.py:708")
        rep["error"] = str(exc)
        return rep
    rep["bytes"] = len(raw)
    rep["fonts"] = raw.count(b"/Type /Font") + raw.count(b"/Type/Font")
    rep["images"] = (raw.count(b"/Subtype /Image")
                     + raw.count(b"/Subtype/Image"))
    rep["has_tounicode"] = b"/ToUnicode" in raw
    for s in re.findall(rb"stream\r?\n(.*?)endstream", raw, re.S):
        try:
            t = zlib.decompress(s.rstrip(b"\r\n")).decode("latin-1")
        except Exception:
            exc_note("pdf_report @ ggis/ui/views/layout/exporter.py:719")
            continue
        rep["text_objects"] += t.count("BT")
        rep["text_shows"] += t.count("Tj") + t.count("TJ")
        rep["paths"] += t.count(" m\n") + t.count(" l\n") + t.count("re\n")
        rep["strokes"] += t.count("S\n")
        rep["fills"] += t.count("f\n")
    return rep
