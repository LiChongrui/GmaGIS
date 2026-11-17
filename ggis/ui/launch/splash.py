# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

from PySide6.QtCore import Qt, QTimer, QPointF, QRect, QRectF, QEvent
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient,
                             QPainter, QPainterPath, QPen, QBrush,
                             QRadialGradient, QPolygonF, QPixmap)
from PySide6.QtWidgets import QApplication, QWidget

from ggis.common.styling import icons
from ggis.core.app import i18n
import time

_tr = i18n.tr

# frac 按真实环境耗时占比设定（2026-11-17 真实日志两次启动实测，
# 总计≈4.7s；离屏无 GPU/高 DPR 时构造期只有 ~1.1s，不能按它设）：
# 前置+构造 ≈42%（界面 6% / 面板功能区 21% / 设置 3% / 窗口布局 12%）
# → 读文件 ≈4% → 建视图壳 ≈40%（等渲染子进程握手，逐视图均分）
# → 会话+装图层 ≈6% → 显示收尾 ≈6%。
_STEP_PLAN = (
    ("正在加载运行时…", 0.01),
    ("正在注册数据提供者…", 0.02),
    ("正在构建界面…", 0.07),
    ("正在创建面板与功能区…", 0.28),
    ("正在应用设置…", 0.31),
    ("正在准备视图区域…", 0.32),
    ("正在恢复窗口布局…", 0.43),
    ("正在读取工程…", 0.44),
    ("正在创建工程…", 0.44),
    ("正在创建视图…", 0.47),
    ("正在装载图层…", 0.93),
    ("就绪", 1.0),
)
_PLAN = {name: frac for name, frac in _STEP_PLAN}
# 计数器分母 = 去重后的文本数（=11）：构造期文本被多个 Stage 复用重发
# （"正在构建界面…"×4 等），按计划条目数(12)计会让 X/N 提前顶满、
# 看起来"最后一步"提前出现。每种启动流实际触发的去重文本恰好 11 条。
_TOTAL_STEPS = len(set(name for name, _ in _STEP_PLAN))

_W, _H, _R = 620, 372, 14

_LOGO_SIZE = 64

_DARK_PALETTE = {
    "card_a": (10, 28, 48, 255), "card_b": (15, 45, 74, 255),
    "card_c": (20, 66, 95, 255), "edge": (255, 255, 255, 28),
    "grid": (255, 255, 255, 13), "contour": (72, 201, 168, 42),
    "road_a": (255, 255, 255, 34), "road_b": (255, 255, 255, 20),
    "water": (96, 165, 250, 60), "poi": (255, 209, 102, 190),
    "compass": (255, 255, 255, 30), "needle": (255, 255, 255, 60),
    "glow": (72, 201, 168, 80), "pin": (56, 201, 164, 255),
    "pin_edge": (10, 28, 48, 255), "pin_hole": (10, 28, 48, 255),
    "brand": (242, 247, 251, 255), "tagline": (159, 178, 196, 255),
    "accent_a": (56, 201, 164, 255), "accent_b": (96, 165, 250, 255),
    "track": (255, 255, 255, 26), "step": (195, 210, 223, 255),
    "count": (255, 255, 255, 70),
}

_LIGHT_PALETTE = {
    "card_a": (255, 255, 255, 255), "card_b": (241, 246, 252, 255),
    "card_c": (226, 238, 249, 255), "edge": (17, 45, 74, 34),
    "grid": (17, 45, 74, 20), "contour": (14, 150, 130, 58),
    "road_a": (17, 45, 74, 46), "road_b": (17, 45, 74, 26),
    "water": (58, 122, 220, 78), "poi": (232, 152, 18, 210),
    "compass": (17, 45, 74, 46), "needle": (17, 45, 74, 96),
    "glow": (14, 160, 138, 70), "pin": (18, 163, 127, 255),
    "pin_edge": (255, 255, 255, 255), "pin_hole": (255, 255, 255, 255),
    "brand": (18, 40, 64, 255), "tagline": (90, 107, 125, 255),
    "accent_a": (18, 163, 127, 255), "accent_b": (59, 127, 224, 255),
    "track": (17, 45, 74, 30), "step": (61, 77, 94, 255),
    "count": (17, 45, 74, 105),
}


def palette_for(theme):
    return _LIGHT_PALETTE if str(theme or "").lower() == "light" \
        else _DARK_PALETTE


