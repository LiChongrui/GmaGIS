# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QCheckBox, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QProgressBar, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget, QApplication)

from ggis.core.app import i18n
from ggis.common.base.dialog import GgsDialog, GgsMsgBox
from ...exec.progress_hub import hub
from ggis.common.styling import icons as _icons
from ggis.common.styling import themes
from ggis.common.widgets.displays import GgsDimLabel
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_ROLE_DEFS = {
    "apply":  (_tr("应用"), "exec"),
    "run":    (_tr("运行"), "exec"),
    "ok":     (_tr("确定"), "ok"),
    "cancel": (_tr("取消"), "cancel"),
    "close":  (_tr("关闭"), "close"),
}

_SEMANTICS = ("exec", "ok", "cancel", "close", "keep", "custom")


class GgsToolDialog(GgsDialog):

    def __init__(self, parent=None, title="", icon=None,
                 buttons=("apply", "cancel")):
        super().__init__(parent)
        self.setObjectName("GgsToolDialog")
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        if title:
            self.setWindowTitle(_tr(title))
        if icon is not None:
            self.setWindowIcon(icon)
        self._runner = None
        self._finisher = None
        self._task = None
        self._running = False
        self._buttons = []
        self._build_shell()
        self.set_buttons(*buttons)
        self.build_content()
        self.content_layout.addStretch(1)

    def fit_to_content(self, width, max_h=560):
        try:
            h = self._content.sizeHint().height() + 2
        except Exception:
            _log.exception("silent exception in fit_to_content")
            h = 200
        self._scroll.setMinimumHeight(max(120, min(h, max_h)))
        self.resize(int(width), self.sizeHint().height())

    def _build_shell(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        scroll = QScrollArea()
        self._scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        self._content = content
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        scroll.setWidget(content)
        lay.addWidget(scroll, 1)

        self.foot_box = QWidget()
        fv = QVBoxLayout(self.foot_box)
        fv.setContentsMargins(0, 0, 0, 0)
        fv.setSpacing(6)

        self.prog_box = QWidget()
        pv = QVBoxLayout(self.prog_box)
        pv.setContentsMargins(0, 0,0, 0)
        pv.setSpacing(4)
        self.lbl_stage = GgsDimLabel("")
        self.lbl_stage.setWordWrap(True)
        pv.addWidget(self.lbl_stage)
        self.bar = QProgressBar()
        self.bar.setObjectName("GgsProgressBar")
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        self.bar.setFixedHeight(18)
        pv.addWidget(self.bar)
        _ph = self.prog_box.sizeHint().height()
        self.bar.setVisible(False)
        self.prog_box.setFixedHeight(max(_ph, 40))
        fv.addWidget(self.prog_box)

        rowb = QHBoxLayout()
        rowb.setContentsMargins(0, 0, 0, 0)
        rowb.setSpacing(8)
        self.chk_add_to_map = QCheckBox(_tr("将结果加入到地图"))
        self.chk_add_to_map.setChecked(True)
        rowb.addWidget(self.chk_add_to_map)
        rowb.addStretch(1)
        self._btn_row = rowb
        self._buttons = []
        fv.addLayout(rowb)

        lay.addWidget(self.foot_box)

    def set_buttons(self, *specs):
        self._clear_buttons()
        for spec in specs:
            if isinstance(spec, str):
                self._add_role_button(spec)
            elif isinstance(spec, (tuple, list)) and len(spec) >= 1:
                text = spec[0]
                on_click = spec[1] if len(spec) > 1 else None
                semantics = spec[2] if len(spec) > 2 else "custom"
                self.add_button(text, on_click, semantics=semantics)

    def add_button(self, text, on_click=None, *, semantics="custom"):
        btn = QPushButton(_tr(str(text)))
        if on_click is not None:
            btn.clicked.connect(on_click)
        self._register_button(btn, semantics, _tr(str(text)))
        return btn

    def _add_role_button(self, name):
        defs = _ROLE_DEFS.get(name)
        if defs is None:
            return
        text, sem = defs
        btn = QPushButton(text)
        if sem == "exec":
            btn.clicked.connect(self._on_apply)
        elif sem == "ok":
            btn.clicked.connect(self._on_ok)
        elif sem == "cancel":
            btn.clicked.connect(self._on_cancel)
        elif sem == "close":
            btn.clicked.connect(self._on_close)
        self._register_button(btn, sem, text)

    def _register_button(self, btn, semantics, base_text):
        if semantics not in _SEMANTICS:
            semantics = "custom"
        if semantics == "cancel":
            btn.setEnabled(bool(self._running))
        else:
            btn.setEnabled(not self._running)
        self._btn_row.addWidget(btn)
        self._buttons.append((btn, semantics, base_text))

    def _clear_buttons(self):
        for btn, _sem, _txt in self._buttons:
            self._btn_row.removeWidget(btn)
            btn.deleteLater()
        self._buttons = []

    def _apply_run_state(self, running):
        for btn, sem, base_text in self._buttons:
            if sem in ("exec", "ok"):
                btn.setEnabled(True)
                btn.setText(_tr("终止") if running else base_text)
                btn.setObjectName("GgsToolActionButton")
                btn.setIcon(_icons.icon("stop" if running else "processing",
                                        size=16))
                btn.setIconSize(QSize(16, 16))
                btn.setStyleSheet("" if not running else
                                  "QPushButton#GgsToolActionButton { color: %s; }"
                                  % themes.ERR_COLOR)
            elif sem == "cancel":
                btn.setEnabled(running)
            elif sem in ("close", "keep"):
                btn.setEnabled(True)
            else:
                btn.setEnabled(not running)

    _FACE_RUN = "run"
    _FACE_DONE = "done"
    _FACE_CANCEL = "cancel"
    _FACE_FAIL = "fail"

    def _set_progress_face(self, state):
        c = themes.progress_face_color(state)
        try:
            self.bar.setStyleSheet(
                "" if c is None else
                "QProgressBar#GgsProgressBar::chunk { background: %s; }" % c)
        except Exception:
            _log.exception("silent exception in _set_progress_face")
        try:
            self.lbl_stage.setStyleSheet(
                "" if c is None else
                "QLabel#GgsDimLabel { color: %s; }" % c)
        except Exception:
            _log.exception("silent exception in _set_progress_face")

    def add_section(self, title):
        gb = QGroupBox(_tr(title))
        form = QFormLayout(gb)
        form.setContentsMargins(8, 8, 8, 8)
        self.content_layout.addWidget(gb)
        return gb, form

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)
        return widget

    def build_content(self):
        pass

    def collect_params(self):
        return {}

    def validate_params(self, params):
        return ""

    def do_run(self, params, progress, cancel):
        raise NotImplementedError(
            "GgsToolDialog 子类需实现 do_run() 或调用 set_runner()")

    def set_runner(self, fn):
        self._runner = fn

    def set_finisher(self, fn):
        self._finisher = fn

    def add_to_map(self):
        return bool(self.chk_add_to_map.isChecked())

    def on_finished(self, result, ok):
        return result

    def _on_apply(self):
        if self._running:
            self._on_cancel()
            return
        self._run()

    def _on_ok(self):
        self._on_apply()

    def _on_cancel(self):
        if self._task is not None:
            self._task.cancel()
        try:
            self.lbl_stage.setText(_tr("正在取消…"))
            self._set_progress_face(self._FACE_CANCEL)
            self._apply_run_state(True)
        except Exception:
            _log.exception("silent exception in _on_cancel")

    def _on_close(self):
        if self._running:
            self.hide()
        else:
            self.reject()

    def _run(self):
        if self._running:
            return
        params = self.collect_params()
        err = self.validate_params(params)
        if err:
            GgsMsgBox.warning(self, _tr("缺少必填参数"), _tr(str(err)))
            return
        self._begin_busy()
        runner = self._runner

        def _job(progress=None, cancel=None):
            if runner is not None:
                return runner(params, progress, cancel)
            return self.do_run(params, progress, cancel)

        from ...exec import task as _et
        try:
            t = _et.submit(_job, kind=getattr(self, "task_kind", "cpu"),
                           name=self.windowTitle() or _tr("工具"))
        except Exception as e:
            self._set_progress_face(self._FACE_FAIL)
            self._end_busy(False)
            GgsMsgBox.critical(self, _tr("无法启动任务"), _tr(str(e)))
            return
        self._task = t
        t.on_progress(self._on_progress)
        t.on_done(self._on_done)
        t.on_fail(self._on_fail)
        hub().attach(t)
        try:
            from ..panels import task_dock as _td
            _td.bind_window(t.token, self)
        except Exception:
            _log.exception("silent exception in _run")

    def _begin_busy(self):
        self._running = True
        try:
            self.bar.setValue(0)
            self.lbl_stage.setText(_tr("准备中…"))
            self.bar.setVisible(True)
            self.prog_box.setVisible(True)
            self._set_progress_face(self._FACE_RUN)
        except Exception:
            _log.exception("silent exception in _begin_busy")
        self._set_params_enabled(False)
        self._apply_run_state(True)
        try:
            QApplication.processEvents()
        except Exception:
            _log.exception("silent exception in _begin_busy")

    def _end_busy(self, ok=True):
        self._running = False
        self._task = None
        self._set_params_enabled(True)
        self._apply_run_state(False)

    def _set_params_enabled(self, enabled):
        for i in range(self.content_layout.count()):
            it = self.content_layout.itemAt(i)
            w = it.widget()
            if w is not None:
                w.setEnabled(enabled)
        try:
            self.chk_add_to_map.setEnabled(enabled)
        except Exception:
            _log.exception("silent exception in _set_params_enabled")

    def _on_progress(self, ev):
        try:
            f = float(ev.get("frac", 0.0))
            self.bar.setValue(int(max(0.0, min(1.0, f)) * 100))
            text = ev.get("text")
            if text:
                self.lbl_stage.setText(_tr(str(text)))
        except Exception:
            _log.exception("silent exception in _on_progress")

    def _on_done(self, ev):
        cancelled = bool(ev.get("cancelled", False))
        ok = not cancelled
        res = ev.get("result")
        self._set_progress_face(self._FACE_CANCEL if cancelled
                                else self._FACE_DONE)
        self._end_busy(ok)
        try:
            self.on_finished(res, ok)
        except Exception:
            _log.exception("silent exception in _on_done")
        self._fire_finisher(ev)

    def _on_fail(self, ev):
        msg = ev.get("error") if isinstance(ev, dict) else ev
        self._set_progress_face(self._FACE_FAIL)
        self._end_busy(False)
        parent = None if self.isHidden() else self
        GgsMsgBox.critical(parent, _tr("执行失败"), _tr(str(msg)))
        self._fire_finisher(ev if isinstance(ev, dict)
                            else {"error": str(msg)})

    def _fire_finisher(self, ev):
        if self._finisher is None:
            return
        try:
            self._finisher(ev)
        except Exception:
            try:
                import logging as _logging
                _logging.getLogger(__name__).exception(
                    "工具收尾函数执行失败：%s" % (self.windowTitle() or ""))
            except Exception:
                _log.exception("silent exception in _fire_finisher")

    def closeEvent(self, ev):
        if self._running:
            self.hide()
            ev.ignore()
        else:
            ev.accept()
