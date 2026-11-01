"""Integer BP arithmetic. Abbreviated labels are never final order prices."""

from dataclasses import dataclass
from decimal import Decimal
import re


def parse_bp(text):
    text = text.strip().removesuffix(" BP").strip()
    if re.fullmatch(r"[0-9]+", text):
        return int(text)
    if (
        re.fullmatch(r"[0-9]{1,3}([,. ][0-9]{3})+", text)
        and len(set(re.findall(r"[^0-9]", text))) == 1
    ):
        return int(re.sub(r"[^0-9]", "", text))
    raise ValueError("Nhập số BP đầy đủ, ví dụ 10.000.000.000")


@dataclass(frozen=True)
class PriceLabel:
    value: int
    quantum: int = 1

    def contains(self, exact):
        return exact > 0 and abs(exact - self.value) < self.quantum


def parse_label(text):
    match = re.fullmatch(r"([0-9]+(?:[.,][0-9]+)?)\s*([KMBT])", text.strip(), re.I)
    if not match:
        value = parse_bp(text)
        if value <= 0:
            raise ValueError("Giá phải lớn hơn 0")
        return PriceLabel(value)
    number, suffix = match.groups()
    number = number.replace(",", ".")
    multiplier = {"K": 10**3, "M": 10**6, "B": 10**9, "T": 10**12}[suffix.upper()]
    value = Decimal(number) * multiplier
    if value <= 0 or value != value.to_integral_value():
        raise ValueError("Không đọc được giá rút gọn")
    decimals = len(number.partition(".")[2])
    return PriceLabel(int(value), max(1, multiplier // 10**decimals))


@dataclass(frozen=True)
class Quote:
    floor: PriceLabel
    ceiling: PriceLabel

    def __post_init__(self):
        if self.floor.value > self.ceiling.value:
            raise ValueError("Giá tối thiểu lớn hơn giá tối đa")

    def target(self, side):
        if side not in ("buy", "sell"):
            raise ValueError("Không nhận diện được Mua/Bán")
        return self.ceiling if side == "buy" else self.floor


def permits(side, exact, limit):
    if type(exact) is not int or type(limit) is not int or exact <= 0 or limit <= 0:
        return False
    return exact <= limit if side == "buy" else exact >= limit if side == "sell" else False


def may_qualify(side, label, limit):
    if side == "buy":
        return label.value - label.quantum + 1 <= limit
    if side == "sell":
        return label.value + label.quantum - 1 >= limit
    return False


class ChangeDetector:
    """Require two consecutive changed quotes, with a stable initial baseline."""

    def __init__(self):
        self.baseline = self.candidate = None
        self.count = 0

    def observe(self, quote):
        self.count = self.count + 1 if quote == self.candidate else 1
        self.candidate = quote
        if self.count < 2:
            return False
        if self.baseline is None:
            self.baseline = quote
            return False
        if self.baseline == quote:
            return False
        self.baseline = quote
        return True

    def invalidate(self):
        self.candidate, self.count = None, 0
