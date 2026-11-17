# -*- coding: utf-8 -*-
import os

from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import (Qt, QSize, QPoint, QRect, QRectF, QPointF,
                            Signal, QTimer, QEvent)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontDatabase,
                           QFontMetrics, QIcon, QPainter, QPainterPath,
                           QPalette, QPen)
from PySide6.QtWidgets import (QApplication, QDialogButtonBox, QWidget,
                               QHBoxLayout, QVBoxLayout, QGridLayout,
                               QFormLayout, QFrame, QLabel, QLayout,
                               QMenu, QScrollArea, QToolButton,
                               QSizePolicy, QLineEdit, QComboBox,
                               QListView, QCompleter, QDoubleSpinBox,
                               QFileDialog, QSlider, QSpinBox,
                               QAbstractSpinBox, QButtonGroup,
                               QCheckBox, QRadioButton, QWidgetAction)

from ggis.common.styling import icons as _icons
from ggis.common.styling import themes as _themes
from ggis.core.app import i18n as _i18n
from ggis.core.app import settings as _settings
from ggis.core.crs import GgsCoordinateReferenceSystem as _GgsCrs
from ggis.core.crs.extent import GgsRectangle
from ggis.common.widgets.buttons import GgsSmallButtonStyle1
from ggis.common.widgets.colors import (GgsColorSwatch,
                                        ramp_strip_pixmap,
                                        _RampMenuItem, _MenuRow)
from ggis.common.widgets.itemviews import GgsListWidget
from ggis.common.base.dialog import GgsDialog
from ggis.io.formats import (RASTER_WRITE_FORMATS,
                             VECTOR_WRITE_FORMATS, TABLE_WRITE_FORMATS,
                             raster_filters, table_filters,
                             vector_filters, vector_supports_layer_name)

_tr = _i18n.tr
from ggis.common.widgets.buttons import (GgsSmallButtonStyle1)


def _tr_filter_text(s):
    return ";;".join(_tr(part) for part in str(s or "").split(";;"))


from ggis.render.map_canvas import GgsMapCanvas
from ggis.render.renderers import render_version as _render_version

_FONT_USABLE = {}


_FONT_USABLE = {}

_RASTER_ONLY_FONTS = frozenset((
    "terminal", "fixedsys", "modern", "system", "roman", "script",
    "courier", "ms serif", "ms sans serif", "small fonts",
    "8514oem", "courier 10,12,15",
))


def _font_preview_ok(family):
    fam = str(family or "").strip()
    if not fam:
        return False
    hit = _FONT_USABLE.get(fam)
    if hit is not None:
        return hit
    ok = True
    if fam.lower() in _RASTER_ONLY_FONTS:
        ok = False
    else:
        try:
            from PySide6.QtGui import QFontDatabase
            ok = bool(QFontDatabase.isSmoothlyScalable(fam))
            if ok:
                try:
                    ok = not bool(QFontDatabase.isPrivateFamily(fam))
                except Exception:
                    exc_note("_font_preview_ok @ ggis/common/widgets/standard.py:1136")
                    pass
        except Exception:
            exc_note("_font_preview_ok @ ggis/common/widgets/standard.py:1138")
            ok = True
    _FONT_USABLE[fam] = ok
    return ok


def _default_font_family():
    cands = []
    try:
        app = QApplication.instance()
        if app is not None:
            cands.append(str(app.font().family() or ""))
    except Exception:
        exc_note("_default_font_family @ ggis/common/widgets/standard.py:1164")
        pass
    try:
        from PySide6.QtGui import QFontDatabase
        cands.append(str(QFontDatabase.systemFont(
            QFontDatabase.SystemFont.GeneralFont).family() or ""))
        cands.append(str(QFont().family() or ""))
    except Exception:
        exc_note("_default_font_family @ ggis/common/widgets/standard.py:1171")
        pass
    for c in cands:
        c = c.strip()
        if not c:
            continue
        try:
            from PySide6.QtGui import QFontDatabase
            if QFontDatabase.isPrivateFamily(c):
                continue
        except Exception:
            exc_note("_default_font_family @ ggis/common/widgets/standard.py:1181")
            pass
        return c
    return ""


def _set_row_font(combo, index, family):
    try:
        combo.setItemData(int(index), QFont(str(family)),
                          Qt.ItemDataRole.FontRole)
    except Exception:
        exc_note("_set_row_font @ ggis/common/widgets/standard.py:1196")
        pass


def _remember_family(combo, index):
    try:
        d = combo.itemData(int(index))
        if isinstance(d, str):
            combo.setProperty("_ggs_family", d)
    except Exception:
        exc_note("_remember_family @ ggis/common/widgets/standard.py:1210")
        pass


def _snap_font_text(combo):
    try:
        le = combo.lineEdit()
        if le is None:
            return
        txt = str(le.text() or "").strip()
        flags = (Qt.MatchFlag.MatchFixedString |
                 Qt.MatchFlag.MatchCaseInsensitive)
        idx = int(combo.findText(txt, flags))
        if idx < 0:
            idx = int(combo.findData(txt))
        if idx < 0:
            idx = int(combo.findData(str(combo.property("_ggs_family") or "")))
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
        combo.setEditText(str(combo.itemText(idx)))
    except Exception:
        exc_note("_snap_font_text @ ggis/common/widgets/standard.py:1239")
        pass


def ggs_combo_value(combo):
    try:
        if int(combo.currentIndex()) >= 0:
            d = combo.currentData()
            if isinstance(d, str):
                return d
        v = combo.property("_ggs_family")
        return str(v) if isinstance(v, str) else ""
    except Exception:
        exc_note("ggs_combo_value @ ggis/common/widgets/standard.py:1257")
        return ""


def ggs_font_select(combo, family):
    fam = str(family or "")
    try:
        i = int(combo.findData(fam))
    except Exception:
        exc_note("ggs_font_select @ ggis/common/widgets/standard.py:1279")
        i = -1
    if i < 0 and fam:
        try:
            combo.addItem(fam, fam)
            if _font_preview_ok(fam):
                _set_row_font(combo, combo.count() - 1, fam)
            i = combo.count() - 1
        except Exception:
            exc_note("ggs_font_select @ ggis/common/widgets/standard.py:1287")
            i = -1
    try:
        i = max(0, i)
        combo.setCurrentIndex(i)
        combo.setEditText(str(combo.itemText(i)))
        _remember_family(combo, i)
    except Exception:
        exc_note("ggs_font_select @ ggis/common/widgets/standard.py:1296")
        pass


def ggs_font_combo(parent=None, with_default=True):
    w = GgsComboBox(parent)
    default_fam = _default_font_family() if with_default else ""

    def _same_as_default(name):
        return bool(default_fam) and str(name).lower() == default_fam.lower()

    def _add_default(combo):
        combo.addItem(default_fam or _tr("（默认）"), default_fam)
        if default_fam and _font_preview_ok(default_fam):
            _set_row_font(combo, 0, default_fam)

    def _add_family(combo, name, force=False):
        if _same_as_default(name):
            return
        if not force and not _font_preview_ok(name):
            return
        combo.addItem(name, name)
        _set_row_font(combo, combo.count() - 1, name)

    if with_default:
        _add_default(w)
    names = []
    try:
        from PySide6.QtGui import QFontDatabase
        names = [str(n) for n in QFontDatabase.families()]
    except Exception:
        exc_note("ggs_font_combo @ ggis/common/widgets/standard.py:1355")
        names = []
    uniq = sorted({x for x in names if x}, key=lambda s: s.lower())
    for n in uniq:
        _add_family(w, n)
    n_real = w.count() - (1 if with_default else 0)
    if n_real < 3 and len(names) >= 10:
        w.clear()
        if with_default:
            _add_default(w)
        for n in uniq:
            if n.strip().lower() in _RASTER_ONLY_FONTS:
                continue
            _add_family(w, n, force=True)
    try:
        w.setEditable(True)
        w.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    except Exception:
        exc_note("ggs_font_combo @ ggis/common/widgets/standard.py:1382")
        pass
    try:
        c = w.completer()
        if c is None:
            c = QCompleter(w.model(), w)
            w.setCompleter(c)
        c.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        c.setFilterMode(Qt.MatchFlag.MatchContains)
        c.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        try:
            c.popup().setItemDelegate(w.itemDelegate())
        except Exception:
            exc_note("ggs_font_combo @ ggis/common/widgets/standard.py:1397")
            pass
    except Exception:
        exc_note("ggs_font_combo @ ggis/common/widgets/standard.py:1399")
        pass
    try:
        le = w.lineEdit()
        if le is not None:
            le.setPlaceholderText(_tr("输入以搜索字体"))
            le.editingFinished.connect(lambda _c=w: _snap_font_text(_c))
    except Exception:
        exc_note("ggs_font_combo @ ggis/common/widgets/standard.py:1406")
        pass
    w.currentIndexChanged.connect(lambda i, _c=w: _remember_family(_c, i))
    _remember_family(w, w.currentIndex())
    return w



