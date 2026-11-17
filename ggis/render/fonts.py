# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import os

from PySide6.QtCore import QPointF
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QPainter,
                           QPdfWriter)

__all__ = [
    "font_dirs", "candidates", "register_file", "probe_family",
    "print_family", "print_font", "is_embedded", "status", "reset",
]

_ONCE = {"family": None, "probed": {}}
_FALLBACK = ""

_WIN = os.environ.get("WINDIR") or r"C:\Windows"
_SYS_CANDIDATES = (
    (os.path.join(_WIN, "Fonts", "msyh.ttc"), "微软雅黑"),
    (os.path.join(_WIN, "Fonts", "Deng.ttf"), "等线"),
    (os.path.join(_WIN, "Fonts", "simhei.ttf"), "黑体"),
    (os.path.join(_WIN, "Fonts", "simsun.ttc"), "宋体"),
    (os.path.join(_WIN, "Fonts", "msjh.ttc"), "微软正黑"),
    (os.path.join(_WIN, "Fonts", "simkai.ttf"), "楷体"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
     "Noto Sans CJK"),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", "文泉驿正黑"),
    ("/System/Library/Fonts/PingFang.ttc", "苹方"),
    (os.path.join(_WIN, "Fonts", "segoeui.ttf"), "Segoe UI"),
    (os.path.join(_WIN, "Fonts", "arial.ttf"), "Arial"),
    (os.path.join(_WIN, "Fonts", "DejaVuSans.ttf"), "DejaVu Sans"),
)

_FALLBACK_DIRS = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/Library/Fonts"),
    "/Library/Fonts",
)


def _project_font_dirs():
    out = []
    try:
        from ..app_paths import resource_path
    except ImportError:
        exc_note("_project_font_dirs @ ggis/render/fonts.py:94")
        resource_path = None
    if resource_path is not None:
        out.append(resource_path("fonts"))
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out.append(os.path.join(os.path.dirname(here), "resources", "fonts"))
    seen, uniq = set(), []
    for d in out:
        d = os.path.abspath(d)
        if d not in seen:
            seen.add(d)
            uniq.append(d)
    return uniq


def font_dirs():
    return _project_font_dirs() + [d for d in _FALLBACK_DIRS
                                   if os.path.isdir(d)]


def _bundled_files():
    out = []
    for d in _project_font_dirs():
        if not os.path.isdir(d):
            continue
        try:
            names = sorted(os.listdir(d))
        except Exception:
            exc_note("_bundled_files @ ggis/render/fonts.py:121")
            continue
        for n in names:
            if os.path.splitext(n)[1].lower() in (".ttf", ".otf", ".ttc",
                                                  ".otc"):
                out.append(os.path.join(d, n))
    return out


def candidates():
    out = [(p, "随包字体") for p in _bundled_files()]
    seen = set(os.path.normcase(p) for p, _ in out)
    for p, label in _SYS_CANDIDATES:
        if not p or not os.path.isfile(p):
            continue
        key = os.path.normcase(p)
        if key in seen:
            continue
        seen.add(key)
        out.append((p, label))
    return out


def register_file(path):
    p = str(path or "")
    if not p or not os.path.isfile(p):
        return ""
    try:
        fid = QFontDatabase.addApplicationFont(p)
    except Exception:
        exc_note("register_file @ ggis/render/fonts.py:155")
        return ""
    if fid is None or int(fid) < 0:
        return ""
    try:
        fams = QFontDatabase.applicationFontFamilies(int(fid)) or []
    except Exception:
        exc_note("register_file @ ggis/render/fonts.py:161")
        return ""
    return str(fams[0]) if fams else ""


def probe_family(family):
    key = str(family or "")
    hit = _ONCE["probed"].get(key)
    if hit is not None:
        return hit
    ok = False
    path = ""
    try:
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".pdf", prefix="ggs_fontprobe_")
        os.close(fd)
        w = QPdfWriter(path)
        w.setResolution(72)
        f = QFont(family) if family else QFont()
        f.setPointSizeF(12.0)
        p = QPainter(w)
        p.setFont(f)
        p.setPen(QColor("#000000"))
        p.drawText(QPointF(20, 40), "Ag文")
        p.end()
        raw = open(path, "rb").read()
        ok = (b"/Type /Font" in raw or b"/Type/Font" in raw)
    except Exception:
        exc_note("probe_family @ ggis/render/fonts.py:198")
        ok = False
    finally:
        if path:
            try:
                os.remove(path)
            except Exception:
                exc_note("probe_family @ ggis/render/fonts.py:204")
                pass
    _ONCE["probed"][key] = ok
    return ok


def print_family(preferred=""):
    key = str(preferred or "")
    if key:
        fam = register_file(key) if os.path.isfile(key) else key
        if fam and probe_family(fam):
            _ONCE["family"] = fam
            return fam
    elif _ONCE["family"] is not None:
        return _ONCE["family"]

    for path, _label in candidates():
        fam = register_file(path)
        if fam and probe_family(fam):
            _ONCE["family"] = fam
            return fam
    _ONCE["family"] = _FALLBACK
    return _FALLBACK


def print_font(size_pt=10.0, bold=False, italic=False, family=""):
    fam = family or print_family()
    f = QFont(fam) if fam else QFont()
    f.setPointSizeF(max(0.5, float(size_pt)))
    f.setBold(bool(bold))
    f.setItalic(bool(italic))
    return f


def is_embedded(family=""):
    fam = family or print_family()
    return probe_family(fam) if fam else False


def status():
    fam = print_family()
    return {
        "family": fam,
        "embedded": bool(fam) and is_embedded(fam),
        "bundled": [p for p, lab in candidates() if lab == "随包字体"],
        "candidates": [p for p, _ in candidates()],
    }


def reset():
    _ONCE["family"] = None
    _ONCE["probed"].clear()
