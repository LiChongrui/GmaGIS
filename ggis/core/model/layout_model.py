# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import uuid

from PySide6.QtCore import QPointF, QRectF, QSizeF
import logging
_log = logging.getLogger("gmagis")

__all__ = [
    "PAGE_SIZES", "ORIENTATION_PORTRAIT", "ORIENTATION_LANDSCAPE",
    "ORIENTATIONS", "page_size_mm", "LayoutError", "ExportContext",
    "Layout", "LayoutItem", "new_id", "mm_to_px", "px_to_mm",
    "nice_number", "nice_floor",
    "PAGE_UNIT_CODES", "DEFAULT_UNIT", "unit_factor",
]

ORIENTATION_PORTRAIT = "portrait"
ORIENTATION_LANDSCAPE = "landscape"
ORIENTATIONS = (ORIENTATION_PORTRAIT, ORIENTATION_LANDSCAPE)

PAGE_UNIT_CODES = ("mm", "cm", "in")
DEFAULT_UNIT = "mm"


def unit_factor(code):
    return {"cm": 10.0, "in": 25.4}.get(str(code or DEFAULT_UNIT), 1.0)


PAGE_SIZES = {
    "A0": (841.0, 1189.0),
    "A1": (594.0, 841.0),
    "A2": (420.0, 594.0),
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "A6": (105.0, 148.0),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
    "Tabloid": (279.4, 431.8),
    "B5": (176.0, 250.0),
    "B4": (250.0, 353.0),
    "B3": (353.0, 500.0),
    "B2": (500.0, 707.0),
    "B1": (707.0, 1000.0),
    "B0": (1000.0, 1414.0),
}

DEFAULT_PAGE = "A4"


class LayoutError(Exception):
    pass


def new_id(prefix="LY"):
    return "%s-%s" % (prefix, uuid.uuid4().hex[:8])


def mm_to_px(mm, dpi):
    return float(mm) * float(dpi) / 25.4


def px_to_mm(px, dpi):
    d = float(dpi) or 96.0
    return float(px) * 25.4 / d


def page_size_mm(name=DEFAULT_PAGE, orientation=ORIENTATION_PORTRAIT):
    key = str(name or DEFAULT_PAGE)
    base = PAGE_SIZES.get(key)
    if base is None:
        try:
            a, b = key.lower().replace(" ", "").split("x")
            base = (float(a), float(b))
        except Exception:
            raise LayoutError("不支持的纸张：%s" % key)
    w, h = float(base[0]), float(base[1])
    if str(orientation or ORIENTATION_PORTRAIT).lower() != \
            ORIENTATION_PORTRAIT:
        if h > w:
            w, h = h, w
    else:
        if w > h:
            w, h = h, w
    return (w, h)


def nice_number(x):
    return _nice(x, up=True)


def nice_floor(x):
    return _nice(x, up=False)


def _nice(x, up=True):
    x = float(x)
    if x <= 0:
        return 0.0
    import math
    e = math.floor(math.log10(x))
    f = x / (10.0 ** e)
    steps = (1.0, 2.0, 2.5, 5.0, 10.0)
    if up:
        for step in steps:
            if f <= step + 1e-9:
                return step * (10.0 ** e)
        return 10.0 ** (e + 1)
    best = 1.0
    for step in steps:
        if step <= f + 1e-9:
            best = step
    return best * (10.0 ** e)


class ExportContext:

    def __init__(self, layout, project=None, dpi=300.0, font_family="",
                 device=None, background="#FFFFFF"):
        self.layout = layout
        self.project = project
        self.dpi = float(dpi or 300.0)
        self.font_family = str(font_family or "")
        self.device = device
        self.background = background
        self.obstacles_mm = []
        self.map_frames = []
        self.warnings = []
        self.items_drawn = 0
        self._by_link = {}

    def mm_to_px(self, mm):
        return mm_to_px(mm, self.dpi)

    def px_to_mm(self, px):
        return px_to_mm(px, self.dpi)

    def rect_px(self, rect_mm):
        k = self.dpi / 25.4
        return QRectF(rect_mm.x() * k, rect_mm.y() * k,
                      rect_mm.width() * k, rect_mm.height() * k)

    def size_px(self):
        w, h = self.layout.page_mm()
        k = self.dpi / 25.4
        return QSizeF(w * k, h * k)

    def register_link(self, name, item):
        if name:
            self._by_link.setdefault(str(name), item)

    def linked(self, name):
        return self._by_link.get(str(name or ""))

    def reserve(self, rect_mm):
        self.obstacles_mm.append(QRectF(rect_mm))

    def warn(self, text):
        t = str(text)
        if t not in self.warnings:
            self.warnings.append(t)
        return t


