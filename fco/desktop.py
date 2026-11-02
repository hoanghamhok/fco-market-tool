"""Normal Windows capture/click only. No memory hooks or game process modification."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from PIL import ImageGrab
import pyautogui
from .privileges import integrity, input_error
from .bounds import visible_rect


class Stopped(RuntimeError):
    pass


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        pass


@dataclass
class Frame:
    image: object
    origin: tuple


class Desktop:
    def __init__(self, stop):
        self.stop = stop
        self.api = ctypes.windll.user32
        try:
            self.dwm = ctypes.windll.dwmapi
            self.dwm.DwmGetWindowAttribute.argtypes = [
                wintypes.HWND,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self.dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        except (OSError, AttributeError):
            self.dwm = None
        self.api.GetForegroundWindow.restype = wintypes.HWND
        self.api.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.api.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.api.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.api.IsWindowVisible.argtypes = [wintypes.HWND]
        self.api.IsIconic.argtypes = [wintypes.HWND]
        found = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _):
            title = ctypes.create_unicode_buffer(256)
            self.api.GetWindowTextW(hwnd, title, 256)
            if title.value.strip().upper() == "FC ONLINE" and self.api.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        callback = callback_type(visit)
        self.api.EnumWindows(callback, 0)
        if len(found) != 1:
            raise RuntimeError("Hãy mở đúng một cửa sổ FC ONLINE trước")
        self.hwnd = found[0]
        self.api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        pid = wintypes.DWORD()
        self.api.GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        self.access_error = input_error(integrity(pid.value), integrity())
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.03

    def focus(self):
        if self.api.IsIconic(self.hwnd):
            self.api.ShowWindow(self.hwnd, 9)
        self.api.SetForegroundWindow(self.hwnd)
        return self.api.GetForegroundWindow() == self.hwnd

    def guard(self):
        if self.stop.is_set() or self.api.GetAsyncKeyState(0x77) & 0x8000:
            self.stop.set()
            raise Stopped("Đã dừng")
        if self.api.GetForegroundWindow() != self.hwnd or self.api.IsIconic(self.hwnd):
            raise Stopped("FCO không còn ở phía trước; đã dừng thao tác")
        try:
            rect = visible_rect(self.api, self.hwnd, self.dwm)
        except ValueError as error:
            raise Stopped(str(error)) from error
        if rect.right <= rect.left or rect.bottom <= rect.top:
            raise Stopped("Cửa sổ game không hợp lệ")
        return rect

    def capture(self):
        rect = self.guard()
        image = ImageGrab.grab(
            bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True
        ).convert("RGB")
        again = self.guard()
        if (again.left, again.top, again.right, again.bottom) != (
            rect.left,
            rect.top,
            rect.right,
            rect.bottom,
        ):
            raise Stopped("Cửa sổ vừa di chuyển; hãy nhận diện lại")
        return Frame(image, (rect.left, rect.top))

    def scan(self, reader, bound=None, exact=False):
        frame = self.capture()
        snapshot = reader.read(frame.image, bound, exact)
        snapshot.origin = frame.origin
        return snapshot

    def click(self, snapshot, key):
        self.require_input()
        rect = self.guard()
        if (rect.left, rect.top) != snapshot.origin or (
            rect.right - rect.left,
            rect.bottom - rect.top,
        ) != snapshot.frame.size:
            raise Stopped("Vị trí/kích thước cửa sổ đã thay đổi; chưa bấm")
        x, y = snapshot.region(key).center
        if not (0 < x < snapshot.frame.width and 0 < y < snapshot.frame.height):
            raise Stopped("Nút nằm ngoài cửa sổ")
        pyautogui.click(rect.left + x, rect.top + y, _pause=False)
        self.guard()

    def require_input(self):
        if self.access_error:
            raise Stopped(self.access_error)

    def escape(self):
        self.require_input()
        self.guard()
        pyautogui.keyDown("esc", _pause=False)
        try:
            self.stop.wait(0.04)
        finally:
            pyautogui.keyUp("esc", _pause=False)
        self.guard()

    def frame_point(self, frame, x, y):
        rect = self.guard()
        if (rect.left, rect.top) != frame.origin or (
            rect.right - rect.left,
            rect.bottom - rect.top,
        ) != frame.image.size:
            raise Stopped("Bảng TTCN vừa di chuyển; chưa bấm")
        if not (0 < x < frame.image.width and 0 < y < frame.image.height):
            raise Stopped("Điểm nằm ngoài bảng")
        return rect.left + x, rect.top + y

    def move_point(self, frame, x, y):
        self.require_input()
        pyautogui.moveTo(*self.frame_point(frame, x, y), _pause=False)
        self.guard()

    def click_point(self, frame, x, y):
        self.require_input()
        pyautogui.click(*self.frame_point(frame, x, y), _pause=False)
        self.guard()

    def wait(self, seconds):
        if self.stop.wait(seconds):
            raise Stopped("Đã dừng")
        self.guard()
