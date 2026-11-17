# -*- coding: utf-8 -*-

import os
import platform
import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPalette, QPixmap
from PySide6.QtWidgets import (
                               QApplication,
                               QGridLayout,
                               QHBoxLayout,
                               QLabel,
                               QTextBrowser,
                               QVBoxLayout,
                               QWidget,
)

from ggis.core.app import i18n
from ggis.core.app import settings as _settings
from ggis.common.styling import icons
from ggis.common.styling import themes
from ggis.common.base.dialog import GgsDialog
from .app import _NavDialog
from ggis.common.widgets.buttons import GgsMediumButtonStyle1
import logging
from PySide6.QtWidgets import QFrame, QPushButton
_log = logging.getLogger("gmagis")

_tr = i18n.tr

_DEPS = (
    ("PySide6 · Qt", "LGPL-3.0",
     ("PySide6", "PySide6-Essentials", "PySide6-Addons"), "PySide6"),
    ("NumPy", "BSD-3-Clause", ("numpy",), "numpy"),
    ("SciPy", "BSD-3-Clause", ("scipy",), "scipy"),
    ("Matplotlib", "Matplotlib", ("matplotlib",), "matplotlib"),
    ("rasterio · GDAL", "BSD-3-Clause", ("rasterio",), "rasterio"),
    ("pyogrio · OGR", "MIT", ("pyogrio",), "pyogrio"),
    ("Shapely · GEOS", "BSD-3-Clause", ("shapely",), "shapely"),
    ("pyproj · PROJ", "MIT", ("pyproj",), "pyproj"),
    ("Rtree · libspatialindex", "MIT", ("rtree",), "rtree"),
    ("Pillow", "MIT-CMU", ("Pillow",), "PIL"),
)

QT_LICENSE_LINE = ("本产品使用 Qt6，依据 GNU Lesser General Public License v3"
                   "（LGPL v3）授权。")
GEOS_LICENSE_LINE = ("本产品经 shapely / rasterio / pyogrio 以动态链接方式使用 GEOS，"
                     "其许可为 GNU Lesser General Public License v2.1"
                     "（LGPL v2.1）或更高版本。")
LICENSE_DIR_LINE = "完整许可证全文见 resources/licenses/ 。"


def _version_of(cands, module=""):
    try:
        from importlib import metadata
    except Exception:
        _log.exception("silent exception in _version_of")
        metadata = None
    if metadata is not None:
        for name in cands:
            try:
                v = metadata.version(name)
                if v:
                    return v
            except Exception:
                _log.exception("silent exception in _version_of")
                continue
    if module:
        try:
            import importlib
            m = importlib.import_module(module)
            v = getattr(m, "__version__", None)
            if v:
                return str(v)
        except Exception:
            _log.exception("silent exception in _version_of")
    return ""


def _dep_versions():
    rows = []
    for label, lic, cands, module in _DEPS:
        v = _version_of(cands, module)
        rows.append((label, v or _tr("未安装"), lic))
    return rows


def _qt_version():
    try:
        from PySide6.QtCore import qVersion
        return qVersion() or None
    except Exception:
        _log.exception("silent exception in _qt_version")
        return None


def _binding_version():
    try:
        from PySide6 import __version__ as v
        return v
    except Exception:
        _log.exception("silent exception in _binding_version")
        return None


def _qt_show():
    qt = _qt_version()
    bind = _binding_version()
    if qt and bind and qt != bind:
        return "Qt {0}（PySide6 {1}）".format(qt, bind)
    return "Qt {0}".format(qt or bind or "—")


def _os_name():
    if sys.platform == "win32":
        try:
            return "Windows {0}（{1}）".format(platform.release(),
                                             platform.version())
        except Exception:
            _log.exception("silent exception in _os_name")
            return "Windows"
    try:
        return "{0} {1}".format(platform.system(), platform.release())
    except Exception:
        _log.exception("silent exception in _os_name")
        return platform.system()


def _app_version():
    try:
        from ggis import __version__ as v
        return str(v)
    except Exception:
        _log.exception("silent exception in _app_version")
        return "—"


