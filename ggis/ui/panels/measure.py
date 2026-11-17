# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout

from ggis.core.app import i18n
from ggis.core.app import settings as _settings
from ggis.common.styling import themes
from ggis.common.widgets.buttons import GgsSmallButtonStyle1, GgsSmallCheckButtonStyle1
from ggis.common.widgets.separators import GgsSepV
from ggis.common.widgets.separators import GgsSepH
import logging
from PySide6.QtWidgets import QLabel, QToolButton
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_USAGE = {
    "length": "测量距离",
    "area": "测量面积",
    "angle": "测量角度",
}


class GgsMeasurePanel(QFrame):

    clearRequested = Signal()
    closeRequested = Signal()
    liveChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsMeasurePanel")
        self.setWindowFlags(Qt.WindowType.Tool
                            | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,
                          True)
        self.setFixedWidth(268)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        self.lbl_title = GgsMeasureTitle(_tr("测量距离"))
        head.addWidget(self.lbl_title)
        head.addStretch(1)
        self.btn_close = GgsMeasureClose()
        self.btn_close.setText("✕")
        self.btn_close.setToolTip(_tr("关闭并退出测量"))
        self.btn_close.clicked.connect(self.closeRequested)
        head.addWidget(self.btn_close)
        root.addLayout(head)

        self.lbl_result = GgsMeasureResult(_tr("等待测量…"))
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.lbl_result)

        self.lbl_detail = GgsMeasureDetail("")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.lbl_detail)

        row = QHBoxLayout()
        row.setSpacing(6)
        try:
            _live0 = bool(_settings.get("measure_show_overlay", False))
        except Exception:
            _log.exception("silent exception in __init__")
            _live0 = False
        self.chk_live = GgsSmallCheckButtonStyle1(
            "visible", _tr("在地图上实时显示结果"), self.liveChanged,
            checked=_live0)
        self.chk_live.setObjectName("GgsMeasureLive")
        self.chk_live.setToolTip(_tr("在地图上显示测量结果"))
        row.addWidget(self.chk_live)
        sep = GgsSepV()
        row.addWidget(sep)
        self.btn_clear = GgsSmallButtonStyle1("broom", _tr("清除"), self.clearRequested)
        row.addWidget(self.btn_clear)
        row.addStretch(1)
        hint = GgsMeasureHint(_tr("Esc 取消 · 双击结束"))
        row.addWidget(hint)
        root.addLayout(row)

    def setVisible(self, visible):
        if visible:
            try:
                self.adjustSize()
            except Exception:
                _log.exception("silent exception in setVisible")
        super().setVisible(visible)

    def set_kind(self, kind):
        title = _USAGE.get(str(kind or "length"), _USAGE["length"])
        self.lbl_title.setText(_tr(title))
        self.set_result("", "")

    def set_result(self, text, detail=""):
        self.lbl_result.setText(text or _tr("等待测量…"))
        self.lbl_detail.setText(detail or "")

    def is_live(self):
        return bool(self.chk_live.isChecked())

    def set_live(self, on):
        self.chk_live.blockSignals(True)
        self.chk_live.setChecked(bool(on))
        self.chk_live.blockSignals(False)

    def paintEvent(self, event):
        try:
            pal = themes.theme_colors(_settings.get("theme"))
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
            path.addRoundedRect(r, 8, 8)
            p.setClipPath(path)
            p.fillRect(r, QColor(pal["panel"]))
            p.setClipping(False)
            p.setPen(QColor(pal["border"]))
            p.drawPath(path)
            p.end()
        except Exception:
            _log.exception("silent exception in paintEvent")
            super().paintEvent(event)


class GgsMeasureClose(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMeasureClose")
class GgsMeasureDetail(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMeasureDetail")
class GgsMeasureHint(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMeasureHint")
class GgsMeasureResult(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMeasureResult")
class GgsMeasureTitle(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMeasureTitle")
