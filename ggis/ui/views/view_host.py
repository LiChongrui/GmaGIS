# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget


def collect_view_snapshots(project=None, base_dir=""):
    from ggis.core.model.layer import freeze_layer
    vh = ViewHost.instance()
    if vh is None:
        raise RuntimeError("no ViewHost")
    out = []
    for v in vh.views():
        if getattr(v, "kind", None) != "map":
            continue
        lt = None
        try:
            lt = v.layer_tree()
            layer_objs = [(freeze_layer(l), bool(vis))
                         for l, vis in list(lt.entries())]
        except Exception:
            exc_note("collect_view_snapshots @ ggis/ui/views/view_host.py:47")
            layer_objs = []
        try:
            tree = lt.tree_snapshot() if lt is not None else None
        except Exception:
            exc_note("collect_view_snapshots @ ggis/ui/views/view_host.py:60")
            tree = None
        try:
            vcrs = v.crs().authid() if v.has_explicit_crs() else None
        except Exception:
            exc_note("collect_view_snapshots @ ggis/ui/views/view_host.py:51")
            vcrs = None
        try:
            ext = v.extent()
        except Exception:
            exc_note("collect_view_snapshots @ ggis/ui/views/view_host.py:55")
            ext = None
        try:
            display = {"scale_locked": bool(v.canvas.isScaleLocked())}
        except Exception:
            exc_note("collect_view_snapshots @ ggis/ui/views/view_host.py:76")
            display = None
        out.append({
            "id": str(v.view_id),
            "title": str(v.title or ""),
            "crs": vcrs,
            "extent": ext,
            "layers": layer_objs,
            "tree": tree,
            "display": display,
        })
    if not out:
        raise RuntimeError("no map views")
    return out


def collect_ui_session():
    vh = ViewHost.instance()
    if vh is None:
        return None
    pages = []
    cur = vh.current_view()
    cur_vid = str(getattr(cur, "view_id", "") or "") if cur is not None else ""
    cur_kind = str(getattr(cur, "kind", "") or "") if cur is not None else ""
    cur_lay_id = ""
    if cur_kind == "layout":
        cur_lay_id = str(getattr(getattr(cur, "layout", None), "id", "") or "")
    for v in vh.views():
        kind = str(getattr(v, "kind", "") or "")
        vid = str(getattr(v, "view_id", "") or "")
        page = None
        if kind == "map":
            page = {"kind": "map", "id": vid}
        elif kind == "layout":
            lay_id = str(getattr(getattr(v, "layout", None), "id", "") or "")
            if lay_id:
                page = {"kind": "layout", "layout_id": lay_id}
        elif kind == "model":
            mid = vid.split(":", 1)[-1]
            if mid:
                page = {"kind": "model", "model_id": mid}
        if page is None:
            continue
        is_active = (
            (kind == "map" and vid and vid == cur_vid)
            or (kind == "layout" and cur_kind == "layout"
                and page.get("layout_id") == cur_lay_id)
            or (kind == "model" and cur_kind == "model"
                and page.get("model_id") == cur_vid.split(":", 1)[-1]))
        if is_active:
            page["active"] = True
        pages.append(page)
    if not pages:
        return None
    return {"pages": pages}


