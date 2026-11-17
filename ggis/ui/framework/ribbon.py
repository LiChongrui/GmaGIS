# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import (Qt, QSize, QPoint, Signal, QEvent, QRect,
                             QPropertyAnimation, QEasingCurve, QPointF,
                             QTimer, QRectF)
from PySide6.QtGui import (
                           QBrush,
                           QColor,
                           QFont,
                           QFontMetrics,
                           QFontMetricsF,
                           QImage,
                           QPainterPath,
                           QPainter,
                           QPen,
                           QPolygonF,
                           QPixmap,
                           QIcon,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QToolButton, QTabBar, QStackedWidget, QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy, QMenu, QScrollArea, QStyle, QStyleOptionTabBarBase, QStyleOptionTab

try:
    import shiboken6
except Exception:
    exc_note("<module> @ ggis/ui/framework/ribbon.py:51")
    shiboken6 = None

from ggis.core.app import i18n, settings
from ggis.common.styling import themes, icons
from ggis.common.widgets.helpers import hand_cursor
from ggis.common.widgets.buttons import BIG_ICON, SMALL_ICON, SmallDropButton
from PySide6.QtWidgets import QLabel


def _dd_blank_icon():
    ic = getattr(_dd_blank_icon, "_cache", None)
    if ic is None:
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        ic = QIcon(pm)
        _dd_blank_icon._cache = ic
    return ic


ROW_H = 22
SMALL_ROWS = 3
DROP_ARROW_H = 12
DROP_TXT_H = 18
S2_ICON_H = 33
S2_TXT_H = 17
S2_ARW_H = 18
S2_ARW_DY = 2
BIG_MIN_W = 44
SMALL_MIN_W = 64
CONTENT_H = ROW_H * SMALL_ROWS + (SMALL_ROWS - 1)
GROUP_PAD = 4
HEADER_H = 24
TAB_ROW_H = 27
TAB_LINE_H = 2
TAB_HOVER_LINE_H = TAB_LINE_H
TAB_FONT_PT = 9.5
TAB_MARGIN_X = 3


def fit_icon(btn, action):
    if btn is None or action is None:
        return
    try:
        name = action.property("ggsIconName")
    except Exception:
        exc_note("fit_icon @ ggis/ui/framework/ribbon.py:153")
        name = None
    if not name:
        return
    try:
        sz = btn.iconSize()
        n = int(max(int(sz.width()), int(sz.height())))
    except Exception:
        exc_note("fit_icon @ ggis/ui/framework/ribbon.py:160")
        return
    if n > 0:
        try:
            btn.setIcon(icons.icon(str(name), size=n))
        except Exception:
            exc_note("fit_icon @ ggis/ui/framework/ribbon.py:165")
            pass


def _is_flex_spacer(item):
    sp = item.spacerItem() if item is not None else None
    if sp is None:
        return False
    try:
        return bool(sp.expandingDirections() & Qt.Orientation.Vertical)
    except Exception:
        exc_note("_is_flex_spacer @ ggis/ui/framework/ribbon.py:180")
        return False


def _small_used(col):
    n = 0
    for i in range(col.count()):
        it = col.itemAt(i)
        if it is None or _is_flex_spacer(it):
            continue
        n += 1
    return n


def _add_menu_header(menu, title, before=None):
    act = QAction(str(title or "…"), menu)
    act.setEnabled(False)
    try:
        f = act.font()
        f.setBold(True)
        act.setFont(f)
    except Exception:
        exc_note("_add_menu_header @ ggis/ui/framework/ribbon.py:219")
        pass
    if before is not None:
        menu.insertAction(before, act)
    else:
        menu.addAction(act)
    return act


class DropWrap(QFrame):

    def sizeHint(self):
        hint = super().sizeHint()
        main = self.property("dropdownMain")
        if self.property("style2") and main is not None:
            return QSize(min(hint.width(), main.minimumWidth()),
                         hint.height())
        return hint

    def _main_action(self):
        main = self.property("dropdownMain")
        if main is None:
            return None
        try:
            real = main.property("style2MainAction")
            if real is not None:
                return real
        except (RuntimeError, AttributeError):
            exc_note("_main_action @ ggis/ui/framework/ribbon.py:325")
            pass
        try:
            return main.defaultAction()
        except (RuntimeError, AttributeError):
            exc_note("_main_action @ ggis/ui/framework/ribbon.py:329")
            return None

    def _active_state(self):
        act = self._main_action()
        variant = self.property("s2variant")
        if not self.isEnabled() or (act is not None and not act.isEnabled()):
            return False, False, False
        checked = variant in ("GgsBigCheckButtonStyle1", "GgsBigMenuButtonStyle4") and act is not None \
            and act.isChecked()
        if (not checked) and variant == "GgsBigMenuButtonStyle4":
            if self.property("ddActiveByMain"):
                checked = act is not None and act.isChecked()
            else:
                menu = self.property("dropdownMenu")
                if menu is not None:
                    checked = any(a.isChecked() for a in menu.actions())
        return (bool(self.property("ddHover")),
                bool(self.property("ddDown")),
                bool(checked))

    def paintEvent(self, ev):
        super().paintEvent(ev)
        hover, down, checked = self._active_state()
        if not (hover or down or checked):
            return
        dark = icons.is_dark()
        c = lambda k: QColor(themes.theme_color(k, dark))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if down:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c("panel_dn"))
            p.drawRoundedRect(r, 4, 4)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(c("border"), 1))
            p.drawRoundedRect(r, 4, 4)
        elif checked:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c("accent_soft"))
            p.drawRoundedRect(r, 4, 4)
            if hover:
                g = QColor(255, 255, 255)
                g.setAlpha(30 if dark else 64)
                p.setBrush(g)
                p.drawRoundedRect(r, 4, 4)
        elif hover:
            if self.property("s2variant") in ("GgsBigMenuButtonStyle1", "GgsBigButtonStyle1", "GgsBigCheckButtonStyle1"):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c("panel_hi"))
                p.drawRoundedRect(r, 4, 4)
            else:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(c("panel_hi"), 1))
                p.drawRoundedRect(r, 4, 4)


