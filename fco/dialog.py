"""Locate the game dialog and derive its fields relative to that dialog."""

from dataclasses import dataclass
import cv2
import numpy as np
from PIL import Image
from .ocr import normalize
from .pricing import Quote


class RecognitionError(ValueError):
    def __init__(self, field, crop, reason):
        names = {
            "title": "Tiêu đề hộp",
            "tab": "Tab Mua thường / Bán từng cá nhân",
            "name": "Tên cầu thủ",
            "boost": "Mức cộng của thẻ",
            "floor": "Giá MIN",
            "ceiling": "Giá MAX",
            "quantity": "Số lượng",
            "price": "Giá BP đầy đủ",
            "error": "Thông báo trong game",
        }
        self.field = field
        self.crop = crop
        self.reason = reason
        super().__init__(
            f"{names.get(field,field)}: không đọc rõ. Tool chưa gửi lệnh; hãy giữ nguyên hộp và nhận diện lại."
        )


class NoDialog(ValueError):
    """No modal found; distinguish this from an ambiguous or unreadable modal."""


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    width: int
    height: int

    def crop(self, image):
        return image.crop((self.x, self.y, self.x + self.width, self.y + self.height))

    @property
    def center(self):
        return self.x + self.width // 2, self.y + self.height // 2

    def region(self, coordinates):
        l, t, r, b = coordinates
        return Box(
            self.x + round(l * self.width),
            self.y + round(t * self.height),
            round((r - l) * self.width),
            round((b - t) * self.height),
        )


PROFILES = {
    "buy": {
        "tab": (0.068, 0.102, 0.219, 0.147),
        "name": (0.375, 0.202, 0.522, 0.259),
        "boost": (0.532, 0.214, 0.559, 0.250),
        "floor": (0.870, 0.341, 0.941, 0.386),
        "ceiling": (0.870, 0.394, 0.941, 0.439),
        "price": (0.623, 0.513, 0.931, 0.579),
        "quantity": (0.875, 0.622, 0.906, 0.677),
    },
    "sell": {
        "tab": (0.068, 0.102, 0.219, 0.147),
        "name": (0.375, 0.214, 0.522, 0.277),
        "boost": (0.104, 0.436, 0.137, 0.462),
        "floor": (0.870, 0.367, 0.941, 0.412),
        "ceiling": (0.870, 0.420, 0.941, 0.465),
        "price": (0.623, 0.590, 0.931, 0.654),
        "quantity": (0.875, 0.687, 0.906, 0.746),
    },
}
COMMON = {
    "title": (0.06, 0.028, 0.29, 0.083),
    "card": (0.062, 0.194, 0.266, 0.574),
    "submit": (0.629, 0.883, 0.779, 0.934),
    "error": (0.77, 0.837, 0.938, 0.879),
}


def locate_dialog(image):
    scale = min(1, 1000 / image.width)
    small = np.asarray(
        image.resize((round(image.width * scale), round(image.height * scale))).convert("RGB")
    )
    mask = ((small.min(axis=2) > 224) & ((small.max(axis=2) - small.min(axis=2)) < 28)).astype(
        "uint8"
    ) * 255
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates = []
    for x, y, w, h, area in stats[1:]:
        if (
            w > small.shape[1] * 0.35
            and h > small.shape[0] * 0.4
            and 1.35 < w / h < 2.1
            and area > w * h * 0.55
        ):
            candidates.append(
                (
                    int(area),
                    Box(round(x / scale), round(y / scale), round(w / scale), round(h / scale)),
                )
            )
    if not candidates:
        raise NoDialog("Chưa thấy hộp Mua thường / Bán từng cá nhân. Hãy mở hộp trong FCO.")
    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) > 1 and candidates[1][0] > candidates[0][0] * 0.8:
        raise ValueError("Có nhiều hộp giống nhau; chưa thể chọn chính xác")
    return candidates[0][1]


def image_signature(image):
    array = np.asarray(image.convert("L").resize((40, 56)), dtype=np.float32)
    return array


def same_card(first, second):
    diff = np.abs(first - second)
    return float(diff.mean()) < 15 and float((diff > 45).mean()) < 0.13