class ViewHost(QStackedWidget):

    viewChanged = Signal(object)
    viewsChanged = Signal()

    _inst = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsViewHost")
        self._views = []
        self._parked = {}
        self.currentChanged.connect(self._on_current_changed)
        ViewHost._inst = self

    @classmethod
    def instance(cls):
        return cls._inst

    def views(self):
        return list(self._views)

    def parked_view(self, view_id):
        return self._parked.get(str(view_id))

    def view(self, view_id):
        vid = str(view_id)
        for v in self._views:
            if v.view_id == vid:
                return v
        return None

    def current_view(self):
        w = self.currentWidget()
        return w if isinstance(w, object) and hasattr(w, "view_id") else None

    def count_views(self):
        return len(self._views)

    def add_view(self, view, activate=True):
        if view is None:
            return None
        try:
            if getattr(view, "_host", None) is None:
                view._host = self.window()
        except Exception:
            exc_note("add_view @ ggis/ui/views/view_host.py:212")
            pass
        old = self.view(view.view_id)
        if old is not None:
            if activate:
                self.ctx.svc("views").activate(view.view_id)
            return old
        parked = self._parked.pop(str(view.view_id), None)
        if parked is not None:
            try:
                if getattr(parked, "_host", None) is None:
                    parked._host = self.window()
            except Exception:
                exc_note("add_view @ ggis/ui/views/view_host.py:226")
                pass
            self._views.append(parked)
            self.addWidget(parked)
            self.viewsChanged.emit()
            if activate:
                self.ctx.svc("views").activate(parked.view_id)
            return parked
        self._views.append(view)
        self.addWidget(view)
        self.viewsChanged.emit()
        if activate:
            self.ctx.svc("views").activate(view.view_id)
        return view

    def activate(self, view_id):
        v = self.view(view_id)
        if v is None:
            return None
        idx = self.indexOf(v)
        if idx >= 0 and idx != self.currentIndex():
            self.setCurrentIndex(idx)
        else:
            self.viewChanged.emit(v)
        return v

    def close_view(self, view_id, force=False):
        v = self.view(view_id)
        if v is None or not getattr(v, "closable", True):
            return False
        # force=True：工程装载语义——无视"至少保留一个"约束且不 park
        #（装载后旧视图一律丢弃）；用户手动关闭保持约束与 park 语义。
        if len(self._views) <= 1 and not force:
            return False
        park = bool(getattr(v, "park_on_close", False)) and not force
        try:
            v.cleanup()
        except Exception:
            exc_note("close_view @ ggis/ui/views/view_host.py:284")
            pass
        i = self.indexOf(v)
        self._views.remove(v)
        self.removeWidget(v)
        if park:
            try:
                v.hide()
            except Exception:
                exc_note("close_view @ ggis/ui/views/view_host.py:292")
                pass
            v.setParent(None)
            self._parked[str(v.view_id)] = v
        else:
            v.setParent(None)
            try:
                v.deleteLater()
            except Exception:
                exc_note("close_view @ ggis/ui/views/view_host.py:300")
                pass
        if self._views:
            j = max(0, min(i, len(self._views) - 1))
            self.setCurrentIndex(j)
        self.viewsChanged.emit()
        cur = self.current_view()
        self.viewChanged.emit(cur if cur is not None else None)
        return True

    def reorder(self, ids):
        order = {}
        for k, vid in enumerate(list(ids or [])):
            order[str(vid)] = k
        try:
            self._views.sort(key=lambda v: order.get(v.view_id, 10 ** 6))
        except Exception:
            exc_note("reorder @ ggis/ui/views/view_host.py:325")
            return False
        try:
            cur = self.current_view()
            for v in self._views:
                self.removeWidget(v)
            for v in self._views:
                self.addWidget(v)
            if cur is not None:
                idx = self.indexOf(cur)
                if idx >= 0:
                    self.setCurrentIndex(idx)
        except Exception:
            exc_note("reorder @ ggis/ui/views/view_host.py:338")
            pass
        self.viewsChanged.emit()
        return True

    def close_others(self, keep_id):
        # 关闭统一走 views.close_view 门面（dock 注销/ribbon 注销/状态卸载），
        # 机制层只负责"留下谁"，清理动作不在此重复。
        keep = self.view(keep_id) or self.current_view()
        svc = self.ctx.svc("views")
        for v in list(self._views):
            if v is not keep and getattr(v, "closable", True):
                svc.close_view(v.view_id)
        if keep is not None:
            svc.activate(keep.view_id)

    def close_all(self):
        n = 0
        svc = self.ctx.svc("views")
        for v in list(self._views):
            if len(self._views) <= 1:
                break
            if getattr(v, "closable", True):
                try:
                    if svc.close_view(v.view_id):
                        n += 1
                except Exception:
                    exc_note("close_all @ ggis/ui/views/view_host.py:371")
                    pass
        return n

    def dispose_all(self):
        for v in list(self._views):
            try:
                v.cleanup()
            except Exception:
                exc_note("dispose_all @ ggis/ui/views/view_host.py:390")
                pass
            try:
                if v in self._views:
                    self._views.remove(v)
            except Exception:
                exc_note("dispose_all @ ggis/ui/views/view_host.py:395")
                pass
            try:
                self.removeWidget(v)
            except Exception:
                exc_note("dispose_all @ ggis/ui/views/view_host.py:399")
                pass
            try:
                v.setParent(None)
                v.deleteLater()
            except Exception:
                exc_note("dispose_all @ ggis/ui/views/view_host.py:404")
                pass
        for _pid in list(self._parked.keys()):
            _pv = self._parked.pop(_pid, None)
            if _pv is not None:
                try:
                    _pv.setParent(None)
                    _pv.deleteLater()
                except Exception:
                    exc_note("dispose_all @ ggis/ui/views/view_host.py:413")
                    pass
        self.viewsChanged.emit()

    def retain_for_project(self, keep_ids):
        keep = {str(k) for k in (keep_ids or [])}
        for v in list(self._views):
            if str(getattr(v, "view_id", "")) in keep:
                continue
            try:
                v.cleanup()
            except Exception:
                exc_note("retain_for_project @ ggis/ui/views/view_host.py:435")
                pass
            try:
                if v in self._views:
                    self._views.remove(v)
            except Exception:
                exc_note("retain_for_project @ ggis/ui/views/view_host.py:440")
                pass
            try:
                self.removeWidget(v)
            except Exception:
                exc_note("retain_for_project @ ggis/ui/views/view_host.py:444")
                pass
            try:
                v.setParent(None)
                v.deleteLater()
            except Exception:
                exc_note("retain_for_project @ ggis/ui/views/view_host.py:449")
                pass
        for _pid in list(self._parked.keys()):
            _pv = self._parked.pop(_pid, None)
            if _pv is not None:
                try:
                    _pv.setParent(None)
                    _pv.deleteLater()
                except Exception:
                    exc_note("retain_for_project @ ggis/ui/views/view_host.py:458")
                    pass
        self.viewsChanged.emit()

    def rename_view(self, view_id, title):
        v = self.view(view_id)
        if v is None:
            return ""
        new = v.rename(title)
        self.viewsChanged.emit()
        return new

    def _on_current_changed(self, _idx):
        w = self.currentWidget()
        for v in self._views:
            if v is not w:
                try:
                    v.view_deactivated()
                except Exception:
                    exc_note("_on_current_changed @ ggis/ui/views/view_host.py:477")
                    pass
        if w is not None and hasattr(w, "view_activated"):
            try:
                w.view_activated()
            except Exception:
                exc_note("_on_current_changed @ ggis/ui/views/view_host.py:482")
                pass
        self.viewChanged.emit(w if hasattr(w, "view_id") else None)
