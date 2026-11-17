# -*- coding: utf-8 -*-
"""独立起始主页窗口（方案 B：无原生标题栏 + 无左边栏）。

薄自绘顶栏（Logo + 最小化/最大化/关闭，可拖动），主区左对齐铺满：
新建工程模板一行 + 最近工程全宽密集列表（搜索/分页） + 打开其他工程。
本窗口完全不依赖 MainWindow / ctx / ViewHost，只读 recent 模块。

用户在主页点"新建工程/打开工程/最近工程"时，由 app.py 注入的回调
负责构造 MainWindow 并打开对应内容，随后关闭本窗口。
"""
import os

from ggis.common.util.exc_report import exc_note
from ggis.common.base.dialog import GgsDialog
from ggis.ui.framework.titlebar import (GgsWinBtn, _WinCloseButton, win_glyph,
                                        TITLE_H, WINCTL_W)
from PySide6.QtCore import Qt, QSize, Signal, QTimer
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (QMainWindow, QWidget, QFrame, QLabel, QToolButton,
                               QPushButton, QVBoxLayout, QHBoxLayout,
                               QSizePolicy,
                               QCheckBox, QDialogButtonBox, QScrollArea,
                               QToolTip)

from ggis.common.styling import icons
from ggis.common.widgets.inputs import GgsSearchEdit, GgsFileOutputWidget
from ggis.core.app import i18n
from ggis.core.app import recent

_tr = i18n.tr


