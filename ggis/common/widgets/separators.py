# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note
from ggis.common.styling import icons as _icons

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QLayout,
                               QHBoxLayout, QVBoxLayout, QGridLayout)

HANDLE = 5

LINE = 1


class GgsDockSepOverlay(QWidget):

    def __init__(self, vertical, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsDockSepOverlay")
        self._vertical = bool(vertical)
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                          True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_hover(self, on):
        on = bool(on)
        if on != self._hover:
            self._hover = on
            self.update()

    def is_vertical(self):
        return self._vertical

    def paintEvent(self, e):
        from ggis.common.styling import themes
        from ggis.core.app import settings as _settings
        try:
            pal = themes.theme_colors(_settings.get("theme"))
        except Exception:
            exc_note("paintEvent @ ggis/common/widgets/separators.py:78")
            pal = {}
        key = "focus" if self._hover else "border_soft"
        c = QColor(pal.get(key) or ("#969ca8" if self._hover else "#e3e5e8"))
        if not c.isValid():
            return
        p = QPainter(self)
        try:
            if self._vertical:
                x = max(0, (self.width() - LINE) // 2)
                p.fillRect(x, 0, LINE, self.height(), c)
            else:
                y = max(0, (self.height() - LINE) // 2)
                p.fillRect(0, y, self.width(), LINE, c)
        finally:
            p.end()


def layout_separators(win, separators):
    try:
        pass
    except Exception:
        exc_note("layout_separators @ ggis/common/widgets/separators.py:117")
        return separators
    win_w, win_h = win.width(), win.height()
    if win_w <= 0 or win_h <= 0:
        for s in separators:
            s.hide()
        return separators

    def _area(d):
        if d is None:
            return None
        try:
            if not d.isVisible() or d.isFloating():
                return None
            g = d.geometry()
            if g.width() <= 1 or g.height() <= 1:
                return None
            if g.x() < 0 or g.y() < 0:
                return None
            if g.x() >= win_w or g.y() >= win_h:
                return None
            return g
        except Exception:
            exc_note("_area @ ggis/common/widgets/separators.py:147")
            return None

    left = _area(getattr(win, "layer_dock", None))
    right = None
    for d in getattr(win, "_right_docks", ()) or ():
        r = _area(d)
        if r is not None:
            right = r
            break
    bottom = None
    _vh = getattr(win, "view_host", None)
    if _vh is not None:
        for _v in getattr(_vh, "views", lambda: [])():
            if str(getattr(_v, "kind", "")) != "map":
                continue
            for _d in getattr(_v, "_attr_docks", {}).values():
                if _d.isVisible():
                    _g = _area(_d)
                    if _g is not None:
                        bottom = _g
                        break
            if bottom is not None:
                break
    if bottom is None:
        bottom = _area(getattr(win, "attribute_dock", None))
    cv = getattr(win, "centralWidget", None)
    central = cv() if callable(cv) else None
    cg = None
    if central is not None:
        try:
            if central.isVisible():
                cg = central.geometry()
        except Exception:
            exc_note("layout_separators @ ggis/common/widgets/separators.py:183")
            cg = None

    want = []
    if cg is not None:
        top = cg.y()
        bot = cg.y() + cg.height()
        if left is not None:
            x0 = left.x() + left.width()
            x1 = cg.x()
            if x1 - x0 >= 1:
                want.append((True, x0, top, x1 - x0, cg.height()))
        if right is not None:
            x0 = cg.x() + cg.width()
            x1 = right.x()
            if x1 - x0 >= 1:
                want.append((True, x0, top, x1 - x0, cg.height()))
        if bottom is not None and bottom.y() >= bot:
            y0 = bot
            y1 = bottom.y()
            if y1 - y0 >= 1:
                want.append((False, cg.x(), y0, cg.width(), y1 - y0))

    while len(separators) < len(want):
        separators.append(GgsDockSepOverlay(True, win))
    for i, (vert, x, y, w, h) in enumerate(want):
        s = separators[i]
        if s.is_vertical() != vert:
            s._vertical = vert
        s.setGeometry(int(x), int(y), max(1, int(w)), max(1, int(h)))
        s.show()
        s.raise_()
    for s in separators[len(want):]:
        s.hide()
    return separators


def update_sep_hover(win, separators, global_pos):
    if not separators:
        return
    try:
        local = win.mapFromGlobal(global_pos)
    except Exception:
        exc_note("update_sep_hover @ ggis/common/widgets/separators.py:235")
        return
    for s in separators:
        try:
            if not s.isVisible():
                s.set_hover(False)
                continue
            g = s.geometry()
            inside = g.contains(local)
            s.set_hover(inside)
        except Exception:
            exc_note("update_sep_hover @ ggis/common/widgets/separators.py:245")
            pass


def sep_at(separators, local_pos, pad=2):
    for s in separators:
        try:
            if not s.isVisible():
                continue
            g = s.geometry().adjusted(-pad, -pad, pad, pad)
            if g.contains(local_pos):
                return s
        except Exception:
            exc_note("sep_at @ ggis/common/widgets/separators.py:262")
            pass
    return None


class GgsSepH(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSepH")



class GgsSepV(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsSepV")
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Plain)



class GgsGroupCard:

    def __init__(self, title="", icon_name=""):
        self.card = QFrame()
        self.card.setObjectName("GgsAboutCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self.card)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(6)
        if icon_name:
            lab = QLabel()
            lab.setObjectName("GgsAboutIcon")
            lab.setFixedSize(16, 16)
            try:
                lab.setPixmap(_icons.icon(str(icon_name), size=16)
                              .pixmap(16, 16))
            except Exception:
                exc_note("__init__ @ ggis/common/widgets/standard.py:6231")
                pass
            head.addWidget(lab)
        self.lbl_title = QLabel(str(title or ""))
        self.lbl_title.setObjectName("GgsAboutCardTitle")
        head.addWidget(self.lbl_title)
        head.addStretch(1)
        outer.addLayout(head)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(4)
        self.grid.setColumnStretch(1, 1)
        outer.addLayout(self.grid)
        outer.addStretch(1)
        self._row = 0

    def addRow(self, *args):
        if len(args) == 2:
            label, field = args
        elif len(args) == 1:
            label, field = "", args[0]
        else:
            return
        if field is None:
            return
        is_lay = isinstance(field, QLayout)
        if label:
            k = QLabel(str(label))
            k.setObjectName("GgsAboutKey")
            k.setAlignment(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignVCenter)
            self.grid.addWidget(k, self._row, 0)
            if is_lay:
                self.grid.addLayout(field, self._row, 1)
            else:
                self.grid.addWidget(field, self._row, 1)
        else:
            if is_lay:
                self.grid.addLayout(field, self._row, 0, 1, 2)
            else:
                self.grid.addWidget(field, self._row, 0, 1, 2)
        self._row += 1


