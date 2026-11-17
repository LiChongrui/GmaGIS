# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import logging
import time

from PySide6.QtCore import QObject, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsItem

_log = logging.getLogger("gmagis")

__all__ = ["MapFrameNav", "MapNavLayer", "frame_dest_rect", "expand_ext",
           "NAV_PAD", "NAV_MAX_PX", "NAV_KICK_MS"]

NAV_PAD = 0.18
NAV_MAX_PX = 1400
NAV_KICK_MS = 60


def frame_dest_rect(fe, cu, box):
    cw = float(cu.width())
    ch = float(cu.height())
    if cw <= 1e-12 or ch <= 1e-12:
        return None
    x0 = (float(fe.xmin) - float(cu.xmin)) / cw * box.width()
    x1 = (float(fe.xmax) - float(cu.xmin)) / cw * box.width()
    y0 = (float(cu.ymax) - float(fe.ymax)) / ch * box.height()
    y1 = (float(cu.ymax) - float(fe.ymin)) / ch * box.height()
    return QRectF(box.x() + x0, box.y() + y0, x1 - x0, y1 - y0)


def expand_ext(ext, pad):
    from ggis.core.crs.extent import GgsRectangle
    dx = float(ext.width()) * float(pad)
    dy = float(ext.height()) * float(pad)
    return GgsRectangle(float(ext.xmin) - dx, float(ext.ymin) - dy,
                        float(ext.xmax) + dx, float(ext.ymax) + dy)


class MapNavLayer(QGraphicsItem):

    def __init__(self, rect_mm, bg="#FFFFFF"):
        super().__init__()
        self._box = QRectF(rect_mm)
        self._bg = QColor(str(bg or "#FFFFFF"))
        if not self._bg.isValid():
            self._bg = QColor("#FFFFFF")
        self._frame = None
        self._fext = None
        self._cur = None
        self.setZValue(3000)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)

    def set_box(self, rect_mm):
        self.prepareGeometryChange()
        self._box = QRectF(rect_mm)
        self.update()

    def set_state(self, frame=None, fext=None, cur=None):
        if frame is not None:
            self._frame = frame
        if fext is not None:
            self._fext = fext
        if cur is not None:
            self._cur = cur
        self.update()

    def has_frame(self):
        return self._frame is not None and self._fext is not None

    def frame_size(self):
        f = self._frame
        return (0, 0) if f is None else (f.width(), f.height())

    def boundingRect(self):
        return QRectF(self._box)

    def paint(self, painter, option, widget=None):
        box = self._box
        if box.width() <= 0.0 or box.height() <= 0.0:
            return
        painter.fillRect(box, self._bg)
        f = self._frame
        fe = self._fext
        cu = self._cur
        if f is None or fe is None or cu is None or f.isNull():
            return
        dst = frame_dest_rect(fe, cu, box)
        if dst is None or dst.isEmpty():
            return
        inter = dst.intersected(box)
        if inter.isEmpty():
            return
        sx = float(f.width()) / max(1e-9, float(dst.width()))
        sy = float(f.height()) / max(1e-9, float(dst.height()))
        src = QRectF((inter.x() - dst.x()) * sx, (inter.y() - dst.y()) * sy,
                     inter.width() * sx, inter.height() * sy)
        painter.save()
        painter.setClipRect(box)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(inter, f, src)
        painter.restore()


