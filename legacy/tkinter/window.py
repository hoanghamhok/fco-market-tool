import json
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk

from fco.paths import APP_ROOT
from .tax_ui import TaxUI
from .salary_ui import SalaryUI
from fco.calculators.tax import format_bp
from fco import VERSION
from . import theme
from fco.desktop import Desktop, Stopped
from fco.dialog import DialogReader, RecognitionError
from fco.engine import monitor, select_price
from fco.ocr import OCR
from fco.pricing import parse_bp
from fco.storage import FileLock, Journal, atomic_json
from fco.schedule import ResetWindow
from fco.refresh import ParentReader, Refresher


class App(TaxUI, SalaryUI, tk.Tk):
    def __init__(self, hidden=False, salary_settings_path=None):
        super().__init__()
        if hidden:
            self.withdraw()
        theme.apply(self)
        self.title(f"FCO Market {VERSION} • Mua MAX / Bán MIN")
        self.geometry("1080x850")
        self.minsize(960, 810)
        APP_ROOT.mkdir(parents=True, exist_ok=True)
        self.settings_path = APP_ROOT / "settings.json"
        settings = {}
        try:
            settings = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        if not isinstance(settings, dict):
            settings = {}
        self.limit = tk.StringVar(value=str(settings.get("limit", "")))
        self.dry = tk.BooleanVar(
            value=(
                settings.get("dry_run", True)
                if type(settings.get("dry_run", True)) is bool
                else True
            )
        )
        self.refresh_enabled = tk.BooleanVar(
            value=settings.get("refresh_enabled", True) is not False
        )
        self.reset_start = tk.StringVar(value=str(settings.get("reset_start", "")))
        self.reset_duration = tk.StringVar(value=str(settings.get("reset_duration", 120)))
        self.status = tk.StringVar(
            value="Mở hộp Mua thường / Bán từng cá nhân trong FCO rồi bấm Nhận diện."
        )
        self.name = tk.StringVar(value="Chưa nhận diện cầu thủ")
        self.side = tk.StringVar(value="Mua tự chọn MAX • Bán tự chọn MIN")
        self.prices = tk.StringVar(value="MIN  —\nMAX  —")
        self.details = tk.StringVar(value="Không cần chọn vùng hoặc tọa độ.")
        self.limit_label = tk.StringVar(value="Ngưỡng giá (BP)")
        self.warning = tk.StringVar(value="")
        self.bound = None
        self.busy = False
        self.worker = None
        self.stop = threading.Event()
        self.events = queue.Queue()
        self.controls = []
        self.closed = False
        self.journal = Journal(APP_ROOT)
        self.salary_settings_override = salary_settings_path
        self.build()
        self.check_journal()
        self.after(80, self.pump)
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self.bind("<F9>", lambda _: self.launch("diagnose"))

    def build(self):
        header = ttk.Frame(self, padding=(22, 12))
        header.pack(fill="x")
        ttk.Label(header, text="FCO MARKET", font=("Segoe UI", 21, "bold")).pack(side="left")
        ttk.Label(
            header,
            text=f"{VERSION}  /  MUA MAX · BÁN MIN",
            foreground=theme.GREEN,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        self.watch_page = ttk.Frame(self.notebook, padding=(0, 10))
        self.tax_page = ttk.Frame(self.notebook, padding=(0, 16))
        self.notebook.add(self.watch_page, text="Canh giá")
        self.notebook.add(self.tax_page, text="Tính thuế TTCN")
        self.salary_page = ttk.Frame(self.notebook, padding=(0, 12))
        self.notebook.add(self.salary_page, text="Tính lương")
        ttk.Label(
            self.watch_page,
            text="Mở hộp trong game  →  Nhận diện  →  Nhập ngưỡng  →  Canh reset",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        bar = ttk.Frame(self.watch_page, style="Card.TFrame", padding=12)
        bar.pack(fill="x", pady=(0, 12))
        ttk.Label(bar, textvariable=self.status, style="Card.TLabel", wraplength=940).pack(
            anchor="w"
        )
        body = ttk.Frame(self.watch_page)
        body.pack(fill="x")
        body.columnconfigure(0, weight=1, uniform="main")
        body.columnconfigure(1, weight=1, uniform="main")
        left = ttk.Frame(body, style="Card.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ttk.Label(
            left,
            textvariable=self.side,
            style="Card.TLabel",
            foreground=theme.GREEN,
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        self.portrait = ttk.Label(
            left,
            style="Card.TLabel",
            text="Mở sẵn đúng thẻ cầu thủ trong hộp mua / bán",
            anchor="center",
        )
        self.portrait.pack(fill="x", pady=(12, 8))
        ttk.Label(
            left, textvariable=self.name, style="Card.TLabel", font=("Segoe UI", 15, "bold")
        ).pack(anchor="w")
        ttk.Label(
            left,
            textvariable=self.prices,
            style="Card.TLabel",
            font=("Segoe UI", 13, "bold"),
            justify="left",
        ).pack(anchor="w", pady=(10, 8))
        ttk.Label(left, textvariable=self.details, style="CardMuted.TLabel", wraplength=420).pack(
            anchor="w"
        )
        ttk.Label(
            right, text="Điều kiện đặt lệnh", style="Card.TLabel", font=("Segoe UI", 14, "bold")
        ).pack(anchor="w")
        ttk.Label(right, textvariable=self.limit_label, style="CardMuted.TLabel").pack(
            anchor="w", pady=(10, 7)
        )
        self.amount = ttk.Entry(right, textvariable=self.limit, font=("Segoe UI", 17, "bold"))
        self.amount.pack(fill="x")
        self.amount.bind("<FocusOut>", lambda _: self.format_limit())
        self.controls.append(self.amount)
        self.button(right, "Dùng giá MIN/MAX đang hiển thị", self.use_target).pack(
            anchor="w", pady=5
        )
        timing = ttk.Frame(right, style="Card.TFrame")
        timing.pack(fill="x", pady=(0, 7))
        timing.columnconfigure(0, weight=2)
        timing.columnconfigure(1, weight=1)
        ttk.Label(timing, text="Bắt đầu (giờ VN)", style="CardMuted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(timing, text="Canh (giây)", style="CardMuted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )
        begin = ttk.Entry(timing, textvariable=self.reset_start, width=13)
        begin.grid(row=1, column=0, sticky="ew", pady=5)
        duration = ttk.Entry(timing, textvariable=self.reset_duration, width=7)
        duration.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=5)
        self.controls.extend([begin, duration])
        ttk.Label(right, text="HH:MM:SS · để trống để chạy ngay", style="CardMuted.TLabel").pack(
            anchor="w"
        )
        refresh = ttk.Checkbutton(
            right, text="Esc → mở lại bảng để lấy giá mới", variable=self.refresh_enabled
        )
        refresh.pack(anchor="w", pady=(5, 0))
        self.controls.append(refresh)
        dry = ttk.Checkbutton(
            right, text="Chạy thử — làm mới bảng, không gửi lệnh", variable=self.dry
        )
        dry.pack(anchor="w", pady=4)
        self.controls.append(dry)
        ttk.Label(
            right,
            text="Mỗi phiên tối đa 1 lệnh. F8 để dừng.",
            style="CardMuted.TLabel",
            wraplength=420,
        ).pack(anchor="w", pady=5)
        actions = ttk.Frame(self.watch_page)
        actions.pack(fill="x", pady=10)
        self.detect_button = self.button(
            actions, "1  Nhận diện · 4 giây", lambda: self.launch("detect"), "Primary.TButton"
        )
        self.detect_button.pack(side="left")
        self.test_button = self.button(actions, "Thử chọn MAX / MIN", lambda: self.launch("test"))
        self.test_button.pack(side="left", padx=8)
        self.start_button = self.button(
            actions, "2  Canh reset", lambda: self.launch("watch"), "Primary.TButton"
        )
        self.start_button.pack(side="left")
        ttk.Button(actions, text="Dừng · F8", style="Danger.TButton", command=self.stop.set).pack(
            side="right"
        )
        self.start_button.configure(state="disabled")
        self.test_button.configure(state="disabled")
        self.ack_bar = ttk.Frame(self.watch_page, style="Card.TFrame", padding=10)
        ttk.Label(
            self.ack_bar,
            text="Lệnh trước chưa rõ kết quả. Kiểm tra DS của bạn trước khi chạy tiếp.",
            style="CardMuted.TLabel",
            wraplength=650,
        ).pack(side="left")
        self.button(self.ack_bar, "Đã kiểm tra lệnh trước", self.acknowledge).pack(side="right")
        ttk.Label(
            self.watch_page, textvariable=self.warning, foreground="#f1c978", wraplength=960
        ).pack(anchor="w", pady=(0, 7))
        self.logs = tk.Text(
            self.watch_page,
            height=4,
            state="disabled",
            font=("Consolas", 10),
            wrap="word",
            bg="#0d1829",
            fg="#b8cde5",
            relief="flat",
            padx=12,
            pady=10,
        )
        self.logs.pack(fill="both", expand=True)
        self.build_tax(self.tax_page)
        self.build_salary(self.salary_page, self.salary_settings_override)

    def button(self, parent, text, command, style="TButton"):
        widget = ttk.Button(parent, text=text, command=command, style=style)
        self.controls.append(widget)
        return widget

    def card(self, parent, title, subtitle=None):
        box = ttk.Frame(parent, style="Card.TFrame", padding=14)
        box.pack(fill="x", pady=(0, 12))
        ttk.Label(box, text=title, style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(
            anchor="w"
        )
        if subtitle:
            ttk.Label(box, text=subtitle, style="CardMuted.TLabel", wraplength=850).pack(
                anchor="w", pady=8
            )
        return box

    def format_limit(self):
        try:
            self.limit.set(format_bp(parse_bp(self.limit.get())))
        except ValueError:
            pass
        self.save_settings()

    def save_settings(self):
        try:
            atomic_json(
                self.settings_path,
                dict(
                    limit=self.limit.get(),
                    dry_run=self.dry.get(),
                    refresh_enabled=self.refresh_enabled.get(),
                    reset_start=self.reset_start.get(),
                    reset_duration=self.reset_duration.get(),
                ),
            )
        except OSError:
            self.warning.set("Không lưu được cài đặt trong thư mục dữ liệu.")

    def use_target(self):
        if self.bound:
            self.limit.set(format_bp(self.bound.quote.target(self.bound.side).value))

    def show_snapshot(self, snapshot):
        self.bound = snapshot
        self.name.set(f"{snapshot.name}  +{snapshot.boost}")
        self.side.set("MUA  →  CLICK MAX" if snapshot.side == "buy" else "BÁN  →  CLICK MIN")
        self.limit_label.set(
            "Giá mua tối đa (BP)" if snapshot.side == "buy" else "Giá bán tối thiểu (BP)"
        )
        self.prices.set(
            f"MIN   {format_bp(snapshot.quote.floor.value)} BP\nMAX  {format_bp(snapshot.quote.ceiling.value)} BP"
        )
        self.details.set(
            f"Số lượng: {snapshot.quantity}"
            + (f"  ·  Ô giá: {format_bp(snapshot.price)} BP" if snapshot.price else "")
        )
        self.warning.set(snapshot.error if snapshot.error else "")
        portrait = snapshot.region("card").crop(snapshot.frame)
        portrait.thumbnail((120, 155))
        self.photo = ImageTk.PhotoImage(portrait)
        self.portrait.configure(image=self.photo, text="")

    def set_busy(self, value):
        self.busy = value
        for control in self.controls:
            control.configure(state="disabled" if value else "normal")
        self.notebook.tab(1, state="disabled" if value else "normal")
        self.notebook.tab(2, state="disabled" if value else "normal")
        if not value and (not self.bound or self.bound.quantity != 1):
            self.start_button.configure(state="disabled")
            self.test_button.configure(state="disabled")

    def launch(self, action):
        if self.busy:
            return
        if action not in ("detect", "diagnose") and not self.bound:
            self.warning.set("Bấm Nhận diện hộp FCO trước.")
            return
        limit = None
        reset_window = None
        if action == "watch":
            try:
                limit = parse_bp(self.limit.get())
                if limit <= 0:
                    raise ValueError("Ngưỡng BP cần lớn hơn 0")
                try:
                    duration = int(self.reset_duration.get())
                except ValueError:
                    raise ValueError("Số giây canh cần là số nguyên từ 5 đến 1.800")
                reset_window = ResetWindow.create(self.reset_start.get(), duration)
            except ValueError as error:
                self.warning.set(str(error))
                return
        self.save_settings()
        self.stop.clear()
        try:
            controller = Desktop(self.stop)
            focused = controller.focus()
        except Exception as error:
            self.warning.set(str(error))
            return
        self.set_busy(True)
        self.status.set("Chuyển sang FCO trong 4 giây. F8 để dừng.")
        if not focused:
            self.iconify()
        dry = self.dry.get()
        reset_start_text = self.reset_start.get()
        refresh_enabled = self.refresh_enabled.get()
        bound = self.bound

        def work():
            ocr = None
            try:
                with FileLock(APP_ROOT / ".control.lock"):
                    io = controller
                    if self.stop.wait(4):
                        raise Stopped("Đã dừng")
                    ocr = OCR()
                    reader = DialogReader(ocr)
                    if action == "diagnose":
                        frame = io.capture()
                        parent = ParentReader(ocr, APP_ROOT / "diagnostics")
                        parent.orders_selected(frame.image)
                        atomic_json(APP_ROOT / "diagnostics/parent-tab.json", parent.last_report)
                        self.events.put(
                            ("status", json.dumps(parent.last_report, ensure_ascii=False))
                        )
                    elif action == "detect":
                        snapshot = io.scan(reader, exact=True)
                        self.events.put(("snapshot", snapshot))
                        self.events.put(
                            (
                                "status",
                                "Đã nhận diện. Có thể để hộp mở hoặc trở về bảng TTCN; kiểm tra ngưỡng rồi Canh reset.",
                            )
                        )
                    elif action == "test":
                        snapshot = select_price(io, reader, bound)
                        self.events.put(("snapshot", snapshot))
                        self.events.put(
                            (
                                "status",
                                f"Thử chọn giá: {format_bp(snapshot.price)} BP. Không bấm gửi lệnh.",
                            )
                        )
                    else:
                        refresher = (
                            Refresher(
                                ParentReader(ocr, APP_ROOT / "diagnostics"),
                                emit=lambda kind, data: self.events.put((kind, data)),
                            )
                            if refresh_enabled
                            else None
                        )
                        active_window = reset_window.after_setup(not reset_start_text.strip())
                        monitor(
                            io,
                            reader,
                            bound,
                            limit,
                            dry,
                            self.journal,
                            lambda kind, data: self.events.put((kind, data)),
                            refresher=refresher,
                            window=active_window,
                        )
            except Exception as error:
                diagnostic = error if isinstance(error, RecognitionError) else error.__cause__
                if isinstance(diagnostic, RecognitionError):
                    try:
                        folder = APP_ROOT / "diagnostics"
                        folder.mkdir(exist_ok=True)
                        diagnostic.crop.save(folder / "last-field.png")
                        atomic_json(
                            folder / "last-failure.json",
                            dict(field=diagnostic.field, reason=diagnostic.reason),
                        )
                    except OSError:
                        pass
                self.events.put(("error", str(error)))
            finally:
                if ocr:
                    ocr.close()
                self.events.put(("done", None))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def check_journal(self):
        try:
            record = self.journal.pending()
        except (OSError, ValueError, RuntimeError):
            record = {"state": "unverified"}
        if record and record.get("state") != "confirmed":
            self.ack_bar.pack(fill="x", before=self.logs, pady=(0, 8))
        else:
            self.ack_bar.pack_forget()

    def acknowledge(self):
        try:
            with FileLock(APP_ROOT / ".control.lock"):
                self.journal.acknowledge()
            self.check_journal()
            self.status.set("Đã lưu lịch sử lệnh trước. Có thể chạy phiên mới.")
        except (OSError, RuntimeError) as error:
            self.warning.set(str(error))

    def log(self, message):
        line = f'[{time.strftime("%H:%M:%S")}] {message}\n'
        self.logs.configure(state="normal")
        self.logs.insert("end", line)
        self.logs.see("end")
        self.logs.configure(state="disabled")
        try:
            with (APP_ROOT / "activity.log").open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            pass

    def pump(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "snapshot":
                    self.show_snapshot(data)
                elif kind == "phase":
                    self.status.set(data)
                elif kind in ("status", "error"):
                    self.status.set(data)
                    self.log(data)
                    if kind == "error":
                        self.warning.set(data)
                elif kind == "done":
                    self.set_busy(False)
                    self.check_journal()
                    if not self.closed:
                        self.deiconify()
                        self.lift()
        except queue.Empty:
            pass
        if self.closed and (not self.worker or not self.worker.is_alive()):
            self.destroy()
            return
        self.after(80, self.pump)

    def close_app(self):
        self.save_settings()
        self.save_tax_settings()
        self.save_salary_settings()
        self.stop.set()
        self.closed = True
