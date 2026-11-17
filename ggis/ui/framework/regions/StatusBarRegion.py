from ggis.common.util.exc_report import exc_note

import logging

from ggis.core.app import i18n

_log = logging.getLogger("gmagis")
_tr = i18n.tr


class GgsStatusBarRegion:

    def __init__(self, mw):
        self.mw = mw

    def build(self):
        self.mw._build_statusbar()

    def _mount_view_status(self, view):
        if view is None:
            return
        try:
            from ggis.ui.framework.statusbar import ensure_status_controls
            ensure_status_controls(view)
        except Exception:
            exc_note("_mount_view_status @ ggis/ui/framework/regions/StatusBarRegion.py:64")
            pass
        sb = self.mw.statusBar()
        if sb is None:
            return
        _ws = list(getattr(view, "_status_widgets", []) or [])
        for i, w in enumerate(_ws):
            if w is None:
                continue
            try:
                _left = list(getattr(sb, "_left_children", []) or [])
                _right = list(getattr(sb, "_right_children", []) or [])
                if w not in _left and w not in _right:
                    if i == 0:
                        sb.addWidget(w)
                    else:
                        sb.addPermanentWidget(w)
                if bool(w.property("ggs_autohide")):
                    w.setVisible(bool(getattr(view, "_loading", False)))
                else:
                    w.setVisible(True)
                if hasattr(w, "set_suppressed"):
                    w.set_suppressed(False)
            except Exception:
                exc_note("_mount_view_status @ ggis/ui/framework/regions/StatusBarRegion.py:104")
                pass
        try:
            self.mw._update_crs_label()
        except Exception:
            exc_note("_mount_view_status @ ggis/ui/framework/regions/StatusBarRegion.py:112")
            pass
        try:
            cv = self.mw.canvas
            if cv is not None:
                self.mw._on_scale_changed(cv.scale())
        except Exception:
            exc_note("_mount_view_status @ ggis/ui/framework/regions/StatusBarRegion.py:118")
            pass
        self.mw._mounted_status_view = view
        try:
            self._sync_status_to_view(view)
        except Exception:
            exc_note("_mount_view_status @ ggis/ui/framework/regions/StatusBarRegion.py:125")
            pass

    def _unmount_view_status(self, view):
        if view is None:
            return
        if getattr(self.mw, "_mounted_status_view", None) is not view:
            return
        for w in list(getattr(view, "_status_widgets", []) or []):
            if w is None:
                continue
            try:
                w.setVisible(False)
                if hasattr(w, "set_suppressed"):
                    w.set_suppressed(True)
            except Exception:
                exc_note("_unmount_view_status @ ggis/ui/framework/regions/StatusBarRegion.py:149")
                pass
        self.mw._mounted_status_view = None

    def _sync_status_to_view(self, view):
        if view is None:
            return
        lbl = getattr(view, "lbl_render", None)
        if lbl is not None:
            try:
                if getattr(view, "_render_busy", False):
                    lbl.set_busy(_tr("渲染中"))
                elif str(lbl.state()) == "busy":
                    lbl.set_done()
            except Exception:
                exc_note("_sync_status_to_view @ ggis/ui/framework/regions/StatusBarRegion.py:173")
                pass
        p = getattr(view, "progress", None)
        if p is not None:
            try:
                vis = bool(getattr(view, "_loading", False))
                if not vis:
                    p.setValue(0)
                p.setVisible(vis)
            except Exception:
                exc_note("_sync_status_to_view @ ggis/ui/framework/regions/StatusBarRegion.py:183")
                pass
        try:
            _acts = getattr(getattr(self.mw, "_status_ctrl", None),
                            "coord_fmt_actions", None) or {}
            _fmt = getattr(view, "_coord_fmt", "map") or "map"
            for _d, _a in _acts.items():
                _a.setChecked(_d == _fmt)
        except Exception:
            exc_note("_sync_status_to_view @ ggis/ui/framework/regions/StatusBarRegion.py:192")
            pass
        lock = getattr(view, "btn_scale_lock", None)
        cv = getattr(view, "canvas", None)
        if lock is not None and cv is not None:
            try:
                on = bool(cv.isScaleLocked())
                _blocked = lock.blockSignals(True)
                try:
                    lock.setChecked(on)
                finally:
                    lock.blockSignals(_blocked)
                self.mw._update_scale_lock_icon(on)
            except Exception:
                exc_note("_sync_status_to_view @ ggis/ui/framework/regions/StatusBarRegion.py:207")
                pass
        try:
            cl = getattr(view, "coords_label", None)
            if cl is not None:
                xy = getattr(view, "_last_xy", None)
                cl.setText(self.mw._format_coord(xy[0], xy[1]) if xy
                           else "—, —")
        except Exception:
            exc_note("_sync_status_to_view @ ggis/ui/framework/regions/StatusBarRegion.py:216")
            pass

    def _sync_status_for_view(self, kind, view=None):
        _g = self.mw._control_group_of(view) if view is not None else None
        _sk = (_g.status_kind if _g is not None else None) or kind
        is_map = (_sk == "map")
        if is_map and view is not None:
            self._mount_view_status(view)
            try:
                _rs = getattr(view, "lbl_render", None)
                if _rs is not None and hasattr(_rs, "set_clickable"):
                    _rs.set_clickable(bool(view.has_layers()))
            except Exception:
                exc_note("_sync_status_for_view @ ggis/ui/framework/regions/StatusBarRegion.py:252")
                pass
        else:
            self._unmount_view_status(
                getattr(self.mw, "_mounted_status_view", None))
        ws = getattr(view, "workspace", None) if view is not None else None
        try:
            self.mw.attach_view_status(kind, ws)
        except Exception:
            exc_note("_sync_status_for_view @ ggis/ui/framework/regions/StatusBarRegion.py:265")
            pass
