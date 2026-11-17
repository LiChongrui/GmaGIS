# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtWidgets import QVBoxLayout

from ggis.core.app import i18n
from ggis.common.base.view import GgsView

_tr = i18n.tr

MODEL_VIEW_ID = "model"


class ModelViewPage(GgsView):

    def __init__(self, workspace, parent=None, title=None, view_id=None):
        super().__init__(view_id or MODEL_VIEW_ID, title or _tr("模型"), parent)
        self.kind = "model"
        self.closable = True
        self.icon_name = "model"
        self.workspace = workspace
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if workspace is not None:
            try:
                workspace.setParent(self)
            except Exception:
                exc_note("__init__ @ ggis/ui/views/model/model_view.py:64")
                pass
            lay.addWidget(workspace, 1)

    def is_busy(self):
        return _is_busy(self.workspace)

    def cleanup(self):
        ws = self.workspace
        self.workspace = None
        if ws is None:
            return
        host = getattr(ws, "_win", None)
        park = getattr(host, "_park_model_workspace", None)
        if (callable(park) and not getattr(host, "_quitting", False)
                and not getattr(host, "_resetting_models", False)):
            try:
                park(ws)
                return
            except Exception:
                exc_note("cleanup @ ggis/ui/views/model/model_view.py:99")
                pass
        try:
            ws.detach_from_main_docks()
        except Exception:
            exc_note("cleanup @ ggis/ui/views/model/model_view.py:109")
            pass
        try:
            ws.setParent(None)
        except Exception:
            exc_note("cleanup @ ggis/ui/views/model/model_view.py:113")
            pass

    def control_group(self):
        from ggis.ui.views.control_group import ViewControlGroup
        ws = getattr(self, "workspace", None)
        tag = getattr(ws, "_tab_tag", "") if ws is not None else ""
        return ViewControlGroup(
            "model", [], view_tag=tag or "",
            toolbar_tabs=["运行", "视图", "帮助"],
            status_kind="model",
        )


def _is_busy(ws):
    if ws is None:
        return False
    try:
        return (bool(getattr(ws, "_queue", None))
                or bool(getattr(ws, "_editing", None)))
    except Exception:
        exc_note("_is_busy @ ggis/ui/views/model/model_view.py:136")
        return False
