from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import os

import matplotlib
from matplotlib import font_manager
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy

from ggis.common.styling import themes
from ggis.core.app import i18n, settings as _settings

_tr = i18n.tr


def _setup_cjk_font():
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        r"/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            font_manager.fontManager.addfont(path)
            name = font_manager.FontProperties(fname=path).get_name()
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["font.sans-serif"] = [name]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
        except Exception:
            exc_note("_setup_cjk_font @ ggis/ui/charts/mpl_chart.py:47")
            continue


_setup_cjk_font()


def theme_chart_colors():
    try:
        pal = themes.theme_colors(_settings.get("theme"))
    except Exception:
        exc_note("theme_chart_colors @ ggis/ui/charts/mpl_chart.py:58")
        pal = {}
    return {
        "panel": pal.get("panel") or "#ffffff",
        "text": pal.get("text") or "#202020",
        "dim": pal.get("text_dim") or "#8a8f98",
        "border": pal.get("border") or "#c9cdd4",
        "accent": pal.get("accent") or "#3d7fd1",
    }


class MplBusyMixin:

    def _set_fetching(self, on, text=None):
        if text is not None:
            self._busy_text = text
        if on:
            try:
                self.setEnabled(False)
            except Exception:
                exc_note("_set_fetching @ ggis/ui/charts/mpl_chart.py:86")
                pass
            self._draw_busy()
        else:
            try:
                self.setEnabled(True)
            except Exception:
                exc_note("_set_fetching @ ggis/ui/charts/mpl_chart.py:92")
                pass
            self._clear_busy()

    def _draw_busy(self):
        for t in getattr(self, "_busy_arts", None) or []:
            try:
                t.remove()
            except Exception:
                exc_note("_draw_busy @ ggis/ui/charts/mpl_chart.py:100")
                pass
        self._busy_arts = []
        th = theme_chart_colors()
        t = self.figure.text(
            0.5, 0.5,
            getattr(self, "_busy_text", None) or _tr("正在读取数据…"),
            ha="center", va="center", color=th["dim"], fontsize=8)
        self._busy_arts = [t]
        try:
            self.draw()
        except Exception:
            exc_note("_draw_busy @ ggis/ui/charts/mpl_chart.py:111")
            pass

    def _clear_busy(self):
        for t in getattr(self, "_busy_arts", None) or []:
            try:
                t.remove()
            except Exception:
                exc_note("_clear_busy @ ggis/ui/charts/mpl_chart.py:118")
                pass
        self._busy_arts = []
        try:
            self.draw_idle()
        except Exception:
            exc_note("_clear_busy @ ggis/ui/charts/mpl_chart.py:126")
            pass

    def begin_fetching(self, text=None, delay_ms=200):
        if text is not None:
            self._busy_text = text
        timer = getattr(self, "_busy_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                exc_note("begin_fetching @ ggis/ui/charts/mpl_chart.py:142")
                pass
        from PySide6.QtCore import QTimer
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._set_fetching(True))
        timer.start(int(delay_ms))
        self._busy_timer = timer

    def end_fetching(self):
        timer = getattr(self, "_busy_timer", None)
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                exc_note("end_fetching @ ggis/ui/charts/mpl_chart.py:157")
                pass
            self._busy_timer = None
        self._set_fetching(False)


class MplChartBase(FigureCanvasQTAgg):

    def __init__(self, parent=None):
        fig = Figure(figsize=(4.0, 3.0))
        super().__init__(fig)
        self.figure = fig
        self.ax = fig.add_subplot(111)
        self._plot_rect = [0.13, 0.12, 0.83, 0.76]
        self.ax.set_position(self._plot_rect)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self.setMinimumSize(60, 60)

    @staticmethod
    def _color_to_hex(color, fallback="#3d7fd1"):
        if color is None:
            return fallback
        name = getattr(color, "name", None)
        if callable(name):
            try:
                return color.name()
            except Exception:
                exc_note("_color_to_hex @ ggis/ui/charts/mpl_chart.py:192")
                return fallback
        s = str(color)
        return s if s.startswith("#") else fallback

    def _finish_draw(self):
        th = theme_chart_colors()
        try:
            self.figure.patch.set_facecolor(th["panel"])
            self.ax.set_facecolor(th["panel"])
        except Exception:
            exc_note("_finish_draw @ ggis/ui/charts/mpl_chart.py:207")
            pass
        self.draw()
