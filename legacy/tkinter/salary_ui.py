"""Editable football pitch with automatic totals for two squads."""

import json
import tkinter as tk
from tkinter import ttk

from fco.paths import APP_ROOT
from . import theme
from fco.storage import atomic_json
from fco.calculators.salary import FORMATIONS, clean_settings, parse_salary, total_salary


class SalaryUI:
    def build_salary(self, page, settings_path=None):
        self.salary_settings_path = settings_path or APP_ROOT / "salary-settings.json"
        try:
            stored = json.loads(self.salary_settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        settings = clean_settings(stored)
        self.salary_formation = settings["formation"]
        self.salary_vars = {
            formation: {
                position: tk.StringVar(self, value=value) for position, value in values.items()
            }
            for formation, values in settings["squads"].items()
        }
        self.salary_save_job = None
        self.salary_total = tk.StringVar(self)
        self.salary_count = tk.StringVar(self)
        self.salary_error = tk.StringVar(self)
        top = ttk.Frame(page)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text="LƯƠNG ĐỘI HÌNH", font=("Segoe UI", 16, "bold")).pack(side="left")
        self.salary_buttons = {}
        for key, label in [("4-3-3", "4-3-3 · 2 CDM"), ("4-1-4-1", "4-1-4-1")]:
            button = ttk.Button(
                top, text=label, command=lambda value=key: self.select_salary_formation(value)
            )
            button.pack(side="left", padx=(16, 0))
            self.salary_buttons[key] = button
        ttk.Button(top, text="Xóa lương sơ đồ", command=self.clear_salary).pack(side="right")
        ttk.Label(
            page,
            text="Nhập lương vào từng vị trí · Ô trống tính là 0 · Mỗi sơ đồ được lưu riêng.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        self.salary_pitch = tk.Canvas(
            page, bg="#10242e", highlightthickness=0, width=700, height=420
        )
        self.salary_pitch.pack(fill="both", expand=True)
        self.salary_entries = {}
        self.salary_windows = {}
        validate = (self.register(self.valid_salary_input), "%P")
        for position, _, _ in FORMATIONS[self.salary_formation]:
            self.add_salary_entry(position, validate)
        self.salary_validate = validate
        self.salary_pitch.bind("<Configure>", lambda _: self.draw_salary_pitch())
        result = ttk.Frame(page, style="Card.TFrame", padding=(18, 10))
        result.pack(fill="x", pady=(10, 0))
        ttk.Label(
            result, text="TỔNG LƯƠNG", style="CardMuted.TLabel", font=("Segoe UI", 10, "bold")
        ).pack(side="left")
        ttk.Label(
            result,
            textvariable=self.salary_total,
            style="Card.TLabel",
            foreground=theme.GREEN,
            font=("Segoe UI", 26, "bold"),
        ).pack(side="left", padx=18)
        ttk.Label(result, textvariable=self.salary_count, style="CardMuted.TLabel").pack(
            side="right"
        )
        ttk.Label(page, textvariable=self.salary_error, foreground="#ffb6bf").pack(anchor="w")
        for squad in self.salary_vars.values():
            for variable in squad.values():
                variable.trace_add("write", lambda *_: self.recalculate_salary())
        self.select_salary_formation(self.salary_formation, persist=False)

    @staticmethod
    def valid_salary_input(value):
        # Reject negative, fractional and nonnumeric input, including pasted text.
        if value != value.strip():
            return False
        try:
            parse_salary(value)
            return True
        except ValueError:
            return False

    def add_salary_entry(self, position, validate):
        entry = tk.Entry(
            self.salary_pitch,
            textvariable=self.salary_vars[self.salary_formation][position],
            justify="center",
            font=("Segoe UI", 15, "bold"),
            bg="#0e1d29",
            fg="#f0faf6",
            insertbackground=theme.GREEN,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#435d64",
            highlightcolor=theme.GREEN,
            validate="key",
            validatecommand=validate,
            width=5,
        )
        self.salary_entries[position] = entry
        self.salary_windows[position] = self.salary_pitch.create_window(0, 0, window=entry)

    def select_salary_formation(self, formation, persist=True):
        if formation != self.salary_formation:
            for entry in self.salary_entries.values():
                entry.destroy()
            for window in self.salary_windows.values():
                self.salary_pitch.delete(window)
            self.salary_entries.clear()
            self.salary_windows.clear()
            self.salary_formation = formation
            for position, _, _ in FORMATIONS[formation]:
                self.add_salary_entry(position, self.salary_validate)
        for key, button in self.salary_buttons.items():
            button.configure(style="Primary.TButton" if key == formation else "TButton")
        self.draw_salary_pitch()
        self.recalculate_salary(persist=persist)

    def draw_salary_pitch(self):
        canvas = self.salary_pitch
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            return
        canvas.delete("pitch")

        # A perspective pitch, with readable cards layered above the field markings.
        def point(x, y):
            return width * (0.5 + (x - 0.5) * (0.72 + 0.25 * y)), height * (0.07 + 0.89 * y)

        def polygon(points, **kwargs):
            return canvas.create_polygon(
                *[c for p in points for c in point(*p)], tags="pitch", **kwargs
            )

        polygon([(0, 0), (1, 0), (1, 1), (0, 1)], fill="#507d3e")
        for i in range(8):
            if i % 2 == 0:
                polygon(
                    [(0, i / 8), (1, i / 8), (1, (i + 1) / 8), (0, (i + 1) / 8)], fill="#598947"
                )

        def line(points):
            canvas.create_line(
                *[c for p in points for c in point(*p)], fill="#a3c58a", width=2, tags="pitch"
            )

        line([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        line([(0, 0.5), (1, 0.5)])
        for y, end in [(0, 0.19), (1, 0.81)]:
            line([(0.23, y), (0.23, end), (0.77, end), (0.77, y)])
            small = 0.07 if y == 0 else 0.93
            line([(0.39, y), (0.39, small), (0.61, small), (0.61, y)])
        cx, cy = point(0.5, 0.5)
        canvas.create_oval(
            cx - width * 0.12,
            cy - height * 0.085,
            cx + width * 0.12,
            cy + height * 0.085,
            outline="#a3c58a",
            width=2,
            tags="pitch",
        )
        canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#c2dda9", outline="", tags="pitch")
        card_w = min(112, width * 0.135)
        card_h = min(94, height * 0.16)
        for position, x, y in FORMATIONS[self.salary_formation]:
            cx, cy = width * x, height * y
            left, right = cx - card_w / 2, cx + card_w / 2
            top, bottom = cy - card_h / 2, cy + card_h / 2
            canvas.create_polygon(
                left,
                top + 8,
                cx,
                top,
                right,
                top + 8,
                right,
                bottom - 8,
                cx,
                bottom,
                left,
                bottom - 8,
                fill="#182c36",
                outline="#57706d",
                tags="pitch",
            )
            canvas.create_text(
                cx,
                top + card_h * 0.24,
                text=position,
                fill="#bbebce",
                font=("Segoe UI", 10, "bold"),
                tags="pitch",
            )
            canvas.coords(self.salary_windows[position], cx, cy + card_h * 0.13)
            canvas.itemconfigure(
                self.salary_windows[position], width=card_w - 22, height=max(24, card_h * 0.39)
            )
        canvas.tag_lower("pitch")

    def recalculate_salary(self, persist=True):
        values = [variable.get() for variable in self.salary_vars[self.salary_formation].values()]
        self.salary_total.set(str(total_salary(values)))
        self.salary_count.set(f"{sum(bool(value.strip()) for value in values)}/11 vị trí đã nhập")
        if persist:
            if self.salary_save_job:
                self.after_cancel(self.salary_save_job)
            self.salary_save_job = self.after(300, self.save_salary_settings)

    def clear_salary(self):
        for variable in self.salary_vars[self.salary_formation].values():
            variable.set("")

    def save_salary_settings(self):
        if self.salary_save_job:
            self.after_cancel(self.salary_save_job)
            self.salary_save_job = None
        try:
            atomic_json(
                self.salary_settings_path,
                {
                    "formation": self.salary_formation,
                    "squads": {
                        formation: {
                            position: variable.get() for position, variable in squad.items()
                        }
                        for formation, squad in self.salary_vars.items()
                    },
                },
            )
            self.salary_error.set("")
        except OSError:
            self.salary_error.set("Đã tính xong, nhưng không lưu được lương vào thư mục dữ liệu.")
