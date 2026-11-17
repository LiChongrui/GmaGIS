# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMenu,
                               QProgressBar, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget, QFrame)

from ggis.common.styling import themes as _sem_themes
from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.widgets.displays import GgsDimLabel
from ggis.ui.framework.docks import GgsDockBody
from ggis.ui.panels.layertree import GgsDockToolbar
from ggis.ui.panels.placeholders import GgsLogFilter
from ggis.common.widgets.displays import GgsSpinner
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.core.app import i18n
from ...exec.progress_hub import hub
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

MAX_ITEMS = 50

_DONE, _FAIL, _CANCELLED, _WARN = "done", "fail", "cancelled", "warn"

_TASK_FILTERS = (
    ("全部任务", ""),
    ("运行中", "running"),
    ("已完成", _DONE),
    ("有警告", _WARN),
    ("已取消", _CANCELLED),
    ("失败", _FAIL),
)

_BAR_H = 12

_ROW1_H = 20

_OK_COLOR = _sem_themes.OK_COLOR
_ERR_COLOR = _sem_themes.ERR_COLOR
_WARN_COLOR = _sem_themes.WARN_COLOR


def _is_dark():
    try:
        from ggis.common.styling import icons as _icons
        return bool(_icons.is_dark())
    except Exception:
        _log.exception("silent exception in _is_dark")
        return False


def _theme_dim():
    try:
        from ggis.common.styling import themes as _themes
        return str(_themes.theme_colors(
            "dark" if _is_dark() else "light").get("text_dim", "#8a93a0"))
    except Exception:
        _log.exception("silent exception in _theme_dim")
        return "#8a93a0"


class _StateBadge(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = _DONE
        self.setFixedSize(14, 14)

    def set_state(self, state):
        self._state = state
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        if self._state == _DONE:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(_OK_COLOR))
            p.drawEllipse(1, 1, 12, 12)
            p.setPen(_white_pen(1.8))
            p.drawPolyline(QPolygonF([QPointF(4.2, 7.4), QPointF(6.2, 9.6),
                                      QPointF(10.0, 4.8)]))
        elif self._state == _FAIL:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(_ERR_COLOR))
            p.drawEllipse(1, 1, 12, 12)
            p.setPen(_white_pen())
            p.setFont(_badge_font())
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "!")
        elif self._state == _WARN:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(_WARN_COLOR))
            p.drawEllipse(1, 1, 12, 12)
            p.setPen(_white_pen())
            p.setFont(_badge_font())
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "!")
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(_theme_dim()))
            p.drawEllipse(1, 1, 12, 12)
            p.setBrush(QColor("#ffffff"))
            p.drawRect(4, 4, 6, 6)


def _white_pen(width=1.6):
    pen = QPen(QColor("#ffffff"))
    pen.setWidthF(float(width))
    return pen


def _badge_font():
    f = QFont()
    f.setPixelSize(9)
    f.setBold(True)
    return f


def _as_analysis_result(obj):
    try:
        from ...core.analysis import AnalysisResult
        if isinstance(obj, AnalysisResult):
            return obj
    except Exception:
        _log.exception("silent exception in _as_analysis_result")
    return None


def _format_analysis_result(ar):
    try:
        n = ar.count()
        gt = getattr(ar, "geometry_type", "") or ""
        ms = float(getattr(ar, "ms", 0.0) or 0.0)
        warns = list(getattr(ar, "warnings", None) or [])
        label = ""
        try:
            sp = ar.spec()
            if isinstance(sp, dict):
                label = sp.get("label", "") or ""
        except Exception:
            _log.exception("silent exception in _format_analysis_result")
            label = ""
        if not label:
            label = (getattr(ar, "name", "") or getattr(ar, "op", "")
                     or _tr("分析结果"))
        parts = [str(label)]
        parts.append(_tr("{0} 个要素").format(n))
        if gt:
            parts.append(gt)
        if ms > 0:
            parts.append(_tr("用时 {0} ms").format(round(ms, 1)))
        if warns:
            parts.append(_tr("有 {0} 条警告").format(len(warns)))
        return " · ".join(parts)
    except Exception:
        _log.exception("silent exception in _format_analysis_result")
        try:
            return ar.summary()
        except Exception:
            _log.exception("silent exception in _format_analysis_result")
            return str(ar)


