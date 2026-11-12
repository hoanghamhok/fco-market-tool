import unittest
from PIL import Image, ImageDraw
from fco.paths import RESOURCE_ROOT
from fco.dialog import DialogReader, RecognitionError, locate_dialog, PROFILES, COMMON, button_enabled
from fco.ocr import OCR, normalize


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ocr = OCR()

    @classmethod
    def tearDownClass(cls):
        cls.ocr.close()

    def image(self, side):
        return Image.open(RESOURCE_ROOT / "assets/fixtures" / f"sample-{side}.png").convert("RGB")

    def test_actual_buy_and_sell_profiles_without_setup(self):
        buy = DialogReader(self.ocr).read(self.image("buy"), exact=True)
        self.assertEqual((buy.side, buy.boost, buy.quantity, buy.price), ("buy", 5, 1, 8070000000))
        self.assertFalse(buy.enabled)
        self.assertEqual(buy.error, "Không đủ BP")
        sell = DialogReader(self.ocr).read(self.image("sell"), exact=True)
        self.assertEqual(
            (sell.side, sell.boost, sell.quantity, sell.price), ("sell", 6, 1, 16400000000)
        )
        self.assertTrue(sell.enabled)

    def test_changed_player_or_side_is_rejected(self):
        reader = DialogReader(self.ocr)
        bound = reader.read(self.image("buy"))
        with self.assertRaises(ValueError):
            reader.read(self.image("sell"), bound)

    def test_bound_dialog_does_not_depend_on_blurred_title(self):
        reader = DialogReader(self.ocr)
        bound = reader.read(self.image("buy"))
        image = self.image("buy")
        title = locate_dialog(image).region(COMMON["title"])
        ImageDraw.Draw(image).rectangle(
            (title.x, title.y, title.x + title.width, title.y + title.height), fill="white"
        )
        with self.assertRaises(RecognitionError):
            DialogReader(self.ocr).read(image)
        self.assertEqual(reader.read(image, bound).identity, bound.identity)

    def test_selected_tab_check_remains_mandatory(self):
        image = self.image("buy")
        box = locate_dialog(image)
        region = box.region((0.065, 0.10, 0.22, 0.156))
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (region.x, region.y, region.x + region.width, region.y + region.height), fill="white"
        )
        with self.assertRaises(ValueError):
            DialogReader(self.ocr).read(image)

    def test_window_translation_uses_relative_regions(self):
        source = self.image("sell")
        box = locate_dialog(source)
        frame = Image.new("RGB", (2100, 1200), "#172331")
        frame.paste(box.crop(source), (80, 220))
        snapshot = DialogReader(self.ocr).read(frame, exact=True)
        self.assertAlmostEqual(snapshot.box.x, 80, delta=3)
        self.assertEqual(snapshot.price, 16400000000)

    def test_unchanged_fields_do_not_repeat_ocr(self):
        class CountingOCR:
            def __init__(self, base):
                self.base = base
                self.calls = 0

            def __getattr__(self, key):
                def call(*args, **kwargs):
                    self.calls += 1
                    return getattr(self.base, key)(*args, **kwargs)

                return call

        counting = CountingOCR(self.ocr)
        reader = DialogReader(counting)
        frame = self.image("sell")
        first = reader.read(frame, exact=True)
        calls = counting.calls
        reader.read(frame, first, exact=True)
        self.assertEqual(counting.calls, calls)

    def test_no_dialog_and_disabled_button(self):
        with self.assertRaises(ValueError):
            locate_dialog(Image.new("RGB", (1920, 1080), "#222222"))
        for side in ["buy", "sell"]:
            self.assertFalse(button_enabled(Image.new("RGB", (180, 40), "#666666"), side))
        self.assertTrue(button_enabled(Image.new("RGB", (180, 40), (0, 157, 255)), "sell"))
        self.assertFalse(button_enabled(Image.new("RGB", (180, 40), (0, 157, 255)), "buy"))
        self.assertTrue(button_enabled(Image.new("RGB", (180, 40), (250, 65, 30)), "buy"))
        self.assertFalse(button_enabled(Image.new("RGB", (180, 40), (250, 65, 30)), "sell"))

    def test_nedved_buy_gray_selection_and_small_plus_six(self):
        image = Image.open(RESOURCE_ROOT / "assets/fixtures" / "sample-buy-nedved.png").convert(
            "RGB"
        )
        snapshot = DialogReader(self.ocr).read(image, exact=True)
        self.assertEqual((snapshot.side, snapshot.boost, snapshot.price), ("buy", 6, 16400000000))
        self.assertEqual(snapshot.error, "Không đủ BP")

    def test_orange_plus_four_badge_from_failed_diagnostic(self):
        image = Image.open(
            RESOURCE_ROOT / "assets/fixtures/sample-boost-orange-4.png"
        ).convert("RGB")
        for scale in [0.85, 1, 1.15]:
            with self.subTest(scale=scale):
                resized = image.resize(
                    (round(image.width * scale), round(image.height * scale)),
                    Image.Resampling.LANCZOS,
                )
                self.assertEqual(self.ocr.number(resized, 50, badge=True), 4)

    def test_regression_dialogs_across_window_scales(self):
        for fixture in ["buy", "sell", "buy-nedved"]:
            original = Image.open(
                RESOURCE_ROOT / "assets/fixtures" / f"sample-{fixture}.png"
            ).convert("RGB")
            for scale in [0.67, 0.85, 1, 1.15, 1.5]:
                with self.subTest(fixture=fixture, scale=scale):
                    image = original.resize(
                        (round(original.width * scale), round(original.height * scale)),
                        Image.Resampling.LANCZOS,
                    )
                    snapshot = DialogReader(self.ocr).read(image, exact=True)
                    self.assertEqual(
                        snapshot.price, 8070000000 if fixture == "buy" else 16400000000
                    )
                    self.assertEqual(snapshot.boost, 5 if fixture == "buy" else 6)
                    self.assertEqual(snapshot.quantity, 1)

    def test_unclear_field_is_named_and_does_not_get_guessed(self):
        image = self.image("buy")
        box = locate_dialog(image)
        boost = box.region(PROFILES["buy"]["boost"])
        ImageDraw.Draw(image).rectangle(
            (boost.x, boost.y, boost.x + boost.width, boost.y + boost.height), fill="white"
        )
        with self.assertRaises(RecognitionError) as raised:
            DialogReader(self.ocr).read(image, exact=True)
        self.assertEqual(raised.exception.field, "boost")
        self.assertIn("Mức cộng", str(raised.exception))

    def reported_tab(self):
        return Image.open(RESOURCE_ROOT / "assets/fixtures/sample-tab-buy-raw.png").convert("RGB")

    def test_reported_lossless_tab_at_three_scales(self):
        original = self.reported_tab()
        for scale in [0.85, 1, 1.15]:
            with self.subTest(scale=scale):
                image = original.resize(
                    (round(original.width * scale), round(original.height * scale)),
                    Image.Resampling.LANCZOS,
                )
                self.assertEqual(normalize(self.ocr.tab(image)), "muathuong")

    def test_zambrotta_full_screenshot_across_window_scales(self):
        original = self.image("buy-zambrotta")
        for scale in [0.67, 0.85, 1, 1.15, 1.5]:
            with self.subTest(scale=scale):
                image = original.resize(
                    (round(original.width * scale), round(original.height * scale)),
                    Image.Resampling.LANCZOS,
                )
                reader = DialogReader(self.ocr)
                shot = reader.read(image, exact=True)
                self.assertEqual(
                    (shot.side, normalize(shot.name), shot.boost), ("buy", "gzambrotta", 5)
                )
                self.assertEqual(
                    (shot.quote.floor.value, shot.quote.ceiling.value, shot.price, shot.quantity),
                    (630000000, 770000000, 770000000, 1),
                )
                self.assertTrue(shot.enabled)
                self.assertEqual(reader.read(image, bound=shot, exact=True).identity, shot.identity)

    def test_reported_tab_in_complete_buy_dialog(self):
        image = self.image("buy")
        box = locate_dialog(image)
        tab = box.region(PROFILES["buy"]["tab"])
        image.paste(self.reported_tab().resize((tab.width, tab.height)), (tab.x, tab.y))
        result = DialogReader(self.ocr).read(image, exact=True)
        self.assertEqual((result.side, result.price), ("buy", 8070000000))

    def test_readable_label_without_selected_underline_is_rejected(self):
        image = self.image("buy")
        box = locate_dialog(image)
        line = box.region((0.069, 0.145, 0.214, 0.151))
        ImageDraw.Draw(image).rectangle(
            (line.x, line.y, line.x + line.width, line.y + line.height), fill="white"
        )
        with self.assertRaisesRegex(ValueError, "chưa được chọn"):
            DialogReader(self.ocr).read(image)

    def test_sell_tab_cannot_be_used_with_buy_title(self):
        image = self.image("buy")
        box = locate_dialog(image)
        tab = box.region(PROFILES["buy"]["tab"])
        sell = self.image("sell")
        sell_box = locate_dialog(sell)
        label = sell_box.region(PROFILES["sell"]["tab"]).crop(sell)
        image.paste(label.resize((tab.width, tab.height)), (tab.x, tab.y))
        with self.assertRaisesRegex(ValueError, "Hãy chọn"):
            DialogReader(self.ocr).read(image)
