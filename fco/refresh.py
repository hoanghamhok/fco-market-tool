"""Close the quote dialog and reopen it through a verified parent control."""

from dataclasses import dataclass
from collections import OrderedDict
import numpy as np
from pathlib import Path
from .storage import atomic_json
from .dialog import Box, locate_dialog, NoDialog
from .ocr import normalize
from .timing import readiness_delays


def area(image, coords):
    return Box(0, 0, image.width, image.height).region(coords)


@dataclass(frozen=True)
class Entry:
    row_y: int
    boost: int


class ParentReader:
    def __init__(self, ocr, diagnostics=None):
        self.ocr = ocr
        self.diagnostics = Path(diagnostics) if diagnostics else None
        self.last_report = {}
        self._cache = OrderedDict()

    def _read(self, kind, crop, method):
        # Exact pixels only: changed text/background must be read again.
        key = (kind, crop.mode, crop.size, crop.tobytes())
        if key not in self._cache:
            value = method(crop)
            self._cache[key] = value
            if len(self._cache) > 32:
                self._cache.popitem(last=False)
        self._cache.move_to_end(key)
        return self._cache[key]

    def root(self, image):
        title = normalize(
            self._read(
                "root",
                area(image, (0.46, 0.073, 0.54, 0.111)).crop(image),
                lambda crop: self.ocr.text(crop, 60),
            )
        )
        if title != "ttcn":
            raise ValueError("Chưa trở về đúng bảng TTCN; chưa mở lại")

    def orders_selected(self, image):
        region = area(image, (0.474, 0.164, 0.558, 0.195))
        crop = region.crop(image)
        error = ""
        try:
            text = normalize(self.ocr.vietnamese(crop))
        except ValueError as problem:
            text = ""
            error = str(problem)
        line = np.asarray(area(image, (0.466, 0.198, 0.563, 0.205)).crop(image).convert("L"))
        fraction = float((line > 210).mean())
        selected = text == "dscuaban" and fraction > 0.1
        words = self.ocr.labels.last_words if self.ocr.labels else []
        self.last_report = dict(
            frame_size=list(image.size),
            text=" ".join(w for w, _ in words),
            confidences=[round(c, 2) for _, c in words],
            normalized=text,
            underline_fraction=fraction,
            error=error,
            selected=selected,
        )
        if self.diagnostics and not selected:
            self.diagnostics.mkdir(parents=True, exist_ok=True)
            crop.save(self.diagnostics / "parent-tab.png")
            area(image, (0.466, 0.198, 0.563, 0.205)).crop(image).save(
                self.diagnostics / "parent-underline.png"
            )
            atomic_json(self.diagnostics / "parent-tab.json", self.last_report)
        return selected

    def find_entry(self, image, bound):
        self.root(image)
        if not self.orders_selected(image):
            raise ValueError("Cần tab DS của bạn để đăng ký lại lệnh đang treo")
        names = area(image, (0.246, 0.239, 0.335, 0.800))
        candidates = []
        for text, (_, top, _, bottom) in self._read("names", names.crop(image), self.ocr.lines):
            if normalize(text) != normalize(bound.name):
                continue
            y = names.y + (top + bottom) // 2
            badge = Box(
                round(image.width * 0.436),
                y - round(image.height * 0.008),
                round(image.width * 0.014),
                round(image.height * 0.016),
            )
            boost = self._read("boost", badge.crop(image), lambda crop: self.ocr.number(crop, 50))
            if boost != bound.boost:
                continue
            status = Box(
                round(image.width * 0.682),
                y - round(image.height * 0.015),
                round(image.width * 0.048),
                round(image.height * 0.030),
            )
            state = normalize(self._read("state", status.crop(image), self.ocr.vietnamese))
            expected = "dangmua" if bound.side == "buy" else "dangban"
            if state != expected:
                raise ValueError("Lệnh không còn ở trạng thái đang mua/bán; đã dừng")
            candidates.append(Entry(y, boost))
        if len(candidates) != 1:
            raise ValueError("Không tìm được duy nhất một lệnh đúng tên và mức cộng; chưa mở lại")
        return candidates[0]

    def register_button(self, image, bound, entry):
        latest = self.find_entry(image, bound)
        if abs(latest.row_y - entry.row_y) > image.height * 0.01:
            raise ValueError("Vị trí dòng vừa đổi; chưa bấm")
        box = Box(
            round(image.width * 0.738),
            entry.row_y - round(image.height * 0.011),
            round(image.width * 0.038),
            round(image.height * 0.022),
        )
        text = normalize(self._read("register", box.crop(image), self.ocr.vietnamese))
        if text not in ("dangkylai", "dangkilai"):
            raise ValueError("Chưa nhận diện chắc nút Đăng ký lại; không bấm cạnh nút Hủy")
        return box.center

    def market_button(self, image, bound):
        self.root(image)
        if bound.side != "buy":
            raise ValueError("Chưa xác nhận được tab DS của bạn sau khi đóng hộp; chưa mở lại")
        box = area(image, (0.624, 0.871, 0.724, 0.915))
        text = normalize(self._read("market", box.crop(image).getchannel("G"), self.ocr.vietnamese))
        if text != "muacauthu":
            raise ValueError("Chưa thấy nút mở Mua cầu thủ trên bảng TTCN")
        rgb = np.asarray(box.crop(image).convert("RGB")).astype(np.int16)
        active = (rgb[:, :, 0] > 160) & (rgb[:, :, 0] > rgb[:, :, 1] + 50)
        if float(active.mean()) < 0.25:
            raise ValueError("Nút mở mua đang bị khóa")
        return box.center