class LayoutItem:

    type_name = "item"
    label = "元素"
    reserves_space = False
    fixed_ratio = False
    link = ""

    def __init__(self, rect_mm=None, z=0, item_id=""):
        self.rect_mm = QRectF(rect_mm) if rect_mm is not None \
            else QRectF(0, 0, 40, 20)
        self.z = int(z)
        self.id = str(item_id or new_id("IT"))
        self.visible = True
        self.name = ""

    def rect(self):
        return QRectF(self.rect_mm)

    def set_rect_mm(self, rect):
        self.rect_mm = QRectF(rect)

    def move_mm(self, dx, dy):
        self.rect_mm.translate(float(dx), float(dy))

    def contains_mm(self, pt):
        return self.rect_mm.contains(QPointF(pt))

    def content_scale(self):
        try:
            from . import layout_items as _LI
            d = _LI.DEFAULT_SIZES.get(str(getattr(self, "type_name", "")))
            if not d:
                return 1.0
            dw, dh = float(d[0]), float(d[1])
            if dw <= 0 or dh <= 0:
                return 1.0
            sx = float(self.rect_mm.width()) / dw
            sy = float(self.rect_mm.height()) / dh
            return max(0.05, min(sx, sy))
        except Exception:
            _log.exception("silent exception in content_scale")
            return 1.0

    def draw(self, painter, ctx):
        raise NotImplementedError

    def preview_text(self):
        return self.label

    def render_to(self, painter, ctx, dev_rect):
        self.draw(painter, ctx)

    def minimum_size_mm(self):
        return (10.0, 6.0)

    def to_dict(self):
        r = self.rect_mm
        return {"type": self.type_name, "id": self.id, "z": self.z,
                "rect_mm": [r.x(), r.y(), r.width(), r.height()]}

    @staticmethod
    def _rect_from(d):
        try:
            r = d.get("rect_mm") or [0, 0, 40, 20]
            return QRectF(float(r[0]), float(r[1]), float(r[2]),
                          float(r[3]))
        except Exception:
            _log.exception("silent exception in _rect_from")
            return QRectF(0, 0, 40, 20)

    def _load_base(self, d):
        self.id = str(d.get("id") or new_id("IT"))
        self.z = int(d.get("z") or 0)
        self.rect_mm = LayoutItem._rect_from(d)
        return self


