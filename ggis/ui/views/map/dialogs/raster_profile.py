# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
                               QHBoxLayout,
                               QLabel,
                               QSizePolicy,
                               QVBoxLayout,
                               QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ggis.core.app import i18n
from ggis.core.style.raster_display import (_fmt_value, sample_axis,
                                    sample_point, stats_for)
from ggis.exec import task as exec_task
from ggis.ui.panels.pick_dock import (GgsPickDockBase, _canvas_crs, _fmt_coord,
                        _layer_crs, convert_point)

from ggis.ui.charts.mpl_chart import MplBusyMixin, theme_chart_colors
from ggis.ui.charts.mpl_export import MplExportButton
from ggis.common.widgets.separators import GgsSepV
from ggis.common.widgets.inputs import GgsDockComboBox
from ggis.common.widgets.displays import GgsDimLabel
from ggis.ui.framework.docks import GgsDockBody
from ggis.ui.panels.layertree import GgsDockToolbar
from ggis.ui.panels.identify import GgsIdentifyCoord
from ggis.common.widgets.buttons import GgsSmallButtonStyle1

_tr = i18n.tr

MAX_SAMPLES = 600

_CORAL_HEX = "#ff7f50"


def _value_range_for(layer, band):
    try:
        st = stats_for(layer, band=max(0, int(band) - 1))
        if st:
            vlo, vhi = st.get("min"), st.get("max")
            if vlo is not None and vhi is not None and vhi > vlo:
                return (float(vlo), float(vhi))
    except Exception:
        exc_note("_value_range_for @ ggis/ui/views/map/dialogs/raster_profile.py:72")
        pass
    return (0.0, 255.0)


def _profile_frames(layer, band):
    x_ext = (0.0, 1.0)
    y_ext = (0.0, 1.0)
    try:
        e = layer.extent()
        if e is not None and not e.is_empty():
            x_ext = (float(e.xmin), float(e.xmax))
            y_ext = (float(e.ymin), float(e.ymax))
    except Exception:
        exc_note("_profile_frames @ ggis/ui/views/map/dialogs/raster_profile.py:94")
        pass
    vlo, vhi = _value_range_for(layer, band)
    if vhi - vlo < 1e-9:
        vlo, vhi = vlo - 0.5, vhi + 0.5
    return dict(row_x=x_ext, row_y=(vlo, vhi),
                col_x=y_ext, col_y=(vlo, vhi))


def _compute_profile(layer, x, y, band):
    out = {"ok": False, "row": ([], []), "col": ([], []),
           "bval": None, "frames": None}
    try:
        out["frames"] = _profile_frames(layer, band)
    except Exception:
        exc_note("_compute_profile @ ggis/ui/views/map/dialogs/raster_profile.py:115")
        out["frames"] = None
    try:
        s = sample_point(layer, float(x), float(y))
    except Exception:
        exc_note("_compute_profile @ ggis/ui/views/map/dialogs/raster_profile.py:119")
        s = None
    if s is None:
        return out
    try:
        bxs, bys = sample_axis(layer, float(x), float(y), axis="x",
                               max_samples=MAX_SAMPLES, band=band)
    except Exception:
        exc_note("_compute_profile @ ggis/ui/views/map/dialogs/raster_profile.py:127")
        bxs, bys = None, None
    out["row"] = (list(bxs or []), list(bys or []))
    try:
        cxs, cys = sample_axis(layer, float(x), float(y), axis="y",
                               max_samples=MAX_SAMPLES, band=band)
    except Exception:
        exc_note("_compute_profile @ ggis/ui/views/map/dialogs/raster_profile.py:134")
        cxs, cys = None, None
    out["col"] = (list(cxs or []), list(cys or []))
    try:
        vals = list(s.get("values") or [])
        if 1 <= band <= len(vals):
            out["bval"] = vals[band - 1]
    except Exception:
        exc_note("_compute_profile @ ggis/ui/views/map/dialogs/raster_profile.py:142")
        out["bval"] = None
    out["ok"] = True
    return out


