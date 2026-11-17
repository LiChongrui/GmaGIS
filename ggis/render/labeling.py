# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import math
import time

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainterPath, \
    QPen

from ..core.crs import crs_pair_key, crs_scale_factor, crs_transformer
from ggis.core.crs.units import (default_unit as _default_unit,
                          from_px as _px_to_unit, is_known as _unit_known,
                          to_px as _unit_to_px)

__all__ = [
    "LABEL_SIZE_FIELDS", "LabelStyle", "LabelCandidate", "PlacedLabel",
    "LabelEngine",
    "draw_labels", "get_label_style", "set_label_style",
    "invalidate_label_cache", "label_version", "bump_label_version",
    "suggest_label_field", "POSITION_RIGHT", "POSITION_TOP",
    "POSITION_BOTTOM", "POSITION_LEFT", "POSITION_CENTER",
    "make_halo_pen", "stroke_text_path",
]

POSITION_RIGHT = "right"
POSITION_TOP = "top"
POSITION_BOTTOM = "bottom"
POSITION_LEFT = "left"
POSITION_CENTER = "center"

_POINT_POSITIONS = (POSITION_RIGHT, POSITION_TOP,
                    POSITION_BOTTOM, POSITION_LEFT)

_AUTO_POSITIONS = {
    "point": _POINT_POSITIONS,
    "line": (POSITION_TOP, POSITION_BOTTOM, POSITION_CENTER),
    "polygon": (POSITION_CENTER,),
}

_POS_RIGHT, _POS_TOP, _POS_BOTTOM, _POS_LEFT, _POS_CENTER = 1, 2, 3, 4, 5
_POS_CODE = {POSITION_RIGHT: _POS_RIGHT, POSITION_TOP: _POS_TOP,
             POSITION_BOTTOM: _POS_BOTTOM, POSITION_LEFT: _POS_LEFT,
             POSITION_CENTER: _POS_CENTER}
_POS_NAME = {v: k for k, v in _POS_CODE.items()}

_KIND_RANK = {"point": 0, "line": 1, "polygon": 2}

_ROTATE_THRESHOLD = 8.0

_MIN_CELL = 12.0
DEFAULT_MAX_CANDIDATES = 60000

LABEL_CANDIDATE_CAP = 3000
LABEL_GRID_K = 6
LABEL_CANDIDATE_BUDGET_MS = 24.0

_PAN_MATCH_SCALE_MIN = 0.5
_PAN_MATCH_SCALE_MAX = 2.0


LABEL_SIZE_FIELDS = ("halo_width", "buffer", "min_size_px", "repeat_px")

_PX_FACTOR = {}


def _unit_factor(u):
    f = _PX_FACTOR.get(u)
    if f is not None:
        return f
    try:
        f = float(_unit_to_px(1.0, u))
    except Exception:
        exc_note("_unit_factor @ ggis/render/labeling.py:171")
        f = 1.0
    _PX_FACTOR[u] = f
    return f


class LabelStyle:

    __slots__ = ("enabled", "field", "font_family", "font_size", "bold",
                 "italic", "color", "halo_color", "halo_width", "buffer",
                 "offset_x", "offset_y", "placement", "min_scale",
                 "max_scale", "min_size_px", "max_labels", "repeat_px",
                 "formatter", "_font_key", "_font", "unit")

    def __init__(self, enabled=False, field="", font_family="",
                 font_size=9.0, bold=False, italic=False,
                 color="#FFFFFF", halo_color="#000000", halo_width=None,
                 buffer=None, offset_x=0.0, offset_y=0.0, placement="auto",
                 min_scale=0.0, max_scale=0.0, min_size_px=0.0,
                 max_labels=0, repeat_px=0.0, formatter=None, unit=None):
        _u = str(unit or _default_unit())
        self.unit = _u
        self.enabled = bool(enabled)
        self.field = str(field or "")
        self.font_family = str(font_family or "")
        self.font_size = float(font_size)
        self.bold = bool(bold)
        self.italic = bool(italic)
        self.color = str(color or "#FFFFFF")
        self.halo_color = str(halo_color or "#000000")
        self.halo_width = float(_px_to_unit(1.6, _u)) if halo_width is None \
            else float(halo_width)
        self.buffer = float(_px_to_unit(2.0, _u)) if buffer is None \
            else float(buffer)
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)
        self.placement = str(placement or "auto")
        self.min_scale = float(min_scale)
        self.max_scale = float(max_scale)
        self.min_size_px = float(min_size_px)
        self.max_labels = int(max_labels)
        self.repeat_px = float(repeat_px)
        self.formatter = formatter
        self._font_key = None
        self._font = None

    def px_of(self, name):
        try:
            v = float(getattr(self, name, 0.0) or 0.0)
        except Exception:
            exc_note("px_of @ ggis/render/labeling.py:242")
            return 0.0
        try:
            u = getattr(self, "unit", None) or "px"
        except Exception:
            exc_note("px_of @ ggis/render/labeling.py:246")
            u = "px"
        return v * _unit_factor(u)

    def size_fields(self):
        return LABEL_SIZE_FIELDS

    def font(self):
        key = (self.font_family, round(self.font_size, 3), self.bold,
               self.italic)
        if self._font_key == key and self._font is not None:
            return self._font
        f = QFont(self.font_family) if self.font_family else QFont()
        f.setPointSizeF(max(1.0, self.font_size))
        f.setBold(self.bold)
        f.setItalic(self.italic)
        self._font_key = key
        self._font = f
        return f

    def font_key(self):
        self.font()
        return self._font_key

    def positions_for(self, kind, layer_key="auto"):
        base = _AUTO_POSITIONS.get(kind, _POINT_POSITIONS)
        p = (self.placement or "auto").lower()
        if p in (POSITION_RIGHT, POSITION_TOP, POSITION_BOTTOM,
                 POSITION_LEFT, POSITION_CENTER):
            if p in base:
                return (p,) + tuple(x for x in base if x != p)
            return (p,) + base
        return base

    def scale_ok(self, scale_denom):
        if not scale_denom:
            return True
        if self.min_scale and scale_denom < self.min_scale:
            return False
        if self.max_scale and scale_denom > self.max_scale:
            return False
        return True

    def place_key(self):
        return (self.enabled, self.field, self.placement, self.font_key(),
                self.unit, round(self.buffer, 4), round(self.offset_x, 4),
                round(self.offset_y, 4), round(self.min_size_px, 4),
                self.max_labels, self.min_scale, self.max_scale)

    def clone(self):
        s = LabelStyle()
        for name in self.__slots__:
            if name.startswith("_"):
                continue
            setattr(s, name, getattr(self, name))
        return s

    _DICT_KEYS = ("enabled", "field", "font_family", "font_size", "bold",
                  "italic", "color", "halo_color", "halo_width", "buffer",
                  "offset_x", "offset_y", "placement", "min_scale",
                  "max_scale", "min_size_px", "max_labels", "repeat_px",
                  "unit")

    def to_dict(self):
        return {k: getattr(self, k) for k in self._DICT_KEYS}

    @staticmethod
    def from_dict(d):
        d = d or {}
        s = LabelStyle()
        for key in LabelStyle._DICT_KEYS:
            if key in d and d[key] is not None:
                try:
                    setattr(s, key, d[key])
                except Exception:
                    exc_note("from_dict @ ggis/render/labeling.py:332")
                    pass
        if not _unit_known(str(getattr(s, "unit", "") or "").strip().lower()):
            _u = _default_unit()
            for _k in LABEL_SIZE_FIELDS:
                try:
                    setattr(s, _k,
                            _px_to_unit(float(getattr(s, _k) or 0.0), _u))
                except Exception:
                    exc_note("from_dict @ ggis/render/labeling.py:344")
                    pass
            s.unit = _u
        return s

    def __repr__(self):
        return "LabelStyle(%s, field=%r, size=%s)" % (
            "on" if self.enabled else "off", self.field, self.font_size)


