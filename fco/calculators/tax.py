"""FC Online fee estimate with integer BP arithmetic only."""

from dataclasses import dataclass

MEMBER_DISCOUNTS = {"none": 0, "vip": 10, "svip": 30}
COUPON_CHOICES = (0, 10, 20, 30, 35, 40)


@dataclass(frozen=True)
class TaxResult:
    gross_bp: int
    base_tax_bp: int
    saved_bp: int
    tax_bp: int
    net_bp: int
    discount_percent: int
    tax_basis_points: int


def calculate_tax(price_bp: int, member="none", coupon_percent=0, pc=False) -> TaxResult:
    """40% base fee. Discounts add on the fee and cap at 100%.

    Fractional final BP are discarded in net proceeds. This is a basic
    estimate; coupon eligibility/maximum rebates are not inferred.
    """
    if type(price_bp) is not int or price_bp < 0:
        raise ValueError("Giá bán phải là số BP nguyên không âm")
    if member not in MEMBER_DISCOUNTS:
        raise ValueError("Chọn Không có VIP, VIP hoặc SVIP")
    if type(coupon_percent) is not int or not 0 <= coupon_percent <= 100:
        raise ValueError("Coupon phải trong khoảng 0–100%")
    if type(pc) is not bool:
        raise ValueError("Quyền lợi PC phải là bật hoặc tắt")
    discount = min(100, MEMBER_DISCOUNTS[member] + coupon_percent + (30 if pc else 0))
    basis_points = 40 * (100 - discount)
    net = price_bp * (10000 - basis_points) // 10000
    tax = price_bp - net
    base_tax = price_bp - price_bp * 60 // 100
    return TaxResult(price_bp, base_tax, base_tax - tax, tax, net, discount, basis_points)


def format_bp(value: int) -> str:
    return f"{value:,}".replace(",", ".")