def button_enabled(image, side):
    rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    if side == "buy":
        active = (
            (rgb[:, :, 0] > 170)
            & (rgb[:, :, 0] > rgb[:, :, 1] + 60)
            & (rgb[:, :, 0] > rgb[:, :, 2] + 60)
        )
    elif side == "sell":
        active = (rgb[:, :, 2] > 145) & (rgb[:, :, 2] > rgb[:, :, 0] + 55) & (rgb[:, :, 1] > 65)
    else:
        raise ValueError("Không xác định được loại nút mua/bán")
    return float(active.mean()) > 0.32


@dataclass
class Snapshot:
    frame: Image.Image
    box: Box
    side: str
    name: str
    boost: int
    quote: Quote
    quantity: int
    price: int | None
    enabled: bool
    error: str
    card: np.ndarray
    origin: tuple = (0, 0)

    def region(self, key):
        return self.box.region((PROFILES[self.side] | COMMON)[key])

    @property
    def identity(self):
        return self.side, normalize(self.name), self.boost


class DialogReader:
    def __init__(self, ocr):
        self.ocr = ocr
        self.cache = {}

    def read(self, image, bound=None, exact=False):
        box = locate_dialog(image)
        self.cache = self.cache if len(self.cache) < 40 else {}

        def cached(key, area, method, field_name=None):
            crop = area.crop(image)
            signature = (key, crop.size, hash(crop.tobytes()))
            if signature not in self.cache:
                try:
                    self.cache[signature] = method(crop)
                except ValueError as error:
                    raise RecognitionError(field_name or key, crop, str(error)) from error
            return self.cache[signature]

        if bound is None:
            title = cached(
                "title", box.region(COMMON["title"]), lambda crop: normalize(self.ocr.text(crop))
            )
            side = "buy" if "mua" in title else "sell" if "ban" in title else None
            if side is None:
                raise ValueError("Không xác định được hộp Mua/Bán")
        else:
            # Detection already established the dialog type. During refresh the
            # title can be blurred mid-animation, while the selected tab and
            # player/card fields below still verify the binding on every frame.
            side = bound.side
        fields = PROFILES[side] | COMMON

        def field(key, method):
            return cached(side + key, box.region(fields[key]), method, key)

        tab = field("tab", lambda crop: normalize(self.ocr.tab(crop)))
        if tab != ("muathuong" if side == "buy" else "bantungcanhan"):
            raise ValueError("Hãy chọn Mua thường hoặc Bán từng cá nhân")
        # Require the selected tab underline at the expected first-tab position.
        line = box.region((0.069, 0.145, 0.214, 0.151)).crop(image).convert("L")
        if np.mean(np.asarray(line) < 100) < 0.12:
            raise ValueError("Tab thường chưa được chọn")
        name = field("name", lambda crop: self.ocr.text(crop, 0))
        if len(normalize(name)) < 3:
            raise ValueError("Không đọc rõ tên cầu thủ")
        boost = field("boost", lambda crop: self.ocr.number(crop, 50, badge=True))
        if not 1 <= boost <= 13:
            raise ValueError("Không đọc rõ mức cộng của thẻ")
        quote = Quote(field("floor", self.ocr.label), field("ceiling", self.ocr.label))
        quantity = field("quantity", self.ocr.number)
        card = image_signature(box.region(COMMON["card"]).crop(image))
        if bound is not None and (
            (side, normalize(name), boost) != bound.identity or not same_card(bound.card, card)
        ):
            raise ValueError("Cầu thủ, mức cộng hoặc hộp thoại đã đổi. Hãy nhận diện lại.")
        enabled = button_enabled(box.region(COMMON["submit"]).crop(image), side)
        error = ""
        if not enabled:
            try:
                text = field("error", lambda crop: normalize(self.ocr.text(crop, 20)))
                error = (
                    "Không đủ BP"
                    if "bp" in text and ("kh" in text or "du" in text or "di" in text)
                    else "Nút gửi đang bị khóa"
                )
            except ValueError:
                error = "Nút gửi đang bị khóa"
        price = field("price", self.ocr.price) if exact else None
        return Snapshot(image, box, side, name, boost, quote, quantity, price, enabled, error, card)
