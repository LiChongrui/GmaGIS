# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtWidgets import (
                               QComboBox,
                               QDialogButtonBox,
                               QGridLayout,
                               QHBoxLayout,
                               QLabel,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n
from ggis.core.model.field import fields_from_layer
from ggis.core.analysis.stats import (FieldStats, histogram, collect_values,
                           raster_band_stats, raster_band_values)
from ggis.common.base.dialog import GgsDialog
from PySide6.QtWidgets import QCheckBox, QSpinBox

_tr = i18n.tr

_MAX_VECTOR_SAMPLES = 200_000


class GgsHistogramDialog(GgsDialog):

    def __init__(self, layer, parent=None, field=None, band=None):
        super().__init__(parent)
        self._layer = layer
        self._is_raster = bool(layer is not None and layer.is_raster())
        self._warn = ""
        self.setObjectName("GgsHistogramDialog")
        self.setWindowTitle(_tr("直方图 — {0}").format(
            layer.name() if layer is not None else ""))
        from ggis.common.styling import icons as _icons
        self.setWindowIcon(_icons.icon("histogram", size=16))
        self.resize(660, 480)
        self._build()
        self._select_initial(field, band)
        self._seq = 0
        self._pending = None
        self._refresh()

    def _build(self):
        from ggis.ui.views.map.dialogs.histogram_widget import GgsHistogramWidget

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        top = QHBoxLayout()
        self.lbl_target = QLabel(
            _tr("波段") if self._is_raster else _tr("字段"))
        top.addWidget(self.lbl_target)
        self.cmb = QComboBox()
        self.cmb.setObjectName("GgsHistBand" if self._is_raster
                               else "GgsHistField")
        self.cmb.setMinimumWidth(220)
        top.addWidget(self.cmb, 1)

        top.addWidget(QLabel(_tr("箱数")))
        self.sp_bins = GgsHistBins()
        self.sp_bins.setRange(0, 512)
        self.sp_bins.setSpecialValueText(_tr("自动"))
        self.sp_bins.setValue(0)
        self.sp_bins.setToolTip(
            "")
        top.addWidget(self.sp_bins)

        self.chk_log = GgsHistLog(_tr("纵轴对数"))
        self.chk_log.setToolTip(
            "")
        top.addWidget(self.chk_log)
        top.addStretch(1)
        lay.addLayout(top)

        self.view = GgsHistogramWidget(self)
        lay.addWidget(self.view, 1)

        self.box_stats = QWidget()
        grid = QGridLayout(self.box_stats)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(2)
        self._stat_labels = {}
        keys = (("count", "计数"), ("unique", "唯一值"), ("min", "最小"),
                ("max", "最大"), ("mean", "均值"), ("median", "中位"),
                ("std", "标准差"), ("total", "合计"), ("skipped", "空值"))
        for i, (key, label) in enumerate(keys):
            r, c = divmod(i, 3)
            cap = GgsHistStatCap(_tr(label) + "：")
            val = GgsHistStatValue("-")
            val.setMinimumWidth(96)
            grid.addWidget(cap, r, c * 2)
            grid.addWidget(val, r, c * 2 + 1)
            self._stat_labels[key] = val
        lay.addWidget(self.box_stats)


        self.lbl_note = GgsHistNote("")
        self.lbl_note.setWordWrap(True)
        lay.addWidget(self.lbl_note)

        bbox = QDialogButtonBox(self)
        bbox.addButton(_tr("关闭"),
                       QDialogButtonBox.ButtonRole.AcceptRole)
        bbox.accepted.connect(self.accept)
        lay.addWidget(bbox)

        self.cmb.currentIndexChanged.connect(self._refresh)
        self.sp_bins.valueChanged.connect(self._refresh)
        self.chk_log.toggled.connect(self._refresh)

    def _select_initial(self, field, band):
        self.cmb.blockSignals(True)
        self.cmb.clear()
        if self._is_raster:
            n = 1
            try:
                n = max(1, int(self._layer.band_count() or 1))
            except Exception:
                exc_note("_select_initial @ ggis/ui/views/map/dialogs/histogram.py:158")
                n = 1
            for b in range(1, n + 1):
                self.cmb.addItem(_tr("波段 {0}").format(b), b)
            if band:
                i = self.cmb.findData(int(band))
                if i >= 0:
                    self.cmb.setCurrentIndex(i)
        else:
            for f in fields_from_layer(self._layer):
                self.cmb.addItem("%s (%s)" % (f.name, f.type), f.name)
            if field:
                i = self.cmb.findData(str(field))
                if i >= 0:
                    self.cmb.setCurrentIndex(i)
            else:
                for i, f in enumerate(fields_from_layer(self._layer)):
                    if f.is_numeric():
                        self.cmb.setCurrentIndex(i)
                        break
        self.cmb.blockSignals(False)

    def _current_field(self):
        return self.cmb.currentData() if not self._is_raster else None

    def _current_band(self):
        return int(self.cmb.currentData() or 1) if self._is_raster else 1

    def _collect_spec(self):
        if self._is_raster:
            return {"raster": True, "layer": self._layer,
                    "band": self._current_band()}
        return {"raster": False, "layer": self._layer,
                "field": self._current_field() or ""}

    def _refresh(self, *_):
        spec = self._collect_spec()
        from ggis.exec import guard as _g
        if not (_g.ui_mode() and _g.on_ui_thread()):
            return self._apply(*(_collect_heavy(spec) or (None, None, "")))
        return self._refresh_async(spec)

    def _refresh_async(self, spec):
        from ggis.exec import task as _et
        prev = getattr(self, "_pending", None)
        if prev is not None and not prev.done:
            prev.cancel()
        self._seq += 1
        token = self._seq
        try:
            self.view.setHint(_tr("统计中…"))
        except Exception:
            exc_note("_refresh_async @ ggis/ui/views/map/dialogs/histogram.py:223")
            pass
        t = _et.submit(_collect_heavy, spec, name=_tr("统计"), kind="cpu")
        self._pending = t
        t.on_done(lambda ev: self._on_collected(ev, token))
        t.on_fail(lambda ev: self._on_collect_failed(ev, token))
        return t

    def _on_collected(self, ev, token):
        if token != self._seq or ev.get("cancelled"):
            return
        self._apply(*(ev.get("result") or (None, None, "")))

    def _on_collect_failed(self, ev, token):
        if token != self._seq:
            return
        try:
            self.view.setHint(_tr("统计失败：{0}").format(ev.get("error")))
        except Exception:
            exc_note("_on_collect_failed @ ggis/ui/views/map/dialogs/histogram.py:241")
            pass

    def _apply(self, vals, st, note):
        if st is None:
            st = FieldStats([], 0, "")
        vals = vals if vals is not None else []
        banks = int(self.sp_bins.value())
        bins = banks if banks > 0 else None
        counts, edges = histogram(vals, bins=bins)
        if self.chk_log.isChecked() and counts:
            import math
            counts = [int(round(math.log1p(c))) for c in counts]

        self.view.setXLabel(
            _tr("像元值") if self._is_raster else _tr("字段值"))
        self.view.setHint(note or _tr("没有可统计的数值"))
        self.view.setHistogram(counts, edges)

        fmt = _fmt_num
        self._stat_labels["count"].setText("{:,}".format(st.count))
        self._stat_labels["unique"].setText(
            "{:,}".format(st.unique) if st.unique else "-")
        self._stat_labels["min"].setText(fmt(st.minimum) if st.count else "-")
        self._stat_labels["max"].setText(fmt(st.maximum) if st.count else "-")
        self._stat_labels["mean"].setText(fmt(st.mean) if st.count else "-")
        self._stat_labels["median"].setText(
            fmt(st.median) if st.count else "-")
        self._stat_labels["std"].setText(fmt(st.std) if st.count else "-")
        self._stat_labels["total"].setText(fmt(st.total) if st.count else "-")
        self._stat_labels["skipped"].setText("{:,}".format(st.skipped))

        if note:
            self.lbl_note.setText(note)
        elif st.skipped:
            self.lbl_note.setText(
                _tr("已跳过 {0} 个空值 / 非数值").format(st.skipped))
        else:
            self.lbl_note.setText("")