class GgsComboBox(QComboBox):

    def showPopup(self):
        super().showPopup()
        try:
            w = self.view().window()
            if w is not None and w.width() > self.width():
                w.setFixedWidth(max(40, int(self.width())))
        except Exception:
            exc_note("showPopup @ ggis/common/widgets/standard.py:1504")
            pass



class GgsLineEdit(QLineEdit):

    def __init__(self, text="", parent=None):
        super().__init__(str(text or ""), parent)
        self.setObjectName("GgsLineEdit")



class GgsSliderSpin(QWidget):

    valueChanged = Signal(int)

    def __init__(self, parent=None, minimum=0, maximum=100, suffix="",
                 spin_width=58):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(int(minimum), int(maximum))
        self.slider.setMinimumWidth(48)
        self.spin = QSpinBox(self)
        self.spin.setRange(int(minimum), int(maximum))
        if suffix:
            self.spin.setSuffix(str(suffix))
        self.spin.setFixedWidth(int(spin_width))
        self.spin.setSizePolicy(QSizePolicy.Policy.Fixed,
                                QSizePolicy.Policy.Fixed)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)

    def _from_slider(self, v):
        if self.spin.value() != int(v):
            self.spin.blockSignals(True)
            try:
                self.spin.setValue(int(v))
            finally:
                self.spin.blockSignals(False)
        self.valueChanged.emit(int(v))

    def _from_spin(self, v):
        if self.slider.value() != int(v):
            self.slider.blockSignals(True)
            try:
                self.slider.setValue(int(v))
            finally:
                self.slider.blockSignals(False)
        self.valueChanged.emit(int(v))

    def value(self):
        return int(self.spin.value())

    def setValue(self, v):
        try:
            v = max(self.spin.minimum(), min(self.spin.maximum(), int(v)))
        except Exception:
            exc_note("setValue @ ggis/common/widgets/standard.py:1633")
            return
        for w in (self.slider, self.spin):
            w.blockSignals(True)
        try:
            self.slider.setValue(v)
            self.spin.setValue(v)
        finally:
            for w in (self.slider, self.spin):
                w.blockSignals(False)

    def setToolTip(self, text):
        super().setToolTip(text)
        for w in (self.slider, self.spin):
            try:
                w.setToolTip(text)
            except Exception:
                exc_note("setToolTip @ ggis/common/widgets/standard.py:1650")
                pass



class GgsColorField(QWidget):

    colorChanged = Signal(object)

    def __init__(self, color="#FFFFFF", parent=None, shape="rect",
                 width=96, height=22, with_alpha=True):
        super().__init__(parent)
        self.setObjectName("GgsColorField")
        self._color = QColor(color)
        self._with_alpha = bool(with_alpha)
        self.setFixedSize(QSize(int(width), int(height)))
        self.setToolTip(_i18n.tr("点击选择颜色"))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.swatch = GgsColorSwatch(self._color, shape, self)
        self.swatch.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Expanding)
        self.swatch.setToolTip(_i18n.tr("点击打开颜色对话框"))
        self.arrow = QToolButton(self)
        self.arrow.setObjectName("GgsColorArrow")
        self.arrow.setFixedWidth(20)
        self.arrow.setSizePolicy(QSizePolicy.Policy.Fixed,
                                 QSizePolicy.Policy.Expanding)
        self.arrow.setIcon(self.combo_arrow_icon())
        self.arrow.setIconSize(QSize(10, 10))
        self.arrow.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow.setToolTip(_i18n.tr("快速选择颜色"))
        self.arrow.clicked.connect(self.pick)
        self.swatch.installEventFilter(self)
        lay.addWidget(self.swatch, 1)
        lay.addWidget(self.arrow)

    def shape(self):
        try:
            return str(self.swatch.shape() or "rect")
        except Exception:
            exc_note("shape @ ggis/common/widgets/standard.py:1881")
            return "rect"

    def setShape(self, shape):
        try:
            self.swatch.setShape(shape)
        except Exception:
            exc_note("setShape @ ggis/common/widgets/standard.py:1899")
            pass

    @staticmethod
    def combo_arrow_icon():
        try:
            subdir = "dark" if _icons.is_dark() else "light"
            return QIcon(os.path.join(_themes._ICON_DIR, subdir,
                                      "combo_arrow.svg"))
        except Exception:
            exc_note("combo_arrow_icon @ ggis/common/widgets/standard.py:1910")
            return QIcon()

    def eventFilter(self, obj, ev):
        if obj is self.swatch and ev.type() == QEvent.Type.MouseButtonPress:
            if self.isEnabled():
                self.choose()
            return True
        return super().eventFilter(obj, ev)

    def changeEvent(self, e):
        if e.type() == QEvent.Type.EnabledChange:
            cur = (Qt.CursorShape.PointingHandCursor if self.isEnabled()
                   else Qt.CursorShape.ArrowCursor)
            for w in (self, self.swatch, self.arrow):
                try:
                    w.setCursor(cur)
                except Exception:
                    exc_note("changeEvent @ ggis/common/widgets/standard.py:1937")
                    pass
        super().changeEvent(e)

    def choose(self):
        if not self.isEnabled():
            return
        from ggis.ui.dialogs.color import GgsColorDialog
        c = GgsColorDialog.getColor(self._color, self,
                                   with_alpha=self._with_alpha,
                                   shape=self.shape())
        if c.isValid():
            self.setColor(c)

    def pick(self):
        if not self.isEnabled():
            return
        from ggis.ui.dialogs.color import popup_color
        popup_color(self, self._color, self.setColor,
                    with_alpha=self._with_alpha, shape=self.shape())

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        c = QColor(color)
        if c.isValid():
            self._color = c
            self.swatch.setColor(c)
            self.colorChanged.emit(QColor(c))

    def alpha(self):
        return int(self._color.alpha())

    def setAlpha(self, value):
        if not self.isEnabled():
            return
        c = QColor(self._color)
        c.setAlpha(max(0, min(255, int(value))))
        self.setColor(c)




