# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import os
import time

from PySide6.QtCore import (Qt, Signal, QPoint, QPointF, QRect, QRectF, QSize,
                            QMimeData)
from PySide6.QtWidgets import (
                               QTreeWidget,
                               QTreeWidgetItem,
                               QWidget,
                               QVBoxLayout,
                               QHBoxLayout,
                               QMenu,
                               QSizePolicy,
                               QStyledItemDelegate,
                               QStyleOptionViewItem,
                               QStyle,
)
from PySide6.QtGui import (QIcon, QColor, QKeySequence, QLinearGradient,
                           QBrush, QPen, QFontMetrics, QPalette,
                           QDrag, QCursor)

from ggis.ui.framework.docks import GgsDockWidget
from ggis.common.styling import icons as _icons
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.core.app import i18n
from ggis.core.style import raster_display as rd
from ggis.core.model.selection import GgsSelection
from ggis.core.model.layer import layer_allows
from ggis.common.widgets.itemviews import GgsTreeWidget
from ggis.ui.framework.docks import GgsDockBody
import logging
from PySide6.QtWidgets import QFrame
_log = logging.getLogger("gmagis")

_tr = i18n.tr

COL_NAME = 0

ROLE_KIND = int(Qt.ItemDataRole.UserRole) + 1
ROLE_LAYER_ID = int(Qt.ItemDataRole.UserRole) + 2
ROLE_ICON_NAME = int(Qt.ItemDataRole.UserRole) + 3
ROLE_LEGEND = int(Qt.ItemDataRole.UserRole) + 4
ROLE_GROUP_ID = int(Qt.ItemDataRole.UserRole) + 5


def _group_ref(item):
    if item is None:
        return ""
    try:
        if item.data(COL_NAME, ROLE_KIND) != "group":
            return ""
        return str(item.data(COL_NAME, ROLE_GROUP_ID) or "")
    except Exception:
        exc_note("group_ref @ ggis/ui/panels/layertree.py")
        return ""


def _group_from_ref(view, ref):
    gid = str(ref or "")
    if not gid:
        return None

    def _walk(parent):
        n = (parent.childCount() if parent is not None
             else view.topLevelItemCount())
        for i in range(n):
            it = (parent.child(i) if parent is not None
                  else view.topLevelItem(i))
            if it is None:
                continue
            try:
                if (it.data(COL_NAME, ROLE_KIND) == "group"
                        and str(it.data(COL_NAME, ROLE_GROUP_ID) or "") == gid):
                    return it
            except Exception:
                continue
            got = _walk(it)
            if got is not None:
                return got
        return None

    try:
        return _walk(None)
    except Exception:
        exc_note("group_from_ref @ ggis/ui/panels/layertree.py")
        return None


def _pending_view_key():
    try:
        from ggis.ui.views.view_host import ViewHost
        vh = ViewHost.instance()
        cur = vh.current_view() if vh is not None else None
        if cur is not None and getattr(cur, "kind", None) == "map":
            return str(cur.view_id)
    except Exception:
        pass
    return ""

LAYER_MENU_OBJECT_NAME = "GgsLayerTreeMenu"
BLANK_MENU_OBJECT_NAME = "GgsTreeMenu"


def _set_drop_enabled(item, enabled):
    try:
        f = item.flags()
        if enabled:
            f |= Qt.ItemFlag.ItemIsDropEnabled
        else:
            f &= ~Qt.ItemFlag.ItemIsDropEnabled
        item.setFlags(f)
    except Exception:
        _log.exception("silent exception in _set_drop_enabled")


def _item_alive(item):
    if item is None:
        return False
    try:
        import shiboken6
        return bool(shiboken6.isValid(item))
    except Exception:
        _log.exception("silent exception in _item_alive")
        return False


def _norm_path(p):
    try:
        import os as _os
        return _os.path.normcase(_os.path.abspath(str(p)))
    except Exception:
        _log.exception("silent exception in _norm_path")
        return str(p or "")


def _iter_rows(view):
    def _walk(parent):
        n = (parent.childCount() if parent is not None
             else view.topLevelItemCount())
        for i in range(n):
            it = (parent.child(i) if parent is not None
                  else view.topLevelItem(i))
            if it is None:
                continue
            yield it
            yield from _walk(it)

    try:
        yield from _walk(None)
    except Exception:
        _log.exception("silent exception in _iter_rows")
        return


def _fmt_num(v):
    if v is None:
        return "—"
    try:
        f = float(v)
    except Exception:
        _log.exception("silent exception in _fmt_num")
        return str(v)
    a = abs(f)
    if a and (a >= 1e6 or a < 1e-3):
        return "%.3g" % f
    if a >= 100:
        return "%.0f" % f
    if a >= 1:
        return "%.2f" % f
    if a == 0:
        return "0"
    return "%.3g" % f


def _is_int_dtype(layer):
    try:
        dt = str(layer.dtype() or "").strip().lower()
    except Exception:
        _log.exception("silent exception in _is_int_dtype")
        return False
    return dt.startswith(("int", "uint"))


def _legend_num(v, layer=None):
    if layer is not None and _is_int_dtype(layer):
        try:
            return str(int(round(float(v))))
        except Exception:
            _log.exception("silent exception in _legend_num")
            return str(v)
    return _fmt_num(v)


def _gray_stops(n=24):
    return [tuple(int(round(255.0 * i / max(1, n - 1))) for _ in range(3))
            for i in range(n)]


def _legend_rows(layer):
    try:
        if layer.is_vector():
            from ...render.renderers import get_renderer
            r = get_renderer(layer)
            geom = ""
            try:
                geom = str(layer.base_kind() or "")
            except Exception:
                _log.exception("silent exception in _legend_rows")
                geom = ""
            out = []
            for i, (lab, sym) in enumerate((r.legend_items(layer) or [])[:64]):
                out.append({"kind": "vector", "label": str(lab or ""),
                            "geom": geom, "symbol": sym, "index": i})
            return out
        if layer.is_raster():
            from ggis.core.style.raster_display import (get_display, RAMP_NONE,
                                                ramp_stops,
                                                layer_limits, stats_for,
                                                render_mode, class_steps, class_color_list,
                                                class_breaks_of,
                                                legend_palette,
                                                MODE_RGB, MODE_COLORMAP,
                                                MODE_UNIQUE, MODE_CLASSIFY)
            d = get_display(layer)
            try:
                n = int(layer.band_count() or 0)
            except Exception:
                _log.exception("silent exception in _legend_rows")
                n = 0
            band = int(getattr(d, "band", 0) or 0)
            cur_mode = render_mode(d)
            lo = hi = None
            try:
                lim = layer_limits(layer, d, band=band)
                if lim:
                    lo, hi = float(lim[0]), float(lim[1])
            except Exception:
                _log.exception("silent exception in _legend_rows")
            if lo is None or hi is None:
                try:
                    st = stats_for(layer, d, band=band) or {}
                    lo, hi = st.get("min"), st.get("max")
                except Exception:
                    _log.exception("silent exception in _legend_rows")
            ramp = d.ramp if (d.ramp and d.ramp != RAMP_NONE) else None
            inv = bool(getattr(d, "invert_ramp", False))
            cur_ramp = str(getattr(d, "ramp", "") or RAMP_NONE)
            swatches = []

            def _flip(stops):
                return list(reversed(stops)) if (inv and stops) else stops

            if cur_mode == MODE_RGB:
                bands = []
                try:
                    _rb = tuple(int(v or 0) for v in (d.rgb_bands or (0, 0, 0)))
                except Exception:
                    _log.exception("silent exception in _legend_rows")
                    _rb = (0, 0, 0)
                for _i, (_ch, _cn, _hex) in enumerate(
                        (("R", "红色", "#E82828"), ("G", "绿色", "#28B828"),
                         ("B", "蓝色", "#2828E8"))):
                    _b = _rb[_i] if _i < len(_rb) else 0
                    if _b <= 0 or (n and _b > n):
                        _b = min(_i + 1, n) if n > 0 else (_i + 1)
                    swatches.append({"color": _hex, "name": _tr(_cn),
                                     "label": _tr("波段 {0}").format(_b),
                                     "band": int(_b), "channel": _ch})
            elif cur_mode in (MODE_COLORMAP, MODE_UNIQUE):
                keys, cmap = legend_palette(layer, d)
                if keys:
                    bands = [{"stops": [tuple(cmap[k][:3]) for k in keys],
                              "title": None}]
                    lo, hi = float(keys[0]), float(keys[-1])
                    swatches = [{"color": "#%02X%02X%02X" % tuple(cmap[k][:3]),
                                 "label": _legend_num(k, layer),
                                 "value": int(k)} for k in keys]
                else:
                    bands = [{"stops": _flip(_gray_stops(32)), "title": None}]
            elif cur_mode == MODE_CLASSIFY:
                _n = class_steps(d) or 0
                _cols = class_color_list(d)
                _bk = class_breaks_of(d)
                if _n and len(_cols) >= _n:
                    bands = []
                    _lo = float(lo) if lo is not None else 0.0
                    _hi = float(hi) if hi is not None else 1.0
                    if not (_bk and len(_bk) == _n + 1):
                        _bk = [_lo + (_hi - _lo) * i / _n for i in range(_n + 1)]
                    for _i in range(_n):
                        swatches.append({
                            "color": "#%02X%02X%02X" % tuple(_cols[_i]),
                            "label": "%s – %s" % (_fmt_num(_bk[_i]),
                                                  _fmt_num(_bk[_i + 1])),
                            "class_index": int(_i)})
                    lo, hi = float(_bk[0]), float(_bk[-1])
                else:
                    bands = [{"stops": _flip(_gray_stops(32)), "title": None}]
            elif ramp:
                bands = [{"stops": _flip(ramp_stops(ramp, 32)),
                          "title": None}]
            else:
                bands = [{"stops": _flip(_gray_stops(32)), "title": None}]
            base = {"kind": "raster", "bands": [],
                    "lo": lo, "hi": hi, "ramp": cur_ramp, "invert": inv,
                    "lo_text": str(getattr(d, "anno_min", "") or ""),
                    "hi_text": str(getattr(d, "anno_max", "") or ""),
                    "mode": cur_mode,
                    "band_count": n,
                    "rgb": bool(cur_mode == MODE_RGB)}
            if swatches:
                out = []
                for _i, _s in enumerate(swatches):
                    p = dict(base)
                    p["swatches"] = [_s]
                    p["swatch_row"] = int(_i)
                    p["label"] = str(_s.get("label") or "")
                    p["index"] = int(_i)
                    out.append(p)
                return out
            base["bands"] = bands
            base["swatches"] = []
            base["index"] = 0
            return [base]
    except Exception:
        _log.exception("silent exception in _legend_rows")
        return []
    return []


