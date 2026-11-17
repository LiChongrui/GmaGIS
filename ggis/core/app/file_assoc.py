# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note
import os
import sys
import logging
_log = logging.getLogger("gmagis")

_PROG_ID = "GmaGIS.ggs"
_FILE_KIND = "GmaGIS 工程文件"
# Win11“打开方式”机制自生成的 ProgID 名（代码从未写过）：用户曾通过
# 打开方式选择 GmaGIS.exe，系统把选择记进 FileExts\.ggs\UserChoiceLatest
# 并自生成 "GmaGISFile.ggs" 这个 ProgID 名——但定义无人写入，shell 解析
# 到空 ProgID 后退回推荐应用（GmaGIS.exe）的默认图标（组 101=LOGO），
# Classes 里的 GmaGIS.ggs 根本轮不到（2026-11-17 实测踩坑）。 associate
# 时把两个 ProgID 都定义齐，shell 走哪条路都拿得到工程图标。
_WIN_OPENWITH_PROG_ID = "GmaGISFile.ggs"
_PROG_IDS = (_PROG_ID, _WIN_OPENWITH_PROG_ID)

_OLD_EXT_KEY = r"Software\Classes\.ggis"
_OLD_PROG_ID = "GmaGIS.ggis"


def _project_root():
    try:
        from ggis.app_paths import app_root
        return app_root()
    except Exception:
        _log.exception("silent exception in _project_root")
        return os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))


def _launcher_exe():
    exe = os.path.join(_project_root(), "GmaGIS.exe")
    return exe if os.path.isfile(exe) else None


def launcher_command():
    exe = _launcher_exe()
    if exe:
        return '"%s" "%%1"' % exe
    script = os.path.join(_project_root(), "apps", "ggis.py")
    return '"%s" "%s" "%%1"' % (sys.executable, script)


def is_ggs_associated():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Classes\.ggs") as k:
            return str(winreg.QueryValueEx(k, "")[0]) == _PROG_ID
    except Exception:
        _log.exception("silent exception in is_ggs_associated")
        return False


def _cleanup_legacy_keys(winreg):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            _OLD_EXT_KEY, access=winreg.KEY_READ) as k:
            cur = str(winreg.QueryValueEx(k, "")[0])
        if cur == _OLD_PROG_ID:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _OLD_EXT_KEY)
            _delete_key_tree(winreg.HKEY_CURRENT_USER,
                             r"Software\Classes\%s" % _OLD_PROG_ID)
    except Exception:
        _log.exception("silent exception in _cleanup_legacy_keys")


def associate_ggs(enable):
    if sys.platform != "win32":
        return False, "文件关联仅支持 Windows 系统。"
    import winreg
    try:
        if enable:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  r"Software\Classes\.ggs") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _PROG_ID)
            # 每个候选 ProgID 都定义齐（描述 + DefaultIcon + open 命令）：
            # Classes 默认（GmaGIS.ggs）+ Win11 打开方式登记名
            # （GmaGISFile.ggs，UserChoiceLatest 可能指向它）。
            for _pid in _PROG_IDS:
                with winreg.CreateKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Classes\%s" % _pid) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _FILE_KIND)
                # DefaultIcon 引用构建设计（gmagis_launcher.rc 注释）：
                # 工程图标已作为资源组 102 嵌入 GmaGIS.exe（build.bat 每次
                # 构建先经 mk_project_icon.py 重画再编入），故统一引用
                # "EXE,-102"——自包含、免外部文件路径依赖（路径随构建目录
                # 变化 / ico 缺失会静默退回 EXE 默认图标即 LOGO）。
                # EXE 不存在（纯源码运行）才退外部 ico 路径。
                _exe = _launcher_exe()
                if _exe:
                    _icon_ref = "%s,-102" % _exe
                else:
                    _proj_ico = os.path.join(_project_root(), "resources",
                                             "icons", "project.ico")
                    _icon_ref = ('"%s",0' % _proj_ico
                                 if os.path.isfile(_proj_ico)
                                 else "%s,0" % sys.executable)
                with winreg.CreateKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Classes\%s\DefaultIcon" % _pid) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _icon_ref)
                with winreg.CreateKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Classes\%s\shell\open\command" % _pid) as k:
                    winreg.SetValueEx(k, "", 0, winreg.REG_SZ,
                                      launcher_command())
            _cleanup_legacy_keys(winreg)
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                    r"Software\Classes\.ggs",
                                    access=winreg.KEY_READ) as k:
                    cur = str(winreg.QueryValueEx(k, "")[0])
                if cur == _PROG_ID:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,
                                     r"Software\Classes\.ggs")
            except Exception:
                _log.exception("silent exception in associate_ggs")
            for _pid in _PROG_IDS:
                _delete_key_tree(winreg.HKEY_CURRENT_USER,
                                 r"Software\Classes\%s" % _pid)
            _cleanup_legacy_keys(winreg)
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            _log.exception("silent exception in associate_ggs")
        return True, ("已关联 .ggs 工程文件"
                      if enable else "已取消 .ggs 文件关联")
    except Exception as e:
        _log.exception("silent exception in associate_ggs")
        return False, "文件关联失败：%s" % e


def _delete_key_tree(hive, key):
    import winreg
    try:
        hk = winreg.OpenKey(hive, key, access=winreg.KEY_ALL_ACCESS)
    except OSError:
        exc_note("_delete_key_tree @ ggis/core/app/file_assoc.py:181")
        return
    while True:
        try:
            sub = winreg.EnumKey(hk, 0)
        except OSError:
            exc_note("_delete_key_tree @ ggis/core/app/file_assoc.py:187")
            break
        _delete_key_tree(hive, "%s\\%s" % (key, sub))
    try:
        winreg.CloseKey(hk)
    except OSError:
        exc_note("_delete_key_tree @ ggis/core/app/file_assoc.py:192")
        pass
    try:
        winreg.DeleteKey(hive, key)
    except OSError:
        exc_note("_delete_key_tree @ ggis/core/app/file_assoc.py:196")
        pass
