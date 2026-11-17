from ggis.common.util.exc_report import exc_note

import logging

from ggis.core.app import i18n
from PySide6.QtWidgets import QMenu

_log = logging.getLogger("gmagis")
_tr = i18n.tr


class GgsTitleRegion:

    def __init__(self, mw):
        self.mw = mw

    def build(self):
        mw = self.mw
        try:
            mw._app_menu = self._build_app_menu()
        except Exception:
            _log.exception("应用菜单构建失败")
            mw._app_menu = None
        try:
            mw._info_menu = self._build_project_info_menu()
        except Exception:
            _log.exception("工程信息菜单构建失败")
            mw._info_menu = None

    def _build_app_menu(self):
        from ggis.ui.framework.regions.TitleRegion import GgsAppMenu

        m = GgsAppMenu(self.mw)
        for key in ("new_project", "open_project"):
            a = self.mw.ctx.svc("actions")._acts.get(key)
            if a is not None:
                m.addAction(a)
        try:
            sub = m.addMenu(_tr("最近"))
            sub.setObjectName("GgsAppMenuRecent")
            sub.aboutToShow.connect(self._fill_recent_menu)
            self.mw._recent_menus = [sub]
        except Exception:
            exc_note("_build_app_menu @ ggis/ui/framework/regions/TitleRegion.py:87")
            self.mw._recent_menus = []
        m.addSeparator()
        for key in ("save_project", "save_project_as", "project_props"):
            a = self.mw.ctx.svc("actions")._acts.get(key)
            if a is not None:
                m.addAction(a)
        _opt_keys = ("settings", "about_act")
        if any(self.mw.ctx.svc("actions")._acts.get(k) is not None for k in _opt_keys):
            m.addSeparator()
            for k in _opt_keys:
                a = self.mw.ctx.svc("actions")._acts.get(k)
                if a is not None:
                    m.addAction(a)
        m.addSeparator()
        a = self.mw.ctx.svc("actions")._acts.get("quit")
        if a is not None:
            m.addAction(a)
        return m

    def _build_project_info_menu(self):
        from ggis.ui.framework.regions.TitleRegion import GgsProjectInfoMenu

        m = GgsProjectInfoMenu(self.mw)
        try:
            m.aboutToShow.connect(self._fill_project_info_menu)
        except Exception:
            exc_note("_build_project_info_menu @ ggis/ui/framework/regions/TitleRegion.py:126")
            pass
        try:
            self._fill_project_info_menu()
        except Exception:
            exc_note("_build_project_info_menu @ ggis/ui/framework/regions/TitleRegion.py:131")
            pass
        return m

    def _mk_recent_menu(self, parent_menu):
        sub = parent_menu.addMenu(_tr("最近文档"))
        try:
            self.mw.ctx.wiring.connect((sub.aboutToShow), (self._fill_recent_menu), "recent")
        except Exception:
            exc_note("_mk_recent_menu @ ggis/ui/framework/regions/TitleRegion.py:140")
            pass
        return sub


    def _fill_recent_menu(self):
        menus = list(getattr(self.mw, "_recent_menus", []))
        if not menus:
            return
        try:
            from ggis.core.app import recent as _recent
            paths = _recent.load()
        except Exception:
            exc_note("_fill_recent_menu @ ggis/ui/framework/regions/TitleRegion.py:164")
            _recent = None
            paths = []
        for m in menus:
            m.clear()
            if not paths:
                a = m.addAction(_tr("（尚无最近文档）"))
                a.setEnabled(False)
                continue
            for p in paths:
                ok = bool(_recent and _recent.exists(p))
                name = _recent.label(p) if _recent else p
                a = m.addAction(name if ok else
                                _tr("{0}（文件不存在）").format(name))
                a.setToolTip(p)
                if ok:
                    self.mw.ctx.wiring.connect((a.triggered), (lambda _c=False, _p=p: self.mw.ctx.svc("projects").open_recent(_p)), "recent")
                else:
                    a.setEnabled(False)
            m.addSeparator()
            a = m.addAction(_tr("清除最近文档列表"))
            self.mw.ctx.wiring.connect((a.triggered), (self.mw.ctx.svc("projects")._clear_recent), "recent")


    def _fill_project_info_menu(self):
        m = getattr(self.mw, "_info_menu", None)
        if m is None:
            return
        m.clear()

        vh = getattr(self.mw, "view_host", None)
        views = list(vh.views()) if vh is not None else []
        _kind_labels = {"map": _tr("地图"), "layout": _tr("布局"),
                        "model": _tr("模型")}
        counts, order = {}, []
        for v in views:
            k = str(getattr(v, "kind", "") or "generic")
            if k not in counts:
                order.append(k)
                counts[k] = 0
            counts[k] += 1
        if views:
            parts = []
            for k in order:
                lbl = _kind_labels.get(k, k)
                parts.append("{0}×{1}".format(lbl, counts[k]))
            view_line = _tr("视图：{0} 个（{1}）").format(
                len(views), " · ".join(parts))
        else:
            view_line = _tr("视图：0 个")

        import os as _os
        from datetime import datetime as _dt
        path = self.mw.ctx.svc("projects").project_path()
        saved = _tr("尚未保存")
        if path:
            try:
                saved = _dt.fromtimestamp(_os.path.getmtime(path)) \
                    .strftime("%Y-%m-%d %H:%M")
            except Exception:
                exc_note("_fill_project_info_menu @ ggis/ui/framework/regions/TitleRegion.py:238")
                saved = _tr("未知")

        for text in (_tr("文件路径：{0}").format(path) if path
                     else _tr("文件路径：尚未保存"),
                     view_line,
                     _tr("最近保存：{0}").format(saved)):
            a = m.addAction(text)
            a.setEnabled(False)




    def open_style_manager(self, layer=None):
        dark = True
        try:
            dark = bool(self.mw.canvas._is_dark_bg())
        except Exception:
            exc_note("open_style_manager @ ggis/ui/framework/regions/TitleRegion.py:264")
            pass
        from ggis.ui.dialogs.style_manager import GgsStyleManagerDialog
        dlg = GgsStyleManagerDialog(self.mw, dark_bg=dark)
        dlg.exec()
        return dlg


    def _refresh_after_style(self, lyr):
        try:
            self.mw.canvas.invalidate_labels(lyr)
        except Exception:
            exc_note("_refresh_after_style @ ggis/ui/framework/regions/TitleRegion.py:276")
            pass
        self.mw.canvas.refresh()






    def _coord_layer_crs(self):
        lyrs = []
        try:
            mv = self.mw.current_map_view()
            lt = mv.layer_tree() if mv is not None else None
            if lt is not None:
                lyrs = list(lt.layers() or [])
        except Exception:
            exc_note("_coord_layer_crs @ ggis/ui/framework/regions/TitleRegion.py:309")
            lyrs = []
        if not lyrs:
            try:
                lyrs = list(self.mw.ctx.project.layers() or [])
            except Exception:
                exc_note("_coord_layer_crs @ ggis/ui/framework/regions/TitleRegion.py:314")
                lyrs = []
        out = []
        for lyr in lyrs:
            try:
                c = lyr.crs()
                a = c.authid() if c is not None else None
            except Exception:
                exc_note("_coord_layer_crs @ ggis/ui/framework/regions/TitleRegion.py:321")
                a = None
            if a and a not in out:
                out.append(a)
        return out


    def _canvas_crs_authid(self):
        cv = self.mw.canvas
        if cv is None:
            return None
        try:
            c = cv.effectiveCrs()
            if c is not None and c.is_valid():
                return c.authid()
        except Exception:
            exc_note("_canvas_crs_authid @ ggis/ui/framework/regions/TitleRegion.py:343")
            return None
        return None






    def _default_new_crs(self):
        try:
            a = self.mw.canvas.destinationCrs()
        except Exception:
            exc_note("_default_new_crs @ ggis/ui/framework/regions/TitleRegion.py:368")
            a = ""
        return a or "EPSG:4326"






















































class GgsAppMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAppMenu")
class GgsProjectInfoMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsProjectInfoMenu")