_RASTER_RAMP_DOT = "#4C9BE8"
_RASTER_GRAY_DOT = "#9A9A9A"


def _raster_has_attribute_table(layer):
    try:
        if rd.palette(layer):
            return True
        vals = rd.existing_values(layer, cached_only=True)
        if vals:
            return True
    except Exception:
        _log.exception("silent exception in _raster_has_attribute_table")
        return False
    return False




class GgsLegendDelegate(QStyledItemDelegate):

    VECTOR_H = 24
    RASTER_H = 60
    SW_W = 18
    SW_H = 14
    BAR_W = 14
    SWATCH_LH = 24
    PAD = 5

    def __init__(self, view):
        super().__init__(view)
        self._view = view
        self._active = False

    def createEditor(self, parent, option, index):
        ed = super().createEditor(parent, option, index)
        try:
            ed.setObjectName("GgsTreeRenameEdit")
        except Exception:
            _log.exception("silent exception in createEditor")
        return ed

    def updateEditorGeometry(self, editor, option, index):
        row = QRect(option.rect)
        vr = QRect()
        try:
            item = self._view.itemFromIndex(index)
            if item is not None:
                vr = self._view.visualItemRect(item)
        except Exception:
            _log.exception("silent exception in updateEditorGeometry")
            vr = QRect()
        if vr.isValid() and vr.height() > 0:
            row.setTop(vr.top())
            row.setBottom(vr.bottom())
            row.setRight(vr.right() - 2)

        try:
            opt = QStyleOptionViewItem()
            opt.rect = QRect(vr) if (vr.isValid() and vr.height() > 0) \
                else QRect(option.rect)
            opt.widget = self._view
            self.initStyleOption(opt, index)
            opt.rect = QRect(vr) if (vr.isValid() and vr.height() > 0) \
                else QRect(option.rect)
            try:
                opt.features |= (QStyleOptionViewItem.ViewItemFeature
                                 .HasCheckIndicator)
                opt.features |= (QStyleOptionViewItem.ViewItemFeature
                                 .HasDecoration)
                _si = self._view.iconSize()
                if _si.width() > 0:
                    opt.decorationSize = QSize(_si)
            except Exception:
                _log.exception("silent exception in updateEditorGeometry")
            txt = self._view.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemText, opt, self._view)
            left = txt.left() if txt.isValid() else row.left()
            try:
                dec = self._view.style().subElementRect(
                    QStyle.SubElement.SE_ItemViewItemDecoration, opt,
                    self._view)
                if (dec.isValid() and dec.width() > 0
                        and int(left) < int(dec.right())):
                    left = int(dec.right()) + 6
            except Exception:
                _log.exception("silent exception in updateEditorGeometry")
            if left > row.left():
                row.setLeft(int(left))
        except Exception:
            _log.exception("silent exception in updateEditorGeometry")
        editor.setGeometry(row)

    def _payload(self, index):
        if not index.isValid():
            return None
        try:
            if index.data(ROLE_KIND) != "legend":
                return None
        except Exception:
            _log.exception("silent exception in _payload")
            return None
        p = index.data(ROLE_LEGEND)
        return p if isinstance(p, dict) else None

    def sizeHint(self, opt, index):
        p = self._payload(index)
        base = super().sizeHint(opt, index)
        h = (self.RASTER_H if (p or {}).get("kind") == "raster"
             else (max(self.VECTOR_H, base.height()) if p is not None
                   else base.height()))
        if (p or {}).get("kind") == "raster":
            _n = len((p or {}).get("swatches") or [])
            if _n:
                h = max(self.VECTOR_H, base.height())
        return QSize(base.width(), h)

    def paint(self, painter, opt, index):
        p = self._payload(index)
        if p is None:
            super().paint(painter, opt, index)
            return
        self._active = self._is_menu_target(index)
        try:
            o = QStyleOptionViewItem(opt)
            o.text = ""
            o.icon = QIcon()
            o.rect = QRect(opt.rect)
            try:
                o.rect.setRight(max(o.rect.right(),
                                    self._view.viewport().width() - 1))
            except Exception:
                _log.exception("silent exception in paint")
            if self._active:
                o.state |= QStyle.StateFlag.State_Selected
                o.state &= ~QStyle.StateFlag.State_MouseOver
            w = opt.widget if opt.widget is not None else self._view
            w.style().drawControl(QStyle.ControlElement.CE_ItemViewItem,
                                  o, painter, w)
        except Exception:
            _log.exception("silent exception in paint")
        painter.save()
        try:
            r = QRectF(opt.rect)
            if p.get("kind") == "raster":
                self._paint_raster(painter, opt, r, p)
            else:
                self._paint_vector(painter, opt, r, p)
        finally:
            painter.restore()

    def _is_menu_target(self, index):
        view = self._view
        key = getattr(view, "_menu_key", None)
        if key is None:
            return False
        try:
            it = view.itemFromIndex(index)
        except Exception:
            _log.exception("silent exception in _is_menu_target")
            return False
        if it is None:
            return False
        if it is getattr(view, "_menu_item", None):
            return True
        return view._legend_key_of(it) == key

    def _text_color(self, opt):
        return opt.palette.color(QPalette.ColorRole.Text)

    def _paint_vector(self, painter, opt, r, p):
        sy = r.top() + (r.height() - self.SW_H) / 2.0
        sw = QRect(r.left() + 4, int(sy), self.SW_W, self.SW_H)
        try:
            from ggis.core.model.layout_items import draw_symbol_swatch
            draw_symbol_swatch(painter, sw, p.get("symbol"),
                               p.get("geom") or "")
        except Exception:
            _log.exception("silent exception in _paint_vector")
            painter.setPen(QPen(self._text_color(opt), 1))
            painter.drawRect(QRectF(sw).adjusted(2, 3, -2, -3))
        tx = sw.right() + 6
        maxw = max(10, int(r.right() - tx - 2))
        fm = QFontMetrics(opt.font)
        t = fm.elidedText(str(p.get("label") or ""),
                          Qt.TextElideMode.ElideRight, maxw)
        painter.setPen(self._text_color(opt))
        painter.setFont(opt.font)
        painter.drawText(QRectF(tx, r.top(), maxw, r.height()),
                         int(Qt.AlignmentFlag.AlignVCenter
                             | Qt.AlignmentFlag.AlignLeft), t)

    def _paint_raster(self, painter, opt, r, p):
        _sw = [s0 for s0 in (p.get("swatches") or []) if s0.get("color")]
        if _sw:
            self._paint_swatches(painter, opt, r, _sw)
            return
        bands = [b for b in (p.get("bands") or []) if b.get("stops")]
        if not bands:
            bands = [{"stops": _gray_stops(32), "title": None}]
        top = r.top() + self.PAD
        bot = r.bottom() - self.PAD
        h = max(6.0, bot - top)
        x = r.left() + 4
        for b in bands:
            self._paint_bar(painter, QRectF(x, top, self.BAR_W, h),
                            b.get("stops") or [])
            x += self.BAR_W + 4
        tx = x + 4
        maxw = max(10, int(r.right() - tx - 2))
        fm = QFontMetrics(opt.font)
        lh = fm.height()
        painter.setFont(opt.font)
        pen = self._text_color(opt)
        painter.setPen(pen)
        _hi_txt = str(p.get("hi_text") or "").strip() or _fmt_num(p.get("hi"))
        _lo_txt = str(p.get("lo_text") or "").strip() or _fmt_num(p.get("lo"))
        painter.drawText(QRectF(tx, top, maxw, lh),
                         int(Qt.AlignmentFlag.AlignVCenter
                             | Qt.AlignmentFlag.AlignLeft),
                         fm.elidedText(_tr("最大 {0}").format(
                             _hi_txt), Qt.TextElideMode.ElideRight,
                             maxw))
        painter.drawText(QRectF(tx, bot - lh, maxw, lh),
                         int(Qt.AlignmentFlag.AlignVCenter
                             | Qt.AlignmentFlag.AlignLeft),
                         fm.elidedText(_tr("最小 {0}").format(
                             _lo_txt), Qt.TextElideMode.ElideRight,
                             maxw))

    def _paint_swatches(self, painter, opt, r, sw):
        fm = QFontMetrics(opt.font)
        painter.setFont(opt.font)
        x = r.left() + 4
        maxw = max(10, int(r.right() - x - 2))
        try:
            from ggis.core.model.layout_items import draw_flat_swatch
        except Exception:
            _log.exception("silent exception in _paint_swatches")
            draw_flat_swatch = None
        y = r.top() + max(0.0, (r.height() - self.SWATCH_LH
                                * max(1, len(sw))) / 2.0)
        for item in sw:
            try:
                c = QColor(str(item.get("color")))
            except Exception:
                _log.exception("silent exception in _paint_swatches")
                continue
            box = QRectF(x, y + (self.SWATCH_LH - self.SW_H) / 2.0,
                         self.SW_W, self.SW_H)
            if draw_flat_swatch is not None:
                draw_flat_swatch(painter, box, c)
            else:
                painter.setPen(QPen(QColor(0, 0, 0, 45), 1))
                painter.setBrush(QBrush(c))
                painter.drawRect(box)
            painter.setPen(self._text_color(opt))
            tx = int(box.right()) + 6
            wl = maxw - (tx - x)
            nm = str(item.get("name") or "")
            if nm:
                nw = min(wl * 0.5, fm.horizontalAdvance(nm + ":") + 8.0)
                painter.drawText(QRectF(tx, y, nw, self.SWATCH_LH),
                                 int(Qt.AlignmentFlag.AlignVCenter
                                     | Qt.AlignmentFlag.AlignLeft),
                                 nm + ":")
                tx += nw
                wl = max(10.0, wl - nw)
            painter.drawText(QRectF(tx, y, wl, self.SWATCH_LH),
                             int(Qt.AlignmentFlag.AlignVCenter
                                 | Qt.AlignmentFlag.AlignLeft),
                             fm.elidedText(str(item.get("label") or ""),
                                           Qt.TextElideMode.ElideRight, wl))
            y += self.SWATCH_LH

    @staticmethod
    def _paint_bar(painter, rect, stops):
        n = len(stops)
        if n == 0 or rect.isEmpty():
            return
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        for i, rgb in enumerate(stops):
            t = i / max(1, n - 1)
            try:
                c = QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))
            except Exception:
                _log.exception("silent exception in _paint_bar")
                continue
            g.setColorAt(min(1.0, max(0.0, 1.0 - t)), c)
        painter.setPen(QPen(QColor(0, 0, 0, 45), 1))
        painter.setBrush(QBrush(g))
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)