def get_label_style(layer):
    s = layer.__dict__.get("_label_style")
    if s is None:
        s = LabelStyle()
        try:
            layer._label_style = s
        except Exception:
            exc_note("get_label_style @ ggis/render/labeling.py:364")
            pass
    return s


def set_label_style(layer, style):
    try:
        layer._label_style = style
    except Exception:
        exc_note("set_label_style @ ggis/render/labeling.py:372")
        pass
    invalidate_label_cache(layer)
    bump_label_version(layer)


def invalidate_label_cache(layer):
    try:
        layer.__dict__.pop("_ggs_label_cache", None)
    except Exception:
        exc_note("invalidate_label_cache @ ggis/render/labeling.py:382")
        pass


def bump_label_version(layer):
    try:
        layer._label_version = int(
            layer.__dict__.get("_label_version", 0)) + 1
    except Exception:
        exc_note("bump_label_version @ ggis/render/labeling.py:390")
        pass


def label_version(layer):
    return int(layer.__dict__.get("_label_version", 0))


def suggest_label_field(layer):
    try:
        fields = list(layer.fields())
    except Exception:
        exc_note("suggest_label_field @ ggis/render/labeling.py:402")
        return ""
    if not fields:
        return ""
    for name, typ in fields:
        t = str(typ or "").lower()
        if "string" in t or "text" in t or "char" in t:
            return str(name)
    try:
        return str(fields[0][0])
    except Exception:
        exc_note("suggest_label_field @ ggis/render/labeling.py:412")
        return ""


class LabelCandidate:

    __slots__ = ("fid", "text", "x", "y", "angle", "kind", "size",
                 "rank", "weight")

    def __init__(self, text, x, y, fid=-1, angle=0.0, kind="point",
                 size=0.0, weight=None):
        self.fid = int(fid)
        self.text = str(text or "")
        self.x = float(x)
        self.y = float(y)
        self.angle = float(angle)
        self.kind = str(kind)
        self.size = float(size)
        self.rank = _KIND_RANK.get(self.kind, 0)
        self.weight = float(size if weight is None else weight)


class PlacedLabel:

    __slots__ = ("layer_id", "fid", "text", "rect", "anchor", "angle",
                 "position", "style", "rank")

    def __init__(self, layer_id, fid, text, rect, anchor, angle, position,
                 style, rank=0):
        self.layer_id = layer_id
        self.fid = fid
        self.text = text
        self.rect = rect
        self.anchor = anchor
        self.angle = angle
        self.position = position
        self.style = style
        self.rank = rank

    def width(self):
        return self.rect[2] - self.rect[0]

    def height(self):
        return self.rect[3] - self.rect[1]

    def center(self):
        return ((self.rect[0] + self.rect[2]) * 0.5,
                (self.rect[1] + self.rect[3]) * 0.5)

    def qrect(self):
        from PySide6.QtCore import QRectF
        return QRectF(self.rect[0], self.rect[1],
                      self.rect[2] - self.rect[0],
                      self.rect[3] - self.rect[1])

    def __repr__(self):
        return "PlacedLabel(%r, %s, %s)" % (self.text, self.position,
                                            self.rect)


def style_font(style, family=""):
    try:
        f = style.font()
    except Exception:
        exc_note("style_font @ ggis/render/labeling.py:493")
        f = QFont()
    fam = str(family or "")
    if not fam or f.family() == fam:
        return f
    g = QFont(f)
    g.setFamily(fam)
    return g


_UNSET = object()


class _Part:

    __slots__ = ("sel", "px", "py", "tw", "th", "ang", "rank", "wgt",
                 "fid", "texts", "positions", "style", "lid",
                 "texts_all", "fkey", "fm", "fm_h", "sc")

    def __init__(self):
        self.sel = None
        self.px = None
        self.py = None
        self.tw = None
        self.th = None
        self.ang = None
        self.rank = None
        self.wgt = None
        self.fid = None
        self.texts = None
        self.positions = ()
        self.style = None
        self.lid = None
        self.texts_all = None
        self.fkey = None
        self.fm = None
        self.fm_h = 0.0
        self.sc = None


class _PanLabel:

    __slots__ = ("dx0", "dy0", "dx1", "dy1", "pl")

    def __init__(self, dx0, dy0, dx1, dy1, pl):
        self.dx0 = dx0
        self.dy0 = dy0
        self.dx1 = dx1
        self.dy1 = dy1
        self.pl = pl


class _PanFrame:

    __slots__ = ("w", "h", "sx", "sy", "cap", "budget", "obstacles",
                 "items", "dec")

    def __init__(self, w, h, sx, sy, cap, budget, obstacles, items, dec):
        self.w = w
        self.h = h
        self.sx = sx
        self.sy = sy
        self.cap = cap
        self.budget = budget
        self.obstacles = obstacles
        self.items = items
        self.dec = dec