class RibbonGroup(QWidget):

    def __init__(self, title, parent=None, small_rows=SMALL_ROWS):
        super().__init__(parent)
        self.setObjectName("GgsRibbonGroup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._title = i18n.tr(title)
        self._small_rows = max(1, int(small_rows))
        self._small_cols = []
        self._drop_state = {}
        self._btn_meta = []
        self._icon_fits = []
        self._drop_arrows = {}

        self._big_row = QHBoxLayout()
        self._big_row.setContentsMargins(0, 0, 0, 0)
        self._big_row.setSpacing(1)

        self._small_wrap = QHBoxLayout()
        self._small_wrap.setContentsMargins(0, 0, 0, 0)
        self._small_wrap.setSpacing(1)

        body = GgsRibbonBody()
        body.setFixedHeight(CONTENT_H)
        content = QHBoxLayout(body)
        content.setContentsMargins(1, 0, 1, 0)
        content.setSpacing(2)
        content.addLayout(self._big_row)
        content.addLayout(self._small_wrap)
        self._body = body

        cap = GgsRibbonCaption(self._title)
        self._cap = cap
        self._update_cap_height()
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter
                         | Qt.AlignmentFlag.AlignBottom)

        self._compact_btn = QToolButton()
        self._compact_btn.setAutoRaise(True)
        self._compact_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._compact_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._compact_btn.setIcon(icons.icon("chevron_down"))
        self._compact_btn.setIconSize(QSize(BIG_ICON, BIG_ICON))
        self._compact_btn.setFixedHeight(S2_ICON_H)
        self._compact_btn.setProperty("style2Icon", True)
        self._compact_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                        QSizePolicy.Policy.Fixed)
        self._compact_btn.setToolTip(self._title)

        _c_txt = QToolButton()
        _c_txt.setAutoRaise(True)
        _c_txt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _c_txt.setText(self._title)
        _c_txt.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        _c_txt.setFixedHeight(S2_TXT_H)
        _c_txt.setProperty("s2Seg", True)
        _c_txt.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)

        _c_arw = QToolButton()
        _c_arw.setAutoRaise(True)
        _c_arw.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        _c_arw.setArrowType(Qt.ArrowType.DownArrow)
        _c_arw.setFixedHeight(S2_ARW_H)
        _c_arw.setProperty("s2Seg", True)
        _c_arw.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Fixed)
        self._compact_txt = _c_txt
        self._compact_arw = _c_arw
        for _w in (self._compact_btn, _c_txt, _c_arw):
            try:
                hand_cursor(_w)
            except Exception:
                exc_note("__init__ @ ggis/ui/framework/ribbon.py:518")
                pass

        self._compact_menu = QMenu(self)
        wrap = DropWrap()
        wrap.setObjectName("GgsRibbonDrop")
        wrap.setProperty("style2", True)
        wrap.setProperty("s2variant", "GgsBigMenuButtonStyle1")
        wrap.setProperty("dropdownMenu", self._compact_menu)
        wrap.setProperty("dropdownMain", self._compact_btn)
        _cw = QVBoxLayout(wrap)
        _cw.setContentsMargins(0, 0, 0, 0)
        _cw.setSpacing(0)
        _cw.addWidget(self._compact_btn)
        _cw.addWidget(_c_txt)
        _cw.addWidget(_c_arw)
        wrap.setFixedHeight(CONTENT_H)
        self._compact_wrap = wrap

        def _set(prop, on):
            if on and prop in ("ddHover", "ddDown") and not wrap.isEnabled():
                return
            wrap.setProperty(prop, on)
            st = wrap.style()
            for _w in (wrap, self._compact_btn, _c_txt, _c_arw):
                st.unpolish(_w)
                st.polish(_w)
            wrap.update()

        def _open_menu():
            menu = self._compact_menu
            self._fill_compact_menu(menu)
            menu.exec(wrap.mapToGlobal(QPoint(0, wrap.height())))

        for _w in (wrap, self._compact_btn, _c_txt, _c_arw):
            _w.setProperty("inDrop", True)
            _w.installEventFilter(self)
        self._drop_state[wrap] = {"menu": self._compact_menu, "set": _set,
                                  "open": _open_menu}
        self._compact_menu.aboutToShow.connect(lambda: _set("ddDown", True))
        self._compact_menu.aboutToHide.connect(lambda: _set("ddDown", False))

        self._compact_host = QWidget()
        _ch = QVBoxLayout(self._compact_host)
        _ch.setContentsMargins(0, 0, 0, 0)
        _ch.addStretch(1)
        _ch.addWidget(self._compact_wrap)
        _ch.addStretch(1)
        self._compact_host.setVisible(False)

        self._compact_txt.setText("")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(GROUP_PAD, 2, GROUP_PAD, 0)
        lay.setSpacing(1)
        lay.addWidget(body, 1)
        lay.addWidget(self._compact_host, 1)
        lay.addWidget(cap, 0)
        self._lay = lay
        lay.setAlignment(cap, Qt.AlignmentFlag.AlignBottom)
        self._compact = False
        self._view_compact = False
        self._ovf_hidden = False
        self._w_wide = 0

    def _cap_height_natural(self):
        try:
            return int(self._cap.fontMetrics().height()) + 1
        except Exception:
            exc_note("_cap_height_natural @ ggis/ui/framework/ribbon.py:634")
            return 16

    def _update_cap_height(self):
        h = self._cap_height_natural()
        self._cap.setFixedHeight(h)
        lay = getattr(self, "_lay", None)
        if lay is not None:
            try:
                lay.setAlignment(self._cap, Qt.AlignmentFlag.AlignBottom)
            except Exception:
                exc_note("_update_cap_height @ ggis/ui/framework/ribbon.py:652")
                pass

    def is_compact(self):
        return self._compact or self._view_compact

    def is_view_compact(self):
        return self._view_compact

    def _apply_compact_visibility(self):
        on = self._compact or self._view_compact
        self._body.setVisible(not on)
        self._compact_host.setVisible(on)

    def set_view_compact(self, on):
        on = bool(on)
        if on == self._view_compact:
            return False
        self._view_compact = on
        self._apply_compact_visibility()
        self.updateGeometry()
        return True

    def set_compact(self, on):
        on = bool(on)
        if on == self._compact:
            return False
        if on:
            self._remember_wide()
            self._sync_compact_icon()
        self._compact = on
        self._apply_compact_visibility()
        self.updateGeometry()
        return True

    def _remember_wide(self):
        w = self.sizeHint().width()
        if w > 0:
            self._w_wide = w
        return self._w_wide

    def ideal_width(self):
        if not self._compact:
            self._remember_wide()
        if self._w_wide > 0:
            return self._w_wide
        return max(0, self.sizeHint().width())

    def _popup_compact_menu(self):
        menu = self._compact_menu
        if menu is None:
            return
        self._fill_compact_menu(menu)
        btn = self._compact_btn
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))

    def _compact_lead_action(self):
        first = None
        for a in self.actions():
            try:
                if a.isSeparator():
                    continue
                ra = self._real_action(a)
                if not ra.isVisible():
                    continue
                if first is None:
                    first = ra
                if ra.property("ggsIconName") or not ra.icon().isNull():
                    return ra
            except Exception:
                exc_note("_compact_lead_action @ ggis/ui/framework/ribbon.py:791")
                continue
        return first

    def _sync_compact_icon(self):
        btn = getattr(self, "_compact_btn", None)
        if btn is None:
            return
        a = self._compact_lead_action()
        ic = None
        if a is not None:
            try:
                nm = a.property("ggsIconName")
                sz = btn.iconSize()
                n = int(max(int(sz.width()), int(sz.height())))
                if nm and n > 0:
                    ic = icons.icon(str(nm), size=n)
            except Exception:
                exc_note("_sync_compact_icon @ ggis/ui/framework/ribbon.py:816")
                ic = None
            if ic is None or ic.isNull():
                try:
                    ic = a.icon()
                except Exception:
                    exc_note("_sync_compact_icon @ ggis/ui/framework/ribbon.py:821")
                    ic = None
        if ic is None or ic.isNull():
            ic = icons.icon("chevron_down")
        try:
            if ic is not None and not ic.isNull():
                btn.setIcon(ic)
        except RuntimeError:
            exc_note("_sync_compact_icon @ ggis/ui/framework/ribbon.py:828")
            pass

    def compact_width(self):
        wrap = getattr(self, "_compact_wrap", None)
        if wrap is None:
            return 0
        m = self._lay.contentsMargins()
        w = wrap.sizeHint().width()
        if w <= 0:
            lay = wrap.layout()
            if lay is not None:
                w = max(0, lay.sizeHint().width())
                if w <= 0:
                    w = max(0, lay.minimumSize().width())
            if w <= 0:
                w = max((c.sizeHint().width()
                         for c in wrap.findChildren(QWidget)), default=0)
        try:
            w = max(w, self._cap.sizeHint().width())
        except Exception:
            exc_note("compact_width @ ggis/ui/framework/ribbon.py:866")
            pass
        return w + m.left() + m.right()

    def is_overflow_hidden(self):
        return self._ovf_hidden

    def set_overflow_hidden(self, on):
        on = bool(on)
        if on == self._ovf_hidden:
            return False
        self._ovf_hidden = on
        self.setVisible(not on)
        return True

    def _fill_compact_menu(self, menu):
        menu.clear()
        self.fill_menu(menu)
        self._sync_compact_icon()

    def fill_menu(self, menu):
        n = 0
        for a in self.actions():
            try:
                if a.isSeparator():
                    if n:
                        menu.addSeparator()
                    continue
                ra = self._real_action(a)
                if not ra.isVisible():
                    continue
                sub = self._submenu_of(ra)
                if sub is None:
                    menu.addAction(ra)
                    n += 1
                    continue
                sm = menu.addMenu(ra.icon(), ra.text())
                sm.setProperty("ggsCompactSub", True)
                sub_acts = list(sub.actions())
                if sub_acts \
                        and str(sub_acts[0].text() or "").strip() \
                        == str(ra.text() or "").strip():
                    sub_acts = sub_acts[1:]
                    while sub_acts and sub_acts[0].isSeparator():
                        sub_acts = sub_acts[1:]
                for sa in sub_acts:
                    sm.addAction(sa)
                n += 1
            except Exception:
                exc_note("fill_menu @ ggis/ui/framework/ribbon.py:961")
                continue
        if not n:
            act = menu.addAction(i18n.tr("（本组暂无可用命令）"))
            act.setEnabled(False)
        return n

    @staticmethod
    def _real_action(a):
        try:
            real = a.property("ggsRealAction")
            if real is not None:
                return real
        except Exception:
            exc_note("_real_action @ ggis/ui/framework/ribbon.py:981")
            pass
        return a

    @staticmethod
    def _submenu_of(a):
        for get in (lambda: a.property("ggsDropdownMenu"),
                    a.menu):
            try:
                sub = get()
            except Exception:
                exc_note("_submenu_of @ ggis/ui/framework/ribbon.py:1000")
                sub = None
            if sub is not None:
                try:
                    if sub.actions():
                        return sub
                except Exception:
                    exc_note("_submenu_of @ ggis/ui/framework/ribbon.py:1006")
                    pass
        return None

    def add_action(self, action, big=True, tip=None, col=None,
                   icon_only=False, dropdown=False, style2=False,
                   variant=None, _from_dropdown=False):
        if big:
            if variant is None and not _from_dropdown:
                raise ValueError(
                    "add_action(big=True) 必须显式传 variant="
                    "'GgsBigButtonStyle1' / 'GgsBigCheckButtonStyle1' "
                    "(带菜单的传对应 GgsBigMenuButtonStyle*)；不允许静默"
                    "退化成默认 QToolButton。动作：{0!r}".format(
                        getattr(action, "text", lambda: action)()))
            if variant in ("GgsBigButtonStyle1", "GgsBigCheckButtonStyle1"):
                return self._add_style01(action, tip=tip, variant=variant)
        btn = (SmallDropButton() if (dropdown and not big)
               else QToolButton())
        if dropdown and not big:
            btn.setProperty("dropSmall", True)
        if style2 and not big:
            btn.setProperty("style2", True)
            if dropdown:
                btn.setProperty("splitArrow", True)
        elif style2 and big:
            btn.setProperty("style2Icon", True)
        if not big and not dropdown and not style2:
            btn.setObjectName(
                "GgsSmallButtonStyle1" if icon_only
                else "GgsSmallButtonStyle2")
        btn.setDefaultAction(action)
        btn.setAutoRaise(True)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        fm = btn.fontMetrics()
        if big:
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setProperty("ribbonBig", True)
            btn.setIconSize(QSize(BIG_ICON, BIG_ICON))
            btn.setFixedHeight(CONTENT_H - DROP_ARROW_H)
            w = fm.horizontalAdvance(action.text()) + 6
            btn.setMinimumWidth(max(BIG_MIN_W, w))
            if tip:
                btn.setToolTip(i18n.tr(tip))
        elif icon_only:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            btn.setFixedSize(ROW_H + (10 if dropdown else 6), ROW_H)
            if tip:
                btn.setToolTip(i18n.tr(tip))
        else:
            btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            btn.setFixedHeight(ROW_H)
            w = (fm.horizontalAdvance(action.text()) + SMALL_ICON + 10
                 + (25 if (dropdown and style2) else
                    9 if dropdown else 0))
            btn.setMinimumWidth(max(SMALL_MIN_W, w) if action.text() else w)
        self._btn_meta.append((btn, big, icon_only))
        self._icon_fits.append((btn, action))
        fit_icon(btn, action)
        if big:
            self._big_row.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self._put_small(col if col is not None else self._small_slot(),
                            btn)
        return btn

    def _put_small(self, col, widget=None, spacing=None):
        if col.count():
            last = col.itemAt(col.count() - 1)
            if _is_flex_spacer(last):
                col.removeItem(last)
        if widget is not None:
            col.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
        elif spacing:
            col.addSpacing(spacing)
        col.addStretch(1)

    def _add_style01(self, action, tip=None, variant="GgsBigButtonStyle1"):
        btn = QToolButton()
        btn.setAutoRaise(True)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setDefaultAction(action)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.setIconSize(QSize(BIG_ICON, BIG_ICON))
        btn.setFixedHeight(S2_ICON_H)
        btn.setProperty("style2Icon", True)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                          QSizePolicy.Policy.Fixed)
        self._icon_fits.append((btn, action))
        fit_icon(btn, action)
        txt = QToolButton()
        txt.setAutoRaise(True)
        txt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        txt.setDefaultAction(action)
        txt.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        txt.setFixedHeight(S2_TXT_H)
        txt.setProperty("s2Seg", True)
        txt.setSizePolicy(QSizePolicy.Policy.Expanding,
                          QSizePolicy.Policy.Fixed)
        w = max(BIG_MIN_W, txt.fontMetrics().horizontalAdvance(
            action.text()) + 6)
        btn.setMinimumWidth(w)
        txt.setMinimumWidth(w)
        if tip:
            btn.setToolTip(i18n.tr(tip))
            txt.setToolTip(i18n.tr(tip))
        wrap = DropWrap()
        wrap.setObjectName("GgsRibbonDrop")
        wrap.setProperty("style2", True)
        wrap.setProperty("s2variant", variant)
        wrap.setProperty("dropdownMain", btn)
        if tip:
            wrap.setToolTip(i18n.tr(tip))
        if variant == "GgsBigCheckButtonStyle1":
            def _wrap_update(*_a):
                try:
                    wrap.update()
                except RuntimeError:
                    exc_note("_wrap_update @ ggis/ui/framework/ribbon.py:1216")
                    pass
            action.toggled.connect(_wrap_update)
            action.changed.connect(_wrap_update)
        wrap.setFixedHeight(CONTENT_H)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(btn)
        lay.addWidget(txt)
        lay.addSpacing(S2_ARW_H)
        self._btn_meta.append((btn, True, False))
        self._drop_arrows[btn] = [txt]

        def _alive(w):
            try:
                return shiboken6.isValid(w)
            except Exception:
                exc_note("_alive @ ggis/ui/framework/ribbon.py:1250")
                return False

        def _set(prop, on):
            if not _alive(wrap):
                return
            if on and prop in ("ddHover", "ddDown") \
                    and not (wrap.isEnabled() and action.isEnabled()):
                return
            wrap.setProperty(prop, on)
            st = wrap.style()
            st.unpolish(wrap)
            st.polish(wrap)
            wrap.update()

        def _sync_off(*_a):
            if not _alive(wrap):
                try:
                    action.changed.disconnect(_sync_off)
                except Exception:
                    exc_note("_sync_off @ ggis/ui/framework/ribbon.py:1281")
                    pass
                try:
                    action.enabledChanged.disconnect(_sync_off)
                except Exception:
                    exc_note("_sync_off @ ggis/ui/framework/ribbon.py:1285")
                    pass
                return
            off = not (wrap.isEnabled() and action.isEnabled())
            if wrap.property("ddOff") is off:
                return
            wrap.setProperty("ddOff", off)
            _set("ddHover", False)
            _set("ddDown", False)
            st = wrap.style()
            for w in (wrap, btn, txt):
                if not _alive(w):
                    continue
                st.unpolish(w)
                st.polish(w)
            wrap.update()

        _sync_off()
        action.changed.connect(_sync_off)
        try:
            action.enabledChanged.connect(_sync_off)
        except Exception:
            exc_note("_add_style01 @ ggis/ui/framework/ribbon.py:1306")
            pass

        for x in (wrap, btn, txt):
            x.installEventFilter(self)
        btn.pressed.connect(lambda: _set("ddDown", True))
        txt.pressed.connect(lambda: _set("ddDown", True))
        btn.released.connect(lambda: _set("ddDown", False))
        txt.released.connect(lambda: _set("ddDown", False))
        self._drop_state[wrap] = {"menu": None, "set": _set, "open": None}
        self._big_row.addWidget(wrap, 0, Qt.AlignmentFlag.AlignTop)
        return btn

    def small_column(self):
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._small_cols.append(col)
        self._small_wrap.addLayout(col)
        col.addStretch(1)
        return col

    def add_placeholder(self, col=None):
        self._put_small(col if col is not None else self._small_slot(),
                        spacing=ROW_H)

    def add_dropdown(self, action, menu, big=True, tip=None, col=None,
                     icon_only=False, style2=False, variant=None,
                     active_by_main=False):
        btn = self.add_action(action, big=big, tip=tip, col=col,
                              icon_only=icon_only, dropdown=not big,
                              style2=style2, _from_dropdown=True)
        try:
            action.setProperty("ggsDropdownMenu", menu)
        except Exception:
            exc_note("add_dropdown @ ggis/ui/framework/ribbon.py:1385")
            pass
        action.setProperty("ggis_dropdown", True)
        if style2 and big:
            ph = QAction(action.icon(), action.text(), btn)
            try:
                ph.setProperty("ggsRealAction", action)
            except Exception:
                exc_note("add_dropdown @ ggis/ui/framework/ribbon.py:1412")
                pass
            if tip:
                ph.setToolTip(i18n.tr(tip))
            else:
                src = action.toolTip()
                if src:
                    ph.setToolTip(src)
            ph.setEnabled(action.isEnabled())
            def _sync_ph_enabled(on, _ph=ph):
                try:
                    _ph.setEnabled(bool(on))
                except Exception:
                    exc_note("_sync_ph_enabled @ ggis/ui/framework/ribbon.py:1433")
                    pass
            action.enabledChanged.connect(_sync_ph_enabled)
            if variant in ("GgsBigMenuButtonStyle2", "GgsBigMenuButtonStyle1"):
                def _sync_ph_icon(_ph=ph):
                    try:
                        ic = action.icon()
                        if not ic.isNull():
                            _ph.setIcon(ic)
                    except Exception:
                        exc_note("_sync_ph_icon @ ggis/ui/framework/ribbon.py:1451")
                        pass
                action.changed.connect(_sync_ph_icon)
            btn.setProperty("style2MainAction", action)
            btn.setDefaultAction(ph)
        else:
            btn.setMenu(menu)
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu.aboutToShow.connect(lambda: btn.setDown(True))
            menu.aboutToHide.connect(lambda: btn.setDown(False))
        if not big:
            return btn
        self._big_row.takeAt(self._big_row.indexOf(btn))
        zone = None
        if style2:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            btn.setFixedHeight(S2_ICON_H)
            self._icon_fits.append((btn, action))
            fit_icon(btn, action)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
            txt_btn = QToolButton()
            txt_btn.setAutoRaise(True)
            txt_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            txt_btn.setDefaultAction(action)
            txt_btn.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextOnly)
            txt_btn.setFixedHeight(S2_TXT_H)
            hand_cursor(txt_btn)
            txt_btn.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Fixed)
            txt_btn.setProperty("s2Seg", True)
            arw = SmallDropButton()
            arw.setProperty("arrowCentered", True)
            arw.setProperty("arrowDy", S2_ARW_DY)
            arw.setAutoRaise(True)
            arw.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            arw.setFixedHeight(S2_ARW_H)
            hand_cursor(arw)
            arw.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Fixed)
            arw.setProperty("s2Seg", True)
            txt_btn.setMinimumWidth(btn.minimumWidth())
            arw.setMinimumWidth(btn.minimumWidth())
            zone = GgsRibbonDropZone()
            zone.setProperty("inDrop", True)
            zone.setFixedHeight(S2_TXT_H + S2_ARW_H)
            zl = QVBoxLayout(zone)
            zl.setContentsMargins(0, 0, 0, 0)
            zl.setSpacing(0)
            zl.addWidget(txt_btn)
            zl.addWidget(arw)
            for w in (txt_btn, arw):
                w.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            extras = [txt_btn, arw]
        else:
            btn.setProperty("inDrop", True)
            btn.setFixedHeight(CONTENT_H - DROP_ARROW_H)
            arrow = QToolButton()
            arrow.setProperty("inDrop", True)
            arrow.setAutoRaise(True)
            arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            arrow.setArrowType(Qt.ArrowType.DownArrow)
            arrow.setFixedSize(btn.minimumWidth(), DROP_ARROW_H)
            hand_cursor(arrow)
            extras = [arrow]
        drop_arrow = arw if style2 else arrow
        drop_arrow.setEnabled(action.isEnabled())
        def _sync_drop_arrow(on, _a=drop_arrow):
            try:
                _a.setEnabled(bool(on))
            except Exception:
                exc_note("_sync_drop_arrow @ ggis/ui/framework/ribbon.py:1549")
                pass
        action.enabledChanged.connect(_sync_drop_arrow)
        self._drop_arrows[btn] = extras

        wrap = DropWrap() if style2 else QFrame()
        wrap.setObjectName("GgsRibbonDrop")
        wrap.setProperty("dropdownMenu", menu)
        wrap.setProperty("dropdownMain", btn)
        if style2:
            wrap.setProperty("style2", True)
            if variant:
                wrap.setProperty("s2variant", variant)
            if active_by_main:
                wrap.setProperty("ddActiveByMain", True)
        wrap.setFixedHeight(CONTENT_H)
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(btn)
        if style2:
            lay.addWidget(zone)
        else:
            for x in extras:
                lay.addWidget(x)

        target = wrap

        def _set(prop, on):
            if on and prop in ("ddHover", "ddDown") \
                    and not (wrap.isEnabled() and action.isEnabled()):
                return
            target.setProperty(prop, on)
            st = target.style()
            st.unpolish(target)
            st.polish(target)
            target.update()
            if style2:
                for w in (btn, zone):
                    st.unpolish(w)
                    st.polish(w)

        def _sync_off(*_a):
            try:
                off = not (wrap.isEnabled() and action.isEnabled())
                if wrap.property("ddOff") is off:
                    return
                wrap.setProperty("ddOff", off)
                _set("ddHover", False)
                _set("ddDown", False)
                st = wrap.style()
                kids = [wrap, btn] + ([zone] if zone is not None else [])
                for w in kids:
                    st.unpolish(w)
                    st.polish(w)
                wrap.update()
            except RuntimeError:
                exc_note("_sync_off @ ggis/ui/framework/ribbon.py:1628")
                pass

        _sync_off()
        action.changed.connect(_sync_off)
        try:
            action.enabledChanged.connect(_sync_off)
        except Exception:
            exc_note("add_dropdown @ ggis/ui/framework/ribbon.py:1635")
            pass
        if tip:
            wrap.setToolTip(i18n.tr(tip))
            if zone is not None:
                zone.setToolTip(i18n.tr(tip))
        if style2:
            for w in (wrap, btn, zone):
                w.installEventFilter(self)
            btn.pressed.connect(lambda: _set("ddDown", True))
            btn.released.connect(lambda: _set("ddDown", False))
            if variant == "GgsBigMenuButtonStyle1":
                btn.setProperty("inDrop", True)
            elif variant in ("GgsBigMenuButtonStyle2", "GgsBigMenuButtonStyle3", "GgsBigMenuButtonStyle4"):
                def _trigger_rep():
                    if not (wrap.isEnabled() and action.isEnabled()):
                        return
                    acts = menu.actions()
                    rep = None
                    if variant in ("GgsBigMenuButtonStyle3", "GgsBigMenuButtonStyle4"):
                        rep = next((a for a in acts if a.isChecked()),
                                   None)
                        if rep is None:
                            rep = getattr(wrap, "_dd_last_rep", None)
                    if rep is None and acts:
                        rep = acts[0]
                    if rep is not None:
                        rep.trigger()
                btn.released.connect(_trigger_rep)
                _follow_menu_icon = (
                    variant == "GgsBigMenuButtonStyle4"
                    or (variant == "GgsBigMenuButtonStyle3" and any(
                        a.isCheckable() for a in menu.actions())))
                if variant == "GgsBigMenuButtonStyle3" and not _follow_menu_icon:
                    def _sync_ph_icon2(_ph=ph):
                        try:
                            ic = action.icon()
                            if not ic.isNull():
                                _ph.setIcon(ic)
                        except Exception:
                            exc_note("_sync_ph_icon2 @ ggis/ui/framework/ribbon.py:1699")
                            pass
                    action.changed.connect(_sync_ph_icon2)
                if _follow_menu_icon:
                    def _sync_icon():
                        try:
                            rep = next((a for a in menu.actions()
                                       if a.isChecked()), None)
                            if rep is None:
                                rep = getattr(wrap, "_dd_last_rep", None)
                            if rep is None and menu.actions():
                                rep = menu.actions()[0]
                            if rep is not None:
                                wrap._dd_last_rep = rep
                                ic = rep.icon()
                                try:
                                    _nm = rep.property("ggsIconName")
                                    if _nm:
                                        _sz = btn.iconSize()
                                        _n = int(max(int(_sz.width()),
                                                     int(_sz.height())))
                                        if _n > 0:
                                            ic = icons.icon(str(_nm),
                                                            size=_n)
                                except Exception:
                                    exc_note("_sync_icon @ ggis/ui/framework/ribbon.py:1732")
                                    pass
                                da = btn.defaultAction()
                                if da is not None:
                                    da.setIcon(ic if not ic.isNull()
                                               else _dd_blank_icon())
                                t = rep.toolTip()
                                if not t and tip:
                                    t = i18n.tr(tip)
                                if t:
                                    if da is not None:
                                        da.setToolTip(t)
                                    if zone is not None:
                                        zone.setToolTip(t)
                                    wrap.setToolTip(t)
                        except RuntimeError:
                            exc_note("_sync_icon @ ggis/ui/framework/ribbon.py:1758")
                            pass
                    _sync_icon()
                    for a in menu.actions():
                        a.toggled.connect(lambda *_a: _sync_icon())
                        def _on_menu_triggered(checked=False, _a=a):
                            try:
                                wrap._dd_last_rep = _a
                            except Exception:
                                exc_note("_on_menu_triggered @ ggis/ui/framework/ribbon.py:1774")
                                pass
                            _sync_icon()
                        a.triggered.connect(_on_menu_triggered)
                        a.changed.connect(_sync_icon)
                    action.changed.connect(_sync_icon)
                if variant == "GgsBigMenuButtonStyle4":
                    def _wrap_update(*_a):
                        try:
                            wrap.update()
                        except RuntimeError:
                            exc_note("_wrap_update @ ggis/ui/framework/ribbon.py:1797")
                            pass
                    action.toggled.connect(_wrap_update)
                    action.changed.connect(_wrap_update)
                    for a in menu.actions():
                        a.toggled.connect(_wrap_update)
        else:
            for w in (wrap, btn) + tuple(extras):
                w.installEventFilter(self)

        def _open_menu():
            if not (wrap.isEnabled() and action.isEnabled()):
                return
            menu.exec(wrap.mapToGlobal(QPoint(0, wrap.height())))

        self._drop_state[wrap] = {"menu": menu, "set": _set,
                                  "open": _open_menu}

        menu.aboutToShow.connect(lambda: _set("ddDown", True))
        menu.aboutToHide.connect(lambda: _set("ddDown", False))
        if style2:
            def _sync_menu_enabled():
                on = wrap.isEnabled() and action.isEnabled()
                for a in menu.actions():
                    if not a.isSeparator():
                        a.setEnabled(on)
            menu.aboutToShow.connect(_sync_menu_enabled)

        self._big_row.addWidget(wrap)
        return btn

    def eventFilter(self, obj, ev):
        drop = self._drop_state.get(obj)
        target = obj if drop is not None else obj.parentWidget()
        st = self._drop_state.get(target) if target is not None else None
        if st is not None:
            t = ev.type()
            if t == QEvent.Type.Enter or t == QEvent.Type.HoverEnter:
                st["set"]("ddHover", True)
            elif t == QEvent.Type.Leave or t == QEvent.Type.HoverLeave:
                st["set"]("ddHover", False)
            elif (t == QEvent.Type.MouseButtonPress
                    and obj.property("inDrop")):
                st["open"]()
                return True
        return super().eventFilter(obj, ev)

    def _small_slot(self):
        for col in self._small_cols:
            if _small_used(col) < self._small_rows:
                return col
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        self._small_cols.append(col)
        self._small_wrap.addLayout(col)
        return col

    def add_widget(self, widget):
        self._big_row.addWidget(widget)
        return widget

    def actions(self):
        out = []
        for i in range(self._big_row.count()):
            it = self._big_row.itemAt(i)
            w = it.widget() if it else None
            if isinstance(w, QToolButton) and w.defaultAction() is not None:
                out.append(w.defaultAction())
            elif w is not None:
                for b in w.findChildren(QToolButton):
                    if b.defaultAction() is not None:
                        out.append(b.defaultAction())
                        break
        for col in self._small_cols:
            for i in range(col.count()):
                it = col.itemAt(i)
                w = it.widget() if it else None
                if isinstance(w, QToolButton) and w.defaultAction() is not None:
                    out.append(w.defaultAction())
        return out

    def add_separator(self):
        bar = GgsRibbonSep()
        bar.setFixedWidth(1)
        self._big_row.addWidget(bar)
        return bar

    def add_stretch(self):
        self._big_row.addStretch(1)

    def retheme_icons(self):
        for btn, action in list(self._icon_fits):
            try:
                fit_icon(btn, action)
            except RuntimeError:
                exc_note("retheme_icons @ ggis/ui/framework/ribbon.py:1926")
                pass
        self._sync_compact_icon()

    def retext_buttons(self):
        self._update_cap_height()
        for btn, big, icon_only in self._btn_meta:
            real = btn.property("style2MainAction")
            act = real if real is not None else btn.defaultAction()
            if act is None:
                continue
            fm = btn.fontMetrics()
            if big:
                w = max(BIG_MIN_W, fm.horizontalAdvance(act.text()) + 6)
                btn.setMinimumWidth(w)
                for x in self._drop_arrows.get(btn) or []:
                    if x.property("s2Seg"):
                        x.setMinimumWidth(w)
                    else:
                        x.setFixedWidth(w)
            elif not icon_only:
                small_drop = isinstance(btn, SmallDropButton)
                extra = (25 if (small_drop and btn.property("splitArrow"))
                         else 9 if small_drop else 0)
                w = max(SMALL_MIN_W,
                        fm.horizontalAdvance(act.text()) + SMALL_ICON + 10
                        + extra)
                btn.setMinimumWidth(w)


class RibbonPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsRibbonPage")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch(1)
        self._lay = lay
        self._n = 0
        self._groups = []

    def add_group(self, group):
        self._lay.insertWidget(self._lay.count() - 1, group)
        self._n += 1
        self._groups.append(group)
        return group

    def groups(self):
        return list(self._groups)

    def clear_groups(self):
        for g in list(self._groups):
            try:
                self._lay.removeWidget(g)
            except Exception:
                exc_note("clear_groups @ ggis/ui/framework/ribbon.py:2005")
                pass
            try:
                g.setParent(None)
            except Exception:
                exc_note("clear_groups @ ggis/ui/framework/ribbon.py:2009")
                pass
            try:
                g.deleteLater()
            except Exception:
                exc_note("clear_groups @ ggis/ui/framework/ribbon.py:2013")
                pass
        self._groups = []
        self._n = 0

    def set_view_compact(self, on):
        ch = False
        for g in self._groups:
            if g.set_view_compact(on):
                ch = True
        if ch:
            self.updateGeometry()
        return ch

    def is_view_compact(self):
        return bool(self._groups) and self._groups[0].is_view_compact()

    def fit_plan(self, avail):
        groups = self._groups
        n = len(groups)
        if n == 0:
            return 0, 0
        if self.is_view_compact():
            return 0, 0
        wide = [g.ideal_width() for g in groups]
        narrow = [g.compact_width() for g in groups]
        for h in range(0, n + 1):
            for k in range(h, n + 1):
                w = sum(wide[:n - k]) + sum(narrow[n - k:n - h])
                if w <= avail:
                    return k, h
        return n, n

    def apply_width(self, avail):
        groups = self._groups
        if not groups or avail <= 0:
            return False
        if self.is_view_compact():
            return False
        n = len(groups)
        k, h = self.fit_plan(avail)
        changed = False
        for i, g in enumerate(groups):
            if g.set_compact(i >= n - k):
                changed = True
            if g.set_overflow_hidden(i >= n - h):
                changed = True
        return changed


