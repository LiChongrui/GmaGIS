# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging

from PySide6.QtCore import QSettings
import os

_log = logging.getLogger("gmagis")

from ggis.ui.features._hostdeps import _tr


class WindowShell:
    def __init__(self, ctx):
        self.ctx = ctx
        self.mw = ctx.mw

    def _update_window_title(self):
        path = self.mw.ctx.svc("projects").project_path()
        if path:
            base = os.path.splitext(os.path.basename(path))[0]
        else:
            # 无路径 = 内存工程：忽略全局 project_title（那是上一个工程在
            # 工程属性里填的标题，残留在设置里会串台），标题栏给出
            # 明确的内存工程标识
            base = (getattr(self.mw, "_pending_argv_title", "")
                    or _tr("内存工程"))
        self.mw.setWindowTitle(base)
        tb = getattr(self.mw, "_title_bar", None)
        if tb is not None:
            tbtn = getattr(tb, "_title", None)
            if tbtn is not None:
                tbtn.setText(base)



    def _restore_geometry(self):
        self.mw._qset = QSettings("GmaGIS", "GmaGIS")
        geo = self.mw._qset.value("window/geometry")
        if geo is not None:
            self.mw._pending_geo = geo
            try:
                self.mw.restoreGeometry(geo)
            except Exception:
                exc_note("_restore_geometry @ ggis/ui/framework/services/window_shell.py:73")
                pass



    def _finish_boot(self):
        try:
            from PySide6.QtCore import QCoreApplication
            QCoreApplication.sendPostedEvents(None, 0)
        except Exception:
            exc_note("_finish_boot @ ggis/ui/framework/services/window_shell.py:107")
            pass
        d = getattr(self.mw._map_dock_mgr, "identify_dock", None)
        front = False
        try:
            front = bool(d) and self.mw.ctx.region("dock")._dock_is_front(d)
        except Exception:
            exc_note("_finish_boot @ ggis/ui/framework/services/window_shell.py:113")
            front = False
        try:
            if front:
                self.mw.ctx.svc("views")._on_view_method("set_map_tool", "identify")
            else:
                self.mw.ctx.svc("views")._on_view_method("set_map_tool", "pan")
        except Exception:
            exc_note("_finish_boot @ ggis/ui/framework/services/window_shell.py:120")
            pass
        self.mw._booting = False