class MapFrameNav(QObject):

    def __init__(self, view):
        super().__init__(view)
        self._v = view
        self.item = None
        self.layer = None
        self.cur = None
        self._frame = None
        self._fext = None
        self._seq = 0
        self._newest = -1
        self._inflight = {}
        self._kick_ms = 0.0
        self._wired = False
        self.n_kick = 0
        self.n_frame = 0
        self.n_drop = 0

    def begin(self, item):
        self.item = item
        self._frame = None
        self._fext = None
        self._seq = 0
        self._newest = -1
        self._inflight = {}
        self._kick_ms = 0.0
        self._wire()
        try:
            self.cur = self._v._nav_base_extent(item)
        except Exception:
            exc_note("begin @ ggis/ui/views/layout/mapframe_nav.py:241")
            self.cur = None
        return self.cur is not None

    def active(self):
        return self.item is not None and self.layer is not None

    def has_frame(self):
        return self._frame is not None and self._fext is not None

    def drop_layer(self):
        lay = self.layer
        self.layer = None
        if lay is None:
            return
        try:
            sc = self._v.layout_scene()
            if sc is not None:
                sc.removeItem(lay)
        except Exception:
            exc_note("drop_layer @ ggis/ui/views/layout/mapframe_nav.py:273")
            pass
        QTimer.singleShot(0, lambda _k=lay: None)

    def can_drop(self):
        if self.item is None or self.layer is None:
            return True
        fe = self._fext
        cu = self.cur
        if fe is None or cu is None:
            return True
        try:
            def _same(a, b):
                w = max(1.0, abs(float(a.width())))
                h = max(1.0, abs(float(a.height())))
                return (abs(float(a.xmin) - float(b.xmin)) / w < 1e-6
                        and abs(float(a.ymin) - float(b.ymin)) / h < 1e-6
                        and abs(float(a.xmax) - float(b.xmax)) / w < 1e-6
                        and abs(float(a.ymax) - float(b.ymax)) / h < 1e-6)

            return bool(_same(cu, fe) or _same(expand_ext(cu, NAV_PAD), fe))
        except Exception:
            exc_note("can_drop @ ggis/ui/views/layout/mapframe_nav.py:308")
            return True

    def close(self):
        self._seq += 1
        self._inflight = {}
        self.item = None
        self.cur = None
        self._frame = None
        self._fext = None
        self.drop_layer()

    def end(self):
        self._kick_ms = 0.0
        if self.layer is not None:
            self.layer.set_state(None, None, self.cur)

    def stats(self):
        return {"kick": self.n_kick, "frame": self.n_frame, "drop": self.n_drop,
                "state": "active" if self.active() else "idle"}

    def pan(self, dx_mm, dy_mm):
        ext = self.cur
        if ext is None or self.item is None:
            return False
        try:
            from ggis.core.crs.extent import GgsRectangle
            w_mm = max(1e-6, float(self.item.rect_mm.width()))
            h_mm = max(1e-6, float(self.item.rect_mm.height()))
            ux = float(ext.width()) / w_mm
            uy = float(ext.height()) / h_mm
            new = GgsRectangle(float(ext.xmin) + float(dx_mm) * ux,
                              float(ext.ymin) + float(dy_mm) * uy,
                              float(ext.xmax) + float(dx_mm) * ux,
                              float(ext.ymax) + float(dy_mm) * uy)
        except Exception:
            _log.exception("布局：地图框平移失败")
            return False
        self._set_cur(new)
        return True

    def zoom(self, factor, anchor_rel):
        ext = self.cur
        if ext is None or self.item is None:
            return False
        try:
            from ggis.core.crs.extent import GgsRectangle
            ax, ay = float(anchor_rel[0]), float(anchor_rel[1])
            ax = min(1.0, max(0.0, ax))
            ay = min(1.0, max(0.0, ay))
            cx = float(ext.xmin) + ax * float(ext.width())
            cy = float(ext.ymax) - ay * float(ext.height())
            new = GgsRectangle(cx - (cx - float(ext.xmin)) * factor,
                              cy - (cy - float(ext.ymin)) * factor,
                              cx + (float(ext.xmax) - cx) * factor,
                              cy + (float(ext.ymax) - cy) * factor)
        except Exception:
            _log.exception("布局：地图框缩放失败")
            return False
        self._set_cur(new)
        return True

    def _set_cur(self, new):
        self.cur = new
        try:
            self._v._nav_write_extent(self.item, new)
        except Exception:
            exc_note("_set_cur @ ggis/ui/views/layout/mapframe_nav.py:393")
            pass
        self._ensure_layer()
        if self.layer is not None:
            self.layer.set_state(None, None, new)
        self.kick()

    def _ensure_layer(self):
        if self.layer is not None:
            return self.layer
        it = self.item
        if it is None:
            return None
        try:
            sc = self._v.layout_scene()
            if sc is None:
                return None
            lay = MapNavLayer(it.rect_mm, getattr(it, "background", "#FFFFFF"))
            if self._frame is None:
                try:
                    snap = self._v._backdrop_slice(QRectF(it.rect_mm))
                except Exception:
                    exc_note("_ensure_layer @ ggis/ui/views/layout/mapframe_nav.py:420")
                    snap = None
                if snap is not None and not snap.isNull():
                    self._frame = snap.toImage()
                    self._fext = self.cur
            lay.set_state(self._frame, self._fext, self.cur)
            sc.addItem(lay)
            self.layer = lay
            return lay
        except Exception:
            _log.exception("布局：地图框帧层创建失败")
            return None

    def _wire(self):
        if self._wired:
            return
        try:
            sc = self._v.layout_scene()
            rend = sc._map_renderer() if sc is not None else None
            if rend is None:
                return
            rend.rendered.connect(self._on_rendered)
            self._wired = True
        except Exception:
            _log.exception("布局：导航帧信号连接失败")

    def kick(self, force=False):
        it = self.item
        v = self._v
        sc = v.layout_scene()
        if it is None or sc is None or sc.layout is None or self.cur is None:
            return False
        now = time.monotonic() * 1000.0
        if not force and (now - float(self._kick_ms or 0.0)) < float(NAV_KICK_MS):
            return False
        rend = sc._map_renderer()
        if rend is None:
            return False
        r = QRectF(it.rect_mm)
        if r.width() < 1.0 or r.height() < 1.0:
            return False
        try:
            req_ext = expand_ext(self.cur, NAV_PAD)
        except Exception:
            exc_note("kick @ ggis/ui/views/layout/mapframe_nav.py:472")
            req_ext = self.cur
        try:
            k = max(1e-6, float(v.transform().m11()))
        except Exception:
            exc_note("kick @ ggis/ui/views/layout/mapframe_nav.py:477")
            k = 1.0
        w_px = int(max(240.0, min(float(NAV_MAX_PX),
                                  r.width() * k * (1.0 + 2.0 * float(NAV_PAD)))))
        h_px = int(max(180.0, round(w_px * r.height() / r.width())))
        dpi = w_px / max(1e-6, float(r.width())) * 25.4
        self._seq += 1
        seq = self._seq
        self._kick_ms = now
        self._inflight[seq] = req_ext
        self.n_kick += 1
        try:
            rend.invalidate()
        except Exception:
            exc_note("kick @ ggis/ui/views/layout/mapframe_nav.py:493")
            pass
        try:
            try:
                _crs = it.crs(sc.project)
            except Exception:
                exc_note("kick @ ggis/ui/views/layout/mapframe_nav.py:503")
                _crs = None
            ok = bool(rend.request(it, ("__nav__", seq), sc.project, req_ext,
                                   w_px, h_px, dpi,
                                   getattr(it, "background", "#FFFFFF"),
                                   crs=_crs))
        except Exception:
            _log.exception("布局：导航帧投递失败")
            ok = False
        if not ok:
            self._inflight.pop(seq, None)
        return ok

    def _on_rendered(self, img, seq, mf, key):
        try:
            if not (isinstance(key, tuple) and key and key[0] == "__nav__"):
                return
            if mf is not self.item:
                return
            nav_seq = int(key[1])
        except Exception:
            exc_note("_on_rendered @ ggis/ui/views/layout/mapframe_nav.py:532")
            return
        self.on_frame(img, nav_seq)

    def on_frame(self, img, seq):
        ext = self._inflight.pop(int(seq), None)
        if img is None or img.isNull() or ext is None:
            self.n_drop += 1
            return False
        if int(seq) < int(self._newest):
            self.n_drop += 1
            return False
        self._newest = int(seq)
        self._frame = img
        self._fext = ext
        self.n_frame += 1
        lay = self.layer
        if lay is not None:
            lay.set_state(img, ext, self.cur)
        return True
