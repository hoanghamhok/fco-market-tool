import json
from pathlib import Path
from tempfile import TemporaryDirectory
import tkinter as tk
from tkinter import ttk
import unittest

from legacy.tkinter import theme
from fco.calculators.salary import FORMATIONS, clean_settings, parse_salary, total_salary
from legacy.tkinter.salary_ui import SalaryUI


class SalaryCoreTests(unittest.TestCase):
    def test_reference_positions_and_totals(self):
        self.assertEqual(
            {p for p, _, _ in FORMATIONS["4-3-3"]},
            {"ST", "LW", "RW", "CM", "LDM", "RDM", "LB", "LCB", "RCB", "RB", "GK"},
        )
        self.assertEqual(
            {p for p, _, _ in FORMATIONS["4-1-4-1"]},
            {"ST", "LM", "RM", "LCM", "RCM", "CDM", "LB", "LCB", "RCB", "RB", "GK"},
        )
        self.assertEqual(total_salary(["25"] * 11), 275)
        self.assertEqual(total_salary(["", "0", "30", "28", "0018"]), 76)

    def test_invalid_inputs(self):
        for value in ["-1", "2.5", "1e2", "abc", "2,5", None, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_salary(value)

    def test_corrupt_settings(self):
        for stored in [None, [], {"formation": []}, {"squads": []}]:
            self.assertEqual(clean_settings(stored)["formation"], "4-3-3")
        result = clean_settings(
            {"formation": "4-1-4-1", "squads": {"4-1-4-1": {"ST": "25", "GK": "-5", "CDM": None}}}
        )
        self.assertEqual(result["squads"]["4-1-4-1"]["ST"], "25")
        self.assertEqual(result["squads"]["4-1-4-1"]["GK"], "")
        self.assertEqual(result["squads"]["4-1-4-1"]["CDM"], "")


class SalaryHarness(SalaryUI, tk.Tk):
    def __init__(self, path):
        super().__init__()
        self.withdraw()
        theme.apply(self)
        page = ttk.Frame(self)
        page.pack(fill="both", expand=True)
        self.build_salary(page, path)


class SalaryInteractionTests(unittest.TestCase):
    def test_edit_switch_clear_and_reload(self):
        with TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            path = Path(folder) / "salary.json"
            app = SalaryHarness(path)
            try:
                app.salary_entries["ST"].insert(0, "30")
                app.salary_entries["GK"].insert(0, "18")
                self.assertEqual(app.salary_total.get(), "48")
                app.salary_entries["GK"].insert(0, "-")
                self.assertEqual(app.salary_total.get(), "48")
                app.salary_entries["GK"].delete(0, "end")
                self.assertEqual(app.salary_total.get(), "30")
                app.select_salary_formation("4-1-4-1")
                self.assertEqual(app.salary_total.get(), "0")
                for entry in app.salary_entries.values():
                    entry.insert(0, "25")
                self.assertEqual(app.salary_total.get(), "275")
                app.select_salary_formation("4-3-3")
                self.assertEqual(app.salary_total.get(), "30")
                app.clear_salary()
                self.assertEqual(app.salary_total.get(), "0")
                app.select_salary_formation("4-1-4-1")
                self.assertEqual(app.salary_total.get(), "275")
                app.save_salary_settings()
                self.assertEqual(
                    json.loads(path.read_text(encoding="utf-8"))["formation"], "4-1-4-1"
                )
            finally:
                app.destroy()
            restored = SalaryHarness(path)
            try:
                self.assertEqual(restored.salary_formation, "4-1-4-1")
                self.assertEqual(restored.salary_total.get(), "275")
                restored.select_salary_formation("4-3-3", persist=False)
                self.assertEqual(restored.salary_total.get(), "0")
            finally:
                restored.destroy()


if __name__ == "__main__":
    unittest.main()
