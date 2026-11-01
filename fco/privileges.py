"""Read-only integrity checks. Never elevate or change Windows settings."""

import ctypes
from ctypes import wintypes


def integrity(pid=None):
    kernel = ctypes.windll.kernel32
    advapi = ctypes.windll.advapi32
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    advapi.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    advapi.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    advapi.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    advapi.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)
    process = kernel.OpenProcess(0x1000, False, pid) if pid else kernel.GetCurrentProcess()
    if not process:
        return None
    token = wintypes.HANDLE()
    try:
        if not advapi.OpenProcessToken(process, 8, ctypes.byref(token)):
            return None
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, 25, None, 0, ctypes.byref(size))
        data = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, 25, data, size, ctypes.byref(size)):
            return None
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        count = advapi.GetSidSubAuthorityCount(sid)[0]
        return advapi.GetSidSubAuthority(sid, count - 1)[0]
    finally:
        if token:
            kernel.CloseHandle(token)
        if pid:
            kernel.CloseHandle(process)


def input_error(game_level, tool_level):
    if game_level is not None and tool_level is not None and game_level > tool_level:
        return "FCO chạy quyền cao hơn tool. Đóng tool và chọn Run as administrator trước khi dùng chuột/phím tự động."
    return None