def _scale_show():
    try:
        app = QApplication.instance()
        scr = app.primaryScreen() if app is not None else None
        dpr = float(scr.devicePixelRatio() or 1.0)
    except Exception:
        _log.exception("silent exception in _scale_show")
        dpr = 1.0
    return "{0}%".format(int(round(max(1.0, dpr) * 100)))


def _theme_show():
    try:
        t = str(_settings.get("theme") or "dark")
    except Exception:
        _log.exception("silent exception in _theme_show")
        t = "dark"
    return _tr("深色") if t != "light" else _tr("浅色")


def _lang_show():
    try:
        cur = i18n.lang()
    except Exception:
        _log.exception("silent exception in _lang_show")
        cur = "zh_CN"
    if cur == "zh_CN":
        return _tr("简体中文")
    return _tr("英文")


def _cpu_model():
    """CPU 型号（运行环境卡，2026-11-17 用户定稿）。Windows 读注册表
    CentralProcessor\\0 的 ProcessorNameString（友好名）；失败回退
    platform.processor()，仍失败显示「—」。"""
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION"
                    r"\System\CentralProcessor\0") as k:
                name, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if name:
                    return str(name).strip()
    except Exception:
        _log.exception("silent exception in _cpu_model")
    try:
        p = platform.processor()
        if p:
            return str(p)
    except Exception:
        _log.exception("silent exception in _cpu_model")
    return "—"


def _memory_show():
    """物理内存总量（运行环境卡，2026-11-17 用户定稿替代安装位置）。
    自带运行时无 psutil ⇒ 直接走 Windows API GlobalMemoryStatusEx，
    不为此新增依赖；失败显示「—」。"""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(st)):
            return "{0:.1f} GB".format(st.ullTotalPhys / 1024 ** 3)
    except Exception:
        _log.exception("silent exception in _memory_show")
    return "—"


def env_rows():
    py_ver = "{0}.{1}.{2}".format(*sys.version_info[:3])
    return [
        (_tr("版本"), "GmaGIS {0}".format(_app_version())),
        (_tr("界面框架"), _qt_show()),
        (_tr("运行时"), "Python {0}".format(py_ver)),
        (_tr("系统"), _os_name()),
        (_tr("架构"), platform.machine() or "—"),
        (_tr("CPU 型号"), _cpu_model()),
        (_tr("内存大小"), _memory_show()),
        (_tr("显示缩放"), _scale_show()),
        (_tr("主题"), _theme_show()),
        (_tr("界面语言"), _lang_show()),
    ]


def notices_candidates():
    out = []
    try:
        from ggis.app_paths import resource_path
        out.append(resource_path("licenses", "THIRD_PARTY_NOTICES.md"))
    except Exception:
        _log.exception("silent exception in notices_candidates")
    try:
        from ... import app_paths
        out.append(os.path.join(app_paths.app_root(),
                                "THIRD_PARTY_NOTICES.md"))
    except Exception:
        _log.exception("silent exception in notices_candidates")
    try:
        out.append(os.path.join(os.getcwd(), "THIRD_PARTY_NOTICES.md"))
    except Exception:
        _log.exception("silent exception in notices_candidates")
    return [p for p in out if p]


def notices_path():
    for p in notices_candidates():
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def license_text_path():
    cands = []
    try:
        from ... import app_paths
        cands.append(os.path.join(app_paths.app_root(), "license.txt"))
    except Exception:
        _log.exception("silent exception in license_text_path")
    try:
        cands.append(os.path.join(os.getcwd(), "license.txt"))
    except Exception:
        _log.exception("silent exception in license_text_path")
    for p in cands:
        if os.path.isfile(p):
            return os.path.abspath(p)
    return None


