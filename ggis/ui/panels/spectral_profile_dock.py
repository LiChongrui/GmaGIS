# -*- coding: utf-8 -*-

from __future__ import annotations

import logging

from matplotlib.ticker import MaxNLocator, FuncFormatter
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QComboBox, QHBoxLayout,
                               QLabel, QSizePolicy,
                               QVBoxLayout, QWidget)

from ggis.core.app import i18n
from ggis.core.style.raster_display import sample_point
from ...exec import task as exec_task
from ggis.ui.charts.mpl_export import MplExportButton
from ggis.ui.panels.pick_dock import (GgsPickDockBase, _canvas_crs, _fmt_coord,
                         _layer_crs, convert_point)
from ggis.ui.charts.mpl_chart import MplBusyMixin, MplChartBase, theme_chart_colors
from ggis.common.widgets.separators import GgsSepV
from ggis.common.widgets.inputs import GgsDockComboBox
from ggis.ui.framework.docks import GgsDockBody
from ggis.ui.panels.layertree import GgsDockToolbar
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
_log = logging.getLogger("gmagis")

_tr = i18n.tr


_PALETTE = [
    (31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40),
    (148, 103, 189), (140, 86, 75), (227, 119, 194), (127, 127, 127),
    (188, 189, 34), (23, 190, 207),
]

_SPECTRAL_COLOR = (200, 60, 160)


class _MultiCheckCombo(GgsDockComboBox):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModel(QStandardItemModel(self))
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self._placeholder = _tr("选择图层…")
        self.lineEdit().setPlaceholderText(self._placeholder)
        self.lineEdit().setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.view().viewport().installEventFilter(self)
        self.setMinimumWidth(120)
        self._refresh_text()

    def eventFilter(self, obj, event):
        if obj is self.view().viewport() \
                and event.type() == QEvent.Type.MouseButtonRelease:
            idx = self.view().indexAt(event.pos())
            if idx.isValid():
                item = self.model().itemFromIndex(idx)
                cur = item.checkState()
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if cur == Qt.CheckState.Checked
                    else Qt.CheckState.Checked)
                self._refresh_text()
                return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.showPopup()
        else:
            super().mousePressEvent(event)

    def add_layer_item(self, key, name):
        item = QStandardItem(name)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled
                      | Qt.ItemFlag.ItemIsUserCheckable)
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        item.setData(key, Qt.ItemDataRole.UserRole)
        self.model().appendRow(item)

    def clear_layers(self):
        self.model().clear()

    def set_checked(self, keys):
        keys = set(keys)
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in keys
                else Qt.CheckState.Unchecked)

    def checked_keys(self):
        out = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out

    def current_layer_keys(self):
        return [self.model().item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.model().rowCount())]

    def _refresh_text(self):
        n = sum(1 for i in range(self.model().rowCount())
                if self.model().item(i).checkState() == Qt.CheckState.Checked)
        self.setEditText(_tr("已选 %d 个图层") % n if n
                         else self._placeholder)


