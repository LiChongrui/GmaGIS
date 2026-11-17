import logging
_log = logging.getLogger("gmagis")
"""尺寸单位的**唯一真源**（放在 core 层，`render` 与 `core` 都能用）。

为什么在 core：`core/style_library.py` 也要按毫米存符号尺寸，而架构门禁
**R3 规定 core 不许 `import ggis.render`** ⇒ 换算常量与函数必须沉到 core；
`render/symbol.py` 从这里取（并保留它原来的公开名字，调用方无感）。

口径（照 QGIS，96 dpi 逻辑坐标）：

* ``1 mm = 96 / 25.4 = 3.7795`` 画布像素（``PX_PER_MM``）；
* ``1 pt = 96 / 72 = 1.3333`` 像素；``1 in = 96`` 像素。

⚠ 是**逻辑像素**（Qt 在带 ``devicePixelRatio`` 的图上作画本来就是逻辑坐标），
不是设备像素 —— 这一条与 `render/builtin/units.py` 的 ``mScaleFactor`` 同解。

用户 「**渲染单位从 pt 改为毫米**」⇒ 曾把 :data:`DEFAULT_UNIT` 定为 mm；
同日晚「**项目渲染单位统一改为 pt 吧，默认单位可以在选项中设置**」⇒ 现在
**默认 pt**，且真源是设置项 `symbol_unit`（:func:`default_unit()`）。
`DEFAULT_UNIT` 退化成"读不到设置时的兜底值"。
"""

MM_PER_INCH = 25.4
LOGICAL_DPI = 96.0
PX_PER_MM = LOGICAL_DPI / MM_PER_INCH
PX_PER_PT = LOGICAL_DPI / 72.0

DEFAULT_LINE_WIDTH_PX = 0.7 * PX_PER_PT

DEFAULT_UNIT = "pt"

_UNIT_TO_PX = {
    "mm": PX_PER_MM, "millimeter": PX_PER_MM, "millimeters": PX_PER_MM,
    "毫米": PX_PER_MM,
    "px": 1.0, "pixel": 1.0, "pixels": 1.0, "像素": 1.0,
    "pt": PX_PER_PT, "point": PX_PER_PT, "points": PX_PER_PT, "磅": PX_PER_PT,
    "in": LOGICAL_DPI, "inch": LOGICAL_DPI, "inches": LOGICAL_DPI,
    "英寸": LOGICAL_DPI,
}

SELECTABLE_UNITS = ("pt", "mm", "px", "in")


def default_unit():
    try:
        from ggis.core.app import settings as _S
        v = str(_S.get("symbol_unit") or "").strip().lower()
    except Exception:
        _log.exception("silent exception in default_unit")
        v = ""
    return v if v in SELECTABLE_UNITS else DEFAULT_UNIT


def to_px(value, unit=None):
    try:
        key = str(unit or default_unit()).strip().lower()
    except Exception:
        _log.exception("silent exception in to_px")
        key = ""
    return float(value) * _UNIT_TO_PX.get(key, 1.0)


def from_px(px, unit=None):
    try:
        key = str(unit or default_unit()).strip().lower()
    except Exception:
        _log.exception("silent exception in from_px")
        key = ""
    f = _UNIT_TO_PX.get(key, 1.0) or 1.0
    return float(px) / f


def convert(value, src_unit, dst_unit):
    return from_px(to_px(value, src_unit), dst_unit)


def is_known(unit):
    try:
        return str(unit or "").strip().lower() in _UNIT_TO_PX
    except Exception:
        _log.exception("silent exception in is_known")
        return False


def mm_to_px(mm):
    return float(mm) * PX_PER_MM


def px_to_mm(px):
    return float(px) / PX_PER_MM


def pt_to_mm(pt):
    return float(pt) * MM_PER_INCH / 72.0


def mm_to_pt(mm):
    return float(mm) * 72.0 / MM_PER_INCH