class _ProfilePlot(MplBusyMixin, FigureCanvasQTAgg):

    def __init__(self, parent=None):
        fig = Figure(figsize=(4.0, 4.8))
        super().__init__(fig)
        self.figure = fig
        self._busy_arts = []
        self._busy_text = None
        self._row_geom = (0.08, 0.55, 0.89, 0.40)
        self._col_geom = (0.08, 0.05, 0.89, 0.40)
        self.ax_row = fig.add_axes(self._row_geom)
        self.ax_col = fig.add_axes(self._col_geom)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumSize(60, 200)

    _LEFT_MIN = 0.08
    _LEFT_MAX = 0.38
    _RIGHT_PAD = 0.03

    def _fit_y_labels(self):
        try:
            renderer = self.figure.canvas.get_renderer()
            fw = float(self.figure.bbox.width)
        except Exception:
            exc_note("_fit_y_labels @ ggis/ui/views/map/dialogs/raster_profile.py:196")
            return
        if fw <= 0:
            return
        need = self._LEFT_MIN
        for ax in (self.ax_row, self.ax_col):
            try:
                bb = ax.yaxis.get_tightbbox(renderer)
            except Exception:
                exc_note("_fit_y_labels @ ggis/ui/views/map/dialogs/raster_profile.py:205")
                bb = None
            if bb is None:
                continue
            try:
                need = max(need, float(bb.width) / fw + 0.012)
            except Exception:
                exc_note("_fit_y_labels @ ggis/ui/views/map/dialogs/raster_profile.py:211")
                continue
        need = min(need, self._LEFT_MAX)
        for geom, ax in ((self._row_geom, self.ax_row),
                         (self._col_geom, self.ax_col)):
            try:
                _l, b, _w, h = geom
                ax.set_position([need, b,
                                 1.0 - need - self._RIGHT_PAD, h])
            except Exception:
                exc_note("_fit_y_labels @ ggis/ui/views/map/dialogs/raster_profile.py:220")
                return

    @staticmethod
    def _style_axes(ax, th):
        ax.tick_params(color=th["dim"], labelcolor=th["dim"],
                      labelsize=7.5, length=3, width=0.5)
        for sp in ax.spines.values():
            sp.set_visible(True)
            sp.set_color(th["dim"])
            sp.set_linewidth(1.0)
        ax.grid(True, axis="both", color=th["border"], alpha=0.35,
                linewidth=0.5, linestyle="--")
        ax.set_axisbelow(True)

    def set_axes_frames(self, row_frame, col_frame):
        th = theme_chart_colors()
        self.ax_row.clear()
        self._style_axes(self.ax_row, th)
        self._draw_empty(self.ax_row, row_frame, th, _tr("沿行"))
        self.ax_col.clear()
        self._style_axes(self.ax_col, th)
        self._draw_empty(self.ax_col, col_frame, th, _tr("沿列"))
        self._finish_draw_local()

    def set_data(self, row_xs, row_ys, col_xs, col_ys, row_frame, col_frame,
                 row_pos, col_pos, value):
        th = theme_chart_colors()
        self.ax_row.clear()
        self._style_axes(self.ax_row, th)
        self._draw_line(self.ax_row, row_xs, row_ys, row_frame, th,
                        row_pos, value, _tr("沿行"), "X")
        self.ax_col.clear()
        self._style_axes(self.ax_col, th)
        self._draw_line(self.ax_col, col_xs, col_ys, col_frame, th,
                        col_pos, value, _tr("沿列"), "Y")
        self._finish_draw_local()

    @staticmethod
    def _annotate_top(ax, text):
        th = theme_chart_colors()
        ax.annotate(text, xy=(0.5, 1.0), xycoords="axes fraction",
                    xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", color=th["text"],
                    fontsize=7.5, clip_on=False)

    def _draw_empty(self, ax, frame, th, title):
        ax.set_xlim(frame[0][0], frame[0][1])
        ax.set_ylim(frame[1][0], frame[1][1])
        self._annotate_top(ax, title)

    def _draw_line(self, ax, xs, ys, frame, th, pos=None, value=None,
                   title="", coord_label="X"):
        vals = [v for v in ys if v is not None and v == v]
        if not vals:
            self._draw_empty(ax, frame, th, title)
            return
        n = len(ys)
        xa, ya = [], []
        for i, v in enumerate(ys):
            xv = xs[i] if (xs and i < len(xs)) else \
                (frame[0][0] +
                 (i / float(max(1, n - 1))) * ((frame[0][1] - frame[0][0]) or 1.0))
            xa.append(float(xv))
            ya.append(float(v) if (v is not None and v == v) else float("nan"))
        ax.plot(xa, ya, color=th["accent"], linewidth=0.9)
        if pos is not None and value is not None:
            ax.axvline(pos, color=_CORAL_HEX, linewidth=1.0, alpha=0.9, zorder=3)
            ax.axhline(value, color=_CORAL_HEX, linewidth=1.0, alpha=0.9, zorder=3)
            ax.plot([pos], [value], "o", color=_CORAL_HEX, markersize=3.5,
                    zorder=4)
        self._annotate_top(ax, "%s（%s=%s）" % (
            title, coord_label,
            _fmt_value(pos) if pos is not None else "—"))

    def _finish_draw_local(self):
        th = theme_chart_colors()
        try:
            self.figure.patch.set_facecolor(th["panel"])
            self.ax_row.set_facecolor(th["panel"])
            self.ax_col.set_facecolor(th["panel"])
        except Exception:
            exc_note("_finish_draw_local @ ggis/ui/views/map/dialogs/raster_profile.py:281")
            pass
        self._fit_y_labels()
        self.draw_idle()


