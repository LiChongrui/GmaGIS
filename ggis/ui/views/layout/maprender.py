# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging

from PySide6.QtCore import QObject, Signal

from ggis.core.crs import crs_key
from ggis.core.app import settings

_log = logging.getLogger("gmagis")

__all__ = ["MapFrameRenderer"]


class MapFrameRenderer(QObject):

    rendered = Signal(object, int, object, object)

    def __init__(self, parent=None, blocked=None):
        super().__init__(parent)
        self._blocked = blocked
        self._c = None
        self._failed = False
        self._ver = -1
        self._seq = 0
        self._inflight = None
        self._queue = []
        self.last_error = ""
        self._warned = set()
        self.n_req = 0
        self.n_done = 0
        self.n_notwarm = 0
        self.n_blocked = 0
        self.n_noplay = 0
        self.n_queued = 0

    def _warn_once(self, key, msg):
        if key in self._warned:
            return
        self._warned.add(key)
        _log.info(msg)

    def is_available(self):
        c = self._c
        if c is None or self._failed:
            return False
        try:
            return bool(c.is_available())
        except Exception:
            exc_note("is_available @ ggis/ui/views/layout/maprender.py:121")
            return False

    def is_warm(self):
        c = self._c
        if c is None or self._failed:
            return False
        try:
            return bool(c.is_warm())
        except Exception:
            exc_note("is_warm @ ggis/ui/views/layout/maprender.py:131")
            return False

    def is_busy(self):
        return self._inflight is not None or bool(self._queue)

    def start(self, project):
        if self._failed:
            return False
        if self._c is None:
            try:
                from ggis.render.cpu.render_proc import RenderClient
                c = RenderClient(self)
                c.rendered.connect(self._on_frame)
                self._c = c
            except Exception:
                _log.exception("布局：地图框子进程渲染器创建失败（回退主进程渲染）")
                self._failed = True
                return False
        try:
            if not self._c.start():
                self.last_error = str(getattr(self._c, "last_error", "") or "")
                return False
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            _log.exception("布局：地图框子进程启动失败（回退主进程渲染）")
            self._failed = True
            return False
        return self._sync_scene(project)

    def stop(self, wait_ms=4000):
        self._queue = []
        self._inflight = None
        c = self._c
        self._c = None
        if c is None:
            return
        try:
            c.stop()
        except Exception:
            exc_note("stop @ ggis/ui/views/layout/maprender.py:173")
            pass
        del wait_ms

    def invalidate(self):
        self._queue = []

    def _sync_scene(self, project):
        c = self._c
        if c is None or project is None:
            return False
        try:
            from ggis.render.cpu.render_proc import scene_specs, scene_version
            specs = scene_specs(project)
            if specs is None:
                _log.info("布局：地图框不适用子进程渲染（场景规格判不出来）")
                self._failed = True
                return False
            for _sp in specs:
                if str((_sp or {}).get("type") or "") == "tile":
                    _log.info("布局：地图框含在线瓦片层 ⇒ 回退主进程渲染")
                    self._failed = True
                    return False
            ver = int(scene_version(project))
            if ver != self._ver:
                self._ver = ver
                c.set_scene(ver, specs, crs_key(settings.default_crs()))
                c.push_scene()
            return True
        except Exception:
            _log.exception("布局：地图框场景同步失败（回退主进程渲染）")
            self._failed = True
            return False

    def request(self, mf, key, project, extent, w_px, h_px, dpi,
                background="#FFFFFF", crs=None):
        if mf is None or key is None or project is None or extent is None:
            return False
        try:
            if extent.is_empty():
                return False
        except Exception:
            exc_note("request @ ggis/ui/views/layout/maprender.py:245")
            return False
        if self._blocked is not None:
            try:
                if bool(self._blocked()):
                    self.n_blocked += 1
                    self._warn_once(
                        "blocked",
                        "布局：检测到**未保存的要素编辑** ⇒ 地图框暂由主进程渲染"
                        "（保存 / 放弃编辑后会自动切回子进程）")
                    return False
            except Exception:
                exc_note("request @ ggis/ui/views/layout/maprender.py:259")
                pass
        if not self.start(project):
            self.n_noplay += 1
            self._warn_once("noplay",
                            "布局：地图框渲染子进程不可用 ⇒ 由主进程渲染（%s）"
                            % (self.last_error or "未知原因"))
            return False
        if not self.is_warm():
            self.n_notwarm += 1
            self._warn_once(
                "notwarm",
                "布局：地图框渲染子进程还在预热（读盘 / 建缓存）⇒ 本轮由主进程"
                "渲染，稍后自动切到子进程")
            return False
        self._seq += 1
        task = self._build_task(self._seq, extent, w_px, h_px, dpi, background,
                                crs=crs)
        if task is None:
            return False
        item = (mf, key, task)
        if self._inflight is not None:
            if self._inflight[1] == key:
                return False
            self._queue = [q for q in self._queue if q[1] != key]
            self._queue.append(item)
            self.n_queued += 1
            return True
        return self._send(item)

    def _build_task(self, seq, extent, w_px, h_px, dpi, background,
                    crs=None):
        try:
            x0, y0, x1, y1 = (float(extent.xmin), float(extent.ymin),
                              float(extent.xmax), float(extent.ymax))
            q = _qcolor(background)
            task = {
                "seq": int(seq),
                "extent": (x0, y0, x1, y1),
                "size": (max(1, int(w_px)), max(1, int(h_px))),
                "dpr": 1.0,
                "color": (q.red(), q.green(), q.blue()),
                "aa": True,
                "dpi": float(dpi or 96.0),
                "lod_ref_width": 0,
                "labels": False,
                "labels_enabled": False,
                "selection": False,
                "overlay": False,
                "raster_budget_ms": None,
            }
            try:
                k = str(crs_key(crs) or "")
            except Exception:
                exc_note("_build_task @ ggis/ui/views/layout/maprender.py:325")
                k = ""
            if k:
                task["crs"] = k
            return task
        except Exception:
            _log.exception("布局：地图框渲染任务构造失败")
            return None

    def _send(self, item):
        c = self._c
        if c is None:
            return False
        self._inflight = item
        try:
            ok = bool(c.request(int(item[2]["seq"]), item[2]))
        except Exception:
            _log.exception("布局：地图框渲染请求投递失败")
            self._inflight = None
            return False
        if not ok:
            self._inflight = None
        else:
            self.n_req += 1
        return ok

    def _pump(self):
        if self._inflight is not None or not self._queue:
            return
        while self._queue:
            item = self._queue.pop(0)
            if self._send(item):
                return

    def _on_frame(self, img, seq, final=False):
        item = self._inflight
        if item is None:
            return
        if int(seq) != int(item[2].get("seq", -1)):
            return
        if img is None or img.isNull():
            return
        if not final:
            return
        self._inflight = None
        self.n_done += 1
        try:
            self.rendered.emit(img, int(seq), item[0], item[1])
        except Exception:
            _log.exception("布局：地图框渲染结果派发失败")
        self._pump()


def _qcolor(spec):
    from PySide6.QtGui import QColor
    try:
        c = QColor(str(spec or "#FFFFFF"))
        if c.isValid():
            return c
    except Exception:
        exc_note("_qcolor @ ggis/ui/views/layout/maprender.py:390")
        pass
    return QColor("#FFFFFF")
