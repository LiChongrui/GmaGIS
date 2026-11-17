import logging
_log = logging.getLogger("gmagis")
"""
栅格**重采样方式**的注册表（照 QGIS 的 ``QgsRasterResampler`` 转写）。

QGIS 侧对应物：``qgsrasterresampler.h`` 的那一族 ——
``QgsNearestNeighbourResampler`` / ``QgsBilinearRasterResampler`` /
``QgsCubicRasterResampler`` / ``QgsCubicSplineRasterResampler`` /
``QgsLanczosResampler`` / ``QgsAverageRasterResampler`` /
``QgsGaussRasterResampler`` / ``QgsModeRasterResampler``，
以及 ``QgsRasterRenderer`` 上那对
``setZoomedInResampler`` / ``setZoomedOutResampler``。

本模块只做三件事（**不碰 Qt、不碰 rasterio 的会话**）：

1. **名字 → 枚举**：``to_rasterio()`` 把我们的名字翻成 rasterio 的
 ``Resampling``（取不到就回 ``None``，调用方退到驱动默认）；
2. **归一化**：``normalize()`` 把任意输入（``None`` / 名字字符串 /
 rasterio 的 ``Resampling`` 枚举）归一成上面的标准名字，认不出来的
 一律回 :data:`NEAREST`；
3. **方向敏感**：``pick()`` 按"这一帧是放大还是缩小"选其中一个 ——
 QGIS 就是这么干的（放大用一个 resampler、缩小用另一个）。

为什么值得单独成模块：重采样方式要被三处读到（``core/layer.py`` 的
``read_window`` / ``read_window_reprojected``、``render/builtin/raster.py``
的绘制、``core/raster_display.py`` 的抽样），**口径必须只有一份**。
历史上 ``render/builtin/raster.py`` 里那个 ``RESAMPLE`` 模块级常量
**全项目无人写入**（等于写死了最近邻），正是"口径多份"的反面教材。
"""

__all__ = [
    "NEAREST", "BILINEAR", "CUBIC", "CUBIC_SPLINE", "LANCZOS",
    "AVERAGE", "GAUSS", "MODE", "ORDER", "LABELS",
    "normalize", "to_rasterio", "pick", "label",
    "options", "for_display",
]

NEAREST = "nearest"
BILINEAR = "bilinear"
CUBIC = "cubic"
CUBIC_SPLINE = "cubic_spline"
LANCZOS = "lanczos"
AVERAGE = "average"
GAUSS = "gauss"
MODE = "mode"

ORDER = (NEAREST, BILINEAR, CUBIC, CUBIC_SPLINE, LANCZOS,
         AVERAGE, GAUSS, MODE)

LABELS = {
    NEAREST: "最近邻",
    BILINEAR: "双线性",
    CUBIC: "双三次（Cubic）",
    CUBIC_SPLINE: "三次样条",
    LANCZOS: "Lanczos",
    AVERAGE: "平均值",
    GAUSS: "高斯",
    MODE: "众数",
}

_UPSCALE = (NEAREST, BILINEAR, CUBIC, CUBIC_SPLINE, LANCZOS)
_DOWNSCALE = (NEAREST, BILINEAR, AVERAGE, GAUSS, MODE, LANCZOS)

def normalize(value):
    if value is None:
        return NEAREST
    nm = getattr(value, "name", None)
    if isinstance(nm, str):
        return normalize(nm)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in LABELS:
            return v
        v2 = v.replace(" ", "_").replace("-", "_")
        if v2 in LABELS:
            return v2
        if v2 in ("bilinear_interpolation", "linear"):
            return BILINEAR
        if v2 in ("cubic_spline", "bicubic", "cubic_convolution"):
            return CUBIC if "spline" not in v2 else CUBIC_SPLINE
        if v2 in ("nearest_neighbour", "nearest_neighbor", "nn"):
            return NEAREST
        if v2 in ("mean", "avg"):
            return AVERAGE
        return NEAREST
    return NEAREST


def label(value):
    return LABELS.get(normalize(value), LABELS[NEAREST])


def to_rasterio(value):
    name = normalize(value)
    try:
        from rasterio.enums import Resampling
    except Exception:
        _log.exception("silent exception in to_rasterio")
        return None
    table = {
        NEAREST: "nearest",
        BILINEAR: "bilinear",
        CUBIC: "cubic",
        CUBIC_SPLINE: "cubic_spline",
        LANCZOS: "lanczos",
        AVERAGE: "average",
        GAUSS: "gauss",
        MODE: "mode",
    }
    try:
        return Resampling[table[name]]
    except Exception:
        _log.exception("silent exception in to_rasterio")
        return None


def pick(zoomed_in, zoomed_out, is_zoom_in):
    a = normalize(zoomed_in) if zoomed_in is not None else None
    b = normalize(zoomed_out) if zoomed_out is not None else None
    if is_zoom_in:
        return a if a is not None else (b if b is not None else NEAREST)
    return b if b is not None else (a if a is not None else NEAREST)


def options(is_zoom_in=None):
    if is_zoom_in is None:
        return list(ORDER)
    return list(_UPSCALE if is_zoom_in else _DOWNSCALE)


def for_display(layer, extent, out_w, out_h,
                default_in=NEAREST, default_out=NEAREST):
    try:
        is_in = True
        try:
            rx, ry = layer.resolution()
            src_px = (extent.width() / rx) * (extent.height() / ry)
            is_in = (int(out_w) * int(out_h)) >= max(1.0, src_px)
        except Exception:
            _log.exception("silent exception in for_display")
            is_in = True
        up = default_in
        down = default_out
        flag = to_rasterio(pick(up, down, is_in))
        return flag if flag is not None else 0
    except Exception:
        _log.exception("silent exception in for_display")
        return 0