def _collect_heavy(spec):
    note = ""
    if spec.get("raster"):
        lyr = spec.get("layer")
        band = int(spec.get("band") or 1)
        vals = raster_band_values(lyr, band)
        st = raster_band_stats(lyr, band)
        if not vals:
            note = _tr("该波段没有有效像元")
        return vals, st, note

    lyr = spec.get("layer")
    name = str(spec.get("field") or "")
    if not name:
        return [], FieldStats([], 0, ""), _tr("这个图层没有字段可选")
    vals, skipped = collect_values(lyr, name)
    st = FieldStats(vals, skipped, name)
    if not vals:
        note = _tr("字段「{0}」里没有数值").format(name)
    elif st.count > _MAX_VECTOR_SAMPLES:
        step = int(st.count / float(_MAX_VECTOR_SAMPLES)) + 1
        vals = vals[::step]
        note = _tr("数据量较大，已按 1/{0} 抽样绘制").format(step)
    return vals, st, note


def _fmt_num(v):
    try:
        f = float(v)
    except Exception:
        exc_note("_fmt_num @ ggis/ui/views/map/dialogs/histogram.py:329")
        return str(v)
    a = abs(f)
    if f == 0:
        return "0"
    if a >= 1e7 or a < 1e-3:
        return "%.4g" % f
    if a >= 1000:
        return "{:,.2f}".format(f)
    return "{:.4f}".format(f).rstrip("0").rstrip(".") or "0"


class GgsHistBins(QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsHistBins")
class GgsHistLog(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsHistLog")
class GgsHistNote(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsHistNote")
class GgsHistStatCap(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsHistStatCap")
class GgsHistStatValue(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsHistStatValue")
