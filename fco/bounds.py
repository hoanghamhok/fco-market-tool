"""Visible physical window bounds, excluding Windows' invisible resize border."""

import ctypes
from ctypes import wintypes


def visible_rect(api, hwnd, dwm=None):
    fallback = wintypes.RECT()
    if not api.GetWindowRect(hwnd, ctypes.byref(fallback)):
        raise ValueError("Không lấy được cửa sổ game")
    if dwm is not None:
        visible = wintypes.RECT()
        try:
            result = dwm.DwmGetWindowAttribute(
                hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible)
            )
            if result == 0 and visible.right > visible.left and visible.bottom > visible.top:
                return visible
        except (OSError, AttributeError):
            pass
    return fallback
