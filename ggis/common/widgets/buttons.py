# -*- coding: utf-8 -*-
from PySide6.QtCore import (
    QAbstractItemModel,
    QDir,
    QEasingCurve,
    QEvent,
    QMimeData,
    QModelIndex,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    QTimer,
    QUrl,
    QVariantAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QStyleOptionTab,
    QStyleOptionTabBarBase,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from ggis.common.util.exc_report import exc_note
from ggis.common.styling import icons
from ggis.common.styling import icons as _icons
from ggis.common.styling import themes as _themes
from ggis.core.app import i18n

_tr = i18n.tr
BIG_ICON = 32
SMALL_ICON = 16
STATUS_CTRL_H = 20


class SmallDropButton(QToolButton):

    _C_DARK = "#929dab"
    _C_LIGHT = "#5c6572"

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._C_DARK if icons.is_dark() else self._C_LIGHT)
        if not self.isEnabled():
            c.setAlphaF(0.45)
        pen = QPen(c, 1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        w, h = self.width(), self.height()
        if self.property("arrowCentered"):
            dy = float(self.property("arrowDy") or 0)
            x, y = w / 2.0, h / 2.0 - 1.5 + dy
        elif self.property("splitArrow"):
            p.drawLine(QPointF(w - 15.5, 3.0), QPointF(w - 15.5, h - 3.0))
            x, y = w - 8.5, h / 2.0 - 1.5
        elif self.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly:
            x, y = w - 6.0, h - 6.0
        else:
            x, y = w - 7.0, h / 2.0 - 1.5
        p.drawPolyline(QPolygonF([
            QPointF(x - 3.0, y), QPointF(x, y + 3.0), QPointF(x + 3.0, y)]))


def _tight_icon_text_width(btn, pad_l, pad_r):
    try:
        adv = 0
        t = btn.text()
        if t:
            adv = int(btn.fontMetrics().horizontalAdvance(t))
        iw = 0
        try:
            if not btn.icon().isNull():
                iw = int(btn.iconSize().width())
        except Exception:
            exc_note("_tight_icon_text_width @ ggis/common/widgets/standard.py:740")
            iw = 0
        w = 2 * 1 + int(pad_l) + int(pad_r)
        if iw > 0:
            w += iw + 2
        w += adv
        return int(w)
    except Exception:
        exc_note("_tight_icon_text_width @ ggis/common/widgets/standard.py:747")
        return 0


class GgsSmallButtonStyle1(QToolButton):

    def __init__(self, icon_name, tip, slot=None, size=16, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsSmallButtonStyle1")
        self.setToolTip(tip)
        try:
            _icons.bind(self, str(icon_name), size=int(size))
            self.setIconSize(QSize(int(size), int(size)))
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:777")
            self.setText(str(tip)[:2])
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if slot is not None:
            self.clicked.connect(slot)

class GgsSmallButtonStyle2(QToolButton):

    def __init__(self, icon_name, text="", tip="", slot=None, size=16, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsSmallButtonStyle2")
        self.setText(str(text or ""))
        self.setToolTip(str(tip or text or ""))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        try:
            self.setIcon(_icons.icon(str(icon_name), size=int(size)))
            self.setIconSize(QSize(int(size), int(size)))
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:806")
            self.setText(str(text or tip or "")[:6])
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if slot is not None:
            self.clicked.connect(slot)

    def sizeHint(self):
        base = super().sizeHint()
        w = _tight_icon_text_width(self, 2, 6)
        if w <= 0:
            return base
        return QSize(w, int(base.height()))

class GgsSmallCheckButtonStyle2(QToolButton):

    def __init__(self, icon_name, text="", tip="", slot=None, size=16,
                 checked=False, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsSmallCheckButtonStyle2")
        self.setText(str(text or ""))
        self.setToolTip(str(tip or text or ""))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCheckable(True)
        try:
            _icons.bind(self, str(icon_name), size=int(size))
            self.setIconSize(QSize(int(size), int(size)))
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:864")
            self.setText(str(text or tip or "")[:6])
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if checked:
            self.setChecked(True)
        if slot is not None:
            self.clicked.connect(slot)

    def sizeHint(self):
        base = super().sizeHint()
        w = _tight_icon_text_width(self, 2, 6)
        if w <= 0:
            return base
        return QSize(w, int(base.height()))

class GgsSmallCheckButtonStyle1(QToolButton):

    def __init__(self, icon_name, tip, slot=None, size=16, parent=None,
                 checked=False):
        super().__init__(parent)
        self.setObjectName("GgsSmallCheckButtonStyle1")
        self.setToolTip(tip)
        self.setCheckable(True)
        try:
            _icons.bind(self, str(icon_name), size=int(size))
            self.setIconSize(QSize(int(size), int(size)))
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:913")
            self.setText(str(tip)[:2])
        self.setAutoRaise(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if checked:
            self.setChecked(True)
        if slot is not None:
            self.clicked.connect(slot)

class GgsStandardButton(QPushButton):

    def __init__(self, icon_name, text="", tip="", slot=None, size=16,
                 checkable=False, menu=None, parent=None):
        text = text or tip or ""
        super().__init__(str(text), parent)
        self.setObjectName("GgsStandardButton")
        self.setToolTip(str(tip or text or ""))
        if checkable:
            self.setCheckable(True)
        if menu is not None:
            self.setMenu(menu)
        try:
            _icons.bind(self, str(icon_name), size=int(size))
            self.setIconSize(QSize(int(size), int(size)))
        except Exception:
            exc_note("__init__ @ ggis/common/widgets/standard.py:960")
            pass
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if slot is not None:
            self.clicked.connect(slot)

class GgsSwitch(QAbstractButton):

    def __init__(self, checked=False, parent=None, on_toggle=None):
        super().__init__(parent)
        self.setObjectName("GgsSwitch")
        self.setCheckable(True)
        self.setChecked(bool(checked))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if on_toggle is not None:
            self.toggled.connect(on_toggle)
        self._knob = 1.0 if self.isChecked() else 0.0
        self._knob_anim = QVariantAnimation(self)
        self._knob_anim.setDuration(160)
        self._knob_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._knob_anim.valueChanged.connect(self._on_knob_step)
        self.toggled.connect(self._on_toggled)
        self._knob_ready = True

    def _on_knob_step(self, v):
        try:
            self._knob = float(v)
            self.update()
        except RuntimeError:
            exc_note("_on_knob_step @ ggis/common/widgets/standard.py:1014")
            pass

    def _on_toggled(self, on):
        if not getattr(self, "_knob_ready", False):
            return
        try:
            a = self._knob_anim
            a.stop()
            a.setStartValue(self._knob)
            a.setEndValue(1.0 if on else 0.0)
            a.start()
        except Exception:
            exc_note("_on_toggled @ ggis/common/widgets/standard.py:1027")
            self._knob = 1.0 if on else 0.0
            self.update()

    def sizeHint(self):
        return QSize(44, 22)

    def minimumSizeHint(self):
        return QSize(36, 18)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = _icons.is_dark()
        c = lambda k: QColor(_themes.theme_color(k, dark))
        w, h = float(self.width()), float(self.height())
        th = min(h, 22.0)
        tw = min(w, th * 2.0)
        tx = (w - tw) / 2.0
        ty = (h - th) / 2.0
        track = QRectF(tx, ty, tw, th).adjusted(0.5, 0.5, -0.5, -0.5)
        pos = getattr(self, "_knob", None)
        if pos is None:
            pos = 1.0 if self.isChecked() else 0.0
        _ca = QColor(c("panel_dn"))
        _cb = QColor(c("accent"))
        base = QColor(
            int(round(_ca.red() + (_cb.red() - _ca.red()) * pos)),
            int(round(_ca.green() + (_cb.green() - _ca.green()) * pos)),
            int(round(_ca.blue() + (_cb.blue() - _ca.blue()) * pos)))
        if self.isEnabled():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(base)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            base.setAlphaF(0.45)
            p.setBrush(base)
        p.drawRoundedRect(track, track.height() / 2.0,
                          track.height() / 2.0)
        d = track.height() - 6.0
        kx = (track.left() + 3.0) + pos * (
            (track.right() - 3.0 - d) - (track.left() + 3.0))
        knob = QRectF(kx, track.top() + 3.0, d, d)
        p.setBrush(QColor("#ffffff") if not dark else QColor("#dfe5ec"))
        p.setPen(QPen(c("border"), 1))
        p.drawEllipse(knob)

class GgsButtonBox(QDialogButtonBox):

    def __init__(self, buttons=(QDialogButtonBox.StandardButton.Ok
                                | QDialogButtonBox.StandardButton.Cancel),
                 parent=None):
        super().__init__(buttons, parent)
        self.setObjectName("GgsButtonBox")

class GgsRibbonButtonBase(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._lay = lay
        self._host = None
        self._root = None
        self._action = None

    def _build(self, action, menu=None, dropdown=False, icon_only=False,
               style2=False, big=True, variant=None, tip=""):
        from ggis.ui.framework.ribbon import RibbonGroup
        host = RibbonGroup("")
        self._host = host
        before = set(host._drop_state)
        try:
            if dropdown:
                host.add_dropdown(action, menu, big=big, tip=tip,
                                  icon_only=icon_only, style2=style2,
                                  variant=variant)
            elif variant in ("GgsBigButtonStyle1",
                             "GgsBigCheckButtonStyle1") and big:
                host._add_style01(action, tip=tip, variant=variant)
            else:
                host.add_action(action, big=big, tip=tip,
                                icon_only=icon_only, dropdown=dropdown,
                                style2=style2, variant=variant)
        except Exception:
            exc_note("_build @ ggis/ui/framework/buttons.py:83")
            pass
        new = [k for k in host._drop_state if k not in before]
        root = new[0] if new else (
            host._btn_meta[-1][0] if host._btn_meta else None)
        if root is not None:
            root.setParent(None)
            self._lay.addWidget(
                root, 0, Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignTop)
            self._root = root
        self._action = action
        return root

    def action(self):
        return self._action

    def retheme_icons(self):
        try:
            self._host.retheme_icons()
        except Exception:
            exc_note("retheme_icons @ ggis/ui/framework/buttons.py:108")
            pass


def _entity_action(owner, icon_name, text, tip, slot, size=BIG_ICON):
    act = QAction(icons.icon(str(icon_name), size=int(size)),
                  str(text or ""), owner)
    try:
        act.setProperty("ggsIconName", str(icon_name))
    except Exception:
        exc_note("_entity_action @ ggis/ui/framework/buttons.py:123")
        pass
    if tip:
        try:
            act.setToolTip(i18n.tr(tip))
        except Exception:
            exc_note("_entity_action @ ggis/ui/framework/buttons.py:128")
            act.setToolTip(str(tip))
    if slot is not None:
        try:
            act.triggered.connect(slot)
        except Exception:
            exc_note("_entity_action @ ggis/ui/framework/buttons.py:133")
            pass
    return act


def _menu_or_empty(owner, menu):
    return menu if menu is not None else QMenu(owner)


class GgsBigButtonStyle1(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", tip="", slot=None, parent=None):
        super().__init__(parent)
        self._build(_entity_action(self, icon_name, text, tip, slot),
                    big=True, variant="GgsBigButtonStyle1", tip=tip)


class GgsBigCheckButtonStyle1(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", tip="", slot=None,
                 checked=False, parent=None):
        super().__init__(parent)
        act = _entity_action(self, icon_name, text, tip, slot)
        act.setCheckable(True)
        if checked:
            act.setChecked(True)
        self._build(act, big=True, variant="GgsBigCheckButtonStyle1", tip=tip)


class GgsBigMenuButtonStyle1(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", menu=None, tip="", slot=None,
                 parent=None):
        super().__init__(parent)
        self._build(_entity_action(self, icon_name, text, tip, slot),
                    menu=_menu_or_empty(self, menu), dropdown=True, big=True,
                    style2=True, variant="GgsBigMenuButtonStyle1", tip=tip)


class GgsBigMenuButtonStyle2(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", menu=None, tip="", slot=None,
                 parent=None):
        super().__init__(parent)
        self._build(_entity_action(self, icon_name, text, tip, slot),
                    menu=_menu_or_empty(self, menu), dropdown=True, big=True,
                    style2=True, variant="GgsBigMenuButtonStyle2", tip=tip)


class GgsBigMenuButtonStyle3(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", menu=None, tip="", slot=None,
                 parent=None):
        super().__init__(parent)
        self._build(_entity_action(self, icon_name, text, tip, slot),
                    menu=_menu_or_empty(self, menu), dropdown=True, big=True,
                    style2=True, variant="GgsBigMenuButtonStyle3", tip=tip)


class GgsBigMenuButtonStyle4(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", menu=None, tip="", slot=None,
                 checked=False, parent=None):
        super().__init__(parent)
        act = _entity_action(self, icon_name, text, tip, slot)
        act.setCheckable(True)
        if checked:
            act.setChecked(True)
        self._build(act, menu=_menu_or_empty(self, menu), dropdown=True,
                    big=True, style2=True,
                    variant="GgsBigMenuButtonStyle4", tip=tip)


class GgsSmallMenuButtonStyle1(GgsRibbonButtonBase):

    def __init__(self, icon_name, menu=None, tip="", slot=None, parent=None):
        super().__init__(parent)
        self._build(_entity_action(self, icon_name, "", tip, slot,
                                   SMALL_ICON),
                    menu=_menu_or_empty(self, menu), dropdown=True,
                    icon_only=False, big=False, tip=tip)


class GgsSmallMenuButtonStyle2(GgsRibbonButtonBase):

    def __init__(self, icon_name, text="", menu=None, tip="", slot=None,
                 parent=None):
        super().__init__(parent)
        self._build(_entity_action(self, icon_name, text, tip, slot,
                                   SMALL_ICON),
                    menu=_menu_or_empty(self, menu), dropdown=True,
                    icon_only=False, big=False, tip=tip)


class _MediumButtonBase(QToolButton):

    ICON = 16

    def __init__(self, icon_name, text="", tip="", slot=None, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsMediumBtn")
        self.setProperty("dropSmall", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setText(str(text or ""))
        self.setToolTip(str(tip or text or ""))
        try:
            from ggis.common.styling import icons as _icons
            _icons.bind(self, str(icon_name), size=int(self.ICON))
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/buttons.py:283")
            pass
        self.setIconSize(QSize(int(self.ICON), int(self.ICON)))
        try:
            _w = (self.fontMetrics().horizontalAdvance(self.text())
                  + int(self.ICON) + 10)
            self.setMinimumWidth(max(28, int(_w)))
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/buttons.py:290")
            pass
        if slot is not None:
            self.clicked.connect(slot)


class GgsMediumButtonStyle1(_MediumButtonBase):
    pass


class GgsMediumButtonStyle2(_MediumButtonBase):

    def __init__(self, icon_name, text="", tip="", slot=None,
                 checked=False, parent=None):
        super().__init__(icon_name, text, tip, slot, parent)
        self.setCheckable(True)
        if checked:
            self.setChecked(True)


class GgsMediumButtonStyle3(SmallDropButton):

    def __init__(self, icon_name, text="", menu=None, tip="", parent=None):
        super().__init__(parent)
        self.setObjectName("GgsMediumBtn")
        self.setProperty("dropSmall", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setText(str(text or ""))
        self.setToolTip(str(tip or text or ""))
        try:
            from ggis.common.styling import icons as _icons
            _icons.bind(self, str(icon_name), size=16)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/buttons.py:333")
            pass
        self.setIconSize(QSize(16, 16))
        try:
            _w = (self.fontMetrics().horizontalAdvance(self.text())
                  + 16 + 10 + 9)
            self.setMinimumWidth(max(28, int(_w)))
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/buttons.py:340")
            pass
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        if menu is not None:
            self.setMenu(menu)
            menu.aboutToShow.connect(lambda: self.setDown(True))
            menu.aboutToHide.connect(lambda: self.setDown(False))

