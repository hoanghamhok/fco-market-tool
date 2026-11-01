import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fco.controller import DesktopAPI


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.api = DesktopAPI(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_existing_data_migration_and_independent_squads(self):
        (self.root / "salary-settings.json").write_text(
            json.dumps({"formation": "4-1-4-1", "squads": {"4-1-4-1": {"ST": "30", "GK": "18"}}}),
            encoding="utf-8",
        )
        old = self.api.bootstrap()
        self.assertEqual(old["salary"]["squads"]["4-1-4-1"]["ST"], "30")
        self.assertEqual(old["salary"]["squads"]["4-3-3"]["ST"], "")
        self.api.save_salary(old["salary"])
        restored = DesktopAPI(self.root).bootstrap()
        self.assertEqual(restored["salary"], old["salary"])

    def test_tax_precision_and_settings(self):
        result = self.api.tax(
            {"price": "7.600.000.000.000", "member": "svip", "coupon": 30, "pc": False}
        )
        self.assertEqual(result["net_raw"], "6384000000000")
        self.assertEqual(self.api.bootstrap()["tax"]["member"], "svip")
        with self.assertRaises(ValueError):
            self.api.tax({"price": "bad", "member": "svip", "coupon": 30, "pc": False})
        self.assertEqual(self.api.bootstrap()["tax"]["price"], "7.600.000.000.000")

    def test_trade_guards_reject_before_accessing_game(self):
        settings = self.api.bootstrap()["watch"]
        with patch("fco.controller.Desktop") as desktop:
            with self.assertRaises(ValueError):
                self.api.start_action("watch", settings)
            self.api._set(busy=True)
            with self.assertRaises(ValueError):
                self.api.start_action("detect", settings)
            desktop.assert_not_called()
        self.api.stop_action()
        self.assertTrue(self.api._stop.is_set())

    def test_settings_saved_without_starting_a_trade(self):
        settings = self.api.bootstrap()["watch"]
        settings.update(limit="800.000.000", reset_duration="180", dry_run=False)
        self.api.save_watch(settings)
        self.assertEqual(DesktopAPI(self.root).bootstrap()["watch"], settings)
        self.assertFalse(self.api.get_state()["busy"])

    def test_corrupt_files_fall_back_and_journal_still_blocks(self):
        for name in ("salary-settings.json", "settings.json", "tax-settings.json"):
            (self.root / name).write_text("{broken", encoding="utf-8")
        (self.root / "last-order.json").write_text("{broken", encoding="utf-8")
        data = DesktopAPI(self.root).bootstrap()
        self.assertTrue(data["watch"]["dry_run"])
        self.assertTrue(data["state"]["pending"])
        self.assertEqual(data["salary"]["formation"], "4-3-3")