class SplashScreen(QWidget):

    def __init__(self, theme=None):

        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFixedSize(_W, _H)

        if theme is None:
            try:
                from ggis.core.app import settings as _s
                theme = _s.get("theme")
            except Exception:
                exc_note("__init__ @ ggis/ui/launch/splash.py:99")
                theme = "dark"
        self._pal = palette_for(theme)
        self.theme = str(theme or "dark")
        self._step = 0
        self._total = max(1, _TOTAL_STEPS)
        self._last_raw = None
        self._msg = _tr(_STEP_PLAN[0][0])
        self._progress = 0.06
        self._shown = 0.02
        self._logo = icons.app_logo_pixmap(_LOGO_SIZE)
        if self._logo.isNull():
            try:
                _pm = icons.app_icon().pixmap(256, 256)
                _pm.setDevicePixelRatio(4.0)
                self._logo = _pm
            except Exception:
                self._logo = QPixmap()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._detach_from_taskbar()

    def _detach_from_taskbar(self):
        try:
            import ctypes
            u = ctypes.windll.user32
            u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            u.GetWindowLongW.restype = ctypes.c_long
            u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            u.SetWindowLongW.restype = ctypes.c_long
            u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            u.SetWindowPos.restype = ctypes.c_int
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_FRAMECHANGED = 0x0020
            hwnd = int(self.winId())
            style = u.GetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE)
            if style == 0:
                return
            style |= WS_EX_TOOLWINDOW
            style &= ~WS_EX_APPWINDOW
            u.SetWindowLongW(ctypes.c_void_p(hwnd), GWL_EXSTYLE, style)
            u.SetWindowPos(ctypes.c_void_p(hwnd), ctypes.c_void_p(0),
                          0, 0, 0, 0,
                          SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
        except Exception:
            exc_note("_detach_from_taskbar @ ggis/ui/launch/splash.py:152")
            pass

    def _col(self, key, alpha=None):
        r, g, b, a = self._pal.get(key, (128, 128, 128, 255))
        return QColor(r, g, b, a if alpha is None else alpha)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        card = QRectF(0.5, 0.5, _W - 1, _H - 1)
        path = QPainterPath()
        path.addRoundedRect(card, _R, _R)
        grad = QLinearGradient(0, 0, _W * 0.35, _H)
        grad.setColorAt(0.0, self._col("card_a"))
        grad.setColorAt(0.55, self._col("card_b"))
        grad.setColorAt(1.0, self._col("card_c"))
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(self._col("edge"), 1))
        p.drawPath(path)
        p.setClipPath(path)

        self._paint_gis_scene(p)
        self._paint_brand(p)
        self._paint_progress(p)
        p.end()

    def _paint_gis_scene(self, p):
        p.setPen(QPen(self._col("grid"), 1))
        # 网格在左右 / 上下各留一段对称边距，格距均分：
        # 旧写法 range(40, _W, 44) 最后一条落在 x=612，右边只剩 8px
        # （不到一格），右侧看着没铺满。现 40..580 分 12 格，每格 45px，
        # 左右都留 40px；纵向 36..336 分 7 格，上下都留 36px。
        gx0, gx1, gx_n = 40, _W - 40, 12
        for i in range(gx_n + 1):
            x = gx0 + (gx1 - gx0) * i / float(gx_n)
            p.drawLine(x, 0, x, _H)
        gy0, gy1, gy_n = 36, _H - 36, 7
        for i in range(gy_n + 1):
            y = gy0 + (gy1 - gy0) * i / float(gy_n)
            p.drawLine(0, y, _W, y)

        p.setPen(QPen(self._col("contour"), 1.4))
        cx, cy = _W - 120, _H - 84
        for i, r in enumerate((26, 46, 68, 92, 118)):
            p.drawEllipse(QPointF(cx, cy), r, r * 0.62)

        p.setPen(QPen(self._col("road_a"), 2.2,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPolyline(QPolygonF([QPointF(318, _H), QPointF(392, 246),
                        QPointF(470, 262), QPointF(560, 170), QPointF(_W, 148)]))
        p.setPen(QPen(self._col("road_b"), 1.6))
        p.drawPolyline(QPolygonF([QPointF(340, 0), QPointF(430, 96),
                        QPointF(540, 88), QPointF(_W, 40)]))

        p.setPen(QPen(self._col("water"), 2.6))
        p.drawPolyline(QPolygonF([QPointF(0, 300), QPointF(96, 274), QPointF(180, 296),
                        QPointF(268, 330)]))

        p.setPen(Qt.PenStyle.NoPen)
        for x, y in ((392, 246), (470, 262), (540, 88), (96, 274)):
            p.setBrush(self._col("poi"))
            p.drawEllipse(QPointF(x, y), 4, 4)

        p.setPen(QPen(self._col("compass"), 1.2))
        ccx, ccy, r = 54, _H - 108, 26
        p.drawEllipse(QPointF(ccx, ccy), r, r)
        p.drawLine(QPointF(ccx, ccy - r + 4), QPointF(ccx, ccy + r - 4))
        p.drawLine(QPointF(ccx - r + 4, ccy), QPointF(ccx + r - 4, ccy))
        p.setBrush(self._col("needle"))
        p.drawPolygon(QPolygonF([QPointF(ccx, ccy - r + 6), QPointF(ccx - 5, ccy),
                       QPointF(ccx + 5, ccy)]))

        gx, gy = _W - 150, 118
        glow = QRadialGradient(gx, gy, 78)
        c = self._col("glow")
        glow.setColorAt(0.0, c)
        glow.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(gx, gy), 78, 78)

        pin = self._col("pin")
        p.setBrush(pin)
        p.setPen(QPen(self._col("pin_edge"), 2))
        p.drawEllipse(QPointF(gx, gy - 16), 30, 30)
        p.drawPolygon(QPolygonF([QPointF(gx - 17, gy + 2), QPointF(gx + 17, gy + 2),
                       QPointF(gx, gy + 34)]))
        p.setBrush(self._col("pin_hole"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(gx, gy - 16), 12, 12)

    def _paint_brand(self, p):
        if not self._logo.isNull():
            p.drawPixmap(QRect(48, 52, _LOGO_SIZE, _LOGO_SIZE), self._logo,
                         QRect(0, 0, self._logo.width(),
                               self._logo.height()))

        p.setPen(self._col("brand"))
        f = QFont("Microsoft YaHei UI")
        f.setPointSizeF(33)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(48, 122, 380, 56),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "GmaGIS")

        bar = QLinearGradient(50, 0, 160, 0)
        bar.setColorAt(0.0, self._col("accent_a"))
        bar.setColorAt(1.0, self._col("accent_b"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bar))
        p.drawRoundedRect(QRectF(50, 183, 110, 3.5), 1.75, 1.75)

        # 定位语（软件说明，2026-11-17 用户发现被清空后恢复）
        _tag = _tr("专业桌面 GIS 平台 · 空间数据管理与分析")
        _box = QRectF(48, 198, 470, 24)
        f2 = QFont("Microsoft YaHei UI")
        f2.setPointSizeF(10.5)
        _adv = QFontMetrics(f2).horizontalAdvance(_tag)
        if _adv > _box.width():
            f2.setPointSizeF(max(8.5, 10.5 * _box.width() / _adv))
        p.setPen(self._col("tagline"))
        p.setFont(f2)
        p.drawText(_box, Qt.AlignmentFlag.AlignLeft, _tag)

    def _paint_progress(self, p):
        bar = QRectF(48, _H - 66, _W - 96, 9)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._col("track"))
        p.drawRoundedRect(bar, 4.5, 4.5)
        done = max(0.02, min(1.0, self._shown))
        fill = QLinearGradient(bar.left(), 0, bar.right(), 0)
        fill.setColorAt(0.0, self._col("accent_a"))
        fill.setColorAt(1.0, self._col("accent_b"))
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(QRectF(bar.left(), bar.top(),
                                 bar.width() * done, bar.height()), 4.5, 4.5)

        p.setPen(self._col("step"))
        f3 = QFont("Microsoft YaHei UI")
        f3.setPointSizeF(9.5)
        p.setFont(f3)
        p.drawText(QRectF(48, _H - 46, _W - 96, 24), Qt.AlignmentFlag.AlignLeft,
                   self._msg)
        p.setPen(self._col("count"))
        p.drawText(QRectF(48, _H - 46, _W - 96, 24),
                   Qt.AlignmentFlag.AlignRight,
                   "%d%%　·　%d / %d" % (
                       int(round(done * 100)),
                       min(self._step + 1, self._total), self._total))

    def _ease_to(self, target, pump):
        # pump=False（构造/装载期，深堆栈里不能 processEvents）也要平滑：
        # 3 帧 30ms 会把大跨度 tick 变成瞬跳（2026-11-17 用户报
        # "29%→90% 跳太快"），14 帧 ≈170ms 缓升，观感与速率一致。
        n, gap = (6, 0.018) if pump else (14, 0.012)
        for _ in range(n):
            d = target - self._shown
            if abs(d) < 0.0015:
                break
            self._shown += d * 0.45
            self.repaint()
            if pump:
                QApplication.processEvents()
            time.sleep(gap)
        self._shown = target
        self.repaint()

    def next_step(self, text=None, frac=None, pump=True):
        parts = len(_STEP_PLAN)
        if text is None:
            text = _STEP_PLAN[min(self._step, parts - 1)][0]
        raw = str(text)
        self._msg = _tr(raw)
        # 计数器只在出现新文本时前进：合并后的构造期文本会被多个 Stage /
        # 逐视图建壳循环重发同一文本，不去重会把 X/N 提前顶满，
        # 看起来"最后一步"提前出现并卡住（2026-11-17 用户实测复现）。
        if raw != self._last_raw:
            self._step += 1
            self._last_raw = raw
        if frac is None:
            frac = _PLAN.get(raw)
        if frac is None:
            frac = 0.06 + self._step / float(self._total) * 0.9
        self._progress = max(self._progress,
                             max(0.02, min(0.99, float(frac))))
        self._ease_to(self._progress, pump)
        if not pump:

            QApplication.sendPostedEvents(
                self, QEvent.Type.UpdateRequest)
            QApplication.sendPostedEvents(self, QEvent.Type.Paint)

            return
        QApplication.processEvents()

    def finish(self, widget):
        self._step = self._total
        self._progress = 1.0
        self._msg = _tr(_STEP_PLAN[-1][0])
        self._ease_to(1.0, False)

        self._pending = widget
        QTimer.singleShot(200, self._do_finish)

    def _do_finish(self):
        w = getattr(self, "_pending", None)
        if w is not None:

            w.show()
            w.raise_()
            w.activateWindow()

        self.close()