class GgsCrsSelector(QWidget):

    crsChanged = Signal(object)
    baseChanged = Signal(object)

    BASE_BASEMAP = "basemap"

    def __init__(self, parent=None, crs="", label=None):
        super().__init__(parent)
        self.setObjectName("GgsCrsSelector")
        self._authid = ""
        self._base = ""
        self._base_authid = ""
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if label:
            lay.addWidget(QLabel(_tr(label)))
        self._base_label = ""
        self.cmb = GgsComboBox(self)
        self.cmb.addItem(self._base_label, self.BASE_BASEMAP)
        self.cmb.currentIndexChanged.connect(self._on_combo)
        lay.addWidget(self.cmb, 1)
        self.btn = GgsSmallButtonStyle1("crs", _tr("选择坐标系"), self._choose, 16)
        lay.addWidget(self.btn)
        self.setCrs(crs, emit=False)

    def _dup_index(self, disp, auth):
        auth = (auth or "").strip()
        if auth:
            if auth == self._base_authid:
                bi = self.cmb.findData(self.BASE_BASEMAP)
                if bi >= 0:
                    return bi
            idx = self.cmb.findData(auth)
            if idx >= 0:
                return idx
        d = (disp or "").strip()
        if d:
            for i in range(self.cmb.count()):
                try:
                    if (self.cmb.itemText(i) or "").strip() == d:
                        return i
                except Exception:
                    exc_note("_dup_index @ ggis/common/widgets/standard.py:2169")
                    continue
        return -1

    def set_layers(self, items):
        cur = self.cmb.currentData()
        self.cmb.blockSignals(True)
        self.cmb.clear()
        self.cmb.addItem(self._base_label, self.BASE_BASEMAP)
        seen = set()
        for it in (items or []):
            disp, auth = self._entry_of(it)
            if not auth:
                continue
            if auth in seen or self._dup_index(disp, auth) >= 0:
                continue
            seen.add(auth)
            self.cmb.addItem(disp, auth)
        if cur:
            idx = self.cmb.findData(cur)
            if idx < 0:
                _lbl = cur
                try:
                    _c = _GgsCrs.from_user_input(cur)
                    if _c is not None:
                        _lbl = _c.display_label() or cur
                except Exception:
                    exc_note("set_layers @ ggis/common/widgets/standard.py:2208")
                    pass
                idx = self._dup_index(_lbl, cur)
                if idx < 0:
                    self.cmb.addItem(_lbl, cur)
                    idx = self.cmb.count() - 1
            self.cmb.setCurrentIndex(idx)
        else:
            self.cmb.setCurrentIndex(0)
        self.cmb.blockSignals(False)
        self._sync_state(self.cmb.currentIndex(), emit=False)

    @staticmethod
    def _entry_of(it):
        c = None
        if isinstance(it, str):
            auth = it.strip()
            try:
                c = _GgsCrs.from_user_input(auth)
            except Exception:
                exc_note("_entry_of @ ggis/common/widgets/standard.py:2235")
                c = None
        else:
            auth = ""
            try:
                c = it.crs()
            except Exception:
                exc_note("_entry_of @ ggis/common/widgets/standard.py:2241")
                c = None
            if c is not None:
                try:
                    auth = (c.authid() or "").strip()
                except Exception:
                    exc_note("_entry_of @ ggis/common/widgets/standard.py:2246")
                    auth = ""
        disp = auth
        if c is not None:
            try:
                disp = c.display_label() or auth
            except Exception:
                exc_note("_entry_of @ ggis/common/widgets/standard.py:2252")
                disp = auth
        return disp, auth

    def _on_combo(self, idx):
        self._sync_state(idx, emit=True)

    def _sync_state(self, idx, emit):
        data = self.cmb.itemData(idx) or ""
        if data == self.BASE_BASEMAP:
            new_base, new_auth = self.BASE_BASEMAP, ""
        else:
            new_base, new_auth = "", data
        changed_base = (new_base != self._base)
        changed_auth = (new_auth != self._authid)
        self._base = new_base
        self._authid = new_auth
        if emit:
            if changed_base:
                self.baseChanged.emit(new_base)
            if changed_auth:
                self.crsChanged.emit(new_auth)

    def _choose(self):
        try:
            from ggis.ui.dialogs.crs import GgsCrsDialog
        except Exception as e:
            exc_note("_choose @ ggis/common/widgets/standard.py:2279")
            self._choose_failed(e)
            return
        try:
            dlg = GgsCrsDialog(self.window(), current=self._authid)
        except Exception as e:
            exc_note("_choose @ ggis/common/widgets/standard.py:2284")
            self._choose_failed(e)
            return
        if dlg.exec():
            self.setCrs(dlg.selected_authid())

    def _choose_failed(self, err):
        try:
            from ggis.common.base.dialog import GgsMsgBox
            GgsMsgBox.warn(self, _tr("无法打开坐标系选择框"),
                           _tr("原因：{0}").format(err))
        except Exception:
            exc_note("_choose_failed @ ggis/common/widgets/standard.py:2296")
            pass

    def set_base_crs(self, crs):
        obj = None
        if isinstance(crs, _GgsCrs):
            obj = crs
        elif crs:
            try:
                obj = _GgsCrs.from_user_input(crs)
            except Exception:
                exc_note("set_base_crs @ ggis/common/widgets/standard.py:2314")
                obj = None
        label = ""
        if obj is not None and obj.is_valid():
            try:
                label = obj.display_label() or ""
            except Exception:
                exc_note("set_base_crs @ ggis/common/widgets/standard.py:2320")
                label = ""
        if label:
            self._base_label = label
            try:
                self._base_authid = (obj.authid() or "").strip()
            except Exception:
                exc_note("set_base_crs @ ggis/common/widgets/standard.py:2327")
                self._base_authid = ""
            self.cmb.blockSignals(True)
            try:
                bi = self.cmb.findData(self.BASE_BASEMAP)
                if bi >= 0:
                    self.cmb.setItemText(bi, label)
                else:
                    _cur = self.cmb.currentData()
                    self.cmb.insertItem(0, label, self.BASE_BASEMAP)
                    if _cur and _cur != self.BASE_BASEMAP:
                        _ni = self.cmb.findData(_cur)
                        if _ni >= 0:
                            self.cmb.setCurrentIndex(_ni)
            finally:
                self.cmb.blockSignals(False)
            self.cmb.blockSignals(True)
            try:
                _keep = self.cmb.currentData()
                _ba = self._base_authid
                _lb = label.strip()
                for i in range(self.cmb.count() - 1, -1, -1):
                    if self.cmb.itemData(i) == self.BASE_BASEMAP:
                        continue
                    _ia = self.cmb.itemData(i) or ""
                    _it = (self.cmb.itemText(i) or "").strip()
                    if (_ba and _ia == _ba) or (_lb and _it == _lb):
                        self.cmb.removeItem(i)
                if _keep:
                    _ki = self.cmb.findData(_keep)
                    if _ki >= 0:
                        self.cmb.setCurrentIndex(_ki)
            finally:
                self.cmb.blockSignals(False)
            self._sync_state(self.cmb.currentIndex(), emit=False)

    def base(self):
        return self._base

    def setBase(self, base, emit=True):
        self.cmb.blockSignals(True)
        if base == self.BASE_BASEMAP:
            idx = self.cmb.findData(self.BASE_BASEMAP)
        else:
            idx = self.cmb.findData(self.BASE_BASEMAP)
        if idx < 0:
            idx = 0
        self.cmb.setCurrentIndex(idx)
        self.cmb.blockSignals(False)
        self._sync_state(idx, emit=emit)

    def crs(self):
        return self._authid

    def crsObject(self):
        if not self._authid:
            return None
        c = _GgsCrs.from_user_input(self._authid)
        return c if (c is not None and c.is_valid()) else None

    def is_defined(self):
        return self.crsObject() is not None

    def setCrs(self, crs, emit=True):
        if crs == self.BASE_BASEMAP:
            self.setBase(self.BASE_BASEMAP, emit=emit)
            return
        a = ""
        if isinstance(crs, _GgsCrs):
            a = crs.authid() if crs.is_valid() else ""
        elif crs:
            obj = _GgsCrs.from_user_input(crs)
            if obj is not None and obj.is_valid():
                a = obj.authid()
            elif isinstance(crs, str):
                a = crs.strip()
        self.cmb.blockSignals(True)
        idx = self.cmb.findData(a) if a else self.cmb.findData(self.BASE_BASEMAP)
        if idx < 0 and a:
            disp = a
            try:
                obj = _GgsCrs.from_user_input(a)
                if obj is not None and obj.is_valid():
                    disp = obj.display_label() or a
            except Exception:
                exc_note("setCrs @ ggis/common/widgets/standard.py:2430")
                disp = a
            idx = self._dup_index(disp, a)
            if idx < 0:
                self.cmb.addItem(disp, a)
                idx = self.cmb.count() - 1
        if idx < 0:
            idx = 0
        self.cmb.setCurrentIndex(idx)
        self.cmb.blockSignals(False)
        self._sync_state(idx, emit=emit)
        if self.cmb.currentIndex() >= 0 and \
                self.cmb.itemData(self.cmb.currentIndex()) != self.BASE_BASEMAP:
            if not self._base_label:
                _bi = self.cmb.findData(self.BASE_BASEMAP)
                if _bi >= 0:
                    self.cmb.blockSignals(True)
                    try:
                        self.cmb.removeItem(_bi)
                    finally:
                        self.cmb.blockSignals(False)


def relax_wide_inputs(root, limit=96, spin_w=56, combo_w=72):
    out = []
    try:
        from PySide6.QtWidgets import QAbstractSpinBox, QComboBox
        ignored = QSizePolicy.Policy.Ignored
    except Exception:
        exc_note("relax_wide_inputs @ ggis/common/widgets/standard.py:3758")
        return out
    targets = [(w, spin_w) for w in root.findChildren(QAbstractSpinBox)
               if not isinstance(w.parent(), GgsSliderSpin)]
    targets += [(w, combo_w) for w in root.findChildren(QComboBox)]
    try:
        targets += [(w, 120) for w in root.findChildren(GgsColorRampField)]
    except Exception:
        exc_note("relax_wide_inputs @ ggis/common/widgets/standard.py:3779")
        pass
    for w, min_w in targets:
        try:
            if w.sizePolicy().horizontalPolicy() == ignored:
                continue
            if w.minimumSizeHint().width() <= int(limit):
                continue
            sp = w.sizePolicy()
            sp.setHorizontalPolicy(ignored)
            w.setSizePolicy(sp)
            w.setMinimumWidth(int(min_w))
            out.append(w)
        except Exception:
            exc_note("relax_wide_inputs @ ggis/common/widgets/standard.py:3792")
            continue
    return out



def _log_exc(msg):
    try:
        from ggis.app import get_logger
        get_logger(__name__).exception(msg)
    except Exception:
        exc_note("_log_exc @ ggis/common/widgets/standard.py:4255")
        pass



