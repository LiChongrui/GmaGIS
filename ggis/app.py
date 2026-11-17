# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import logging
import logging.handlers
import os
import shutil
import sys

from . import app_paths
_log = logging.getLogger("gmagis")


def _bind_dll_dirs():
    if not sys.platform.startswith("win"):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    sp = os.path.join(root, "python", "Lib", "site-packages")
    if not os.path.isdir(sp):
        return
    try:
        add = os.add_dll_directory
    except AttributeError:
        exc_note("_bind_dll_dirs @ ggis/app.py:35")
        return
    for sub in ("PySide6", os.path.join("rasterio", ".libs"),
                os.path.join("shapely", "DLLs"),
                os.path.join("pyogrio", ".libs"),
                os.path.join("pyproj", ".libs"),
                os.path.join("PySide6", "plugins", "platforms")):
        d = os.path.join(sp, sub)
        if os.path.isdir(d):
            try:
                add(d)
            except Exception:
                _log.exception("silent exception in _bind_dll_dirs")

    libroot = os.path.join(root, "python", "Library")
    if os.path.isdir(os.path.join(libroot, "bin")):
        try:
            add(os.path.join(libroot, "bin"))
        except Exception:
            _log.exception("silent exception in _bind_dll_dirs")
        _bin = os.path.join(libroot, "bin")
        _p = os.environ.get("PATH", "")
        if _bin not in _p.split(os.pathsep):
            os.environ["PATH"] = _bin + os.pathsep + _p
        gpdir = os.path.join(libroot, "lib", "gdalplugins")
        if os.path.isdir(gpdir):
            os.environ.setdefault("GDAL_DRIVER_PATH", gpdir)
        share = os.path.join(libroot, "share")
        for var, sub in (("GDAL_DATA", "gdal"), ("PROJ_LIB", "proj"),
                         ("PROJ_DATA", "proj")):
            d = os.path.join(share, sub)
            if os.path.isdir(d):
                os.environ.setdefault(var, d)


def shutdown_workers():
    global _WORKERS_STOPPED
    if _WORKERS_STOPPED:
        return
    _WORKERS_STOPPED = True
    import time as _time
    _deadline = _time.perf_counter() + 3.0

    def _left():
        return max(0, int((_deadline - _time.perf_counter()) * 1000))

    try:
        from .exec import task as exec_task
        exec_task.wait_protected()
        exec_task.shutdown(_left())
    except Exception:
        _log.exception("silent exception in shutdown_workers")
    try:
        from PySide6.QtWidgets import QApplication as _QApp
        from .render.map_canvas import GgsMapCanvas as _Cv

        _qa = _QApp.instance()
        if _qa is not None:
            for _w in _qa.topLevelWidgets():
                try:
                    for _cv in _w.findChildren(_Cv):
                        try:
                            _cv.release_buffers()
                        except Exception:
                            _log.exception("silent exception in shutdown_workers")
                except Exception:
                    _log.exception("silent exception in shutdown_workers")
    except Exception:
        _log.exception("silent exception in shutdown_workers")
    try:
        from PySide6.QtWidgets import QApplication as _QApp2
        from ggis.ui.views.layout.workspace import GgsLayoutWorkspace as _LWS

        _qa2 = _QApp2.instance()
        if _qa2 is not None:
            for _w in _qa2.topLevelWidgets():
                try:
                    for _ws in _w.findChildren(_LWS):
                        try:
                            _ws.view.layout_scene().shutdown()
                        except Exception:
                            _log.exception("silent exception in shutdown_workers")
                except Exception:
                    _log.exception("silent exception in shutdown_workers")
    except Exception:
        _log.exception("silent exception in shutdown_workers")
    try:
        from .io import async_loader
        async_loader.shutdown(_left())
    except Exception:
        _log.exception("silent exception in shutdown_workers")
    try:
        from .render import tiles
        tiles.shutdown(_left())
    except Exception:
        _log.exception("silent exception in shutdown_workers")


_WORKERS_STOPPED = False


def _prune_raster_cache_async():
    def _work():
        try:
            from .io import raster_pyramid as pyr
            freed = pyr.prune_stale()
            if freed:
                try:
                    get_logger("app").info(
                        "栅格金字塔缓存清理：释放 %.1f MB",
                        freed / 1048576.0)
                except Exception:
                    _log.exception("silent exception in _work")
        except Exception:
            _log.exception("silent exception in _work")

    try:
        import threading
        threading.Thread(target=_work, name="ggs-prune-cache",
                         daemon=True).start()
    except Exception:
        _log.exception("silent exception in _prune_raster_cache_async")


