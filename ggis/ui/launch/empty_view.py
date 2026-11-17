# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout

from ggis.common.styling import icons
from ggis.core.app import i18n
from PySide6.QtWidgets import QLabel, QToolButton


def _tile(text, tip, icon_name):
    b = GgsWelcomeTile()
    b.setText(i18n.tr(text))
    b.setToolTip(i18n.tr(tip))
    icons.bind(b, icon_name, size=26)
    b.setIconSize(QSize(26, 26))
    b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    b.setFixedSize(172, 64)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


class EmptyViewLayer(QFrame):

    def __init__(self, mainWindow, parent):
        super().__init__(parent)
        self.mainWindow = mainWindow
        self.setObjectName("GgsEmptyViewCard")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        title = GgsWelcomeTitle(i18n.tr("没有打开的视图"))
        sub = GgsWelcomeSub(i18n.tr("新建一个视图开始工作：地图用于浏览与编辑空间数据，"
                             "布局用于排版出图，模型构建器用于搭建数据处理流程。"))
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_map = _tile("地图", "新建地图视图", "map_street")
        self.btn_layout = _tile("布局", "新建布局视图", "layout")
        self.btn_model = _tile("模型构建器", "打开模型构建器", "model")

        row = QHBoxLayout()
        row.setSpacing(10)
        for b in (self.btn_map, self.btn_layout, self.btn_model):
            row.addWidget(b)
        row.addStretch(1)

        v = QVBoxLayout(self)
        v.setContentsMargins(30, 26, 30, 24)
        v.setSpacing(12)
        v.addWidget(title)
        v.addWidget(sub)
        v.addSpacing(4)
        v.addLayout(row)

        self.btn_map.clicked.connect(lambda: self._create("map"))
        self.btn_layout.clicked.connect(lambda: self._create("layout"))
        self.btn_model.clicked.connect(lambda: self._create("model"))

        parent.installEventFilter(self)
        self.resize_to_parent()
        self.hide()

    def _create(self, kind):
        win = self.mainWindow
        self.hide()
        try:
            win.ctx.svc("views")._on_view_create(kind)
        except Exception:
            exc_note("_create @ ggis/ui/launch/empty_view.py:100")
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                exc_note("_create @ ggis/ui/launch/empty_view.py:104")
                pass
        try:
            vh = win.view_host
            if vh is None or vh.count_views() == 0:
                self.show_empty()
        except Exception:
            exc_note("_create @ ggis/ui/launch/empty_view.py:111")
            self.show_empty()

    def show_empty(self):
        try:
            self.setVisible(True)
            self.resize_to_parent()
            self.raise_()
        except Exception:
            exc_note("show_empty @ ggis/ui/launch/empty_view.py:120")
            pass

    def hide_empty(self):
        try:
            self.hide()
        except Exception:
            exc_note("hide_empty @ ggis/ui/launch/empty_view.py:126")
            pass

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.resize_to_parent()
        return super().eventFilter(obj, event)

    def showEvent(self, e):
        super().showEvent(e)
        self.resize_to_parent()
        self.raise_()

    def resize_to_parent(self):
        p = self.parentWidget()
        if p is None:
            return
        sh = self.sizeHint()
        w = min(sh.width(), max(320, p.width() - 24))
        h = min(sh.height(), max(200, p.height() - 24))
        self.setGeometry(max(0, (p.width() - w) // 2),
                         max(0, (p.height() - h) // 2), w, h)


class GgsWelcomeSub(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsWelcomeSub")
class GgsWelcomeTile(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsWelcomeTile")
class GgsWelcomeTitle(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsWelcomeTitle")