class LabelEngine:

    def __init__(self, max_candidates=DEFAULT_MAX_CANDIDATES):
        self.max_candidates = int(max_candidates)
        self._fm_cache = {}
        self._size_cache = {}
        self._anchor_errors = []
        self._stats = {"candidates": 0, "placed": 0, "dropped": 0,
                       "ms": 0.0, "layers": 0, "measured": 0,
                       "thinned": 0, "capped": 0, "budget_hit": False,
                       "pan_reuse": 0}
        self._device = None
        self._device_dpi = 0.0
        self._font_family = ""
        self._pan = None

    def set_paint_device(self, device, dpi=0.0):
        self._device = device
        try:
            self._device_dpi = float(dpi or 0.0)
        except Exception:
            exc_note("set_paint_device @ ggis/render/labeling.py:618")
            self._device_dpi = 0.0
        self._fm_cache.clear()
        self._pan = None
        return self

    def set_font_family(self, family):
        fam = str(family or "")
        if fam != self._font_family:
            self._font_family = fam
            self._fm_cache.clear()
            self._pan = None
        return self

    def font_family(self):
        return self._font_family

    def stats(self):
        d = dict(self._stats)
        d["anchor_errors"] = tuple(self._anchor_errors)
        return d

    def reset_stats(self):
        self._stats = {"candidates": 0, "placed": 0, "dropped": 0,
                       "ms": 0.0, "layers": 0, "measured": 0,
                       "thinned": 0, "capped": 0, "budget_hit": False,
                       "pan_reuse": 0}

    def anchor_errors(self):
        return tuple(self._anchor_errors)

    def clear_errors(self):
        del self._anchor_errors[:]

    def invalidate(self, layer=None):
        self._fm_cache.clear()
        self._size_cache.clear()
        self._pan = None
        if layer is not None:
            invalidate_label_cache(layer)

    def font_key(self, style):
        return style.font_key() + (self._dpi_key(), self._font_family)

    def font_metrics(self, style):
        key = self.font_key(style)
        fm = self._fm_cache.get(key)
        if fm is None:
            font = style_font(style, self._font_family)
            if self._device is not None:
                try:
                    fm = QFontMetricsF(font, self._device)
                except Exception:
                    exc_note("font_metrics @ ggis/render/labeling.py:687")
                    fm = QFontMetricsF(font)
            else:
                fm = QFontMetricsF(font)
            self._fm_cache[key] = fm
        return fm

    def _dpi_key(self):
        if self._device is not None:
            if self._device_dpi > 0:
                return int(round(self._device_dpi))
            for getter in ("logicalDpiY", "logicalDpiX"):
                try:
                    v = getattr(self._device, getter)()
                    if v:
                        return int(round(float(v)))
                except Exception:
                    exc_note("_dpi_key @ ggis/render/labeling.py:704")
                    continue
        return LabelEngine._screen_dpi()

    @staticmethod
    def _screen_dpi():
        try:
            from PySide6.QtGui import QGuiApplication
            scr = QGuiApplication.primaryScreen()
            if scr is None:
                return 96
            return int(round(scr.logicalDotsPerInch()))
        except Exception:
            exc_note("_screen_dpi @ ggis/render/labeling.py:716")
            return 96

    def text_size(self, text, style):
        key = self.font_key(style)
        sc = self._size_cache.get(key)
        if sc is None:
            sc = {}
            self._size_cache[key] = sc
        v = sc.get(text)
        if v is None:
            fm = self.font_metrics(style)
            v = (float(fm.horizontalAdvance(text)), float(fm.height()))
            if len(sc) > 400000:
                sc.clear()
            sc[text] = v
        return v

    def _measure(self, p, idx=None):
        n = int(p.fid.shape[0])
        if p.tw is None:
            p.tw = np.empty(n, dtype=np.float64)
            p.th = np.empty(n, dtype=np.float64)
            p.texts = [""] * n
        fm = p.fm
        fm_h = p.fm_h
        sc = p.sc
        texts_all = p.texts_all
        tw = p.tw
        th = p.th
        texts = p.texts
        fid = p.fid
        n_meas = 0
        it = range(n) if idx is None else idx
        for j in it:
            t = texts_all[int(fid[j])]
            texts[j] = t
            v = sc.get(t)
            if v is None:
                v = (float(fm.horizontalAdvance(t)), fm_h)
                n_meas += 1
                if len(sc) > 400000:
                    sc.clear()
                sc[t] = v
            tw[j] = v[0]
            th[j] = v[1]
        return n_meas

    def _pan_match(self, fr, items, w, h, sx, sy, obstacles, cap, budget):
        if fr.w != w or fr.h != h:
            return False
        if fr.sx > 0 and sx > 0:
            _r = sx / fr.sx
            if _r < _PAN_MATCH_SCALE_MIN or _r > _PAN_MATCH_SCALE_MAX:
                return False
        else:
            if abs(fr.sx - sx) > 1e-6 * max(1.0, abs(sx)):
                return False
        if fr.sy > 0 and sy > 0:
            _r = sy / fr.sy
            if _r < _PAN_MATCH_SCALE_MIN or _r > _PAN_MATCH_SCALE_MAX:
                return False
        else:
            if abs(fr.sy - sy) > 1e-6 * max(1.0, abs(sy)):
                return False
        if fr.cap != cap or fr.budget != budget:
            return False
        if (fr.obstacles is None) != (obstacles is None):
            return False
        if fr.obstacles is not None and fr.obstacles != obstacles:
            return False
        if len(fr.items) != len(items):
            return False
        for a, b in zip(fr.items, items):
            if a[0] is not b[0] or a[1] is not b[1] or a[2] is not b[2]:
                return False
            if a[3] != b[3]:
                return False
            if a[4] is not b[4]:
                return False
        return True

    def _store_pan(self, items, w, h, sx, sy, obstacles, cap, budget, dec):
        self._pan = _PanFrame(w, h, sx, sy, cap, budget, obstacles,
                              tuple(items), dec)

    def _place_pan(self, fr, parts, w, h, sx, sy, obstacles, budget_ms,
                   limit):
        dec_old = fr.dec
        dec_new = {}
        kept = []
        new_parts = []
        n_meas = 0
        for p in parts:
            sel_l = p.sel.tolist()
            px_l = p.px.tolist()
            py_l = p.py.tolist()
            lid = p.lid
            todo = []
            for j, a in enumerate(sel_l):
                key = (lid, a)
                d = dec_old.get(key, _UNSET)
                if d is _UNSET:
                    todo.append(j)
                    continue
                dec_new[key] = d
                if d is None:
                    continue
                pl = d.pl
                ax = px_l[j]
                ay = py_l[j]
                pl.rect = (ax + d.dx0, ay + d.dy0, ax + d.dx1, ay + d.dy1)
                pl.anchor = (ax, ay)
                kept.append(pl)
            if todo:
                n_meas += self._measure(p, todo)
                new_parts.append((p, np.asarray(todo, dtype=np.intp)))

        n_kept = len(kept)
        n_new = 0
        rem = limit - n_kept
        if new_parts:
            n_new = int(sum(int(idx.size) for _p, idx in new_parts))
        if new_parts and rem > 0:
            PX = np.concatenate([p.px[idx] for p, idx in new_parts])
            PY = np.concatenate([p.py[idx] for p, idx in new_parts])
            TW = np.concatenate([p.tw[idx] for p, idx in new_parts])
            TH = np.concatenate([p.th[idx] for p, idx in new_parts])
            AANG = np.concatenate([p.ang[idx] for p, idx in new_parts])
            RANK = np.concatenate([p.rank[idx] for p, idx in new_parts])
            WGT = np.concatenate([p.wgt[idx] for p, idx in new_parts])
            FID = np.concatenate([p.fid[idx] for p, idx in new_parts])
            AID = np.concatenate([p.sel[idx] for p, idx in new_parts])
            flat_txt = []
            flat_pos = []
            flat_sty = []
            flat_lid = []
            for p, idx in new_parts:
                k = int(idx.size)
                flat_txt.extend([p.texts[int(j)] for j in idx.tolist()])
                flat_pos.extend([p.positions] * k)
                flat_sty.extend([p.style] * k)
                flat_lid.extend([p.lid] * k)
            order = np.lexsort((-WGT, RANK))
            if int(order.size) > rem:
                order = order[:rem]
            olist = order.tolist()
            obs = list(obstacles or [])
            obs.extend(pl.rect for pl in kept)
            kept.extend(self._greedy(
                w, h,
                PX[order].tolist(), PY[order].tolist(),
                TW[order].tolist(), TH[order].tolist(),
                AANG[order].tolist(),
                [flat_sty[i] for i in olist],
                [flat_pos[i] for i in olist],
                FID[order].tolist(),
                [flat_lid[i] for i in olist],
                [flat_txt[i] for i in olist],
                RANK[order].tolist(), obs,
                budget_ms=budget_ms,
                aid=AID[order].tolist(), dec=dec_new))
        self._stats["measured"] = n_meas
        self._stats["thinned"] = 0
        self._stats["capped"] = max(0, n_new - max(rem, 0))
        self._stats["pan_reuse"] = n_kept
        self._store_pan(fr.items, w, h, sx, sy, obstacles, fr.cap,
                        fr.budget, dec_new)
        return kept

    @staticmethod
    def _cache_of(layer):
        c = layer.__dict__.get("_ggs_label_cache")
        if c is None:
            c = {}
            try:
                layer.__dict__["_ggs_label_cache"] = c
            except Exception:
                exc_note("_cache_of @ ggis/render/labeling.py:940")
                pass
        return c

    @staticmethod
    def _visible_mask(layer, fids):
        try:
            sub = layer.subset_fids()
        except Exception:
            exc_note("_visible_mask @ ggis/render/labeling.py:956")
            return None
        if sub is None:
            return None
        import numpy as np
        try:
            return np.isin(fids, np.fromiter(sub, dtype=fids.dtype,
                                             count=len(sub)))
        except Exception:
            exc_note("_visible_mask @ ggis/render/labeling.py:964")
            try:
                return np.fromiter((int(f) in sub for f in fids.tolist()),
                                   dtype=bool, count=int(fids.size))
            except Exception:
                exc_note("_visible_mask @ ggis/render/labeling.py:968")
                return None

    def _texts(self, layer, style):
        import re as _re
        from ggis.core.expr import label_expr as _le
        attrs = layer.attrs()
        n_feat = layer.feature_count()
        field = style.field
        fmt = style.formatter
        is_template = "[" in field
        pattern = _re.compile(r"\[([\w\u4e00-\u9fff]+)\]") if is_template else None
        use_expr = bool(is_template) and _le.has_new_syntax(field)
        use_py = _le.is_python_expr(field)
        key = ("texts", field, fmt)
        c = self._cache_of(layer)
        hit = c.get(key)
        if hit is not None and hit[0] is attrs and hit[2] == n_feat:
            return hit[1]
        out = []
        if field:
            for d in attrs:
                if use_py:
                    try:
                        v = _le.eval_label_python(field, d)
                    except Exception:
                        exc_note("_texts @ ggis/render/labeling.py:1013")
                        v = ""
                elif use_expr:
                    try:
                        v = _le.eval_label_expression(field, d)
                    except Exception:
                        exc_note("_texts @ ggis/render/labeling.py:1020")
                        v = ""
                elif is_template:
                    def _repl(m):
                        name = m.group(1)
                        if name not in d:
                            return ""
                        v = d[name]
                        return "" if v is None else str(v)
                    try:
                        v = pattern.sub(_repl, field)
                    except Exception:
                        exc_note("_texts @ ggis/render/labeling.py:1034")
                        v = ""
                else:
                    try:
                        v = d.get(field)
                    except Exception:
                        exc_note("_texts @ ggis/render/labeling.py:1039")
                        v = None
                if v is None or v == "":
                    out.append("")
                    continue
                if fmt is not None:
                    try:
                        v = fmt(v)
                    except Exception:
                        exc_note("_texts @ ggis/render/labeling.py:1047")
                        pass
                out.append(v if isinstance(v, str) else str(v))
        if len(out) < n_feat:
            out.extend([""] * (n_feat - len(out)))
        c[key] = (attrs, out, n_feat)
        return out

    def _anchors(self, layer, style, dst_crs=None):
        kind = layer.base_kind() or "polygon"
        n_feat = layer.feature_count()
        src_crs = None
        try:
            src_crs = layer.crs()
        except Exception:
            exc_note("_anchors @ ggis/render/labeling.py:1073")
            pass
        tf = crs_transformer(src_crs, dst_crs) if dst_crs is not None else None
        ckey = crs_pair_key(src_crs, dst_crs) if tf is not None else ""
        key = ("anchors", kind, n_feat,
               round(style.px_of("repeat_px"), 2), ckey)
        c = self._cache_of(layer)
        hit = c.get(key)
        if hit is not None:
            return hit[1]

        if kind == "point":
            from .painter import _xy_cache
            xy, _off, rows, counts = _xy_cache(layer, dst_crs)
            if xy.shape[0] and rows.size:
                if counts.size and int(counts.max()) == 1:
                    px = xy[rows, 0]
                    py = xy[rows, 1]
                    ffid = np.arange(rows.size, dtype=np.int64)
                else:
                    ffid = np.repeat(np.arange(counts.size, dtype=np.int64),
                                     counts)
                    px = xy[rows[ffid], 0]
                    py = xy[rows[ffid], 1]
                zero_i = np.zeros(px.shape[0], dtype=np.int8)
                data = (ffid, px, py,
                        np.zeros(px.shape[0], dtype=np.float32),
                        np.zeros(px.shape[0], dtype=np.float64),
                        zero_i)
            else:
                e = np.zeros(0)
                data = (np.zeros(0, dtype=np.int64), e, e,
                        np.zeros(0, dtype=np.float32), e,
                        np.zeros(0, dtype=np.int8))
            c[key] = (None, data)
            return data

        geoms = layer.geoms()
        is_poly = (kind == "polygon")
        fracs = (0.5,) if is_poly else ((0.5,) if style.px_of("repeat_px") <= 0
                                        else (0.25, 0.5, 0.75))
        fids, xs, ys, angs, sizes = [], [], [], [], []
        for i, g in enumerate(geoms):
            if g is None or getattr(g, "is_empty", True):
                continue
            try:
                if is_poly:
                    p = g.representative_point()
                    fids.append(i)
                    xs.append(p.x)
                    ys.append(p.y)
                    angs.append(0.0)
                    sizes.append(math.sqrt(max(0.0, float(g.area))))
                    continue
                L = float(g.length)
                if not (L > 0):
                    continue
                for f in fracs:
                    p = g.interpolate(f, normalized=True)
                    a = g.interpolate(max(0.0, f - 0.02), normalized=True)
                    b = g.interpolate(min(1.0, f + 0.02), normalized=True)
                    ang = -math.degrees(math.atan2(b.y - a.y, b.x - a.x))
                    if ang > 90.0:
                        ang -= 180.0
                    elif ang < -90.0:
                        ang += 180.0
                    fids.append(i)
                    xs.append(p.x)
                    ys.append(p.y)
                    angs.append(ang if abs(ang) >= _ROTATE_THRESHOLD else 0.0)
                    sizes.append(L)
            except Exception as e:
                exc_note("_anchors @ ggis/render/labeling.py:1156")
                if len(self._anchor_errors) < 8:
                    self._anchor_errors.append(
                        "fid=%s %s: %s" % (i, type(e).__name__, e))
                continue

        rank = 2 if is_poly else 1
        xs_arr = np.asarray(xs, dtype=np.float64)
        ys_arr = np.asarray(ys, dtype=np.float64)
        sizes_arr = np.asarray(sizes, dtype=np.float64)
        if tf is not None and xs_arr.size:
            try:
                tx, ty = tf.transform(xs_arr, ys_arr)
                xs_arr = np.asarray(tx, dtype=np.float64)
                ys_arr = np.asarray(ty, dtype=np.float64)
            except Exception:
                exc_note("_anchors @ ggis/render/labeling.py:1172")
                pass
            f = crs_scale_factor(src_crs, dst_crs)
            if f > 1e-12:
                sizes_arr = sizes_arr / f
        data = (np.asarray(fids, dtype=np.int64),
                xs_arr,
                ys_arr,
                np.asarray(angs, dtype=np.float32),
                sizes_arr,
                np.full(len(fids), rank, dtype=np.int8))
        c[key] = (None, data)
        return data

    def place(self, settings, layers, obstacles=None, budget_ms=None,
              candidate_cap=None, pan_reuse=None):
        t0 = time.perf_counter()
        self.reset_stats()
        if settings is None or not settings.is_ready():
            return []
        w = float(settings.output_width())
        h = float(settings.output_height())
        if w <= 0 or h <= 0:
            return []
        if pan_reuse is None:
            pan_reuse = candidate_cap is not None

        mupp = 1.0
        try:
            mupp = float(settings.map_units_per_pixel())
        except Exception:
            exc_note("place @ ggis/render/labeling.py:1218")
            pass
        if not (mupp > 0):
            mupp = 1.0
        scale_denom = 0.0
        try:
            scale_denom = float(settings.scale())
        except Exception:
            exc_note("place @ ggis/render/labeling.py:1225")
            pass

        ext = settings.extent()
        xmin = float(ext.xmin)
        ymax = float(ext.ymax)
        sx = w / max(float(ext.width()), 1e-12)
        sy = h / max(float(ext.height()), 1e-12)

        parts = []
        sig_items = []
        n_layers = 0
        for item in layers or []:
            try:
                layer, style = item
            except Exception:
                exc_note("place @ ggis/render/labeling.py:1245")
                continue
            if layer is None or style is None or not style.enabled:
                continue
            if not style.field:
                continue
            if not style.scale_ok(scale_denom):
                continue
            try:
                if not layer.is_valid() or not layer.is_visible():
                    continue
            except Exception:
                exc_note("place @ ggis/render/labeling.py:1256")
                pass

            kind = layer.base_kind() or "polygon"
            positions = tuple(_POS_CODE.get(p, _POS_CENTER)
                              for p in style.positions_for(kind))
            fm = self.font_metrics(style)
            fkey = self.font_key(style)
            sc = self._size_cache.get(fkey)
            if sc is None:
                sc = {}
                self._size_cache[fkey] = sc
            fm_h = float(fm.height())
            texts_all = self._texts(layer, style)
            anchors = self._anchors(layer, style, settings.destination_crs())
            fids, ax, ay, aang, asize, arank = anchors
            n = int(ax.shape[0])
            if n == 0:
                continue
            n_feat = len(texts_all)
            if int(fids.max()) >= n_feat:
                ok = fids < n_feat
                if not ok.any():
                    continue
                fids = fids[ok]
                ax = ax[ok]
                ay = ay[ok]
                aang = aang[ok]
                asize = asize[ok]
                arank = arank[ok]
                n = int(ax.shape[0])
            if n == 0:
                continue

            px = (ax - xmin) * sx
            py = (ymax - ay) * sy

            pad = 240.0
            keep = ((px >= -pad) & (px <= w + pad) &
                    (py >= -pad) & (py <= h + pad))
            _min_px = style.px_of("min_size_px")
            if _min_px > 0 and kind != "point":
                px_size = asize * min(sx, sy)
                keep = keep & (px_size >= _min_px)
            fid_list = fids.tolist()
            tmask = np.fromiter(
                (bool(texts_all[k]) for k in fid_list),
                dtype=bool, count=n)
            keep = keep & tmask
            vmask = self._visible_mask(layer, fids)
            if vmask is not None:
                keep = keep & vmask
            if not keep.any():
                continue

            sel = np.nonzero(keep)[0]
            lim = style.max_labels
            if lim and sel.size > lim:
                order = np.argsort(-asize[sel])[:lim]
                order.sort()
                sel = sel[order]

            p = _Part()
            p.sel = sel
            p.px = px[sel]
            p.py = py[sel]
            p.ang = aang[sel].astype(np.float64)
            p.rank = arank[sel].astype(np.float64)
            p.wgt = asize[sel].astype(np.float64)
            p.fid = fids[sel]
            p.positions = positions
            p.style = style
            p.lid = layer.id()
            p.texts_all = texts_all
            p.fkey = fkey
            p.fm = fm
            p.fm_h = fm_h
            p.sc = sc
            parts.append(p)
            try:
                _sub = layer.subset_fids()
            except Exception:
                exc_note("place @ ggis/render/labeling.py:1358")
                _sub = None
            sig_items.append((layer, texts_all, anchors,
                              style.place_key(), _sub))
            n_layers += 1

        if not parts:
            self._stats["ms"] = (time.perf_counter() - t0) * 1000.0
            self._pan = None
            return []

        limit = self.max_candidates
        if candidate_cap is not None:
            limit = min(limit, max(0, int(candidate_cap)))

        try:
            _uniq = len({p.lid for p in parts}) == len(parts)
        except Exception:
            exc_note("place @ ggis/render/labeling.py:1384")
            _uniq = False
        _fr = self._pan
        if (pan_reuse and self._device is None and _uniq
                and _fr is not None
                and self._pan_match(_fr, sig_items, w, h, sx, sy,
                                    obstacles, candidate_cap, budget_ms)):
            best = self._place_pan(_fr, parts, w, h, sx, sy, obstacles,
                                   budget_ms, limit)
            _tot = int(sum(int(p.px.shape[0]) for p in parts))
            self._stats["candidates"] = _tot
            self._stats["placed"] = len(best)
            self._stats["dropped"] = _tot - len(best)
            self._stats["layers"] = n_layers
            self._stats["ms"] = (time.perf_counter() - t0) * 1000.0
            return best

        n_measured = 0
        for p in parts:
            n_measured += self._measure(p)

        PX = np.concatenate([p.px for p in parts])
        PY = np.concatenate([p.py for p in parts])
        TW = np.concatenate([p.tw for p in parts])
        TH = np.concatenate([p.th for p in parts])
        AANG = np.concatenate([p.ang for p in parts])
        RANK = np.concatenate([p.rank for p in parts])
        WGT = np.concatenate([p.wgt for p in parts])
        FID_ALL = np.concatenate([p.fid for p in parts])
        AID_ALL = np.concatenate([p.sel for p in parts])
        total_all = int(PX.shape[0])

        flat_txt = []
        flat_pos = []
        flat_sty = []
        flat_lid = []
        for p in parts:
            k = int(p.px.shape[0])
            flat_txt.extend(p.texts)
            flat_pos.extend([p.positions] * k)
            flat_sty.extend([p.style] * k)
            flat_lid.extend([p.lid] * k)

        order = np.lexsort((-WGT, RANK))
        n_before = int(order.size)
        thinned = 0
        if candidate_cap is not None and n_before > limit:
            order = self._thin_by_grid(order, PX, PY, TW, TH)
            thinned = n_before - int(order.size)
        n_after_thin = int(order.size)
        if n_after_thin > limit:
            order = order[:limit]
        self._stats["thinned"] = thinned
        self._stats["capped"] = n_after_thin - int(order.size)
        olist = order.tolist()

        PXl = PX[order].tolist()
        PYl = PY[order].tolist()
        TWl = TW[order].tolist()
        THl = TH[order].tolist()
        ANGl = AANG[order].tolist()
        RANKl = RANK[order].tolist()
        FIDl = FID_ALL[order].tolist()
        AIDl = AID_ALL[order].tolist()
        TXTl = [flat_txt[i] for i in olist]
        STYl = [flat_sty[i] for i in olist]
        POSl = [flat_pos[i] for i in olist]
        LIDl = [flat_lid[i] for i in olist]

        dec_new = {} if pan_reuse else None
        best = self._greedy(w, h, PXl, PYl, TWl, THl, ANGl, STYl, POSl,
                            FIDl, LIDl, TXTl, RANKl, obstacles,
                            budget_ms=budget_ms, aid=AIDl, dec=dec_new)
        self._stats["candidates"] = total_all
        self._stats["placed"] = len(best)
        self._stats["dropped"] = total_all - len(best)
        self._stats["layers"] = n_layers
        self._stats["measured"] = n_measured
        self._stats["ms"] = (time.perf_counter() - t0) * 1000.0
        if dec_new is not None and self._device is None and _uniq:
            self._store_pan(sig_items, w, h, sx, sy, obstacles,
                            candidate_cap, budget_ms, dec_new)
        return best

    def _thin_by_grid(self, order, PX, PY, TW, TH, k=None):
        if k is None:
            k = LABEL_GRID_K
        n = int(order.size)
        if n == 0 or k <= 0:
            return order
        widths = sorted(TW)
        med = widths[len(widths) // 2]
        cell = max(_MIN_CELL, min(240.0, med + 8.0))
        inv = 1.0 / cell
        raw = (np.floor(PY[order] * inv).astype(np.int64) * np.int64(1 << 22)
               + np.floor(PX[order] * inv).astype(np.int64))
        _uniq, key = np.unique(raw, return_inverse=True)
        key = np.asarray(key).reshape(-1)
        by_key = np.argsort(key, kind="stable")
        skey = key[by_key]
        first = np.empty(n, dtype=bool)
        first[0] = True
        np.not_equal(skey[1:], skey[:-1], out=first[1:])
        starts = np.maximum.accumulate(np.where(first, np.arange(n), 0))
        within = np.empty(n, dtype=np.int64)
        within[by_key] = np.arange(n) - starts
        return order[within < k]

    def _greedy(self, w, h, PX, PY, TW, TH, ANG, STY, POS, FID, LID, TXT,
                RANK, obstacles, budget_ms=None, aid=None, dec=None):
        n = len(PX)
        if n == 0:
            return []

        check_every = 0
        t_budget0 = 0.0
        budget_hit = False
        if budget_ms:
            check_every = max(64, n // 32)
            t_budget0 = time.perf_counter()

        widths = sorted(TW)
        med = widths[len(widths) // 2]
        cell = max(_MIN_CELL, min(240.0, med + 8.0))
        inv = 1.0 / cell
        nbx = int(w * inv) + 4
        nby = int(h * inv) + 4
        bx_max = nbx - 1
        by_max = nby - 1

        cells = [None] * (nbx * nby)
        R = []

        def _insert(x0, y0, x1, y1):
            k = len(R)
            R.append((x0, y0, x1, y1))
            bx0 = int(x0 * inv)
            bx1 = int(x1 * inv)
            by0 = int(y0 * inv)
            by1 = int(y1 * inv)
            if bx0 < 0:
                bx0 = 0
            elif bx0 > bx_max:
                bx0 = bx_max
            if bx1 < 0:
                bx1 = 0
            elif bx1 > bx_max:
                bx1 = bx_max
            if by0 < 0:
                by0 = 0
            elif by0 > by_max:
                by0 = by_max
            if by1 < 0:
                by1 = 0
            elif by1 > by_max:
                by1 = by_max
            for by in range(by0, by1 + 1):
                row = by * nbx
                for bx in range(bx0, bx1 + 1):
                    c = cells[row + bx]
                    if c is None:
                        cells[row + bx] = [k]
                    else:
                        c.append(k)

        for ob in obstacles or []:
            try:
                ax0, ay0, ax1, ay1 = (float(ob[0]), float(ob[1]),
                                      float(ob[2]), float(ob[3]))
            except Exception:
                exc_note("_greedy @ ggis/render/labeling.py:1610")
                continue
            _insert(min(ax0, ax1), min(ay0, ay1),
                    max(ax0, ax1), max(ay0, ay1))

        placed = []
        append = placed.append
        for i in range(n):
            if check_every and i and (i % check_every) == 0:
                if (time.perf_counter() - t_budget0) * 1000.0 >= budget_ms:
                    budget_hit = True
                    break
            ax = PX[i]
            ay = PY[i]
            tw = TW[i]
            th = TH[i]
            style = STY[i]
            buf = style.px_of("buffer")
            if buf < 0.0:
                buf = 0.0
            ox = style.offset_x
            oy = style.offset_y
            p_right = buf + ox + tw * 0.5
            p_left = buf - ox + tw * 0.5
            p_top = buf - oy + th * 0.5
            p_bottom = buf + oy + th * 0.5
            ang = ANG[i]
            hw = tw * 0.5
            hh = th * 0.5
            if ang:
                ca = abs(math.cos(math.radians(ang)))
                sa = abs(math.sin(math.radians(ang)))
                ex = hw * ca + hh * sa
                ey = hw * sa + hh * ca
            else:
                ex = hw
                ey = hh

            hit_rect = None
            hit_pos = 0
            for pc in POS[i]:
                if pc == _POS_RIGHT:
                    cx = ax + p_right
                    cy = ay + oy
                elif pc == _POS_TOP:
                    cx = ax + ox
                    cy = ay - p_top
                elif pc == _POS_BOTTOM:
                    cx = ax + ox
                    cy = ay + p_bottom
                elif pc == _POS_LEFT:
                    cx = ax - p_left
                    cy = ay + oy
                else:
                    cx = ax + ox
                    cy = ay + oy
                x0 = cx - ex
                y0 = cy - ey
                x1 = cx + ex
                y1 = cy + ey

                bx0 = int(x0 * inv)
                bx1 = int(x1 * inv)
                by0 = int(y0 * inv)
                by1 = int(y1 * inv)
                if bx0 < 0 or bx1 > bx_max or by0 < 0 or by1 > by_max:
                    if bx0 < 0:
                        bx0 = 0
                    elif bx0 > bx_max:
                        bx0 = bx_max
                    if bx1 < 0:
                        bx1 = 0
                    elif bx1 > bx_max:
                        bx1 = bx_max
                    if by0 < 0:
                        by0 = 0
                    elif by0 > by_max:
                        by0 = by_max
                    if by1 < 0:
                        by1 = 0
                    elif by1 > by_max:
                        by1 = by_max

                clash = False
                if bx0 == bx1 and by0 == by1:
                    cc = cells[by0 * nbx + bx0]
                    if cc:
                        for r in cc:
                            rx0, ry0, rx1, ry1 = R[r]
                            if not (x1 <= rx0 or x0 >= rx1 or
                                    y1 <= ry0 or y0 >= ry1):
                                clash = True
                                break
                else:
                    for by in range(by0, by1 + 1):
                        row = by * nbx
                        for bx in range(bx0, bx1 + 1):
                            cc = cells[row + bx]
                            if not cc:
                                continue
                            for r in cc:
                                rx0, ry0, rx1, ry1 = R[r]
                                if not (x1 <= rx0 or x0 >= rx1 or
                                        y1 <= ry0 or y0 >= ry1):
                                    clash = True
                                    break
                            if clash:
                                break
                        if clash:
                            break
                if not clash:
                    hit_rect = (x0, y0, x1, y1)
                    hit_pos = pc
                    break

            if hit_rect is None:
                if dec is not None:
                    dec[(LID[i], aid[i])] = None
                continue

            _insert(hit_rect[0], hit_rect[1], hit_rect[2], hit_rect[3])
            pl = PlacedLabel(LID[i], FID[i], TXT[i], hit_rect,
                             (ax, ay), ang, _POS_NAME.get(hit_pos, ""),
                             style, int(RANK[i]))
            append(pl)
            if dec is not None:
                dec[(LID[i], aid[i])] = _PanLabel(
                    hit_rect[0] - ax, hit_rect[1] - ay,
                    hit_rect[2] - ax, hit_rect[3] - ay, pl)
        self._stats["budget_hit"] = budget_hit
        return placed

    def place_candidates(self, settings, candidates, style=None):
        style = style or LabelStyle(enabled=True)
        self.reset_stats()
        if not candidates or settings is None or not settings.is_ready():
            return []
        t0 = time.perf_counter()
        w = float(settings.output_width())
        h = float(settings.output_height())
        ext = settings.extent()
        sx = w / max(ext.width(), 1e-12)
        sy = h / max(ext.height(), 1e-12)
        cs = list(candidates)
        order = sorted(range(len(cs)),
                       key=lambda i: (cs[i].rank, -cs[i].weight, i))
        PX, PY, TW, TH, ANG, STY, POS, FID, LID, TXT, RANK = (
            [], [], [], [], [], [], [], [], [], [], [])
        fm = self.font_metrics(style)
        for i in order:
            c = cs[i]
            if not c.text:
                continue
            PX.append((c.x - ext.xmin) * sx)
            PY.append((ext.ymax - c.y) * sy)
            TW.append(float(fm.horizontalAdvance(c.text)))
            TH.append(float(fm.height()))
            ANG.append(float(c.angle))
            STY.append(style)
            POS.append(tuple(_POS_CODE.get(p, _POS_CENTER)
                             for p in style.positions_for(c.kind)))
            FID.append(c.fid)
            LID.append("")
            TXT.append(c.text)
            RANK.append(c.rank)
        best = self._greedy(w, h, PX, PY, TW, TH, ANG, STY, POS, FID, LID,
                            TXT, RANK, None)
        self._stats.update({"candidates": len(PX), "placed": len(best),
                            "dropped": len(PX) - len(best), "layers": 1,
                            "measured": len(PX),
                            "ms": (time.perf_counter() - t0) * 1000.0})
        return best

    @staticmethod
    def overlaps(placed, tolerance=0.0):
        n = len(placed)
        if n < 2:
            return 0
        if n > 3000:
            return _overlaps_bucketed(placed, tolerance)
        bad = 0
        for i in range(n):
            a = placed[i].rect
            for j in range(i + 1, n):
                b = placed[j].rect
                if (min(a[2], b[2]) - max(a[0], b[0]) - tolerance > 0 and
                        min(a[3], b[3]) - max(a[1], b[1]) - tolerance > 0):
                    bad += 1
        return bad


def _overlaps_bucketed(placed, tolerance=0.0):
    sizes = sorted((p.rect[2] - p.rect[0]) + (p.rect[3] - p.rect[1])
                   for p in placed)
    cell = max(8.0, sizes[len(sizes) // 2] * 0.5 + tolerance + 1.0)
    grid = {}
    bad = 0
    for idx, p in enumerate(placed):
        x0, y0, x1, y1 = p.rect
        bx0 = int(math.floor(x0 / cell))
        bx1 = int(math.floor(x1 / cell))
        by0 = int(math.floor(y0 / cell))
        by1 = int(math.floor(y1 / cell))
        hits = set()
        for by in range(by0, by1 + 1):
            for bx in range(bx0, bx1 + 1):
                lst = grid.get((bx, by))
                if not lst:
                    continue
                for k in lst:
                    if k in hits:
                        continue
                    hits.add(k)
                    q = placed[k].rect
                    if (min(x1, q[2]) - max(x0, q[0]) - tolerance > 0 and
                            min(y1, q[3]) - max(y0, q[1]) - tolerance > 0):
                        bad += 1
        for by in range(by0, by1 + 1):
            for bx in range(bx0, bx1 + 1):
                grid.setdefault((bx, by), []).append(idx)
    return bad


def make_halo_pen(color, width):
    pen = QPen(color if isinstance(color, QColor) else QColor(color))
    pen.setWidthF(float(width))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def stroke_text_path(painter, path, pen):
    if path.isEmpty():
        return
    painter.save()
    painter.setRenderHint(painter.RenderHint.Antialiasing, True)
    painter.setPen(pen)
    painter.strokePath(path, pen)
    painter.restore()


def draw_labels(painter, placed, opacity=1.0, font_family=""):
    if not placed:
        return 0
    groups = {}
    for pl in placed:
        g = groups.get(id(pl.style))
        if g is None:
            groups[id(pl.style)] = (pl.style, [pl])
        else:
            g[1].append(pl)

    painter.save()
    painter.setRenderHint(painter.RenderHint.TextAntialiasing, True)
    drawn = 0
    for style, items in groups.values():
        font = style_font(style, font_family)
        dev = painter.device()
        try:
            fm = QFontMetricsF(font, dev) if dev is not None \
                else QFontMetricsF(font)
        except Exception:
            exc_note("draw_labels @ ggis/render/labeling.py:1922")
            fm = QFontMetricsF(font)
        base = (fm.ascent() - fm.descent()) * 0.5
        color = QColor(style.color)
        if opacity < 1.0:
            color.setAlphaF(max(0.0, min(1.0, opacity)))
        brush = QBrush(color)
        halo = None
        _hw = style.px_of("halo_width")
        if _hw > 0:
            halo = make_halo_pen(style.halo_color, _hw * 2.0)
        painter.setFont(font)
        for pl in items:
            x0, y0, x1, y1 = pl.rect
            txt = pl.text
            if pl.angle:
                cx = (x0 + x1) * 0.5
                cy = (y0 + y1) * 0.5
                painter.translate(cx, cy)
                painter.rotate(pl.angle)
                if halo is not None:
                    path = QPainterPath()
                    path.addText(QPointF(-(x1 - x0) * 0.5, base), font, txt)
                    stroke_text_path(painter, path, halo)
                    painter.fillPath(path, brush)
                else:
                    painter.setPen(QPen(color))
                    painter.drawText(QPointF(-(x1 - x0) * 0.5, base), txt)
                painter.rotate(-pl.angle)
                painter.translate(-cx, -cy)
            else:
                if halo is not None:
                    path = QPainterPath()
                    path.addText(QPointF(x0, (y0 + y1) * 0.5 + base),
                                 font, txt)
                    stroke_text_path(painter, path, halo)
                    painter.fillPath(path, brush)
                else:
                    painter.setPen(QPen(color))
                    painter.drawText(QPointF(x0, (y0 + y1) * 0.5 + base), txt)
            drawn += 1
    painter.restore()
    return drawn
