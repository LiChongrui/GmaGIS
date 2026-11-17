# -*- coding: utf-8 -*-
from ggis.common.widgets.inputs import GgsSearchEdit
from ggis.common.util.exc_report import exc_note
SEARCH_SHORTCUT = "Ctrl+K"

from PySide6.QtCore import Qt, QEvent, QObject, Signal
from shiboken6 import isValid as _shiboken_valid
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (QApplication, QFrame, QLineEdit, QListWidget,
                               QListWidgetItem, QSizePolicy, QVBoxLayout)

from ggis.common.styling import icons as _icons
from ggis.core.app import i18n

_tr = i18n.tr

_MAX_RESULTS = 40

_POPUP_ROW_H = 26
_POPUP_MAX_ROWS = 10
_POPUP_PAD = 8
_POPUP_MARGIN = 12

_BAR_H = 26

_EDIT_H = _BAR_H - 2

_PY_INITIAL = {
    "添": "t", "加": "j", "矢": "s", "量": "l", "栅": "z", "格": "g",
    "图": "t", "层": "c", "数": "s", "据": "j", "库": "k", "选": "x",
    "择": "z", "测": "c", "距": "j", "离": "l", "积": "j", "角": "j",
    "度": "d", "具": "j", "箱": "x", "属": "s", "性": "x", "表": "b",
    "符": "f", "号": "h", "化": "h", "系": "x", "标": "b", "注": "z",
    "过": "g", "滤": "l", "要": "y", "素": "s", "导": "d", "出": "c",
    "入": "r", "建": "j", "工": "g", "程": "c", "开": "k", "保": "b",
    "存": "c", "另": "l", "为": "w", "制": "z", "粘": "z", "贴": "t",
    "删": "s", "除": "c", "重": "z", "命": "m", "名": "m", "视": "s",
    "野": "y", "缩": "s", "放": "f", "全": "q", "移": "y", "动": "d",
    "刷": "s", "新": "x", "帮": "b", "助": "z", "关": "g", "于": "y",
    "主": "z", "题": "t", "语": "y", "言": "y", "坐": "z", "投": "t",
    "影": "y", "裁": "c", "剪": "j", "缓": "h", "冲": "c", "区": "q",
    "融": "r", "差": "c", "并": "b", "交": "j", "集": "j", "分": "f",
    "组": "z", "义": "y", "查": "c", "询": "x", "编": "b", "辑": "j",
    "历": "l", "史": "s", "撤": "c", "销": "x", "恢": "h", "窗": "c",
    "口": "k", "面": "m", "板": "b", "布": "b", "局": "j", "插": "c",
    "值": "z", "渲": "x", "染": "r", "模": "m", "式": "s", "显": "x",
    "示": "s", "隐": "y", "藏": "c", "锁": "s", "定": "d", "排": "p",
    "序": "x", "对": "d", "齐": "q", "合": "h", "拆": "c", "校": "j",
    "验": "y", "修": "x", "复": "f", "转": "z", "换": "h", "统": "t",
    "计": "j", "报": "b", "告": "g", "打": "d", "印": "y", "预": "y",
    "览": "l", "页": "y", "设": "s", "置": "z", "基": "j", "础": "c",
}


def _pinyin_initials(text):
    out = []
    for ch in str(text or ""):
        if ch in _PY_INITIAL:
            out.append(_PY_INITIAL[ch])
        elif ch.isascii():
            out.append(ch.lower())
    return "".join(out)


class _PopupDismissFilter(QObject):

    _TYPES = (QEvent.Type.MouseButtonPress,
              QEvent.Type.MouseButtonDblClick,
              QEvent.Type.NonClientAreaMouseButtonPress)

    def __init__(self, bar):
        super().__init__(bar)
        self._bar = bar

    def eventFilter(self, obj, e):
        bar = self._bar
        if bar is None:
            return False
        popup = getattr(bar, "popup", None)
        if popup is None:
            return False
        try:
            if not (_shiboken_valid(popup) and _shiboken_valid(bar)):
                return False
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/searchbar.py:150")
            return False
        try:
            if e.type() not in self._TYPES:
                return False
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/searchbar.py:155")
            return False
        try:
            gp = e.globalPosition().toPoint()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/searchbar.py:159")
            try:
                gp = e.globalPos()
            except Exception:
                exc_note("eventFilter @ ggis/ui/framework/searchbar.py:162")
                return False
        try:
            if popup.frameGeometry().contains(gp):
                return False
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/searchbar.py:167")
            return False
        try:
            popup.hide()
        except Exception:
            exc_note("eventFilter @ ggis/ui/framework/searchbar.py:171")
            pass
        return False


