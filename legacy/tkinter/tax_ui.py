"""Standalone fee calculator page. Does not interact with the game."""

import json
import tkinter as tk
from tkinter import ttk

from fco.pricing import parse_bp
from fco.paths import APP_ROOT
from fco.storage import atomic_json
from fco.calculators.tax import calculate_tax, format_bp, COUPON_CHOICES

ACCENT = "#57dfb2"


class TaxUI:
    def build_tax(self, page):
        settings = {"price": "0", "member": "none", "coupon": 0, "pc": False}
        self.tax_settings_path = APP_ROOT / "tax-settings.json"
        try:
            stored = json.loads(self.tax_settings_path.read_text(encoding="utf-8"))
            calculate_tax(
                parse_bp(stored["price"]), stored["member"], stored["coupon"], stored["pc"]
            )
            settings.update(stored)
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.tax_vars = {
            "price": tk.StringVar(value=settings["price"]),
            "member": tk.StringVar(value=settings["member"]),
            "coupon": tk.IntVar(value=settings["coupon"]),
            "pc": tk.BooleanVar(value=settings["pc"]),
        }
        self.tax_net = tk.StringVar()
        self.tax_fee = tk.StringVar()
        self.tax_saving = tk.StringVar()
        self.tax_detail = tk.StringVar()
        self.tax_error = tk.StringVar()
        self.tax_result = None
        self.tax_save_job = None
        box = self.card(page, "Giá bán cầu thủ (BP)")
        self.tax_price_entry = ttk.Entry(
            box, textvariable=self.tax_vars["price"], font=("Segoe UI", 18, "bold")
        )
        self.tax_price_entry.pack(fill="x", pady=(8, 0))
        self.tax_price_entry.bind("<FocusOut>", lambda _: self.format_tax_price())
        self.tax_price_entry.bind("<Return>", lambda _: self.format_tax_price())
        # Calculator inputs stay independent of trade settings and screen setup.
        box = self.card(page, "Giảm thuế")
        member_row = ttk.Frame(box, style="Card.TFrame")
        member_row.pack(fill="x", pady=(8, 8))
        self.tax_member_buttons = {}
        for member, text in [
            ("none", "Không có VIP"),
            ("vip", "VIP · 10%"),
            ("svip", "SVIP · 30%"),
        ]:
            button = ttk.Button(
                member_row,
                text=text,
                command=lambda value=member: self.tax_vars["member"].set(value),
            )
            button.pack(side="left", padx=(0, 8))
            self.tax_member_buttons[member] = button
        coupon_row = ttk.Frame(box, style="Card.TFrame")
        coupon_row.pack(fill="x", pady=(0, 6))
        self.tax_coupon_buttons = {}
        for percent in COUPON_CHOICES:
            button = ttk.Button(
                coupon_row,
                text="Không coupon" if percent == 0 else f"CP {percent}%",
                command=lambda value=percent: self.tax_vars["coupon"].set(value),
            )
            button.pack(side="left", padx=(0, 6))
            self.tax_coupon_buttons[percent] = button
        ttk.Checkbutton(
            box,
            text="Có quyền lợi phòng máy PC / Gcafe · giảm thêm 30% tiền thuế",
            variable=self.tax_vars["pc"],
        ).pack(anchor="w")
        box = self.card(page, "THU NHẬP SAU THUẾ")
        self.tax_net_label = ttk.Label(
            box,
            textvariable=self.tax_net,
            foreground=ACCENT,
            style="Card.TLabel",
            font=("Segoe UI", 25, "bold"),
        )
        self.tax_net_label.pack(anchor="w", pady=(6, 10))
        ttk.Label(box, textvariable=self.tax_fee, style="Card.TLabel", foreground="#f1c978").pack(
            anchor="w"
        )
        ttk.Label(box, textvariable=self.tax_saving, style="CardMuted.TLabel").pack(
            anchor="w", pady=(5, 0)
        )
        ttk.Label(box, textvariable=self.tax_detail, style="CardMuted.TLabel", wraplength=650).pack(
            anchor="w", pady=(8, 0)
        )
        ttk.Label(page, textvariable=self.tax_error, foreground="#ffb6bf", wraplength=650).pack(
            anchor="w", padx=4
        )
        for variable in self.tax_vars.values():
            variable.trace_add("write", lambda *_: self.recalculate_tax())
        self.recalculate_tax(persist=False)

    def format_tax_price(self):
        try:
            price = parse_bp(self.tax_vars["price"].get())
            self.tax_vars["price"].set(format_bp(price))
        except ValueError:
            pass

    def recalculate_tax(self, persist=True):
        member = self.tax_vars["member"].get()
        coupon = self.tax_vars["coupon"].get()
        for value, button in self.tax_member_buttons.items():
            button.configure(style="Primary.TButton" if member == value else "TButton")
        for value, button in self.tax_coupon_buttons.items():
            button.configure(style="Primary.TButton" if coupon == value else "TButton")
        try:
            result = calculate_tax(
                parse_bp(self.tax_vars["price"].get()), member, coupon, self.tax_vars["pc"].get()
            )
        except ValueError:
            self.tax_result = None
            self.tax_net.set("— BP")
            self.tax_fee.set("")
            self.tax_saving.set("")
            self.tax_detail.set("")
            self.tax_error.set("Nhập số BP đầy đủ, ví dụ 7.600.000.000.000. Không dùng dạng 7.6T.")
            if self.tax_save_job:
                self.after_cancel(self.tax_save_job)
                self.tax_save_job = None
            return
        self.tax_result = result
        self.tax_error.set("")
        self.tax_net.set(f"{format_bp(result.net_bp)} BP")
        self.tax_net_label.configure(
            font=("Segoe UI", 25 if len(str(result.net_bp)) <= 16 else 18, "bold")
        )
        rate = f"{result.tax_basis_points / 100:g}".replace(".", ",")
        self.tax_fee.set(f"Thuế còn phải trả: {format_bp(result.tax_bp)} BP  ·  {rate}% giá bán")
        self.tax_saving.set(
            f"Đã giảm: {format_bp(result.saved_bp)} BP từ thuế gốc {format_bp(result.base_tax_bp)} BP"
        )
        self.tax_detail.set(
            f"Thuế gốc 40% · Tổng giảm {result.discount_percent}% tiền thuế. "
            "Ước tính cơ bản, chưa áp dụng giới hạn BP hoặc điều kiện riêng của coupon."
        )
        if persist:
            if self.tax_save_job:
                self.after_cancel(self.tax_save_job)
            self.tax_save_job = self.after(300, self.save_tax_settings)

    def save_tax_settings(self):
        self.tax_save_job = None
        if self.tax_result is None:
            return
        try:
            atomic_json(
                self.tax_settings_path,
                {
                    "price": format_bp(self.tax_result.gross_bp),
                    "member": self.tax_vars["member"].get(),
                    "coupon": self.tax_vars["coupon"].get(),
                    "pc": self.tax_vars["pc"].get(),
                },
            )
        except OSError:
            self.tax_error.set("Đã tính xong, nhưng không lưu được lựa chọn vào thư mục dữ liệu.")