def license_notice_text():
    p = notices_path()
    if p:
        try:
            with open(p, encoding="utf-8") as f:
                txt = f.read()
            if txt.strip():
                return txt
        except Exception:
            _log.exception("silent exception in license_notice_text")
    return "\n".join([
        "# " + _tr("第三方许可声明"),
        "",
        _tr(QT_LICENSE_LINE),
        "",
        _tr(GEOS_LICENSE_LINE),
        "",
        _tr(LICENSE_DIR_LINE),
        "",
        "",
    ])


def _icon_label(name, size=16):
    lab = GgsAboutIcon()
    lab.setFixedSize(QSize(size, size))
    try:
        lab.setPixmap(icons.icon(name, size=size).pixmap(size, size))
    except Exception:
        _log.exception("silent exception in _icon_label")
    return lab


def _qr_cell(filename, caption, parent=None):
    """hero 右侧的二维码格：码图(96×96，与 hero 的 LOGO 等高，
    hero 高度不被撑高——2026-11-17 用户嫌 56px 太小调大) 纯贴图
    无卡片，说明文字悬停显示（用户定稿：标签直接放着挤，文本走
    tooltip）。hero 是 accent 渐变底，jpg 自带白底即视觉边界、
    暗浅主题都可直接扫。源图平滑缩放并按 DPR 出图。加载失败记
    日志整格隐藏——关于对话框在设置入口上，不弹错框。"""
    w = QWidget(parent)
    w.setToolTip(_tr(caption))
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    img = QLabel(w)
    img.setFixedSize(QSize(96, 96))
    img.setToolTip(_tr(caption))
    try:
        dpr = float(w.devicePixelRatioF()) or 1.0
        pm = QPixmap(os.path.join(icons.ICON_DIR, filename))
        if pm.isNull():
            raise FileNotFoundError(filename)
        scaled = pm.scaled(
            int(96 * dpr), int(96 * dpr),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        img.setPixmap(scaled)
    except Exception:
        _log.exception("qr pixmap @ about.py::_qr_cell")
        w.setVisible(False)
    lay.addWidget(img, 0, Qt.AlignmentFlag.AlignHCenter)
    return w


def _card(title, icon_name):
    box = GgsAboutCard()
    box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    lay = QVBoxLayout(box)
    lay.setContentsMargins(12, 10, 12, 12)
    lay.setSpacing(8)

    head = QHBoxLayout()
    head.setSpacing(6)
    head.addWidget(_icon_label(icon_name))
    lab = GgsAboutCardTitle(_tr(title))
    head.addWidget(lab)
    head.addStretch(1)
    lay.addLayout(head)

    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(4)
    grid.setColumnStretch(1, 1)
    lay.addLayout(grid)
    lay.addStretch(1)
    return box, grid


def _kv(grid, row, key, val, note=""):
    k = GgsAboutKey(_tr(key))
    k.setAlignment(Qt.AlignmentFlag.AlignRight
                   | Qt.AlignmentFlag.AlignVCenter)
    grid.addWidget(k, row, 0)
    v = GgsAboutVal(str(val))
    v.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse)
    grid.addWidget(v, row, 1)
    if note is not None:
        n = GgsAboutNote(str(note))
        grid.addWidget(n, row, 2)


