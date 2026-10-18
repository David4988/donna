"""The only file that looks at the windows on your screen.

    visible_windows() -> {handle: title}
    front()           -> (handle, title) of the window in front

Read-only, deliberately: it lists windows and reads their titles, and it can
neither click nor type. open_app uses it to check that an app it launched
actually appeared, instead of assuming so.

Everything Windows-specific is imported inside the functions, so this module
imports fine on the Linux machine that runs the tests, where both functions
simply report an empty screen.
"""

import sys

IS_WINDOWS = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080  # floating palettes and tray helpers, not apps
DWMWA_CLOAKED = 14  # a Store app's window can exist while invisible

_api = None


def visible_windows():
    """Every top-level window a person could actually see, by handle."""
    if not IS_WINDOWS:
        return {}
    user32, dwmapi, w, ctypes, ENUMPROC = _windows_api()
    found = {}

    def visit(handle, _):
        if not user32.IsWindowVisible(handle):
            return True
        if user32.GetWindowLongW(handle, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        cloaked = w.DWORD()
        dwmapi.DwmGetWindowAttribute(handle, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value:
            return True
        title = _title(user32, ctypes, handle)
        if title:
            found[handle] = title
        return True

    user32.EnumWindows(ENUMPROC(visit), 0)
    return found


def front():
    """The window in front, and its title. (None, "") if there isn't one."""
    if not IS_WINDOWS:
        return None, ""
    user32, _, _, ctypes, _ = _windows_api()
    handle = user32.GetForegroundWindow()
    return (handle, _title(user32, ctypes, handle)) if handle else (None, "")


def _title(user32, ctypes, handle):
    length = user32.GetWindowTextLengthW(handle)
    if not length:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value


def _windows_api():
    """user32 and dwmapi with every argument type declared.

    Undeclared, ctypes passes a 64-bit window handle as a 32-bit int and it
    fails with "int too long to convert" -- measured, on this PC.
    """
    global _api
    if _api is None:
        import ctypes
        import ctypes.wintypes as w

        user32 = ctypes.WinDLL("user32")
        dwmapi = ctypes.WinDLL("dwmapi")
        ENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        user32.EnumWindows.argtypes = [ENUMPROC, w.LPARAM]
        user32.IsWindowVisible.argtypes = [w.HWND]
        user32.GetWindowLongW.argtypes = [w.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.GetWindowTextLengthW.argtypes = [w.HWND]
        user32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
        user32.GetForegroundWindow.restype = w.HWND
        dwmapi.DwmGetWindowAttribute.argtypes = [w.HWND, w.DWORD, ctypes.c_void_p, w.DWORD]
        _api = (user32, dwmapi, w, ctypes, ENUMPROC)
    return _api