class _SpectralCurve(MplBusyMixin, MplChartBase):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsSpectralPlot")
        self.setMinimumHeight(200)
        self._series = []
        self._status = ""
        self._busy_arts = []
        self._busy_text = None
        self._rect_default = [0.13, 0.32, 0.83, 0.56]
        self.ax.set_position(self._rect_default)

    def set_series(self, series):
        self._series = list(series or [])
        self._redraw()

    def set_status(self, text):
        self._status = str(text or "")
        self._redraw()

    def _redraw(self):
        ax = self.ax
        ax.clear()
        th = theme_chart_colors()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_formatter(
            FuncFormatter(lambda v, _pos: "%g" % v))
        ax.tick_params(color=th["dim"], labelcolor=th["dim"], labelsize=7.5)
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_color(th["dim"])
            sp.set_linewidth(1.0)
        ax.grid(True, axis="both", color=th["border"], alpha=0.35,
                linewidth=0.5, linestyle="--")
        ax.set_axisbelow(True)

        allv = []
        for (_lbl, _c, xs, ys) in self._series:
            allv.extend(v for v in ys if v is not None and v == v)
        if not allv:
            self.ax.set_position(self._rect_default)
            self._finish_draw()
            return

        for (lbl, color, xs, ys) in self._series:
            n = len(ys)
            if n == 0:
                continue
            xa, ya = [], []
            for i, v in enumerate(ys):
                xv = xs[i] if (xs and i < len(xs)) else (i + 1)
                xa.append(float(xv))
                ya.append(float(v) if (v is not None and v == v)
                          else float("nan"))
            style = dict(color=self._color_to_hex(color, th["accent"]),
                         linewidth=1.0, label=lbl)
            if n == 1:
                style.update(marker="o", markersize=4, linestyle="None")
            ax.plot(xa, ya, **style)

        _xs = [x for (_l, _c, xs, ys) in self._series
               if xs for x in xs]
        if _xs:
            _bmin, _bmax = min(_xs), max(_xs)
            if _bmax > _bmin:
                ax.set_xlim(_bmin - 0.5, _bmax + 0.5)
            else:
                ax.set_xlim(_bmin - 1, _bmax + 1)

        ax.set_xlabel(_tr("波段"), color=th["dim"], fontsize=7.5)
        ax.xaxis.set_label_coords(0.5, -0.06)

        self._place_legend(ax, th)

        self._finish_draw()


    def _place_legend(self, ax, th):
        n = len(self._series)
        if n == 0:
            return
        ncol = max(1, min(n, 6))
        leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12),
                        ncol=ncol, fontsize=7.5, frameon=False)
        for t in leg.get_texts():
            t.set_color(th["text"])
        try:
            self._finish_draw()
            renderer = self.figure.canvas.get_renderer()
            if renderer is None:
                return
            inv = self.figure.transFigure.inverted()
            bb = leg.get_window_extent(renderer)
            (fx0, fy0), (fx1, fy1) = inv.transform(bb.get_points())
            leg_w = fx1 - fx0
            leg_h = fy1 - fy0
            if leg_w > 0.83 and ncol > 1:
                one = leg_w / ncol
                new_ncol = max(1, int(0.83 / one))
                if new_ncol < ncol:
                    ncol = new_ncol
                    leg = ax.legend(loc="upper center",
                                    bbox_to_anchor=(0.5, -0.12),
                                    ncol=ncol, fontsize=7.5, frameon=False)
                    for t in leg.get_texts():
                        t.set_color(th["text"])
                    bb = leg.get_window_extent(renderer)
                    (fx0, fy0), (fx1, fy1) = inv.transform(bb.get_points())
                    leg_h = fy1 - fy0
            bottom_margin = 0.04
            label_gap = 0.06
            need_bottom = bottom_margin + label_gap + leg_h
            need_bottom = min(need_bottom, 0.45)
            top = 0.92
            if top - need_bottom < 0.30:
                need_bottom = top - 0.30
            ax.set_position([0.13, need_bottom, 0.83, top - need_bottom])
            self._finish_draw()
        except Exception:
            _log.exception("silent exception in _place_legend")


def _layer_key(layer):
    try:
        k = layer.id()
        if k:
            return str(k)
    except Exception:
        _log.exception("silent exception in _layer_key")
    return "id%d" % id(layer)


def _compute_spectral(items, cc):
    out = []
    log = logging.getLogger("gmagis")
    for it in items:
        layer = it["layer"]
        lx, ly = it["cx"], it["cy"]
        converted = False
        if cc is not None:
            try:
                lc = _layer_crs(layer)
                if lc is not None:
                    px, py = convert_point(cc, lc, it["cx"], it["cy"])
                    if cc != lc and (px, py) == (it["cx"], it["cy"]):
                        converted = False
                    else:
                        lx, ly = px, py
                        converted = True
            except Exception:
                _log.exception("silent exception in _compute_spectral")
                converted = False
        s = None
        try:
            s = sample_point(layer, lx, ly)
        except Exception:
            _log.exception("silent exception in _compute_spectral")
            s = None
        if s is None:
            try:
                s2 = sample_point(layer, it["cx"], it["cy"])
                if s2 is not None:
                    s = s2
                    lx, ly = it["cx"], it["cy"]
            except Exception:
                _log.exception("silent exception in _compute_spectral")
        bands = list(s.get("bands") or []) if s else []
        values = list(s.get("values") or []) if s else []
        out.append({"key": it["key"], "name": it["name"],
                    "color": it["color"], "bands": bands,
                    "values": values, "ok": s is not None})
        log.debug("[spectral] 图层=%s 图层点=(%.6f,%.6f) 换算=%s 采样=%s",
                  it["name"], lx, ly,
                  ("是(%s,%s)" % (round(lx, 6), round(ly, 6)))
                  if converted else "否",
                  ("有%d值" % len(values)) if s else "空")
    return out