class GgsSearchBar(QFrame):

    activated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsSearchBar")
        self.setFixedWidth(260)
        self.setFixedHeight(_BAR_H)
        self._actions = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.edit = GgsSearchEdit(self)
        self.edit.setMinimumHeight(_EDIT_H)
        self.edit.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Expanding)
        self.edit.setPlaceholderText(
            _tr("搜索功能") + "（%s）…" % SEARCH_SHORTCUT)
        try:
            self.edit.addAction(_icons.icon("search", size=16),
                                QLineEdit.ActionPosition.LeadingPosition)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/searchbar.py:216")
            pass
        self.edit.setClearButtonEnabled(True)
        lay.addWidget(self.edit, 0, Qt.AlignmentFlag.AlignVCenter)

        self.popup = GgsSearchPopup(self)
        self.popup.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus)
        try:
            self.popup.setAttribute(
                Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/searchbar.py:239")
            pass
        try:
            self.popup.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.popup.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.popup.setVerticalScrollMode(
                QListWidget.ScrollMode.ScrollPerPixel)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/searchbar.py:250")
            pass
        try:
            from PySide6.QtCore import QSize
            self.popup.setIconSize(QSize(16, 16))
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/searchbar.py:257")
            pass
        self.popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.popup.setMouseTracking(True)
        self.popup.itemActivated.connect(self._on_item)
        self.popup.itemClicked.connect(self._on_item)
        self.popup.destroyed.connect(self._on_popup_destroyed)
        self.popup.hide()

        self.destroyed.connect(self._on_self_destroyed)

        self.edit.textChanged.connect(self._on_text)
        self.edit.returnPressed.connect(self._on_return)
        self._dismiss = _PopupDismissFilter(self)
        try:
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self._dismiss)
                app.applicationStateChanged.connect(self._on_app_state)
        except Exception:
            exc_note("__init__ @ ggis/ui/framework/searchbar.py:277")
            pass

    def _on_popup_destroyed(self, *_):
        self.popup = None

    def _on_self_destroyed(self, *_):
        try:
            app = QApplication.instance()
            d = getattr(self, "_dismiss", None)
            if app is not None and d is not None:
                app.removeEventFilter(d)
                d._bar = None
        except Exception:
            exc_note("_on_self_destroyed @ ggis/ui/framework/searchbar.py:287")

    def _on_app_state(self, state):
        p = self.popup
        if p is None:
            return
        try:
            if not _shiboken_valid(p):
                return
        except Exception:
            exc_note("_on_app_state @ ggis/ui/framework/searchbar.py:285")
            return
        try:
            if state != Qt.ApplicationState.ApplicationActive:
                p.hide()
        except Exception:
            exc_note("_on_app_state @ ggis/ui/framework/searchbar.py:285")
            pass

    def set_actions(self, actions):
        self._actions = [a for a in (actions or [])
                         if isinstance(a, QAction)]

    def set_extra_provider(self, fn):
        self._extra_provider = fn

    def _extras(self, q, ql):
        fn = getattr(self, "_extra_provider", None)
        if fn is None or not q:
            return []
        try:
            return list(fn(q) or [])
        except Exception:
            exc_note("_extras @ ggis/ui/framework/searchbar.py:312")
            return []

    def _entries(self):
        q = self.edit.text().strip()
        if not q:
            return []
        ql = q.lower()
        q_norm = ql.replace(" ", "")
        out = []
        for a in self._actions:
            try:
                if a.isSeparator() or not a.text():
                    continue
                text = a.text().replace("&", "")
                tl = text.lower()
                tip = (a.toolTip() or "").replace("&", "")
                tipl = tip.lower()
            except RuntimeError:
                exc_note("_entries @ ggis/ui/framework/searchbar.py:332")
                continue
            score = 0
            if tl == ql:
                score = 100
            elif tl.startswith(ql):
                score = 80
            elif ql in tl:
                score = 60
            else:
                py = _pinyin_initials(text)
                if py and ql == py:
                    score = 70
                elif py and py.startswith(ql):
                    score = 50
                elif ql in tipl:
                    score = 40
                elif q_norm and q_norm in tipl.replace(" ", ""):
                    score = 35
            if score <= 0:
                continue
            try:
                if not a.isEnabled():
                    score -= 5
            except RuntimeError:
                exc_note("_entries @ ggis/ui/framework/searchbar.py:357")
                continue
            out.append((score, a))
        out.sort(key=lambda t: (-t[0], t[1].text()))
        return out

    def _on_text(self, *_):
        if self.popup is None:
            return
        res = self._entries()[:_MAX_RESULTS]
        extras = self._extras(self.edit.text().strip(),
                              self.edit.text().strip().lower())
        extras = sorted(extras, key=lambda t: -t[0])[:_MAX_RESULTS]
        if not res and not extras:
            self.popup.hide()
            return
        self.popup.clear()
        for _s, a in res:
            try:
                item = QListWidgetItem(a.icon(), a.text().replace("&", ""))
                sc = a.shortcut().toString()
                if sc:
                    item.setText("%s    %s" % (a.text().replace("&", ""), sc))
                item.setToolTip(a.toolTip() or "")
                item.setData(Qt.ItemDataRole.UserRole, ("act", id(a)))
                self.popup.addItem(item)
            except RuntimeError:
                exc_note("_on_text @ ggis/ui/framework/searchbar.py:382")
                continue
        for _s, title, icon_name, _cb in extras:
            try:
                from ggis.common.styling import icons as _icons
                text = "%-34s %s" % (title, _tr("（算法）"))
                item = QListWidgetItem(_icons.icon(icon_name or "tool", size=16),
                                       text)
                item.setData(Qt.ItemDataRole.UserRole, ("extra", title))
                self.popup.addItem(item)
            except Exception:
                exc_note("_on_text @ ggis/ui/framework/searchbar.py:394")
                continue
        self._extra_cache = {t[1]: t[3] for t in extras}
        if self.popup.count() == 0:
            self.popup.hide()
            return
        self.popup.setCurrentRow(0)
        self._place_popup()

    def _place_popup(self):
        try:
            gp = self.mapToGlobal(self.rect().bottomLeft())
            top = gp.y() + 2
            rows = self.popup.count()
            full = rows * _POPUP_ROW_H + _POPUP_PAD
            cap = _POPUP_MAX_ROWS * _POPUP_ROW_H + _POPUP_PAD
            try:
                scr = (QGuiApplication.screenAt(gp)
                       or QGuiApplication.primaryScreen())
                if scr is not None:
                    cap = min(cap, max(_POPUP_ROW_H + _POPUP_PAD,
                                       scr.availableGeometry().bottom()
                                       - top - _POPUP_MARGIN))
            except Exception:
                exc_note("_place_popup @ ggis/ui/framework/searchbar.py:425")
                pass
            h = int(min(full, max(_POPUP_ROW_H + _POPUP_PAD, cap)))
            self.popup.setGeometry(gp.x(), top, self.width(), h)
            self.popup.show()
            self.popup.raise_()
        except Exception:
            exc_note("_place_popup @ ggis/ui/framework/searchbar.py:431")
            pass

    def _on_item(self, item):
        payload = item.data(Qt.ItemDataRole.UserRole)
        self.popup.hide()
        self.edit.clear()
        if isinstance(payload, tuple) and len(payload) == 2:
            kind, val = payload
            if kind == "act":
                for a in self._actions:
                    try:
                        if id(a) == val:
                            self.activated.emit(a)
                            if a.isEnabled():
                                a.trigger()
                            return
                    except RuntimeError:
                        exc_note("_on_item @ ggis/ui/framework/searchbar.py:448")
                        continue
                return
            if kind == "extra":
                cb = (getattr(self, "_extra_cache", {}) or {}).get(val)
                if cb is not None:
                    try:
                        cb()
                    except Exception:
                        exc_note("_on_item @ ggis/ui/framework/searchbar.py:456")
                        pass
                return

    def _on_return(self):
        item = self.popup.currentItem()
        if item is None:
            self._on_text()
            item = self.popup.currentItem()
            if item is None:
                return
        self._on_item(item)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self.popup.hide()
            return
        if self.popup.isVisible() and k in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            r = self.popup.currentRow()
            n = self.popup.count()
            r = (r + 1) % n if k == Qt.Key.Key_Down else (r - 1 + n) % n
            self.popup.setCurrentRow(r)
            return
        if self.popup.isVisible() and k in (Qt.Key.Key_Return,
                                            Qt.Key.Key_Enter):
            item = self.popup.currentItem()
            if item is not None:
                self._on_item(item)
                return
        super().keyPressEvent(e)

    def retheme(self):
        try:
            self.popup.viewport().update()
        except Exception:
            exc_note("retheme @ ggis/ui/framework/searchbar.py:500")
            pass


class GgsSearchPopup(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSearchPopup")
