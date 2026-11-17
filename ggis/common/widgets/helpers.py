# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QObject, QEvent

class _CursorGuard(QObject):

    def __init__(self, widget, cursor):
        super().__init__(widget)
        self._w = widget
        self._cursor = cursor
        widget.installEventFilter(self)
        self.sync()

    def sync(self):
        try:
            self._w.setCursor(self._cursor if self._w.isEnabled()
                              else Qt.CursorShape.ArrowCursor)
        except RuntimeError:
            exc_note("sync @ ggis/common/widgets/standard.py:139")
            pass

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.EnabledChange:
            self.sync()
        return False


def hand_cursor(widget, cursor=None):
    cur = cursor if cursor is not None else Qt.CursorShape.PointingHandCursor
    try:
        g = widget.findChild(_CursorGuard)
        if g is None:
            _CursorGuard(widget, cur)
        else:
            g._cursor = cur
            g.sync()
    except Exception:
        exc_note("hand_cursor @ ggis/common/widgets/standard.py:163")
        try:
            widget.setCursor(cur)
        except Exception:
            exc_note("hand_cursor @ ggis/common/widgets/standard.py:166")
            pass
    return widget
