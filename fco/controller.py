"""UI-independent application boundary for the local desktop web interface."""

import base64
import copy
from io import BytesIO
import json
from pathlib import Path
import threading
import time
import sys

from fco.paths import APP_ROOT
from fco.calculators.salary import FORMATIONS, clean_settings, parse_salary
from fco.calculators.tax import calculate_tax, format_bp
from . import VERSION
from .desktop import Desktop, Stopped
from .dialog import DialogReader, RecognitionError
from .engine import monitor, select_price
from .ocr import OCR
from .pricing import parse_bp
from .refresh import ParentReader, Refresher
from .schedule import ResetWindow
from .storage import FileLock, Journal, atomic_json
from .updater import Updater


class DesktopAPI:
    def __init__(self, root=APP_ROOT, updates=True):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._worker = None
        self._bound = None
        self._window = None
        self._closing = False
        self._close_ready = False
        self._journal = Journal(self._root)
        self._updater = Updater(self._root, enabled=updates)
        self._state = dict(
            busy=False,
            status="Sẵn sàng nhận diện cầu thủ.",
            warning="",
            snapshot=None,
            logs=[],
            pending=False,
            revision=0,
        )
        self._check_journal()

    def _read(self, name, fallback):
        try:
            data = json.loads((self._root / name).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else fallback
        except (OSError, ValueError):
            return fallback

    def bootstrap(self):
        with self._lock:
            watch = self._read("settings.json", {})
            settings = dict(
                limit=str(watch.get("limit", "")),
                dry_run=watch.get("dry_run") is not False,
                refresh_enabled=watch.get("refresh_enabled") is not False,
                reset_start=str(watch.get("reset_start", "")),
                reset_duration=str(watch.get("reset_duration", 120)),
            )
            tax = self._read("tax-settings.json", {})
            try:
                calculate_tax(parse_bp(tax["price"]), tax["member"], tax["coupon"], tax["pc"])
            except (KeyError, ValueError, TypeError):
                tax = dict(price="", member="none", coupon=0, pc=False)
            page = self._read("ui-settings.json", {}).get("page", "salary")
            return dict(
                version=VERSION,
                formations=FORMATIONS,
                salary=clean_settings(self._read("salary-settings.json", {})),
                tax=tax,
                watch=settings,
                state=self.get_state(),
                auto_check_updates=self._updater.enabled and bool(getattr(sys, "frozen", False)),
                updates_enabled=self._updater.enabled,
                update_install_supported=bool(getattr(sys, "frozen", False)),
                page=page if page in ("salary", "tax", "watch") else "salary",
            )

    def save_page(self, page):
        if page not in ("salary", "tax", "watch"):
            raise ValueError("Trang không hợp lệ")
        with self._lock:
            atomic_json(self._root / "ui-settings.json", {"page": page})

    def save_watch(self, settings):
        if (
            not isinstance(settings, dict)
            or type(settings.get("dry_run")) is not bool
            or type(settings.get("refresh_enabled")) is not bool
        ):
            raise ValueError("Cài đặt canh giá không hợp lệ")
        with self._lock:
            atomic_json(
                self._root / "settings.json",
                {
                    key: settings[key]
                    for key in (
                        "limit",
                        "dry_run",
                        "refresh_enabled",
                        "reset_start",
                        "reset_duration",
                    )
                },
            )

    def save_salary(self, settings):
        with self._lock:
            if not isinstance(settings, dict) or settings.get("formation") not in FORMATIONS:
                raise ValueError("Sơ đồ không hợp lệ")
            squads = settings.get("squads", {})
            for formation, positions in FORMATIONS.items():
                for position, _, _ in positions:
                    parse_salary(squads.get(formation, {}).get(position, ""))
            cleaned = clean_settings(settings)
            atomic_json(self._root / "salary-settings.json", cleaned)
            return {"saved": True}

    def tax(self, settings, persist=True):
        result = calculate_tax(
            parse_bp(settings.get("price", "") or "0"),
            settings["member"],
            settings["coupon"],
            settings["pc"],
        )
        if persist:
            with self._lock:
                atomic_json(
                    self._root / "tax-settings.json",
                    dict(
                        price=settings.get("price", ""),
                        member=settings["member"],
                        coupon=settings["coupon"],
                        pc=settings["pc"],
                    ),
                )
        return dict(
            net=format_bp(result.net_bp),
            fee=format_bp(result.tax_bp),
            saved=format_bp(result.saved_bp),
            gross=format_bp(result.gross_bp),
            discount=result.discount_percent,
            rate=result.tax_basis_points / 100,
            net_raw=str(result.net_bp),
        )

    def get_state(self):
        with self._lock:
            state = copy.deepcopy(self._state)
            state["update"] = self._updater.state()
            return state

    def check_update(self):
        return self._updater.check()

    def download_update(self):
        with self._lock:
            if self._closing or self._state["busy"]:
                raise ValueError("Hãy dừng phiên canh giá trước khi cập nhật.")
            return self._updater.start_download()

    def install_update(self):
        with self._lock:
            if self._closing or self._state["busy"]:
                raise ValueError("Hãy dừng phiên canh giá trước khi cập nhật.")
            return self._updater.prepare_install()

    def restart_for_update(self):
        if self._updater.state()["status"] != "installing":
            raise ValueError("Bộ cập nhật chưa sẵn sàng.")
        if self._window:
            self._window.destroy()

    def _set(self, **values):
        with self._lock:
            self._state.update(values)
            self._state["revision"] += 1

    def _emit(self, kind, data):
        if kind == "timing":
            self._emit(
                "status",
                "Hiệu năng cục bộ: làm mới/đọc giá {round_ms:.0f} ms · "
                "chọn và xác minh BP {price_verify_ms:.0f} ms · "
                "từ xác nhận giá đổi đến bấm gửi {trigger_to_click_ms:.0f} ms.".format(**data),
            )
            return
        if kind == "snapshot":
            self._snapshot(data)
        elif kind in ("phase", "status", "error"):
            self._set(status=str(data))
            if kind == "error":
                self._set(warning=str(data))
            if kind != "phase":
                line = {
                    "time": time.strftime("%H:%M:%S"),
                    "text": str(data),
                    "error": kind == "error",
                }
                with self._lock:
                    self._state["logs"] = (self._state["logs"] + [line])[-80:]
                try:
                    with (self._root / "activity.log").open("a", encoding="utf-8") as handle:
                        handle.write(f"[{line['time']}] {line['text']}\n")
                except OSError:
                    pass

    def _snapshot(self, shot):
        self._bound = shot
        portrait = shot.region("card").crop(shot.frame)
        portrait.thumbnail((170, 220))
        buffer = BytesIO()
        portrait.save(buffer, format="PNG")
        self._set(
            snapshot=dict(
                name=shot.name,
                boost=shot.boost,
                side=shot.side,
                quantity=shot.quantity,
                floor=format_bp(shot.quote.floor.value),
                ceiling=format_bp(shot.quote.ceiling.value),
                target=format_bp(shot.quote.target(shot.side).value),
                price=format_bp(shot.price) if shot.price else "",
                portrait="data:image/png;base64,"
                + base64.b64encode(buffer.getvalue()).decode("ascii"),
            ),
            warning=shot.error or "",
        )

    def _check_journal(self):
        try:
            record = self._journal.pending()
        except (OSError, ValueError, RuntimeError):
            record = {"state": "unverified"}
        self._set(pending=bool(record and record.get("state") != "confirmed"))

    def acknowledge(self):
        with self._lock:
            if self._state["busy"]:
                raise ValueError("Dừng phiên hiện tại trước khi xác nhận.")
            with FileLock(self._root / ".control.lock"):
                self._journal.acknowledge()
            self._check_journal()
            self._set(status="Đã lưu lịch sử lệnh trước. Có thể chạy phiên mới.")
        return self.get_state()

    def stop_action(self):
        self._stop.set()
        if self._state["busy"]:
            self._set(status="Đang dừng phiên…")
        return self.get_state()

    def start_action(self, action, settings):
        with self._lock:
            if self._updater.state()["status"] in ("downloading", "preparing", "installing"):
                raise ValueError("Hãy hoàn tất cập nhật trước khi chạy phiên mới.")
            if self._closing or self._state["busy"]:
                raise ValueError("Một phiên đang chạy. Hãy dừng phiên trước.")
            if action not in ("detect", "test", "watch", "diagnose"):
                raise ValueError("Thao tác không hợp lệ")
            if action not in ("detect", "diagnose") and not self._bound:
                raise ValueError("Nhận diện cầu thủ trước khi bắt đầu.")
            if (
                type(settings.get("dry_run")) is not bool
                or type(settings.get("refresh_enabled")) is not bool
            ):
                raise ValueError("Thiếu chế độ chạy thử hoặc làm mới bảng.")
            limit = None
            reset_window = None
            if action == "watch":
                limit = parse_bp(settings.get("limit", ""))
                if limit <= 0:
                    raise ValueError("Ngưỡng BP cần lớn hơn 0")
                try:
                    duration = int(settings.get("reset_duration", ""))
                except ValueError:
                    raise ValueError("Số giây canh cần là số nguyên từ 5 đến 1.800")
                reset_window = ResetWindow.create(settings.get("reset_start", ""), duration)
            atomic_json(
                self._root / "settings.json",
                {
                    key: settings[key]
                    for key in (
                        "limit",
                        "dry_run",
                        "refresh_enabled",
                        "reset_start",
                        "reset_duration",
                    )
                },
            )
            controller = Desktop(self._stop)
            self._stop.clear()
            controller.focus()
            bound = self._bound
            self._set(busy=True, warning="", status="Chuyển sang FCO trong 4 giây. F8 để dừng.")
            self._worker = threading.Thread(
                target=self._run,
                args=(action, settings.copy(), controller, bound, limit, reset_window),
                daemon=True,
            )
            self._worker.start()
        return self.get_state()

    def _run(self, action, settings, controller, bound, limit, reset_window):
        ocr = None
        show_result = False
        try:
            with FileLock(self._root / ".control.lock"):
                if self._stop.wait(4):
                    raise Stopped("Đã dừng")
                ocr = OCR()
                reader = DialogReader(ocr)
                if action == "diagnose":
                    frame = controller.capture()
                    parent = ParentReader(ocr, self._root / "diagnostics")
                    parent.orders_selected(frame.image)
                    atomic_json(self._root / "diagnostics/parent-tab.json", parent.last_report)
                    self._emit("status", "Đã lưu chẩn đoán nhận diện tab. Không gửi lệnh.")
                elif action == "detect":
                    self._snapshot(controller.scan(reader, exact=True))
                    self._emit(
                        "status", "Đã nhận diện. Kiểm tra cầu thủ và ngưỡng giá trước khi canh."
                    )
                    show_result = True
                elif action == "test":
                    shot = select_price(controller, reader, bound)
                    self._snapshot(shot)
                    self._emit(
                        "status", f"Thử chọn giá: {format_bp(shot.price)} BP. Không bấm gửi lệnh."
                    )
                else:
                    refresher = (
                        Refresher(ParentReader(ocr, self._root / "diagnostics"), emit=self._emit)
                        if settings["refresh_enabled"]
                        else None
                    )
                    result = monitor(
                        controller,
                        reader,
                        bound,
                        limit,
                        settings["dry_run"],
                        self._journal,
                        self._emit,
                        refresher=refresher,
                        window=reset_window.after_setup(not settings["reset_start"].strip()),
                    )
                    show_result = result == "confirmed"
        except Exception as error:
            diagnostic = error if isinstance(error, RecognitionError) else error.__cause__
            if isinstance(diagnostic, RecognitionError):
                try:
                    folder = self._root / "diagnostics"
                    folder.mkdir(exist_ok=True)
                    diagnostic.crop.save(folder / "last-field.png")
                    atomic_json(
                        folder / "last-failure.json",
                        dict(field=diagnostic.field, reason=diagnostic.reason),
                    )
                except OSError:
                    pass
            self._emit("error", str(error))
        finally:
            if ocr:
                ocr.close()
            self._set(busy=False)
            self._check_journal()
            if self._window:
                if self._closing and self._close_ready:
                    self._window.destroy()
                elif not self._closing:
                    self._window.restore()
                    if show_result:
                        self._window.show()

    def _on_closing(self):
        if self._close_ready:
            return not self._state["busy"]
        if self._closing:
            return False
        self._closing = True
        self._stop.set()
        # Let the JavaScript write queue finish before closing the native window.
        # The WinForms closing callback must return before WebView can evaluate JS.
        threading.Thread(target=self._flush_close, daemon=True).start()
        return False

    def _flush_close(self):
        try:
            self._window.evaluate_js(
                "window.prepareClose ? window.prepareClose() : window.pywebview.api.finish_close()"
            )
        except Exception:
            self.finish_close()

    def finish_close(self):
        self._close_ready = True
        self._stop.set()
        if self._window and not self._state["busy"]:
            self._window.destroy()