_GGS_STYLE_KEEP = []


def _install_tree_branch_style(app) -> None:
    try:
        from PySide6.QtWidgets import (QProxyStyle, QStyle,
                                       QStyleFactory, QTreeView)
    except Exception:
        _log.exception("silent exception in _install_tree_branch_style")
        return
    try:
        if "windows11" not in QStyleFactory.keys():
            return
        base = QStyleFactory.create("windows11")
        if base is None:
            return
    except Exception:
        _log.exception("silent exception in _install_tree_branch_style")
        return

    pe_row = QStyle.PrimitiveElement.PE_PanelItemViewRow
    sel = QStyle.StateFlag.State_Selected
    over = QStyle.StateFlag.State_MouseOver

    class _GgsTreeStyle(QProxyStyle):

        def drawPrimitive(self, pe, opt, p, w):
            if (pe == pe_row and isinstance(w, QTreeView)
                    and ((opt.state & sel) or (opt.state & over))):
                return
            super().drawPrimitive(pe, opt, p, w)

    try:
        proxy = _GgsTreeStyle(base)
        _GGS_STYLE_KEEP.extend([base, proxy, _GgsTreeStyle])
        app.setStyle(proxy)
    except Exception:
        _log.exception("silent exception in _install_tree_branch_style")
        return


