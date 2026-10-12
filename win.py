"""The few Windows calls Lorekeeper needs: the window in front, its exe and title, and the monitors."""
import ctypes, sys

if sys.platform == 'win32':
    from ctypes import wintypes as W
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = W.HWND
    user32.GetWindowThreadProcessId.argtypes = [W.HWND, ctypes.POINTER(W.DWORD)]
    user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
    user32.GetWindowTextLengthW.argtypes = [W.HWND]
    kernel32.OpenProcess.restype = W.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD)]
    kernel32.CloseHandle.argtypes = [W.HANDLE]


def exe_of(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION: works on most elevated games too
    if not h:
        return ''
    try:
        buf, n = ctypes.create_unicode_buffer(1024), W.DWORD(1024)
        return buf.value if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
    finally:
        kernel32.CloseHandle(h)


def front():
    """(exe path, window title) of the window in front, ('', '') if none."""
    if sys.platform != 'win32':
        return '', ''
    h = user32.GetForegroundWindow()
    if not h:
        return '', ''
    pid = W.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    buf = ctypes.create_unicode_buffer(user32.GetWindowTextLengthW(h) + 1)
    user32.GetWindowTextW(h, buf, len(buf))
    return exe_of(pid.value), buf.value


def monitors():
    """[(x, y, w, h, primary)] for each display."""
    out = []
    if sys.platform != 'win32':
        return out

    class MI(ctypes.Structure):
        _fields_ = [('cbSize', W.DWORD), ('rcMonitor', W.RECT), ('rcWork', W.RECT), ('dwFlags', W.DWORD)]

    def each(hmon, _hdc, _rect, _data):
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
        r = mi.rcWork
        out.append((r.left, r.top, r.right - r.left, r.bottom - r.top, bool(mi.dwFlags & 1)))
        return True
    proc = ctypes.WINFUNCTYPE(ctypes.c_int, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)(each)
    user32.EnumDisplayMonitors(None, None, proc, 0)
    return out
