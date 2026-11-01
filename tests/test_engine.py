from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from datetime import datetime, timedelta
from fco.schedule import ResetWindow, VN
from fco.engine import monitor, select_price
from fco.pricing import PriceLabel, Quote
from fco.storage import Journal, FileLock


def snapshot(side="buy", low=100, high=120, price=None, enabled=True, quantity=1, quantum=1):
    return SimpleNamespace(
        side=side,
        quote=Quote(PriceLabel(low, quantum), PriceLabel(high, quantum)),
        price=price,
        enabled=enabled,
        error="Không đủ BP" if not enabled else "",
        quantity=quantity,
        name="Test Player",
        boost=5,
    )


class FakeIO:
    def __init__(self, frames, journal=None):
        self.frames = iter(frames)
        self.actions = []
        self.journal = journal

    def scan(self, *args, **kwargs):
        return next(self.frames)

    def wait(self, seconds):
        pass

    def click(self, shot, key):
        if key == "submit":
            assert self.journal.pending()["state"] == "pending"
        self.actions.append(key)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.journal = Journal(self.temp.name)

    def frames(self, side="buy", exact=130, enabled=True, quantity=1, quantum=1):
        old = snapshot(side=side, quantum=quantum)
        new = snapshot(side=side, low=110, high=130, quantum=quantum)
        selected = snapshot(
            side=side,
            low=110,
            high=130,
            price=exact,
            enabled=enabled,
            quantity=quantity,
            quantum=quantum,
        )
        return [old, old, new, new, new, selected, selected]

    def run_monitor(self, io, side="buy", dry=False, limit=130, quantum=1):
        return monitor(
            io,
            object(),
            snapshot(side=side, quantum=quantum),
            limit,
            dry,
            self.journal,
            lambda *_: None,
        )

    def test_dry_run_never_clicks(self):
        io = FakeIO(self.frames(), self.journal)
        self.assertEqual(self.run_monitor(io, dry=True), "preview")
        self.assertEqual(io.actions, [])
        self.assertIsNone(self.journal.pending())

    def test_buy_max_sell_min_and_one_final_click(self):
        for side, target, price, limit in [
            ("buy", "ceiling", 130, 130),
            ("sell", "floor", 110, 100),
        ]:
            with self.subTest(side=side):
                io = FakeIO(self.frames(side, price), self.journal)
                with patch("fco.engine.wait_result", return_value="confirmed"):
                    self.assertEqual(self.run_monitor(io, side, limit=limit), "confirmed")
                self.assertEqual(io.actions, [target, "submit"])
                self.assertEqual(self.journal.pending()["price_bp"], price)

    def test_disabled_or_wrong_quantity_stops_before_journal(self):
        for kwargs in [dict(enabled=False), dict(quantity=2)]:
            io = FakeIO(self.frames(**kwargs), self.journal)
            with self.assertRaises(RuntimeError):
                self.run_monitor(io)
            self.assertNotIn("submit", io.actions)
            self.assertIsNone(self.journal.pending())

    def test_exact_full_price_over_cap_stops_even_when_display_may_qualify(self):
        io = FakeIO(self.frames(exact=136, quantum=10), self.journal)
        with self.assertRaisesRegex(RuntimeError, "ngưỡng"):
            self.run_monitor(io, limit=135, quantum=10)
        self.assertNotIn("submit", io.actions)

    def test_cannot_submit_without_durable_record(self):
        io = FakeIO(self.frames(), self.journal)
        with patch.object(self.journal, "write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.run_monitor(io)
        self.assertNotIn("submit", io.actions)

    def test_unverified_attempt_blocks_retries_until_acknowledged(self):
        io = FakeIO(self.frames(), self.journal)
        with patch("fco.engine.wait_result", return_value="unverified"):
            self.run_monitor(io)
        second = FakeIO(self.frames(), self.journal)
        with self.assertRaisesRegex(RuntimeError, "Lệnh trước"):
            self.run_monitor(second)
        self.assertEqual(second.actions, [])
        self.journal.acknowledge()
        self.assertIsNone(self.journal.pending())

    def test_lock_prevents_two_controllers(self):
        path = Path(self.temp.name) / ".control.lock"
        with FileLock(path):
            with self.assertRaises(RuntimeError):
                with FileLock(path):
                    pass
        with FileLock(path):
            pass

    def refresh_monitor(self, dry=True, clock=None):
        now = datetime(2026, 10, 26, 20, tzinfo=VN)
        window = ResetWindow(now, now + timedelta(seconds=120))
        new = snapshot(low=110, high=130)
        selected = snapshot(low=110, high=130, price=130)
        io = FakeIO([new, new, new, selected, selected], self.journal)
        io.require_input = lambda: None

        def cycle(io, *args):
            io.actions.append("refresh")
            return io.scan()

        refresher = SimpleNamespace(cycle=cycle, rounds=1)
        result = monitor(
            io,
            object(),
            snapshot(),
            130,
            dry,
            self.journal,
            lambda *_: None,
            refresher=refresher,
            window=window,
            clock=clock or (lambda: now),
        )
        return result, io

    def test_first_fresh_changed_quote_triggers_dry_preview_without_order(self):
        result, io = self.refresh_monitor()
        self.assertEqual(result, "preview")
        self.assertEqual(io.actions, ["refresh"])
        self.assertIsNone(self.journal.pending())

    def test_expiry_during_refresh_or_price_selection_never_submits(self):
        now = datetime(2026, 10, 26, 20, tzinfo=VN)
        for times, expected in [
            ([now, now + timedelta(seconds=120)], ["refresh"]),
            ([now, now, now + timedelta(seconds=120)], ["refresh", "ceiling"]),
        ]:
            with self.subTest(times=times):
                ticks = iter(times)
                result, io = self.refresh_monitor(dry=False, clock=lambda: next(ticks))
                self.assertEqual(result, "expired")
                self.assertEqual(io.actions, expected)
                self.assertIsNone(self.journal.pending())

    def test_waiting_window_does_not_refresh_before_start(self):
        now = datetime(2026, 10, 26, 20, tzinfo=VN)
        ticks = iter([now - timedelta(seconds=1), now, now])
        result, io = self.refresh_monitor(clock=lambda: next(ticks))
        self.assertEqual((result, io.actions), ("preview", ["refresh"]))

    def test_max_click_waits_for_price_paint_without_clicking_again(self):
        current = snapshot(low=110, high=130, price=100)
        chosen = snapshot(low=110, high=130, price=130)
        io = FakeIO([current, current, chosen, chosen])
        result = select_price(io, object(), current, 130)
        self.assertEqual(result.price, 130)
        self.assertEqual(io.actions, ["ceiling"])

    def test_unresponsive_price_field_never_submits_or_reclicks_max(self):
        current = snapshot(low=110, high=130, price=100)
        io = FakeIO([current] * 16)
        with self.assertRaisesRegex(RuntimeError, "chưa điền"):
            select_price(io, object(), current, 130)
        self.assertEqual(io.actions, ["ceiling"])
        self.assertIsNone(self.journal.pending())

    def test_real_red_buy_dialog_reset_clicks_max_then_submit_once(self):
        from PIL import Image
        from dataclasses import replace
        from fco.paths import RESOURCE_ROOT
        from fco.dialog import DialogReader
        from fco.ocr import OCR

        ocr = OCR()
        try:
            reader = DialogReader(ocr)
            image = Image.open(RESOURCE_ROOT / "assets/fixtures/sample-buy-zambrotta.png").convert(
                "RGB"
            )
            actual = reader.read(image, exact=True)
            self.assertTrue(actual.enabled)
            bound = replace(
                actual, quote=Quote(PriceLabel(620000000, 1000000), PriceLabel(760000000, 1000000))
            )
            events = []
            clicks = []
            journal = self.journal

            class IO:
                def require_input(self):
                    pass

                def wait(self, seconds):
                    pass

                def scan(self, reader, bound, exact=False):
                    events.append("read")
                    return reader.read(image, bound, exact=exact)

                def click(self, shot, key):
                    events.append(key)
                    clicks.append((key, shot.region(key).center))
                    if key == "submit":
                        assert journal.pending()["state"] == "pending"

            def cycle(io, reader, bound):
                events.append("refresh")
                return io.scan(reader, bound)

            refresher = SimpleNamespace(cycle=cycle, rounds=1)
            with patch("fco.engine.wait_result", return_value="confirmed"):
                result = monitor(
                    IO(),
                    reader,
                    bound,
                    900000000,
                    False,
                    self.journal,
                    lambda *_: None,
                    refresher=refresher,
                )
            self.assertEqual(result, "confirmed")
            self.assertEqual(
                events, ["refresh", "read", "read", "ceiling", "read", "read", "submit"]
            )
            self.assertEqual([key for key, _ in clicks], ["ceiling", "submit"])
            x, y = clicks[-1][1]
            self.assertTrue(1120 < x < 1310 and 809 < y < 848)
            self.assertEqual(self.journal.pending()["price_bp"], 770000000)
        finally:
            ocr.close()