def main() -> int:
    try:
        setup()
    except Exception:
        _log.exception("silent exception in main")

    _bind_dll_dirs()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts,
                              True)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GmaGIS")
    app.setOrganizationName("GmaGIS")

    _install_tree_branch_style(app)

    app.aboutToQuit.connect(shutdown_workers)

    _prune_raster_cache_async()

    from ggis.core.app import settings as _settings
    from ggis.core.app import i18n
    from ggis.common.styling import icons
    from ggis.common.styling import themes
    from ggis.main_window import MainWindow


    try:
        i18n.install_translators()
    except Exception:
        _log.exception("silent exception in main")

    theme = _settings.get("theme") or "dark"

    splash = None
    _argv_projects = [a.strip() for a in sys.argv[1:]
                      if a.strip() and a.strip().lower().endswith(".ggs")]

    def _start_splash():
        """启动画面先行：加载必要组件期间即显示；无工程文件时先隐藏、
        弹欢迎页让用户选择，选完工程再恢复显示，掩盖工程装载过程。"""
        nonlocal splash
        if splash is not None:
            return
        try:
            from .ui.launch.splash import SplashScreen
            splash = SplashScreen(theme=theme)
            splash.show()
            app.processEvents()
        except Exception:
            _log.exception("silent exception in main")
            splash = None

    # 双击 exe 与双击 .ggs 文件同一节奏：启动画面先出，组件在画面下加载。
    _start_splash()

    def _boot_step(text, work=None):
        if splash is not None:
            try:
                splash.next_step(text)
            except Exception:
                _log.exception("silent exception in _boot_step")
        if work is None:
            return
        try:
            work()
        except Exception:
            _log.exception("silent exception in _boot_step")

    _boot_step("正在加载运行时…",
               lambda: icons.set_theme(theme != "light"))

    def _apply_qss():
        app.setStyleSheet(themes.qss(theme))
        app.setWindowIcon(icons.app_icon())

    _boot_step("正在注册数据提供者…", _apply_qss)

    def _boot_tick(text, frac=None):
        if splash is None:
            return
        try:
            splash.next_step(text, frac=frac, pump=False)
        except Exception:
            _log.exception("silent exception in _boot_tick")

    # —— 主窗口构造（启动重活）：在 splash 画面下完成。无工程文件时
    # 随后隐藏 splash 弹欢迎页，用户选择期间主窗口已在待命——选完工程
    # 只做装载，不再等构造，欢迎页之后的等待大幅缩短。——
    _boot_step("正在构建界面…")
    win = MainWindow(boot=_boot_tick)

    # —— 欢迎页：无工程文件参数时，splash 已加载完必要组件，
    # 先隐藏它、弹出欢迎页让用户选择；选完工程再恢复 splash 装载。——
    _home_pick_path = None
    _home_pick_new = False
    _home_pick_kinds = []
    if not _argv_projects:
        # 没有工程文件 → 隐藏启动画面，弹欢迎页（组件已加载完）
        try:
            from .ui.launch.home import HomeWindow
            from ggis.common.base.dialog import GgsFileDialog
            from ggis.core.app import i18n as _i18n

            _home = {"win": None, "loop": None}
            _choice = {"path": None, "kinds": [], "new": False, "done": False}

            def _on_new():
                from .ui.launch.home import NewProjectDialog
                dlg = NewProjectDialog(_home["win"])
                if dlg.exec() != dlg.DialogCode.Accepted:
                    return
                # C 方案：保存路径已在对话框内选好，不再二次弹保存框；
                # 留空 = 内存工程（new_project("") 不绑定文件）。
                path = dlg.chosen_path().strip()
                kinds = dlg.chosen_kinds()
                _choice.update(path=path, kinds=kinds, new=True, done=True)
                _home["loop"].quit()

            def _on_open():
                path, _ = GgsFileDialog.getOpenFileName(
                    _home["win"], _i18n.tr("打开工程"), "",
                    _i18n.tr("GmaGIS 工程 (*.ggs);;所有文件 (*)"))
                if not path:
                    return
                _choice.update(path=path, new=False, done=True)
                _home["loop"].quit()

            def _on_recent(path):
                _choice.update(path=path, new=False, done=True)
                _home["loop"].quit()

            def _on_options():
                """主页阶段的选项对话框：无主窗口，改完落盘即生效（主题立即换肤）。"""
                from .ui.dialogs.settings import SettingsDialog
                dlg = SettingsDialog(_home["win"])
                if not dlg.exec():
                    return
                if not dlg.changed():
                    return
                _keys = set()
                try:
                    _keys = set(dlg.changed_keys() or ())
                except Exception:
                    _keys = set()
                for _k, _v in dlg._collect().items():
                    try:
                        _settings.set(_k, _v, persist=False)
                    except Exception:
                        exc_note("_on_options @ ggis/app.py")
                try:
                    _settings.save(commit_ephemeral=True)
                except Exception:
                    exc_note("_on_options @ ggis/app.py")
                # 主题立即应用到主页（语言/渲染等进主界面或重启后生效）
                if "theme" in _keys:
                    try:
                        _t = _settings.get("theme") or "dark"
                        icons.set_theme(_t != "light")
                        app.setStyleSheet(themes.qss(_t))
                        # 窗口字形图标颜色随主题重刷
                        _home["win"].title_bar.refresh_glyphs()
                    except Exception:
                        exc_note("_on_options theme @ ggis/app.py")

            from PySide6.QtCore import QEventLoop
            # splash 先隐藏：欢迎页是此时的前台交互，不与启动画面叠放
            if splash is not None:
                splash.hide()
                app.processEvents()
            hw = HomeWindow(on_new=_on_new, on_open=_on_open,
                            on_recent=_on_recent, on_options=_on_options)
            _home["win"] = hw
            _home["loop"] = QEventLoop()
            hw.closed.connect(_home["loop"].quit)
            hw.show()
            _home["loop"].exec()  # 阻塞：直到选完工程（quit）或用户关窗
            if _choice["done"]:
                _home_pick_path = _choice["path"]
                _home_pick_new = _choice["new"]
                _home_pick_kinds = _choice["kinds"]
            try:
                hw.close()
                hw.deleteLater()
            except Exception:
                _log.exception("silent exception closing home window")
            if not _choice["done"]:
                # 用户直接关掉欢迎页 = 放弃启动，退出程序
                return 0
        except Exception:
            _log.exception("silent exception in home page")
        # 选完工程 → 恢复启动画面：装载链各阶段（读取/建视图/装图层）
        # 会经 ctx.boot 推进进度（splash._STEP_PLAN 按实测耗时占比设定）
        if splash is not None:
            splash.show()
            app.processEvents()

    def _open_incoming_file(p):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: win.ctx.svc("projects").open_path(p))

    try:
        from . import ipc as _ipc
        _ipc.install(_open_incoming_file)
    except Exception:
        _log.exception("silent exception in main")

    # 视图装载必须在 show 之前完成：QOpenGLWidget 加入"已显示"的窗口会
    # 触发原生窗口销毁重建（界面出现→消失→出现）；在未显示窗口里创建则无
    # 此问题。装载链与打开工程完全一致（new_project / views.create /
    # open_path），只是时机提前——splash 期间完成装载，show 时界面即就绪。
    _to_open = [a.strip() for a in sys.argv[1:]
                if a.strip() and not a.strip().startswith("-")]
    if _home_pick_path and not _home_pick_new:
        _to_open.insert(0, _home_pick_path)
    _log.info("[启动] argv_files=%s to_open=%s",
              sys.argv[1:], _to_open)
    if _home_pick_new:
        # 欢迎页选的是新建工程；内存工程路径为空串，只看 _home_pick_new 标记。
        # 视图走与打开工程同一装载机制（先关现有工程的全部视图再按勾选建）。
        # 不吞异常：启动装载失败直接退出，不半装载硬撑。
        win.ctx.svc("projects").new_project(_home_pick_path)
        win.ctx.svc("views").apply_new_project_views(_home_pick_kinds)
    for _p in _to_open:
        win.ctx.svc("projects").open_path(_p)

    _vh = getattr(win, "view_host", None)
    _tabs = getattr(win, "view_tabs", None)
    _log.info("[启动] pre-show views=%s tabs=%d",
              [str(getattr(v, "view_id", "?")) for v in _vh.views()]
              if _vh is not None else [],
              _tabs.tabs.count() if _tabs is not None else -1)

    win.show()

    def _log_tabs_display():
        # 显示层取证：页签条数据已验证正确（tabs=2），若界面只见一个页签，
        # 这里输出条子几何/可见性/父级/每页签宽度，直接定位显示环节。
        try:
            _t = getattr(win, "view_tabs", None)
            if _t is None:
                _log.info("[显示] view_tabs 不存在")
                return
            _tb = getattr(_t, "tabs", None)
            _geo = _t.geometry()
            _pw = _t.parentWidget()
            _gp = _pw.parentWidget() if _pw is not None else None
            _log.info(
                "[显示] count=%s visible=%s strip=(%d,%d %dx%d) "
                "parent=%s gp=%s rects=%s",
                _tb.count() if _tb is not None else -1,
                _t.isVisible(),
                _geo.x(), _geo.y(), _geo.width(), _geo.height(),
                type(_pw).__name__ if _pw is not None else None,
                type(_gp).__name__ if _gp is not None else None,
                [(str(_tb.tabText(i)), int(_tb.tabRect(i).width()))
                 for i in range(_tb.count())] if _tb is not None else [])
        except Exception:
            _log.exception("[显示] 页签条显示状态记录失败")

    from PySide6.QtCore import QTimer
    QTimer.singleShot(800, _log_tabs_display)

    if splash is not None:
        try:
            splash.finish(win)
        except Exception:
            _log.exception("silent exception in main")
            try:
                splash.close()
            except Exception:
                _log.exception("silent exception in main")
        try:
            splash.deleteLater()
        except Exception:
            _log.exception("silent exception in main")
        splash = None

    try:
        from .exec import guard as _exec_guard
        _exec_guard.set_ui_mode(True)
    except Exception:
        _log.exception("silent exception in main")

    try:
        rc = app.exec()
    finally:
        shutdown_workers()
    return rc



