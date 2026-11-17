# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter,
                           QPalette, QPen, QPolygonF)
from PySide6.QtWidgets import (
                               QCheckBox,
                               QComboBox,
                               QDialogButtonBox,
                               QGridLayout,
                               QHBoxLayout,
                               QLabel,
                               QMessageBox,
                               QSizePolicy,
                               QToolButton,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n as _i18n
from ggis.core.style.user_ramps import band_edges as _band_edges
from ggis.common.styling import icons as _icons
from ggis.common.widgets.inputs import GgsColorField
from ggis.common.base.dialog import GgsDialog, GgsMsgBox
import logging
from PySide6.QtWidgets import QDoubleSpinBox, QLineEdit, QPushButton
_log = logging.getLogger("gmagis")


class _HLine(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            try:
                c = self.palette().color(QPalette.ColorRole.Mid)
            except Exception:
                _log.exception("silent exception in paintEvent")
                c = QColor("#c9cdd4")
            p.fillRect(self.rect(), c)
        finally:
            p.end()


class _GradientStopBar(QWidget):

    changed = Signal()
    selectedChanged = Signal(int)
    pickRequested = Signal(int)

    BAR_H = 22
    MARK_H = 16
    PAD = 7
    BAR_PAD = PAD

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsRampStopBar")
        self.setMinimumHeight(self.BAR_H + self.MARK_H + 6)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)
        self._stops = []
        self._sel = -1
        self._drag = -1
        self._discrete = False
        self.setMouseTracking(True)
        self.setToolTip("")

    def setDiscrete(self, on):
        on = bool(on)
        if on != self._discrete:
            self._discrete = on
            self.update()

    def isDiscrete(self):
        return bool(self._discrete)

    def stops(self):
        return [(p, c) for p, c in self._stops]

    def setStops(self, stops, selected=None):
        self._stops = [(max(0.0, min(1.0, float(p))), str(c))
                       for p, c in (stops or [])]
        head = self._ensure_ends()
        if selected is not None:
            self._sel = int(selected) + head
        elif self._sel >= len(self._stops):
            self._sel = len(self._stops) - 1
        if self._sel >= 0:
            self._sel = min(self._sel, max(0, len(self._stops) - 1))
        self.update()

    def _ensure_ends(self):
        if len(self._stops) < 2:
            return 0
        head = 0
        if float(self._stops[0][0]) > 1e-6:
            self._stops.insert(0, (0.0, self._stops[0][1]))
            head = 1
        if float(self._stops[-1][0]) < 1.0 - 1e-6:
            self._stops.append((1.0, self._stops[-1][1]))
        return head

    def selected(self):
        return self._sel

    def setSelected(self, i):
        i = int(i)
        if i == self._sel:
            return
        if 0 <= i < len(self._stops):
            self._sel = i
            self.update()
            self.selectedChanged.emit(i)

    def _span(self):
        return max(1, self.width() - self.PAD * 2)

    def _x_of(self, pos):
        return self.PAD + float(pos) * self._span()

    def _pos_of(self, x):
        return max(0.0, min(1.0, (float(x) - self.PAD) / float(self._span())))

    def _hit(self, x):
        best, bd = -1, 10.0
        for i, (pos, _c) in enumerate(self._stops):
            d = abs(self._x_of(pos) - float(x))
            if d < bd:
                best, bd = i, d
        return best

    def mousePressEvent(self, e):
        x = float(e.position().x())
        i = self._hit(x)
        if e.button() == Qt.MouseButton.RightButton:
            if i >= 0 and len(self._stops) > 2:
                self._stops.pop(i)
                self._sel = min(i, len(self._stops) - 1)
                self.update()
                self.changed.emit()
                self.selectedChanged.emit(self._sel)
            e.accept()
            return
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(e)
        if i < 0:
            self._stops.append((self._pos_of(x), self._color_at(x)))
            self._stops.sort(key=lambda t: t[0])
            self._sel = [k for k, (p, _c) in enumerate(self._stops)
                         if abs(p - self._pos_of(x)) < 1e-9][0]
            self._drag = self._sel
            self.update()
            self.changed.emit()
            self.selectedChanged.emit(self._sel)
            e.accept()
            return
        if i != self._sel:
            self._sel = i
            self.update()
            self.selectedChanged.emit(i)
        self._drag = i
        e.accept()

    def mouseMoveEvent(self, e):
        if self._drag < 0:
            return super().mouseMoveEvent(e)
        if not (0 <= self._drag < len(self._stops)):
            self._drag = -1
            return
        pos = self._pos_of(float(e.position().x()))
        col = self._stops[self._drag][1]
        self._stops[self._drag] = (pos, col)
        self.update()
        self.changed.emit()
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._drag >= 0:
            cur = self._stops[self._drag] if self._drag < len(self._stops) \
                else None
            self._drag = -1
            if cur is not None:
                self._stops.sort(key=lambda t: t[0])
                self._sel = self._stops.index(cur)
            self.update()
            self.changed.emit()
            self.selectedChanged.emit(self._sel)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        i = self._hit(float(e.position().x()))
        if i >= 0:
            if i != self._sel:
                self._sel = i
                self.update()
                self.selectedChanged.emit(i)
            self.pickRequested.emit(i)
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def _color_at(self, x):
        if not self._stops:
            return "#FFFFFF"
        pos_now = self._pos_of(x)
        if self._discrete:
            try:
                edges = _band_edges(self._stops)
                nstop = len(self._stops)
                for i, (_p, col) in enumerate(self._stops):
                    if pos_now < edges[i + 1] or i == nstop - 1:
                        return str(col)
            except Exception:
                _log.exception("silent exception in _color_at")
        prev = self._stops[0]
        for pos, col in self._stops:
            if pos_now <= pos:
                if pos <= prev[0]:
                    return str(col)
                k = (pos_now - prev[0]) / (pos - prev[0])
                a, b = QColor(prev[1]), QColor(col)
                return QColor(
                    int(round(a.red() + (b.red() - a.red()) * k)),
                    int(round(a.green() + (b.green() - a.green()) * k)),
                    int(round(a.blue() + (b.blue() - a.blue()) * k))
                ).name()
            prev = (pos, col)
        return str(self._stops[-1][1])

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            bw = max(2.0, float(self.width()) - self.BAR_PAD * 2)
            bar = QRectF(self.BAR_PAD, 3.0, bw, self.BAR_H)
            if self._stops:
                p.setPen(Qt.PenStyle.NoPen)
                if self._discrete:
                    edges = _band_edges(self._stops)
                    nstop = len(self._stops)
                    for i, (_pos, col) in enumerate(self._stops):
                        x0 = self._x_of(edges[i])
                        x1 = self._x_of(edges[min(i + 1, nstop)])
                        if x1 - x0 <= 0.0:
                            continue
                        p.setBrush(QColor(col))
                        p.drawRect(QRectF(x0, bar.top(), x1 - x0, bar.height()))
                else:
                    g = QLinearGradient(bar.left(), 0.0, bar.right(), 0.0)
                    for pos, col in self._stops:
                        g.setColorAt(max(0.0, min(1.0, pos)), QColor(col))
                    p.setBrush(QBrush(g))
                    p.drawRect(bar)
            p.setBrush(Qt.BrushStyle.NoBrush)
            try:
                edge = self.palette().color(QPalette.ColorRole.Mid)
            except Exception:
                _log.exception("silent exception in paintEvent")
                edge = QColor("#666666")
            p.setPen(QPen(edge, 1.0))
            p.drawRect(bar)
            hi = None
            try:
                hi = self.palette().color(QPalette.ColorRole.Highlight)
            except Exception:
                _log.exception("silent exception in paintEvent")
                hi = QColor("#4c9be8")
            edge = QColor(0, 0, 0, 150)
            INSET_X, INSET_Y = 1.0, 2.0
            for i, (pos, col) in enumerate(self._stops):
                x = self._x_of(pos)
                cur = (i == self._sel)
                w = 13.0 if cur else 9.0
                hw = w / 2.0
                top = bar.bottom() + 2.5
                tip = hw + 1.0
                bot = top + hw + 7.0
                poly = QPolygonF([
                    QPointF(x, top),
                    QPointF(x + hw, top + tip),
                    QPointF(x + hw, bot),
                    QPointF(x - hw, bot),
                    QPointF(x - hw, top + tip),
                ])
                if cur:
                    lx = min(max(x, bar.left() + INSET_X),
                             bar.right() - INSET_X)
                    p.setPen(QPen(hi, 1.0))
                    p.drawLine(QPointF(lx, bar.top() + INSET_Y),
                               QPointF(lx, bar.bottom() - INSET_Y))
                    p.setPen(QPen(hi, 2.0))
                else:
                    p.setPen(QPen(edge, 1.0))
                p.setBrush(QBrush(QColor(col)))
                p.drawPolygon(poly)
        finally:
            p.end()


class GgsColorRampDialog(GgsDialog):

    def __init__(self, stops=None, name="", parent=None, kind=None, code=""):
        super().__init__(parent)
        self.setObjectName("GgsColorRampDialog")
        self.setWindowTitle(_i18n.tr("配色方案编辑器"))
        self.resize(460, 420)
        self._stops = [(max(0.0, min(1.0, float(p))), str(c))
                       for p, c in (stops or [])]
        if len(self._stops) < 2:
            self._stops = [(0.0, "#000000"), (1.0, "#FFFFFF")]
        self._stops.sort(key=lambda t: t[0])
        self._guard = False
        self._saved_code = ""
        self._orig_code = str(code or "")

        out = QVBoxLayout(self)
        out.setContentsMargins(12, 10, 12, 10)
        out.setSpacing(9)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(QLabel(_i18n.tr("名称")))
        self.ed_name = GgsRampNameEdit(str(name or ""))
        self.ed_name.setPlaceholderText("")
        top.addWidget(self.ed_name, 1)
        self.btn_add = self._tool(_i18n.tr("添加色标"), "add", self._add_stop)
        self.btn_del = self._tool(_i18n.tr("删除色标"), "delete", self._del_stop)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_del)
        out.addLayout(top)
        out.addWidget(_HLine(self))

        self.bar = _GradientStopBar(self)
        self.bar.changed.connect(self._on_bar_changed)
        self.bar.selectedChanged.connect(self._on_bar_selected)
        self.bar.pickRequested.connect(self._pick_stop_color)
        out.addWidget(self.bar)

        lbl_set = QLabel(_i18n.tr("设置"))
        try:
            f = lbl_set.font()
            f.setBold(True)
            lbl_set.setFont(f)
        except Exception:
            _log.exception("silent exception in __init__")
        out.addWidget(lbl_set)
        out.addWidget(_HLine(self))

        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        grid.addWidget(QLabel(_i18n.tr("颜色")), 0, 0)
        self.fld_color = GgsColorField(QColor(self._stops[0][1]), self,
                                       shape="rect", width=92, height=24)
        self.fld_color.setToolTip(
            _i18n.tr("改的是**当前选中**的那个色标（点色带上的手柄切换）"))
        self.fld_color.colorChanged.connect(self._on_color_changed)
        grid.addWidget(self.fld_color, 1, 0)
        grid.addWidget(QLabel(_i18n.tr("位置")), 0, 1)
        self.sp_pos = GgsRampPosSpin(self)
        self.sp_pos.setRange(0.0, 100.0)
        self.sp_pos.setDecimals(1)
        self.sp_pos.setSingleStep(1.0)
        self.sp_pos.setSuffix(" %")
        self.sp_pos.setKeyboardTracking(False)
        self.sp_pos.valueChanged.connect(self._on_pos_changed)
        grid.addWidget(self.sp_pos, 1, 1)
        lbl_flip = QLabel(_i18n.tr("翻转"))
        lbl_flip.setAlignment(Qt.AlignmentFlag.AlignRight
                              | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(lbl_flip, 0, 2)
        self.btn_flip = self._tool(_i18n.tr("把色带高低端对调"),
                                   "invert_sel", self._flip)
        grid.addWidget(self.btn_flip, 1, 2, Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 1)
        out.addLayout(grid)

        self.chk_even = QCheckBox(_i18n.tr("平均分配颜色停靠点"), self)
        self.chk_even.setToolTip(
            _i18n.tr("把各色标的位置均匀铺开（0%、…、100%）"))
        self.chk_even.clicked.connect(lambda _c=False: self._even_out())
        out.addWidget(self.chk_even, 0, Qt.AlignmentFlag.AlignLeft)


        out.addStretch(1)

        brow = QHBoxLayout()
        brow.setSpacing(6)
        brow.addWidget(QLabel(_i18n.tr("配色方案类型")))
        self.cb_type = QComboBox(self)
        self.cb_type.addItem(_i18n.tr("连续配色方案"), "continuous")
        self.cb_type.addItem(_i18n.tr("离散配色方案"), "discrete")
        self.cb_type.setToolTip(_i18n.tr(
            "连续：色标之间平滑过渡；离散：每个色标管一段（段内纯色块）"))
        self.cb_type.currentIndexChanged.connect(self._on_type_changed)
        brow.addWidget(self.cb_type)
        brow.addStretch(1)
        out.addLayout(brow)
        out.addWidget(_HLine(self))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel,
                              self)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        foot = QHBoxLayout()
        foot.setSpacing(6)
        self.btn_style = GgsRampSaveStyle(_i18n.tr("保存到样式…"), self)
        self.btn_style.setToolTip(
            _i18n.tr("先存起来（存进色带列表，不关这个窗口）"))
        self.btn_style.clicked.connect(self._save_to_style)
        foot.addWidget(self.btn_style)
        foot.addStretch(1)
        foot.addWidget(bb)
        out.addLayout(foot)

        self._kind = ("discrete" if str(kind or "") == "discrete"
                      else "continuous")
        try:
            self.cb_type.blockSignals(True)
            self.cb_type.setCurrentIndex(1 if self._kind == "discrete" else 0)
        finally:
            try:
                self.cb_type.blockSignals(False)
            except Exception:
                _log.exception("silent exception in __init__")
        self.bar.setDiscrete(self._kind == "discrete")

        self._sync_all(selected=0)

    def _tool(self, tip, icon_name, slot):
        b = QToolButton(self)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setAutoRaise(True)
        try:
            _icons.bind(b, icon_name, 16)
        except Exception:
            _log.exception("silent exception in _tool")
            b.setText(tip)
        b.clicked.connect(lambda _c=False: slot())
        return b

    def ramp_name(self):
        return str(self.ed_name.text() or "").strip()

    def ramp_kind(self):
        try:
            return str(self.cb_type.currentData() or "continuous")
        except Exception:
            _log.exception("silent exception in ramp_kind")
            return "continuous"

    def _on_type_changed(self, _i=0):
        self.bar.setDiscrete(self.ramp_kind() == "discrete")
        self.bar.update()

    def stops(self):
        return list(self._stops)

    def _sync_all(self, selected=None):
        sel = self.bar.selected() if selected is None else int(selected)
        sel = min(max(0, sel), len(self._stops) - 1)
        self.bar.setStops(self._stops, selected=sel)
        self._stops = self.bar.stops()
        self._push_controls()
        self.btn_del.setEnabled(len(self._stops) > 2)

    def _push_controls(self):
        i = self.bar.selected()
        if not (0 <= i < len(self._stops)):
            return
        pos, col = self._stops[i]
        self._guard = True
        try:
            try:
                self.fld_color.setColor(QColor(col))
            except Exception:
                _log.exception("silent exception in _push_controls")
            try:
                self.sp_pos.setValue(float(pos) * 100.0)
            except Exception:
                _log.exception("silent exception in _push_controls")
        finally:
            self._guard = False

    def _on_bar_changed(self):
        self._stops = self.bar.stops()
        self._push_controls()
        self.btn_del.setEnabled(len(self._stops) > 2)

    def _on_bar_selected(self, _i):
        self._push_controls()

    def _on_color_changed(self, color):
        if self._guard:
            return
        i = self.bar.selected()
        if not (0 <= i < len(self._stops)):
            return
        pos, _col = self._stops[i]
        self._stops[i] = (pos, QColor(color).name())
        self.bar.setStops(self._stops)

    def _on_pos_changed(self, value):
        if self._guard:
            return
        i = self.bar.selected()
        if not (0 <= i < len(self._stops)):
            return
        _pos, col = self._stops[i]
        self._stops[i] = (max(0.0, min(1.0, float(value) / 100.0)), col)
        cur = self._stops[i]
        self._stops.sort(key=lambda t: t[0])
        self.bar.setStops(self._stops, selected=self._stops.index(cur))

    def _pick_stop_color(self, i):
        if not (0 <= i < len(self._stops)):
            return
        try:
            self.fld_color.choose()
        except Exception:
            _log.exception("silent exception in _pick_stop_color")

    def _add_stop(self):
        n = len(self._stops)
        if n < 2:
            return
        i = self.bar.selected()
        if not (0 <= i < n):
            i = 0
        if i - 1 >= 0:
            other = float(self._stops[i - 1][0])
        elif i + 1 < n:
            other = float(self._stops[i + 1][0])
        else:
            return
        pos = (float(self._stops[i][0]) + other) / 2.0
        col = self.bar._color_at(self.bar._x_of(pos))
        self._stops.append((pos, col))
        self._stops.sort(key=lambda t: t[0])
        hit = [k for k, (p, _c) in enumerate(self._stops)
               if abs(p - pos) < 1e-9]
        self._sync_all(selected=(hit[0] if hit else self.bar.selected()))

    def _del_stop(self):
        if len(self._stops) <= 2:
            return
        i = self.bar.selected()
        if not (0 <= i < len(self._stops)):
            return
        self._stops.pop(i)
        self._sync_all(selected=min(i, len(self._stops) - 1))

    def _flip(self):
        sel = self.bar.selected()
        cur = self._stops[sel] if 0 <= sel < len(self._stops) else None
        self._stops = [(1.0 - p, c) for p, c in reversed(self._stops)]
        i = self._stops.index(cur) if cur in self._stops else 0
        self._sync_all(selected=i)

    def _even_out(self):
        n = len(self._stops)
        if n < 2:
            return
        sel = self.bar.selected()
        cur = self._stops[sel] if 0 <= sel < len(self._stops) else None
        cols = [c for _p, c in self._stops]
        self._stops = [(i / float(n - 1), cols[i]) for i in range(n)]
        i = self._stops.index(cur) if cur in self._stops else 0
        self._sync_all(selected=i)

    def _say_not_saved(self, text):
        try:
            self.btn_style.setText(str(text))
        except Exception:
            _log.exception("silent exception in _say_not_saved")

    def _used_names(self):
        try:
            from ggis.core.style import user_ramps
            return {str(n) for _c, n, _s in user_ramps.entries()}
        except Exception:
            _log.exception("silent exception in _used_names")
            return set()

    def _unique_name(self, name):
        used = self._used_names()
        if name not in used:
            return name
        k = 2
        while ("%s %d" % (name, k)) in used:
            k += 1
        return "%s %d" % (name, k)

    def _resolve_name(self):
        name = self.ramp_name() or _i18n.tr("未命名配色方案")
        try:
            from ggis.core.style import user_ramps
            code = user_ramps._code_for(name)
            exists = any(str(c) == code for c, _n, _s in user_ramps.entries())
        except Exception:
            _log.exception("silent exception in _resolve_name")
            return name
        if (not exists) or code == self._orig_code:
            return name
        ret = GgsMsgBox.question(
            self, _i18n.tr("配色方案已存在"),
            _i18n.tr(""
                     ""
                     ).format(name),
            buttons=(QMessageBox.StandardButton.Yes
                     | QMessageBox.StandardButton.No
                     | QMessageBox.StandardButton.Cancel),
            default=QMessageBox.StandardButton.Cancel)
        if ret == QMessageBox.StandardButton.Cancel:
            self._say_not_saved(_i18n.tr("未保存：名字重复"))
            try:
                self.ed_name.setFocus()
                self.ed_name.selectAll()
            except Exception:
                _log.exception("silent exception in _resolve_name")
            return ""
        if ret == QMessageBox.StandardButton.No:
            new = self._unique_name(name)
            try:
                self.ed_name.setText(new)
            except Exception:
                _log.exception("silent exception in _resolve_name")
            return new
        return name

    def accept(self):
        if not self._resolve_name():
            return
        super().accept()

    def _save_to_style(self):
        try:
            from ggis.core.style import user_ramps
        except Exception:
            _log.exception("silent exception in _save_to_style")
            return
        name = self._resolve_name()
        if not name:
            return
        try:
            code = user_ramps.save(name, self._stops,
                                   kind=self.ramp_kind())
        except Exception:
            _log.exception("silent exception in _save_to_style")
            code = ""
        if code:
            self._saved_code = code
            self._orig_code = code
            try:
                self.btn_style.setText(_i18n.tr("已保存到色带列表"))
            except Exception:
                _log.exception("silent exception in _save_to_style")


def edit_ramp(parent=None, current_code=""):
    from ggis.core.style import raster_display as rd
    from ggis.core.style import user_ramps

    code = str(current_code or "")
    stops, name, kind = [], "", "continuous"
    if user_ramps.is_user(code):
        stops = user_ramps.stops_of(code)
        name = user_ramps.label_of(code)
        kind = user_ramps.kind_of(code)
    if len(stops) < 2:
        pts = rd.ramp_control_points(code) or rd.ramp_control_points("viridis")
        if pts:
            stops = [(p, "#%02X%02X%02X" % tuple(c)) for p, c in pts]
        name = rd.RAMP_LABELS.get(code, "") or str(name or "")
    if not name:
        name = _i18n.tr("我的配色方案")
    dlg = GgsColorRampDialog(stops, name, parent, kind=kind, code=code)
    if dlg.exec() != int(GgsDialog.DialogCode.Accepted):
        return ""
    return user_ramps.save(dlg.ramp_name() or _i18n.tr("未命名配色方案"),
                           dlg.stops(), kind=dlg.ramp_kind())


class GgsRampNameEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRampNameEdit")
class GgsRampPosSpin(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRampPosSpin")
class GgsRampSaveStyle(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRampSaveStyle")
