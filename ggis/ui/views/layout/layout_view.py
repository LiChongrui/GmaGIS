# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout

from ggis.core.app import i18n
from ggis.common.base.view import GgsView

_tr = i18n.tr


def layout_view_id(layout):
    return "layout:%d" % id(layout)


class LayoutViewPage(GgsView):

    closed = Signal(str)

    def __init__(self, workspace, layout, parent=None):
        title = str(getattr(layout, "name", "") or _tr("布局"))
        super().__init__(layout_view_id(layout), title, parent)
        self.kind = "layout"
        self.closable = True
        self.icon_name = "layout"
        self.workspace = workspace
        self.layout = layout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if workspace is not None:
            try:
                workspace.setParent(self)
            except Exception:
                exc_note("__init__ @ ggis/ui/views/layout/layout_view.py:59")
                pass
            lay.addWidget(workspace, 1)
            try:
                workspace.closeRequested.connect(self._on_close_requested)
            except Exception:
                exc_note("__init__ @ ggis/ui/views/layout/layout_view.py:66")
                pass

    def _on_close_requested(self):
        host = self.parent()
        fn = getattr(host, "close_view", None)
        if not callable(fn):
            return
        try:
            fn(self.view_id)
        except Exception:
            exc_note("_on_close_requested @ ggis/ui/views/layout/layout_view.py:82")
            pass

    def rename(self, title):
        new = super().rename(title)
        try:
            if self.layout is not None:
                self.layout.name = new
        except Exception:
            exc_note("rename @ ggis/ui/views/layout/layout_view.py:91")
            pass
        return new

    def cleanup(self):
        try:
            sc = self.workspace.view.layout_scene()
            sc.shutdown()
        except Exception:
            exc_note("cleanup @ ggis/ui/views/layout/layout_view.py:102")
            pass
        try:
            if self.workspace is not None:
                self.workspace.detach_from_main_docks()
        except Exception:
            exc_note("cleanup @ ggis/ui/views/layout/layout_view.py:111")
            pass
        try:
            if self.workspace is not None:
                _win = getattr(self.workspace, "_win", None)
                if _win is not None and getattr(
                        _win, "_shared_layout_delegate", None) is self.workspace:
                    _win._shared_layout_delegate = None
        except Exception:
            exc_note("cleanup @ ggis/ui/views/layout/layout_view.py:123")
            pass
        try:
            if self.workspace is not None:
                self.workspace.setParent(None)
        except Exception:
            exc_note("cleanup @ ggis/ui/views/layout/layout_view.py:128")
            pass
        self.closed.emit(self.view_id)

    def control_group(self):
        from ggis.ui.views.control_group import ViewControlGroup
        ws = getattr(self, "workspace", None)
        tag = getattr(ws, "_tab_tag", "") if ws is not None else ""
        return ViewControlGroup(
            "layout", [], view_tag=tag or "",
            toolbar_tabs=["开始", "页面", "视图", "帮助"],
            status_kind="layout",
        )