_SEL_BOLD_SHIFT = 0.30


class _RibbonTabBar(QTabBar):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover_index = -1

        self.setMouseTracking(True)

    def tabSizeHint(self, index):
        return super().tabSizeHint(index)

    def _set_hover(self, i):
        try:
            i = int(i)
        except Exception:
            exc_note("_set_hover @ ggis/ui/framework/ribbon.py:2155")
            i = -1
        if i == int(getattr(self, "_hover_index", -1)):
            return
        self._hover_index = i
        self.update()
        rib = getattr(self, "_ribbon", None)
        if rib is not None:
            try:
                rib._update_tab_indicator()
            except Exception:
                exc_note("_set_hover @ ggis/ui/framework/ribbon.py:2170")
                pass

    def _line_geom(self, index, full=False):
        try:
            rect = self.tabRect(index)
        except Exception:
            exc_note("_line_geom @ ggis/ui/framework/ribbon.py:2194")
            return (0, 0)
        if not rect.isValid() or rect.isEmpty():
            return (0, 0)
        inner = max(rect.width() - 2 * TAB_MARGIN_X, 12)
        if full:
            w = inner
        else:
            w = 0
            try:
                txt = self.tabText(index)
            except Exception:
                exc_note("_line_geom @ ggis/ui/framework/ribbon.py:2206")
                txt = ""
            if txt:
                try:
                    w = QFontMetrics(self.font()).horizontalAdvance(txt)
                except Exception:
                    exc_note("_line_geom @ ggis/ui/framework/ribbon.py:2211")
                    w = 0
            if w <= 0:
                w = max(int(rect.width() * 0.9), 12)
            w = min(w, inner)
        x = rect.x() + (rect.width() - w) // 2
        return (x, w)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        try:
            self._set_hover(self.tabAt(event.position().toPoint()))
        except Exception:
            exc_note("mouseMoveEvent @ ggis/ui/framework/ribbon.py:2223")
            pass

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._set_hover(-1)

    def _paint_hover_line(self):
        i = int(getattr(self, "_hover_index", -1))
        if i < 0 or i >= self.count() or i == self.currentIndex():
            return
        try:
            rect = self.tabRect(i)
        except Exception:
            exc_note("_paint_hover_line @ ggis/ui/framework/ribbon.py:2250")
            return
        if not rect.isValid() or rect.isEmpty():
            return
        try:
            col = QColor(themes.text_dim(settings.get("theme")))
            col.setAlpha(150)
        except Exception:
            exc_note("_paint_hover_line @ ggis/ui/framework/ribbon.py:2263")
            col = QColor(0, 0, 0)
        x, w = self._line_geom(i)
        if w <= 0:
            return
        y = self.height() - TAB_HOVER_LINE_H
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.fillRect(QRect(x, y, w, TAB_HOVER_LINE_H), col)
        p.end()

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            style = self.style()
            if self.drawBase():
                ob = QStyleOptionTabBarBase()
                try:
                    self.initStyleOptionBase(ob)
                except Exception:
                    exc_note(
                        "_RibbonTabBar.paintEvent"
                        " @ ggis/ui/framework/ribbon.py")
                style.drawPrimitive(QStyle.PE_FrameTabBarBase, ob, p, self)
            cur = self.currentIndex()
            for i in range(self.count()):
                try:
                    if hasattr(self, "isTabVisible") \
                            and not self.isTabVisible(i):
                        continue
                except Exception:
                    exc_note(
                        "_RibbonTabBar.paintEvent"
                        " @ ggis/ui/framework/ribbon.py")
                opt = QStyleOptionTab()
                self.initStyleOption(opt, i)
                if opt.text:
                    txt = opt.text
                    opt.text = ""
                    style.drawControl(QStyle.CE_TabBarTab, opt, p, self)
                    opt.text = txt
                    self._draw_tab_label(p, style, opt, i,
                                         bold=(i == cur))
                else:
                    style.drawControl(QStyle.CE_TabBarTab, opt, p, self)
        except Exception:
            exc_note(
                "_RibbonTabBar.paintEvent @ ggis/ui/framework/ribbon.py")
            p.end()
            super().paintEvent(event)
            return
        p.end()
        rib = getattr(self, "_ribbon", None)
        if rib is not None and rib._ctx_pages:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            cur = self.currentIndex()
            try:
                base = QColor(themes.accent(settings.get("theme")))
            except Exception:
                exc_note("paintEvent @ ggis/ui/framework/ribbon.py:2296")
                base = QColor(0, 0, 0)
            for j in range(len(rib._ctx_pages)):
                i = rib._main_count + j
                try:
                    if hasattr(self, "isTabVisible") and not self.isTabVisible(i):
                        continue
                except Exception:
                    exc_note("paintEvent @ ggis/ui/framework/ribbon.py:2305")
                    pass
                sel = (i == cur)
                rect = self.tabRect(i).adjusted(
                    TAB_MARGIN_X, 1, -TAB_MARGIN_X, -1)
                fill = QColor(base)
                fill.setAlpha(40 if sel else 18)
                p.setBrush(fill)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(QRectF(rect), 5, 5)
            p.end()
        self._paint_hover_line()


    def _draw_tab_label(self, p, style, opt, idx, bold=False):
        """所有页签统一自绘：同一 y 公式 + 同一字形渲染 => 相对位移恒 0。
        选中态只多做一道横向对称加宽（墨迹高度与常规体逐像素一致）。
        """
        txt = opt.text
        if not txt:
            return
        try:
            tr = style.subElementRect(QStyle.SE_TabBarTabText, opt, self)
            if not (tr.isValid() and not tr.isEmpty()):
                return
            freg = self.font()
            try:
                tc = self.tabTextColor(idx)
                if tc.isValid():
                    col = tc
                else:
                    th = settings.get("theme")
                    if (not bold) and idx == getattr(self, "_hover_index", -1):
                        col = QColor(themes.text_dim(th))
                    else:
                        col = QColor(themes.text(th))
            except Exception:
                exc_note("_draw_tab_label @ ggis/ui/framework/ribbon.py")
                col = QColor(0, 0, 0)
            fmI = QFontMetrics(freg)
            adv = fmI.horizontalAdvance(txt)
            if adv <= 0:
                return
            x = tr.x() + (tr.width() - adv) // 2
            y = tr.y() + (tr.height() - fmI.height()) // 2 + fmI.ascent()
            path = QPainterPath()
            path.addText(QPointF(float(x), float(y)), freg, txt)
            if path.isEmpty():
                return
            shape = path
            if bold:
                shape = (path.united(path.translated(_SEL_BOLD_SHIFT, 0))
                             .united(path.translated(-_SEL_BOLD_SHIFT, 0)))
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.fillPath(shape, QBrush(col))
        except Exception:
            import logging
            logging.getLogger("gmagis").warning(
                "_draw_tab_label failed (tab=%r)", txt, exc_info=True)