class GgsProfileDock(GgsPickDockBase):

    def __init__(self, title=_tr("剖面曲线"), parent=None):
        super().__init__(title, parent)
        self.setObjectName("GgsProfileDock")
        self._layer = None
        self._x = 0.0
        self._y = 0.0
        self._layer_provider = None
        self._layer_tree_provider = None
        self._connected_tree = None
        self._centre_provider = None
        self._action_name = "raster_profile"
        self._last_frames = None
        self._has_point = False
        self._req_seq = 0
        self._base_title = _tr("剖面曲线")
        self._layer_name = ""
        try:
            self.set_short_title(self._base_title)
        except Exception:
            exc_note("__init__ @ ggis/ui/views/map/dialogs/raster_profile.py:310")
            pass

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(6, 0, 6, 2)
        lay.setSpacing(4)
        self._build(lay)
        self.setWidget(body)

    def set_layer_provider(self, fn):
        self._layer_provider = fn

    def set_centre_provider(self, fn):
        self._centre_provider = fn

    def _current_layer(self):
        lyr = None
        if self._layer_provider is not None:
            try:
                lyr = self._layer_provider()
            except Exception:
                exc_note("_current_layer @ ggis/ui/views/map/dialogs/raster_profile.py:346")
                lyr = None
        if lyr is None:
            lyr = self._layer
        if lyr is not None and not self._layer_visible(lyr):
            return None
        return lyr

    def set_layer_tree_provider(self, fn):
        self._layer_tree_provider = fn

    def _layer_visible(self, lyr):
        if self._layer_tree_provider is None:
            return True
        try:
            lt = self._layer_tree_provider()
        except Exception:
            exc_note("_layer_visible @ ggis/ui/views/map/dialogs/raster_profile.py:367")
            return True
        if lt is None:
            return True
        try:
            return bool(lt.is_visible(lyr.id()))
        except Exception:
            exc_note("_layer_visible @ ggis/ui/views/map/dialogs/raster_profile.py:373")
            return True

    def _ensure_tree_connection(self):
        if self._layer_tree_provider is None:
            return
        try:
            lt = self._layer_tree_provider()
        except Exception:
            exc_note("_ensure_tree_connection @ ggis/ui/views/map/dialogs/raster_profile.py:385")
            lt = None
        if lt is None or lt is self._connected_tree:
            return
        if self._connected_tree is not None:
            try:
                self._connected_tree.visibilityChanged.disconnect(
                    self._on_layer_visibility_changed)
            except Exception:
                exc_note("_ensure_tree_connection @ ggis/ui/views/map/dialogs/raster_profile.py:393")
                pass
        try:
            lt.visibilityChanged.connect(self._on_layer_visibility_changed)
            self._connected_tree = lt
        except Exception:
            exc_note("_ensure_tree_connection @ ggis/ui/views/map/dialogs/raster_profile.py:398")
            pass

    def _on_layer_visibility_changed(self, _layer_id=None, _on=None):
        try:
            self.refresh()
        except Exception:
            exc_note("_on_layer_visibility_changed @ ggis/ui/views/map/dialogs/raster_profile.py:405")
            pass

    def _redraw(self):
        try:
            self._reload()
        except Exception:
            exc_note("_redraw @ ggis/ui/views/map/dialogs/raster_profile.py:419")
            pass

    def on_current_layer_changed(self):
        try:
            self.refresh()
        except Exception:
            exc_note("on_current_layer_changed @ ggis/ui/views/map/dialogs/raster_profile.py:427")
            pass
        try:
            self._sync_tool()
        except Exception:
            exc_note("on_current_layer_changed @ ggis/ui/views/map/dialogs/raster_profile.py:436")
            pass

    def _need_tool(self):
        if self._current_layer() is None:
            return False
        return super()._need_tool()

    def _on_front_changed(self, front):
        try:
            super()._on_front_changed(front)
        except Exception:
            exc_note("_on_front_changed @ ggis/ui/views/map/dialogs/raster_profile.py:440")
            pass
        if front:
            try:
                self.refresh()
            except Exception:
                exc_note("_on_front_changed @ ggis/ui/views/map/dialogs/raster_profile.py:445")
                pass

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
            lambda: self.plot.figure, self,
            on_message=self._show_export_status)
        bl.addWidget(self.btn_export)
        bl.addSpacing(6)
        bl.addWidget(GgsSepV())
        bl.addSpacing(6)
        bl.addWidget(QLabel(_tr("波段")))
        self.cmb_band = GgsDockComboBox()
        bl.addWidget(self.cmb_band, 1)
        bar.setSizePolicy(QSizePolicy.Policy.Preferred,
                          QSizePolicy.Policy.Fixed)
        lay.addWidget(bar)
        self.bar = bar

        coord_row = QWidget(self)
        cl = QHBoxLayout(coord_row)
        cl.setContentsMargins(8, 2, 8, 2)
        cl.setSpacing(4)
        self.lbl_pos = GgsIdentifyCoord(_tr("（尚未取点）"))
        self.lbl_pos.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        cl.addWidget(self.lbl_pos)
        cl.addStretch(1)
        lay.addWidget(coord_row)
        self.coord_row = coord_row

        self.plot = _ProfilePlot(self)
        lay.addWidget(self.plot, 1)

        self.lbl_info = GgsDimLabel("")
        self.lbl_info.setWordWrap(True)
        lay.addWidget(self.lbl_info)

        self.cmb_band.currentIndexChanged.connect(lambda *_: self._reload())

    def set_layer(self, layer):
        self._layer = layer
        if layer is not None:
            try:
                n = int(layer.band_count() or 1)
            except Exception:
                exc_note("set_layer @ ggis/ui/views/map/dialogs/raster_profile.py:514")
                n = 1
            self._fill_bands(n)
            c = self._raster_centre()
            if c is not None:
                x, y, is_canvas = c
                if is_canvas:
                    lx, ly = x, y
                    pair = self._tool_pair()
                    canvas = pair[0] if pair else None
                    if canvas is not None:
                        lc = _layer_crs(layer)
                        cc = _canvas_crs(canvas)
                        if lc is not None and cc is not None:
                            try:
                                lx, ly = convert_point(cc, lc, x, y)
                            except Exception:
                                exc_note("set_layer @ ggis/ui/views/map/dialogs/raster_profile.py:534")
                                lx, ly = x, y
                    self.set_point(lx, ly, canvas_pt=(x, y))
                else:
                    self.set_point(x, y, canvas_pt=None)
        else:
            self.refresh()

    def _raster_centre(self):
        if self._centre_provider is not None:
            try:
                c = self._centre_provider()
                if c is not None:
                    return (c[0], c[1], True)
            except Exception:
                exc_note("_raster_centre @ ggis/ui/views/map/dialogs/raster_profile.py:549")
                pass
        lyr = self._current_layer()
        if lyr is not None:
            try:
                e = lyr.extent()
                return (e.center()[0], e.center()[1], False)
            except Exception:
                exc_note("_raster_centre @ ggis/ui/views/map/dialogs/raster_profile.py:556")
                pass
        return None

    def set_point(self, x, y, canvas_pt=None):
        try:
            self._x, self._y = float(x), float(y)
        except Exception:
            exc_note("set_point @ ggis/ui/views/map/dialogs/raster_profile.py:569")
            return
        self._has_point = True
        if canvas_pt is not None:
            self._set_canvas_point(canvas_pt[0], canvas_pt[1])
        else:
            self._recompute_canvas_point()
        self.refresh()

    def _recompute_canvas_point(self):
        layer = self._current_layer()
        if layer is None:
            return
        pair = self._tool_pair()
        canvas = pair[0] if pair else None
        if canvas is None:
            return
        lc = _layer_crs(layer)
        cc = _canvas_crs(canvas)
        if lc is None or cc is None:
            return
        cx, cy = convert_point(lc, cc, self._x, self._y)
        self._set_canvas_point(cx, cy)

    def _handle_pick(self, cx, cy):
        layer = self._current_layer()
        if layer is None:
            return
        canvas = None
        try:
            pair = self._tool_pair()
            if pair:
                canvas = pair[0]
        except Exception:
            exc_note("_handle_pick @ ggis/ui/views/map/dialogs/raster_profile.py:604")
            canvas = None
        lx, ly = float(cx), float(cy)
        if canvas is not None:
            try:
                from ggis.core.expr.query import to_layer_point
                lx, ly = to_layer_point(layer, float(cx), float(cy), canvas)
            except Exception:
                exc_note("_handle_pick @ ggis/ui/views/map/dialogs/raster_profile.py:611")
                lx, ly = float(cx), float(cy)
        self._x, self._y = float(lx), float(ly)
        self._set_canvas_point(cx, cy)
        self._has_point = True
        self.refresh()

    def _set_pos_label(self, x, y, value=None):
        try:
            base = _tr("位置：{0}, {1}").format(_fmt_coord(x), _fmt_coord(y))
            if value is not None and value == value:
                base += _tr("　当前值：{0}").format(_fmt_value(value))
            else:
                base += _tr("　当前值：—")
            self.lbl_pos.setText(base)
        except Exception:
            exc_note("_set_pos_label @ ggis/ui/views/map/dialogs/raster_profile.py:627")
            pass

    def _fill_bands(self, n):
        cur = self.cmb_band.currentData()
        self.cmb_band.blockSignals(True)
        self.cmb_band.clear()
        for b in range(1, max(1, int(n)) + 1):
            self.cmb_band.addItem(_tr("波段 {0}").format(b), b)
        i = self.cmb_band.findData(cur)
        self.cmb_band.setCurrentIndex(i if i >= 0 else 0)
        self.cmb_band.blockSignals(False)

    def _band(self):
        return int(self.cmb_band.currentData() or 1)

    def refresh(self):
        self._ensure_tree_connection()
        self._refresh_data(fill_bands=True)

    def _reload(self):
        self._refresh_data(fill_bands=False)

    def _refresh_data(self, fill_bands=False):
        lyr = self._current_layer()
        if lyr is None:
            self._update_title(None)
            self.cmb_band.blockSignals(True)
            self.cmb_band.clear()
            self.cmb_band.blockSignals(False)
            try:
                self.bar.setVisible(False)
                self.coord_row.setVisible(False)
                self.plot.setVisible(False)
            except Exception:
                exc_note("_refresh_data @ ggis/ui/views/map/dialogs/raster_profile.py:672")
                pass
            self.plot.end_fetching()
            try:
                self._sync_tool()
            except Exception:
                exc_note("_refresh_data @ ggis/ui/views/map/dialogs/raster_profile.py:679")
                pass
            self.lbl_info.setText("")
            self.lbl_info.setVisible(False)
            return
        try:
            self.bar.setVisible(True)
            self.coord_row.setVisible(True)
            self.plot.setVisible(True)
        except Exception:
            exc_note("_refresh_data @ ggis/ui/views/map/dialogs/raster_profile.py:690")
            pass
        self._update_title(lyr)
        if fill_bands:
            try:
                n = int(lyr.band_count() or 1)
            except Exception:
                exc_note("_refresh_data @ ggis/ui/views/map/dialogs/raster_profile.py:688")
                n = 1
            self._fill_bands(n)
        self.plot.begin_fetching(_tr("正在提取数据…"), 200)
        self._req_seq += 1
        token = self._req_seq
        x, y, b = self._x, self._y, self._band()

        def _on_done(ev):
            if ev.get("cancelled"):
                return
            if token != self._req_seq:
                return
            self.plot.end_fetching()
            self.lbl_info.setText("")
            self.lbl_info.setVisible(False)
            self._apply_profile(ev.get("result") or {})

        try:
            self._pending_task = exec_task.submit(
                _compute_profile, lyr, x, y, b,
                kind="cpu", name=_tr("剖面取数"), on_done=_on_done)
        except Exception:
            exc_note("_refresh_data @ ggis/ui/views/map/dialogs/raster_profile.py:716")
            self.plot.end_fetching()
            self.lbl_info.setText("")
            self.lbl_info.setVisible(False)

    def _apply_profile(self, res):
        frames = res.get("frames")
        if frames is not None:
            self._last_frames = frames
        if frames is not None:
            row_fr = (frames["row_x"], frames["row_y"])
            col_fr = (frames["col_x"], frames["col_y"])
        else:
            fr = self._last_frames or dict(
                row_x=(0.0, 1.0), row_y=(0.0, 255.0),
                col_x=(0.0, 1.0), col_y=(0.0, 255.0))
            row_fr = (fr["row_x"], fr["row_y"])
            col_fr = (fr["col_x"], fr["col_y"])
        if not res.get("ok"):
            self.plot.set_axes_frames(row_fr, col_fr)
            if self._has_point:
                self._set_pos_label(self._x, self._y, None)
            return
        row_xs, row_ys = res["row"]
        col_xs, col_ys = res["col"]
        bval = res["bval"]
        self.plot.set_data(row_xs, row_ys, col_xs, col_ys, row_fr, col_fr,
                           self._x, self._y, bval)
        if self._has_point:
            self._set_pos_label(self._x, self._y, bval)

    def _update_title(self, lyr):
        name = ""
        if lyr is not None:
            try:
                name = lyr.name() or ""
            except Exception:
                exc_note("_update_title @ ggis/ui/views/map/dialogs/raster_profile.py:761")
                name = ""
        self._layer_name = name
        title = self._base_title
        if name:
            title = "%s - %s" % (self._base_title, name)
        try:
            self.set_title_label(title)
        except Exception:
            exc_note("_update_title @ ggis/ui/views/map/dialogs/raster_profile.py:769")
            pass

    def _show_export_status(self, msg):
        try:
            self.lbl_info.setText(msg)
            self.lbl_info.setVisible(True)
        except Exception:
            exc_note("_show_export_status @ ggis/ui/views/map/dialogs/raster_profile.py:777")
            pass


