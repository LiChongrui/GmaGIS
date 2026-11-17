# -*- coding: utf-8 -*-

from __future__ import annotations

from PySide6.QtWidgets import QWidget


class GgsView(QWidget):

    kind = "generic"
    closable = True
    park_on_close = False

    def __init__(self, view_id, title, parent=None):
        super().__init__(parent)
        self.view_id = str(view_id)
        self.title = str(title)
        self.icon_name = ""
        self.canvas = None
        self.layer_dock = None

    def crs(self):
        return None

    def view_activated(self):
        pass

    def view_deactivated(self):
        pass

    def cleanup(self):
        pass

    def rename(self, title):
        self.title = str(title or "").strip() or self.title
        return self.title
