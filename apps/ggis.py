import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == '__main__':
    if os.environ.get("GGIS_PROBE"):
        import faulthandler
        faulthandler.dump_traceback_later(20, repeat=True, file=sys.stderr)

        def _max_test():
            import ctypes
            import time as _time

            user32 = ctypes.windll.user32
            MY_PID = os.getpid()
            _time.sleep(float(os.environ.get("GGIS_PROBE_DELAY", "9.0")))

            def _find_win():
                out = []

                @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                    ctypes.c_void_p)
                def cb(hwnd, _l):
                    if user32.IsWindowVisible(hwnd):
                        wpid = ctypes.c_ulong()
                        user32.GetWindowThreadProcessId(
                            hwnd, ctypes.byref(wpid))
                        if int(wpid.value) == MY_PID:
                            buf = ctypes.create_unicode_buffer(128)
                            user32.GetWindowTextW(hwnd, buf, 128)
                            if buf.value:
                                out.append(hwnd)
                    return True

                user32.EnumWindows(cb, None)
                return out[0] if out else None

            hwnd = _find_win()
            if not hwnd:
                print("[MAXTEST] no window", flush=True)
                os._exit(3)
            SMTO = 0x0002
            for rnd in range(3):
                user32.ShowWindow(hwnd, 3)
                _time.sleep(2.5)
                res = ctypes.c_ulong()
                ok1 = bool(user32.SendMessageTimeoutW(
                    hwnd, 0, 0, 0, SMTO, 2500, ctypes.byref(res)))
                user32.ShowWindow(hwnd, 9)
                _time.sleep(2.5)
                ok2 = bool(user32.SendMessageTimeoutW(
                    hwnd, 0, 0, 0, SMTO, 2500, ctypes.byref(res)))
                print("[MAXTEST] round%d max=%s restore=%s"
                      % (rnd, ok1, ok2), flush=True)
                if not (ok1 and ok2):
                    print("[MAXTEST] FROZE", flush=True)
                    try:
                        k32 = ctypes.windll.kernel32
                        h = k32.OpenThread(0x1FFFFF, False, 0)
                        hproc = k32.GetCurrentProcess()
                        ft1 = (ctypes.c_ulonglong(), ctypes.c_ulonglong())
                        kt1 = ctypes.c_ulonglong()
                        ut1 = ctypes.c_ulonglong()
                        k32.GetProcessTimes(hproc, ctypes.byref(ft1[0]),
                                            ctypes.byref(ft1[1]),
                                            ctypes.byref(kt1),
                                            ctypes.byref(ut1))
                        for _i in range(4):
                            _time.sleep(1.0)
                            kt2 = ctypes.c_ulonglong()
                            ut2 = ctypes.c_ulonglong()
                            k32.GetProcessTimes(hproc, ctypes.byref(ft1[0]),
                                                ctypes.byref(ft1[1]),
                                                ctypes.byref(kt2),
                                                ctypes.byref(ut2))
                            d = (ut2.value - ut1.value) / 1e7
                            print("[CPU] +%.0f%% of one core"
                                  % (d * 100.0), flush=True)
                            kt1, ut1 = kt2, ut2
                    except Exception as _e:
                        print("[CPU] fail %r" % _e, flush=True)
                    _time.sleep(16.0)
                    break
            _time.sleep(2.0)
            os._exit(0)

        import threading
        threading.Thread(target=_max_test, daemon=True).start()

    from ggis.app import main
    raise SystemExit(main())
