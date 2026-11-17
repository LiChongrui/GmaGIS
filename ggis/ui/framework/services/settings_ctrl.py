# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
import re

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from ggis.core.app import i18n
from ggis.common.styling import icons, themes

_tr = i18n.tr
_log = logging.getLogger("gmagis")

LEVEL_SUCCESS = "Success"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"

HANDLERS = (
    (r"^theme$",         "_apply_theme",          False),
    (r"^font.*",         "_apply_font",           True),
    (r"^canvas_color$",  "_apply_canvas_color",   True),
    (r"^language$",      None,                    False),
)


class SettingsCtrl:

    def __init__(self, ctx):
        self.ctx = ctx
        self.last_changed_keys = set()
        self.restart_pending = []

    @property
    def mw(self):
        return self.ctx.mw

    def apply_all(self):
        return self.apply(None)

    def apply(self, changed_keys=None):
        full = changed_keys is None
        keys = set() if full else set(changed_keys or ())
        self.last_changed_keys = None if full else set(keys)
        for pattern, handler, only_full in HANDLERS:
            if handler is None or (only_full and not full):
                continue
            if full or any(re.match(pattern, k) for k in keys):
                getattr(self, handler)()
        if full or "theme" in keys or "language" in keys:
            self._retext_all_ribbons()
        return sorted(keys)

    def restart_pending_labels(self):
        return list(self.restart_pending)

    def open_dialog(self):
        import os as _os
        if _os.environ.get("GGIS_PROBE"):
            import sys as _s
            import traceback as _tb
            _tb.print_stack(file=_s.stderr)
            _s.stderr.write("[P] open_settings entered\n")
            _s.stderr.flush()
        mw = self.mw
        self.restart_pending = []
        try:
            from ggis.ui.dialogs.settings import SettingsDialog
        except Exception as e:
            mw.show_message(_tr("选项对话框加载失败：{}").format(e),
                            LEVEL_CRITICAL)
            return
        dlg = SettingsDialog(mw)
        try:
            if not dlg.exec():
                return
            if dlg.changed():
                for k, v in dlg._collect().items():
                    try:
                        self.ctx.settings.set(k, v, persist=False)
                    except Exception:
                        exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:146")
                        pass
                self.ctx.settings.save(commit_ephemeral=True)
                _changed_keys = set()
                try:
                    _changed_keys = set(dlg.changed_keys() or ())
                except Exception:
                    exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:155")
                    _changed_keys = set()
                self.apply(changed_keys=(_changed_keys or None))
                mw.ctx.svc("shell")._update_window_title()
                try:
                    if dlg.render_changed():
                        mw.canvas.refresh_render_settings()
                    if dlg.selection_style_changed():
                        mw.canvas.refresh_selection()
                    if dlg.canvas_color_changed():
                        self.apply_canvas_color()
                except Exception:
                    exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:178")
                    pass
                try:
                    _mvs = mw.current_map_view()
                    sn = getattr(_mvs, "_snapper", None) if _mvs is not None else None
                    if sn is None and _mvs is not None:
                        try:
                            sn = _mvs.snapper()
                        except Exception:
                            exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:188")
                            sn = None
                    if sn is not None:
                        sn.tolerance_px = float(
                            self.ctx.settings.get("snap_tolerance_px", 8) or 8)
                except Exception:
                    exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:193")
                    pass
                if dlg.cache_clear_requested():
                    self.clear_render_caches()
                try:
                    _lf = dlg.log_file_requested()
                    if _lf:
                        from ggis.app import set_log_file as _set_log_file
                        _set_log_file(_lf)
                except Exception:
                    exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:203")
                    pass
                self._emit_restart_hints(dlg)
            self.ctx.events.settings_applied.emit(
                None if self.last_changed_keys is None else set(self.last_changed_keys))
        finally:
            try:
                dlg.deleteLater()
            except Exception:
                exc_note("open_dialog @ ggis/ui/framework/services/settings_ctrl.py:213")
                pass

    def _emit_restart_hints(self, dlg):
        mw = self.mw
        _pending = dlg.restart_pending_labels()
        self.restart_pending = list(_pending or ())
        if not _pending:
            return
        _msg = _tr("{0} 已保存，重启程序后生效。").format("、".join(_pending))
        mw.show_message(_msg, LEVEL_SUCCESS)
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.warning(mw, _tr("需要重启"), _msg)
        except Exception:
            exc_note("_emit_restart_hints @ ggis/ui/framework/services/settings_ctrl.py:231")
            pass

    def _apply_theme(self):
        mw = self.mw
        name = self.ctx.settings.get("theme")
        dark = (name == "dark")
        icons.set_theme(dark)
        app = QApplication.instance()
        try:
            app.setStyleSheet(themes.qss(name))
        except Exception as e:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:245")
            mw.log(_tr("[错误] 样式加载失败：{}").format(e))
        try:
            app.setPalette(themes.palette(name))
        except Exception:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:249")
            pass
        try:
            for w in QApplication.allWidgets():
                st = w.style()
                st.unpolish(w)
                st.polish(w)
                w.update()
        except Exception:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:257")
            pass
        for a, icon_name in mw.ctx.svc("actions")._icon_actions:
            try:
                a.setIcon(icons.icon(icon_name))
            except Exception:
                exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:262")
                pass
        try:
            mw._update_dirty_ui(force=True)
        except Exception:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:268")
            pass
        try:
            icons.retheme_all()
        except Exception:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:272")
            pass
        try:
            for w in mw.findChildren(QWidget):
                fn = getattr(w, "retheme", None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:284")
                        pass
        except Exception:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:286")
            pass
        try:
            mw.retheme_statusbar()
        except Exception:
            exc_note("_apply_theme @ ggis/ui/framework/services/settings_ctrl.py:293")
            pass

    def _apply_font(self):
        try:
            app = QApplication.instance()
            f = app.font()
            f.setFamily("Microsoft YaHei")
            f.setPointSizeF(9.0)
            app.setFont(f)
        except Exception:
            exc_note("_apply_font @ ggis/ui/framework/services/settings_ctrl.py:307")
            pass

    def canvas_bg_color(self):
        try:
            c = str(self.ctx.settings.get("canvas_color") or "").strip()
            if c:
                qc = QColor(c)
                if qc.isValid():
                    return qc
        except Exception:
            exc_note("canvas_bg_color @ ggis/ui/framework/services/settings_ctrl.py:327")
            pass
        return QColor(themes.canvas_color(self.ctx.settings.get("theme")))

    def _apply_canvas_color(self):
        mw = self.mw
        col = self.canvas_bg_color()
        changed = False
        try:
            cv = mw.canvas
            if cv is not None:
                changed = (cv.canvasColor() != col)
                cv.setCanvasColor(col)
        except Exception:
            exc_note("_apply_canvas_color @ ggis/ui/framework/services/settings_ctrl.py:345")
            pass
        try:
            mw._map_dock_mgr.overview.setBackgroundColor(col)
        except Exception:
            exc_note("_apply_canvas_color @ ggis/ui/framework/services/settings_ctrl.py:349")
            pass
        if changed:
            try:
                mw.canvas.refresh_canvas_color()
            except Exception:
                exc_note("_apply_canvas_color @ ggis/ui/framework/services/settings_ctrl.py:354")
                pass

    def apply_canvas_color(self):
        return self._apply_canvas_color()

    def _retext_all_ribbons(self):
        mw = self.mw
        try:
            mw.ribbon.retext()
        except Exception:
            exc_note("_retext_all_ribbons @ ggis/ui/framework/services/settings_ctrl.py:370")
            pass
        try:
            ribbons = mw._all_ribbons()
        except Exception:
            exc_note("_retext_all_ribbons @ ggis/ui/framework/services/settings_ctrl.py:374")
            ribbons = ()
        for _r in ribbons or ():
            if _r is not mw.ribbon:
                try:
                    _r.retext()
                except Exception:
                    exc_note("_retext_all_ribbons @ ggis/ui/framework/services/settings_ctrl.py:380")
                    pass

    def clear_render_caches(self):
        try:
            from ggis.render.cpu import backend as _qb
            from ggis.render.cpu import raster as _qr
            _qb.clear_cache()
            _qr.clear_cache()
        except Exception:
            exc_note("clear_render_caches @ ggis/ui/framework/services/settings_ctrl.py:394")
            pass
        try:
            from ggis.render.painter import RASTER_WINDOW_CACHE, THUMB_CACHE
            RASTER_WINDOW_CACHE.clear()
            THUMB_CACHE.clear()
        except Exception:
            exc_note("clear_render_caches @ ggis/ui/framework/services/settings_ctrl.py:400")
            pass
        try:
            self.mw.canvas.update()
        except Exception:
            exc_note("clear_render_caches @ ggis/ui/framework/services/settings_ctrl.py:404")
            pass

    def open_help(self, topic=""):
        try:
            from ggis.ui.dialogs.help import show_help
            show_help(self.mw, topic=topic)
            return True
        except Exception as e:
            self.mw.show_message(_tr("使用手册加载失败：{}").format(e),
                                 LEVEL_WARNING)
            return False

    def open_shortcuts(self):
        try:
            from ggis.ui.dialogs.app import ShortcutsDialog
            dlg = ShortcutsDialog(self.mw)
            dlg.exec()
        except Exception as e:
            self.mw.show_message(_tr("快捷键速查表加载失败：{}").format(e),
                                 LEVEL_WARNING)

    def about(self):
        try:
            from ggis.ui.dialogs.about import show_about
            show_about(self.mw)
        except Exception as e:
            self.mw.show_message(_tr("关于对话框加载失败：{}").format(e),
                                 LEVEL_WARNING)

    def open_widget_gallery(self):
        try:
            from ggis.ui.dialogs.widget_gallery import GgsWidgetGalleryDialog
        except Exception as e:
            self.mw.show_message(_tr("控件画廊加载失败：{}").format(e),
                                 LEVEL_WARNING)
            return
        GgsWidgetGalleryDialog(self.mw).exec()
