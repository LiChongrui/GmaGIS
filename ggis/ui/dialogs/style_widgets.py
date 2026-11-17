# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel,
                               QLineEdit, QSpinBox, QVBoxLayout, QWidget)

from ggis.core.app import i18n as lib
from ggis.common.widgets.inputs import (GgsColorField, GgsComboBox, ggs_font_combo,
                            ggs_font_select)

_tr = lib.tr

_COLOR_SHAPES = {
    "fill": "rect", "color": "rect",
    "stroke": "line", "halo_color": "line",
}

_CHOICE_LABELS = {
    "point": "点", "line": "线", "polygon": "面",
    "auto": "自动", "right": "右侧", "top": "上方", "bottom": "下方",
    "left": "左侧", "center": "居中",
}

_FIELD_TITLES = {
    "kind": "几何类型", "fill": "填充色", "stroke": "描边色",
    "width": "线宽", "size": "符号大小", "fill_alpha": "填充透明度",
    "line_style": "线样式", "fill_style": "填充样式",
    "cap": "线端样式", "join": "拐角样式",
    "placement": "放置方式", "offset_x": "水平偏移", "offset_y": "垂直偏移",
    "min_size_px": "最小要素尺寸", "repeat_px": "沿线间隔",
    "max_labels": "每层上限", "font_family": "字体", "font_size": "字号",
    "bold": "粗体", "italic": "斜体", "color": "文字颜色",
    "halo_color": "晕圈颜色", "halo_width": "晕圈宽度", "buffer": "文字间距",
}

_FIELD_OPTIONS = {
    "line_style": {
        "solid": "实线", "dash": "虚线", "dot": "点线",
        "dash_dot": "点划线", "dash_dot_dot": "双点划线",
        "short_dash": "短虚线", "short_dash_dot": "短点划线",
        "short_dash_dot_dot": "短双点划线",
        "long_dash": "长虚线", "long_dash_dot": "长点划线",
        "long_dash_dot_dot": "长双点划线",
    },
    "fill_style": {
        "solid": "实心", "horizontal": "横线", "vertical": "竖线",
        "diagonal": "斜线", "back_diagonal": "反斜线",
        "cross": "十字线", "diagonal_cross": "交叉线",
    },
    "cap": {"flat": "平头", "square": "方头", "round": "圆头"},
    "join": {"miter": "尖角", "bevel": "斜角", "round": "圆角"},
}


def _preview_title(item):
    t = _tr(item.get("title") or item["key"])
    return t if not item.get("builtin") else "%s · %s" % (t, _tr("内置"))


def _category_word(category):
    return _tr(lib.CATEGORY_TITLES.get(category, category))


def _field_title(name):
    return _tr(_FIELD_TITLES.get(name, name))


def _choice_label(field, opt):
    table = _FIELD_OPTIONS.get(field)
    if table and opt in table:
        return _tr(table[opt])
    return _tr(_CHOICE_LABELS.get(opt, opt))


def _color_row(btn):
    host = QWidget()
    h = QHBoxLayout(host)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    h.addWidget(btn)
    lab = QLabel(btn.color().name().upper())
    btn.colorChanged.connect(
        lambda *_a: lab.setText(btn.color().name().upper()))
    h.addWidget(lab)
    h.addStretch(1)
    return host


def _form_label(text):
    host = QWidget()
    v = QVBoxLayout(host)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)
    v.addStretch(1)
    v.addWidget(QLabel(text))
    v.addStretch(1)
    return host


def _left_row(widget):
    host = QWidget()
    h = QHBoxLayout(host)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    h.addWidget(widget)
    h.addStretch(1)
    return host


def _make_editor(name, spec, value, on_change):
    t = spec["type"]
    if name == "font_family":
        w = ggs_font_combo(None)
        ggs_font_select(w, str(value if value is not None else spec["default"]))
        w.currentIndexChanged.connect(lambda *_a: on_change())
        return w
    if t == "color":
        w = GgsColorField(str(value or spec["default"]),
                          shape=_COLOR_SHAPES.get(name, "rect"))
        w.colorChanged.connect(lambda *_a: on_change())
        return w
    if t == "bool":
        w = QCheckBox()
        w.setChecked(bool(value))
        w.toggled.connect(lambda *_a: on_change())
        return w
    if t == "float":
        w = QDoubleSpinBox()
        w.setRange(float(spec["min"]), float(spec["max"]))
        w.setDecimals(int(spec.get("decimals", 1)))
        w.setSingleStep(0.1 if spec["max"] > 5 else 0.01)
        if spec.get("suffix"):
            w.setSuffix(_tr(spec["suffix"]))
        w.setValue(float(value if value is not None else spec["default"]))
        w.valueChanged.connect(lambda *_a: on_change())
        return w
    if t == "int":
        w = QSpinBox()
        w.setRange(int(spec["min"]), int(spec["max"]))
        if spec["min"] == 0:
            w.setSpecialValueText(_tr("不限"))
        if spec.get("suffix"):
            w.setSuffix(_tr(spec["suffix"]))
        w.setValue(int(value if value is not None else spec["default"]))
        w.valueChanged.connect(lambda *_a: on_change())
        return w
    if t == "choice":
        w = GgsComboBox()
        for opt in spec["options"]:
            w.addItem(_choice_label(name, opt), opt)
        v = str(value if value is not None else spec["default"])
        for i in range(w.count()):
            if w.itemData(i) == v:
                w.setCurrentIndex(i)
                break
        w.currentIndexChanged.connect(lambda *_a: on_change())
        return w
    w = QLineEdit(str(value if value is not None else spec["default"]))
    w.textChanged.connect(lambda *_a: on_change())
    return w