_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_CONSOLE = logging.StreamHandler(sys.stderr)
_configured = False
_fault_fp = None


class _SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):

    def emit(self, record):
        try:
            if self.shouldRollover(record):
                self.doRollover()
            logging.FileHandler.emit(self, record)
        except Exception:
            self._force_fresh(record)

    def _force_fresh(self, record):
        try:
            try:
                if self.stream is not None:
                    self.stream.close()
            except Exception:
                pass
            self.stream = None
            try:
                if (os.path.exists(self.baseFilename)
                        and os.path.getsize(self.baseFilename) > 0):
                    shutil.copyfile(self.baseFilename,
                                    self.baseFilename + ".overflow")
            except Exception:
                pass
            self.stream = open(self.baseFilename, "w",
                               encoding=self.encoding or "utf-8")
            logging.StreamHandler.emit(self, record)
        except Exception:
            self.handleError(record)

_log_path_override = None
_log_path_resolved = False


def log_file():
    global _log_path_override, _log_path_resolved
    if not _log_path_resolved:
        _log_path_resolved = True
        try:
            from ggis.core.app import settings as _s
            p = _s.get("log_file")
            if p:
                _log_path_override = str(p)
        except Exception:
            _log.exception("silent exception in log_file")
    if _log_path_override:
        return _log_path_override
    return os.path.join(app_paths.log_dir(), "gmagis.log")


def set_log_file(path):
    global _log_path_override, _log_path_resolved
    path = str(path or "").strip()
    if not path:
        return
    _log_path_override = path
    _log_path_resolved = True
    try:
        root = logging.getLogger()
        for h in list(root.handlers):
            if getattr(h, "_is_gmagis_log", False):
                root.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    _log.exception("silent exception in set_log_file")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fh = _SafeRotatingFileHandler(
            path, maxBytes=2 << 20, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT, _DATEFMT))
        fh._is_gmagis_log = True
        root.addHandler(fh)
        _install_noise_filter([fh])
        get_logger().info("日志文件已切换到 %s", path)
    except Exception:
        _log.exception("silent exception in set_log_file")


