# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy
from ggis.common.styling import themes as _themes
from ggis.common.util.exc_report import exc_note
from ggis.core.app import settings as _settings
from ggis.core.app import i18n as _i18n
_tr = _i18n.tr


class GgsHistogramWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsHistogramWidget")
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self._counts = []
        self._edges = []
        self._title = ""
        self._xlabel = ""
        self._hint = _tr("暂无数据")

    def clear(self):
        self._counts = []
        self._edges = []
        self.update()

    def setHint(self, text):
        self._hint = str(text or "")
        if not self._counts:
            self.update()

    def setTitle(self, text):
        self._title = str(text or "")
        self.update()

    def setXLabel(self, text):
        self._xlabel = str(text or "")
        self.update()

    def setValues(self, values, bins=None, lo=None, hi=None):
        from ggis.core.analysis.stats import histogram
        try:
            counts, edges = histogram(values, bins=bins, lo=lo, hi=hi)
        except Exception:
            exc_note("setValues @ ggis/common/widgets/standard.py:2514")
            counts, edges = [], []
        self.setHistogram(counts, edges)

    def setHistogram(self, counts, edges):
        if counts is None:
            counts = ()
        if edges is None:
            edges = ()
        try:
            self._counts = [int(c) for c in counts]
            self._edges = [float(e) for e in edges]
        except (TypeError, ValueError):
            exc_note("setHistogram @ ggis/common/widgets/standard.py:2532")
            self._counts, self._edges = [], []
        self.update()

    def counts(self):
        return list(self._counts)

    def edges(self):
        return list(self._edges)

    def isEmpty(self):
        return not self._counts

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r = self.rect().adjusted(1, 1, -1, -1)
            dark = str(_settings.get("theme") or "dark") != "light"

            def _c(key):
                return QColor(_themes.theme_color(key, dark))

            bg = _c("window")
            fg = _c("text")
            dim = _c("text_dim")
            accent = _c("accent")
            p.fillRect(r, bg)
            p.setPen(QPen(_c("border"), 1))
            p.drawRect(r)

            top = 20 if self._title else 8
            bottom = 34 if self._xlabel else 20
            plot = r.adjusted(44, top, -10, -bottom)
            if plot.width() <= 4 or plot.height() <= 4:
                return

            if not self._counts:
                p.setPen(dim)
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._hint)
                return

            nmax = max(self._counts) or 1
            nb = len(self._counts)
            bw = plot.width() / float(nb)

            bar = QColor(accent)
            bar.setAlpha(200)
            p.setBrush(bar)
            p.setPen(QPen(accent.darker(115), 1))
            for i, c in enumerate(self._counts):
                if c <= 0:
                    continue
                h = int(round(plot.height() * (c / float(nmax))))
                h = max(1, h)
                x = int(round(plot.left() + i * bw))
                w = max(1, int(round(bw)) - 1)
                p.drawRect(x, plot.bottom() - h, w, h)

            p.setPen(QPen(fg, 1))
            p.drawLine(plot.left(), plot.bottom(), plot.right(),
                       plot.bottom())

            p.setPen(dim)
            fm = p.fontMetrics()
            for frac, val in ((0.0, 0), (0.5, nmax // 2), (1.0, nmax)):
                y = int(round(plot.bottom() - frac * plot.height()))
                p.drawLine(plot.left() - 4, y, plot.left(), y)
                p.drawText(0, y - fm.height() // 2,
                           plot.left() - 7, fm.height(),
                           int(Qt.AlignmentFlag.AlignRight
                               | Qt.AlignmentFlag.AlignVCenter), str(val))

            if len(self._edges) >= 2:
                lo, hi = self._edges[0], self._edges[-1]
                xs = (0.0, 0.5, 1.0)
                texts = _fmt_axis((lo, (lo + hi) / 2.0, hi))
                for frac, txt in zip(xs, texts):
                    x = int(round(plot.left() + frac * plot.width()))
                    p.drawLine(x, plot.bottom(), x, plot.bottom() + 3)
                    tw = fm.horizontalAdvance(txt)
                    tx = x - tw // 2
                    tx = max(r.left() + 1, min(tx, r.right() - tw - 1))
                    p.drawText(tx, plot.bottom() + 5, tw, fm.height(),
                               int(Qt.AlignmentFlag.AlignLeft
                                   | Qt.AlignmentFlag.AlignTop), txt)

            if self._title:
                p.setPen(fg)
                p.drawText(r.adjusted(6, 3, -6, 0),
                           int(Qt.AlignmentFlag.AlignLeft
                               | Qt.AlignmentFlag.AlignTop), self._title)
            if self._xlabel:
                p.setPen(dim)
                p.drawText(plot.left(), plot.bottom() + 20, plot.width(),
                           fm.height(),
                           int(Qt.AlignmentFlag.AlignHCenter
                               | Qt.AlignmentFlag.AlignTop), self._xlabel)
        finally:
            p.end()


def _fmt_axis(values):
    vals = []
    for v in values:
        try:
            vals.append(float(v))
        except Exception:
            exc_note("_fmt_axis @ ggis/common/widgets/standard.py:2650")
            return [str(v) for v in values]
    span = max((abs(v) for v in vals), default=0.0)
    if span >= 1e6 or (0.0 < span < 1e-3):
        return ["%.2g" % v for v in vals]
    if span >= 100:
        return ["{:,.0f}".format(v) for v in vals]
    if span >= 10:
        dec = 1
    elif span >= 1:
        dec = 2
    else:
        dec = 3
    pat = "{:,.%df}" % dec
    return [pat.format(v) for v in vals]