def _format_result(res):
    if res is None:
        return ""
    obj = res
    if isinstance(obj, (tuple, list)):
        obj = obj[0] if obj else None
    if obj is None:
        return ""
    ar = _as_analysis_result(obj)
    if ar is not None:
        return _format_analysis_result(ar)
    try:
        name = obj.name()
        if not name:
            raise ValueError("空名")
        try:
            n = int(obj.feature_count())
        except Exception:
            _log.exception("silent exception in _format_result")
            n = -1
        if n >= 0:
            return _tr("已生成图层「{0}」（{1} 个要素）").format(name, n)
        return _tr("已生成图层「{0}」").format(name)
    except Exception:
        _log.exception("silent exception in _format_result")
    s = str(obj)
    return s if s else ""


class _TaskItem(QFrame):

    def __init__(self, panel, token, name):
        super().__init__()
        self.setObjectName("GgsTaskItem")
        self._panel = panel
        self._token = token
        self._window = None
        self._running = True
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Maximum)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 7, 8, 7)
        lay.setSpacing(4)

        row1 = QWidget()
        row1.setFixedHeight(_ROW1_H)
        t1 = QHBoxLayout(row1)
        t1.setContentsMargins(0, 0, 0, 0)
        t1.setSpacing(6)
        self.spinner = GgsSpinner(self, diameter=14)
        self.spinner.start()
        t1.addWidget(self.spinner, 0, Qt.AlignmentFlag.AlignVCenter)
        self.badge = _StateBadge(self)
        self.badge.setVisible(False)
        t1.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.lbl_name = QLabel(str(name or _tr("处理中")))
        self.lbl_name.setObjectName("GgsTaskName")
        self.lbl_name.setWordWrap(False)
        self.lbl_name.setSizePolicy(QSizePolicy.Policy.Ignored,
                                    QSizePolicy.Policy.Preferred)
        self.lbl_name.setMinimumWidth(1)
        t1.addWidget(self.lbl_name, 1)
        self.lbl_pct = QLabel("0%")
        self.lbl_pct.setObjectName("GgsTaskPct")
        t1.addWidget(self.lbl_pct, 0, Qt.AlignmentFlag.AlignVCenter)
        self.btn_stop = GgsSmallButtonStyle1(
            "stop", _tr("终止任务"), self._on_stop, size=15)
        t1.addWidget(self.btn_stop, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(row1)

        self.lbl_stage = GgsDimLabel("")
        self.lbl_stage.setObjectName("GgsTaskStage")
        self.lbl_stage.setWordWrap(True)
        self.lbl_stage.setSizePolicy(QSizePolicy.Policy.Ignored,
                                     QSizePolicy.Policy.Preferred)
        self.lbl_stage.setMinimumHeight(1)
        self.lbl_stage.setVisible(False)
        lay.addWidget(self.lbl_stage)

        self.bar = QProgressBar(self)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(_BAR_H)
        lay.addWidget(self.bar)
        self.lbl_name.setToolTip(str(name or ""))
        self.lbl_result = QLabel("")
        self.lbl_result.setObjectName("GgsTaskResult")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Preferred)
        self.lbl_result.setMinimumHeight(_BAR_H)
        self.lbl_result.setVisible(False)
        lay.addWidget(self.lbl_result)
        self.setToolTip(_tr("双击显示工具窗口"))

    @property
    def state(self):
        return "" if self._running else self.badge._state

    def update_progress(self, frac, text):
        try:
            f = max(0.0, min(1.0, float(frac or 0.0)))
        except Exception:
            _log.exception("silent exception in update_progress")
            f = 0.0
        self.bar.setValue(int(round(f * 100)))
        self.lbl_pct.setText("%d%%" % int(round(f * 100)))
        if text:
            self.lbl_stage.setText(str(text))
            self.lbl_stage.setVisible(True)

    def finish(self, ev):
        self._running = False
        try:
            self.spinner.stop()
        except Exception:
            _log.exception("silent exception in finish")
        self.spinner.setVisible(False)
        self.btn_stop.setVisible(False)
        self.bar.setVisible(False)
        self.lbl_pct.setVisible(False)
        self.setToolTip("")
        try:
            ms = float(ev.get("ms") or 0.0)
        except Exception:
            _log.exception("silent exception in finish")
            ms = 0.0
        result_text = ""
        if ev.get("cancelled"):
            self.badge.set_state(_CANCELLED)
            self.lbl_stage.setText(_tr("已取消"))
            result_text = _tr("任务已取消，未产生输出")
        elif ev.get("error"):
            self.badge.set_state(_FAIL)
            self.lbl_stage.setText(_tr("失败"))
            result_text = _tr("失败：{0}").format(str(ev.get("error") or "")[:160])
        else:
            res = ev.get("result")
            warn = (res.get("warning") if isinstance(res, dict) else None)
            if warn:
                self.badge.set_state(_WARN)
                self.lbl_stage.setText(_tr("完成（有警告）"))
                result_text = _tr("警告：{0}").format(str(warn)[:160])
            else:
                self.badge.set_state(_DONE)
                self.lbl_stage.setText(
                    _tr("已完成 · 用时 {0} 秒").format(round(ms / 1000.0, 1)))
                if res is not None:
                    formatted = _format_result(res)
                    if formatted:
                        result_text = _tr("结果：{0}").format(formatted)
        self.lbl_result.setText(result_text)
        self.lbl_result.setToolTip(result_text)
        self.lbl_result.setVisible(True)
        self.badge.setVisible(True)
        self.lbl_stage.setVisible(True)

    def reset(self):
        self._running = True
        self.badge.setVisible(False)
        self.lbl_result.setText("")
        self.lbl_result.setToolTip("")
        self.lbl_result.setVisible(False)
        self.lbl_stage.setText("")
        self.lbl_stage.setVisible(False)
        self.bar.setValue(0)
        self.bar.setVisible(True)
        self.lbl_pct.setText("0%")
        self.lbl_pct.setVisible(True)
        self.btn_stop.setVisible(True)
        self.spinner.setVisible(True)
        try:
            self.spinner.start()
        except Exception:
            _log.exception("silent exception in reset")
        self.setToolTip(_tr("双击显示工具窗口"))

    def bind_window(self, window):
        self._window = window

    def open_window(self):
        w = self._window
        if w is None:
            return False
        try:
            w.show()
            w.raise_()
            w.activateWindow()
            return True
        except Exception:
            _log.exception("silent exception in open_window")
            return False

    def _on_stop(self):
        self._panel.cancel_token(self._token)

    def mouseDoubleClickEvent(self, ev):
        self.open_window()
        super().mouseDoubleClickEvent(ev)

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        a_open = menu.addAction(_tr("显示窗口"))
        a_open.setEnabled(self._window is not None)
        a_stop = menu.addAction(_tr("终止任务"))
        a_stop.setEnabled(self._running)
        menu.addSeparator()
        a_del = menu.addAction(_tr("清除此条目"))
        a_del.setEnabled(not self._running)
        picked = menu.exec(ev.globalPos())
        if picked is a_open:
            self.open_window()
        elif picked is a_stop:
            self._panel.cancel_token(self._token)
        elif picked is a_del:
            self._panel.remove_item(self._token, dispose_window=True)
        super().contextMenuEvent(ev)


