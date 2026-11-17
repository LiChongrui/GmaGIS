# -*- coding: utf-8 -*-

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (QDialogButtonBox, QHBoxLayout,
                               QListWidgetItem, QTextBrowser, QVBoxLayout)

from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.widgets.buttons import GgsButtonBox
from ggis.common.styling import icons
from ggis.common.base.dialog import GgsDialog
from ggis.core.app import i18n
import logging
_log = logging.getLogger("gmagis")

_tr = i18n.tr

MANUAL_FILE = "manual.md"

_FALLBACK = """# GmaGIS

手册文件 `resources/help/manual.md` 未能读取。

常用入口：

* **添加数据** —— 地图页 → 添加数据
* **编辑要素** —— 编辑页 → 开始编辑
* **空间分析** —— 分析页 → 处理工具箱
* **制图出图** —— 出图页 → 布局设计器
"""


def manual_path():
    try:
        from ...app_paths import resources_dir
        p = os.path.join(resources_dir(), "help", MANUAL_FILE)
        return p if os.path.exists(p) else ""
    except Exception:
        _log.exception("silent exception in manual_path")
        return ""


def load_manual():
    path = manual_path()
    if not path:
        return _FALLBACK
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        _log.exception("silent exception in load_manual")
        return _FALLBACK


def _outline(md_text):
    out = []
    for line in str(md_text or "").splitlines():
        s = line.strip()
        if not s.startswith("#"):
            continue
        level = len(s) - len(s.lstrip("#"))
        title = s[level:].strip()
        if not title or level > 3:
            continue
        out.append((level, title, title))
    return out


class GgsHelpDialog(GgsDialog):

    def __init__(self, parent=None, topic=""):
        super().__init__(parent)
        self.setObjectName("GgsHelpDialog")
        self.setWindowTitle(_tr("GmaGIS 使用手册"))
        try:
            self.setWindowIcon(icons.icon("help", size=16))
        except Exception:
            _log.exception("silent exception in __init__")
        self.resize(920, 680)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        body = QHBoxLayout()
        body.setSpacing(10)
        self.nav = GgsListWidget()
        self.nav.setFixedWidth(190)
        body.addWidget(self.nav)

        self.browser = QTextBrowser()
        self.browser.setObjectName("GgsHelpBody")
        self.browser.setOpenExternalLinks(False)
        body.addWidget(self.browser, 1)
        root.addLayout(body, 1)

        self._md = load_manual()
        self.browser.setMarkdown(self._md)
        self._fill_nav()
        self.nav.currentRowChanged.connect(self._on_nav)
        if topic:
            self._goto_topic(str(topic))

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_close = GgsButtonBox(QDialogButtonBox.StandardButton.Close)
        self.btn_close.button(
            QDialogButtonBox.StandardButton.Close).setText(_tr("关闭"))
        self.btn_close.rejected.connect(self.reject)
        row.addWidget(self.btn_close)
        root.addLayout(row)

    def _fill_nav(self):
        for level, title, anchor in _outline(self._md):
            it = QListWidgetItem(("　" * max(0, level - 1)) + _tr(title))
            it.setData(Qt.ItemDataRole.UserRole, anchor)
            if level == 1:
                f = it.font()
                f.setBold(True)
                it.setFont(f)
            self.nav.addItem(it)

    def _on_nav(self, row):
        if row < 0:
            return
        it = self.nav.item(row)
        if it is None:
            return
        title = str(it.data(Qt.ItemDataRole.UserRole) or "")
        if not title:
            return
        doc = self.browser.document()
        block = doc.firstBlock()
        while block.isValid():
            if block.text().strip() == title:
                self.browser.setTextCursor(QTextCursor(block))
                return
            block = block.next()

    def _goto_topic(self, topic):
        want = str(topic or "")
        for i in range(self.nav.count()):
            if want and want in self.nav.item(i).text():
                self.nav.setCurrentRow(i)
                return


def show_help(parent=None, topic=""):
    dlg = GgsHelpDialog(parent, topic=topic)
    try:
        dlg.exec()
    finally:
        try:
            dlg.deleteLater()
        except Exception:
            _log.exception("silent exception in show_help")
    return dlg
