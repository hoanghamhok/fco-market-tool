from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from PIL import Image, ImageDraw
from fco.paths import RESOURCE_ROOT
from fco.dialog import DialogReader, NoDialog
from fco.ocr import OCR
from fco.refresh import ParentReader, Refresher, Entry
from fco.schedule import ResetWindow, VN
from fco.privileges import input_error


class ScheduleTests(unittest.TestCase):
    def test_timezone_and_exact_boundaries(self):
        now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
        window = ResetWindow.create("19:01:00", 120, now)
        self.assertEqual(window.start.hour, 19)
        self.assertEqual(window.state(now), "waiting")
        self.assertEqual(window.state(window.start), "active")
        self.assertEqual(window.state(window.end), "ended")

    def test_current_window_and_next_day(self):
        now = datetime(2026, 10, 26, 19, 1, tzinfo=VN)
        current = ResetWindow.create("19:00", 120, now)
        self.assertEqual(current.state(now), "active")
        tomorrow = ResetWindow.create("19:00", 30, now)
        self.assertEqual(tomorrow.start.day, 27)
        immediate = ResetWindow.create("", 30, now)
        self.assertEqual(immediate.start, now)
        self.assertEqual(immediate.end - now, timedelta(seconds=30))

    def test_reject_invalid_settings(self):
        for text, seconds in [("25:01", 120), ("abc", 120), ("", 0), ("", 1801), ("", True)]:
            with self.subTest(text=text, seconds=seconds):
                with self.assertRaises(ValueError):
                    ResetWindow.create(text, seconds)

    def test_active_window_crossing_midnight(self):
        now = datetime(2026, 10, 27, 0, 0, tzinfo=VN)
        window = ResetWindow.create("23:59", 120, now)
        self.assertEqual(window.start.day, 26)
        self.assertEqual(window.state(now), "active")

    def test_reports_privilege_mismatch(self):
        self.assertIn("Run as administrator", input_error(0x3000, 0x2000))
        self.assertIsNone(input_error(0x3000, 0x3000))
        self.assertIsNone(input_error(None, 0x2000))

    def test_immediate_duration_starts_after_setup_delay(self):
        now = datetime(2026, 10, 26, 21, 57, tzinfo=VN)
        original = ResetWindow.create("", 5, now)
        run = original.after_setup(True, now + timedelta(seconds=4))
        self.assertEqual(run.end - now, timedelta(seconds=9))
        self.assertEqual(run.end - run.start, timedelta(seconds=5))
        self.assertIs(original.after_setup(False, now + timedelta(seconds=4)), original)


