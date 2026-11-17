# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note
from ggis.core.app import i18n

_tr = i18n.tr


def symbol_from_item(item, kind, dark_bg):
    from .symbol import GgsSymbol
    from ggis.core.style.style_library import target_unit
    return GgsSymbol(fill=item.get("fill", "#4C9BE8"),
                     stroke=item.get("stroke", "#1B2430"),
                     width=item.get("width", 1.0),
                     size=item.get("size", 4.0),
                     fill_alpha=item.get("fill_alpha", 1.0),
                     dark_bg=dark_bg,
                     unit=target_unit(),
                     line_style=item.get("line_style", "solid"),
                     fill_style=item.get("fill_style", "solid"),
                     cap=item.get("cap", "flat"),
                     join=item.get("join", "bevel"))


def apply_style_to_layer(category, item, layer, dark_bg):
    from .renderers import (GgsGraduatedRenderer, GgsSingleSymbolRenderer,
                            set_renderer)
    if category == "symbol":
        kind = layer.base_kind()
        sym = symbol_from_item(item, kind, dark_bg)
        set_renderer(layer, GgsSingleSymbolRenderer(sym, kind))
        return ""
    if category == "ramp":
        from ggis.core.model.field import fields_from_layer
        nums = [f for f in fields_from_layer(layer) if f.is_numeric()]
        if not nums:
            raise ValueError(_tr("该图层没有数值字段，无法做分级渲染"))
        r = GgsGraduatedRenderer(nums[0].name, "equal", 5, item["key"],
                                 geometry_kind=layer.base_kind())
        r.rebuild(layer)
        set_renderer(layer, r)
        return _tr("按字段「{0}」分 5 级").format(nums[0].name)
    from .labeling import LABEL_SIZE_FIELDS, get_label_style, set_label_style
    st = get_label_style(layer)
    from ggis.core.style.style_library import target_unit
    from ggis.core.crs.units import from_px
    _u = str(getattr(st, "unit", "") or "") or target_unit()
    for k, v in item.items():
        if k in ("key", "title", "builtin"):
            continue
        if k in LABEL_SIZE_FIELDS:
            try:
                v = float(from_px(float(v), _u))
            except Exception:
                exc_note("apply_style_to_layer @ ggis/render/style_apply.py:92")
                pass
        if hasattr(st, k):
            setattr(st, k, v)
    if category == "label":
        st.enabled = True
        if not st.field:
            from .labeling import suggest_label_field
            st.field = suggest_label_field(layer)
    set_label_style(layer, st)
    return _tr("标注样式已更新")
