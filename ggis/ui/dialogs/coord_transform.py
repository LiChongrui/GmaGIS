# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtWidgets import (
                               QComboBox,
                               QDialogButtonBox,
                               QGridLayout,
                               QGroupBox,
                               QLabel,
                               QVBoxLayout,
)

from ggis.core.app import i18n
from ...core.crs import GgsCoordinateReferenceSystem as GgsCrs
from ggis.common.base.dialog import GgsDialog
import logging
from PySide6.QtWidgets import QLineEdit, QPushButton
_log = logging.getLogger("gmagis")

_tr = i18n.tr

COMMON_CRS = (
    ("EPSG:4326", "WGS 84 经纬度"),
    ("EPSG:4490", "CGCS2000 经纬度"),
    ("EPSG:3857", "Web 墨卡托"),
    ("EPSG:32650", "WGS 84 / UTM 50N"),
    ("EPSG:32649", "WGS 84 / UTM 49N"),
    ("EPSG:4547", "CGCS2000 / 3 度带 114E"),
    ("EPSG:4548", "CGCS2000 / 3 度带 117E"),
    ("EPSG:4526", "CGCS2000 / 3 度带 108E"),
)


class GgsCoordinateTransformDialog(GgsDialog):

    def __init__(self, parent=None, source="EPSG:4326",
                 target="EPSG:3857", x=None, y=None):
        super().__init__(parent)
        self._result = None
        self.setObjectName("GgsCoordinateTransformDialog")
        self.setWindowTitle(_tr("坐标转换"))
        self.resize(520, 400)
        self._build()
        self._set_crs(self.cmb_src, source)
        self._set_crs(self.cmb_dst, target)
        if x is not None and y is not None:
            self.ed_x.setText(_fmt(x))
            self.ed_y.setText(_fmt(y))
        self._on_input_changed()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        box_crs = QGroupBox(_tr("坐标系"), self)
        g1 = QGridLayout(box_crs)
        g1.setHorizontalSpacing(8)
        g1.setVerticalSpacing(6)

        g1.addWidget(QLabel(_tr("源坐标系")), 0, 0)
        self.cmb_src = self._crs_combo("GgsCtSrc")
        g1.addWidget(self.cmb_src, 0, 1)

        self.btn_swap = GgsCtSwap(_tr("↑↓ 互换"))
        self.btn_swap.setToolTip(_tr("交换"))
        g1.addWidget(self.btn_swap, 0, 2, 2, 1)

        g1.addWidget(QLabel(_tr("目标坐标系")), 1, 0)
        self.cmb_dst = self._crs_combo("GgsCtDst")
        g1.addWidget(self.cmb_dst, 1, 1)
        g1.setColumnStretch(1, 1)
        lay.addWidget(box_crs)

        box_in = QGroupBox(_tr("输入坐标"), self)
        g2 = QGridLayout(box_in)
        g2.setHorizontalSpacing(8)
        g2.setVerticalSpacing(6)
        self.lbl_x = QLabel(_tr("X (经度)"))
        self.lbl_y = QLabel(_tr("Y (纬度)"))
        self.ed_x = GgsCtX()
        self.ed_y = GgsCtY()
        g2.addWidget(self.lbl_x, 0, 0)
        g2.addWidget(self.ed_x, 0, 1)
        g2.addWidget(self.lbl_y, 1, 0)
        g2.addWidget(self.ed_y, 1, 1)
        g2.setColumnStretch(1, 1)
        lay.addWidget(box_in)

        box_out = QGroupBox(_tr("转换结果"), self)
        g3 = QGridLayout(box_out)
        g3.setHorizontalSpacing(8)
        g3.setVerticalSpacing(6)
        self.lbl_res1 = QLabel(_tr("X"))
        self.lbl_res2 = QLabel(_tr("Y"))
        self.out_x = GgsCtOutX()
        self.out_x.setReadOnly(True)
        self.out_y = GgsCtOutY()
        self.out_y.setReadOnly(True)
        self.btn_copy = GgsCtCopy(_tr("复制"))
        g3.addWidget(self.lbl_res1, 0, 0)
        g3.addWidget(self.out_x, 0, 1)
        g3.addWidget(self.lbl_res2, 1, 0)
        g3.addWidget(self.out_y, 1, 1)
        g3.addWidget(self.btn_copy, 0, 2, 2, 1)
        g3.setColumnStretch(1, 1)

        self.lbl_extra = GgsCtExtra("")
        self.lbl_extra.setWordWrap(True)
        g3.addWidget(self.lbl_extra, 2, 0, 1, 3)
        lay.addWidget(box_out)

        self.lbl_err = GgsCtError("")
        self.lbl_err.setWordWrap(True)
        lay.addWidget(self.lbl_err)
        lay.addStretch(1)

        bbox = QDialogButtonBox(self)
        bbox.addButton(_tr("关闭"),
                       QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.accepted.connect(self.accept)
        lay.addWidget(bbox)

        for w in (self.ed_x, self.ed_y):
            w.textChanged.connect(self._on_input_changed)
        self.cmb_src.currentTextChanged.connect(self._on_crs_changed)
        self.cmb_dst.currentTextChanged.connect(self._on_crs_changed)
        self.cmb_src.currentIndexChanged.connect(self._on_crs_changed)
        self.cmb_dst.currentIndexChanged.connect(self._on_crs_changed)
        self.btn_swap.clicked.connect(self._on_swap)
        self.btn_copy.clicked.connect(self._on_copy)

    def _crs_combo(self, name):
        c = QComboBox()
        c.setObjectName(name)
        c.setEditable(True)
        for code, label in COMMON_CRS:
            c.addItem("%s — %s" % (code, _tr(label)), code)
        return c

    @staticmethod
    def _set_crs(combo, value):
        value = str(value or "")
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        if value.isdigit():
            idx = combo.findData("EPSG:" + value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return
        if value:
            combo.setEditText(value)

    def _crs_text(self, combo):
        d = combo.currentData()
        if combo.isEditable() and combo.currentText() != \
                (combo.itemText(combo.currentIndex()) if
                 combo.currentIndex() >= 0 else ""):
            return combo.currentText().strip()
        return str(d or combo.currentText()).strip()

    def _resolve(self, text):
        t = str(text or "").strip()
        if not t:
            return None
        if t.isdigit():
            t = "EPSG:" + t
        c = GgsCrs.from_user_input(t)
        return c if c is not None and c.is_valid() else None

    def _on_crs_changed(self, *_):
        src = self._resolve(self._crs_text(self.cmb_src))
        dst = self._resolve(self._crs_text(self.cmb_dst))
        for c, lx, ly in ((src, self.lbl_x, self.lbl_y),):
            geo = bool(c is not None and c.is_geographic())
            lx.setText(_tr("X (经度)") if geo else _tr("X"))
            ly.setText(_tr("Y (纬度)") if geo else _tr("Y"))
        try:
            geo2 = bool(dst is not None and dst.is_geographic())
        except Exception:
            _log.exception("silent exception in _on_crs_changed")
            geo2 = False
        self.lbl_res1.setText(_tr("经度") if geo2 else _tr("X"))
        self.lbl_res2.setText(_tr("纬度") if geo2 else _tr("Y"))
        self._on_input_changed()

    def _on_input_changed(self, *_):
        self._result = None
        x = _parse(self.ed_x.text())
        y = _parse(self.ed_y.text())
        if x is None or y is None:
            self.lbl_err.setText("")
            self.out_x.setText("")
            self.out_y.setText("")
            self.lbl_extra.setText(_tr("请输入数值"))
            return

        src = self._resolve(self._crs_text(self.cmb_src))
        dst = self._resolve(self._crs_text(self.cmb_dst))
        if src is None:
            self.lbl_err.setText(_tr("源坐标系无法识别：{0}").format(
                self._crs_text(self.cmb_src)))
            return
        if dst is None:
            self.lbl_err.setText(_tr("目标坐标系无法识别：{0}").format(
                self._crs_text(self.cmb_dst)))
            return
        self.lbl_err.setText("")
        try:
            self._result = transform_point_checked(
                (x, y), src.authid(), dst.authid())
        except Exception as e:
            _log.exception("silent exception in _on_input_changed")
            self.lbl_err.setText(_tr("转换失败：{0}").format(e))
            self.out_x.setText("")
            self.out_y.setText("")
            return
        ox, oy = self._result
        self.out_x.setText(_fmt(ox))
        self.out_y.setText(_fmt(oy))
        self.lbl_extra.setText(self._describe(ox, oy, dst))

    def _describe(self, x, y, dst):
        try:
            if dst.is_geographic():
                return _tr("该点位于纬度 {0}°、经度 {1}°").format(
                    _fmt(y, 5), _fmt(x, 5))
            u = dst.unit_abbreviation() or ""
            return _tr("单位：{0}").format(
                u or _tr("未知"), dst.display_name() or _tr("未知"))
        except Exception:
            _log.exception("silent exception in _describe")
            return ""

    def _on_swap(self):
        s = self._crs_text(self.cmb_src)
        d = self._crs_text(self.cmb_dst)
        self._set_crs(self.cmb_src, d)
        self._set_crs(self.cmb_dst, s)
        if self._result is not None:
            self.ed_x.setText(_fmt(self._result[0]))
            self.ed_y.setText(_fmt(self._result[1]))
            self._result = None
        self._on_crs_changed()

    def _on_copy(self):
        from PySide6.QtWidgets import QApplication
        txt = "%s\t%s" % (self.out_x.text(), self.out_y.text())
        try:
            QApplication.clipboard().setText(txt)
            self.lbl_err.setText(_tr("已复制到剪贴板"))
        except Exception:
            _log.exception("silent exception in _on_copy")

    def result_point(self):
        return self._result


def transform_point(point, src_authid, dst_authid):
    from pyproj import Transformer

    src = str(src_authid or "").strip() or "EPSG:4326"
    dst = str(dst_authid or "").strip() or "EPSG:4326"
    t = Transformer.from_crs(src, dst, always_xy=True)
    x, y = t.transform(float(point[0]), float(point[1]))
    return float(x), float(y)


def transform_point_checked(point, src_authid, dst_authid):
    import math

    x, y = transform_point(point, src_authid, dst_authid)
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError(_tr("坐标超出该坐标系的有效范围"))
    return x, y


def _parse(text):
    s = str(text or "").strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        _log.exception("silent exception in _parse")
        return None


def _fmt(v, digits=8):
    try:
        f = float(v)
    except Exception:
        _log.exception("silent exception in _fmt")
        return str(v)
    s = ("%." + str(int(digits)) + "f") % f
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


class GgsCtCopy(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtCopy")
class GgsCtError(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtError")
class GgsCtExtra(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtExtra")
class GgsCtOutX(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtOutX")
class GgsCtOutY(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtOutY")
class GgsCtSwap(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtSwap")
class GgsCtX(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtX")
class GgsCtY(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsCtY")