class GgsAboutDialog(GgsDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsAboutDialog")
        self.setWindowTitle(_tr("关于 GmaGIS"))
        try:
            self.setWindowIcon(icons.app_icon())
        except Exception:
            _log.exception("silent exception in __init__")
        self.setMinimumWidth(680)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 0, 1, 0)
        root.setSpacing(0)
        root.addWidget(self._build_hero())

        body = QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 12)
        body.setSpacing(10)
        body.addLayout(self._build_columns())
        body.addWidget(self._build_license())
        body.addLayout(self._build_buttons())
        root.addLayout(body)

    def _build_hero(self):
        hero = GgsAboutHero()
        hero.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(hero)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(14)

        logo = QLabel()
        try:
            # LOGO 与右侧二维码同规出图（2026-11-17 用户实测 125% DPI
            # 下 LOGO 比码大 25%）：QIcon::pixmap(w,h) 无 DPR 参数版
            # 会按屏幕 DPR 放大返回，此前再固定 DPR=2.0 ⇒ 显示
            # 192*1.25/2=120 逻辑像素 ≠ 码的 96。现取大图源后 scaled
            # 到 96*dpr 物理像素并按 dpr 标记，任何缩放下严格 96 逻辑，
            # 与 _qr_cell 同一公式。
            dpr = float(logo.devicePixelRatioF()) or 1.0
            src = icons.app_icon().pixmap(256, 256)
            pm = src.scaled(
                int(96 * dpr), int(96 * dpr),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            logo.setPixmap(pm)
            logo.setFixedSize(QSize(96, 96))
        except Exception:
            _log.exception("silent exception in _build_hero")
        lay.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)

        col = QVBoxLayout()
        # LOGO/码 96px 后本列被拉到 96 高：此前 row/tagline 无对齐
        # 约束、多余空间被两项对半摊分（断言实测各 ~47px、文字各自
        # 居中），名称与定位语之间空出一大截（2026-11-17 用户报
        # "间距太大"）。现上下 stretch 夹住让文字组整体垂直居中、
        # 内部紧凑 6px；字号另在 themes.py 放大（20/9.5/10.5pt）。
        col.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        name = GgsAboutName("GmaGIS")
        row.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)
        badge = GgsAboutBadge("v" + _app_version())
        # 垂直居中，禁止被标题行高拉伸（QHBoxLayout 无对齐参数时
        # 子项默认拉伸到整行高 ⇒ 胶囊过高；居中后回落到内容高）。
        # 样式为用户定稿：半透明白底 + 边框原状。
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addStretch(1)
        col.addStretch(1)
        col.addLayout(row)
        # 定位语与启动页一致（2026-11-17 用户要求统一口径）。
        tag = GgsAboutTagline(
            _tr("专业桌面 GIS 平台 · 空间数据管理与分析"))
        col.addWidget(tag)
        col.addStretch(1)
        lay.addLayout(col, 1)

        # 右侧：联系作者 / 扫码赞助（用户定稿 hero 右端：96px 纯贴图，
        # 说明文字悬停显示，方案 A 的直放标签已按用户要求撤掉）。
        # 前后 addSpacing 把分隔线两侧间距抬到 24px（spacing 14 + 10）。
        lay.addSpacing(10)
        sep = QFrame(hero)
        sep.setObjectName("GgsAboutHeroSep")
        lay.addWidget(sep)
        lay.addSpacing(10)
        lay.addWidget(_qr_cell("LuoWeiXin.jpg", "联系作者", hero))
        lay.addSpacing(2)
        lay.addWidget(_qr_cell("Sponsor.jpg", "扫码赞助", hero))
        return hero

    def _build_columns(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        env, eg = _card("运行环境", "chip")
        for i, (k, v) in enumerate(env_rows()):
            _kv(eg, i, k, v, note=None)
        row.addWidget(env, 1)

        deps, dg = _card("组件版本", "modules")
        for i, (n, v, lic) in enumerate(_dep_versions()):
            _kv(dg, i, n, v, note=lic)
        row.addWidget(deps, 1)
        return row

    def _build_license(self):
        box, grid = _card("特别声明", "license")

        def _notice(row, key, html):
            k = GgsAboutKey(_tr(key))
            k.setAlignment(Qt.AlignmentFlag.AlignRight
                           | Qt.AlignmentFlag.AlignTop)
            v = GgsAboutVal("")
            v.setTextFormat(Qt.TextFormat.RichText)
            v.setText(html)
            v.setWordWrap(True)
            v.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(k, row, 0)
            grid.addWidget(v, row, 1)

        try:
            dim = themes.text_dim(_settings.get("theme"))
        except Exception:
            _log.exception("silent exception in _build_license")
            dim = "#8a8f99"
        _notice(0, "Qt6", _tr(QT_LICENSE_LINE).replace("Qt6", "<b>Qt6</b>"))
        _notice(1, "GEOS",
                "<span style='color:{}'>{}</span>".format(
                    dim, _tr(GEOS_LICENSE_LINE)))
        return box

    def _build_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        btn_license = GgsMediumButtonStyle1(
            "license", _tr("许可声明"),
            slot=lambda: show_license_declaration(self), parent=self)
        row.addWidget(btn_license)
        row.addStretch(1)

        ok = GgsAboutOkButton(_tr("确定"))
        ok.setDefault(True)
        ok.setMinimumWidth(88)
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        return row


def show_about(parent=None):
    dlg = GgsAboutDialog(parent)
    try:
        dlg.exec()
    finally:
        try:
            dlg.deleteLater()
        except Exception:
            _log.exception("silent exception in show_about")
    return dlg


class LicenseDeclarationDialog(_NavDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GgsLicenseDeclarationDialog")
        self.setWindowTitle(_tr("许可声明"))
        try:
            self.setWindowIcon(icons.app_icon())
        except Exception:
            _log.exception("silent exception in __init__")

        try:
            ic_g = icons.icon("license", size=16)
        except Exception:
            _log.exception("silent exception in __init__")
            ic_g = QIcon()
        try:
            ic_t = icons.icon("modules", size=16)
        except Exception:
            _log.exception("silent exception in __init__")
            ic_t = QIcon()
        self._add_page(ic_g, _tr("GmaGIS许可声明"),
                       self._make_view(self._gmagis_license_text()),
                       _tr("本软件许可全文"))
        self._add_page(ic_t, _tr("第三方许可声明"),
                       self._make_view(license_notice_text()),
                       _tr("第三方组件许可全文"))
        self.finish()

    def _make_view(self, markdown):
        b = QTextBrowser(self)
        b.setObjectName("GgsNoticesView")
        try:
            b.document().setDefaultStyleSheet(self._doc_css())
        except Exception:
            _log.exception("silent exception in _make_view")
        b.setMarkdown(markdown or _tr("（无内容）"))
        return b


    def _doc_css(self):
        name = "dark" if icons.is_dark() else "light"
        pal = themes.theme_colors(name)
        try:
            link = themes.palette(name).color(
                QPalette.ColorRole.Link).name()
        except Exception:
            _log.exception("silent exception in _doc_css")
            link = pal.get("accent", "#3d7fd1")
        return (
            "h1 { font-size: 1.2em; font-weight: 600; color: %s;"
            " margin: 2px 0 5px 0; }"
            "h2 { font-size: 1.1em; font-weight: 600; color: %s;"
            " margin: 2px 0 4px 0; }"
            "h3, h4, h5, h6 { font-size: 1.0em; font-weight: 600;"
            " color: %s; margin: 2px 0 3px 0; }"
            "a { color: %s; text-decoration: underline; }"
            "blockquote { color: %s; margin: 3px 0 3px 10px; }"
            "p, ul, ol { margin: 2px 0; }"
            "pre, code { font-family: Consolas, 'Courier New', monospace;"
            " font-size: 0.92em; }"
            % (pal["text"], pal["text"], pal["text"],
               link, pal["text_dim"])
        )

    def _gmagis_license_text(self):
        p = license_text_path()
        if p:
            try:
                with open(p, encoding="utf-8") as f:
                    data = f.read()
                if data.strip():
                    return data
            except Exception:
                _log.exception("silent exception in _gmagis_license_text")
        return _tr("未找到 license.txt。")


def show_license_declaration(parent=None):
    dlg = LicenseDeclarationDialog(parent)
    try:
        dlg.exec()
    finally:
        try:
            dlg.deleteLater()
        except Exception:
            _log.exception("silent exception in show_license_declaration")
    return dlg


class GgsAboutBadge(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutBadge")
class GgsAboutCard(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutCard")
class GgsAboutCardTitle(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutCardTitle")
class GgsAboutHero(QFrame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutHero")
class GgsAboutIcon(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutIcon")
class GgsAboutKey(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutKey")
class GgsAboutName(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutName")
class GgsAboutNote(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutNote")
class GgsAboutOkButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutOkButton")
class GgsAboutTagline(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutTagline")
class GgsAboutVal(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("GgsAboutVal")