def make_app_button(parent=None):
    from ggis.common.styling import icons

    btn = GgsAppButton(parent)
    btn.setText(i18n.tr("工程"))
    btn.setIcon(icons.icon("project", color="#ffffff", size=16))
    btn.setIconSize(QSize(16, 16))
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    btn.setFixedHeight(25)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn.setToolTip(i18n.tr("工程") + "（新建 / 打开 / 保存 / 选项 / 退出）")
    fit_app_button(btn)
    return btn


def fit_app_button(btn):
    try:
        w = int(btn.sizeHint().width())
    except Exception:
        exc_note("fit_app_button @ ggis/ui/framework/ribbon.py:2489")
        w = 0
    if w <= 0:
        try:
            fm = btn.fontMetrics()
            w = fm.horizontalAdvance(btn.text()) + 16 + 16
        except Exception:
            exc_note("fit_app_button @ ggis/ui/framework/ribbon.py:2496")
            return
    try:
        btn.setFixedWidth(w)
    except Exception:
        exc_note("fit_app_button @ ggis/ui/framework/ribbon.py:2500")
        pass


class GgsRibbon(QWidget):

    collapsedChanged = Signal(bool)
    tabPicked = Signal(int, object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsRibbon")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        from ggis.common.styling import icons

        self.app_button = make_app_button(self)

        self.tabs = _RibbonTabBar()
        self.tabs._ribbon = self
        self.tabs.setObjectName("GgsRibbonTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabs.setDocumentMode(True)
        self.tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tabs.setFixedHeight(HEADER_H + 1)
        try:
            _tf = self.tabs.font()
            _tf.setPointSizeF(TAB_FONT_PT)
            self.tabs.setFont(_tf)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/ribbon.py:2563")
            pass
        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        try:
            self.tabs.currentChanged.connect(
                lambda *_: self._apply_ctx_text_colors())
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/ribbon.py:2574")
            pass

        self._tab_indicator = GgsRibbonTabIndicator(self)
        self._tab_indicator.setFixedHeight(TAB_LINE_H)
        self._tab_indicator.setFrameShape(QFrame.Shape.NoFrame)
        self._tab_indicator.setAutoFillBackground(True)
        self._tab_indicator.setStyleSheet(
            "background-color: {}; border: 0; border-radius: 0;".format(
                themes.accent(settings.get("theme"))))
        self._tab_indicator.hide()
        self.tabs.currentChanged.connect(self._update_tab_indicator)
        self.tabs.installEventFilter(self)

        self._main_count = 0
        self._ctx_pages = []
        self._ctx_colors = {}
        self._ctx_owners = []
        self._uid_seq = 0

        self._collapse_btn = GgsRibbonCollapseBtn()
        icons.bind(self._collapse_btn, "chevron_up")
        self._collapse_btn.setAutoRaise(True)
        self._collapse_btn.setToolTip(i18n.tr("折叠功能区"))
        self._collapse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._collapse_btn.setFixedSize(QSize(22, HEADER_H))
        self._collapse_btn.setAutoRaise(True)
        self._collapse_btn.clicked.connect(
            lambda: self.set_collapsed(not self._collapsed))

        self._right = QHBoxLayout()
        self._right.setContentsMargins(0, 0, 0, 0)
        self._right.setSpacing(6)
        self._right.addWidget(self._collapse_btn, 0,
                              Qt.AlignmentFlag.AlignVCenter)

        header = QHBoxLayout()
        header.setContentsMargins(6, 0, 6, 2)
        header.setSpacing(10)
        header.addWidget(self.app_button, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.tabs, 1)
        header.addLayout(self._right)

        self.stack = GgsRibbonStack()
        self.stack.setContentsMargins(2, 1, 2, 4)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addLayout(header)
        lay.addWidget(self.stack)

        self.tabs.currentChanged.connect(self._on_tab)
        self.tabs.tabBarDoubleClicked.connect(
            lambda _i: self.set_collapsed(not self._collapsed))
        self._collapsed = False
        self._prev_index = 0
        self._main_before_ctx = 0
        self.suppress_tab_picked = False
        self._batch_depth = 0
        self.tabGroupGuard = None
        QTimer.singleShot(0, self._normalize_stack_height)
        self._update_tab_indicator(0)

    def set_app_menu(self, menu):
        if menu is not None:
            self.app_button.setMenu(menu)


    def retext(self):
        fit_app_button(self.app_button)
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            page = w.widget() if isinstance(w, QScrollArea) else w
            for grp in getattr(page, "groups", lambda: [])():
                grp.retext_buttons()
            if isinstance(w, QScrollArea):
                self._update_overflow(w)
        self._normalize_stack_height()

    def add_tab(self, title, icon=None, tag=None):
        """新建页签并返回对应 RibbonPage。

 **主页签必须永远排在上下文页签左边**。
 原来这里两句都是**追加**（`tabs.addTab` + `stack.addWidget`）⇒ 只要
 "先建过上下文页签、之后又建主页签"，新主页签就会落到上下文页签
 **右边**。实测（`build/_r492ez_ctx_tabs.py`）：页签条一度是
 「地图 / **编辑 / 栅格图层** / 分析 / 视图 / 帮助」——上下文页签被
 夹在固定页签中间。
 现在：已经有上下文页签时，把新主页签**插到 `_main_count` 那个位置**
 （页签与页堆叠**同索引**插，两者一一对应的约定不变；插完
 `_ctx_pages[j]` 仍在 `_main_count + j`，映射不用动）。
 """
        page = RibbonPage()
        self._stamp_uid(page)
        wrap = self._wrap_page(page)
        try:
            _prev_cur = int(self.tabs.currentIndex())
        except Exception:
            exc_note("add_tab @ ggis/ui/framework/ribbon.py:2762")
            _prev_cur = -1
        if self._ctx_pages:
            i = self._main_count
            if icon is None or icon.isNull():
                self.tabs.insertTab(i, i18n.tr(title))
            else:
                self.tabs.insertTab(i, icon, i18n.tr(title))
            self.stack.insertWidget(i, wrap)
        else:
            i = self.tabs.count()
            if icon is None or icon.isNull():
                self.tabs.addTab(i18n.tr(title))
            else:
                self.tabs.addTab(icon, i18n.tr(title))
            self.stack.addWidget(wrap)
        self._main_count += 1
        try:
            if _prev_cur >= 0 and _prev_cur < self.tabs.count():
                if _prev_cur != int(self.tabs.currentIndex()):
                    self.set_current_tab(_prev_cur)
        except Exception:
            exc_note("add_tab @ ggis/ui/framework/ribbon.py:2785")
            pass
        if tag is not None:
            try:
                self.tabs.setTabData(i, tag)
            except Exception:
                exc_note("add_tab @ ggis/ui/framework/ribbon.py:2796")
                pass
        try:
            self._move_keep_tabs_to_tail()
        except Exception:
            exc_note("add_tab @ ggis/ui/framework/ribbon.py:2804")
            pass
        return page

    def attach_page(self, page, title, tag=None):
        if page is None:
            return None
        self._stamp_uid(page)
        wrap = self._wrap_page(page)
        try:
            _prev_cur = int(self.tabs.currentIndex())
        except Exception:
            exc_note("attach_page @ ggis/ui/framework/ribbon.py:2821")
            _prev_cur = -1
        if self._ctx_pages:
            i = self._main_count
            self.tabs.insertTab(i, i18n.tr(title))
            self.stack.insertWidget(i, wrap)
        else:
            i = self.tabs.count()
            self.tabs.addTab(i18n.tr(title))
            self.stack.addWidget(wrap)
        self._main_count += 1
        try:
            if _prev_cur >= 0 and _prev_cur < self.tabs.count():
                if _prev_cur != int(self.tabs.currentIndex()):
                    self.set_current_tab(_prev_cur)
        except Exception:
            exc_note("attach_page @ ggis/ui/framework/ribbon.py:2836")
            pass
        if tag is not None:
            try:
                self.tabs.setTabData(i, tag)
            except Exception:
                exc_note("attach_page @ ggis/ui/framework/ribbon.py:2841")
                pass
        try:
            self._move_keep_tabs_to_tail()
        except Exception:
            exc_note("attach_page @ ggis/ui/framework/ribbon.py:2845")
            pass
        return page

    def detach_tabs_by_tag(self, tag):
        out = []
        if tag is None:
            return out
        for i in range(self.tabs.count() - 1, -1, -1):
            if i >= self._main_count:
                continue
            try:
                if self.tabs.tabData(i) != tag:
                    continue
            except Exception:
                exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2874")
                continue
            try:
                title = self.tabs.tabText(i)
            except Exception:
                exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2878")
                title = ""
            wrap = None
            try:
                wrap = self.stack.widget(i)
            except Exception:
                exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2883")
                wrap = None
            page = None
            if wrap is not None:
                try:
                    page = wrap.widget()
                except Exception:
                    exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2889")
                    page = None
            try:
                self.tabs.removeTab(i)
            except Exception:
                exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2893")
                continue
            self._main_count = max(0, int(self._main_count) - 1)
            try:
                if wrap is not None:
                    wrap.setParent(None)
            except Exception:
                exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2900")
                pass
            out.append((title, page, wrap, tag))
        out.reverse()
        try:
            self._move_keep_tabs_to_tail()
        except Exception:
            exc_note("detach_tabs_by_tag @ ggis/ui/framework/ribbon.py:2908")
            pass
        return out

    def attach_tabs(self, entries):
        if not entries:
            return
        first_at = -1
        for entry in entries:
            if len(entry) >= 4:
                title, page, wrap, etag = entry[0], entry[1], entry[2], entry[3]
            else:
                title, page, wrap, etag = entry[0], entry[1], entry[2], None
            if wrap is None or page is None:
                continue
            try:
                i = self._main_count
                self.tabs.insertTab(i, i18n.tr(title))
                self.stack.insertWidget(i, wrap)
                self._main_count += 1
                if etag is not None:
                    self.tabs.setTabData(i, etag)
                if first_at < 0:
                    first_at = i
            except Exception:
                exc_note("attach_tabs @ ggis/ui/framework/ribbon.py:2947")
                continue
        try:
            self._move_keep_tabs_to_tail()
        except Exception:
            exc_note("attach_tabs @ ggis/ui/framework/ribbon.py:2952")
            pass
        if first_at >= 0:
            try:
                self.set_current_tab(first_at)
            except Exception:
                exc_note("attach_tabs @ ggis/ui/framework/ribbon.py:2961")
                pass
            try:
                sa = self.stack.widget(first_at)
                if sa is not None and hasattr(sa, "_overflow_btn"):
                    sa._overflow_btn.hide()
            except Exception:
                exc_note("attach_tabs @ ggis/ui/framework/ribbon.py:2967")
                pass
        try:
            self.tabs.updateGeometry()
            self.tabs.update()
        except Exception:
            exc_note("attach_tabs @ ggis/ui/framework/ribbon.py:2972")
            pass

    _TAB_ORDER = ("地图", "分析", "开始", "页面", "视图", "模型")

    def _move_keep_tabs_to_tail(self):
        try:
            n_main = min(int(self._main_count), self.tabs.count())
            if n_main <= 0:
                return

            def _rank(i):
                d = self.tabs.tabData(i)
                s = d if isinstance(d, str) else ""
                if s.startswith("__"):
                    return 1
                if ":" in s:
                    return 0
                return 2

            def _sub(i):
                t = self.tabs.tabText(i)
                for k in self._TAB_ORDER:
                    if t == k or t == i18n.tr(k):
                        return self._TAB_ORDER.index(k)
                return 99

            want = sorted(range(n_main), key=lambda i: (_rank(i), _sub(i), i))
            if want == list(range(n_main)):
                return
            cur_tag = None
            cur_text = None
            try:
                ci = int(self.tabs.currentIndex())
                if 0 <= ci < n_main:
                    cur_tag = self.tabs.tabData(ci)
                    cur_text = self.tabs.tabText(ci)
            except Exception:
                exc_note("_move_keep_tabs_to_tail @ ggis/ui/framework/ribbon.py:3047")
                cur_tag = None
            items = []
            for i in range(n_main):
                _vis = True
                try:
                    _vis = bool(self.tabs.isTabVisible(i))
                except Exception:
                    exc_note("_move_keep_tabs_to_tail @ ggis/ui/framework/ribbon.py:3057")
                    _vis = True
                items.append((self.tabs.tabText(i),
                              self.tabs.tabData(i),
                              self.stack.widget(i),
                              _vis))
            order = [items[k] for k in want]
            for i in range(n_main - 1, -1, -1):
                self.tabs.removeTab(i)
                w = self.stack.widget(i)
                if w is not None:
                    w.setParent(None)
            for k, (title, data, w, vis) in enumerate(order):
                self.tabs.insertTab(k, title)
                if w is not None:
                    self.stack.insertWidget(k, w)
                self.tabs.setTabData(k, data)
                try:
                    if hasattr(self.tabs, "setTabVisible"):
                        self.tabs.setTabVisible(k, vis)
                    else:
                        if w is not None:
                            w.setVisible(vis)
                except Exception:
                    exc_note("_move_keep_tabs_to_tail @ ggis/ui/framework/ribbon.py:3096")
                    pass
            if cur_tag is not None:
                target = -1
                for k, (t, data, _w, _vis) in enumerate(order):
                    if data == cur_tag and (cur_text is None or t == cur_text):
                        target = k
                        break
                if target < 0:
                    for k, (_t, data, _w, _vis) in enumerate(order):
                        if data == cur_tag:
                            target = k
                            break
                if target >= 0:
                    try:
                        self.set_current_tab(target)
                    except Exception:
                        exc_note("_move_keep_tabs_to_tail @ ggis/ui/framework/ribbon.py:3115")
                        pass
        except Exception:
            exc_note("_move_keep_tabs_to_tail @ ggis/ui/framework/ribbon.py:3117")
            pass

    def _wrap_page(self, page):
        sa = GgsRibbonScroll()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setWidget(page)

        btn = GgsRibbonOverflow(sa)
        btn.setText(">>")
        btn.setAutoRaise(True)
        btn.setToolTip(i18n.tr("更多分组"))
        hand_cursor(btn)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedSize(QSize(28, 22))
        btn.hide()
        btn.clicked.connect(lambda: self._open_overflow_menu(sa))
        sa._overflow_btn = btn
        sa.installEventFilter(self)
        page.installEventFilter(self)
        return sa

    def _update_overflow(self, sa):
        btn = getattr(sa, "_overflow_btn", None)
        page = sa.widget()
        if btn is None or page is None:
            return
        if not (hasattr(page, "apply_width") and hasattr(page, "fit_plan")):
            return
        vis = sa.viewport().width()
        _k, h = page.fit_plan(vis)
        need_btn = h > 0
        avail = max(1, vis - (btn.width() + 6)) if need_btn else vis
        if page.apply_width(avail):
            self._normalize_stack_height()
        if need_btn:
            btn.raise_()
            btn.move(vis - btn.width() - 2,
                     (sa.height() - btn.height()) // 2)
            btn.show()
        else:
            btn.hide()

    def _open_overflow_menu(self, sa):
        page = sa.widget()
        btn = getattr(sa, "_overflow_btn", None)
        if page is None:
            return
        sb = sa.horizontalScrollBar()
        vis_right = sb.value() + sa.viewport().width()
        menu = QMenu(self)
        listed = 0
        for g in page.groups() if hasattr(page, "groups") else []:
            hidden = bool(getattr(g, "is_overflow_hidden", lambda: False)())
            if not hidden:
                if g.x() + g.width() <= vis_right:
                    continue
            acts = g.actions() if hasattr(g, "actions") else []
            if acts:
                _add_menu_header(menu, getattr(g, "_title", "") or "…")
                if hasattr(g, "fill_menu"):
                    g.fill_menu(menu)
                else:
                    for a in acts:
                        menu.addAction(a)
                listed += 1
        if not listed:
            act = menu.addAction(i18n.tr("（没有更多分组）"))
            act.setEnabled(False)
        menu.exec(btn.mapToGlobal(
            QPoint(btn.width(), btn.height())) if btn is not None
            else sa.mapToGlobal(QPoint(0, 0)))

    def _stamp_uid(self, page):
        try:
            self._uid_seq = int(getattr(self, "_uid_seq", 0)) + 1
        except Exception:
            exc_note("_stamp_uid @ ggis/ui/framework/ribbon.py:3257")
            self._uid_seq = 1
        try:
            page._ggs_uid = int(self._uid_seq)
        except Exception:
            exc_note("_stamp_uid @ ggis/ui/framework/ribbon.py:3261")
            pass
        return page

    @staticmethod
    def uid_of_page(page):
        try:
            return int(getattr(page, "_ggs_uid", 0) or 0)
        except Exception:
            exc_note("uid_of_page @ ggis/ui/framework/ribbon.py:3270")
            return 0

    def page_at(self, index):
        try:
            w = self.stack.widget(int(index))
        except Exception:
            exc_note("page_at @ ggis/ui/framework/ribbon.py:3280")
            return None
        if w is None:
            return None
        try:
            return w.widget()
        except Exception:
            exc_note("page_at @ ggis/ui/framework/ribbon.py:3286")
            return None

    def current_uid(self):
        try:
            i = int(self.tabs.currentIndex())
        except Exception:
            exc_note("current_uid @ ggis/ui/framework/ribbon.py:3297")
            return 0
        if i < 0:
            return 0
        return self.uid_of_page(self.page_at(i))

    def index_of_uid(self, uid):
        try:
            uid = int(uid)
        except Exception:
            exc_note("index_of_uid @ ggis/ui/framework/ribbon.py:3311")
            return -1
        if uid <= 0:
            return -1
        for i in range(self.tabs.count()):
            if self.uid_of_page(self.page_at(i)) != uid:
                continue
            try:
                if hasattr(self.tabs, "isTabVisible") \
                        and not self.tabs.isTabVisible(i):
                    return -1
            except Exception:
                exc_note("index_of_uid @ ggis/ui/framework/ribbon.py:3322")
                return -1
            return i
        return -1

    def add_to_header(self, widget):
        try:
            widget.setFixedHeight(HEADER_H)
        except Exception:
            exc_note("add_to_header @ ggis/ui/framework/ribbon.py:3331")
            pass
        self._right.addWidget(widget)
        return widget

    def tab_index(self, identifier, owner=None):
        if isinstance(identifier, int):
            return identifier
        want = i18n.tr(identifier)
        j = self._ctx_index(want, owner)
        if j >= 0:
            return j
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == want:
                return i
        return -1

    def set_tab_visible(self, identifier, visible, owner=None):
        i = self.tab_index(identifier, owner)
        if i < 0 or i >= self.tabs.count():
            return
        was_ctx = self.tabs.currentIndex() >= self._main_count
        hidden_ctx = i >= self._main_count
        self.begin_batch()
        try:
            if hasattr(self.tabs, "setTabVisible"):
                self.tabs.setTabVisible(i, bool(visible))
            else:
                self.stack.widget(i).setVisible(bool(visible))
        finally:
            self.end_batch()
        if (not visible and was_ctx and hidden_ctx and self._main_count > 0):
            try:
                self.set_current_tab(0)
            except Exception:
                exc_note("set_tab_visible @ ggis/ui/framework/ribbon.py:3399")
                pass
        try:
            self.tabs.updateGeometry()
            self.tabs.update()
        except Exception:
            exc_note("set_tab_visible @ ggis/ui/framework/ribbon.py:3408")
            pass
        self._apply_ctx_text_colors()

    def _apply_ctx_text_colors(self):
        for j in range(len(self._ctx_pages)):
            i = self._main_count + j
            if i >= self.tabs.count():
                continue
            try:
                self.tabs.setTabTextColor(i, QColor())
            except Exception:
                exc_note("_apply_ctx_text_colors @ ggis/ui/framework/ribbon.py:3426")
                pass

    def is_tab_visible(self, identifier, owner=None):
        i = self.tab_index(identifier, owner)
        if i < 0 or i >= self.tabs.count():
            return False
        if hasattr(self.tabs, "isTabVisible"):
            return bool(self.tabs.isTabVisible(i))
        return bool(self.stack.widget(i).isVisible())

    def begin_batch(self):
        try:
            self._batch_depth = int(getattr(self, "_batch_depth", 0)) + 1
        except Exception:
            exc_note("begin_batch @ ggis/ui/framework/ribbon.py:3452")
            self._batch_depth = 1

    def end_batch(self):
        try:
            n = int(getattr(self, "_batch_depth", 0)) - 1
            self._batch_depth = n if n > 0 else 0
        except Exception:
            exc_note("end_batch @ ggis/ui/framework/ribbon.py:3460")
            self._batch_depth = 0

    def set_current_tab(self, idx):
        old = bool(getattr(self, "suppress_tab_picked", False))
        self.suppress_tab_picked = True
        try:
            self.tabs.setCurrentIndex(int(idx))
        finally:
            self.suppress_tab_picked = old

    def _on_tab(self, idx):
        if idx < 0:
            return
        try:
            if self.tabs.currentIndex() != idx:
                self.set_current_tab(idx)
                return
        except Exception:
            exc_note("_on_tab @ ggis/ui/framework/ribbon.py:3498")
            pass
        if idx >= self._main_count \
                and 0 <= self._prev_index < self._main_count:
            self._main_before_ctx = self._prev_index
        self.stack.setCurrentIndex(idx)
        self._prev_index = idx
        try:
            if (not getattr(self, "suppress_tab_picked", False)
                    and not getattr(self, "_batch_depth", 0)):
                d = self.tabs.tabData(idx)
                ok = True
                host = self.tabGroupGuard
                if callable(host):
                    ok = bool(host(d))
                if ok:
                    self.tabPicked.emit(idx, d, self.tabs.tabText(idx))
        except Exception:
            exc_note("_on_tab @ ggis/ui/framework/ribbon.py:3540")
            pass

    def _update_tab_indicator(self, idx=None):
        if idx is None:
            idx = self.tabs.currentIndex()
        if idx < 0 or not self.tabs.isVisible():
            self._tab_indicator.hide()
            return
        color = themes.accent(settings.get("theme"))
        rect = self.tabs.tabRect(idx)
        if not rect.isValid():
            self._tab_indicator.hide()
            return
        tab_bottom = self.tabs.mapToParent(
            QPoint(0, self.tabs.height())).y()
        if getattr(self, "_indicator_color", None) != color:
            self._tab_indicator.setStyleSheet(
                "background-color: {}; border: 0; border-radius: 0;".format(
                    color))
            self._indicator_color = color
        _hov = -1
        try:
            _hov = int(getattr(self.tabs, "_hover_index", -1))
        except Exception:
            exc_note("_update_tab_indicator @ ggis/ui/framework/ribbon.py:3599")
            _hov = -1
        x_bar, w = self.tabs._line_geom(idx, full=(_hov == int(idx)))
        if w <= 0:
            self._tab_indicator.hide()
            return
        x = self.tabs.mapToParent(QPoint(x_bar, 0)).x()
        y = tab_bottom - TAB_LINE_H
        target = QRect(x, y, w, TAB_LINE_H)
        self._tab_indicator.show()
        self._tab_indicator.raise_()
        if not getattr(self, "_indicator_placed", False):
            self._tab_indicator.setGeometry(target)
            self._indicator_placed = True
            return
        anim = getattr(self, "_indicator_anim", None)
        if anim is None:
            anim = QPropertyAnimation(self._tab_indicator, b"geometry")
            anim.setDuration(160)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self._indicator_anim = anim
        anim.stop()
        anim.setEndValue(target)
        anim.start()

    def _normalize_stack_height(self):
        hs = []
        for i in range(min(self._main_count, self.stack.count())):
            w = self.stack.widget(i)
            if isinstance(w, QScrollArea):
                w = w.widget()
            if w is not None:
                hs.append(w.sizeHint().height())
        if hs:
            m = self.stack.contentsMargins()
            want = max(hs) + m.top() + m.bottom()
            prev = int(getattr(self, "_stack_h_locked", 0) or 0)
            if int(want) > prev:
                self._stack_h_locked = int(want)
            self.stack.setFixedHeight(int(self._stack_h_locked))

    def add_contextual_tab(self, title, color=None, tag=None, owner=None):
        color = color or themes.contextual(settings.get("theme"))
        own = "" if owner is None else str(owner)
        for j in range(len(self._ctx_pages)):
            i = self._main_count + j
            if (self.tabs.tabText(i) == title
                    and self._ctx_owner_at(j) == own):
                self._ctx_colors[(own, title)] = color
                return self._ctx_pages[j]
        i = self._main_count + len(self._ctx_pages)
        try:
            _cur = int(self.tabs.currentIndex())
        except Exception:
            exc_note("add_contextual_tab @ ggis/ui/framework/ribbon.py:3706")
            _cur = 0
        self.tabs.addTab(title)
        try:
            if _cur >= 0:
                self.set_current_tab(_cur)
        except Exception:
            exc_note("add_contextual_tab @ ggis/ui/framework/ribbon.py:3712")
            pass
        page = RibbonPage()
        self._stamp_uid(page)
        self.stack.addWidget(self._wrap_page(page))
        self._ctx_pages.append(page)
        self._ctx_owners.append(own)
        self._ctx_colors[(own, title)] = color
        self._apply_ctx_text_colors()
        try:
            self.tabs.setTabData(i, tag if tag is not None
                                 else "ctx:%s:%s" % (own, title))
        except Exception:
            exc_note("add_contextual_tab @ ggis/ui/framework/ribbon.py:3727")
            pass
        return page

    def attach_contextual_page(self, page, title, color=None, owner=None):
        if page is None:
            return None
        color = color or themes.contextual(settings.get("theme"))
        own = "" if owner is None else str(owner)
        for j in range(len(self._ctx_pages)):
            i = self._main_count + j
            if (self.tabs.tabText(i) == title
                    and self._ctx_owner_at(j) == own):
                self._ctx_colors[(own, title)] = color
                return self._ctx_pages[j]
        i = self._main_count + len(self._ctx_pages)
        try:
            _cur = int(self.tabs.currentIndex())
        except Exception:
            exc_note("attach_contextual_page @ ggis/ui/framework/ribbon.py:3751")
            _cur = 0
        self.tabs.addTab(title)
        try:
            if _cur >= 0:
                self.set_current_tab(_cur)
        except Exception:
            exc_note("attach_contextual_page @ ggis/ui/framework/ribbon.py:3757")
            pass
        self._stamp_uid(page)
        self.stack.addWidget(self._wrap_page(page))
        self._ctx_pages.append(page)
        self._ctx_owners.append(own)
        self._ctx_colors[(own, title)] = color
        self._apply_ctx_text_colors()
        try:
            self.tabs.setTabData(i, "ctx:%s:%s" % (own, title))
        except Exception:
            exc_note("attach_contextual_page @ ggis/ui/framework/ribbon.py:3767")
            pass
        return page

    def _ctx_owner_at(self, j):
        return self._ctx_owners[j]

    def remove_contextual_tab(self, title, owner=None):
        i = self._ctx_index(title, owner)
        if i < 0:
            return
        j = i - self._main_count
        own = self._ctx_owner_at(j)
        page = self._ctx_pages.pop(j)
        self._ctx_owners.pop(j)
        self._ctx_colors.pop((own, title), None)
        was_ctx = self.tabs.currentIndex() >= self._main_count
        self.tabs.removeTab(i)
        wrap = page.parentWidget().parentWidget() \
            if page.parentWidget() is not None else None
        if wrap is not None and wrap.parentWidget() is self.stack:
            self.stack.removeWidget(wrap)
            wrap.deleteLater()
        else:
            self.stack.removeWidget(page)
        page.deleteLater()
        if was_ctx and self._main_count > 0:
            self.set_current_tab(0)

    def clear_contextual_tabs(self):
        was_ctx = self.tabs.currentIndex() >= self._main_count
        for page in self._ctx_pages:
            wrap = page.parentWidget().parentWidget() \
                if page.parentWidget() is not None else None
            if wrap is not None and wrap.parentWidget() is self.stack:
                self.stack.removeWidget(wrap)
                wrap.deleteLater()
            else:
                self.stack.removeWidget(page)
            page.deleteLater()
        self._ctx_pages.clear()
        self._ctx_owners.clear()
        self._ctx_colors.clear()
        while self.tabs.count() > self._main_count:
            self.tabs.removeTab(self.tabs.count() - 1)
        if was_ctx and self._main_count > 0:
            self.set_current_tab(0)

    def _ctx_index(self, title, owner=None):
        for j in range(len(self._ctx_pages)):
            i = self._main_count + j
            if self.tabs.tabText(i) != title:
                continue
            if owner is not None and self._ctx_owner_at(j) != str(owner):
                continue
            return i
        return -1

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            if watched is self.tabs:
                self._update_tab_indicator()
            elif hasattr(watched, "_overflow_btn"):
                self._update_overflow(watched)
            elif hasattr(watched, "groups"):
                sa = watched.parentWidget()
                if sa is not None:
                    sa = sa.parentWidget()
                if sa is not None and hasattr(sa, "_overflow_btn"):
                    self._update_overflow(sa)
        return super().eventFilter(watched, event)

    def set_collapsed(self, collapsed):
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self.stack.setVisible(not collapsed)
        if not collapsed:
            self._normalize_stack_height()
        self._collapse_btn.setIcon(
            icons.icon("chevron_down" if collapsed else "chevron_up"))
        self._collapse_btn.setToolTip(
            i18n.tr("展开功能区") if collapsed else i18n.tr("折叠功能区"))
        self.collapsedChanged.emit(collapsed)

    def is_collapsed(self):
        return self._collapsed

    def showEvent(self, event):
        super().showEvent(event)
        self._update_tab_indicator()

    def retheme(self):
        try:
            fit_app_button(self.app_button)
        except Exception:
            exc_note("retheme @ ggis/ui/framework/ribbon.py:3908")
            pass
        self._update_tab_indicator()
        for g in self.findChildren(RibbonGroup):
            try:
                g.retheme_icons()
            except Exception:
                exc_note("retheme @ ggis/ui/framework/ribbon.py:3916")
                pass

    def current_page(self):
        return self.stack.currentWidget()


class GgsAppButton(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAppButton")
class GgsRibbonBody(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonBody")
class GgsRibbonCaption(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonCaption")
class GgsRibbonCollapseBtn(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonCollapseBtn")
class GgsRibbonDropZone(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonDropZone")
class GgsRibbonOverflow(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonOverflow")
class GgsRibbonScroll(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonScroll")
class GgsRibbonSep(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonSep")
class GgsRibbonStack(QStackedWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonStack")
class GgsRibbonTabIndicator(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsRibbonTabIndicator")
