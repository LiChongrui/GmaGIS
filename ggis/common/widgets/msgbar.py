# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ggis.core.app import i18n
from ggis.core.app import settings as _settings
from ggis.common.styling import themes
from PySide6.QtWidgets import QLabel, QToolButton

_MAX_ITEMS = 4

_LEVEL_NAMES = {
    "Info": "info",
    "Success": "success",
    "Warning": "warn",
    "Critical": "crit",
}

_LEVEL_DOTS = {
    "info": "#41ADFF",
    "success": "#43A047",
    "warn": "#F5A623",
    "crit": "#E05252",
}


def _level_key(level):
    try:
        name = level.name if hasattr(level, "name") else str(level)
    except Exception:
        exc_note("_level_key @ ggis/common/widgets/msgbar.py:58")
        name = "Info"
    return _LEVEL_NAMES.get(str(name).split(".")[-1], "info")


class _MsgCard(QFrame):

    dismissed = Signal(object)

    def __init__(self, text, level_key, duration, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsMsgCard")
        pol = self.sizePolicy()
        pol.setHeightForWidth(True)
        self.setSizePolicy(pol)

        self.dot = QLabel()
        self.dot.setObjectName("GgsMsgDot")
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet(
            "background:{}; border-radius:4px;".format(
                _LEVEL_DOTS.get(level_key, _LEVEL_DOTS["info"])))

        self.label = GgsMsgText(str(text))
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)

        self.btn_close = GgsMsgClose()
        self.btn_close.setText("✕")
        self.btn_close.setAutoRaise(True)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setToolTip(i18n.tr("关闭提示"))
        self.btn_close.clicked.connect(self._dismiss)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 6, 6)
        lay.setSpacing(8)
        lay.addWidget(self.dot, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.btn_close)


        if duration and int(duration) > 0:
            QTimer.singleShot(int(duration) * 1000, self._dismiss)

    def _dismiss(self):
        self.dismissed.emit(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            pal = themes.theme_colors(_settings.get("theme"))
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
            path.addRoundedRect(r, 6, 6)
            p.setClipPath(path)
            p.fillRect(r, QColor(pal["panel"]))
            p.setClipping(False)
            p.setPen(QColor(pal["border"]))
            p.drawPath(path)
            p.end()
        except Exception:
            exc_note("paintEvent @ ggis/common/widgets/msgbar.py:145")
            pass


class GgsMessageBar(QFrame):

    widgetAdded = Signal(QWidget)
    widgetRemoved = Signal(QWidget)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsMsgBar")
        self.setSizePolicy(QSizePolicy.Policy.Minimum,
                           QSizePolicy.Policy.Fixed)
        self._cards = []
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4)
        self.hide()

    def items(self):
        return list(self._cards)

    def clearWidgets(self):
        for card in list(self._cards):
            self._remove_card(card)
        self.hide()

    def pushMessage(self, title, text, level=None, duration=4):
        try:
            while len(self._cards) >= _MAX_ITEMS:
                self._remove_card(self._cards[0])
            card = _MsgCard(text, _level_key(level), duration, self)
            card.dismissed.connect(self._remove_card)
            self._cards.append(card)
            self._lay.addWidget(card)
            self._sync_size()
            self.widgetAdded.emit(card)
        except Exception:
            exc_note("pushMessage @ ggis/common/widgets/msgbar.py:202")
            pass

    def _sync_size(self):
        try:
            lay = self._lay
            lay.activate()
            w = self.width() if self.width() > 0 else 480
            spacing = lay.spacing()
            y = 0
            total = 0
            for c in self._cards:
                ch = c.heightForWidth(w)
                if ch <= 0:
                    ch = c.sizeHint().height()
                c.setGeometry(0, y, w, ch)
                y += ch + spacing
                total += ch
            if self._cards:
                total += spacing * (len(self._cards) - 1)
            self.setFixedHeight(max(1, total))
            lay.activate()
        except Exception:
            exc_note("_sync_size @ ggis/common/widgets/msgbar.py:235")
            pass

    def _remove_card(self, card):
        try:
            if card in self._cards:
                self._cards.remove(card)
            lay = self._lay
            lay.removeWidget(card)
            card.hide()
            card.deleteLater()
            self._sync_size()
            self.widgetRemoved.emit(card)
        except Exception:
            exc_note("_remove_card @ ggis/common/widgets/msgbar.py:248")
            pass


class GgsMsgClose(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMsgClose")
class GgsMsgText(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsMsgText")