class GgsTaskDockPanel(GgsDockWidget):

    def __init__(self, parent=None, title=None):
        super().__init__(title or _tr("任务"), parent)
        self.setObjectName("GgsTaskDock")
        self._items = {}
        self._order = []
        self._filter = ""

        body = GgsDockBody(self)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = GgsDockToolbar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        bl.setSpacing(2)

        def _btn(icon_name, tip, cb):
            b = GgsSmallButtonStyle1(icon_name, _tr(tip), cb)
            bl.addWidget(b)
            return b

        self.btn_sample = _btn("task", "打开任务演示样例窗口", self._open_sample)
        self.btn_clear = _btn("clear", "清除已完成", self.clear_finished)
        bl.addSpacing(6)
        self.cmb_filter = GgsLogFilter()
        self.cmb_filter.setToolTip(_tr("只显示指定状态的任务"))
        for label, key in _TASK_FILTERS:
            self.cmb_filter.addItem(_tr(label), key)
        self.cmb_filter.currentIndexChanged.connect(
            lambda _i: self._set_filter(self.cmb_filter.currentData()))
        try:
            self.cmb_filter.setFixedHeight(22)
        except Exception:
            _log.exception("silent exception in __init__")
        bl.addWidget(self.cmb_filter)
        bl.addStretch(1)
        self.lbl_stat = GgsDimLabel("")
        bl.addWidget(self.lbl_stat)
        bar.setSizePolicy(QSizePolicy.Policy.Preferred,
                          QSizePolicy.Policy.Fixed)
        lay.addWidget(bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        self._list_lay = QVBoxLayout(container)
        self._list_lay.setContentsMargins(6, 6, 6, 6)
        self._list_lay.setSpacing(6)
        self._list_lay.addStretch(1)
        self._scroll.setWidget(container)
        lay.addWidget(self._scroll, 1)

        self.lbl_empty = QLabel(_tr("暂无任务"))
        self.lbl_empty.setObjectName("GgsTaskEmpty")
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setContentsMargins(6, 12, 6, 12)
        lay.addWidget(self.lbl_empty)

        self.setWidget(body)
        self._refresh()
        try:
            hub().subscribe(_TaskDockPresenter(self))
        except Exception:
            _log.exception("silent exception in __init__")
        _register(self)

    def add_task(self, token, name):
        it = self._items.get(token)
        if it is not None:
            it.reset()
            try:
                it.lbl_name.setText(str(name or it.lbl_name.text()))
                it.lbl_name.setToolTip(str(name or ""))
            except Exception:
                _log.exception("silent exception in add_task")
            self._refresh()
            return it
        it = _TaskItem(self, token, name)
        self._items[token] = it
        self._order.append(token)
        self._list_lay.insertWidget(self._list_lay.count() - 1, it)
        self._prune()
        self._refresh()
        return it

    def update_task(self, token, frac, text):
        it = self._items.get(token)
        if it is not None:
            it.update_progress(frac, text)

    def finish_task(self, token, ev):
        it = self._items.get(token)
        if it is not None:
            it.finish(ev or {})
            self._refresh()

    def bind_window(self, token, window):
        it = self._items.get(token)
        if it is not None:
            it.bind_window(window)

    def cancel_token(self, token):
        try:
            hub().request_cancel(token)
        except Exception:
            _log.exception("silent exception in cancel_token")

    def remove_item(self, token, dispose_window=False):
        it = self._items.pop(token, None)
        if it is None:
            return
        try:
            self._order.remove(token)
        except ValueError:
            exc_note("remove_item @ ggis/ui/panels/task_dock.py:622")
            pass
        if (dispose_window and it._window is not None
                and it._window.isHidden()
                and not getattr(it._window, "is_persistent_window", False)):
            try:
                it._window.deleteLater()
            except Exception:
                _log.exception("silent exception in remove_item")
        it.setParent(None)
        it.deleteLater()
        self._refresh()

    def _open_sample(self):
        try:
            from . import task_sample
            task_sample.open_sample(self)
        except Exception:
            _log.exception("silent exception in _open_sample")

    def clear_finished(self):
        for token in [t for t in list(self._order)
                      if (it := self._items.get(t)) is not None
                      and not it._running]:
            self.remove_item(token, dispose_window=True)

    def _prune(self):
        while len(self._order) > MAX_ITEMS:
            victim = None
            for t in self._order:
                it = self._items.get(t)
                if it is not None and not it._running:
                    victim = t
                    break
            if victim is None:
                break
            self.remove_item(victim, dispose_window=True)

    def _matches_filter(self, it):
        key = self._filter
        if key == "running":
            return it._running
        if key == "":
            return True
        return it.state == key

    def _apply_filter(self):
        for it in self._items.values():
            it.setVisible(self._matches_filter(it))

    def _set_filter(self, key):
        self._filter = ("" if key is None else str(key))
        self._refresh()

    def _refresh(self):
        self._apply_filter()
        n_run = sum(1 for it in self._items.values() if it._running)
        n_end = len(self._items) - n_run
        n_fail = sum(1 for it in self._items.values()
                     if it.state == _FAIL)
        parts = []
        if n_run:
            parts.append(_tr("运行中 {0}").format(n_run))
        if n_end:
            parts.append(_tr("已结束 {0}").format(n_end))
        if n_fail:
            parts.append(_tr("失败 {0}").format(n_fail))
        self.lbl_stat.setText(" · ".join(parts) if parts else "")
        n_visible = sum(1 for it in self._items.values()
                        if self._matches_filter(it))
        has_any = len(self._items) > 0
        self._scroll.setVisible(n_visible > 0)
        self.lbl_empty.setVisible(n_visible == 0)
        if not has_any:
            self.lbl_empty.setText(_tr("暂无任务"))
        elif n_visible == 0:
            self.lbl_empty.setText(_tr("无匹配任务"))
        else:
            self.lbl_empty.setText("")


class _TaskDockPresenter:

    def __init__(self, panel):
        self._panel = panel

    def show(self, token, name):
        self._panel.add_task(token, name)

    def update(self, token, frac, text):
        self._panel.update_task(token, frac, text)

    def done(self, token, ev=None):
        self._panel.finish_task(token, ev or {})

    def cancel_requested(self, token):
        return False


_PANEL = None


def bind_window(token, window):
    if _PANEL is not None:
        _PANEL.bind_window(token, window)


def _register(panel):
    global _PANEL
    _PANEL = panel