def child_log_file():
    return os.path.join(app_paths.log_dir(), "gmagis_render.log")


def setup_child(level=None, console=True):
    global _configured
    path = ""
    try:
        setup(level=level, to_file=False, console=console)
        path = child_log_file()
        root = logging.getLogger()
        if not any(isinstance(h, logging.handlers.RotatingFileHandler)
                   and getattr(h, "baseFilename", "") == os.path.abspath(path)
                   for h in root.handlers):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fh = _SafeRotatingFileHandler(
                path, maxBytes=1 << 20, backupCount=2, encoding="utf-8")
            fh.setFormatter(logging.Formatter(_FMT, _DATEFMT))
            root.addHandler(fh)
        get_logger().info("渲染子进程日志就绪 pid=%s file=%s",
                          os.getpid(), path)
    except Exception:
        _log.exception("silent exception in setup_child")
        return ""
    return path


def crash_file():
    return os.path.join(app_paths.log_dir(), "gmagis_crash.txt")


def _enable_faulthandler():
    global _fault_fp
    if _fault_fp is not None:
        return
    try:
        import faulthandler
        path = crash_file()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _fault_fp = open(path, "a", encoding="utf-8")
        faulthandler.enable(file=_fault_fp, all_threads=True)
    except Exception:
        _log.exception("silent exception in _enable_faulthandler")
        _fault_fp = None


def get_logger(name=None):
    return logging.getLogger(name if name else "gmagis")


class _RepeatNoiseFilter(logging.Filter):

    RULES = (
        ("rasterio._err", logging.INFO, "PROJ: aea: Invalid latitude"),
    )

    def __init__(self):
        super().__init__()
        self._seen = set()

    def filter(self, record):
        try:
            if record.levelno > logging.INFO:
                return True
            name = str(getattr(record, "name", "") or "")
            msg = ""
            for _n, _lv, _key in self.RULES:
                if not name.startswith(_n):
                    continue
                if not msg:
                    msg = record.getMessage()
                if _key in msg:
                    k = (_n, _key)
                    if k in self._seen:
                        return False
                    self._seen.add(k)
                    return True
        except Exception:
            _log.exception("silent exception in filter")
            return True
        return True


_noise_installed = False


def _install_noise_filter(handlers):
    global _noise_installed
    if _noise_installed:
        return
    try:
        f = _RepeatNoiseFilter()
        for h in list(handlers or []):
            if not any(isinstance(x, _RepeatNoiseFilter) for x in h.filters):
                h.addFilter(f)
        _noise_installed = True
    except Exception:
        _log.exception("silent exception in _install_noise_filter")


def _excepthook(exc_type, exc, tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc, tb)
        return
    logging.getLogger("gmagis").critical(
        "未捕获异常", exc_info=(exc_type, exc, tb))


def setup(level=None, to_file=True, console=True, max_bytes=2 << 20,
          backups=3):
    global _configured
    root = logging.getLogger()
    if level is None:
        level = getattr(logging, os.environ.get("GMAGIS_LOG", "INFO").upper(),
                        logging.INFO)
    root.setLevel(level)
    _CONSOLE.setFormatter(logging.Formatter(_FMT, _DATEFMT))

    if console and _CONSOLE not in root.handlers:
        root.addHandler(_CONSOLE)

    path = ""
    if to_file:
        path = log_file()
        if not any(isinstance(h, logging.handlers.RotatingFileHandler)
                   and getattr(h, "baseFilename", "") == os.path.abspath(path)
                   for h in root.handlers):
            try:
                fh = _SafeRotatingFileHandler(
                    path, maxBytes=max_bytes, backupCount=backups,
                    encoding="utf-8")
                fh.setFormatter(logging.Formatter(_FMT, _DATEFMT))
                fh._is_gmagis_log = True
                root.addHandler(fh)
            except Exception as e:
                _CONSOLE.handle(logging.LogRecord(
                    "gmagis", logging.WARNING, __file__, 0,
                    "日志文件打不开（%s），只输出到控制台：%s",
                    (path, e), None))

    if not _configured:
        sys.excepthook = _excepthook
        _enable_faulthandler()
        logging.captureWarnings(True)
        _configured = True

    _install_noise_filter(root.handlers)

    get_logger().info("日志就绪 level=%s file=%s",
                      logging.getLevelName(level), path or "(无)")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
