# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
import os
from contextlib import contextmanager

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from ggis.core.app import i18n
from ggis.core.app import settings as app_settings
from ggis.core.model.project import GgsProject
from ggis.common.base.dialog import GgsMsgBox

_tr = i18n.tr
_log = logging.getLogger("gmagis")

LEVEL_INFO = "Info"
LEVEL_SUCCESS = "Success"
LEVEL_WARNING = "Warning"
LEVEL_CRITICAL = "Critical"
LEVEL_WARN = "Warning"


def _tree_leaves(nodes):
    out = []
    for nd in (nodes or []):
        if isinstance(nd, dict):
            out.extend(_tree_leaves(nd.get("children") or []))
        elif isinstance(nd, (tuple, list)) and nd and nd[0] is not None:
            out.append(nd)
    return out


class ProjectCtrl:

    def __init__(self, ctx):
        self.ctx = ctx
        self._save_task = None
        self._open_task = None
        self._applying_project_ui = False
        # 打开工程的 dirty 静音闸挂在主窗口上（消费点 map_view 读
        # self._host=self.window()，即主窗口属性），由 assembly 初始化 False。
        try:
            self.project.set_fingerprint_provider(self._content_fingerprint)
        except Exception:
            _log.exception("silent exception in ProjectCtrl.__init__")

    @property
    def mw(self):
        return self.ctx.mw

    @property
    def project(self):
        return self.ctx.project


    def open_project_properties(self):
        try:
            from ggis.ui.dialogs.app import ProjectPropertiesDialog
            dlg = ProjectPropertiesDialog(self.ctx.mw)
            if dlg.exec():
                data = dlg.collect()
                for k, v in data.items():
                    app_settings.set(k, v, persist=False)
                app_settings.save(commit_ephemeral=True)
                self.ctx.svc("shell")._update_window_title()
                self.ctx.mw.show_message(_tr("工程属性已保存"), LEVEL_SUCCESS)
        except Exception as e:
            self.ctx.mw.show_message(_tr("工程属性对话框加载失败：{}").format(e),
                              LEVEL_WARNING)

    def _mark_project_dirty(self):
        if getattr(self.ctx.mw, "_applying_project_ui", False):
            return
        if getattr(self.ctx.mw, "_booting", False):
            return
        try:
            proj = self.project
            proj.set_dirty(True)
        except Exception:
            exc_note("_mark_project_dirty @ ggis/ui/framework/services/project_ctrl.py:108")
            pass

    def _clear_recent(self):
        try:
            from ggis.core.app import recent as _recent
            _recent.clear()
        except Exception:
            exc_note("_clear_recent @ ggis/ui/framework/services/project_ctrl.py:116")
            pass
        try:
            self.ctx.region("title")._fill_recent_menu()
        except Exception:
            exc_note("_clear_recent @ ggis/ui/framework/services/project_ctrl.py:123")
            pass

    def project_path(self):
        try:
            return str(self.project.file_name() or "")
        except Exception:
            exc_note("project_path @ ggis/ui/framework/services/project_ctrl.py:129")
            return ""

    def confirm_before_close(self):
        dirty = False
        try:
            dirty = bool(self.project.is_dirty())
        except Exception:
            exc_note("confirm_before_close @ ggis/ui/framework/services/project_ctrl.py:137")
            dirty = False
        if bool(self.ctx.svc("views")._on_view_method("has_dirty_edits")):
            dirty = True
        if not dirty:
            return True
        res = GgsMsgBox.question(
            self.ctx.mw, _tr("未保存的更改"),
            _tr("工程有未保存的更改，要先保存吗？"),
            GgsMsgBox.StandardButton.Save
            | GgsMsgBox.StandardButton.Discard
            | GgsMsgBox.StandardButton.Cancel,
            GgsMsgBox.StandardButton.Save)
        if res == GgsMsgBox.StandardButton.Cancel:
            return False
        if res == GgsMsgBox.StandardButton.Save:
            return bool(self.save_project())
        return True

    def _content_fingerprint(self):
        proj = self.project
        layers = []
        for l in proj.layers():
            d = getattr(l, "__dict__", {})
            try:
                layers.append((
                    str(d.get("_id", "")),
                    int(d.get("_data_version", 0)),
                    int(d.get("_render_version", 0)),
                    str(getattr(l, "name", lambda: "")() or ""),
                    str(getattr(l, "source", lambda: "")() or ""),
                ))
            except Exception:
                exc_note("_content_fingerprint @ ggis/ui/framework/services/project_ctrl.py:186")
                layers.append((str(d.get("_id", "")), -1, -1, "?", "?"))
        views = []
        try:
            from ggis.ui.views.view_host import ViewHost
            vh = ViewHost.instance()
            for v in (vh.views() if vh is not None else []):
                if getattr(v, "kind", None) != "map":
                    continue
                try:
                    ext = v.extent()
                    ext_key = (tuple(round(float(x), 6) for x in ext)
                               if ext else None)
                except Exception:
                    exc_note("_content_fingerprint @ ggis/ui/framework/services/project_ctrl.py:199")
                    ext_key = None
                try:
                    ents = tuple(
                        (str(getattr(l, "__dict__", {}).get("_id", "")),
                         bool(vis))
                        for l, vis in v.layer_tree().entries())
                except Exception:
                    exc_note("_content_fingerprint @ ggis/ui/framework/services/project_ctrl.py:206")
                    ents = ()
                views.append((str(getattr(v, "view_id", "")), ext_key, ents))
        except Exception:
            exc_note("_content_fingerprint @ ggis/ui/framework/services/project_ctrl.py:209")
            views = []
        layouts = tuple(
            (str(getattr(la, "id", "")), str(getattr(la, "name", "")))
            for la in proj.layouts())
        models = []
        try:
            import json as _json
            for m in proj.models():
                models.append((
                    str(m.get("id", "")), str(m.get("name", "")),
                    _json.dumps(m.get("graph") or {}, sort_keys=True,
                                default=str)))
        except Exception:
            exc_note("_content_fingerprint @ ggis/ui/framework/services/project_ctrl.py:222")
            models = []
        return (str(proj.file_name() or ""), tuple(layers), tuple(views),
                layouts, tuple(models))

    def _mark_saved_baseline(self):
        try:
            self.project.set_saved_fingerprint(self._content_fingerprint())
        except Exception:
            _log.exception("silent exception in _mark_saved_baseline")

    def _project_sig(self):
        from ggis.core.model.layer import data_version
        try:
            proj = self.project
            out = []
            for lyr in proj.layers():
                out.append((str(lyr.__dict__.get("_id", "")),
                            int(data_version(lyr))))
            return (str(proj.file_name() or ""), tuple(sorted(out)))
        except Exception:
            exc_note("_project_sig @ ggis/ui/framework/services/project_ctrl.py:257")
            return None

    def _write_project(self, path):
        from ggis.io.project_io import save_project as _save
        self.ctx.mw._forward_to_map_view("_remember_current_extent")
        try:
            from ggis.ui.views.view_host import collect_view_snapshots
            views = collect_view_snapshots(self.project)
        except Exception:
            exc_note("_write_project @ ggis/ui/framework/services/project_ctrl.py:270")
            views = None
        try:
            from ggis.ui.views.view_host import collect_ui_session
            session = collect_ui_session()
        except Exception:
            exc_note("_write_project @ ggis/ui/framework/services/project_ctrl.py:278")
            session = None
        try:
            _docks = self.ctx.mw.dock_region.collect_session_docks()
        except Exception:
            exc_note("_write_project @ ggis/ui/framework/services/project_ctrl.py:286")
            _docks = None
        if _docks:
            if not isinstance(session, dict):
                session = {}
            session["docks"] = _docks
        try:
            res = _save(self.project, path, views=views, session=session)
        except Exception as e:
            self.ctx.mw.show_message(
                _tr("保存工程失败：{0}").format(e), LEVEL_WARN)
            return False
        if hasattr(res, "on_done"):
            self._save_task = res
            self.ctx.mw.show_message(_tr("正在保存工程…"), LEVEL_INFO)
            res.on_done(lambda ev: self._finish_write_project(ev.get("result")))
            res.on_fail(lambda ev: self.ctx.mw.show_message(
                _tr("保存工程失败：{0}").format(ev.get("error")), LEVEL_WARN))
            return True
        return self._finish_write_project(res)

    def _finish_write_project(self, res):
        if not res:
            return False
        proj = self.project
        sig_now = self._project_sig()
        sig_snap = res.get("sig")
        unchanged = (sig_snap is None or sig_now is None or sig_now == sig_snap)
        try:
            if unchanged:
                proj.set_file_name(res["path"])
                proj.set_dirty(False)
                self._mark_saved_baseline()
        except Exception:
            exc_note("_finish_write_project @ ggis/ui/framework/services/project_ctrl.py:335")
            pass
        if res["unsaved"]:
            self.ctx.mw.show_message(
                _tr("已保存工程：{0}（{1} 个图层）；"
                    "另有 {2} 个未落盘的图层未记入，请先保存这些图层")
                .format(res["path"], res["layers"], len(res["unsaved"])),
                LEVEL_WARN)
        else:
            self.ctx.mw.show_message(
                _tr("已保存工程：{0}（{1} 个图层）")
                .format(res["path"], res["layers"]), LEVEL_INFO)
        if not unchanged:
            self.ctx.mw.show_message(
                _tr("保存期间有改动，请再保存一次"),
                LEVEL_WARN)
        if unchanged:
            try:
                for lyr in proj.layers():
                    if str(lyr.source() or ""):
                        continue
                    s = self.ctx.svc("views")._on_view_method("_session_for", lyr)
                    if s.is_active() and s.is_dirty():
                        s.accept_in_memory()
            except Exception:
                exc_note("_finish_write_project @ ggis/ui/framework/services/project_ctrl.py:364")
                pass
        self.ctx.mw.log(_tr("工程已保存 → {0}").format(res["path"]))
        try:
            from ggis.core.app import recent as _recent
            _recent.add(res["path"])
        except Exception:
            exc_note("_finish_write_project @ ggis/ui/framework/services/project_ctrl.py:371")
            pass
        try:
            self.ctx.mw._update_dirty_ui(force=True)
        except Exception:
            exc_note("_finish_write_project @ ggis/ui/framework/services/project_ctrl.py:376")
            pass
        try:
            self.ctx.svc("shell")._update_window_title()
        except Exception:
            exc_note("_finish_write_project @ ggis/ui/framework/services/project_ctrl.py:381")
            pass
        return True

    def new_project(self, path=None):
        """新建工程。path 为 None 时弹保存框（原行为）；显式传空串
        = 内存工程（不绑定文件，窗口标题落"未命名工程"，保存时才选位置）；
        非空路径由外部（起始主页/向导）预先选好时跳过保存框。"""
        if not self.confirm_before_close():
            return False
        if path is None:
            try:
                from ggis.common.base.dialog import GgsFileDialog
                default = self.project_path() or self.ctx.svc("views")._on_view_method(
                    "_default_open_dir")
                path, _ = GgsFileDialog.getSaveFileName(
                    self.ctx.mw, _tr("新建工程（选择位置与名称）"), default,
                    _tr("GmaGIS 工程 (*.ggs);;所有文件 (*)"))
                if not path:
                    return False  # 弹框分支取消 = 不建工程（原行为不变）
            except Exception:
                exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:402")
                return False
        path = str(path or "").strip()
        if path:
            try:
                if not os.path.isabs(path):
                    path = os.path.abspath(path)
            except Exception:
                exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:409")
                pass
        # 启动画面进度：新建工程分支的装载从这里开始（splash._STEP_PLAN 0.27）。
        self.ctx.boot("正在创建工程…")
        proj = self.project
        try:
            proj.clear_undo()
        except Exception:
            _log.exception("silent exception in new_project")
        try:
            proj.remove_all()
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:420")
            pass
        try:
            proj.clear_layouts()
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:424")
            pass
        try:
            proj.clear_models()
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:428")
            pass
        self.ctx.svc("views")._close_all_model_views()
        self.ctx.svc("views")._reload_model_builder()
        try:
            proj.set_file_name(path)
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:436")
            pass
        try:
            proj.set_title("")
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:440")
            pass
        # 清掉上一个工程在"工程属性"里填的标题残留：新工程（尤其内存
        # 工程）的工程标题必须从空白开始，不串台
        try:
            app_settings.set("project_title", "")
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:445")
            pass
        try:
            proj.set_dirty(False)
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:444")
            pass
        self.ctx.mw._pending_argv_title = ""
        try:
            self.ctx.svc("shell")._update_window_title()
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:451")
            pass
        self.ctx.svc("views")._on_view_method("_refresh_layer_tree")
        try:
            if self.ctx.mw.canvas is not None:
                self.ctx.mw.canvas.adopt_project_crs()
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:460")
            pass
        try:
            if self.ctx.mw.canvas is not None:
                self.ctx.mw.canvas.refresh()
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:464")
            pass
        self._mark_saved_baseline()
        try:
            proj.set_dirty(False)
        except Exception:
            exc_note("new_project @ ggis/ui/framework/services/project_ctrl.py:471")
            pass
        self.ctx.mw.show_message(_tr("已新建工程"), LEVEL_INFO)
        return True

    def open_project(self):
        from ggis.common.base.dialog import GgsFileDialog
        if not self.confirm_before_close():
            return False
        default = self.project_path() or self.ctx.svc("views")._on_view_method("_default_open_dir")
        path, _ = GgsFileDialog.getOpenFileName(
            self.ctx.mw, _tr("打开工程"), default,
            _tr("GmaGIS 工程 (*.ggs);;所有文件 (*)"))
        if not path:
            return False
        return self._open_project_path(path)

    def open_recent(self, path):
        if not path:
            return False
        if not self.confirm_before_close():
            return False
        return self._open_project_path(path)

    def open_path(self, path):
        if not path:
            return False
        try:
            if not os.path.isabs(path):
                path = os.path.abspath(path)
        except Exception:
            exc_note("open_path @ ggis/ui/framework/services/project_ctrl.py:514")
            pass
        try:
            self.ctx.mw.activateWindow()
            self.ctx.mw.raise_()
        except Exception:
            exc_note("open_path @ ggis/ui/framework/services/project_ctrl.py:520")
            pass
        low = path.lower()
        if low.endswith(".ggs"):
            # 与对话框/最近工程入口同一保护：当前工程有未保存修改先问。
            # 启动期（主页/命令行）工程为空未标脏，confirm 直接过不弹框。
            if not self.confirm_before_close():
                return False
            return self._open_project_path(path)
        return self.ctx.svc("views")._on_view_method("_add_data_path", path, is_user=True)

    def _open_project_path(self, path):
        from ggis.io.project_io import load_project as _load
        # 启动画面进度：读取工程从这里开始（splash._STEP_PLAN 0.27）。
        self.ctx.boot("正在读取工程…")
        self.ctx.mw._pending_argv_title = ""
        self.ctx.svc("views")._on_view_method("_remember_dir", path)
        self.mw._mute_view_dirty = True
        try:
            self.project.set_saved_fingerprint(None)
        except Exception:
            exc_note("_open_project_path @ ggis/ui/framework/services/project_ctrl.py:546")
            pass

        proj = self.project
        try:
            proj.clear_undo()
        except Exception:
            _log.exception("silent exception in _open_project_path")
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.show_busy(
                self.ctx.mw, _tr("打开工程"),
                _tr("正在读取工程：{0}").format(os.path.basename(str(path))))
        except Exception:
            exc_note("_open_project_path @ ggis/ui/framework/services/project_ctrl.py:570")
            pass
        try:
            res = _load(path, proj)
        except Exception as e:
            return self._abort_open(e, path)
        if hasattr(res, "on_done"):
            self._open_task = res
            self.ctx.mw.show_message(_tr("正在打开工程…"), LEVEL_INFO)
            res.on_done(lambda ev: self._finish_open_project(
                ev.get("result"), path))
            res.on_fail(lambda ev: self.fail_open(
                ev.get("error"), path))
            return True
        return self._finish_open_project(res, path)

    def _forget_recent(self, path):
        try:
            from ggis.core.app import recent as _recent
            _recent.remove(path)
        except Exception:
            exc_note("_forget_recent @ ggis/ui/framework/services/project_ctrl.py:611")
            pass

    def _restore_project_session(self, session):
        if not isinstance(session, dict):
            return
        pages = session.get("pages") or []
        if not isinstance(pages, list) or not pages:
            return
        vh = getattr(self.ctx.mw, "view_host", None)
        if vh is None:
            return

        def _vid_of(p):
            kind = str(p.get("kind") or "")
            if kind == "map":
                return str(p.get("id") or "") or None
            if kind == "layout":
                lay = self.project.layout_by_id(str(p.get("layout_id") or ""))
                if lay is None:
                    return None
                from ggis.ui.views.layout.layout_view import layout_view_id
                return layout_view_id(lay)
            if kind == "model":
                mid = str(p.get("model_id") or "")
                return ("model:%s" % mid) if mid else None
            return None

        try:
            for p in pages:
                if not isinstance(p, dict):
                    continue
                kind = str(p.get("kind") or "")
                if kind == "layout":
                    lay = self.project.layout_by_id(
                        str(p.get("layout_id") or ""))
                    if lay is not None:
                        self.ctx.svc("views").open_layout_view(
                            lay, activate=False)
                elif kind == "model":
                    self.ctx.svc("views").restore_model_view(
                        str(p.get("model_id") or ""), activate=False)
            order = [vid for vid in (_vid_of(p) for p in pages
                                     if isinstance(p, dict))
                     if vid and vh.view(vid) is not None]
            if order:
                vh.reorder(order)
            for p in pages:
                if isinstance(p, dict) and p.get("active"):
                    vid = _vid_of(p)
                    if vid and vh.view(vid) is not None:
                        vh.activate(vid)
                    break
        except Exception:
            exc_note("_restore_project_session @ ggis/ui/framework/services/project_ctrl.py:681")
            pass

    def _abort_open(self, err, path):
        """打开失败统一收口：运行期弹提示条并终止装载；启动期（窗口
        未显示）直接退出进程——不半装载硬撑，异常也不靠 raise（任务
        回调里 raise 会被 PySide6 事件循环吞掉）。"""
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.hide_busy()
        except Exception:
            _log.exception("silent exception hiding busy on abort_open")
        self.mw._mute_view_dirty = False
        if self.ctx.mw.isVisible():
            self.ctx.mw.show_message(
                _tr("打开工程失败：{0}").format(err), LEVEL_WARN)
            if path:
                self._forget_recent(path)
            return False
        _log.exception("启动工程装载失败，退出：%r", path)
        import sys
        sys.exit(1)

    def fail_open(self, err, path=""):
        return self._abort_open(err, path)

    def apply_shell(self, res):
        """工程视图装载唯一入口（打开工程 / 新建工程共用）。阶段固定：
        ①对齐视图集 ②建壳 ③session 恢复（顺序+激活唯一权威）
        ④视图显示属性 ⑤装图层。激活兜底与图层 dock 显示在尾部统一做。
        不吞异常：任何阶段失败直接抛给调用方——运行期打开由
        _finish_open_project 走 fail_open 报错终止；启动期装载失败直接退出。
        title 在建壳构造期传入、extent 由 finalize_views 统一恢复，
        两者都不在此重复。"""
        vh = getattr(self.ctx.mw, "view_host", None)
        built_views = res["built_views"]
        view_meta = res["view_meta"]
        _log.info("[装载] ①begin built=%s meta_keys=%s",
                  list(built_views.keys()), list((view_meta or {}).keys()))

        def _vids():
            return [str(getattr(v, "view_id", "?")) for v in vh.views()]

        with self.suppress_ui_changes():
            self._align_view_set(vh, built_views)
            _log.info("[装载] ②aligned views=%s", _vids())
            # 启动画面进度按真实环境耗时占比推进（见 splash._STEP_PLAN，
            # 真实日志实测构造期/建壳期 ≈42%/42% 均分）：建视图壳
            # ≈40%（等渲染子进程握手），逐视图 tick 在
            # _ensure_view_shells 内（0.47→0.87）持续移动。
            first_vid = self._ensure_view_shells(vh, built_views, view_meta)
            _log.info("[装载] ③shells views=%s first=%s",
                      _vids(), first_vid)
            _session = res.get("session")
            if isinstance(_session, dict) and _session:
                self._restore_project_session(_session)
                _docks = _session.get("docks")
                if isinstance(_docks, dict) and _docks:
                    self.ctx.mw.dock_region.apply_session_docks(_docks)
            _cur = vh.current_view() if vh is not None else None
            _log.info("[装载] ④session done views=%s cur=%s",
                      _vids(), getattr(_cur, "view_id", None))
            for vid in built_views.keys():
                self._apply_view_meta(vh, vid, view_meta.get(vid) or {})
            self.ctx.boot("正在装载图层…")
            for vid, built in built_views.items():
                self._load_layers_into(vh, vid, built)
            # 激活兜底：session 未给出有效激活页时用第一个视图。
            _cur = vh.current_view() if vh is not None else None
            if _cur is None and first_vid is not None \
                    and vh.view(first_vid) is not None:
                vh.activate(first_vid)
            _cur = vh.current_view() if vh is not None else None
            if _cur is not None and str(getattr(_cur, "kind", "")) == "map":
                self.ctx.mw.dock_region._show_active_map_layer_dock(_cur)
            _tabs = getattr(self.ctx.mw, "view_tabs", None)
            _log.info("[装载] ⑤layers done views=%s cur=%s tabs=%d",
                      _vids(), getattr(_cur, "view_id", None),
                      _tabs.tabs.count() if _tabs is not None else -1)

        QTimer.singleShot(
            0, lambda: self.finalize_views(view_meta, res.get("session")))

    @contextmanager
    def suppress_ui_changes(self):
        self._applying_project_ui = True
        try:
            yield
        finally:
            self._applying_project_ui = False

    def _align_view_set(self, vh, built_views):
        if vh is None:
            return
        # 注意：built_views 允许为空——新建工程不勾任何视图时走这里，
        # 语义 = 关闭现有工程的全部视图（零视图工程），不能提前 return。
        _keep = {str(_k) for _k in built_views.keys()}
        svc_v = self.ctx.svc("views")
        for _v in list(vh.views()):
            _vid = str(getattr(_v, "view_id", ""))
            if _vid in _keep:
                continue
            # force：装载场景旧视图一律丢弃——无视"至少保留一个"约束、
            # 不 park，dock/ribbon/状态清理在关闭门面里完整执行。
            svc_v.close_view(_vid, force=True)
        # 清掉旧工程遗留的 parked 视图（装载=全新工程，不复用 parked）。
        vh.retain_for_project(built_views.keys())
        vh.reorder(list(built_views.keys()))

    def _ensure_view_shells(self, vh, built_views, view_meta=None):
        _n = max(1, len(built_views))
        for _i, vid in enumerate(built_views.keys()):
            # 启动画面进度：建壳与构造期同为启动最长段（真实各 ~2s，各占
            # ~42%）。逐视图发 tick（0.47→0.87 按视图数均分），同文本 +
            # 显式 frac——splash 计数器不去重推进、百分比持续移动。
            self.ctx.boot("正在创建视图…",
                          frac=0.47 + _i / float(_n) * 0.40)
            _t = ((view_meta or {}).get(vid) or {}).get("title")
            v = self.ctx.svc("views")._restore_map_view(
                vid, title=(str(_t) if _t else None))
            if v is None:
                raise RuntimeError(_tr("视图壳创建失败") + ": " + str(vid))
            # 复用的旧壳可能挂着上一工程的属性表 dock，建壳后立即清。
            _docks = getattr(v, "_attr_docks", None)
            if _docks:
                for _ad in list(_docks.values()):
                    _ad.close()
                    _ad.deleteLater()
                _docks.clear()
        _svc_v = self.ctx.svc("views")
        _svc_v._close_all_model_views()
        _svc_v._reload_model_builder()
        # 全部壳建完（最后一个握手也结束）：进度推到 0.87，接装载图层 0.93。
        self.ctx.boot("正在创建视图…", frac=0.87)
        return next(iter(built_views.keys()), None)

    def _apply_view_meta(self, vh, vid, meta):
        """视图显示属性恢复：CRS 与比例锁。title 在建壳构造期传入、
        extent 由 finalize_views 统一恢复——都不在此重复。
        数据坏（无效 CRS 等）直接抛，由打开失败路径报告，不吞。"""
        v = vh.view(vid) if vh is not None else None
        if v is None or getattr(v, "kind", None) != "map":
            return
        _m = meta or {}
        _vcrs = _m.get("crs")
        if _vcrs:
            from ggis.core.crs import GgsCoordinateReferenceSystem as _Crs
            v.set_crs(_Crs.from_user_input(str(_vcrs)))
        _disp = _m.get("display")
        if isinstance(_disp, dict) and "scale_locked" in _disp:
            v.canvas.setScaleLocked(bool(_disp.get("scale_locked")))

    def _load_layers_into(self, vh, vid, built):
        v = vh.view(vid) if vh is not None else None
        if v is None or getattr(v, "kind", None) != "map":
            return
        lt = v.layer_tree()
        if lt is None:
            raise RuntimeError(_tr("视图图层树不可用") + ": " + str(vid))

        _has_tree = any(isinstance(e, dict) for e in (built or []))
        lt.from_built(built)

        # 视图无显式 CRS 时取第一个有效图层的 CRS（数据缺省约定，非兜底）。
        if not v.has_explicit_crs():
            _seq = list(reversed(_tree_leaves(built))) if _has_tree else built
            for _e in _seq:
                if not isinstance(_e, (tuple, list)) or not _e \
                        or _e[0] is None:
                    continue
                _lc = _e[0].crs()
                if _lc is not None and _lc.is_valid():
                    v.set_crs(_lc)
                    break



    def _finish_open_project(self, res, path=""):
        res = res or {}
        try:
            from ggis.ui.dialogs import busy as _busy
            _busy.hide_busy()
        except Exception:
            exc_note("_finish_open_project @ ggis/ui/framework/services/project_ctrl.py:1031")
            pass

        try:
            self.apply_shell(res)
        except Exception as e:
            # 装载失败统一收口：运行期弹条终止；启动期直接退出进程。
            return self._abort_open(e, path)

        _vh = getattr(self.ctx.mw, "view_host", None)
        _tabs = getattr(self.ctx.mw, "view_tabs", None)
        _log.info("[装载] applied path=%s views=%s tabs=%d visible=%s", path,
                  [str(getattr(v, "view_id", "?")) for v in _vh.views()]
                  if _vh is not None else [],
                  _tabs.tabs.count() if _tabs is not None else -1,
                  _tabs.isVisible() if _tabs is not None else "?")


        try:
            self.ctx.svc("shell")._update_window_title()
        except Exception:
            exc_note("_finish_open_project @ ggis/ui/framework/services/project_ctrl.py:1059")
            pass

        if path:
            try:
                from ggis.core.app import recent as _recent
                _recent.add(path)
            except Exception:
                exc_note("_finish_open_project @ ggis/ui/framework/services/project_ctrl.py:1067")
                pass

        errs = res.get("errors") or []
        if errs:
            self.ctx.mw.show_message(
                _tr("已打开工程：{0} 个图层；{1} 个未能恢复")
                .format(res.get("loaded", 0), len(errs)), LEVEL_WARN)
            for line in errs[:12]:
                self.ctx.mw.log(_tr("工程加载：{0}").format(line))
        else:
            self.ctx.mw.show_message(
                _tr("已打开工程：{0} 个图层").format(res.get("loaded", 0)),
                LEVEL_INFO)
        return True

    def finalize_views(self, view_meta, session=None):
        """装载收尾（唯一）：恢复各视图范围（全链路唯一的 extent 恢复点）、
        复位 dirty 静音闸、记保存基线。经 QTimer.singleShot(0) 在装载
        主流程之后执行。范围数据坏直接抛，由失败路径报告，不吞。"""
        vh = getattr(self.ctx.mw, "view_host", None)
        if vh is not None:
            from ggis.core.crs.extent import GgsRectangle as _Rect
            for _vid, _meta in (view_meta or {}).items():
                _vv = vh.view(_vid)
                if _vv is None or getattr(_vv, "kind", None) != "map":
                    continue
                _cv = getattr(_vv, "canvas", None)
                if _cv is None:
                    continue
                _ext = _meta.get("extent")
                _have_ext = (bool(_ext) and len(_ext) == 4
                             and (float(_ext[2]) - float(_ext[0])) > 0
                             and (float(_ext[3]) - float(_ext[1])) > 0)
                if _have_ext:
                    _x0, _y0, _x1, _y1 = (float(x) for x in _ext)
                    if (_x1 - _x0) > 0 and (_y1 - _y0) > 0:
                        _cv.zoomToExtent(_Rect(_x0, _y0, _x1, _y1))
                else:
                    self.ctx.svc("views")._zoom_view_to_layers(_vv)
        self.mw._mute_view_dirty = False
        self._mark_saved_baseline()
        self.project.set_dirty(False)
        _tabs = getattr(self.mw, "view_tabs", None)
        _log.info("[装载] finalize views=%s cur=%s tabs=%d",
                  [str(getattr(v, "view_id", "?"))
                   for v in (vh.views() if vh is not None else [])],
                  getattr(vh.current_view(), "view_id", None)
                  if vh is not None else None,
                  _tabs.tabs.count() if _tabs is not None else -1)

    def save_project(self):
        path = self.project_path()
        if not path:
            return self.save_project_as()
        return self._write_project(path)

    def save_project_as(self):
        from ggis.common.base.dialog import GgsFileDialog
        proj = self.project
        try:
            title = str(proj.title() or "") or _tr("未命名工程")
        except Exception:
            exc_note("save_project_as @ ggis/ui/framework/services/project_ctrl.py:1163")
            title = _tr("未命名工程")
        base = (self.ctx.svc("views")._on_view_method("_default_open_dir")
                or app_settings.get("last_open_dir")
                or os.path.expanduser("~"))
        default = self.project_path() or os.path.join(base, title + ".ggs")
        path, _ = GgsFileDialog.getSaveFileName(
            self.ctx.mw, _tr("工程另存为"), default,
            _tr("GmaGIS 工程 (*.ggs);;所有文件 (*)"))
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += ".ggs"
        self.ctx.svc("views")._on_view_method("_remember_dir", path)
        return self._write_project(path)

    def is_dirty(self):
        try:
            return bool(self.project.is_dirty())
        except Exception:
            exc_note("is_dirty @ ggis/ui/framework/services/project_ctrl.py:1189")
            return False

