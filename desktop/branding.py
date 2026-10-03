"""Original CLI mascot rectangle for the UI and stable Windows app identity."""
MASCOT_RECT = (130, 100, 250, 250)

# Stable across upgrades, and shared with the Windows Start menu/Desktop links.
WINDOWS_APP_ID = "ChaosTic.ChaosticTool.Desktop"


def configure_windows_identity():
    """Identify the GUI to Explorer before Qt creates any native window."""
    import sys
    if sys.platform != 'win32':
        return
    import ctypes
    shell = ctypes.WinDLL('shell32')
    configure = shell.SetCurrentProcessExplicitAppUserModelID
    configure.argtypes = [ctypes.c_wchar_p]
    configure.restype = ctypes.c_long
    result = configure(WINDOWS_APP_ID)
    if result:
        raise OSError(f'Cannot set Windows taskbar identity: HRESULT {result & 0xffffffff:#x}')


def current_windows_identity():
    """Read the real process identity for packaged Windows regression checks."""
    import ctypes
    shell = ctypes.WinDLL('shell32')
    read = shell.GetCurrentProcessExplicitAppUserModelID
    read.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    read.restype = ctypes.c_long
    pointer = ctypes.c_void_p()
    result = read(ctypes.byref(pointer))
    if result:
        raise OSError(f'Cannot read Windows taskbar identity: HRESULT {result & 0xffffffff:#x}')
    try:
        return ctypes.wstring_at(pointer)
    finally:
        release = ctypes.WinDLL('ole32').CoTaskMemFree
        release.argtypes = [ctypes.c_void_p]
        release.restype = None
        release(pointer)