class NewProjectDialog(GgsDialog):
    """新建工程（C 方案）：先选工程保存文件，再选视图类型。
    视图类型可多选（复选框）；布局/模型暂不可用，置灰。
    必须至少勾选一个视图：零勾选时确定按钮禁用（不允许空视图工程）。
    路径与类型由 chosen_path()/chosen_kinds() 输出。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsNewProjectDialog")
        self.setWindowTitle(i18n.tr("新建工程"))
        try:
            self.setWindowIcon(icons.icon("new", size=16))
        except Exception:
            exc_note("icon @ home.py::NewProjectDialog")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(10)

        # 1) 选择保存文件（Ggs 内嵌控件：路径框 + 浏览按钮）
        self.file_out = GgsFileOutputWidget(
            self, kind="vector", title=i18n.tr("保存位置"))
        self.file_out.set_suffix(".ggs")
        self.file_out.set_filters(
            i18n.tr("GmaGIS 工程 (*.ggs);;所有文件 (*)"))
        # 留空 = 内存工程（不落盘，退出前需另存才能保留）
        self.file_out.ed_path.setPlaceholderText(i18n.tr("留空创建内存工程"))
        root.addWidget(self.file_out)

        sep = QFrame(self)
        sep.setObjectName("GgsHomeSep")
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # 2) 视图类型（复选框纵排，仅名称，无多余提示/说明）
        t = QLabel(i18n.tr("视图类型"))
        t.setObjectName("GgsNewProjSection")
        root.addWidget(t)

        specs = (
            ("map", "map_street", i18n.tr("地图视图"), True),
            ("layout", "layout", i18n.tr("布局视图"), False),
            ("model", "model", i18n.tr("模型构建器"), False),
        )
        self._checks = {}
        self._cards = {}
        for key, icon_name, name, enabled in specs:
            card = QFrame(self)
            card.setObjectName("GgsNewProjCard")
            card.setEnabled(enabled)
            hl = QHBoxLayout(card)
            hl.setContentsMargins(12, 8, 12, 8)
            hl.setSpacing(12)
            cb = QCheckBox(card)
            cb.setObjectName("GgsNewProjCheck")
            cb.setChecked(key == "map")
            cb.setEnabled(enabled)
            hl.addWidget(cb)
            ic = QLabel(card)
            ic.setObjectName("GgsNewProjIcon")
            ic.setFixedSize(34, 34)
            try:
                ic.setPixmap(icons.icon(icon_name, size=32).pixmap(32, 32))
            except Exception:
                exc_note("view icon @ home.py::NewProjectDialog")
            hl.addWidget(ic)
            nm = QLabel(name)
            nm.setObjectName("GgsNewProjName")
            nm.setEnabled(enabled)
            hl.addWidget(nm)
            hl.addStretch(1)
            root.addWidget(card)
            self._checks[key] = cb
            self._cards[key] = card
            # 勾选态高亮：卡片随复选框切换 property，QSS 给选中态描边
            cb.toggled.connect(lambda on, c=card: (
                c.setProperty("checked", bool(on)),
                c.style().unpolish(c), c.style().polish(c)))
            card.setProperty("checked", cb.isChecked())
            # 必须至少勾选一个视图：勾选变化同步刷新确定按钮可用态
            cb.toggled.connect(self._update_ok)

        root.addStretch(1)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel, self)
        self._ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText(i18n.tr("确定"))
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(
            i18n.tr("取消"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)
        # 必须至少勾选一个视图：零勾选禁用确定（不允许空视图工程）
        self._update_ok()

    def _update_ok(self, *_):
        """零勾选禁用确定：新建工程必须至少选择一个视图。"""
        self._ok_btn.setEnabled(bool(self.chosen_kinds()))

    def chosen_path(self):
        return self.file_out.value()

    def chosen_kinds(self):
        """返回所有勾选的视图类型（布局/模型禁用，当前只有 map 可勾）。"""
        return [key for key, cb in self._checks.items() if cb.isChecked()]


class _HomeTitleBar(QFrame):
    """主页品牌行（照 ArcGIS Pro）：大 LOGO + 大字产品名在左，
    右侧窗口按钮与主窗口标题栏同款标准尺寸（GgsWinBtn + win_glyph
    字形图标，无最大化）；品牌行白底与内容区区分，空白处可拖动窗口。"""

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsHomeTitleBar")
        self.setFixedHeight(56)
        self._host = host
        self._drag_pos = None

        lay = QHBoxLayout(self)
        # 左边距 40 与主区对齐，品牌行像内容区的一部分
        lay.setContentsMargins(40, 0, 0, 0)
        lay.setSpacing(12)

        logo = QLabel(self)
        logo.setObjectName("GgsHomeBrandIcon")
        try:
            logo.setPixmap(icons.app_icon().pixmap(34, 34))
        except Exception:
            exc_note("brand icon @ home.py::_HomeTitleBar")
        lay.addWidget(logo)

        brand = QLabel("GmaGIS")
        brand.setObjectName("GgsHomeBrand")
        lay.addWidget(brand)
        lay.addStretch(1)

        # 窗口按钮组：与主窗口标题栏同款字形 + 标准尺寸（45×32）
        self.btn_min = GgsWinBtn()
        self.btn_min.setIcon(self._glyph("min"))
        self.btn_min.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_min.setFixedSize(WINCTL_W, TITLE_H)
        self.btn_min.setToolTip(_tr("最小化"))
        self.btn_min.clicked.connect(host.showMinimized)
        # 贴顶：原生标题栏按钮都顶着窗口上沿（行加高后按钮不悬空）
        lay.addWidget(self.btn_min, 0, Qt.AlignmentFlag.AlignTop)

        self.btn_close = _WinCloseButton(self)
        self.btn_close.setObjectName("GgsWinClose")
        self.btn_close.setIcon(self._glyph("close"))
        self.btn_close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_close.setFixedSize(WINCTL_W, TITLE_H)
        self.btn_close.setToolTip(_tr("关闭"))
        self.btn_close.clicked.connect(host.close)
        lay.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)

    def _glyph(self, kind, color=None):
        """与主窗口标题栏同款的窗口字形图标（win_glyph，主题取色）。"""
        try:
            dpr = float(self.devicePixelRatioF()) or 1.0
        except Exception:
            exc_note("_glyph @ home.py::_HomeTitleBar")
            dpr = 1.0
        return win_glyph(kind, dpr, 16, color)

    def refresh_glyphs(self):
        """换主题后重刷字形颜色（QSS 由 app 层统一重设）。"""
        self.btn_min.setIcon(self._glyph("min"))
        self.btn_close.repaint_glyph()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            try:
                wh = self.window().windowHandle()
                if wh is not None:
                    wh.startSystemMove()
                    return
            except Exception:
                exc_note("startSystemMove @ home.py::_HomeTitleBar")
            self._drag_pos = e.globalPosition().toPoint() - self.window().pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        super().mouseReleaseEvent(e)


class _HomeNewCard(QToolButton):
    """新建工程模板卡：图标+名称上下排，悬停高亮，点开新建工程对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsHomeNewCard")
        self.setText(_tr("新建工程"))
        self.setToolTip(_tr("新建工程并选择视图类型"))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(40, 40))
        self.setFixedSize(128, 92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            # 图标 = 项目工程文件图标（resources/icons/project.ico，
            # 与 .ggs 文件关联的 DefaultIcon 同源——资源管理器里
            # .ggs 文件长什么样，这里就是什么样）。
            self.setIcon(QIcon(os.path.join(icons.ICON_DIR, "project.ico")))
        except Exception:
            exc_note("new icon @ home.py::_HomeNewCard")


class _HomeQrCell(QWidget):
    """主页右列的二维码：纯贴图（无边框无背景卡），码图(160×160)
    居中、9pt 标签(GgsHomeHint)在下。源图平滑缩放并按 DPR 出图
    （1.25/1.5 缩放下约 200/240 物理像素，扫码非常稳）；jpg 自带
    白底，暗色主题下仍为白底黑码、保持可扫。资源缺失走本文件 icon
    加载的既有惯例（exc_note 记日志 + 整格隐藏，主页在启动关键
    路径上不弹错框）。"""

    _SIZE = 160

    def __init__(self, filename, caption, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.img = QLabel(self)
        self.img.setFixedSize(QSize(self._SIZE, self._SIZE))
        try:
            dpr = float(self.devicePixelRatioF()) or 1.0
            pm = QPixmap(os.path.join(icons.ICON_DIR, filename))
            if pm.isNull():
                raise FileNotFoundError(filename)
            scaled = pm.scaled(
                int(self._SIZE * dpr), int(self._SIZE * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            self.img.setPixmap(scaled)
        except Exception:
            exc_note("qr pixmap @ home.py::_HomeQrCell")
            self.setVisible(False)
        lay.addWidget(self.img, 0, Qt.AlignmentFlag.AlignHCenter)
        cap = QLabel(_tr(caption), self)
        cap.setObjectName("GgsHomeHint")
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(cap)


class _HomeRecentCell(QWidget):
    """最近工程行容器：整行可点（不只文件名文本），手型光标。
    悬停提示自实现（enter 后 700ms 显式 showText）：Qt 原生 tooltip 走
    系统派发层，在"窗口非激活"等场景会被静默吞掉，这里不依赖它。"""

    def __init__(self, host, path, parent=None, enabled=True):
        super().__init__(parent)
        # QWidget 子类默认不画 QSS 背景：必须显式开 WA_StyledBackground，
        # 否则底色和 :hover 悬停高亮都不渲染。
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._host = host
        self._path = path if enabled else None
        self._tip = path
        if not enabled:
            # 文件丢失：整行禁用 ⇒ QSS :enabled:hover 不给它悬停高亮
            # （不可点的行不该亮），子控件文本色本就走禁用样式，无额外变化。
            self.setEnabled(False)
        self.setToolTip(path)
        self._tip_timer = QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.setInterval(700)
        self._tip_timer.timeout.connect(self._show_tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ArrowCursor)

    def _show_tip(self):
        if self.isVisible() and self.underMouse() and self._tip:
            QToolTip.showText(QCursor.pos(), self._tip, self)

    def enterEvent(self, e):
        if self._tip:
            self._tip_timer.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._tip_timer.stop()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton
                and self._path is not None):
            self._host._recent(self._path)
            return
        super().mousePressEvent(e)


class _HomeRecentBtn(QToolButton):
    def __init__(self, label, path, parent=None, enabled=True):
        super().__init__(parent)
        self.setObjectName("GgsHomeRecentBtn")
        self.setText(label)
        self.setToolTip(path)
        self.path = path
        self.setEnabled(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled
                       else Qt.CursorShape.ForbiddenCursor)


class HomeWindow(QMainWindow):

    closed = Signal()

    def __init__(self, on_new=None, on_open=None, on_recent=None,
                 on_options=None):
        super().__init__()
        self.setObjectName("GgsHomeWindow")
        self.setWindowTitle("GmaGIS")
        try:
            self.setWindowIcon(icons.app_icon())
        except Exception:
            exc_note("icon @ HomeWindow")
        # 去掉原生标题栏：自绘顶栏替代（保留 Window 类型以显示于任务栏）。
        self.setWindowFlags(Qt.WindowType.Window
                            | Qt.WindowType.FramelessWindowHint)
        # Qt 系统层对"非激活窗口"静默吞 tooltip 事件；主页是无边框窗 +
        # 嵌套事件循环（loop.exec 阻塞在 main），显式放开此门槛。
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self._dwm_round_done = False
        self.resize(1120, 720)
        self.setMinimumSize(880, 560)

        self._on_new = on_new or (lambda: None)
        self._on_open = on_open or (lambda: None)
        self._on_recent = on_recent or (lambda _p: None)
        self._on_options = on_options or (lambda: None)
        self._items = []
        self._filter = ""

        central = QWidget(self)
        central.setObjectName("GgsHomeCentral")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # —— 自绘薄顶栏（替代原生标题栏） ——
        self.title_bar = _HomeTitleBar(self, central)
        root.addWidget(self.title_bar)

        # —— 主区：左右两栏。左=新建工程+最近工程（原有内容整体在此
        # 列竖排，布局沿用 mv 变量名）；中=栏间细分隔线；右=独立二维码
        # 列（用户定稿：码 120px，顶部与"新建工程"标题对齐）。 ——
        main = QWidget(central)
        main.setObjectName("GgsHomeMain")
        cols = QHBoxLayout(main)
        # 右 margin 16（非 40）：保证二维码左右空白对称——
        # 分隔线→码左 = spacing16 + 列内余量24 = 40px，
        # 码右→窗口右缘 = 列内余量24 + 右margin16 = 40px（实测等宽）。
        cols.setContentsMargins(40, 18, 16, 14)
        cols.setSpacing(16)
        root.addWidget(main, 1)

        left = QWidget(main)
        mv = QVBoxLayout(left)
        mv.setContentsMargins(0, 0, 0, 0)
        mv.setSpacing(10)
        cols.addWidget(left, 1)

        vsep = QFrame(main)
        vsep.setObjectName("GgsHomeSep")
        vsep.setFixedWidth(1)
        cols.addWidget(vsep)

        qr_col = QWidget(main)
        # 列宽 208 = 码 160 + 左右各 24 余量（对称配比见上方 cols 注释）。
        qr_col.setFixedWidth(208)
        qv = QVBoxLayout(qr_col)
        qv.setContentsMargins(0, 0, 0, 0)
        qv.setSpacing(12)
        cols.addWidget(qr_col, 0)

        # 新建工程：标题 + 一张模板卡（图标+名称，悬停高亮），点开新建工程对话框
        t_new = QLabel(_tr("新建工程"))
        t_new.setObjectName("GgsHomeSection")
        t_new.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        mv.addWidget(t_new)
        card_row = QHBoxLayout()
        card_row.setSpacing(12)
        card_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.card_new = _HomeNewCard(main)
        self.card_new.clicked.connect(self._new)
        card_row.addWidget(self.card_new)
        card_row.addStretch(1)
        mv.addLayout(card_row)

        # 分隔
        sep = QFrame(main)
        sep.setObjectName("GgsHomeSep")
        sep.setFixedHeight(1)
        mv.addWidget(sep)

        # 最近工程 标题行
        h = QHBoxLayout()
        t_recent = QLabel(_tr("最近工程"))
        t_recent.setObjectName("GgsHomeSection")
        t_recent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        h.addWidget(t_recent)
        self.ed_search = GgsSearchEdit(main)
        self.ed_search.setPlaceholderText(_tr("搜索"))
        self.ed_search.setFixedWidth(180)
        self.ed_search.textChanged.connect(self._on_search)
        h.addWidget(self.ed_search)
        h.addStretch(1)
        self.btn_open = QPushButton(_tr("打开其他工程…"), main)
        self.btn_open.setObjectName("GgsHomeOpenBtn")
        self.btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open.setToolTip(_tr("打开工程"))
        self.btn_open.setIconSize(QSize(16, 16))
        try:
            self.btn_open.setIcon(icons.icon("project_open", size=16))
        except Exception:
            exc_note("open icon @ home.py::HomeWindow")
        self.btn_open.clicked.connect(self._open)
        h.addWidget(self.btn_open)
        mv.addLayout(h)

        # 最近工程列表：全部显示，超出部分滚动（无分页按钮）
        self.list_host = QWidget()
        self.list_host.setObjectName("GgsHomeListHost")
        self.list_grid = QVBoxLayout(self.list_host)
        self.list_grid.setContentsMargins(0, 0, 0, 0)
        self.list_grid.setSpacing(4)
        self.scroll = QScrollArea(main)
        self.scroll.setObjectName("GgsHomeScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setWidget(self.list_host)
        mv.addWidget(self.scroll, 1)  # 占满剩余空间，条目在内部顶部对齐、超出滚动

        # 底部左下角：选项入口（纯图标，悬停提示说明用途）
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 2, 0, 0)
        self.btn_options = QToolButton(main)
        self.btn_options.setObjectName("GgsHomeIconBtn")
        self.btn_options.setToolTip(
            _tr("工程设置（名称 / 单位）与应用程序选项（主题 / 语言等）"))
        self.btn_options.setIconSize(QSize(18, 18))
        try:
            self.btn_options.setIcon(icons.icon("settings", size=18))
        except Exception:
            exc_note("settings icon @ home.py::HomeWindow")
        self.btn_options.clicked.connect(self._options)
        bottom.addWidget(self.btn_options)
        bottom.addStretch(1)
        mv.addLayout(bottom)

        # 右列：联系作者 / 扫码赞助（用户定稿右侧独立一列，纯贴图
        # 无卡片、码 144px），列内上下三段弹性等分——两码均匀分布、
        # 不靠顶（用户定稿）。
        self.qr_weixin = _HomeQrCell("LuoWeiXin.jpg", "联系作者", qr_col)
        self.qr_sponsor = _HomeQrCell("Sponsor.jpg", "扫码赞助", qr_col)
        qv.addStretch(1)
        qv.addWidget(self.qr_weixin)
        qv.addStretch(1)
        qv.addWidget(self.qr_sponsor)
        qv.addStretch(1)

        self._rebuild()

    # ---------- 数据 ----------
    def _load_items(self):
        try:
            return list(recent.load())
        except Exception:
            exc_note("_load_items @ home.py")
            return []

    def _on_search(self, text):
        self._filter = str(text or "").strip().lower()
        self._rebuild()

    def _rebuild(self):
        while self.list_grid.count():
            it = self.list_grid.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()  # deleteLater 是异步的：先隐藏并脱父，避免旧行滞留左上角
                w.setParent(None)
                w.deleteLater()
        items = self._load_items()
        if self._filter:
            items = [p for p in items if self._filter in p.lower()
                     or self._filter in recent.label(p).lower()]
        self._items = items
        if not items:
            empty = QLabel(_tr("（尚无最近工程）"))
            empty.setObjectName("GgsHomeHint")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_grid.addWidget(empty)
        else:
            for path in items:
                ok = recent.exists(path)
                cell = _HomeRecentCell(self, path, self, ok)
                cell.setObjectName("GgsHomeRecentRow")
                cell.setFixedHeight(46)
                cell.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Fixed)
                hl = QHBoxLayout(cell)
                hl.setContentsMargins(10, 4, 10, 4)
                hl.setSpacing(10)
                ic = QLabel(cell)
                ic.setToolTip(path)
                try:
                    # 图标 = 项目工程文件图标（同新建工程卡，与资源
                    # 管理器里 .ggs 文件图标一致）。
                    ic.setPixmap(QIcon(os.path.join(
                        icons.ICON_DIR, "project.ico")).pixmap(24, 24))
                except Exception:
                    exc_note("recent icon @ home.py::_rebuild")
                hl.addWidget(ic)
                name = (recent.label(path) if ok
                        else _tr("{0}（文件已不存在）").format(path))
                btn = _HomeRecentBtn(name, path, cell, ok)
                btn.clicked.connect(lambda _c=False, p=path: self._recent(p))
                vl = QVBoxLayout()
                vl.setSpacing(0)
                vl.addWidget(btn)
                pth = QLabel(path)
                pth.setObjectName("GgsHomeHint")
                pth.setToolTip(path)
                vl.addWidget(pth)
                hl.addLayout(vl, 1)
                self.list_grid.addWidget(cell)
        # 末尾留白由 list_host 的布局处理：条目顶部对齐，不参与拉伸均分
        self.list_grid.addStretch(1)

    # ---------- 动作（委托给 app.py 注入的回调） ----------
    def _new(self):
        self._on_new()

    def _options(self):
        self._on_options()

    def _open(self):
        self._on_open()

    def _recent(self, path):
        self._on_recent(path)

    def refresh(self):
        self._rebuild()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._dwm_round_done:
            self._dwm_round_done = True
            QTimer.singleShot(0, self._apply_dwm_round)

    def _apply_dwm_round(self):
        """Win11 DWM 圆角：与 MainWindow._apply_dwm_round 同款
        （DWMWA_WINDOW_CORNER_PREFERENCE = 2 即 DWMWCP_ROUND）。"""
        try:
            import ctypes
            hwnd = int(self.winId())
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), 4)
        except Exception:
            exc_note("_apply_dwm_round @ home.py::HomeWindow")

    def closeEvent(self, event):
        super().closeEvent(event)
        self.closed.emit()