class Layout:

    def __init__(self, name="", page=DEFAULT_PAGE,
                 orientation=ORIENTATION_LANDSCAPE,
                 margins_mm=(10.0, 10.0, 10.0, 10.0),
                 items=None, layout_id="", dpi=300.0, unit=DEFAULT_UNIT):
        self.id = str(layout_id or new_id("LY"))
        self.name = str(name or "布局 1")
        self.page = str(page or DEFAULT_PAGE)
        self.orientation = str(orientation or ORIENTATION_LANDSCAPE)
        if self.orientation not in ORIENTATIONS:
            self.orientation = ORIENTATION_LANDSCAPE
        self.unit = str(unit or DEFAULT_UNIT)
        if self.unit not in PAGE_UNIT_CODES:
            self.unit = DEFAULT_UNIT
        self.margins_mm = tuple(float(x) for x in (margins_mm or
                                                   (10, 10, 10, 10)))
        self.items = list(items or [])
        self.dpi = float(dpi or 300.0)

    def set_page(self, page, orientation=None):
        self.page = str(page or DEFAULT_PAGE)
        if orientation:
            self.orientation = str(orientation)
        page_size_mm(self.page, self.orientation)

    def page_mm(self):
        return page_size_mm(self.page, self.orientation)

    def page_rect_mm(self):
        w, h = self.page_mm()
        return QRectF(0.0, 0.0, w, h)

    def margins(self):
        l, t, r, b = self.margins_mm
        return (float(l), float(t), float(r), float(b))

    def content_rect_mm(self):
        w, h = self.page_mm()
        l, t, r, b = self.margins()
        return QRectF(l, t, max(1.0, w - l - r), max(1.0, h - t - b))

    def set_margins(self, l, t, r, b):
        self.margins_mm = (max(0.0, float(l)), max(0.0, float(t)),
                           max(0.0, float(r)), max(0.0, float(b)))

    def add_item(self, item, index=None):
        if index is None:
            self.items.append(item)
        else:
            self.items.insert(max(0, int(index)), item)
        return item

    def remove_item(self, item):
        try:
            self.items.remove(item)
            return True
        except ValueError:
            exc_note("remove_item @ ggis/core/model/layout_model.py:383")
            return False

    def item_by_id(self, item_id):
        for it in self.items:
            if it.id == item_id:
                return it
        return None

    def items_in_draw_order(self):
        return sorted(self.items, key=lambda it: int(it.z))

    def raise_item(self, item, delta=1):
        item.z = int(item.z) + int(delta)
        return item.z

    def lower_item(self, item, delta=1):
        item.z = int(item.z) - int(delta)
        return item.z

    def map_frames(self):
        return [it for it in self.items
                if getattr(it, "type_name", "") == "map_frame"]

    def resolve_link(self, link):
        s = str(link or "").strip()
        if not s:
            frames = self.map_frames()
            return frames[0] if frames else None
        if "#" in s:
            base, _, idx = s.partition("#")
            try:
                i = int(idx)
            except ValueError:
                exc_note("resolve_link @ ggis/core/model/layout_model.py:418")
                i = 0
            frames = [it for it in self.items
                      if getattr(it, "type_name", "") == base]
            return frames[i] if 0 <= i < len(frames) else None
        for it in self.items:
            if it.id == s or getattr(it, "name", "") == s:
                return it
        return None

    def link_names(self):
        out = []
        for i, _f in enumerate(self.map_frames()):
            out.append("map_frame#%d" % i)
        return out

    def to_dict(self):
        from . import layout_items
        return {
            "id": self.id,
            "name": self.name,
            "page": self.page,
            "orientation": self.orientation,
            "unit": self.unit,
            "margins_mm": list(self.margins_mm),
            "dpi": self.dpi,
            "items": [layout_items.item_to_dict(it)
                      for it in self.items_in_draw_order()],
        }

    @staticmethod
    def from_dict(d):
        from . import layout_items
        d = d or {}
        page = d.get("page") or DEFAULT_PAGE
        orient = d.get("orientation") or ORIENTATION_LANDSCAPE
        try:
            page_size_mm(page, orient)
        except LayoutError:
            exc_note("from_dict @ ggis/core/model/layout_model.py:461")
            page, orient = DEFAULT_PAGE, ORIENTATION_LANDSCAPE
        lay = Layout(name=d.get("name") or "布局",
                     page=page, orientation=orient,
                     margins_mm=d.get("margins_mm") or (10, 10, 10, 10),
                     layout_id=d.get("id") or "",
                     dpi=d.get("dpi") or 300.0,
                     unit=d.get("unit") or DEFAULT_UNIT)
        for raw in d.get("items") or []:
            it = layout_items.item_from_dict(raw)
            if it is not None:
                lay.items.append(it)
        orphan_grids = []
        keep = []
        for it in lay.items:
            if str(getattr(it, "type_name", "")) == "grid":
                orphan_grids.append(it)
            else:
                keep.append(it)
        lay.items = keep
        for g in orphan_grids:
            target = None
            try:
                target = lay.resolve_link(getattr(g, "link", ""))
            except Exception:
                _log.exception("silent exception in from_dict")
                target = None
            if target is None:
                frames = lay.map_frames()
                target = frames[0] if frames else None
            if target is None or getattr(target, "grid", None) is not None:
                lay.items.append(g)
                continue
            g.set_rect_mm(QRectF(target.rect_mm))
            g.link = ""
            target.grid = g
        return lay

    def clone(self):
        return Layout.from_dict(self.to_dict())

    def __repr__(self):
        w, h = self.page_mm()
        return "Layout(%s, %gx%gmm, %d items)" % (self.name, w, h,
                                                  len(self.items))
