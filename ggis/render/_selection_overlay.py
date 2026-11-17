# -*- coding: utf-8 -*-

from ggis.core.crs.extent import GgsRectangle
from PySide6.QtGui import QColor, QImage, QPainter

from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from ggis.common.util.exc_report import exc_note
from .renderers import default_renderer, get_renderer, set_renderer
from .painter import (GgsRasterPainter, GgsVectorPainter, invalidate_caches,
                      selection_symbol, vector_lod_tol)


class SelectionOverlayMixin:


    def selection(self):
        return self._sel

    def _draw_selection(self, painter, settings):
        sel = self.selection()
        for lyr in self._layer_source():
            if not lyr.is_visible() or not lyr.is_vector():
                continue
            if not self._in_scale(lyr, settings):
                continue
            fids = sel.fids(lyr)
            if not fids:
                continue
            sym = selection_symbol(lyr.base_kind(), get_renderer(lyr))
            tol = vector_lod_tol(settings, lyr.crs(),
                                  settings.destination_crs())
            self._vec_painter.draw_selection(
                painter, lyr, settings, fids, sym, None, tol)

    def refresh_selection(self):
        self._sel_img = None
        self._sel_key = None
        self._overlay_version = getattr(self, "_overlay_version", 0) + 1
        self.update()

    def _paint_tool_overlay(self):
        tool = getattr(self, "_tool", None)
        if tool is None or not hasattr(tool, "paint_overlay"):
            return
        self._overlay_version = getattr(self, "_overlay_version", 0) + 1
        try:
            s = self._map_settings()
            if not s.is_ready():
                return
            p = QPainter(self)
            try:
                if self._anti_alias:
                    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                self._draw_tool_overlay(p, s)
            finally:
                p.end()
        except Exception:
            exc_note("_paint_tool_overlay @ ggis/render/map_canvas.py:2404")
            pass

    def _selection_overlay(self, ext4, w, h, dpr):
        if ext4 is None or w <= 0 or h <= 0:
            return None
        sel_total = self._sel.total()
        if sel_total <= 0:
            return None
        key = (tuple(round(float(v), 9) for v in ext4),
               int(w), int(h), round(float(dpr), 4))
        img = self._sel_img
        if img is not None and self._sel_key == key and not img.isNull():
            return img
        img = QImage(max(1, int(round(w * dpr))),
                     max(1, int(round(h * dpr))),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)
        p = QPainter(img)
        try:
            if self._anti_alias:
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._draw_selection(
                p, self._settings_for_extent(ext4, out=(w, h)))
        finally:
            p.end()
        self._sel_img = img
        self._sel_key = key
        return img

    def _paint_selection_overlay(self):
        dpr = self._eff_dpr()
        w, h = self.width(), self.height()
        fe, cur = self._frozen_fe, self._extent_snapshot()

        def _t4(r):
            if r is None:
                return None
            return (float(r.xmin), float(r.ymin),
                    float(r.xmax), float(r.ymax))

        def _lsize(img):
            d = float(img.devicePixelRatio() or 1.0) or 1.0
            return (int(round(img.width() / d)),
                    int(round(img.height() / d)))

        fz = self._frozen
        fw, fh = _lsize(fz)

        if fe is None or fz is None or fz.isNull():
            img = self._selection_overlay(_t4(cur), w, h, dpr)
            if img is not None:
                self._blit(img)
            return

        def _overlay_for(t4, iw, ih):
            if t4 is None or iw <= 0 or ih <= 0:
                return None, None
            key = (tuple(round(float(v), 9) for v in t4),
                   int(iw), int(ih), round(float(dpr), 4))
            img = self._sel_img
            if (key is not None and img is not None
                    and self._sel_key == key and not img.isNull()):
                return img, fe
            if (img is not None and not img.isNull()
                    and self._sel_key is not None):
                old = self._sel_key[0]
                fe_old = GgsRectangle(float(old[0]), float(old[1]),
                                      float(old[2]), float(old[3]))
                self._schedule_sel_rebuild()
                return img, fe_old
            return self._selection_overlay(t4, iw, ih, dpr), fe

        if self._panning:
            img, fe2 = _overlay_for(_t4(fe), fw, fh)
            if img is None:
                return
            out = self._make_scaled(img, fe2, self._extent, transparent=True)
            if out is not None:
                self._blit(out)
            return

        same = (cur is not None and bool(fe == cur))
        if same:
            img, fe2 = _overlay_for(_t4(fe), fw, fh)
            if img is None:
                return
            if fe2 == cur and _lsize(img) == (fw, fh):
                self._blit(img)
                return
            out = self._make_scaled(img, fe2, cur, transparent=True)
            if out is not None:
                self._blit(out)
            return

        img, fe2 = _overlay_for(_t4(fe), fw, fh)
        if img is None:
            return
        out = self._make_scaled(img, fe2, cur, transparent=True)
        if out is not None:
            self._blit(out)

    def _schedule_sel_rebuild(self):
        if getattr(self, "_sel_rebuild_pending", False):
            return
        self._sel_rebuild_pending = True

        def _do():
            self._sel_rebuild_pending = False
            dpr = self._eff_dpr()
            fe = self._frozen_fe
            fz = self._frozen
            iw = ih = 0
            if fz is not None and not fz.isNull():
                d = float(fz.devicePixelRatio() or 1.0) or 1.0
                iw = max(1, int(round(fz.width() / d)))
                ih = max(1, int(round(fz.height() / d)))
            t4 = None
            if fe is not None:
                t4 = (float(fe.xmin), float(fe.ymin),
                      float(fe.xmax), float(fe.ymax))
            has_sel = self._sel.total() > 0
            if t4 is not None and iw > 0 and ih > 0 and has_sel:
                self._selection_overlay(t4, iw, ih, dpr)
                self.update()

        QTimer.singleShot(0, _do)

    def _paint_gpu_error_overlay(self, reason):
        try:
            from PySide6.QtGui import QColor, QPainter, QFont
            from PySide6.QtCore import Qt
            p = QPainter(self)
            try:
                p.fillRect(self.rect(), QColor(40, 40, 44))
                p.setPen(QColor(225, 225, 225))
                _f = QFont()
                _f.setPointSize(11)
                p.setFont(_f)
                _txt = ("GPU 渲染后端不可用\n\n"
                        + str(reason)
                        + "\n\n恢复方式：\n"
                        "• 修复显卡驱动 / OpenGL 后重启程序。")
                p.drawText(self.rect(),
                           Qt.AlignmentFlag.AlignCenter
                           | Qt.TextFlag.TextWordWrap, _txt)
            finally:
                p.end()
        except Exception:
            exc_note("_paint_gpu_error_overlay @ ggis/render/map_canvas.py:2585")
            pass

    def _draw_tool_overlay(self, painter, settings):
        tool = self._tool
        if tool is None:
            return
        fn = getattr(tool, "paint_overlay", None)
        if fn is None:
            return
        try:
            fn(painter, settings)
        except Exception:
            exc_note("_draw_tool_overlay @ ggis/render/map_canvas.py:5850")
            pass

    def _draw_empty_hint(self, p, rect=None):
        return
