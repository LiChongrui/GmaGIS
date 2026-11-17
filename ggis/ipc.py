# -*- coding: utf-8 -*-
from ggis.common.util.exc_report import exc_note

import ctypes
import ctypes.wintypes as wt

WM_COPYDATA = 0x004A
GMA_IPC_CLASS = "GmaGIS_IPC_Window"

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ("dwData", wt.LPARAM),
        ("cbData", wt.DWORD),
        ("lpData", ctypes.c_void_p),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HCURSOR),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
HWND_MESSAGE = ctypes.c_void_p(-3)

_KEEPALIVE = None


def install(on_files):
    return None
    global _KEEPALIVE
    if _KEEPALIVE is not None:
        return _KEEPALIVE[0]

    inst = ctypes.cast(_kernel32.GetModuleHandleW(None), wt.HINSTANCE)

    def _wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_COPYDATA:
            cds = ctypes.cast(lparam, ctypes.POINTER(COPYDATASTRUCT)).contents
            if cds.cbData and cds.lpData:
                try:
                    raw = ctypes.wstring_at(cds.lpData, cds.cbData // 2)
                except Exception:
                    exc_note("_wndproc @ ggis/ipc.py:78")
                    raw = ""
                text = raw.split("\x00", 1)[0]
                for line in text.split("\n"):
                    line = line.strip()
                    if line:
                        try:
                            on_files(line)
                        except Exception:
                            exc_note("_wndproc @ ggis/ipc.py:87")
                            pass
            return 1
        return _user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wndproc = WNDPROC(_wndproc)

    clazz = WNDCLASSEXW()
    clazz.cbSize = ctypes.sizeof(WNDCLASSEXW)
    clazz.lpfnWndProc = wndproc
    clazz.hInstance = inst
    clazz.lpszClassName = GMA_IPC_CLASS

    atom = _user32.RegisterClassExW(ctypes.byref(clazz))
    if not atom:
        if ctypes.GetLastError() != 1410:
            raise ctypes.WinError()

    hwnd = _user32.CreateWindowExW(
        0, GMA_IPC_CLASS, None, 0, 0, 0, 0, 0,
        HWND_MESSAGE, None, inst, None)
    if not hwnd:
        raise ctypes.WinError()

    _KEEPALIVE = (hwnd, wndproc, clazz)
    return hwnd
