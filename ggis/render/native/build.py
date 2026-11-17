# -*- coding: utf-8 -*-

from __future__ import annotations
from ggis.common.util.exc_report import exc_note

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MODULES = ("ggs_accel", "ggs_prims")
SOURCE = os.path.join(HERE, "ggs_accel.c")
TARGET = os.path.join(HERE, "ggs_accel.dll")


def source_of(name):
    return os.path.join(HERE, name + ".c")


def target_of(name):
    return os.path.join(HERE, name + ".dll")

_VS_ROOTS = (
    r"C:\Program Files\Microsoft Visual Studio\18\Community",
    r"C:\Program Files\Microsoft Visual Studio\2022\Community",
    r"C:\Program Files\Microsoft Visual Studio\2022\Professional",
    r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise",
    r"C:\Program Files\Microsoft Visual Studio\2022\BuildTools",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools",
)

_SDK_ROOTS = (
    r"C:\Program Files (x86)\Windows Kits\10",
    r"C:\Program Files\Windows Kits\10",
)


def _ver_key(s):
    parts = []
    for p in os.path.basename(s).split("."):
        try:
            parts.append(int(p))
        except ValueError:
            exc_note("_ver_key @ ggis/render/native/build.py:74")
            parts.append(-1)
    return parts


def find_toolchain():
    cl = None
    msvc_root = None
    for root in _VS_ROOTS:
        pat = os.path.join(root, "VC", "Tools", "MSVC", "*",
                           "bin", "Hostx64", "x64", "cl.exe")
        hits = sorted(glob.glob(pat), key=lambda p: _ver_key(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(p))))))
        if hits:
            cl = hits[-1]
            msvc_root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(cl))))
            break
    if cl is None:
        return None

    inc, lib = [], []
    inc.append(os.path.join(msvc_root, "include"))
    lib.append(os.path.join(msvc_root, "lib", "x64"))
    lib.append(os.path.join(msvc_root, "lib", "x64", "store"))

    sdk = None
    for root in _SDK_ROOTS:
        hd = os.path.join(root, "Include")
        if os.path.isdir(hd):
            vers = sorted([d for d in glob.glob(os.path.join(hd, "*"))
                           if os.path.isdir(d)], key=_ver_key)
            if vers:
                sdk = (root, os.path.basename(vers[-1]))
                break
    if sdk is None:
        return None
    sdk_root, sdk_ver = sdk
    for part in ("ucrt", "um", "shared", "winrt", "cppwinrt"):
        p = os.path.join(sdk_root, "Include", sdk_ver, part)
        if os.path.isdir(p):
            inc.append(p)
    for part in ("ucrt", "um"):
        p = os.path.join(sdk_root, "Lib", sdk_ver, part, "x64")
        if os.path.isdir(p):
            lib.append(p)

    return {"cl": cl, "include": inc, "lib": lib,
            "sdk": "%s / %s" % (sdk_root, sdk_ver),
            "msvc": msvc_root}


def can_build():
    return find_toolchain() is not None


def _decode(raw):
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            exc_note("_decode @ ggis/render/native/build.py:141")
            continue
    return repr(raw)


def build(name="ggs_accel", verbose=True, cxx=False, avx2=False):
    src = source_of(name)
    tgt = target_of(name)
    if not os.path.isfile(src):
        return False, "找不到源文件 %s" % src
    tc = find_toolchain()
    if tc is None:
        return False, ("未找到 MSVC C++ 工具链或 Windows SDK。"
                       "纯 Python 回退可用，功能不受影响。")
    obj = os.path.join(HERE, name + ".obj")
    if os.path.isfile(tgt):
        try:
            os.remove(tgt)
        except OSError as e:
            if verbose:
                print("提示：删除旧 %s 失败（%s），交给 cl 直接覆盖"
                      % (os.path.basename(tgt), e))
    env = dict(os.environ)
    env["PATH"] = (os.path.dirname(tc["cl"]) + os.pathsep
                   + env.get("PATH", ""))
    env["INCLUDE"] = os.pathsep.join(tc["include"])
    env["LIB"] = os.pathsep.join(tc["lib"])
    env["VSCMD_SKIP_SENDTELEMETRY"] = "1"

    cmd = [tc["cl"], "/nologo", "/O2", "/W3", "/LD", "/utf-8"]
    if cxx:
        cmd += ["/TP", "/EHsc"]
    if avx2:
        cmd += ["/arch:AVX2"]
    cmd += ["/Fe:" + tgt, "/Fo:" + obj, src]
    if verbose:
        print("cl  : %s" % tc["cl"])
        print("sdk : %s" % tc["sdk"])
        print("out : %s" % tgt)
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=600, env=env)
    except Exception as e:
        exc_note("build @ ggis/render/native/build.py:195")
        return False, "无法启动 cl.exe：%r" % (e,)
    out = _decode((r.stdout or b"") + (r.stderr or b"")).strip()
    ok = (r.returncode == 0) and os.path.isfile(tgt)
    for ext in (".obj", ".exp", ".lib", ".pdb"):
        p = os.path.join(HERE, name + ext)
        try:
            if os.path.isfile(p):
                os.remove(p)
        except Exception:
            exc_note("build @ ggis/render/native/build.py:204")
            pass
    if verbose:
        tail = "\n".join(out.splitlines()[-14:])
        print(tail if tail else "(no output)")
    if not ok:
        return False, "编译失败（rc=%s）" % r.returncode
    return True, "已生成 %s（%.1f KB）" % (
        tgt, os.path.getsize(tgt) / 1024.0)


def clean():
    n = 0
    for mod in MODULES:
        for ext in (".dll", ".obj", ".exp", ".lib", ".pdb"):
            p = os.path.join(HERE, mod + ext)
            try:
                if os.path.isfile(p):
                    os.remove(p)
                    n += 1
            except Exception:
                exc_note("clean @ ggis/render/native/build.py:224")
                pass
    return n


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--clean" in argv:
        print("已删除 %d 个产物" % clean())
        return 0
    if "--check" in argv:
        tc = find_toolchain()
        if tc:
            print("cl  : %s" % tc["cl"])
            print("sdk : %s" % tc["sdk"])
            print("可构建: 是")
            return 0
        print("可构建: 否（纯 Python 回退可用）")
        return 1
    ok_all = True
    for mod in MODULES:
        ok, msg = build(mod, cxx=("--cxx" in argv), avx2=("--avx2" in argv))
        print("[%s] %s%s" % (mod, "OK   " if ok else "FAIL ", msg))
        ok_all = ok_all and ok
    ok = ok_all
    print(("OK   " if ok else "FAIL ") + msg)
    if not ok:
        print("提示：不构建也不影响功能 —— ggis/render/native/accel.py 会自动"
              "回退到等效的纯 Python 实现。")
        return 1
    try:
        APP = os.path.dirname(os.path.dirname(HERE))
        if APP not in sys.path:
            sys.path.insert(0, APP)
        from ggis.render.native import accel, primitives
        accel.reload()
        primitives.reload()
        print("自证 accel：", accel.describe())
        print("自证 primitives：", primitives.describe())
        for nm, mod in (("accel", accel), ("primitives", primitives)):
            v = getattr(mod, "verify", None)
            if v is not None:
                print("交叉验证 %s：%s" % (nm, v()))
    except Exception as e:
        print("自证失败（DLL 可能不可用）：%r" % (e,))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
