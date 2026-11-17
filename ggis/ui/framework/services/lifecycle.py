# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
from PySide6.QtCore import QTimer

from ggis.core.app import settings as app_settings
from ggis.core.app import i18n
from ggis.common.base.dialog import GgsMsgBox

_log = logging.getLogger("gmagis")
_tr = i18n.tr


def is_headless():
    try:
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.platformName().strip().lower() in (
            "offscreen", "minimal")
    except Exception:
        exc_note("is_headless @ ggis/ui/framework/services/lifecycle.py:38")
        return False


class Lifecycle:
    def __init__(self, ctx):
        self.ctx = ctx
        self.mw = ctx.mw

    def on_close(self, event) -> bool:
        mw = self.mw
        if getattr(mw, "_quitting", False):
            return True
        if not is_headless():
            if self.ctx.svc("projects").is_dirty():
                ans = self.ask_save_before_close()
                if ans == "cancel":
                    return False
                if ans == "save":
                    if not self.ctx.svc("projects").save_project():
                        return False
            else:
                ret = GgsMsgBox.question(
                    mw, _tr("退出 GmaGIS"), _tr("确定要退出 GmaGIS 吗？"),
                    GgsMsgBox.StandardButton.Yes
                    | GgsMsgBox.StandardButton.No,
                    GgsMsgBox.StandardButton.Yes)
                if ret != GgsMsgBox.StandardButton.Yes:
                    return False
        mw._quitting = True
        try:
            app_settings.save()
        except Exception:
            exc_note("on_close @ ggis/ui/framework/services/lifecycle.py:82")
            pass
        self.disconnect_all_timers()
        self.save_state()
        self._close_sub_windows()
        self.shutdown()
        return True

    def shutdown(self):
        self.disconnect_all_timers()
        try:
            self.ctx.svc("wiring").disconnect_all()
        except Exception:
            exc_note("shutdown @ ggis/ui/framework/services/lifecycle.py:106")
            pass
        try:
            from ggis.app import shutdown_workers
            shutdown_workers()
        except Exception:
            exc_note("shutdown @ ggis/ui/framework/services/lifecycle.py:111")
            pass
        try:
            vh = getattr(self.mw, "view_host", None)
            views = list(vh.views()) if vh is not None else []
            try:
                views += list(getattr(vh, "_parked", {}).values())
            except Exception:
                exc_note("shutdown @ ggis/ui/framework/services/lifecycle.py:121")
                pass
            for v in views:
                if str(getattr(v, "kind", "")) != "map":
                    continue
                cv = getattr(v, "canvas", None)
                if cv is not None and hasattr(cv, "release_buffers"):
                    cv.release_buffers()
        except Exception:
            exc_note("shutdown @ ggis/ui/framework/services/lifecycle.py:129")
            pass

    def disconnect_all_timers(self):
        for name in ("_save_timer", "_dirty_poll"):
            t = getattr(self.mw, name, None)
            if t is not None:
                try:
                    t.stop()
                except Exception:
                    exc_note("disconnect_all_timers @ ggis/ui/framework/services/lifecycle.py:139")
                    pass

    def is_quitting(self):
        return bool(getattr(self.mw, "_quitting", False))

    def schedule_state_save(self):
        mw = self.mw
        if getattr(mw, "_applying_project_ui", False):
            return
        t = getattr(mw, "_save_timer", None)
        if t is None:
            t = QTimer(mw)
            t.setSingleShot(True)
            self.ctx.wiring.connect((t.timeout), (self.save_state), "window")
            mw._save_timer = t
        t.start(1200)

    def save_state(self):
        mw = self.mw
        q = getattr(mw, "_qset", None)
        if q is None:
            return
        try:
            q.setValue("window/geometry", mw.saveGeometry())
        except Exception:
            exc_note("save_state @ ggis/ui/framework/services/lifecycle.py:188")
            pass
        try:
            sizes = mw.dock_region.collect_dock_sizes()
            for k, v in sizes.items():
                q.setValue("docksizes/%s" % str(k), int(v))
        except Exception:
            exc_note("save_state @ ggis/ui/framework/services/lifecycle.py:196")
            pass
        try:
            q.sync()
        except Exception:
            exc_note("save_state @ ggis/ui/framework/services/lifecycle.py:202")
            pass

    def ask_save_before_close(self):
        mw = self.mw
        try:
            title = str(self.ctx.project.title() or "") or _tr("未命名工程")
        except Exception:
            exc_note("ask_save_before_close @ ggis/ui/framework/services/lifecycle.py:194")
            title = _tr("未命名工程")
        ret = GgsMsgBox.question(
            mw, _tr("关闭 GmaGIS"),
            _tr("工程「{0}」有尚未保存的修改。\n\n"
                "关闭前要保存这些改动吗？").format(title),
            GgsMsgBox.StandardButton.Save
            | GgsMsgBox.StandardButton.Discard
            | GgsMsgBox.StandardButton.Cancel,
            GgsMsgBox.StandardButton.Save)
        if ret == GgsMsgBox.StandardButton.Save:
            return "save"
        if ret == GgsMsgBox.StandardButton.Cancel:
            return "cancel"
        return "discard"

    def _close_sub_windows(self):
        for w in list(getattr(self.mw, "_sub_windows", [])):
            try:
                w.close()
            except Exception:
                exc_note("_close_sub_windows @ ggis/ui/framework/services/lifecycle.py:217")
                pass