class GgsLayerTreeView(GgsTreeWidget):

    orderChanged = Signal()
    itemActivated = Signal(object)
    legendActionRequested = Signal(str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsLayerTree")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setIndentation(14)
        self.setAnimated(False)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._popup_menu)
        self.setItemDelegate(GgsLegendDelegate(self))
        self.itemDoubleClicked.connect(self._on_double)
        self._menu_item = None
        self._menu_key = None
        self._legend_pos = None

    def _on_double(self, item, _col):
        if item is not None and item.data(COL_NAME, ROLE_KIND) == "layer":
            self.editItem(item, COL_NAME)

    def set_project(self, project):
        self._project = project

    def _layer_of(self, item):
        proj = getattr(self, "_project", None)
        if proj is None or item is None:
            return None
        cur = item
        while cur is not None:
            lid = cur.data(COL_NAME, ROLE_LAYER_ID)
            if lid and cur.data(COL_NAME, ROLE_KIND) == "layer":
                try:
                    return proj.layer_by_id(lid)
                except Exception:
                    _log.exception("silent exception in _layer_of")
                    return None
            cur = cur.parent()
        return None

    def _labels_enabled(self, layer):
        try:
            from ...render.labeling import get_label_style
            return bool(get_label_style(layer).enabled)
        except Exception:
            _log.exception("silent exception in _labels_enabled")
            return False

    def select_layer_item(self, item):
        if item is None:
            return
        try:
            already = item in self.selectedItems()
        except Exception:
            _log.exception("silent exception in select_layer_item")
            already = False
        if not already:
            try:
                self.setCurrentItem(item)
            except Exception:
                _log.exception("silent exception in select_layer_item")
            return
        try:
            from PySide6.QtCore import QItemSelectionModel
            self.selectionModel().setCurrentIndex(
                self.indexFromItem(item),
                QItemSelectionModel.SelectionFlag.NoUpdate)
        except Exception:
            _log.exception("silent exception in select_layer_item")

    def picked_layer_items(self, item):
        sel = [it for it in self.selectedItems()
               if it.data(COL_NAME, ROLE_KIND) == "layer"]
        if item is None:
            return sel
        if item not in sel:
            if item.data(COL_NAME, ROLE_KIND) == "layer":
                return [item]
            return []
        return sel

    def picked_items(self, item):
        kinds = ("layer", "group")
        sel = [it for it in self.selectedItems()
               if it.data(COL_NAME, ROLE_KIND) in kinds]
        if item is None:
            return sel
        if item not in sel:
            return [item] if item.data(COL_NAME, ROLE_KIND) in kinds else []
        return sel

    def group_selected_items(self, item):
        items = self.picked_items(item)
        if not items:
            return
        top = [it for it in items if it.parent() is None]
        if len(top) < 1:
            return
        dock = getattr(self, "layer_dock", None)
        if dock is None or getattr(dock, "_tree", None) is None:
            _log.warning("group_selected_items: 图层树模型未挂载，无法建分组")
            return
        try:
            first = min(self.indexOfTopLevelItem(it) for it in top)
        except Exception:
            _log.exception("silent exception in group_selected_items")
            first = 0
        grp = dock.add_group(name=_tr("组"), parent=None, pos=max(0, first))
        gid = _group_ref(grp) if grp is not None else ""
        if not gid:
            _log.warning("group_selected_items: 新建分组未落模型，放弃成组")
            return
        ids = []
        for it in top:
            try:
                kind = it.data(COL_NAME, ROLE_KIND)
                nid = (it.data(COL_NAME, ROLE_LAYER_ID)
                       if kind == "layer" else it.data(COL_NAME, ROLE_GROUP_ID))
            except Exception:
                _log.exception("silent exception in group_selected_items")
                continue
            if nid:
                ids.append(str(nid))
        if ids:
            dock._tree.move_nodes(ids, gid, 0)
        try:
            new_it = _group_from_ref(self, gid)
            if new_it is not None:
                self.setCurrentItem(new_it)
        except Exception:
            _log.exception("silent exception in group_selected_items")

    def paste_available(self):
        fn = getattr(self, "can_paste", None)
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                _log.exception("silent exception in paste_available")
                return True
        return True

    def build_menu(self, item):
        m = QMenu(self)
        try:
            m.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        except Exception:
            _log.exception("silent exception in build_menu")
        kind = item.data(COL_NAME, ROLE_KIND) if item is not None else None
        if kind == "layer":
            m.setObjectName(LAYER_MENU_OBJECT_NAME)
            self._fill_layer_menu(m, item)
        elif kind == "group":
            m.setObjectName(LAYER_MENU_OBJECT_NAME)
            self._fill_group_menu(m, item)
        elif kind == "legend":
            m.setObjectName(LAYER_MENU_OBJECT_NAME)
            self._fill_legend_menu(m, item)
        else:
            m.setObjectName(BLANK_MENU_OBJECT_NAME)
            self._fill_blank_menu(m)
        return m

    def _mi(self, menu, text, icon_name, slot, checkable=None, shortcut=None,
            accel=None):
        if accel:
            text = "%s(&%s)" % (str(text), str(accel))
        a = menu.addAction(text)
        if icon_name:
            try:
                from ggis.common.styling import icons as _icons
                _icons.bind(a, icon_name, size=16)
            except Exception:
                _log.exception("silent exception in _mi")
        if checkable is not None:
            a.setCheckable(True)
            a.setChecked(bool(checkable))
        if shortcut:
            try:
                a.setShortcut(QKeySequence(str(shortcut)))
            except Exception:
                _log.exception("silent exception in _mi")
        a.triggered.connect(slot)
        return a

    def _fill_layer_menu(self, m, item):
        lyr = self._layer_of(item)
        picked = self.picked_layer_items(item)
        multi = len(picked) > 1
        is_tile = bool(lyr is not None and lyr.is_tile())
        is_table = bool(lyr is not None and lyr.is_table())
        is_vec = bool(lyr is None or lyr.is_vector())

        self._mi(m, _tr("复制"), "copy_features",
                 lambda: self._emit("copy", item), accel="C")
        self._mi(m, _tr("剪贴"), "cut_features",
                 lambda: self._emit("cut", item), accel="X")
        if not multi:
            self._mi(m, _tr("复制路径"), "copy_path",
                     lambda: self._emit("copypath", item), accel="A")
        m.addSeparator()
        if not multi:
            self._mi(m, _tr("重命名"), "edit",
                     lambda: self.editItem(item, COL_NAME), accel="R")
        self._mi(m, _tr("移除"), "remove",
                 lambda: self._emit("remove", item), accel="D")
        m.addSeparator()

        if not multi and not is_tile:
            if is_vec:
                self._mi(m, _tr("属性表"), "table",
                         lambda: self._emit("table", item), accel="T")
            else:
                _act = self._mi(m, _tr("属性表"), "table",
                                lambda: self._emit("raster_attr", item), accel="T")
                if not _raster_has_attribute_table(lyr):
                    _act.setEnabled(False)
                    _act.setToolTip(
                        _tr("这个栅格没有属性表"))
            m.addSeparator()

        if multi:
            if layer_allows(lyr, "zoom"):
                self._mi(m, _tr("缩放至图层"), "zoom_layer",
                         lambda: self._emit("zoom", item), accel="Z")
            self._mi(m, _tr("显示"), "visible",
                     lambda: self._emit("vis_on", item), accel="S")
            self._mi(m, _tr("隐藏"), "hidden",
                     lambda: self._emit("vis_off", item), accel="H")
            self._mi(m, _tr("将所选成组"), "new_group",
                     lambda: self._emit("group_selected", item), accel="G")
            return
        if layer_allows(lyr, "zoom"):
            self._mi(m, _tr("缩放至图层"), "zoom_layer",
                     lambda: self._emit("zoom", item), accel="Z")
            if is_vec and not is_tile:
                _zoom_sel = self._mi(m, _tr("缩放至选中要素"), "zoom_layer",
                                     lambda: self._emit("zoom_sel", item),
                                     accel="E")
                if _zoom_sel is not None:
                    try:
                        _has = bool(GgsSelection.instance().fids(lyr))
                    except Exception:
                        _log.exception("silent exception in _fill_layer_menu")
                        _has = False
                    if not _has:
                        _zoom_sel.setEnabled(False)
            m.addSeparator()

        if is_vec and not is_tile and layer_allows(lyr, "toggle_labels"):
            self._mi(m, _tr("显示标注"),
                     "checkbox_on" if self._labels_enabled(lyr)
                     else "checkbox_off",
                     lambda: self._emit("toggle_labels", item), accel="B")
            self._mi(m, _tr("标注设置"), "label",
                     lambda: self._emit("labels", item), accel="S")
            m.addSeparator()

        if is_tile:
            sub = m.addMenu("%s(&%s)" % (_tr("导出"), "E"))
            self._mi(sub, _tr("导出数据"), "export",
                     lambda: self._emit("export", item), accel="D")
            m.addSeparator()
        elif is_vec and layer_allows(lyr, "symbol"):
            self._mi(m, _tr("符号系统"), "styling",
                     lambda: self._emit("symbol", item), accel="Y")
            m.addSeparator()
        elif is_table:
            pass
        else:
            self._mi(m, _tr("符号系统"), "opacity",
                     lambda: self._emit("raster_display", item), accel="Y")
            self._mi(m, _tr("直方图"), "histogram",
                     lambda: self._emit("raster_histogram", item), accel="H")
            m.addSeparator()

        if not is_tile:
            if is_vec and layer_allows(lyr, "filter"):
                self._mi(m, _tr("过滤要素"), "filter",
                         lambda: self._emit("filter", item), accel="F")
            sub = m.addMenu("%s(&%s)" % (_tr("导出"), "E"))
            self._mi(sub, _tr("导出数据"), "export",
                     lambda: self._emit("export", item), accel="D")
            if layer_allows(lyr, "export_style"):
                self._mi(sub, _tr("导出样式"), "style_library",
                         lambda: self._emit("export_style", item), accel="S")
            if is_table:
                self._mi(m, _tr("表转矢量"), "table_to_layer",
                         lambda: self._emit("table_to_layer", item))
            m.addSeparator()

        self._mi(m, _tr("属性"), "info",
                 lambda: self._emit("props", item), accel="P")

    def _layer_node_of(self, item):
        cur = item
        while cur is not None:
            if cur.data(COL_NAME, ROLE_KIND) == "layer":
                return cur
            cur = cur.parent()
        return item

    def _emit_legend(self, kind, item, payload=None):
        node = self._layer_node_of(item)
        try:
            self.legendActionRequested.emit(kind, node, payload)
        except Exception:
            _log.exception("silent exception in _emit_legend")

    def _fill_legend_menu(self, m, item):
        p = item.data(COL_NAME, ROLE_LEGEND) or {}
        if str(p.get("kind") or "") == "raster":
            if p.get("rgb"):
                self._fill_rgb_band_menu(m, item, p)
                return
            if p.get("swatches"):
                self._embed_swatch_color(m, item, p)
                return
            self._embed_ramp_menu(m, item, p)
            return
        self._embed_color_panel(m, item, p)

    def _swatch_row_at(self, item, p):
        pos = getattr(self, "_legend_pos", None)
        if pos is None:
            return -1
        try:
            rect = self.visualItemRect(item)
            y = int(pos.y()) - int(rect.top()) - int(GgsLegendDelegate.PAD)
        except Exception:
            _log.exception("silent exception in _swatch_row_at")
            return -1
        if y < 0:
            return -1
        i = int(y // max(1, int(GgsLegendDelegate.SWATCH_LH)))
        n = len([s0 for s0 in (p.get("swatches") or [])
                 if s0.get("color")])
        return i if 0 <= i < n else -1

    def _swatch_row_of(self, item, p):
        v = (p or {}).get("swatch_row")
        if v is not None:
            try:
                return int(v)
            except Exception:
                _log.exception("silent exception in _swatch_row_of")
        return self._swatch_row_at(item, p)

    def _embed_swatch_color(self, menu, item, p):
        sw = [s0 for s0 in (p.get("swatches") or []) if s0.get("color")]
        if not sw:
            return
        row = self._swatch_row_of(item, p)
        if row < 0:
            row = 0
        try:
            from PySide6.QtGui import QColor
            from ..dialogs.color import GgsColorPopup
        except Exception:
            _log.exception("silent exception in _embed_swatch_color")
            return
        try:
            cur = QColor(str(sw[0].get("color") or "#FFFFFF"))
        except Exception:
            _log.exception("silent exception in _embed_swatch_color")
            cur = QColor("#FFFFFF")
        try:
            pnl = GgsColorPopup(cur, menu, with_alpha=True, shape="rect",
                                embedded=True)
        except Exception:
            _log.exception("silent exception in _embed_swatch_color")
            return

        def _picked(c, _row=int(row)):
            self._emit_legend("raster_swatch_color", item, (_row, c))

        pnl.colorPicked.connect(_picked)
        self._embed(menu, pnl)

    def _fill_rgb_band_menu(self, menu, item, p):
        node = self._layer_node_of(item)
        rows = [s0 for s0 in (p.get("swatches") or []) if s0.get("channel")]
        if not rows:
            self._mi(menu, _tr("符号系统…"), "styling",
                     lambda: self._emit("symbol", node), accel="Y")
            return
        try:
            n = int(p.get("band_count") or 0)
        except Exception:
            _log.exception("silent exception in _fill_rgb_band_menu")
            n = 0
        row = self._swatch_row_of(item, p)
        pairs = [(int(s0.get("swatch_row", i)), s0)
                 for i, s0 in enumerate(rows)]
        if any(i == row for i, _s in pairs):
            pairs = [x for x in pairs if x[0] == row]
        for i, s0 in pairs:
            nm = str(s0.get("name") or s0.get("channel") or "")
            sub = menu.addMenu(_tr("{0} 波段").format(nm))
            cur = int(s0.get("band") or 0)
            for b in range(1, max(1, n) + 1):
                icon = "checkbox_on" if int(cur) == int(b) else "checkbox_off"
                self._mi(sub, _tr("波段 {0}").format(b), icon,
                         lambda _i=int(i), _v=b: self._emit_legend(
                             "raster_rgb_band", item, (_i, _v)))

    MENU_FIELD_WIDTH = 168

    def _embed(self, menu, widget):
        try:
            from PySide6.QtWidgets import QWidgetAction
        except Exception:
            _log.exception("silent exception in _embed")
            return None
        try:
            wa = QWidgetAction(menu)
            wa.setDefaultWidget(widget)
            menu.addAction(wa)
            return wa
        except Exception:
            _log.exception("silent exception in _embed")
            return None

    def _embed_color_panel(self, menu, item, p):
        sym = p.get("symbol")
        if sym is None:
            return
        try:
            from PySide6.QtGui import QColor
            from ..dialogs.color import GgsColorPopup
        except Exception:
            _log.exception("silent exception in _embed_color_panel")
            return
        try:
            idx = int(p.get("index") or 0)
        except Exception:
            _log.exception("silent exception in _embed_color_panel")
            idx = 0
        geom = str(p.get("geom") or "")
        try:
            cur = QColor(sym.stroke if geom == "line" else sym.fill)
        except Exception:
            _log.exception("silent exception in _embed_color_panel")
            cur = QColor("#FFFFFF")
        shape = {"line": "line", "point": "dot"}.get(geom, "rect")
        node = self._layer_node_of(item)
        try:
            pnl = GgsColorPopup(cur, menu, with_alpha=True, shape=shape,
                                embedded=True)
        except Exception:
            _log.exception("silent exception in _embed_color_panel")
            return

        def _picked(c, _node=node, _idx=idx):
            self._emit_legend("legend_color", _node, (_idx, c))

        pnl.colorPicked.connect(_picked)
        self._embed(menu, pnl)

    def _ramp_items(self):
        from ggis.core.style.raster_display import RAMPS, ramp_hex_stops
        try:
            from ggis.core.style import user_ramps
            users = user_ramps.entries()
        except Exception:
            _log.exception("silent exception in _ramp_items")
            users = []
        out = [(code, _tr(label), ramp_hex_stops(code, 32))
               for code, label, _pts in RAMPS]
        for code, name, _stops in users:
            out.append((code, name, user_ramps.hex_stops(code, 32)))
        return out

    def _legend_payload_of(self, item):
        try:
            for i in range(item.childCount()):
                p = item.child(i).data(0, ROLE_LEGEND)
                if isinstance(p, dict):
                    return p
        except Exception:
            _log.exception("silent exception in _legend_payload_of")
        return {}

    def _embed_raster_mode_menu(self, menu, item):
        try:
            from PySide6.QtWidgets import QVBoxLayout, QWidget
            from ggis.common.widgets.inputs import GgsColorRampField
            from ggis.core.style import raster_display as rd
        except Exception:
            _log.exception("silent exception in _embed_raster_mode_menu")
            return
        p = self._legend_payload_of(item)
        cur_mode = str(p.get("mode") or rd.MODE_RGB)
        for code, label in rd.RENDER_MODES:
            self._mi(menu, _tr(label),
                     "checkbox_on" if code == cur_mode else "checkbox_off",
                     lambda _c=False, _v=code:
                     self._emit_legend("raster_mode", item, _v))
        menu.addSeparator()
        try:
            box = QWidget(menu)
            vl = QVBoxLayout(box)
            vl.setContentsMargins(6, 4, 6, 6)
            vl.setSpacing(4)
            fld = GgsColorRampField(box, width=self.MENU_FIELD_WIDTH,
                                    height=16)
            fld.setMinimumWidth(self.MENU_FIELD_WIDTH)
            fld.setItemsProvider(self._ramp_items)
            fld.setItems(self._ramp_items(),
                         current=str(p.get("ramp") or rd.RAMP_NONE))
            fld.setInvert(bool(p.get("invert")))
            fld.setEnabled(cur_mode == rd.MODE_PSEUDO)
        except Exception:
            _log.exception("silent exception in _embed_raster_mode_menu")
            return

        def _ramp(c, _item=item):
            self._emit_legend("ramp", _item, c)

        def _invert(on, _item=item):
            self._emit_legend("ramp_invert_set", _item, bool(on))

        fld.rampChanged.connect(_ramp)
        fld.invertChanged.connect(_invert)
        vl.addWidget(fld)
        self._embed(menu, box)

    def _embed_ramp_menu(self, menu, item, p):
        try:
            from PySide6.QtWidgets import QVBoxLayout, QWidget
            from ggis.common.widgets.inputs import GgsColorRampField
            from ggis.core.style.raster_display import (RAMP_NONE)
        except Exception:
            _log.exception("silent exception in _embed_ramp_menu")
            return
        items = self._ramp_items()
        node = self._layer_node_of(item)
        try:
            box = QWidget(menu)
            v = QVBoxLayout(box)
            v.setContentsMargins(6, 4, 6, 6)
            v.setSpacing(4)
            fld = GgsColorRampField(box, width=self.MENU_FIELD_WIDTH,
                                    height=16)
            fld.setMinimumWidth(self.MENU_FIELD_WIDTH)
            fld.setItemsProvider(self._ramp_items)
            fld.setItems(items, current=str(p.get("ramp") or RAMP_NONE))
            fld.setInvert(bool(p.get("invert")))
        except Exception:
            _log.exception("silent exception in _embed_ramp_menu")
            return

        def _ramp(c, _node=node):
            self._emit_legend("ramp", _node, c)

        def _invert(on, _node=node):
            self._emit_legend("ramp_invert_set", _node, bool(on))

        fld.rampChanged.connect(_ramp)
        fld.invertChanged.connect(_invert)
        v.addWidget(fld)
        self._embed(menu, box)

    def _fill_group_menu(self, m, item):
        self._mi(m, _tr("缩放至范围"), "zoom_layer",
                 lambda: self._emit("zoom_group", item), accel="Z")
        m.addSeparator()
        self._mi(m, _tr("重命名"), "edit",
                 lambda: self.editItem(item, COL_NAME), accel="R")
        self._mi(m, _tr("展开"), "expand", lambda: self.expandItem(item), accel="E")
        self._mi(m, _tr("折叠"), "collapse",
                 lambda: self.collapseItem(item), accel="C")
        m.addSeparator()
        self._mi(m, _tr("新建子组"), "folder",
                 lambda: self._emit("newgroup_in", item), accel="G")
        _paste_in = self._mi(m, _tr("粘贴"), "paste_features",
                             lambda: self._emit("paste_into", item), accel="P")
        if _paste_in is not None and not self.paste_available():
            _paste_in.setEnabled(False)
        m.addSeparator()
        self._mi(m, _tr("全部显示"), "visible",
                 lambda: self._set_group_visible(item, True), accel="S")
        self._mi(m, _tr("全部隐藏"), "hidden",
                 lambda: self._set_group_visible(item, False), accel="H")
        m.addSeparator()
        self._mi(m, _tr("移除"), "remove",
                 lambda: self._emit("remove_group", item), accel="D")
        self._mi(m, _tr("属性"), "info",
                 lambda: self._emit("props", item), accel="P")

    def _fill_blank_menu(self, m):
        self._mi(m, _tr("添加数据"), "add_data",
                 lambda: self._emit("add", None), accel="A")
        self._mi(m, _tr("新建组"), "new_group",
                 lambda: self._emit("newgroup", None), accel="G")
        _paste = self._mi(m, _tr("粘贴图层"), "paste_features",
                          lambda: self._emit("paste", None), accel="P")
        if _paste is not None and not self.paste_available():
            _paste.setEnabled(False)
        m.addSeparator()
        self._mi(m, _tr("全部展开"), "expand_all", self.expandAll, accel="E")
        self._mi(m, _tr("全部折叠"), "collapse_all", self.collapseAll, accel="C")

    def _set_group_visible(self, item, on):
        if item is None:
            return
        dock = self._owning_dock()
        tree = getattr(dock, "_tree", None) if dock is not None else None
        if tree is None:
            return
        try:
            gid = str(item.data(COL_NAME, ROLE_GROUP_ID) or "")
        except Exception:
            _log.exception("silent exception in _set_group_visible")
            gid = ""
        if gid:
            tree.set_group_all_visible(gid, bool(on))

    def _legend_key_of(self, item):
        if item is None:
            return None
        try:
            if item.data(COL_NAME, ROLE_KIND) != "legend":
                return None
            parent = item.parent()
            if parent is None:
                return None
            lid = parent.data(COL_NAME, ROLE_LAYER_ID)
            idx = 0
            for i in range(parent.childCount()):
                c = parent.child(i)
                if c is item:
                    break
                if c.data(COL_NAME, ROLE_KIND) == "legend":
                    idx += 1
            return (str(lid or ""), idx)
        except Exception:
            _log.exception("silent exception in _legend_key_of")
            return None

    def _set_menu_item(self, item):
        self._menu_item = item
        self._menu_key = self._legend_key_of(item)
        try:
            self.viewport().update()
        except Exception:
            _log.exception("silent exception in _set_menu_item")

    def _legend_hit(self, pos):
        try:
            item = self.itemAt(pos)
        except Exception:
            _log.exception("silent exception in _legend_hit")
            return False
        if item is None:
            return False
        try:
            return str(item.data(COL_NAME, ROLE_KIND) or "") == "legend"
        except Exception:
            _log.exception("silent exception in _legend_hit")
            return False

    def mousePressEvent(self, event):
        try:
            p = event.position().toPoint()
        except Exception:
            _log.exception("silent exception in mousePressEvent")
            p = event.pos()
        if self._legend_hit(p):
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        try:
            p = event.position().toPoint()
        except Exception:
            _log.exception("silent exception in mouseDoubleClickEvent")
            p = event.pos()
        try:
            is_left = (event.button() == Qt.MouseButton.LeftButton)
        except Exception:
            _log.exception("silent exception in mouseDoubleClickEvent")
            is_left = False
        if is_left and self._legend_hit(p):
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _popup_menu(self, pos):
        item = self.itemAt(pos)
        kind = item.data(COL_NAME, ROLE_KIND) if item is not None else None
        if kind == "legend":
            self._legend_pos = pos
            menu = self.build_menu(item)
            if not menu.actions():
                self._legend_pos = None
                return
            self._set_menu_item(item)
            try:
                menu.exec(self.viewport().mapToGlobal(pos))
            finally:
                self._legend_pos = None
                self._set_menu_item(None)
            return
        if item is not None and item not in self.selectedItems():
            self.setCurrentItem(item)
        self.build_menu(item).exec(self.viewport().mapToGlobal(pos))

    def _emit(self, kind, item):
        dock = self.parent()
        while dock is not None and not isinstance(dock, GgsLayerTreeDock):
            dock = dock.parent()
        if dock is not None:
            dock.nodeActionRequested.emit(kind, item)

    def startDrag(self, actions):
        try:
            items = self.selectedItems()
            if not items:
                return
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData("application/x-qabstractitemmodeldatalist",
                         b"\x00\x00")
            drag.setMimeData(mime)
            try:
                r = self.visualItemRect(items[0])
                if r.isValid() and r.width() > 0:
                    pm = self.viewport().grab(r)
                    if not pm.isNull():
                        drag.setPixmap(pm)
                        pos = self.viewport().mapFromGlobal(QCursor.pos())
                        drag.setHotSpot(QPoint(max(0, pos.x() - r.x()),
                                               max(0, pos.y() - r.y())))
            except Exception:
                _log.exception("silent exception in startDrag preview")
            drag.exec(Qt.DropAction.MoveAction)
        except Exception:
            _log.exception("silent exception in startDrag")

    def _dragged_items(self):
        out = []
        try:
            sel = list(self.selectedItems())
        except Exception:
            _log.exception("silent exception in _dragged_items")
            sel = []
        if not sel:
            try:
                cur = self.currentItem()
            except Exception:
                _log.exception("silent exception in _dragged_items")
                cur = None
            sel = [cur] if cur is not None else []
        ids = set(id(x) for x in sel)
        for it in sel:
            try:
                kind = it.data(COL_NAME, ROLE_KIND)
            except Exception:
                _log.exception("silent exception in _dragged_items")
                continue
            if kind not in ("layer", "group"):
                continue
            p, skip = it.parent(), False
            while p is not None:
                if id(p) in ids:
                    skip = True
                    break
                p = p.parent()
            if not skip:
                out.append(it)
        try:
            out.sort(key=lambda x: self.visualItemRect(x).top())
        except Exception:
            _log.exception("silent exception in _dragged_items")
        return out

    def _drop_slot(self, e, dragged):
        try:
            pos = e.position().toPoint()
        except Exception:
            _log.exception("silent exception in _drop_slot")
            pos = e.pos()
        it = self.itemAt(pos)
        if it is None:
            return (None, 0)
        try:
            kind = it.data(COL_NAME, ROLE_KIND)
        except Exception:
            _log.exception("silent exception in _drop_slot")
            kind = None
        frac_override = None
        if kind not in ("layer", "group"):
            p = it.parent() if it is not None else None
            if p is None:
                return (None, 0)
            it, kind = p, p.data(COL_NAME, ROLE_KIND)
            frac_override = 0.75
        for d in dragged:
            if d is it:
                return None
            p = it.parent()
            while p is not None:
                if p is d:
                    return None
                p = p.parent()
        try:
            r = self.visualItemRect(it)
            h = max(1, int(r.height()))
            frac = (frac_override if frac_override is not None
                    else (pos.y() - r.top()) / float(h))
        except Exception:
            _log.exception("silent exception in _drop_slot")
            frac = 0.6
        if kind == "group" and 0.25 < frac < 0.75:
            n = int(it.childCount())
            k = int(round((frac - 0.25) / 0.5 * (n + 1)))
            return (it, max(0, min(k, n)))
        parent = it.parent()
        try:
            idx = (parent.indexOfChild(it) if parent is not None
                   else self.indexOfTopLevelItem(it))
        except Exception:
            _log.exception("silent exception in _drop_slot")
            return None
        if idx < 0:
            return None
        return (parent, idx + (0 if frac < 0.5 else 1))


    def drop_slot_at(self, pos):
        try:
            pt = QPointF(pos)
        except Exception:
            _log.exception("silent exception in drop_slot_at")
            return None

        class _E:
            @staticmethod
            def position():
                return pt

            @staticmethod
            def pos():
                return QPoint(int(pt.x()), int(pt.y()))

        try:
            return self._drop_slot(_E(), [])
        except Exception:
            _log.exception("silent exception in drop_slot_at")
            return None

    def _external_urls(self, e):
        try:
            mime = e.mimeData()
        except Exception:
            _log.exception("silent exception in _external_urls")
            return []
        try:
            if not mime.hasUrls():
                return []
        except Exception:
            _log.exception("silent exception in _external_urls")
            return []
        try:
            if e.source() is self:
                return []
        except Exception:
            _log.exception("silent exception in _external_urls")
        out = []
        try:
            for u in list(mime.urls()):
                p = u.toLocalFile() or u.toString()
                if p:
                    out.append(p)
        except Exception:
            _log.exception("silent exception in _external_urls")
            return []
        return out

    def _owning_dock(self):
        d = getattr(self, "_dock", None)
        if d is not None:
            return d
        p = self.parent()
        while p is not None:
            if isinstance(p, GgsLayerTreeDock):
                return p
            p = p.parent()
        return None

    def _drop_db_layers(self, e):
        try:
            mime = e.mimeData()
            raw = mime.data("application/x-ggis-uri")
        except Exception:
            _log.exception("silent exception in _drop_db_layers")
            return False
        if raw is None or not raw.data():
            return False
        try:
            lines = [ln.strip() for ln in bytes(raw.data()).decode(
                "utf-8", "replace").splitlines() if ln.strip()]
        except Exception:
            _log.exception("silent exception in _drop_db_layers")
            return False
        if not lines:
            return False
        try:
            urls = [u.toLocalFile() or u.toString()
                    for u in list(mime.urls())]
        except Exception:
            _log.exception("silent exception in _drop_db_layers")
            urls = []

        def _nk(p):
            try:
                return os.path.normcase(os.path.abspath(str(p or "")))
            except Exception:
                _log.exception("silent exception in _nk")
                return str(p or "")

        covered = set()
        for ln in lines:
            try:
                covered.add(_nk(ln.split("|", 1)[0]))
            except Exception:
                _log.exception("silent exception in _drop_db_layers")
        rest = [p for p in urls if p and _nk(p) not in covered]
        win = self.window()
        dock = self._owning_dock()
        slot = None
        try:
            slot = self._drop_slot(e, [])
        except Exception:
            _log.exception("silent exception in _drop_db_layers")
            slot = None
        _counts = {}
        for _ln in lines:
            _c = _ln.split("|", 1)[0]
            _counts[_c] = _counts.get(_c, 0) + 1
        pend = []
        for _c, _n in _counts.items():
            pend.extend([_c] * _n)
        pend.extend(rest)
        if dock is not None:
            try:
                dock.set_pending_drop(
                    pend,
                    slot[0] if slot else None,
                    slot[1] if slot else 0)
            except Exception:
                _log.exception("silent exception in _drop_db_layers")
        if win is None:
            return True
        added = 0
        for ln in reversed(lines):
            try:
                p, name = ln.split("|", 1)
            except ValueError:
                exc_note("_drop_db_layers @ ggis/ui/panels/layertree.py:2360")
                continue
            try:
                if win.ctx.svc("views")._on_view_method("add_uri_layer_from_db",
                                       p, name, False):
                    added += 1
            except Exception:
                _log.exception("silent exception in _drop_db_layers")
                continue
        if rest:
            try:
                self._drop_files(rest, e)
            except Exception:
                _log.exception("silent exception in _drop_db_layers")
                import traceback
                traceback.print_exc()
        if added:
            try:
                win.show_message(_tr("已拖入 {} 个图层").format(added),
                                 win.LEVEL_SUCCESS)
            except Exception:
                _log.exception("silent exception in _drop_db_layers")
        return True

    def _drop_files(self, paths, e):
        win = self.window()
        dock = self._owning_dock()
        slot = None
        try:
            slot = self._drop_slot(e, [])
        except Exception:
            _log.exception("silent exception in _drop_files")
            slot = None
        if dock is not None:
            try:
                dock.set_pending_drop(
                    paths,
                    slot[0] if slot else None,
                    slot[1] if slot else 0)
            except Exception:
                _log.exception("silent exception in _drop_files")
        if win is None:
            return
        try:
            had_layers = bool(win.ctx.svc("views")._on_view_method("has_layers"))
        except Exception:
            _log.exception("silent exception in _drop_files")
            had_layers = True
        single = (len(paths) == 1)
        added = 0
        for p in reversed(list(paths)):
            try:
                if win.ctx.svc("views")._on_view_method("add_uri_layer", p, single):
                    added += 1
            except Exception:
                _log.exception("silent exception in _drop_files")
                continue
        if not added:
            return
        try:
            if not had_layers:
                win._forward_to_map_view("zoom_full")
        except Exception:
            _log.exception("silent exception in _drop_files")
        try:
            win.show_message(_tr("已拖入 {} 个图层").format(added),
                             win.LEVEL_SUCCESS)
        except Exception:
            _log.exception("silent exception in _drop_files")

    def dragEnterEvent(self, e):
        if self._external_urls(e):
            try:
                self.viewport().unsetCursor()
            except Exception:
                _log.exception("silent exception in dragEnterEvent")
            e.acceptProposedAction()
            return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if self._external_urls(e):
            try:
                self.viewport().unsetCursor()
            except Exception:
                _log.exception("silent exception in dragMoveEvent")
            e.acceptProposedAction()
            return
        ok = False
        try:
            ok = self._drop_slot(e, self._dragged_items()) is not None
        except Exception:
            _log.exception("silent exception in dragMoveEvent")
            ok = False
        if ok:
            try:
                self.viewport().unsetCursor()
            except Exception:
                _log.exception("silent exception in dragMoveEvent")
            try:
                super().dragMoveEvent(e)
            except Exception:
                _log.exception("silent exception in dragMoveEvent")
            e.accept()
            return
        try:
            super().dragMoveEvent(e)
        except Exception:
            _log.exception("silent exception in dragMoveEvent")
        e.ignore()
        try:
            self.viewport().setCursor(Qt.CursorShape.ForbiddenCursor)
        except Exception:
            _log.exception("silent exception in dragMoveEvent")

    def dragLeaveEvent(self, e):
        try:
            self.viewport().unsetCursor()
        except Exception:
            _log.exception("silent exception in dragLeaveEvent")
        super().dragLeaveEvent(e)

    def dropEvent(self, e):
        try:
            self.viewport().unsetCursor()
        except Exception:
            _log.exception("silent exception in dropEvent")
        _files = self._external_urls(e)
        if _files:
            try:
                if self._drop_db_layers(e):
                    e.accept()
                    return
            except Exception:
                _log.exception("silent exception in dropEvent")
                import traceback
                traceback.print_exc()
            try:
                self._drop_files(_files, e)
            except Exception:
                _log.exception("silent exception in dropEvent")
                import traceback
                traceback.print_exc()
            e.accept()
            return
        dragged = self._dragged_items()
        if not dragged:
            _log.warning("[拖拽] dropEvent：识别不到被拖条目（selection=%r）",
                         self.selectedItems())
            e.ignore()
            return
        slot = None
        try:
            slot = self._drop_slot(e, dragged)
        except Exception:
            _log.exception("silent exception in dropEvent")
            slot = None
        if slot is None:
            _log.warning("[拖拽] dropEvent：落点被拒（防环/无效），被拖=%s",
                         [it.text(0) for it in dragged])
            e.ignore()
            return
        dock = self._owning_dock()
        tree = getattr(dock, "_tree", None) if dock is not None else None
        if tree is None:
            _log.warning("[拖拽] dropEvent：无绑定图层树模型，忽略移动")
            e.ignore()
            return
        ids = []
        for it in dragged:
            try:
                kind = it.data(COL_NAME, ROLE_KIND)
                nid = (it.data(COL_NAME, ROLE_LAYER_ID)
                       if kind == "layer" else it.data(COL_NAME, ROLE_GROUP_ID))
            except Exception:
                _log.exception("silent exception in dropEvent")
                continue
            if nid:
                ids.append(str(nid))
        if not ids:
            _log.warning("[拖拽] dropEvent：被拖条目解析不出节点 id")
            e.ignore()
            return
        dst_gid = _group_ref(slot[0]) if slot[0] is not None else None
        try:
            ok = tree.move_nodes(ids, dst_gid or None, int(slot[1] or 0))
        except Exception:
            _log.exception("silent exception in dropEvent")
            ok = False
        if not ok:
            _log.warning("[拖拽] dropEvent：模型拒绝移动（防环/无效）被拖=%s "
                         "→ 目标组=%s index=%d", ids, dst_gid, slot[1])
            e.ignore()
            return
        try:
            e.setDropAction(Qt.DropAction.CopyAction)
        except Exception:
            _log.exception("silent exception in dropEvent")
        e.accept()
        _log.info("[拖拽] 命令成功：move %s → 组=%s index=%d",
                  ids, dst_gid or "顶层", slot[1])


class GgsLayerTreeDock(GgsDockWidget):

    nodeActionRequested = Signal(str, object)
    legendActionRequested = Signal(str, object, object)

    def __init__(self, title="图层", parent=None):
        super().__init__(title, parent)
        self.setObjectName("GgsLayerTreeDock")
        self._tree = None

        body = GgsDockBody()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        bar = GgsDockToolbar()
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        bl.setSpacing(2)

        def _btn(text, icon_name, tip, cb):
            b = GgsSmallButtonStyle1(icon_name, _tr(tip), cb)
            bl.addWidget(b)
            return b

        self.b_add = _btn("", "add_data", "添加数据", self._on_add)
        self.b_group = _btn("", "new_group", "新建组", self._on_new_group)
        self.b_del = _btn("", "remove", "移除全部图层", self._on_remove_all)
        bl.addStretch(1)
        self.b_expand = _btn("", "expand_all", "全部展开", self.view_expand_all)
        self.b_collapse = _btn("", "collapse_all", "全部折叠",
                               self.view_collapse_all)
        lay.addWidget(bar)

        self.view = GgsLayerTreeView()
        self.view.layer_dock = self
        self.view.itemExpanded.connect(
            lambda it: self._on_expand_state(it, True))
        self.view.itemCollapsed.connect(
            lambda it: self._on_expand_state(it, False))
        self.view.itemChanged.connect(self._on_item_changed)
        self.view.itemActivated.connect(self._on_item_activated)
        self.view.legendActionRequested.connect(self.legendActionRequested.emit)
        lay.addWidget(self.view, 1)

        self.setWidget(body)

    def root_item(self):
        return self.view.invisibleRootItem()

    def sync_check_states(self):
        self._rebuild_ui()

    def add_group(self, name="组", parent=None, pos=None):
        tree = getattr(self, "_tree", None)
        gid = _group_ref(parent) if parent is not None else None
        if parent is not None and not gid:
            gid = None
        if tree is None:
            it = self._build_item(str(name or _tr("组")), "folder", "group", None)
            it.setCheckState(COL_NAME, Qt.CheckState.Checked)
            if pos is None:
                self.view.addTopLevelItem(it)
            else:
                self.view.insertTopLevelItem(
                    max(0, min(int(pos), self.view.topLevelItemCount())), it)
            return it
        node = tree.add_group(str(name or _tr("组")), gid, pos)
        try:
            if parent is not None:
                self.view.expandItem(parent)
        except Exception:
            _log.exception("silent exception in add_group")
        return self._find_item_by_group_id(node.id)

    def _find_item_by_group_id(self, group_id):
        gid = str(group_id or "")
        if not gid:
            return None

        def _walk(parent):
            n = (parent.childCount() if parent is not None
                 else self.view.topLevelItemCount())
            for i in range(n):
                it = (parent.child(i) if parent is not None
                      else self.view.topLevelItem(i))
                if it is None:
                    continue
                try:
                    if (it.data(COL_NAME, ROLE_KIND) == "group"
                            and str(it.data(COL_NAME, ROLE_GROUP_ID) or "")
                            == gid):
                        return it
                except Exception:
                    continue
                got = _walk(it)
                if got is not None:
                    return got
            return None

        try:
            return _walk(None)
        except Exception:
            _log.exception("silent exception in _find_item_by_group_id")
            return None

    def ensure_group(self, name):
        name = str(name or "")
        for i in range(self.view.topLevelItemCount()):
            it = self.view.topLevelItem(i)
            if (it is not None
                    and it.data(COL_NAME, ROLE_KIND) == "group"
                    and (it.text(COL_NAME) or "") == name):
                return it
        try:
            parent, idx = self.resolve_add_target()
        except Exception:
            _log.exception("silent exception in ensure_group")
            parent, idx = None, 0
        if parent is not None:
            try:
                top = parent
                while top.parent() is not None:
                    top = top.parent()
                i = self.view.indexOfTopLevelItem(top)
                idx = i if i >= 0 else 0
            except Exception:
                _log.exception("silent exception in ensure_group")
                idx = 0
        return self.add_group(name=name, parent=None, pos=max(0, int(idx)))

    def move_layer_to_group(self, layer_id, group):
        if group is None:
            _log.warning("move_layer_to_group: 目标分组为空 (layer=%s)",
                         layer_id)
            return
        it = self._find_item_by_layer_id(str(layer_id))
        if it is None:
            _log.warning("move_layer_to_group: 树里找不到图层节点 layer=%s",
                         layer_id)
            return
        tree = getattr(self, "_tree", None)
        gid = _group_ref(group)
        if tree is None or not gid:
            _log.warning("move_layer_to_group: 无模型树或目标不是分组行"
                         " (layer=%s)", layer_id)
            return
        tree.set_group_expanded(gid, True)
        ok = tree.move_nodes([str(layer_id)], gid, 0)
        if not ok:
            _log.warning("move_layer_to_group: 模型拒绝移动 (layer=%s → 组%s)",
                         layer_id, gid)

    def _attach_legend(self, it, layer):
        for i in range(it.childCount() - 1, -1, -1):
            c = it.child(i)
            if c.data(COL_NAME, ROLE_KIND) == "legend":
                it.removeChild(c)
        if (layer is None or layer.is_table()
                or not (layer.is_vector() or layer.is_raster())):
            return
        rows = _legend_rows(layer)
        if not rows:
            return
        for p in rows:
            child = QTreeWidgetItem([str(p.get("label") or " ")])
            child.setData(COL_NAME, ROLE_KIND, "legend")
            child.setData(COL_NAME, ROLE_LEGEND, p)
            child.setFlags(Qt.ItemFlag.ItemIsEnabled)
            _set_drop_enabled(child, False)
            it.addChild(child)
        self.view.expandItem(it)

    def refresh_legend(self, layer_id=None):
        proj = getattr(self, "_project", None)
        if proj is None:
            return
        root = self.view.invisibleRootItem()

        def _walk(item):
            kind = item.data(COL_NAME, ROLE_KIND)
            lid = item.data(COL_NAME, ROLE_LAYER_ID)
            if kind == "layer" and lid and (layer_id is None
                                            or str(lid) == str(layer_id)):
                try:
                    lyr = proj.layer_by_id(lid)
                except Exception:
                    _log.exception("silent exception in _walk")
                    lyr = None
                self._attach_legend(item, lyr)
            for i in range(item.childCount()):
                _walk(item.child(i))

        for i in range(root.childCount()):
            _walk(root.child(i))

    def _set_item_icon(self, item, icon_name, col=0):
        try:
            item.setData(col, ROLE_ICON_NAME, icon_name)
        except Exception:
            _log.exception("silent exception in _set_item_icon")
        try:
            item.setIcon(col, _icons.icon(icon_name, size=16))
        except Exception:
            _log.exception("silent exception in _set_item_icon")

    def retheme(self):
        def _walk(item):
            name = item.data(0, ROLE_ICON_NAME)
            if name:
                try:
                    item.setIcon(0, _icons.icon(name, size=16))
                except Exception:
                    _log.exception("silent exception in _walk")
            for i in range(item.childCount()):
                _walk(item.child(i))

        root = self.view.invisibleRootItem()
        for i in range(root.childCount()):
            _walk(root.child(i))
        self.view.viewport().update()

    def _push_layer_cmd(self, text, do, undo):
        proj = getattr(self, "_project", None)
        push = getattr(proj, "push_layer_command", None)
        if not callable(push):
            try:
                do()
            except Exception:
                _log.exception("silent exception in _push_layer_cmd")
            return
        try:
            push(text, do, undo)
        except Exception:
            _log.exception("silent exception in _push_layer_cmd")
            try:
                do()
            except Exception:
                _log.exception("silent exception in _push_layer_cmd")

    def _apply_layer_visible(self, layer_id, on, item=None):
        proj = getattr(self, "_project", None)
        lid = str(layer_id)
        try:
            if self._tree is not None:
                self._tree.set_visible(lid, bool(on))
            elif proj is not None:
                lyr = proj.layer_by_id(lid)
                if lyr is not None:
                    proj.set_layer_visible(lyr, bool(on))
        except Exception:
            _log.exception("silent exception in _apply_layer_visible")
        it = item if item is not None else self._find_item_by_layer_id(lid)
        if it is not None:
            was = getattr(self, "_syncing", False)
            self._syncing = True
            try:
                it.setCheckState(
                    COL_NAME, Qt.CheckState.Checked if on
                    else Qt.CheckState.Unchecked)
            except Exception:
                _log.exception("silent exception in _apply_layer_visible")
            finally:
                self._syncing = was
        try:
            self.nodeActionRequested.emit("refresh_view", it)
        except Exception:
            _log.exception("silent exception in _apply_layer_visible")
        try:
            self.view.viewport().update()
        except Exception:
            _log.exception("silent exception in _apply_layer_visible")

    def remove_selected(self):
        proj = getattr(self, "_project", None)
        tree = getattr(self, "_tree", None)
        items = list(self.view.selectedItems())
        if not items:
            return
        ids = set(id(x) for x in items)
        tops = []
        for it in items:
            p, skip = it.parent(), False
            while p is not None:
                if id(p) in ids:
                    skip = True
                    break
                p = p.parent()
            if not skip:
                tops.append(it)
        rec = []

        def _collect(it):
            kind = it.data(COL_NAME, ROLE_KIND)
            if kind == "layer":
                lid = str(it.data(COL_NAME, ROLE_LAYER_ID) or "")
                lyr = (proj.layer_by_id(lid)
                       if (proj is not None and lid) else None)
                p = it.parent()
                g = _group_ref(p) if p is not None else ""
                try:
                    idx = (p.indexOfChild(it) if p is not None
                           else self.view.indexOfTopLevelItem(it))
                except Exception:
                    _log.exception("silent exception in remove_selected")
                    idx = 0
                vis = (bool(tree.is_visible(lid))
                       if (tree is not None and lid) else True)
                if lyr is not None:
                    rec.append((lid, lyr, g, max(0, int(idx)), vis))
                return
            if kind == "group":
                for i in range(it.childCount()):
                    _collect(it.child(i))

        for it in tops:
            _collect(it)

        def _do_remove():
            for it in tops:
                try:
                    kind = it.data(COL_NAME, ROLE_KIND)
                except Exception:
                    _log.exception("silent exception in remove_selected")
                    continue
                if kind == "group":
                    gid = _group_ref(it)
                    if tree is not None and gid:
                        tree.remove_group(gid)
                elif kind == "layer":
                    lid = str(it.data(COL_NAME, ROLE_LAYER_ID) or "")
                    if not lid:
                        continue
                    if tree is not None:
                        tree.remove(lid)
                    elif proj is not None:
                        proj.remove_layer(lid, close=False)
            try:
                self.view.viewport().update()
            except Exception:
                _log.exception("silent exception in remove_selected")

        def _undo_remove():
            self._restore_removed(rec)

        if rec:
            self._push_layer_cmd(_tr("移除图层"), _do_remove, _undo_remove)
        else:
            _do_remove()

    def _restore_removed(self, rec):
        proj = getattr(self, "_project", None)
        if proj is None:
            return
        tree = getattr(self, "_tree", None)
        if tree is not None:
            for r in rec:
                lid = r[0]
                lyr = r[1]
                g = str(r[2]) if len(r) > 2 and r[2] else ""
                idx = int(r[3]) if len(r) > 3 and r[3] is not None else 0
                vis = bool(r[4]) if len(r) > 4 else True
                try:
                    if not tree.has(lid):
                        tree.place_layer(lyr, g or None, idx, vis)
                except Exception:
                    _log.exception("silent exception in _restore_removed")
        else:
            for r in rec:
                lid, lyr = r[0], r[1]
                idx = r[2] if len(r) > 2 else None
                vis = bool(r[3]) if len(r) > 3 else True
                try:
                    if proj.layer_by_id(lid) is None:
                        proj.add_layer(lyr, idx)
                        proj.set_layer_visible(lyr, vis)
                except Exception:
                    _log.exception("silent exception in _restore_removed")
        try:
            self.view.viewport().update()
        except Exception:
            _log.exception("silent exception in _restore_removed")

    def restore_removed_layer(self, lyr, idx=None, visible=True):
        if lyr is None:
            return
        tree = getattr(self, "_tree", None)
        pos = 0
        if tree is not None and idx is not None:
            try:
                pos = max(0, len(tree.entries()) - max(0, int(idx)))
            except Exception:
                _log.exception("silent exception in restore_removed_layer")
                pos = 0
        self._restore_removed(
            [(str(lyr.id()), lyr, "", pos, bool(visible))])

    def view_expand_all(self):
        self.view.expandAll()
        self._sync_expand_to_model(True)

    def view_collapse_all(self):
        self.view.collapseAll()
        self._sync_expand_to_model(False)

    def _sync_expand_to_model(self, on):
        tree = getattr(self, "_tree", None)
        if tree is None:
            return
        for it in _iter_rows(self.view):
            try:
                if it.data(COL_NAME, ROLE_KIND) != "group":
                    continue
                gid = str(it.data(COL_NAME, ROLE_GROUP_ID) or "")
                if gid:
                    tree.set_group_expanded(gid, bool(on))
            except Exception:
                _log.exception("silent exception in _sync_expand_to_model")

    def _on_expand_state(self, item, on):
        if getattr(self, "_syncing", False):
            return
        tree = getattr(self, "_tree", None)
        if tree is None or item is None:
            return
        try:
            if item.data(COL_NAME, ROLE_KIND) != "group":
                return
            gid = str(item.data(COL_NAME, ROLE_GROUP_ID) or "")
        except Exception:
            _log.exception("silent exception in _on_expand_state")
            return
        if gid:
            tree.set_group_expanded(gid, bool(on))

    def bind_tree(self, tree):
        old = getattr(self, "_tree", None)
        if old is not None:
            try:
                old.structureChanged.disconnect(self._rebuild_ui)
            except Exception:
                _log.exception("silent exception in bind_tree")
        self._project = tree._project
        self._tree = tree
        try:
            self.view.set_project(self._project)
        except Exception:
            _log.exception("silent exception in bind_tree")
        try:
            tree.structureChanged.connect(self._rebuild_ui)
        except Exception:
            _log.exception("silent exception in bind_tree")
        self._rebuild_ui()

    def _rebuild_ui(self):
        tree = getattr(self, "_tree", None)
        if tree is None:
            return
        view = self.view
        proj = getattr(self, "_project", None)
        sel_lids, cur_lid, scroll = [], "", 0
        try:
            for it in view.selectedItems():
                if it.data(COL_NAME, ROLE_KIND) == "layer":
                    sel_lids.append(str(it.data(COL_NAME, ROLE_LAYER_ID) or ""))
            cur = view.currentItem()
            if (cur is not None
                    and cur.data(COL_NAME, ROLE_KIND) == "layer"):
                cur_lid = str(cur.data(COL_NAME, ROLE_LAYER_ID) or "")
        except Exception:
            _log.exception("silent exception in _rebuild_ui")
        try:
            sb = view.verticalScrollBar()
            scroll = int(sb.value())
        except Exception:
            _log.exception("silent exception in _rebuild_ui")
            scroll = 0
        self._syncing = True
        try:
            view.blockSignals(True)
            view.clear()
            built = {}

            def _place(nodes, parent_qtw):
                for nd in (nodes or []):
                    if not isinstance(nd, dict):
                        continue
                    if str(nd.get("kind") or "") == "group":
                        g = self._build_item(
                            str(nd.get("name") or _tr("组")),
                            "folder", "group", None)
                        g.setData(COL_NAME, ROLE_GROUP_ID,
                                  str(nd.get("id") or ""))
                        g.setCheckState(
                            COL_NAME,
                            Qt.CheckState.Checked
                            if bool(nd.get("visible", True))
                            else Qt.CheckState.Unchecked)
                        parent_qtw.addChild(g)
                        try:
                            g.setExpanded(bool(nd.get("expanded", True)))
                        except Exception:
                            _log.exception(
                                "silent exception in _rebuild_ui")
                        _place(nd.get("children") or [], g)
                    else:
                        lid = str(nd.get("id") or "")
                        layer = None
                        if proj is not None and lid:
                            try:
                                layer = proj.layer_by_id(lid)
                            except Exception:
                                _log.exception(
                                    "silent exception in _rebuild_ui")
                        if layer is None:
                            continue
                        it = self._build_item(
                            layer.name() or _tr("图层"),
                            self._icon_for_layer(layer),
                            "layer", layer.id())
                        try:
                            it.setCheckState(
                                COL_NAME,
                                Qt.CheckState.Checked
                                if tree.is_visible(lid)
                                else Qt.CheckState.Unchecked)
                        except Exception:
                            _log.exception(
                                "silent exception in _rebuild_ui")
                        parent_qtw.addChild(it)
                        try:
                            self._attach_legend(it, layer)
                        except Exception:
                            _log.exception(
                                "silent exception in _rebuild_ui")
                        built[lid] = it

            try:
                _place(tree.tree_snapshot(), view.invisibleRootItem())
            except Exception:
                _log.exception("silent exception in _rebuild_ui")
            try:
                if cur_lid and cur_lid in built:
                    view.setCurrentItem(built[cur_lid])
                elif sel_lids:
                    first = True
                    for lid in sel_lids:
                        it = built.get(lid)
                        if it is None:
                            continue
                        if first:
                            view.setCurrentItem(it)
                            first = False
                        else:
                            it.setSelected(True)
            except Exception:
                _log.exception("silent exception in _rebuild_ui")
        finally:
            try:
                view.blockSignals(False)
            except Exception:
                _log.exception("silent exception in _rebuild_ui")
            self._syncing = False
        try:
            view.verticalScrollBar().setValue(scroll)
        except Exception:
            _log.exception("silent exception in _rebuild_ui")
        try:
            view.viewport().update()
        except Exception:
            _log.exception("silent exception in _rebuild_ui")

    def restore_expand(self, view_id):
        _ = str(view_id)
        self._rebuild_ui()


    def resolve_add_target(self):
        cur = None
        kind = None
        try:
            cur = self.view.currentItem()
            if cur is not None and not _item_alive(cur):
                cur = None
            if cur is not None:
                kind = cur.data(COL_NAME, ROLE_KIND)
                if kind not in ("layer", "group"):
                    p = cur.parent()
                    cur = p if (p is not None and _item_alive(p)
                                and p.data(COL_NAME, ROLE_KIND) == "layer") \
                        else None
                    kind = "layer" if cur is not None else None
        except Exception:
            _log.exception("silent exception in resolve_add_target")
            cur, kind = None, None
        if cur is None:
            return (None, 0)
        try:
            if kind == "group":
                return (cur, 0)
            parent = cur.parent()
            idx = (parent.indexOfChild(cur) if parent is not None
                   else self.view.indexOfTopLevelItem(cur))
            return (parent, max(0, int(idx)))
        except Exception:
            _log.exception("silent exception in resolve_add_target")
            return (None, 0)

    def take_drop_target(self, path):
        pick = self._pop_pending_slot(_norm_path(path))
        if pick is None:
            return None
        parent = _group_from_ref(self.view, pick.get("ref") or "")
        if parent is not None and not _item_alive(parent):
            return None
        return _group_ref(parent) or None


    def _build_item(self, name, icon_name, kind, layer_id):
        it = QTreeWidgetItem([str(name)])
        it.setData(0, ROLE_KIND, kind)
        if layer_id:
            it.setData(0, ROLE_LAYER_ID, layer_id)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable
                    | Qt.ItemFlag.ItemIsUserCheckable)
        _set_drop_enabled(it, kind == "group")
        self._set_item_icon(it, icon_name)
        return it

    def _icon_for_layer(self, layer):
        if layer.is_table():
            return "table"
        if layer.is_tile():
            return "xyz_tile"
        if layer.is_raster():
            return "raster_layer"
        kind = layer.base_kind()
        return {"point": "point_layer", "line": "line_layer",
                "polygon": "polygon_layer"}.get(kind, "layer")

    def set_pending_drop(self, paths, parent, index):
        try:
            _paths = [x for x in (paths or []) if x]
            base = int(index or 0)
            ref = _group_ref(parent)
            vk = _pending_view_key()
            now = time.time()
            pd = getattr(self, "_pending_drop", None)
            if not isinstance(pd, dict):
                pd = {"by_path": {}, "ts": now}
            by_path = pd.setdefault("by_path", {})
            for k, p in enumerate(_paths):
                key = _norm_path(p)
                if key:
                    by_path.setdefault(key, []).append({
                        "ref": ref, "idx": max(0, base + k),
                        "view": vk, "ts": now})
            pd["ts"] = now
            self._pending_drop = pd if by_path else None
        except Exception:
            _log.exception("silent exception in set_pending_drop")
            self._pending_drop = None

    def discard_pending(self, paths):
        pd = getattr(self, "_pending_drop", None)
        if not isinstance(pd, dict):
            return
        by_path = pd.get("by_path") or {}
        for p in (paths or []):
            key = _norm_path(p)
            slots = by_path.get(key)
            if not slots:
                continue
            slots.pop(0)
            if not slots:
                by_path.pop(key, None)
        if not by_path:
            self._pending_drop = None

    def _pop_pending_slot(self, key):
        pd = getattr(self, "_pending_drop", None)
        if not pd or not isinstance(pd, dict):
            return None
        by_path = pd.get("by_path") or {}
        slots = by_path.get(key)
        if not slots:
            return None
        now = time.time()
        vk = _pending_view_key()
        slots[:] = [s for s in slots
                    if now - float(s.get("ts", 0)) <= 600.0]
        pick = None
        for i, s in enumerate(slots):
            if str(s.get("view", "")) == vk:
                pick = slots.pop(i)
                break
        if not slots:
            by_path.pop(key, None)
        if not by_path:
            self._pending_drop = None
        return pick

    def _find_item_by_layer_id(self, layer_id, parent=None):
        root = parent if parent is not None else self.view.invisibleRootItem()
        for i in range(root.childCount()):
            ch = root.child(i)
            if ch.data(COL_NAME, ROLE_LAYER_ID) == layer_id:
                return ch
            found = self._find_item_by_layer_id(layer_id, ch)
            if found is not None:
                return found
        return None

    def _on_item_changed(self, item, col):
        if self._syncing or col != 0:
            return
        kind = item.data(0, ROLE_KIND)
        tree = getattr(self, "_tree", None)
        proj = getattr(self, "_project", None)
        if kind == "group":
            if tree is None:
                return
            gid = str(item.data(0, ROLE_GROUP_ID) or "")
            if not gid:
                return
            try:
                on = item.checkState(0) == Qt.CheckState.Checked
                if bool(tree.group_visible(gid)) != on:
                    tree.set_group_visible(gid, on)
                text = item.text(0)
                if text and text != tree.group_name(gid):
                    tree.rename_group(gid, text)
            except Exception:
                _log.exception("silent exception in _on_item_changed")
            return
        if kind != "layer":
            return
        layer_id = item.data(0, ROLE_LAYER_ID)
        if not layer_id:
            return
        if proj is None:
            return
        lyr = proj.layer_by_id(layer_id)
        if lyr is None:
            return
        try:
            new_vis = item.checkState(0) == Qt.CheckState.Checked
            old_vis = (bool(tree.is_visible(layer_id))
                       if tree is not None else bool(lyr.is_visible()))
        except Exception:
            _log.exception("silent exception in _on_item_changed")
            new_vis = item.checkState(0) == Qt.CheckState.Checked
            old_vis = not new_vis
        if new_vis != old_vis:
            self._push_layer_cmd(
                _tr("图层显隐"),
                lambda v=new_vis, lid=layer_id, it=item:
                    self._apply_layer_visible(lid, v, it),
                lambda v=old_vis, lid=layer_id, it=item:
                    self._apply_layer_visible(lid, v, it))
        text = item.text(0)
        if text and text != lyr.name():
            try:
                lyr.setName(text)
            except Exception:
                _log.exception("silent exception in _on_item_changed")
        self.nodeActionRequested.emit("refresh_view", item)

    def _on_item_activated(self, item):
        self.nodeActionRequested.emit("props", item)

    def _on_add(self):
        self.nodeActionRequested.emit("add", None)

    def _on_new_group(self):
        try:
            parent, idx = self.resolve_add_target()
        except Exception:
            _log.exception("silent exception in _on_new_group")
            parent, idx = None, 0
        self.add_group(parent=parent, pos=idx)

    def _on_up(self):
        self._move(-1)

    def _on_down(self):
        self._move(1)

    def _on_remove(self):
        self.remove_selected()

    def _on_remove_all(self):
        self.nodeActionRequested.emit("remove_all", None)

    def _move(self, delta):
        tree = getattr(self, "_tree", None)
        it = self.view.currentItem()
        if tree is None or it is None:
            return
        try:
            kind = it.data(COL_NAME, ROLE_KIND)
            nid = (it.data(COL_NAME, ROLE_LAYER_ID)
                   if kind == "layer" else it.data(COL_NAME, ROLE_GROUP_ID))
        except Exception:
            _log.exception("silent exception in _move")
            return
        if not nid:
            return
        p = it.parent()
        try:
            i = (p.indexOfChild(it) if p is not None
                 else self.view.indexOfTopLevelItem(it))
            n = (p.childCount() if p is not None
                 else self.view.topLevelItemCount())
        except Exception:
            _log.exception("silent exception in _move")
            return
        j = i + int(delta)
        if not (0 <= j < n):
            return
        gid = _group_ref(p) if p is not None else None
        dst = j if delta < 0 else j + 1
        try:
            tree.move_nodes([str(nid)], gid or None, dst)
        except Exception:
            _log.exception("silent exception in _move")


class GgsDockToolbar(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsDockToolbar")