class GgsSpectralDock(GgsPickDockBase):

    def __init__(self, title=_tr("光谱曲线"), parent=None):
        super().__init__(title, parent)
        self.setObjectName("GgsSpectralDock")
        self._cx = 0.0
        self._cy = 0.0
        self._has_point = False
        self._layers_provider = None
        self._layer_provider = None
        self._tree_provider = None
        self._centre_provider = None
        self._action_name = "spectral_profile"

        self._selected = set()
        self._last = {}
        self._req_seq = 0
        self._pending_task = None

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 0, 6, 2)
        lay.setSpacing(4)
        self._build(lay)
        self.setWidget(body)


    def set_layer_provider(self, fn):
        self._layer_provider = fn

    def set_layers_provider(self, fn):
        self._layers_provider = fn

    def set_layer_tree_provider(self, fn):
        self._tree_provider = fn

    def set_centre_provider(self, fn):
        self._centre_provider = fn

    def _build(self, lay):
        bar = GgsDockToolbar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        bl.setSpacing(2)
        self.btn_pick = GgsSmallButtonStyle1(
            "select", _tr("地图取点"), self._on_toggle_pick)
        self.btn_pick.setChecked(False)
        self._pick_btn = self.btn_pick
        bl.addWidget(self.btn_pick)
        self.btn_export = MplExportButton(
            lambda: self.curve.figure, self,
            on_message=lambda m: self.lbl_status.setText(m))
        bl.addWidget(self.btn_export)
        bl.addSpacing(6)
        bl.addWidget(GgsSepV())
        bl.addSpacing(6)
        lab = QLabel(_tr("图层"))
        lab.setObjectName("GgsDimLabel")
        bl.addWidget(lab)
        self.cmb_layers = _MultiCheckCombo(self)
        self.cmb_layers.model().dataChanged.connect(self._on_layers_changed)
        bl.addWidget(self.cmb_layers, 1)
        bar.setSizePolicy(QSizePolicy.Policy.Preferred,
                          QSizePolicy.Policy.Fixed)
        lay.addWidget(bar)

        coord_row = QWidget(self)
        cl = QHBoxLayout(coord_row)
        cl.setContentsMargins(8, 2, 8, 2)
        cl.setSpacing(4)
        self.lbl_coord = QLabel(_tr("尚未取点"))
        self.lbl_coord.setObjectName("GgsDimLabel")
        self.lbl_coord.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        cl.addWidget(self.lbl_coord)
        cl.addStretch(1)
        lay.addWidget(coord_row)

        self.curve = _SpectralCurve(self)
        lay.addWidget(self.curve, 1)

        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("GgsDimLabel")
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)

    def _gather_layers(self):
        out = []
        tree = None
        if self._tree_provider is not None:
            try:
                tree = self._tree_provider()
            except Exception:
                logging.getLogger("gmagis").exception(
                    "光谱候选池：图层树 provider 失败")
                tree = None
        if tree is not None:
            self._ensure_tree_wired(tree)
            try:
                out = list(reversed(tree.layers()))
            except Exception:
                logging.getLogger("gmagis").exception(
                    "光谱候选池：读取图层树 layers() 失败")
                out = []
        if not out and self._layers_provider is not None:
            try:
                out = list(self._layers_provider() or [])
            except Exception:
                logging.getLogger("gmagis").exception(
                    "光谱候选池：layers provider 失败")
                out = []
        if not out and self._layer_provider is not None:
            try:
                l = self._layer_provider()
                if l is not None:
                    out = [l]
            except Exception:
                _log.exception("silent exception in _gather_layers")
        return [l for l in out
                if l is not None and l.is_raster() and l.is_valid()]

    def _color_for(self, idx):
        return QColor(*_PALETTE[idx % len(_PALETTE)])

    def _ensure_tree_wired(self, tree):
        if getattr(self, "_tree_wired", None) is tree:
            return
        old = getattr(self, "_tree_wired", None)
        if old is not None:
            try:
                old.membershipChanged.disconnect(
                    self._on_tree_membership_changed)
            except Exception:
                _log.exception("silent exception in _ensure_tree_wired")
        self._tree_wired = tree
        try:
            tree.membershipChanged.connect(
                self._on_tree_membership_changed)
        except Exception:
            logging.getLogger("gmagis").exception(
                "光谱候选池：挂接图层树 membershipChanged 失败")

    def _on_tree_membership_changed(self):
        try:
            self._redraw()
        except Exception:
            logging.getLogger("gmagis").exception(
                "光谱候选池：树成员变化刷新失败")

    def _sync_combo(self, available):
        keys_now = [(_layer_key(l), l.name()) for l in available]
        if [k for k, _ in keys_now] == self.cmb_layers.current_layer_keys():
            return
        self.cmb_layers.blockSignals(True)
        self.cmb_layers.clear_layers()
        for key, name in keys_now:
            self.cmb_layers.add_layer_item(key, name)
        if not self._selected:
            self._selected = self._default_selected_keys(available)
        self.cmb_layers.set_checked(self._selected)
        self.cmb_layers._refresh_text()
        self.cmb_layers.blockSignals(False)

    def _default_selected_keys(self, available):
        cur = None
        if self._layer_provider is not None:
            try:
                cur = self._layer_provider()
            except Exception:
                _log.exception("silent exception in _default_selected_keys")
                cur = None
        if cur is None or not (cur.is_raster() and cur.is_valid()):
            return set()
        key = _layer_key(cur)
        if any(_layer_key(l) == key for l in available):
            return {key}
        return set()

    def _on_layers_changed(self, *args):
        self._selected = set(self.cmb_layers.checked_keys())
        self._redraw()

    def showEvent(self, e):
        try:
            super().showEvent(e)
        except Exception:
            _log.exception("silent exception in showEvent")
        self._redraw()

    def _set_pos_label(self):
        if not self._has_point:
            self.lbl_coord.setText(_tr("尚未取点"))
        else:
            self.lbl_coord.setText(
                _tr("位置：{0}, {1}").format(
                    _fmt_coord(self._cx), _fmt_coord(self._cy)))

    def set_point(self, cx, cy):
        try:
            self._cx, self._cy = float(cx), float(cy)
        except Exception:
            _log.exception("silent exception in set_point")
            return
        self._has_point = True
        self._set_canvas_point(self._cx, self._cy)
        self._set_pos_label()
        self._redraw()

    def _redraw(self):
        available = self._gather_layers()
        self._sync_combo(available)
        self._selected &= {_layer_key(l) for l in available}
        ordered = sorted(available, key=lambda l: _layer_key(l))
        selected_keys = self._selected

        layers_sorted = ordered
        canvas = None
        try:
            pair = self._tool_pair()
            if pair:
                canvas = pair[0]
        except Exception:
            _log.exception("silent exception in _redraw")
            canvas = None
        cc = _canvas_crs(canvas) if canvas is not None else None

        has_point = self._has_point

        self._req_seq += 1
        token = self._req_seq
        if not has_point or not selected_keys:
            self.curve.end_fetching()
            self.curve.set_series([])
            self._last = {}
            self._update_status(has_point, canvas, cc, available)
            return

        items = []
        for idx, layer in enumerate(layers_sorted):
            key = _layer_key(layer)
            if key not in selected_keys:
                continue
            items.append({"layer": layer, "key": key,
                          "name": layer.name(),
                          "color": self._color_for(idx),
                          "cx": self._cx, "cy": self._cy})
        self.curve.begin_fetching(_tr("正在提取数据…"), 200)

        def _on_spectral_done(ev):
            if ev.get("cancelled"):
                return
            if token != self._req_seq:
                return
            self.curve.end_fetching()
            res = ev.get("result") or []
            series = [(d["name"], d["color"], d["bands"], d["values"])
                      for d in res]
            self._last = {d["key"]: (d["name"], d["color"], d["bands"],
                                     d["values"], d["ok"]) for d in res}
            self.curve.set_series(series)
            self._update_status(has_point, canvas, cc, available)

        try:
            self._pending_task = exec_task.submit(
                _compute_spectral, items, cc,
                kind="cpu", name=_tr("光谱取数"), on_done=_on_spectral_done)
        except Exception:
            _log.exception("silent exception in _redraw")
            self.curve.end_fetching()
            self.curve.set_series([])
            self._update_status(has_point, canvas, cc, available)

    def _update_status(self, has_point, canvas, cc, available=None):
        if not has_point:
            self.curve.set_status(
                _tr("请点击取样点"))
            return
        n_total = len(self._last)
        if n_total == 0:
            if not (available if available is not None else self._gather_layers()):
                self.curve.set_status(
                    _tr("请先加载栅格图层"))
            else:
                self.curve.set_status(
                    _tr("请勾选栅格图层"))
            return
        keys = list(self._last)
        sampled = [k for k in keys if self._last.get(k, (None,) * 5)[4]]
        if canvas is None or cc is None:
            self.curve.set_status(
                _tr("无法换算坐标"
                    ""))
            logging.getLogger("gmagis").warning(
                "[spectral] 取样点换算被跳过：canvas=%r cc=%r "
                "（_cx,_cy=%r）", canvas, cc, (self._cx, self._cy))
            return
        if not sampled:
            self.curve.set_status(
                _tr("取样点超出数据范围"
                    ""))
            return
        self.curve.set_status("")

    def _handle_pick(self, cx, cy):
        self.set_point(cx, cy)