class Refresher:
    def __init__(self, parent, emit=None):
        self.parent = parent
        self.rounds = 0
        self.emit = emit
        self.phase = "Kiểm tra bảng"

    def step(self, message):
        self.phase = message
        if self.emit:
            self.emit("phase", f"Vòng {self.rounds+1}: {message}")

    def cycle(self, io, reader, bound):
        try:
            return self._cycle(io, reader, bound)
        except ValueError as error:
            raise RuntimeError(f"{self.phase}: {error}") from error

    def _cycle(self, io, reader, bound):
        self.step("Kiểm tra hộp hoặc bảng TTCN")
        frame = io.capture()
        try:
            locate_dialog(frame.image)
        except NoDialog:
            # A recognized binding may resume from its parent without a blind Esc.
            self.parent.root(frame.image)
            closed = False
        else:
            io.scan(reader, bound)
            self.step("Bấm Esc để đóng hộp")
            io.escape()
            for delay in readiness_delays(0.96):
                io.wait(delay)
                frame = io.capture()
                try:
                    locate_dialog(frame.image)
                except NoDialog:
                    try:
                        self.parent.root(frame.image)
                    except ValueError:
                        continue
                    break
            else:
                raise RuntimeError(
                    "Esc chưa đưa về bảng TTCN. Game có thể chưa nhận phím; kiểm tra quyền Run as administrator."
                )
            closed = True
        self.step("Tìm nút mở lại đúng cầu thủ")
        # Esc removes the modal before the parent tab/underline finishes fading in.
        # A negative OCR result is inconclusive: wait rather than choose another route.
        last = None
        for _ in range(20):
            try:
                self.parent.root(frame.image)
                if self.parent.orders_selected(frame.image):
                    route = "orders"
                    break
                point = self.parent.market_button(frame.image, bound)
                route = "market"
                break
            except ValueError as error:
                last = error
            io.wait(0.08)
            frame = io.capture()
        else:
            raise ValueError("Bảng TTCN chưa sẵn sàng sau khi đọc lại: " + str(last))
        if route == "orders":
            entry = self.parent.find_entry(frame.image, bound)
            io.move_point(frame, round(frame.image.width * 0.64), entry.row_y)
            last = None
            for delay in readiness_delays(0.96):
                io.wait(delay)
                hover = io.capture()
                try:
                    point = self.parent.register_button(hover.image, bound, entry)
                    break
                except ValueError as error:
                    last = error
            else:
                raise ValueError("Không đọc được nút Đăng ký lại sau khi rê chuột: " + str(last))
            self.step("Mở lại bằng Đăng ký lại")
            io.click_point(hover, *point)
        else:
            self.step("Mở lại bằng Mua cầu thủ")
            io.click_point(frame, *point)
        self.step("Chờ hộp mở và kiểm tra lại thẻ / MIN / MAX")
        last = None
        for delay in readiness_delays(1.2):
            io.wait(delay)
            try:
                reopened = io.scan(reader, bound)
                self.rounds += 1
                if self.emit:
                    route = "Esc → mở lại" if closed else "Mở từ bảng TTCN"
                    self.emit(
                        "status",
                        f"Vòng {self.rounds}: {route} OK · MIN {reopened.quote.floor.value:,} · MAX {reopened.quote.ceiling.value:,}",
                    )
                return reopened
            except ValueError as error:
                last = error
                # If a dialog opened with another card/type, never interact with it.
                if "đã đổi" in str(error):
                    raise
        raise RuntimeError("Chưa mở lại đúng hộp sau khi làm mới: " + str(last))