class GgsColorRampField(QWidget):

    rampChanged = Signal(str)
    invertChanged = Signal(bool)

    def __init__(self, parent=None, width=150, height=16, with_invert=True):
        super().__init__(parent)
        self._w = int(width)
        self._h = int(height)
        self._code = ""
        self._items = []
        self._by_code = {}
        self._invert = False
        self._icon_w = 0
        self._scroll = None
        self._inner = None
        self._row_widgets = {}
        self._wrap_custom = None
        self._wrap_names = None
        self._lbl_custom = None

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        self.btn = QToolButton(self)
        self.btn.setObjectName("GgsRampField")
        self.btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.btn.setIconSize(QSize(self._w, self._h))
        self.btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setFixedHeight(self._h + 10)
        self.btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Fixed)
        self.btn.installEventFilter(self)
        self._menu = QMenu(self.btn)
        self._menu.setToolTipsVisible(True)
        self.btn.setMenu(self._menu)
        try:
            self._menu.aboutToShow.connect(self._before_menu_show)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:4365")
            pass
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(40)
        self._hover_timer.timeout.connect(self._poll_hover)
        try:
            self._menu.aboutToShow.connect(self._start_hover_poll)
            self._menu.aboutToHide.connect(self._stop_hover_poll)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:4378")
            pass
        v.addWidget(self.btn)

        self.chk_invert = None
        if with_invert:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            self.chk_invert = QCheckBox(_i18n.tr("翻转颜色"), self)
            self.chk_invert.setToolTip(
                _i18n.tr("把色带高低端对调（如高程用深色表示高处时）"))
            self.chk_invert.toggled.connect(self._on_invert_toggled)
            row.addWidget(self.chk_invert)
            row.addStretch(1)
            v.addLayout(row)

        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def eventFilter(self, obj, ev):
        if obj is getattr(self, "btn", None):
            try:
                t = ev.type()
            except Exception:
                exc_note("eventFilter @ ggis/common/widgets/standard.py:4409")
                t = None
            if t in (QEvent.Type.Resize, QEvent.Type.Show):
                try:
                    if self._target_icon_w() != self._icon_w:
                        self._apply_ramp_icon()
                except Exception:
                    exc_note("eventFilter @ ggis/common/widgets/standard.py:4415")
                    pass
                try:
                    self._sync_menu_width()
                except Exception:
                    exc_note("eventFilter @ ggis/common/widgets/standard.py:4419")
                    pass
        return super().eventFilter(obj, ev)

    def _preferred_height(self):
        try:
            return int(self.layout().sizeHint().height())
        except Exception:
            exc_note("_preferred_height @ ggis/common/widgets/standard.py:4428")
            return int(getattr(self, "_h", 16)) + 10 + 24

    def sizeHint(self):
        return QSize(max(int(getattr(self, "_w", 150) or 150), 60),
                     self._preferred_height())

    def minimumSizeHint(self):
        try:
            ext = int(self.btn.fontMetrics().horizontalAdvance("\u25bc"))
        except Exception:
            exc_note("minimumSizeHint @ ggis/common/widgets/standard.py:4464")
            ext = 12
        return QSize(max(40, ext + 10), self._preferred_height())

    MAX_VISIBLE_ROWS = 10
    SHOW_NAMES_KEY = "ramp_show_names"

    def setItems(self, items, current=None):
        menu = self._menu
        menu.clear()
        self._items = []
        self._by_code = {}
        self._row_widgets = {}

        scroll = QScrollArea(menu)
        scroll.setObjectName("GgsRampList")
        scroll.setFrameShape(QFrame.Shape.Box)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        for code, label, colors in items:
            code, label = str(code), str(label)
            wgt = _RampMenuItem(code, label, colors, self._w, self._h, inner)
            wgt.picked.connect(self._pick)
            lay.addWidget(wgt, 0, Qt.AlignmentFlag.AlignLeft)
            self._row_widgets[code] = wgt
            self._items.append((code, label, colors))
            self._by_code[code] = (label, colors)
        inner.adjustSize()
        scroll.setWidget(inner)
        self._scroll = scroll
        self._inner = inner
        act = QWidgetAction(menu)
        act.setDefaultWidget(scroll)
        menu.addAction(act)

        wrap = QWidget(menu)
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 6, 0, 3)
        wl.setSpacing(0)
        self._lbl_custom = _MenuRow(_i18n.tr("设置配色方案格式…"), wrap)
        self._lbl_custom.setToolTip(
            _i18n.tr("打开配色方案编辑器（基于当前色带）"))
        self._lbl_custom.clicked.connect(self._on_custom_clicked)
        wl.addWidget(self._lbl_custom)
        act_c = QWidgetAction(menu)
        act_c.setDefaultWidget(wrap)
        menu.addAction(act_c)
        self._act_custom = act_c
        self._wrap_custom = wrap

        nwrap = QWidget(menu)
        nl = QVBoxLayout(nwrap)
        nl.setContentsMargins(8, 2, 8, 6)
        nl.setSpacing(0)
        self._chk_names = QCheckBox(_i18n.tr("显示名称"), nwrap)
        self._chk_names.setChecked(self._show_names_pref())
        self._chk_names.toggled.connect(self._on_show_names)
        nl.addWidget(self._chk_names)
        act2 = QWidgetAction(menu)
        act2.setDefaultWidget(nwrap)
        menu.addAction(act2)
        self._wrap_names = nwrap

        self._apply_show_names()
        if current is not None:
            self.setRamp(current)
        elif self._items:
            self.setRamp(self._items[0][0])
        self._sync_menu_width()

    def _show_names_pref(self):
        try:
            return bool(_settings.get(self.SHOW_NAMES_KEY, False))
        except Exception:
            exc_note("_show_names_pref @ ggis/common/widgets/standard.py:4584")
            return False

    def _on_show_names(self, on):
        try:
            _settings.set(self.SHOW_NAMES_KEY, bool(on), persist=True)
        except Exception:
            exc_note("_on_show_names @ ggis/common/widgets/standard.py:4590")
            pass
        self._apply_show_names()
        self._sync_menu_width()

    def _apply_show_names(self):
        chk = getattr(self, "_chk_names", None)
        on = bool(chk is not None and chk.isChecked())
        for wgt in getattr(self, "_row_widgets", {}).values():
            try:
                wgt.setShowName(on)
            except Exception:
                exc_note("_apply_show_names @ ggis/common/widgets/standard.py:4604")
                pass

    def setShowNames(self, on):
        try:
            self._chk_names.setChecked(bool(on))
        except Exception:
            exc_note("setShowNames @ ggis/common/widgets/standard.py:4611")
            pass

    def ramp(self):
        return self._code

    @staticmethod
    def _code_exists(code):
        code = str(code or "")
        if not code:
            return False
        try:
            from ggis.core.style import raster_display as rd
            if rd.ramp_control_points(code):
                return True
        except Exception:
            exc_note("_code_exists @ ggis/common/widgets/standard.py:4635")
            pass
        try:
            from ggis.core.style import user_ramps
            return bool(user_ramps.is_user(code) and user_ramps.stops_of(code))
        except Exception:
            exc_note("_code_exists @ ggis/common/widgets/standard.py:4640")
            return False

    def setRamp(self, code):
        code = str(code or "")
        if code not in self._by_code and self._items:
            if self._code_exists(code):
                self.reload_items()
            else:
                code = self._items[0][0]
        self._code = code
        for cd, wgt in getattr(self, "_row_widgets", {}).items():
            try:
                wgt.setCurrent(cd == code)
            except Exception:
                exc_note("setRamp @ ggis/common/widgets/standard.py:4665")
                pass
        self._apply_ramp_icon()

    def setInvert(self, on):
        on = bool(on)
        try:
            self.chk_invert.blockSignals(True)
            self.chk_invert.setChecked(on)
        except Exception:
            exc_note("setInvert @ ggis/common/widgets/standard.py:4680")
            pass
        finally:
            try:
                self.chk_invert.blockSignals(False)
            except Exception:
                exc_note("setInvert @ ggis/common/widgets/standard.py:4685")
                pass
        if on != self._invert:
            self._invert = on
            self._apply_ramp_icon()

    def _on_invert_toggled(self, on):
        self._invert = bool(on)
        self._apply_ramp_icon()
        self.invertChanged.emit(bool(on))

    def _on_custom_clicked(self):
        try:
            self._menu.close()
        except Exception:
            exc_note("_on_custom_clicked @ ggis/common/widgets/standard.py:4705")
            pass
        QTimer.singleShot(0, self._open_custom)

    def _open_custom(self):
        try:
            from ggis.ui.dialogs.color_ramp import edit_ramp
        except Exception:
            _log_exc("导入配色方案编辑器失败")
            return
        try:
            code = edit_ramp(self, self._code)
        except Exception:
            _log_exc("打开配色方案编辑器失败")
            return
        if not code:
            return
        self.reload_items()
        self.setRamp(code)
        self.rampChanged.emit(code)

    def reload_items(self):
        provider = getattr(self, "_items_provider", None)
        if getattr(self, "_reloading", False):
            return
        self._reloading = True
        try:
            if provider is None:
                try:
                    from ggis.core.style import user_ramps
                    merged = list(self._items)
                    have = {c for c, _l, _s in merged}
                    for code, name, _stops in user_ramps.entries():
                        if code not in have:
                            merged.append((code, name,
                                           user_ramps.hex_stops(code, 32)))
                    self.setItems(merged, current=self._code)
                except Exception:
                    exc_note("reload_items @ ggis/common/widgets/standard.py:4763")
                    pass
                return
            try:
                items = provider()
                self.setItems(items, current=self._code)
            except Exception:
                exc_note("reload_items @ ggis/common/widgets/standard.py:4769")
                pass
        finally:
            self._reloading = False

    def _before_menu_show(self):
        self.reload_items()

    def _hover_targets(self):
        out = []
        try:
            for code, _l, _c in self._items:
                w = self._row_widgets.get(code)
                if w is not None:
                    out.append(w)
        except Exception:
            exc_note("_hover_targets @ ggis/common/widgets/standard.py:4795")
            pass
        for name in ("_lbl_custom", "_chk_names"):
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "set_hover"):
                out.append(w)
        return out

    def _start_hover_poll(self):
        try:
            self._hover_timer.start()
        except Exception:
            exc_note("_start_hover_poll @ ggis/common/widgets/standard.py:4807")
            pass
        self._poll_hover()

    def _stop_hover_poll(self):
        try:
            self._hover_timer.stop()
        except Exception:
            exc_note("_stop_hover_poll @ ggis/common/widgets/standard.py:4815")
            pass
        for w in self._hover_targets():
            try:
                w.set_hover(False)
            except Exception:
                exc_note("_stop_hover_poll @ ggis/common/widgets/standard.py:4820")
                pass

    def _poll_hover(self):
        try:
            if not self._menu.isVisible():
                self._hover_timer.stop()
                return
        except Exception:
            exc_note("_poll_hover @ ggis/common/widgets/standard.py:4835")
            return
        try:
            pos = QCursor.pos()
        except Exception:
            exc_note("_poll_hover @ ggis/common/widgets/standard.py:4839")
            return
        targets = self._hover_targets()
        hit = None
        for w in targets:
            try:
                if not w.isVisible():
                    continue
                rect = QRect(w.mapToGlobal(QPoint(0, 0)), w.size())
                if rect.contains(pos):
                    hit = w
                    break
            except Exception:
                exc_note("_poll_hover @ ggis/common/widgets/standard.py:4851")
                continue
        for w in targets:
            try:
                w.set_hover(w is hit)
            except Exception:
                exc_note("_poll_hover @ ggis/common/widgets/standard.py:4856")
                pass

    def setItemsProvider(self, fn):
        self._items_provider = fn

    def invert(self):
        return bool(self._invert)

    def _arrow_pad(self):
        try:
            if self.btn.popupMode() == QToolButton.ToolButtonPopupMode.InstantPopup:
                return 20
        except Exception:
            exc_note("_arrow_pad @ ggis/common/widgets/standard.py:4877")
            pass
        return 4

    def _target_icon_w(self, avail=None):
        w = int(self.btn.width()) if avail is None else int(avail)
        w = max(24, w - self._arrow_pad())
        return max(24, (w // 8) * 8)

    def _apply_ramp_icon(self):
        hit = self._by_code.get(self._code)
        if hit is None:
            self._icon_w = 0
            self.btn.setIcon(QIcon())
            self.btn.setToolTip("")
            return
        label, colors = hit
        if self._invert:
            colors = list(reversed(list(colors or [])))
        w = self._target_icon_w()
        self._icon_w = w
        aw = max(12, int(self._arrow_pad()))
        h = int(self._h)
        full_w = w + aw
        pm = ramp_strip_pixmap(colors, w, h)
        try:
            from PySide6.QtGui import QPixmap, QPolygonF, QPalette
            out = QPixmap(full_w, h + 6)
            out.fill(Qt.GlobalColor.transparent)
            p = QPainter(out)
            try:
                p.drawPixmap(0, 3, pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(self.btn.palette().color(QPalette.ColorRole.ButtonText))
                cx = w + aw / 2.0
                cy = (h + 6) / 2.0
                s = 3.5
                p.drawPolygon(QPolygonF([
                    QPointF(cx - s, cy - s * 0.6),
                    QPointF(cx + s, cy - s * 0.6),
                    QPointF(cx, cy + s * 0.8)]))
            finally:
                p.end()
            if self.btn.iconSize() != QSize(full_w, h + 6):
                self.btn.setIconSize(QSize(full_w, h + 6))
            self.btn.setIcon(QIcon(out))
        except Exception:
            exc_note("_apply_ramp_icon @ ggis/common/widgets/standard.py:4946")
            if self.btn.iconSize() != QSize(w, h):
                self.btn.setIconSize(QSize(w, h))
            self.btn.setIcon(QIcon(pm))
        self.btn.setToolTip(label)

    def _sync_menu_width(self):
        scroll = getattr(self, "_scroll", None)
        inner = getattr(self, "_inner", None)
        if scroll is None or inner is None:
            return
        try:
            target = max(120, int(self.btn.width()) - 12)
        except Exception:
            exc_note("_sync_menu_width @ ggis/common/widgets/standard.py:4972")
            target = max(120, int(getattr(self, "_w", 150)))
        try:
            sbw = int(scroll.verticalScrollBar().sizeHint().width())
        except Exception:
            exc_note("_sync_menu_width @ ggis/common/widgets/standard.py:4976")
            sbw = 14
        item_w = max(40, target - sbw - 18)
        for code, _l, _c in self._items:
            wgt = self._row_widgets.get(code)
            if wgt is None:
                continue
            try:
                wgt.set_width(item_w)
            except Exception:
                exc_note("_sync_menu_width @ ggis/common/widgets/standard.py:4986")
                pass
        rows = max(1, len(self._items))
        vis = min(rows, int(self.MAX_VISIBLE_ROWS))
        row_h = int(self._h) + 8 + 2
        try:
            inner.adjustSize()
        except Exception:
            exc_note("_sync_menu_width @ ggis/common/widgets/standard.py:4998")
            pass
        scroll.setFixedWidth(item_w + 10 + 6 + sbw + 4)
        scroll.setFixedHeight(vis * row_h + 8)
        in_w = item_w + 10 + 6 + sbw + 4
        for _wrap in (getattr(self, "_wrap_custom", None),
                      getattr(self, "_wrap_names", None)):
            if _wrap is None:
                continue
            try:
                _wrap.setMinimumWidth(in_w)
            except Exception:
                exc_note("_sync_menu_width @ ggis/common/widgets/standard.py:5012")
                pass

    def _pick(self, code):
        self.setRamp(code)
        try:
            self._menu.close()
        except Exception:
            exc_note("_pick @ ggis/common/widgets/standard.py:5022")
            pass
        self.rampChanged.emit(self._code)



class GgsExtentPicker(QWidget):

    extentChanged = Signal()
    modeChanged = Signal(str)

    MODE_VIEW = "view"
    MODE_LAYER = "layer"
    MODE_CUSTOM = "custom"
    _MODE_LABELS = ((MODE_VIEW, "当前地图视图范围"),
                    (MODE_LAYER, "图层自身范围"),
                    (MODE_CUSTOM, "自定义范围"))

    def __init__(self, parent=None, modes=("layer", "custom")):
        super().__init__(parent)
        self._canvas = None
        self._ref = None
        self._view_rect = None
        self._view_sync = None
        self._decimals = 6

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._bg = QButtonGroup(self)
        self._rb = {}
        _valid = dict(self._MODE_LABELS)
        for key in modes:
            if key not in _valid:
                continue
            rb = QRadioButton(_tr(_valid[key]), self)
            rb.clicked.connect(self._on_mode_clicked)
            self._bg.addButton(rb)
            self._rb[key] = rb
            lay.addWidget(rb)
        if not self._rb:
            rb = QRadioButton(_tr("自定义范围"), self)
            rb.clicked.connect(self._on_mode_clicked)
            self._bg.addButton(rb)
            self._rb[self.MODE_CUSTOM] = rb
            lay.addWidget(rb)
        first = next(iter(self._rb))
        self._rb[first].setChecked(True)

        self.sp_minx = QDoubleSpinBox(self)
        self.sp_maxx = QDoubleSpinBox(self)
        self.sp_miny = QDoubleSpinBox(self)
        self.sp_maxy = QDoubleSpinBox(self)
        for sp in (self.sp_minx, self.sp_maxx, self.sp_miny, self.sp_maxy):
            sp.setRange(-1e9, 1e9)
            sp.setDecimals(self._decimals)
            sp.setMinimumWidth(120)
            sp.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cust_box = QWidget(self)
        g = QGridLayout(self.cust_box)
        g.setContentsMargins(8, 4, 8, 4)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(4)
        for col in range(3):
            g.setColumnStretch(col, 1)

        def _cell(cap, sp, align):
            w = QWidget(self)
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(4)
            if align == Qt.AlignmentFlag.AlignRight:
                h.addStretch(1)
            h.addWidget(QLabel(_tr(cap), w))
            h.addWidget(sp)
            if align == Qt.AlignmentFlag.AlignLeft:
                h.addStretch(1)
            return w

        _C = Qt.AlignmentFlag
        g.addWidget(_cell("北", self.sp_maxy, _C.AlignHCenter),
                    0, 1, _C.AlignHCenter)
        g.addWidget(_cell("西", self.sp_minx, _C.AlignRight),
                    1, 0, _C.AlignRight | _C.AlignVCenter)
        g.addWidget(_cell("东", self.sp_maxx, _C.AlignLeft),
                    1, 2, _C.AlignLeft | _C.AlignVCenter)
        g.addWidget(_cell("南", self.sp_miny, _C.AlignHCenter),
                    2, 1, _C.AlignHCenter)
        lay.addWidget(self.cust_box)

        for sp in (self.sp_minx, self.sp_miny, self.sp_maxx, self.sp_maxy):
            sp.valueChanged.connect(self._on_value_changed)
        self._sync_editable()

    def set_canvas(self, canvas):
        self._canvas = canvas
        rb = self._rb.get(self.MODE_VIEW)
        if rb is not None:
            rb.setEnabled(canvas is not None)
        if canvas is None:
            if self.mode() == self.MODE_VIEW:
                self.set_mode(self.MODE_CUSTOM)
            return
        try:
            canvas.extentChanged.connect(self._on_canvas_extent_changed)
        except Exception:
            exc_note("set_canvas @ ggis/common/widgets/standard.py:5221")
            pass
        self._on_canvas_extent_changed()

    def set_view_sync(self, fn):
        self._view_sync = fn
        self._on_canvas_extent_changed()

    def set_reference_extent(self, rect):
        if rect is not None:
            self._ref = rect
            span = max(abs(float(rect.xmax) - float(rect.xmin)),
                       abs(float(rect.ymax) - float(rect.ymin)))
            self._decimals = 4 if span > 1000.0 else 6
            lo_x, hi_x = float(rect.xmin), float(rect.xmax)
            lo_y, hi_y = float(rect.ymin), float(rect.ymax)
            for sp, lo, hi in ((self.sp_minx, lo_x, hi_x),
                               (self.sp_maxx, lo_x, hi_x),
                               (self.sp_miny, lo_y, hi_y),
                               (self.sp_maxy, lo_y, hi_y)):
                sp.setRange(min(lo, hi), max(lo, hi))
                sp.setDecimals(self._decimals)
                sp.setSingleStep(max((hi - lo) / 1000.0,
                                     10.0 ** -self._decimals))
        if self._ref is not None:
            self._fill(self._ref)
        self.extentChanged.emit()

    def mode(self):
        for key, rb in self._rb.items():
            if rb.isChecked():
                return key
        return ""

    def set_mode(self, key):
        rb = self._rb.get(key)
        if rb is not None and not rb.isChecked():
            rb.setChecked(True)
            self._on_mode_changed()

    def extent(self):
        m = self.mode()
        if m == self.MODE_VIEW:
            r = self._view_rect
            return None if r is None else r.copy()
        if m == self.MODE_LAYER:
            return None if self._ref is None else self._ref.copy()
        try:
            minx = float(self.sp_minx.value())
            miny = float(self.sp_miny.value())
            maxx = float(self.sp_maxx.value())
            maxy = float(self.sp_maxy.value())
        except Exception:
            exc_note("extent @ ggis/common/widgets/standard.py:5285")
            return None
        if maxx <= minx or maxy <= miny:
            return None
        return GgsRectangle(minx, miny, maxx, maxy)

    def setExtent(self, rect):
        if rect is None or rect.is_empty():
            return
        d = self._decimals
        self._fill(rect, d)
        self.extentChanged.emit()

    def _fill(self, rect, decimals=None):
        d = self._decimals if decimals is None else decimals
        was = self.cust_box.isEnabled()
        self.cust_box.setEnabled(True)
        try:
            self.sp_minx.setValue(round(float(rect.xmin), d))
            self.sp_miny.setValue(round(float(rect.ymin), d))
            self.sp_maxx.setValue(round(float(rect.xmax), d))
            self.sp_maxy.setValue(round(float(rect.ymax), d))
        except Exception:
            exc_note("_fill @ ggis/common/widgets/standard.py:5310")
            pass
        self.cust_box.setEnabled(was)

    def _sync_editable(self):
        self.cust_box.setEnabled(self.mode() == self.MODE_CUSTOM)

    def _on_canvas_extent_changed(self, *_):
        if self._canvas is None:
            return
        try:
            ext = self._canvas.extent()
        except Exception:
            exc_note("_on_canvas_extent_changed @ ggis/common/widgets/standard.py:5323")
            return
        if ext is None or ext.is_empty():
            self._view_rect = None
        else:
            rect = ext
            if self._view_sync is not None:
                try:
                    rect = self._view_sync(ext)
                except Exception:
                    exc_note("_on_canvas_extent_changed @ ggis/common/widgets/standard.py:5332")
                    rect = None
            self._view_rect = rect
        if self.mode() == self.MODE_VIEW:
            if self._view_rect is not None:
                self._fill(self._view_rect)
            self.extentChanged.emit()

    def _on_value_changed(self, *_):
        self.extentChanged.emit()

    def _on_mode_clicked(self, *_):
        self._on_mode_changed()

    def _on_mode_changed(self, *_):
        m = self.mode()
        if m == self.MODE_VIEW:
            if self._view_rect is not None:
                self._fill(self._view_rect)
        elif m == self.MODE_LAYER:
            if self._ref is not None:
                self._fill(self._ref)
        self._sync_editable()
        self.modeChanged.emit(m)
        self.extentChanged.emit()

class GgsDockComboBox(GgsComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsDockComboBox")
        self.setProperty("compact", "true")



class GgsSearchEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSearchEdit")


class GgsMultiLayerInputWidget(QWidget):

    layersChanged = Signal()

    def __init__(self, parent=None, kind="raster", title=""):
        super().__init__(parent)
        self._kind = "raster" if str(kind) == "raster" else "vector"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self._title = QLabel(str(title or ""), self)
        lay.addWidget(self._title)
        self._title.setVisible(bool(str(title or "")))
        self.lst = GgsListWidget(self)
        self.lst.setMinimumHeight(88)
        lay.addWidget(self.lst)

    def kind(self):
        return self._kind

    def setTitleVisible(self, on):
        self._title.setVisible(bool(on))

    def set_layers(self, layers, prefer=None, labels=None):
        from PySide6.QtCore import Qt as _Qt
        lst = self.lst
        old = [lst.item(k) for k in range(lst.count())]
        checked = {it.data(_Qt.UserRole) for it in old
                   if it is not None and it.checkState() == _Qt.Checked}
        lst.clear()
        for k, l in enumerate(layers or []):
            label = (str(labels[k]) if labels and k < len(labels)
                     else str(getattr(l, "name", lambda: "")() or l))
            lst.addItem(label)
            item = lst.item(lst.count() - 1)
            item.setFlags(item.flags() | _Qt.ItemIsUserCheckable)
            was = (l is prefer) or (l in checked)
            item.setCheckState(_Qt.Checked if was else _Qt.Unchecked)
            item.setData(_Qt.UserRole, l)
        self.layersChanged.emit()

    def add_layer(self, lyr, label=None, checked=True):
        from PySide6.QtCore import Qt as _Qt
        for k in range(self.lst.count()):
            if self.lst.item(k).data(_Qt.UserRole) is lyr:
                self.lst.item(k).setCheckState(
                    _Qt.Checked if checked else _Qt.Unchecked)
                self.layersChanged.emit()
                return
        self.lst.addItem(str(label or getattr(lyr, "name",
                                              lambda: "")() or lyr))
        item = self.lst.item(self.lst.count() - 1)
        item.setFlags(item.flags() | _Qt.ItemIsUserCheckable)
        item.setCheckState(_Qt.Checked if checked else _Qt.Unchecked)
        item.setData(_Qt.UserRole, lyr)
        self.layersChanged.emit()

    def checked_layers(self):
        from PySide6.QtCore import Qt as _Qt
        out = []
        for k in range(self.lst.count()):
            it = self.lst.item(k)
            if it.checkState() == _Qt.Checked:
                lyr = it.data(_Qt.UserRole)
                if lyr is not None:
                    out.append(lyr)
        return out


class GgsLayerInputWidget(QWidget):

    layerPicked = Signal(object)
    filePicked = Signal(str)

    def __init__(self, parent=None, kind="vector", title=""):
        super().__init__(parent)
        self._kind = "raster" if str(kind) == "raster" else "vector"
        self._file_loader = False
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(4)
        try:
            self.form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:5495")
            pass
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.cmb = GgsComboBox(self)
        self.cmb.addItem("", None)
        row.addWidget(self.cmb, 1)
        self.btn_open = GgsSmallButtonStyle1(
            "folder", _tr("打开文件"), self._browse, 16)
        row.addWidget(self.btn_open)
        _title = str(title or "").strip()
        if _title:
            self.form.addRow(QLabel(_title), row)
        else:
            self.form.addRow(row)
        self.cmb.currentIndexChanged.connect(
            lambda _i: self.layerPicked.emit(self.value()))

    def kind(self):
        return self._kind

    def set_items(self, items):
        cur = self.value()
        self.cmb.blockSignals(True)
        self.cmb.clear()
        self.cmb.addItem("", None)
        for _label, _data in (items or []):
            self.cmb.addItem(str(_label), _data)
        if cur is not None:
            _i = self.cmb.findData(cur)
            if _i >= 0:
                self.cmb.setCurrentIndex(_i)
        self.cmb.blockSignals(False)
        self.layerPicked.emit(self.value())

    def add_file(self, path):
        path = str(path or "")
        if not path:
            return
        _i = self.cmb.findData(path)
        if _i < 0:
            self.cmb.addItem(path, path)
            _i = self.cmb.count() - 1
        self.cmb.setCurrentIndex(_i)

    def set_file_loader(self, on):
        self._file_loader = bool(on)

    def add_layer(self, lyr, label=None):
        label = str(label or getattr(lyr, "name", lambda: "")() or "")
        for i in range(self.cmb.count()):
            if self.cmb.itemData(i) is lyr:
                self.cmb.setCurrentIndex(i)
                return
        self.cmb.addItem(label, lyr)
        self.cmb.setCurrentIndex(self.cmb.count() - 1)

    def value(self):
        return self.cmb.currentData()

    def _filters(self):
        rows = (VECTOR_WRITE_FORMATS if self._kind == "vector"
                else RASTER_WRITE_FORMATS)
        exts = []
        for row in rows:
            pat = "*" + str(row[0])
            if pat not in exts:
                exts.append(pat)
        all_f = _tr("所有支持的格式") + " (" + " ".join(exts) + ")"
        ind = _tr_filter_text(
            vector_filters() if self._kind == "vector"
            else raster_filters())
        return all_f + (";;" + ind if ind else "")

    def _browse(self):
        path, _f = QFileDialog.getOpenFileName(
            self, _tr("打开文件"), "", self._filters())
        if not path:
            return
        if getattr(self, "_file_loader", False):
            self.filePicked.emit(path)
        else:
            self.add_file(path)


_LAYER_CREATE_OPTS = {
    "raster": {
        "GTiff": (
            ("COMPRESS", "choice",
             ("NONE", "LZW", "PACKBITS", "DEFLATE", "JPEG", "ZSTD", "LZMA",
              "CCITTFAX4")),
            ("TILED", "choice", ("YES", "NO")),
            ("PREDICTOR", "choice", ("1", "2", "3")),
            ("JPEG_QUALITY", "text", "1-100"),
            ("BIGTIFF", "choice", ("YES", "NO", "IF_NEEDED", "IF_SAFER")),
        ),
        "COG": (
            ("COMPRESS", "choice",
             ("NONE", "LZW", "DEFLATE", "JPEG", "LZMA", "ZSTD", "PACKBITS")),
            ("OVERVIEWS", "choice", ("AUTO", "IGNORE_EXISTING", "NONE")),
            ("BLOCKSIZE", "choice", ("512", "1024", "2048", "4096")),
            ("BIGTIFF", "choice", ("YES", "NO", "IF_NEEDED", "IF_SAFER")),
        ),
        "HFA": (("COMPRESSED", "choice", ("YES", "NO")),),
        "GPKG": (("TILE_FORMAT", "choice",
                  ("PNG", "JPEG", "WEBP", "PNG_JPEG")),),
        "netCDF": (
            ("COMPRESS", "choice", ("NONE", "DEFLATE")),
            ("ZLEVEL", "text", "1-9"),
        ),
        "JP2OpenJPEG": (
            ("QUALITY", "text", "1-100"),
            ("REVERSIBLE", "choice", ("TRUE", "FALSE")),
            ("PROGRESSION", "choice",
             ("LRCP", "RLCP", "RPCL", "PCRL", "CPRL")),
        ),
        "PNG": (("ZLEVEL", "text", "1-9"),),
        "JPEG": (
            ("QUALITY", "text", "1-100"),
            ("WORLD_FILE", "choice", ("YES", "NO")),
        ),
        "WEBP": (
            ("QUALITY", "text", "1-100"),
            ("LOSSLESS", "choice", ("TRUE", "FALSE")),
        ),
    },
    "vector": {
        "GPKG": (
            ("VERSION", "choice", ("AUTO", "1.0", "1.1", "1.2", "1.3")),
            ("LAUNDER", "choice", ("YES", "NO")),
            ("GEOMETRY_NAME", "text", "geom"),
            ("SPATIAL_INDEX", "choice", ("YES", "NO")),
            ("FID", "text", "fid"),
        ),
        "ESRI Shapefile": (
            ("ENCODING", "text", "UTF-8"),
            ("RESIZE", "choice", ("YES", "NO")),
        ),
        "GeoJSON": (
            ("WRITE_BBOX", "choice", ("YES", "NO")),
            ("RFC7946", "choice", ("YES", "NO")),
            ("COORDINATE_PRECISION", "text", "0-15"),
        ),
        "GeoJSONSeq": (("COORDINATE_PRECISION", "text", "0-15"),),
        "FlatGeobuf": (("CREATE_INDEX", "choice", ("YES", "NO")),),
        "CSV": (
            ("GEOMETRY", "choice",
             ("AS_WKT", "AS_XY", "AS_YX", "NONE")),
            ("CREATE_CSVT", "choice", ("YES", "NO")),
            ("SEPARATOR", "choice", ("COMMA", "SEMICOLON", "TAB")),
        ),
        "SQLite": (
            ("LAUNDER", "choice", ("YES", "NO")),
            ("SPATIAL_INDEX", "choice", ("OGR_GPKG", "NO")),
        ),
        "OpenFileGDB": (("FEATURE_DATASET", "text", "要素数据集名"),),
        "GML": (("FORMAT", "choice", ("GML3", "GML3.1", "GML2")),),
    },
}


class GgsLayerOutputWidget(QWidget):

    def __init__(self, parent=None, kind="vector"):
        super().__init__(parent)
        self._kind = ("table" if str(kind) == "table"
                      else "raster" if str(kind) == "raster" else "vector")
        self._rows = (TABLE_WRITE_FORMATS if self._kind == "table"
                      else RASTER_WRITE_FORMATS if self._kind == "raster"
                      else VECTOR_WRITE_FORMATS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(4)
        try:
            self.form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:5727")
            pass
        outer.addLayout(self.form)
        self.cmb_fmt = GgsComboBox(self)
        self._fmt = []
        if self._kind == "raster":
            for _suf, _drv, _name, _filt, _e8 in self._rows:
                self.cmb_fmt.addItem(_tr(_filt), _drv)
                self._fmt.append((_suf, _filt))
        else:
            for _suf, _drv, _name, _filt in self._rows:
                self.cmb_fmt.addItem(_tr(_filt), _drv)
                self._fmt.append((_suf, _filt))
        self.btn_opts = GgsSmallButtonStyle1(
            "settings", _tr("创建选项…"), self._open_opts, 16)
        self.btn_opts.setObjectName("GgsStdButton")
        if self._kind == "table":
            self.btn_opts.setVisible(False)
        _hf = QHBoxLayout()
        _hf.setContentsMargins(0, 0, 0, 0)
        _hf.setSpacing(4)
        _hf.addWidget(self.cmb_fmt, 1)
        _hf.addWidget(self.btn_opts)
        self.form.addRow(_tr("输出格式"), _hf)

        self.ed_file = QLineEdit(self)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self.ed_file, 1)
        self.btn_save = GgsSmallButtonStyle1(
            "save", _tr("保存文件"), self._browse_save, 16)
        row.addWidget(self.btn_save)
        self.form.addRow(_tr("输出文件"), row)

        self.ed_name = None
        if self._kind == "vector":
            self.ed_name = QLineEdit(self)
            self.form.addRow(_tr("输出图层"), self.ed_name)

        self._opt_rows = []
        self.gb_opts = QWidget(self)
        self._opts_form = QFormLayout(self.gb_opts)
        self._opts_form.setContentsMargins(0, 0, 0, 0)
        self._opts_form.setHorizontalSpacing(10)
        self._opts_form.setVerticalSpacing(4)
        try:
            self._opts_form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:5790")
            pass
        self._opts_dialog = GgsDialog(self)
        self._opts_dialog.setWindowTitle(_tr("创建选项"))
        self._opts_dialog.setMinimumWidth(420)
        _dlg_lay = QVBoxLayout(self._opts_dialog)
        _dlg_lay.setContentsMargins(8, 8, 8, 8)
        _dlg_lay.addWidget(self.gb_opts, 1)
        _bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        _bb.accepted.connect(self._opts_dialog.accept)
        _dlg_lay.addWidget(_bb)
        self._opts_taken = False

        self._build_opts()
        self._sync_layer_name_enabled()
        self.cmb_fmt.currentIndexChanged.connect(self._on_fmt_changed)

    def kind(self):
        return self._kind

    def spec(self):
        row = self._cur_row()
        return {
            "kind": self._kind,
            "name": (self.ed_name.text().strip()
                     if (self.ed_name is not None
                         and self.ed_name.isEnabled()) else ""),
            "driver": (str(row[1]) if row else ""),
            "filename": self.ed_file.text().strip(),
            "options": self._options_text(),
        }

    def current_suffix(self):
        row = self._cur_row()
        return str(row[0]) if row else ""

    def current_driver(self):
        row = self._cur_row()
        return str(row[1]) if row else ""

    def _options_text(self):
        parts = []
        for key, ed, is_combo in self._opt_rows:
            if is_combo:
                v = str(ed.currentData() or "")
            else:
                v = ed.text().strip()
            if v:
                parts.append("%s=%s" % (key, v))
        custom = ""
        if getattr(self, "_custom", None) is not None:
            custom = self._custom.text().strip().rstrip(";")
        if custom:
            parts.append(custom)
        return ";".join(parts)

    def set_options_provider(self, fn):
        self._opts_provider = fn
        self._build_opts()

    def supports_options(self):
        return bool(getattr(self, "_opts_supported", False))

    def take_options_group(self):
        lay = self._opts_dialog.layout()
        if lay is not None:
            lay.removeWidget(self.gb_opts)
        self.gb_opts.hide()
        self._opts_taken = True
        if getattr(self, "btn_opts", None) is not None:
            self.btn_opts.setEnabled(False)
        return self.gb_opts

    def _build_opts(self):
        if self._kind == "table":
            self._opts_supported = False
            if getattr(self, "btn_opts", None) is not None:
                self.btn_opts.setVisible(False)
            return
        while self._opts_form.rowCount() > 0:
            self._opts_form.removeRow(self._opts_form.rowCount() - 1)
        self._opt_rows = []
        self._custom = None
        row = self._cur_row()
        drv = str(row[1]) if row else ""
        provider = getattr(self, "_opts_provider", None)
        if callable(provider):
            try:
                provider(self._opts_form, drv)
            except Exception:
                exc_note("_build_opts @ ggis/common/widgets/standard.py:5925")
                pass
        else:
            for key, kind, extra in (_LAYER_CREATE_OPTS.get(self._kind, {})
                                     .get(drv) or ()):
                if kind == "choice":
                    ed = QComboBox()
                    ed.addItem(_tr("（默认）"), "")
                    for _v in extra:
                        ed.addItem(_v, _v)
                else:
                    ed = QLineEdit()
                    ed.setPlaceholderText(str(extra))
                self._opt_rows.append((key, ed, kind == "choice"))
                self._opts_form.addRow(_tr(key), ed)
            self._custom = QLineEdit()
            self._custom.setPlaceholderText(_tr("自定义") + ": KEY=VALUE;KEY=VALUE")
            self._opts_form.addRow(_tr("自定义"), self._custom)
        self._opts_supported = self._opts_form.rowCount() > 0
        self.gb_opts.setVisible(self._opts_supported)
        if getattr(self, "btn_opts", None) is not None:
            self.btn_opts.setEnabled(
                self._opts_supported and not self._opts_taken)

    def _open_opts(self):
        self._opts_dialog.exec()

    def _sync_layer_name_enabled(self):
        if self.ed_name is None:
            return
        self.ed_name.setDisabled(
            not vector_supports_layer_name(self.current_driver()))

    def _cur_row(self):
        _i = self.cmb_fmt.currentIndex()
        return self._rows[_i] if 0 <= _i < len(self._rows) else None

    def _on_fmt_changed(self, _i=0):
        self._build_opts()
        self._sync_layer_name_enabled()
        row = self._cur_row()
        if not row:
            return
        suf = str(row[0] or "")
        txt = self.ed_file.text().strip()
        if not txt or not suf:
            return
        base, dot, old = txt.rpartition(".")
        if dot and len(old) <= 5 and old.isalnum():
            self.ed_file.setText(base + suf)
        elif not dot or len(old) > 5:
            self.ed_file.setText(txt + suf)

    def _browse_save(self):
        row = self._cur_row()
        path, _f = QFileDialog.getSaveFileName(
            self, _tr("保存文件"), self.ed_file.text().strip(),
            (_tr(str(row[3])) if row else "") or "")
        if not path:
            return
        if row and not path.lower().endswith(str(row[0])):
            path += str(row[0])
        self.ed_file.setText(path)


class GgsFileInputWidget(QWidget):

    pathChanged = Signal(str)

    def __init__(self, parent=None, kind="vector", title="", filters=""):
        super().__init__(parent)
        self._kind = "raster" if str(kind) == "raster" else "vector"
        self._filters = str(filters or "")
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(4)
        try:
            self.form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:6038")
            pass
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.ed_path = QLineEdit(self)
        self.ed_path.setPlaceholderText(_tr("选择文件"))
        self.ed_path.textChanged.connect(
            lambda _t: self.pathChanged.emit(self.value()))
        row.addWidget(self.ed_path, 1)
        self.btn_open = GgsSmallButtonStyle1(
            "folder", _tr("打开文件"), self._browse, 16)
        row.addWidget(self.btn_open)
        _title = str(title or "").strip()
        if _title:
            self.form.addRow(QLabel(_title), row)
        else:
            self.form.addRow(row)

    def value(self):
        return self.ed_path.text().strip()

    def set_path(self, path):
        self.ed_path.setText(str(path or ""))

    def set_filters(self, filters):
        self._filters = str(filters or "")

    def _filter_str(self):
        if self._filters:
            return self._filters
        rows = (VECTOR_WRITE_FORMATS if self._kind == "vector"
                else RASTER_WRITE_FORMATS)
        exts = []
        for r in rows:
            pat = "*" + str(r[0])
            if pat not in exts:
                exts.append(pat)
        ind = _tr_filter_text(
            vector_filters() if self._kind == "vector"
            else raster_filters())
        return (_tr("所有支持的格式") + " (" + " ".join(exts) + ")"
                + (";;" + ind if ind else ""))

    def _browse(self):
        path, _f = QFileDialog.getOpenFileName(
            self, _tr("打开文件"), self.value(), self._filter_str())
        if path:
            self.ed_path.setText(path)


class GgsFileOutputWidget(QWidget):

    pathChanged = Signal(str)

    def __init__(self, parent=None, kind="vector", title="", filters="",
                 suffix=""):
        super().__init__(parent)
        self._kind = "raster" if str(kind) == "raster" else "vector"
        self._filters = str(filters or "")
        self._suffix = str(suffix or "")
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setHorizontalSpacing(10)
        self.form.setVerticalSpacing(4)
        try:
            self.form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:6126")
            pass
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.ed_path = QLineEdit(self)
        self.ed_path.setPlaceholderText(_tr("输出文件"))
        self.ed_path.textChanged.connect(
            lambda _t: self.pathChanged.emit(self.value()))
        row.addWidget(self.ed_path, 1)
        self.btn_save = GgsSmallButtonStyle1(
            "save", _tr("保存文件"), self._browse, 16)
        row.addWidget(self.btn_save)
        _title = str(title or "").strip()
        if _title:
            self.form.addRow(QLabel(_title), row)
        else:
            self.form.addRow(row)

    def value(self):
        return self.ed_path.text().strip()

    def set_path(self, path):
        self.ed_path.setText(str(path or ""))

    def set_filters(self, filters):
        self._filters = str(filters or "")

    def set_suffix(self, suffix):
        self._suffix = str(suffix or "")

    def _filter_str(self):
        if self._filters:
            return self._filters
        rows = (VECTOR_WRITE_FORMATS if self._kind == "vector"
                else RASTER_WRITE_FORMATS)
        exts = []
        for r in rows:
            pat = "*" + str(r[0])
            if pat not in exts:
                exts.append(pat)
        ind = _tr_filter_text(
            vector_filters() if self._kind == "vector"
            else raster_filters())
        return (_tr("所有支持的格式") + " (" + " ".join(exts) + ")"
                + (";;" + ind if ind else ""))

    def _browse(self):
        path, _f = QFileDialog.getSaveFileName(
            self, _tr("保存文件"), self.value(), self._filter_str())
        if not path:
            return
        suf = str(self._suffix or "")
        if suf and not path.lower().endswith(suf.lower()):
            path += suf
        self.ed_path.setText(path)