class ParentImageTests(unittest.TestCase):
    def test_cached_parent_rejects_changed_state_and_register_button(self):
        parent = ParentReader(self.ocr)
        image = self.image("orders-hover")
        bound = DialogReader(self.ocr).read(self.image("sell"))
        entry = parent.find_entry(image, bound)
        self.assertEqual(parent.register_button(image, bound, entry), (1453, 278))
        changed = image.copy()
        ImageDraw.Draw(changed).rectangle((1410, 260, 1494, 294), fill="#4d5151")
        with self.assertRaises(ValueError):
            parent.register_button(changed, bound, entry)
        changed = image.copy()
        ImageDraw.Draw(changed).rectangle((1300, 260, 1410, 295), fill="#4d5151")
        with self.assertRaises(ValueError):
            parent.find_entry(changed, bound)

    @classmethod
    def setUpClass(cls):
        cls.ocr = OCR()

    @classmethod
    def tearDownClass(cls):
        cls.ocr.close()

    def image(self, name):
        return Image.open(RESOURCE_ROOT / "assets/fixtures" / f"sample-{name}.png").convert("RGB")

    def test_real_parent_controls_and_same_player(self):
        parent = ParentReader(self.ocr)
        sell = DialogReader(self.ocr).read(self.image("sell"))
        im = self.image("orders-hover")
        entry = parent.find_entry(im, sell)
        self.assertEqual((entry.row_y, entry.boost), (278, 6))
        x, y = parent.register_button(im, sell, entry)
        self.assertTrue(1410 < x < 1494 and 260 < y < 294)
        buy = DialogReader(self.ocr).read(self.image("buy-nedved"))
        x, y = parent.market_button(self.image("buy-parent"), buy)
        self.assertTrue(1199 < x < 1385 and 901 < y < 941)

    def test_blank_register_button_never_becomes_cancel(self):
        parent = ParentReader(self.ocr)
        im = self.image("orders-hover")
        bound = DialogReader(self.ocr).read(self.image("sell"))
        entry = parent.find_entry(im, bound)
        ImageDraw.Draw(im).rectangle((1410, 260, 1494, 294), fill="#4d5151")
        with self.assertRaises(ValueError):
            parent.register_button(im, bound, entry)

    def test_parent_controls_at_three_image_scales(self):
        parent = ParentReader(self.ocr)
        for scale in [0.85, 1, 1.15]:
            with self.subTest(scale=scale):
                im = self.image("orders-hover")
                im = im.resize(
                    (round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS
                )
                bound = DialogReader(self.ocr).read(self.image("sell"))
                entry = parent.find_entry(im, bound)
                x, y = parent.register_button(im, bound, entry)
                self.assertAlmostEqual(x, 1453 * scale, delta=2)
                self.assertAlmostEqual(y, 278 * scale, delta=2)

    def test_changed_boost_or_duplicate_row_rejected(self):
        parent = ParentReader(self.ocr)
        im = self.image("orders-hover")
        bound = DialogReader(self.ocr).read(self.image("sell"))
        bound.boost = 5
        with self.assertRaises(ValueError):
            parent.find_entry(im, bound)
        bound.boost = 6
        duplicate = im.copy()
        duplicate.paste(im.crop((287, 249, 1633, 307)), (287, 307))
        with self.assertRaises(ValueError):
            parent.find_entry(duplicate, bound)

    def test_wrong_tab_or_parent_rejected(self):
        parent = ParentReader(self.ocr)
        bound = DialogReader(self.ocr).read(self.image("sell"))
        with self.assertRaises(ValueError):
            parent.market_button(self.image("buy-parent"), bound)
        with self.assertRaises(ValueError):
            parent.find_entry(self.image("buy-parent"), bound)

    def test_blank_ocr_is_read_error(self):
        with self.assertRaises(ValueError):
            self.ocr.text(Image.new("RGB", (80, 30), "white"))

    def test_reported_orders_tab_fixture_and_fade(self):
        from PIL import ImageEnhance

        parent = ParentReader(self.ocr)
        im = self.image("orders-3.2.2")
        self.assertTrue(parent.orders_selected(im))
        bound = DialogReader(self.ocr).read(self.image("sell"))
        self.assertEqual(parent.find_entry(im, bound).boost, 6)
        self.assertFalse(parent.orders_selected(ImageEnhance.Brightness(im).enhance(0.8)))

    def test_two_full_cycles_from_parent_with_real_ocr(self):
        reader = DialogReader(self.ocr)
        modal = self.image("sell")
        parent = self.image("orders-hover")
        bound = reader.read(modal)
        state = ["parent"]
        events = []
        reports = []

        def capture():
            return SimpleNamespace(image=modal if state[0] == "modal" else parent)

        def scan(reader, bound):
            return reader.read(capture().image, bound)

        def escape():
            events.append("esc")
            state[0] = "parent"

        def click(frame, x, y):
            self.assertEqual((x, y), (1453, 278))
            events.append("open")
            state[0] = "modal"

        io = SimpleNamespace(
            capture=capture,
            scan=scan,
            escape=escape,
            wait=lambda _: None,
            move_point=lambda *args: events.append("hover"),
            click_point=click,
        )
        refresh = Refresher(ParentReader(self.ocr), emit=lambda *args: reports.append(args))
        refresh.cycle(io, reader, bound)
        refresh.cycle(io, reader, bound)
        self.assertEqual(events, ["hover", "open", "esc", "hover", "open"])
        self.assertEqual(refresh.rounds, 2)
        self.assertTrue(any("Vòng 2: Esc → mở lại OK" in text for _, text in reports))

    def test_unrelated_screen_with_real_ocr_never_sends_input(self):
        bound = DialogReader(self.ocr).read(self.image("sell"))
        events = []
        io = SimpleNamespace(
            capture=lambda: SimpleNamespace(image=Image.new("RGB", (1920, 1032), "#222222")),
            escape=lambda: events.append("esc"),
            click_point=lambda *args: events.append("click"),
        )
        with self.assertRaisesRegex(RuntimeError, "Kiểm tra hộp"):
            Refresher(ParentReader(self.ocr)).cycle(io, DialogReader(self.ocr), bound)
        self.assertEqual(events, [])


class RefreshFlowTests(unittest.TestCase):
    def io(self, scan_error=None, begin="modal", esc_works=True):
        events = []
        scans = [0]
        state = [begin]
        quote = SimpleNamespace(
            quote=SimpleNamespace(
                floor=SimpleNamespace(value=100), ceiling=SimpleNamespace(value=120)
            )
        )

        def scan(*args):
            scans[0] += 1
            if scans[0] > 1 and scan_error:
                raise scan_error
            if state[0] != "modal":
                raise NoDialog("closed")
            return quote

        def escape():
            events.append("esc")
            if esc_works:
                state[0] = "parent"

        def reopen(*args):
            events.append("reopen")
            state[0] = "modal"

        io = SimpleNamespace(
            scan=scan,
            escape=escape,
            quote=quote,
            wait=lambda _: None,
            capture=lambda: SimpleNamespace(
                image=SimpleNamespace(width=1920, height=1032, kind=state[0])
            ),
            move_point=lambda *args: events.append("hover"),
            click_point=reopen,
        )
        return io, events, scans

    def locate(self, image):
        if image.kind != "modal":
            raise NoDialog("closed")
        return object()

    def parent(self, orders=True):
        return SimpleNamespace(
            root=lambda _: None,
            orders_selected=lambda _: orders,
            find_entry=lambda *args: Entry(278, 6),
            register_button=lambda *args: (1453, 278),
            market_button=lambda *args: (1294, 921),
        )

    def test_esc_hover_reopen_then_verify(self):
        io, events, scans = self.io()
        refresh = Refresher(self.parent())
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            self.assertEqual(refresh.cycle(io, object(), object()), io.quote)
        self.assertEqual(events, ["esc", "hover", "reopen"])
        self.assertEqual((scans[0], refresh.rounds), (2, 1))

    def test_esc_not_received_stops_without_reopen(self):
        io, events, _ = self.io(esc_works=False)
        refresh = Refresher(self.parent())
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            with self.assertRaises(RuntimeError):
                refresh.cycle(io, object(), object())
        self.assertEqual(events, ["esc"])

    def test_wrong_card_after_reopen_stops_without_another_input(self):
        io, events, scans = self.io(ValueError("Thẻ đã đổi"))
        refresh = Refresher(self.parent(False))
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            with self.assertRaisesRegex(RuntimeError, "đã đổi"):
                refresh.cycle(io, object(), object())
        self.assertEqual(events, ["esc", "reopen"])
        self.assertGreater(scans[0], 2)

    def test_transient_modal_read_recovers_before_esc(self):
        io, events, scans = self.io()
        scan = io.scan

        def transient(*args):
            if scans[0] == 0:
                scans[0] += 1
                raise ValueError("OCR chưa đọc rõ")
            return scan(*args)

        io.scan = transient
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            Refresher(self.parent()).cycle(io, object(), object())
        self.assertEqual(events, ["esc", "hover", "reopen"])

    def test_partial_card_after_reopen_recovers_without_more_input(self):
        io, events, scans = self.io()
        scan = io.scan

        def partial(*args):
            if scans[0] == 1:
                scans[0] += 1
                raise ValueError("Cầu thủ hoặc mức cộng đã đổi")
            return scan(*args)

        io.scan = partial
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            Refresher(self.parent()).cycle(io, object(), object())
        self.assertEqual(events, ["esc", "hover", "reopen"])
        self.assertEqual(scans[0], 3)

    def test_row_paints_after_tab_without_clicking_unverified_row(self):
        io, events, _ = self.io()
        parent = self.parent()
        reads = [0]

        def delayed(*args):
            reads[0] += 1
            if reads[0] < 3:
                raise ValueError("Dòng chưa vẽ xong")
            return Entry(278, 6)

        parent.find_entry = delayed
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            Refresher(parent).cycle(io, object(), object())
        self.assertEqual(reads[0], 3)
        self.assertEqual(events, ["esc", "hover", "reopen"])

    def test_resume_from_parent_opens_without_blind_esc(self):
        io, events, scans = self.io(begin="parent")
        messages = []
        refresh = Refresher(self.parent(), emit=lambda *args: messages.append(args))
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            self.assertEqual(refresh.cycle(io, object(), object()), io.quote)
        self.assertEqual(events, ["hover", "reopen"])
        self.assertEqual(scans[0], 1)
        self.assertTrue(any("Mở từ bảng TTCN" in text for _, text in messages))

    def test_unknown_screen_stops_without_input(self):
        io, events, _ = self.io(begin="parent")
        parent = self.parent()

        def invalid(_):
            raise ValueError("Không phải TTCN")

        parent.root = invalid
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            with self.assertRaisesRegex(RuntimeError, "Không phải TTCN"):
                Refresher(parent).cycle(io, object(), object())
        self.assertEqual(events, [])

    def test_waits_for_hover_button_and_only_clicks_once(self):
        io, events, _ = self.io()
        parent = self.parent()
        attempts = [0]

        def button(*args):
            attempts[0] += 1
            if attempts[0] < 3:
                raise ValueError("not painted")
            return (1453, 278)

        parent.register_button = button
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            Refresher(parent).cycle(io, object(), object())
        self.assertEqual(attempts[0], 3)
        self.assertEqual(events, ["esc", "hover", "reopen"])

    def test_ambiguous_modal_is_not_treated_as_closed(self):
        io, events, _ = self.io()
        with patch("fco.refresh.locate_dialog", side_effect=ValueError("Nhiều hộp")):
            with self.assertRaisesRegex(RuntimeError, "Nhiều hộp"):
                Refresher(self.parent()).cycle(io, object(), object())
        self.assertEqual(events, [])

    def test_parent_tab_fades_in_without_wrong_route_or_another_esc(self):
        io, events, _ = self.io()
        parent = self.parent()
        reads = [0]

        def selected(_):
            reads[0] += 1
            return reads[0] >= 3

        def no_market(*args):
            raise ValueError("tab still fading in")

        parent.orders_selected = selected
        parent.market_button = no_market
        with patch("fco.refresh.locate_dialog", side_effect=self.locate):
            Refresher(parent).cycle(io, object(), object())
        self.assertEqual(reads[0], 3)
        self.assertEqual(events, ["esc", "hover", "reopen"])
