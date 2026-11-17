# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import math

import numpy as np

from ggis.core.style.style_library import RAMP_STOPS as _ramp_stops
from ggis.core.style.style_library import (LEGACY_STOPS as _legacy_stops)
from ggis.core.model.layer import data_version as _data_version
from .symbol import GgsSymbol, PALETTE
from .symbol import px_to_unit

__all__ = [
    "GgsFeatureRenderer", "GgsSingleSymbolRenderer",
    "GgsCategorizedRenderer", "GgsGraduatedRenderer",
    "GgsRuleBasedRenderer", "GgsRule",
    "default_renderer", "RAMP_NAMES", "classify", "make_ramp",
]

MAX_CLASSES = 1024

OTHERS_FILL = "#9C9C9C"


class _Ramp:
    __slots__ = ("name", "stops")

    def __init__(self, name, stops):
        self.name = name
        self.stops = stops


def _hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


_RAMPS = [_Ramp(_k, list(_stops))
          for _k, _stops in _ramp_stops.items()]
_LEGACY_RAMPS = [_Ramp(_k, list(_st))
                 for _k, _st in _legacy_stops.items()]

RAMP_NAMES = [r.name for r in _RAMPS]


def make_ramp(name, n):
    n = max(1, int(n))
    name = str(name or "")
    if name.startswith("user:"):
        try:
            from ggis.core.style import user_ramps
            hx = user_ramps.hex_stops(name, n)
            if hx:
                return hx
        except Exception:
            exc_note("make_ramp @ ggis/render/renderers.py:100")
            pass
    ramp = None
    for r in _RAMPS + _LEGACY_RAMPS:
        if r.name == name:
            ramp = r
            break
    if ramp is None:
        ramp = _RAMPS[0]
    stops = [_hx(s) for s in ramp.stops]
    if n == 1:
        return ["#%02X%02X%02X" % stops[len(stops) // 2]]
    out = []
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        k = min(int(t), len(stops) - 2)
        f = t - k
        a, b = stops[k], stops[k + 1]
        out.append("#%02X%02X%02X" % (
            round(a[0] + (b[0] - a[0]) * f),
            round(a[1] + (b[1] - a[1]) * f),
            round(a[2] + (b[2] - a[2]) * f)))
    return out


def categorical_colors(n):
    out = []
    for i in range(max(1, int(n))):
        out.append(PALETTE[i % len(PALETTE)])
    return out


def _clean(values):
    a = np.asarray(values, dtype=np.float64)
    a = a[np.isfinite(a)]
    return np.sort(a)


def equal_interval_breaks(values, n):
    a = _clean(values)
    if a.size == 0:
        return [0.0, 1.0]
    lo, hi = float(a[0]), float(a[-1])
    if hi <= lo:
        hi = lo + 1.0
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


def quantile_breaks(values, n):
    a = _clean(values)
    if a.size == 0:
        return [0.0, 1.0]
    qs = np.linspace(0.0, 1.0, n + 1)
    b = np.quantile(a, qs)
    out = [float(x) for x in b]
    return _dedup(out)


def jenks_breaks(values, n, max_iter=24):
    a = _clean(values)
    if a.size == 0:
        return [0.0, 1.0]
    if a.size <= n:
        return _dedup([float(x) for x in a] + [float(a[-1])])
    cent = np.sort(np.quantile(
        a, np.linspace(0.0, 1.0, n + 2)[1:-1]).astype(np.float64))
    for _ in range(max_iter):
        mids = (cent[:-1] + cent[1:]) * 0.5
        idx = np.searchsorted(mids, a, side="right")
        cnt = np.bincount(idx, minlength=n).astype(np.float64)
        sums = np.bincount(idx, weights=a, minlength=n)
        new = np.where(cnt > 0, sums / np.maximum(cnt, 1.0), cent)
        moved = bool(np.max(np.abs(new - cent)) > 1e-9)
        cent = np.sort(new)
        if not moved:
            break
    breaks = [float(a[0])]
    for k in range(n - 1):
        breaks.append(float((cent[k] + cent[k + 1]) * 0.5))
    breaks.append(float(a[-1]))
    return _dedup(breaks)


def std_dev_breaks(values, n=2, factor=1.0):
    a = _clean(values)
    if a.size == 0:
        return [0.0, 1.0]
    mu = float(a.mean())
    sd = float(a.std()) or 1.0
    out = [float(a[0])]
    k = int(n)
    for i in range(-k, k):
        out.append(mu + i * factor * sd)
    out.append(float(a[-1]))
    out = sorted(set(round(x, 10) for x in out))
    return _dedup([float(x) for x in out])


def _dedup(breaks):
    out = []
    for b in breaks:
        if not out or b > out[-1]:
            out.append(b)
    if len(out) < 2:
        out.append(out[0] + 1.0 if out else 1.0)
    return out


CLASSIFY_MODES = ("equal", "quantile", "jenks", "stddev",
                   "pretty", "log")

MODE_LABELS = {"equal": "等间隔", "quantile": "分位数",
               "jenks": "自然断点", "stddev": "标准差",
               "pretty": "美观断点", "log": "对数刻度"}


def pretty_breaks(values, n):
    a = _clean(values)
    if a.size == 0:
        return [0.0, 1.0]
    lo, hi = float(a[0]), float(a[-1])
    if hi <= lo:
        hi = lo + 1.0
    n = max(1, int(n))
    raw = (hi - lo) / n
    if raw <= 0:
        return [lo, hi]
    mag = 10.0 ** math.floor(math.log10(raw))
    step = mag
    for m in (1.0, 2.0, 5.0, 10.0):
        if raw <= m * mag:
            step = m * mag
            break

    def _bounds(st):
        return (math.floor(lo / st) * st, math.ceil(hi / st) * st)

    start, end = _bounds(step)
    cnt = int(round((end - start) / step))
    while cnt > n and step < (hi - lo):
        step *= 2.0
        start, end = _bounds(step)
        cnt = int(round((end - start) / step))
    cnt = max(1, min(cnt, max(n, 1) * 4))
    return _dedup([start + i * step for i in range(cnt + 1)])


def log_breaks(values, n):
    a = _clean(values)
    if a.size == 0:
        return [0.0, 1.0]
    lo, hi = float(a[0]), float(a[-1])
    n = max(1, int(n))
    if lo <= 0:
        return equal_interval_breaks(a, n)
    if hi <= lo:
        hi = lo * 10.0
    l0, l1 = math.log(lo), math.log(hi)
    return _dedup([math.exp(l0 + (l1 - l0) * i / n) for i in range(n + 1)])


def classify(values, n_classes, mode="equal"):
    n = max(1, min(int(n_classes), MAX_CLASSES))
    mode = mode if mode in CLASSIFY_MODES else "equal"
    if mode == "quantile":
        b = quantile_breaks(values, n)
    elif mode == "jenks":
        b = jenks_breaks(values, n)
    elif mode == "stddev":
        b = std_dev_breaks(values, 2)
    elif mode == "pretty":
        b = pretty_breaks(values, n)
    elif mode == "log":
        b = log_breaks(values, n)
    else:
        b = equal_interval_breaks(values, n)
    return _dedup(b)


def _categorized_class_array(layer, field, entries, others_symbol=None,
                             others=True):
    if not field:
        return None
    n = layer.feature_count()
    m = {v: i for i, (v, _s) in enumerate(entries, start=1)}
    others = len(entries) + 1
    arr = np.zeros(n, dtype=np.int32)
    attrs = layer.attrs()
    geoms = layer.geoms()
    for i in range(min(n, len(attrs))):
        g = geoms[i] if i < len(geoms) else None
        if g is None or getattr(g, "is_empty", True):
            continue
        a = attrs[i] if isinstance(attrs[i], dict) else {}
        v = a.get(field)
        if v is None or v == "":
            v = None
        k = m.get(v)
        if k is None:
            if others:
                arr[i] = others
            continue
        arr[i] = k
    return arr


def _graduated_class_array(layer, field, breaks, others=False):
    from ggis.core.model.field import numeric_array
    if not field or len(breaks) < 2:
        return None
    vals = numeric_array(layer, field)
    br = np.asarray(breaks, dtype=np.float64)
    n = len(br) - 1
    idx = np.searchsorted(br, vals, side="right") - 1
    outside = (vals < br[0]) | (vals > br[-1])
    bad = ~np.isfinite(vals)
    idx = np.clip(idx, 0, n - 1)
    arr = (idx + 1).astype(np.int32)
    if others:
        arr[outside | bad] = n + 1
    else:
        arr[bad] = 0
    return arr


def _class_array_plan(layer, r):
    try:
        n = int(layer.feature_count())
    except Exception:
        exc_note("_class_array_plan @ ggis/render/renderers.py:412")
        return None
    if isinstance(r, GgsCategorizedRenderer):
        if not r.field:
            return None
        key = (id(layer), n, r.field, len(r.entries),
               r.others_symbol is not None, _data_version(layer))
        return (_categorized_class_array,
                (layer, r.field, list(r.entries), r.others_symbol), key)
    if isinstance(r, GgsGraduatedRenderer):
        if not r.field or len(r.breaks) < 2:
            return None
        key = (id(layer), n, r.field, tuple(r.breaks),
               r.others_symbol is not None, _data_version(layer))
        return (_graduated_class_array,
                (layer, r.field, list(r.breaks),
                 r.others_symbol is not None), key)
    if isinstance(r, GgsRuleBasedRenderer):
        try:
            r._collect()
            if not r._syms:
                return None
            key = (id(layer), n, _data_version(layer),
                   _rule_tree_sig(r.root))
        except Exception:
            exc_note("_class_array_plan @ ggis/render/renderers.py:438")
            return None

        def _calc(layer_, root_):
            return _rule_class_array(layer_, root_)[0]

        return (_calc, (layer, r.root), key)
    return None


def prewarm_class_array(layer, r=None):
    try:
        from ..exec import guard as _g
        from ..exec import task as _et
        if not (_g.ui_mode() and _g.on_ui_thread()):
            return None
        if r is None:
            r = get_renderer(layer)
        plan = _class_array_plan(layer, r)
        if plan is None:
            return None
        fn, args, key = plan
        if getattr(r, "_cache_key", None) == key and \
                getattr(r, "_cache", None) is not None:
            return None
        if getattr(r, "_prewarm_key", None) == key:
            return None
        r._prewarm_key = key
        t = _et.submit(fn, *args, name="prewarm-class-array", kind="cpu")

        def _store(ev):
            if getattr(r, "_prewarm_key", None) == key:
                r._prewarm_key = None
            arr = ev.get("result")
            if arr is None:
                return
            if r is not get_renderer(layer):
                return
            r._cache_key = key
            r._cache = arr

        def _fail(_ev):
            if getattr(r, "_prewarm_key", None) == key:
                r._prewarm_key = None

        t.on_done(_store)
        t.on_fail(_fail)
        return t
    except Exception:
        exc_note("prewarm_class_array @ ggis/render/renderers.py:495")
        return None


class GgsFeatureRenderer:

    type_name = "single"

    def __init__(self, geometry_kind="point"):
        self.geometry_kind = geometry_kind

    def symbols(self):
        raise NotImplementedError

    def class_array(self, layer):
        return None

    def legend_labels(self, layer=None):
        return [""]

    def legend_items(self, layer=None):
        syms = self.symbols()
        labels = self.legend_labels(layer)
        out = []
        for i, s in enumerate(syms):
            lab = labels[i] if i < len(labels) else str(i + 1)
            out.append((lab, s))
        return out

    def legend_symbols(self):
        return list(self.symbols())

    def clone(self):
        return type(self).from_dict(self.to_dict())

    def to_dict(self):
        return {"type": self.type_name, "kind": self.geometry_kind}

    @staticmethod
    def from_dict(d):
        t = (d or {}).get("type", "single")
        cls = {"single": GgsSingleSymbolRenderer,
               "categorized": GgsCategorizedRenderer,
               "graduated": GgsGraduatedRenderer,
               "rule": GgsRuleBasedRenderer}.get(t)
        if cls is None:
            return GgsSingleSymbolRenderer()
        return cls._load(d)


class GgsSingleSymbolRenderer(GgsFeatureRenderer):

    type_name = "single"

    def __init__(self, symbol=None, geometry_kind="point"):
        super().__init__(geometry_kind)
        self.symbol = symbol or _default_sym(geometry_kind, 0)

    def symbols(self):
        return [self.symbol]

    def legend_symbols(self):
        return [self.symbol]

    def legend_labels(self, layer=None):
        return ["全部要素"]

    def to_dict(self):
        d = super().to_dict()
        d["symbol"] = _sym_to_dict(self.symbol)
        return d

    @staticmethod
    def _load(d):
        r = GgsSingleSymbolRenderer(_sym_from_dict(d.get("symbol")),
                                    d.get("kind", "point"))
        return r


class GgsCategorizedRenderer(GgsFeatureRenderer):

    type_name = "categorized"

    def __init__(self, field="", entries=None, geometry_kind="point",
                 others_symbol=None, others_label="其他", others_visible=True):
        super().__init__(geometry_kind)
        self.field = str(field or "")
        self.entries = list(entries or [])
        self.others_symbol = others_symbol
        self.others_label = others_label
        self.others_visible = bool(others_visible)
        self._cache_key = None
        self._cache = None

    def rebuild(self, layer, max_classes=MAX_CLASSES):
        n = layer.feature_count()
        attrs = layer.attrs()
        counts = {}
        order = []
        for i in range(min(n, len(attrs))):
            a = attrs[i] if isinstance(attrs[i], dict) else {}
            v = a.get(self.field)
            if v is None or v == "":
                v = None
            key = v
            if key not in counts:
                counts[key] = 0
                order.append(key)
            counts[key] += 1
        order.sort(key=lambda k: (-counts[k], str(k)))
        shown = [k for k in order if k is not None][:max_classes]
        colors = categorical_colors(len(shown))
        self.entries = [(v, _default_sym(self.geometry_kind, i,
                                         fill=colors[i]))
                        for i, v in enumerate(shown)]
        has_null = any(k is None for k in order)
        self.others_symbol = (_default_sym(self.geometry_kind, 0,
                                           fill=OTHERS_FILL)
                              if (has_null or len(order) > len(shown))
                              else None)
        self.invalidate()
        prewarm_class_array(layer, self)
        return self

    def invalidate(self):
        self._cache_key = None
        self._cache = None

    def others_fallback(self):
        if self.others_symbol is not None:
            return self.others_symbol
        return _default_sym(self.geometry_kind, 0, fill=OTHERS_FILL)

    def symbols(self):
        out = [s for _v, s in self.entries]
        if self.others_visible:
            out.append(self.others_fallback())
        return out or [_default_sym(self.geometry_kind, 0)]

    def legend_symbols(self):
        out = [s for _v, s in self.entries]
        if self.others_visible:
            out.append(self.others_fallback())
        return out

    def class_array(self, layer):
        if not self.field:
            return None
        key = (id(layer), int(layer.feature_count()), self.field,
               len(self.entries), self.others_symbol is not None,
               bool(self.others_visible),
               _data_version(layer))
        if self._cache_key == key and self._cache is not None:
            return self._cache
        arr = _categorized_class_array(layer, self.field, self.entries,
                                       self.others_symbol,
                                       others=bool(self.others_visible))
        self._cache_key = key
        self._cache = arr
        return arr

    def legend_labels(self, layer=None):
        out = ["" if v is None else str(v) for v, _s in self.entries]
        if self.others_visible:
            out.append(self.others_label)
        return out or ["全部要素"]

    def to_dict(self):
        d = super().to_dict()
        d["field"] = self.field
        d["entries"] = [[v, _sym_to_dict(s)] for v, s in self.entries]
        d["others"] = (_sym_to_dict(self.others_symbol)
                       if self.others_symbol is not None else None)
        d["others_label"] = self.others_label
        d["others_visible"] = bool(self.others_visible)
        return d

    @staticmethod
    def _load(d):
        r = GgsCategorizedRenderer(
            d.get("field", ""),
            [(v, _sym_from_dict(s)) for v, s in (d.get("entries") or [])],
            d.get("kind", "point"),
            _sym_from_dict(d["others"]) if d.get("others") else None,
            d.get("others_label", "其他"),
            others_visible=bool(d.get("others_visible", True)))
        return r


class GgsGraduatedRenderer(GgsFeatureRenderer):

    type_name = "graduated"

    def __init__(self, field="", mode="equal", n_classes=5, ramp="spectral",
                 breaks=None, symbols=None, geometry_kind="point",
                 others_symbol=None, others_label="其他值"):
        super().__init__(geometry_kind)
        self.field = str(field or "")
        self.mode = mode
        self.n_classes = int(n_classes)
        self.ramp = ramp
        self.breaks = list(breaks) if breaks else []
        self.symbols_ = list(symbols) if symbols else []
        self.others_symbol = others_symbol
        self.others_label = others_label
        self._others_checked = others_symbol is not None
        self._cache_key = None
        self._cache = None

    def rebuild(self, layer):
        from ggis.core.model.field import numeric_array
        vals = numeric_array(layer, self.field)
        finite = vals[np.isfinite(vals)]
        self.breaks = classify(finite, self.n_classes, self.mode)
        nb = len(self.breaks) - 1
        self.n_classes = max(1, nb)
        colors = make_ramp(self.ramp, self.n_classes)
        self.symbols_ = [_default_sym(self.geometry_kind, i, fill=colors[i])
                         for i in range(self.n_classes)]
        try:
            lo, hi = float(self.breaks[0]), float(self.breaks[-1])
            outside = int((np.isfinite(vals)
                           & ((vals < lo) | (vals > hi))).sum())
            bad = int((~np.isfinite(vals)).sum())
        except Exception:
            exc_note("rebuild @ ggis/render/renderers.py:790")
            outside, bad = 0, 0
        self.others_symbol = (_default_sym(self.geometry_kind, 0,
                                           fill=OTHERS_FILL)
                              if (outside or bad) else None)
        self.invalidate()
        prewarm_class_array(layer, self)
        return self

    def invalidate(self):
        self._cache_key = None
        self._cache = None

    def ensure_others(self, layer):
        if self.others_symbol is not None:
            return True
        if getattr(self, "_others_checked", False):
            return False
        self._others_checked = True
        try:
            from ggis.core.model.field import numeric_array
            import numpy as _np
            vals = numeric_array(layer, self.field)
            finite = _np.isfinite(vals)
            lo, hi = float(self.breaks[0]), float(self.breaks[-1])
            need = bool((~finite).any()
                        or (finite & ((vals < lo) | (vals > hi))).any())
        except Exception:
            exc_note("ensure_others @ ggis/render/renderers.py:828")
            need = False
        if need:
            self.others_symbol = _default_sym(self.geometry_kind, 0,
                                              fill=OTHERS_FILL)
            self.invalidate()
        return self.others_symbol is not None

    def others_fallback(self):
        if self.others_symbol is not None:
            return self.others_symbol
        return _default_sym(self.geometry_kind, 0, fill=OTHERS_FILL)

    def symbols(self):
        out = list(self.symbols_)
        if self.others_symbol is not None:
            out.append(self.others_fallback())
        return out or [_default_sym(self.geometry_kind, 0)]

    def legend_symbols(self):
        out = list(self.symbols_)
        if self.others_symbol is not None:
            out.append(self.others_fallback())
        return out

    def class_array(self, layer):
        if not self.field or len(self.breaks) < 2:
            return None
        key = (id(layer), int(layer.feature_count()), self.field,
               tuple(self.breaks), self.others_symbol is not None,
               _data_version(layer))
        if self._cache_key == key and self._cache is not None:
            return self._cache
        arr = _graduated_class_array(layer, self.field, self.breaks,
                                     self.others_symbol is not None)
        self._cache_key = key
        self._cache = arr
        return arr

    def legend_labels(self, layer=None):
        out = []
        for i in range(len(self.breaks) - 1):
            out.append("%s – %s" % (_fmt(self.breaks[i]),
                                    _fmt(self.breaks[i + 1])))
        if self.others_symbol is not None:
            out.append(self.others_label)
        return out or ["全部要素"]

    def to_dict(self):
        d = super().to_dict()
        d.update({"field": self.field, "mode": self.mode,
                  "n_classes": self.n_classes, "ramp": self.ramp,
                  "breaks": list(self.breaks),
                  "symbols": [_sym_to_dict(s) for s in self.symbols_]})
        d["others"] = (_sym_to_dict(self.others_symbol)
                       if self.others_symbol is not None else None)
        d["others_label"] = self.others_label
        return d

    @staticmethod
    def _load(d):
        return GgsGraduatedRenderer(
            d.get("field", ""), d.get("mode", "equal"),
            d.get("n_classes", 5), d.get("ramp", "spectral"),
            d.get("breaks"), [_sym_from_dict(s)
                              for s in (d.get("symbols") or [])],
            d.get("kind", "point"),
            _sym_from_dict(d["others"]) if d.get("others") else None,
            d.get("others_label", "其他值"))


class GgsRule:

    __slots__ = ("filter", "label", "symbol", "children", "is_else",
                 "active")

    def __init__(self, filter="", label="", symbol=None, children=None,
                 is_else=False, active=True):
        self.filter = str(filter or "")
        self.label = str(label or "")
        self.symbol = symbol
        self.children = list(children or [])
        self.is_else = bool(is_else)
        self.active = bool(active)

    def add(self, child):
        self.children.append(child)
        return child

    def clone(self):
        return GgsRule.from_dict(self.to_dict())

    def to_dict(self):
        d = {"label": self.label, "filter": self.filter,
             "else": self.is_else, "active": self.active}
        if self.symbol is not None:
            d["symbol"] = _sym_to_dict(self.symbol)
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @staticmethod
    def from_dict(d):
        d = d or {}
        sym = d.get("symbol")
        r = GgsRule(d.get("filter", ""), d.get("label", ""),
                    _sym_from_dict(sym) if sym else None, None,
                    d.get("else", False), d.get("active", True))
        for cd in (d.get("children") or []):
            r.children.append(GgsRule.from_dict(cd))
        return r

    def __repr__(self):
        return "<GgsRule %r%s%s%s>" % (
            self.filter or ("else" if self.is_else else "*"),
            " sym" if self.symbol is not None else "",
            " x%d" % len(self.children) if self.children else "",
            "" if self.active else " (off)")


def _rule_tree_sig(node):
    return (node.filter, bool(node.is_else), bool(node.active),
            node.symbol is not None,
            tuple(_rule_tree_sig(c) for c in node.children))


def _rule_class_array(layer, root):
    from ggis.core.expr import expression as _expr
    n = int(layer.feature_count())
    attrs = layer.attrs()
    geoms = layer.geoms()
    out = np.zeros(n, dtype=np.int32)
    ok = np.ones(n, dtype=bool)
    for i in range(min(n, len(geoms))):
        g = geoms[i]
        if g is None or getattr(g, "is_empty", True):
            ok[i] = False
    empty = np.zeros(n, dtype=bool)
    state = {"k": 0, "rules": []}

    def _mask(node):
        if node.is_else or not node.filter.strip():
            return None
        try:
            tree = _expr.parse(node.filter)
        except Exception:
            exc_note("_mask @ ggis/render/renderers.py:1026")
            return empty
        if tree is None:
            return None
        try:
            return _expr.select_mask(tree, attrs)
        except Exception:
            exc_note("_mask @ ggis/render/renderers.py:1032")
            return empty

    def _walk(node, avail):
        if not node.active:
            return avail
        m = avail
        mk = _mask(node)
        if mk is not None:
            m = avail & mk
        if node.symbol is not None:
            state["k"] += 1
            out[m] = state["k"]
            state["rules"].append(node)
            rest = empty
        else:
            rest = m
        for ch in node.children:
            rest = _walk(ch, rest)
        return (avail & ~m) | rest

    rest = ok
    for ch in root.children:
        rest = _walk(ch, rest)
    return out, state["rules"]


class GgsRuleBasedRenderer(GgsFeatureRenderer):

    type_name = "rule"

    def __init__(self, root=None, geometry_kind="point"):
        super().__init__(geometry_kind)
        self.root = root if root is not None else GgsRule(label="")
        self._cache_key = None
        self._cache = None
        self._labels = []
        self._syms = []

    def invalidate(self):
        self._cache_key = None
        self._cache = None

    def add_rule(self, rule):
        self.root.add(rule)
        self.invalidate()
        return rule

    def rule_count(self):
        self._collect()
        return len(self._syms)

    def _collect(self):
        labels, syms = [], []

        def _go(node):
            for ch in node.children:
                if not ch.active:
                    continue
                if ch.symbol is not None:
                    labels.append(ch.label or ch.filter or "规则")
                    syms.append(ch.symbol)
                _go(ch)

        _go(self.root)
        self._labels, self._syms = labels, syms

    def symbols(self):
        self._collect()
        return self._syms or [_default_sym(self.geometry_kind, 0)]

    def legend_symbols(self):
        self._collect()
        return list(self._syms)

    def legend_labels(self, layer=None):
        self._collect()
        return self._labels or ["全部要素"]

    def class_array(self, layer):
        self._collect()
        if not self._syms:
            return None
        key = (id(layer), int(layer.feature_count()),
               _data_version(layer), _rule_tree_sig(self.root))
        if self._cache_key == key and self._cache is not None:
            return self._cache
        arr, _rules = _rule_class_array(layer, self.root)
        self._cache_key = key
        self._cache = arr
        return arr

    @staticmethod
    def from_rules(items, geometry_kind="point"):
        r = GgsRuleBasedRenderer(None, geometry_kind)
        for it in items:
            f, lab, sym = it
            r.add_rule(GgsRule(f, lab, sym))
        return r

    def to_dict(self):
        d = super().to_dict()
        d["root"] = self.root.to_dict()
        return d

    @staticmethod
    def _load(d):
        return GgsRuleBasedRenderer(GgsRule.from_dict(d.get("root")),
                                    d.get("kind", "point"))



def _fmt(v):
    av = abs(v)
    if av >= 10000 or (av < 0.01 and av > 0):
        return "%.3g" % v
    if av >= 100:
        return "%.1f" % v
    if av < 1:
        return ("%.3f" % v).rstrip("0").rstrip(".")
    return "%.2f" % v


def _default_sym(kind, index, fill=None):
    from .symbol import default_symbol
    if fill is None:
        return default_symbol(kind, index)
    from ggis.core.crs.units import DEFAULT_LINE_WIDTH_PX as _DW
    alpha, width, size = {"point": (1.0, _DW, 4.0),
                          "line": (1.0, _DW, 0.0),
                          "polygon": (1.0, _DW, 0.0)}.get(kind, (1.0, _DW, 3.0))
    from .symbol import color_field_for_kind
    from .symbol import px_size as _pxs, px_width as _pxw
    kw = {"fill": fill}
    if color_field_for_kind(kind) == "stroke":
        kw["stroke"] = fill
    return GgsSymbol(width=_pxw(width), size=_pxs(size), fill_alpha=alpha,
                     **kw)


make_symbol = _default_sym


def _color_text(c):
    try:
        from PySide6.QtGui import QColor
        q = QColor(c)
        if not q.isValid():
            return "#000000"
        return q.name() if q.alpha() >= 255 \
            else q.name(QColor.NameFormat.HexArgb)
    except Exception:
        exc_note("_color_text @ ggis/render/renderers.py:1241")
        return "#000000"


def _sym_to_dict(sym):
    if sym is None:
        return None
    from .symbol import current_unit
    return {"fill": _color_text(sym.fill), "stroke": _color_text(sym.stroke),
            "width": sym.width, "size": sym.size,
            "opacity": sym.opacity, "fill_alpha": sym.fill_alpha,
            "line_style": str(getattr(sym, "line_style", "solid") or "solid"),
            "fill_style": str(getattr(sym, "fill_style", "solid") or "solid"),
            "fill_spacing": getattr(sym, "fill_spacing", None),
            "fill_width": getattr(sym, "fill_width", None),
            "cap": str(getattr(sym, "cap", "flat") or "flat"),
            "join": str(getattr(sym, "join", "bevel") or "bevel"),
            "dash_custom": [float(v) for v in
                            (getattr(sym, "dash_custom", ()) or ())],
            "unit": str(getattr(sym, "unit", None) or current_unit())}


def _sym_from_dict(d):
    if not d:
        return None
    from .symbol import current_unit
    from ggis.core.crs.units import is_known
    unit = str(d.get("unit") or "").strip().lower()
    width = float(d.get("width", 1.0) or 0.0)
    size = float(d.get("size", 4.0) or 0.0)
    if not is_known(unit):
        _u = current_unit()
        width = px_to_unit(width, _u)
        size = px_to_unit(size, _u)
        unit = _u
    return GgsSymbol(d.get("fill", "#4C9BE8"), d.get("stroke"),
                     width, size,
                     d.get("opacity", 1.0), d.get("fill_alpha", 0.6),
                     unit=unit,
                     line_style=d.get("line_style", "solid"),
                     fill_style=d.get("fill_style", "solid"),
                     fill_spacing=d.get("fill_spacing"),
                     fill_width=d.get("fill_width"),
                     cap=d.get("cap", "flat"),
                     join=d.get("join", "bevel"),
                     dash_custom=tuple(d.get("dash_custom") or ()))


def default_renderer(layer, index=0):
    kind = "polygon" if layer.base_kind() == "polygon" else \
        ("line" if layer.base_kind() == "line" else "point")
    return GgsSingleSymbolRenderer(_default_sym(kind, index), kind)


def get_renderer(layer):
    r = layer.__dict__.get("_renderer")
    if r is None:
        r = default_renderer(layer)
        try:
            layer._renderer = r
        except Exception:
            exc_note("get_renderer @ ggis/render/renderers.py:1331")
            pass
    return r


def set_renderer(layer, renderer):
    try:
        layer._renderer = renderer
    except Exception:
        exc_note("set_renderer @ ggis/render/renderers.py:1339")
        pass
    _bump_render_version(layer)
    prewarm_class_array(layer, renderer)


def _bump_render_version(layer):
    try:
        layer._render_version = int(layer.__dict__.get("_render_version", 0)) + 1
    except Exception:
        exc_note("_bump_render_version @ ggis/render/renderers.py:1351")
        pass


def render_version(layer):
    return int(layer.__dict__.get("_render_version", 0))
