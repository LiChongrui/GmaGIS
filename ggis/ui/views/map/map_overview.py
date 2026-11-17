# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt, QSize, QRectF, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy
from ggis.common.styling import themes as _themes
from ggis.common.util.exc_report import exc_note
from ggis.common.widgets.colors import _is_dark_color
from ggis.core.app import settings as _settings
from ggis.render.renderers import render_version as _render_version
from ggis.core.app import i18n as _i18n
_tr = _i18n.tr


class GgsMapOverviewCanvas(QWidget):

    def __init__(self, parent=None, canvas=None):
        super().__init__(parent)
        self.setObjectName("GgsMapOverviewCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumSize(120, 90)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._canvas = canvas
        _uc = QColor(str(_settings.get("canvas_color") or "").strip())
        self._bg = (_uc if _uc.isValid()
                    else QColor(_themes.canvas_color(_settings.get("theme"))))
        self._on = False
        self._img = None
        self._img_key = None
        self._dragging = False
        self._rev = 0
        self._ov_ext = None
        self._ov_ext_key = None
        self._loading = False
        self._hook_canvas()

    def _hook_canvas(self):
        c = self._canvas
        if c is None:
            return
        if getattr(self, "_hooked", None) is c:
            return
        try:
            c.extentChanged.connect(self._on_ext_changed)
        except Exception:
            exc_note("_hook_canvas @ ggis/common/widgets/standard.py:237")
            pass
        try:
            c.crsChanged.connect(self._on_scene_changed)
        except Exception:
            exc_note("_hook_canvas @ ggis/common/widgets/standard.py:246")
            pass
        try:
            proj = c.project()
        except Exception:
            exc_note("_hook_canvas @ ggis/common/widgets/standard.py:250")
            proj = None
        if proj is None:
            self._hooked = c
            return
        for name in ("layersChanged", "layerAdded", "layerRemoved",
                     "layerVisibilityChanged", "layerOrderChanged"):
            sig = getattr(proj, name, None)
            if sig is None:
                continue
            try:
                sig.connect(self._on_scene_changed)
            except Exception:
                exc_note("_hook_canvas @ ggis/common/widgets/standard.py:262")
                pass
        self._hooked = c

    def _unhook_canvas(self):
        c = getattr(self, "_hooked", None)
        self._hooked = None
        if c is None:
            return
        try:
            c.extentChanged.disconnect(self._on_ext_changed)
        except Exception:
            exc_note("_unhook_canvas @ ggis/common/widgets/standard.py:275")
            pass
        try:
            c.crsChanged.disconnect(self._on_scene_changed)
        except Exception:
            exc_note("_unhook_canvas @ ggis/common/widgets/standard.py:279")
            pass
        try:
            proj = c.project()
        except Exception:
            exc_note("_unhook_canvas @ ggis/common/widgets/standard.py:283")
            proj = None
        if proj is None:
            return
        for name in ("layersChanged", "layerAdded", "layerRemoved",
                     "layerVisibilityChanged", "layerOrderChanged"):
            sig = getattr(proj, name, None)
            if sig is None:
                continue
            try:
                sig.disconnect(self._on_scene_changed)
            except Exception:
                exc_note("_unhook_canvas @ ggis/common/widgets/standard.py:294")
                pass

    def _on_ext_changed(self, *_a):
        self.update()

    def _on_scene_changed(self, *_a):
        self._rev += 1
        self.update()

    def refresh(self):
        self._img = None
        self._img_key = None
        self._ov_ext = None
        self.update()

    def setBackgroundColor(self, color):
        try:
            self._bg = QColor(color)
            self._img = None
            self._img_key = None
            self.update()
        except Exception:
            exc_note("setBackgroundColor @ ggis/common/widgets/standard.py:323")
            pass

    def set_canvas(self, canvas):
        if canvas is self._canvas:
            return
        self._unhook_canvas()
        self._canvas = canvas
        self._img = None
        self._img_key = None
        self._ov_ext = None
        self._ov_ext_key = None
        self._hook_canvas()
        self.update()

    def enable(self, on):
        self._on = bool(on)
        self.update()

    def enabled(self):
        return self._on

    def _crs_authid(self):
        c = self._canvas
        if c is None:
            return ""
        try:
            crs = c.destinationCrs()
        except Exception:
            exc_note("_crs_authid @ ggis/common/widgets/standard.py:372")
            return ""
        if crs is None:
            return ""
        try:
            if hasattr(crs, "is_valid") and not crs.is_valid():
                return ""
            if hasattr(crs, "authid"):
                return str(crs.authid())
            return str(crs)
        except Exception:
            exc_note("_crs_authid @ ggis/common/widgets/standard.py:382")
            return ""

    def _scene_key(self):
        c = self._canvas
        if c is None:
            return None
        sig = []
        try:
            for lyr in c.project().layers():
                sig.append((lyr.id(), bool(lyr.is_visible()),
                            _render_version(lyr)))
        except Exception:
            exc_note("_scene_key @ ggis/common/widgets/standard.py:404")
            pass
        return (self.width(), self.height(),
                float(self.devicePixelRatioF() or 1.0),
                self._rev, self._crs_authid(), tuple(sig))

    def _overview_extent(self):
        c = self._canvas
        if c is None:
            return None
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return None
        key = (w, h, self._rev, id(c), self._crs_authid())
        if self._ov_ext is not None and self._ov_ext_key == key \
                and not self._ov_ext.is_empty():
            return self._ov_ext
        try:
            r = c.fullExtent()
        except Exception:
            exc_note("_overview_extent @ ggis/common/widgets/standard.py:432")
            return None
        if r is None or r.is_empty():
            self._ov_ext = None
            self._ov_ext_key = key
            return None
        r = r.copy()
        r.expand_to_ratio(w / float(h))
        if r.is_empty() or r.width() <= 0 or r.height() <= 0:
            self._ov_ext = None
            self._ov_ext_key = key
            return None
        self._ov_ext = r
        self._ov_ext_key = key
        return r

    def _ensure_image(self, ext):
        key = self._scene_key()
        if (self._img is not None and key is not None
                and self._img_key == key and not self._img.isNull()):
            return self._img
        return None

    def _schedule_thumbnail(self):
        if self._loading:
            return
        key = self._scene_key()
        if key is None:
            return
        if (self._img is None and self._img_key is not None
                and self._img_key == key):
            return
        self._loading = True
        try:
            QTimer.singleShot(0, self._render_thumbnail)
        except Exception:
            exc_note("_schedule_thumbnail @ ggis/common/widgets/standard.py:491")
            self._loading = False

    def _render_thumbnail(self):
        try:
            ext = self._overview_extent()
        except Exception:
            exc_note("_render_thumbnail @ ggis/common/widgets/standard.py:505")
            ext = None
        if ext is None:
            self._img = None
            self._img_key = None
            self._loading = False
            self.update()
            return
        key = self._scene_key()
        img = None
        try:
            dpr = float(self.devicePixelRatioF() or 1.0) or 1.0
            img = self._canvas.render_to_image(
                max(1, int(round(self.width() * dpr))),
                max(1, int(round(self.height() * dpr))),
                with_labels=False,
                with_selection=False,
                with_overlay=False,
                extent=ext)
            if img is not None:
                img.setDevicePixelRatio(dpr)
        except Exception:
            exc_note("_render_thumbnail @ ggis/common/widgets/standard.py:532")
            img = None
        self._img = img
        self._img_key = key
        self._loading = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            if not self._on:
                self._paint_hint(p, _tr("鹰眼图已关闭"))
                return
            p.fillRect(self.rect(), self._bg)
            ext = self._overview_extent()
            if ext is None:
                self._paint_hint(p, _tr("暂无图层，无法生成鹰眼图"))
                return
            img = self._ensure_image(ext)
            if img is not None:
                p.drawImage(0, 0, img)
                self._paint_viewport(p, ext)
                return
            self._paint_loading(p)
            self._schedule_thumbnail()
        except Exception:
            exc_note("paintEvent @ ggis/common/widgets/standard.py:563")
            pass
        finally:
            p.end()

    def _paint_hint(self, p, text):
        p.setPen(QPen(QColor(_themes.text_dim()), 1, Qt.PenStyle.DashLine))
        p.drawRect(self.rect().adjusted(8, 8, -8, -8))
        p.setPen(QColor(_themes.text_dim()))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def _paint_loading(self, p):
        p.setPen(QColor(_themes.text_dim()))
        p.drawText(self.rect(),
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   _tr("加载中…"))

    def _view_box(self, ext):
        try:
            cur = self._canvas.extent()
        except Exception:
            exc_note("_view_box @ ggis/common/widgets/standard.py:586")
            return None
        if cur is None or cur.is_empty():
            return None
        sx = self.width() / float(ext.width())
        sy = self.height() / float(ext.height())
        if sx <= 0 or sy <= 0:
            return None
        return QRectF((cur.xmin - ext.xmin) * sx,
                      (ext.ymax - cur.ymax) * sy,
                      cur.width() * sx, cur.height() * sy)

    def _paint_viewport(self, p, ext):
        box = self._view_box(ext)
        if box is None:
            return
        r = QRectF(self.rect())
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.save()
        p.setClipRect(r)
        veil = QColor(self._bg)
        veil.setAlpha(110)
        outside = QPainterPath()
        outside.addRect(r)
        inner = QPainterPath()
        inner.addRect(box)
        p.fillPath(outside.subtracted(inner), veil)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 190), 1))
        p.drawRect(box.adjusted(-1.0, -1.0, 1.0, 1.0))
        light = QColor("#FFFFFF") if _is_dark_color(self._bg) else QColor("#000000")
        p.setPen(QPen(light, 1))
        p.drawRect(box)

    def _move_center_to(self, pos):
        ext = self._overview_extent()
        if ext is None:
            return
        try:
            cur = self._canvas.extent()
        except Exception:
            exc_note("_move_center_to @ ggis/common/widgets/standard.py:637")
            return
        if cur is None or cur.is_empty():
            return
        sx = self.width() / float(ext.width())
        sy = self.height() / float(ext.height())
        if sx <= 0 or sy <= 0:
            return
        mx = ext.xmin + pos.x() / sx
        my = ext.ymax - pos.y() / sy
        half_w, half_h = cur.width() / 2.0, cur.height() / 2.0
        self._canvas.setExtent((mx - half_w, my - half_h,
                                mx + half_w, my + half_h))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._on:
            self._dragging = self._overview_extent() is not None
            if self._dragging:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self._move_center_to(e.position())
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._move_center_to(e.position())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._dragging and e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        if self._on and self._canvas is not None:
            dy = e.angleDelta().y()
            if dy > 0:
                self._canvas.zoomIn()
                e.accept()
                return
            if dy < 0:
                self._canvas.zoomOut()
                e.accept()
                return
        super().wheelEvent(e)

    def sizeHint(self):
        return QSize(220, 160)
