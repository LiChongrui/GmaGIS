# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import time

from PySide6.QtWidgets import QLabel, QVBoxLayout

from ggis.common.widgets.displays import GgsDimLabel
from ggis.common.widgets.inputs import GgsComboBox
from ..dialogs.tool_dialog import GgsToolDialog
from ggis.core.app import i18n
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_DLG = None


def open_sample(parent=None):
    global _DLG
    if _DLG is not None:
        try:
            _DLG.show()
            _DLG.raise_()
            _DLG.activateWindow()
            return _DLG
        except RuntimeError:
            exc_note("open_sample @ ggis/ui/panels/task_sample.py:52")
            _DLG = None
    try:
        _DLG = GgsTaskSampleDialog(parent)
    except Exception:
        _log.exception("silent exception in open_sample")
        _DLG = None
        return None
    try:
        _DLG.show()
        _DLG.raise_()
        _DLG.activateWindow()
    except Exception:
        _log.exception("silent exception in open_sample")
    return _DLG


class GgsTaskSampleDialog(GgsToolDialog):

    def __init__(self, parent=None):
        super().__init__(
            parent, title=_tr("任务面板演示样例"),
            buttons=(("运行", self._on_apply, "exec"),))
        self.setObjectName("GgsTaskSampleDialog")
        self.is_persistent_window = True
        self._run_no = 0

        box, form = self.add_section(_tr("运行模式"))
        self.cmb = GgsComboBox()
        self.cmb.addItem(_tr("正常完成（约 1 秒）"), "ok")
        self.cmb.addItem(_tr("完成但带警告"), "warn")
        self.cmb.addItem(
            _tr("较慢"),
            "long")
        self.cmb.addItem(_tr("必定失败"), "fail")
        form.addRow(QLabel(_tr("模式")), self.cmb)

        hint = GgsDimLabel(_tr(
            "点「运行」后观察任务面板：条目进度、终止按钮、"
            "双击条目回显本窗口、完成/失败/取消三态与结果行。"))
        hint.setWordWrap(True)
        lay = QVBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(hint)
        form.addRow(lay)

        self.fit_to_content(460)

    def collect_params(self):
        self._run_no += 1
        return {"mode": str(self.cmb.currentData() or "ok"),
                "n": self._run_no}

    def validate_params(self, params):
        return ""

    def do_run(self, params, progress, cancel):
        mode = str(params.get("mode") or "ok")
        steps = 100 if mode == "long" else 20
        for i in range(steps):
            if cancel():
                return None
            progress((i + 1) / float(steps),
                     _tr("演示步骤 {0}/{1}").format(i + 1, steps))
            time.sleep(0.05)
        if mode == "fail":
            raise RuntimeError(_tr("演示任务失败（故意注入的错误）"))
        if mode == "warn":
            return {"result": _tr("演示结果（置信度存疑）"),
                    "warning": _tr("演示：结果置信度较低，请人工复核")}
        return _tr("演示任务第 {0} 次运行完成").format(
            int(params.get("n") or 0))
