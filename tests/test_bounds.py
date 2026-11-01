import ctypes
from ctypes import wintypes
from types import SimpleNamespace
import unittest
import threading
from unittest.mock import patch
from PIL import Image, ImageOps
from fco.paths import RESOURCE_ROOT
from fco.bounds import visible_rect
from fco.refresh import ParentReader
from fco.ocr import OCR
from fco.desktop import Desktop


def fill(pointer, values):
    rect = ctypes.cast(pointer, ctypes.POINTER(wintypes.RECT)).contents
    rect.left, rect.top, rect.right, rect.bottom = values


class BoundsTests(unittest.TestCase):
    def api(self, rect):
        def get(hwnd, pointer):
            fill(pointer, rect)
            return 1

        return SimpleNamespace(GetWindowRect=get)

    def dwm(self, rect, result=0):
        def get(hwnd, attribute, pointer, size):
            self.assertEqual(attribute, 9)
            fill(pointer, rect)
            return result

        return SimpleNamespace(DwmGetWindowAttribute=get)

    def values(self, rect):
        return rect.left, rect.top, rect.right, rect.bottom

    def test_actual_maximized_invisible_border_is_excluded(self):
        api = self.api((-8, -8, 1928, 1040))
        dwm = self.dwm((0, 0, 1920, 1032))
        self.assertEqual(self.values(visible_rect(api, 1, dwm)), (0, 0, 1920, 1032))

    def test_moved_window_and_negative_monitor_coordinates(self):
        api = self.api((-1508, 92, -212, 838))
        dwm = self.dwm((-1500, 100, -220, 830))
        self.assertEqual(self.values(visible_rect(api, 1, dwm)), (-1500, 100, -220, 830))

    def test_failed_or_invalid_dwm_uses_win32_fallback(self):
        api = self.api((30, 40, 1030, 740))
        for dwm in [None, self.dwm((0, 0, 0, 0)), self.dwm((0, 0, 1920, 1080), -1)]:
            self.assertEqual(self.values(visible_rect(api, 1, dwm)), (30, 40, 1030, 740))

    def test_real_parent_reproduces_border_failure_and_corrected_crop(self):
        ocr = OCR()
        try:
            parent = ParentReader(ocr)
            reference = Image.open(
                RESOURCE_ROOT / "assets/fixtures/sample-orders-3.2.2.png"
            ).convert("RGB")
            raw = ImageOps.expand(reference, border=8, fill="black")
            self.assertEqual(raw.size, (1936, 1048))
            self.assertFalse(parent.orders_selected(raw))
            self.assertLessEqual(parent.last_report["underline_fraction"], 0.1)
            corrected = raw.crop((8, 8, 1928, 1040))
            self.assertTrue(parent.orders_selected(corrected))
        finally:
            ocr.close()

    def test_capture_and_click_use_the_same_visible_origin(self):
        desktop = Desktop.__new__(Desktop)
        desktop.stop = threading.Event()
        desktop.hwnd = 1
        desktop.access_error = None
        desktop.api = self.api((-8, -8, 1928, 1040))
        desktop.dwm = self.dwm((0, 0, 1920, 1032))
        desktop.api.GetAsyncKeyState = lambda _: 0
        desktop.api.GetForegroundWindow = lambda: 1
        desktop.api.IsIconic = lambda _: False
        image = Image.open(RESOURCE_ROOT / "assets/fixtures/sample-orders-3.2.2.png").convert("RGB")
        with patch("fco.desktop.ImageGrab.grab", return_value=image) as grab:
            frame = desktop.capture()
        grab.assert_called_once_with(bbox=(0, 0, 1920, 1032), all_screens=True)
        self.assertEqual(frame.origin, (0, 0))
        with patch("fco.desktop.pyautogui.click") as click:
            desktop.click_point(frame, 1453, 278)
        click.assert_called_once_with(1453, 278)
