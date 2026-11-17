import logging
_log = logging.getLogger("gmagis")
"""符号的**规格表**：线样式 / 填充图案 / 端头 / 连接（纯数据，**不依赖 Qt**）。

这几张表原来写在 ``render/symbol.py`` 里，但
**``core/style_library.py`` 也要用它们**（样式库的 ``SCHEMA`` 要按它们生成
下拉选项），而门禁 R3 **不许 core → render** ⇒ 单一真源搬到这里，
由 :mod:`ggis.render.symbol` 反过来 import（`symbol.LINE_STYLES` 这些
旧名字继续可用，调用点一个都不用改）。

⚠ 加新样式时**只改这里**：UI 的文案表（`core/symbol_spec.LINE_STYLE_LABELS`
等）与样式库的下拉选项都从这几张表推出来，改一处三处对。
"""

__all__ = ["LINE_STYLES", "LINE_PATTERNS", "FILL_STYLES", "CAPS", "JOINS",
           "CAP_DEFAULT", "JOIN_DEFAULT", "FILL_SPACING_PX", "FILL_WIDTH_PX",
           "LINE_STYLE_LABELS", "FILL_STYLE_LABELS", "CAP_LABELS",
           "JOIN_LABELS", "DASH_CUSTOM", "style_label"]

LINE_STYLES = (
    "solid",
    "dash", "dot", "dash_dot", "dash_dot_dot",
    "short_dash", "short_dash_dot", "short_dash_dot_dot",
    "long_dash", "long_dash_dot", "long_dash_dot_dot",
)

DASH_CUSTOM = "custom"

LINE_PATTERNS = {
    "dash": (4.0, 2.0),
    "dot": (1.0, 2.0),
    "dash_dot": (4.0, 2.0, 1.0, 2.0),
    "dash_dot_dot": (4.0, 2.0, 1.0, 2.0, 1.0, 2.0),
    "short_dash": (2.0, 2.0),
    "short_dash_dot": (2.0, 2.0, 1.0, 2.0),
    "short_dash_dot_dot": (2.0, 2.0, 1.0, 2.0, 1.0, 2.0),
    "long_dash": (8.0, 3.0),
    "long_dash_dot": (8.0, 3.0, 1.0, 3.0),
    "long_dash_dot_dot": (8.0, 3.0, 1.0, 3.0, 1.0, 3.0),
}

FILL_STYLES = ("solid", "horizontal", "vertical", "diagonal",
               "back_diagonal", "cross", "diagonal_cross")

CAPS = ("flat", "square", "round")
JOINS = ("miter", "bevel", "round")

CAP_DEFAULT = "flat"
JOIN_DEFAULT = "bevel"

FILL_SPACING_PX = 8.0
FILL_WIDTH_PX = 1.0


LINE_STYLE_LABELS = {
    "solid": "实线", "dash": "虚线", "dot": "点线",
    "dash_dot": "点划线", "dash_dot_dot": "双点划线",
    "short_dash": "短划线", "short_dash_dot": "短点划线",
    "short_dash_dot_dot": "短双点划线",
    "long_dash": "长划线", "long_dash_dot": "长点划线",
    "long_dash_dot_dot": "长双点划线",
}
FILL_STYLE_LABELS = {
    "solid": "实心", "horizontal": "横线", "vertical": "竖线",
    "diagonal": "斜线", "back_diagonal": "反斜线",
    "cross": "十字交叉", "diagonal_cross": "斜线交叉",
}
CAP_LABELS = {"flat": "平头", "square": "方头", "round": "圆头"}
JOIN_LABELS = {"miter": "斜接", "bevel": "斜切", "round": "圆角"}


def style_label(mapping, key):
    try:
        return mapping.get(str(key), str(key))
    except Exception:
        _log.exception("silent exception in style_label")
        return str(key)
