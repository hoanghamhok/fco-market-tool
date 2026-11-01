from pathlib import Path
import sys
import traceback
from tempfile import TemporaryDirectory
from PIL import Image, ImageOps
from fco.paths import RESOURCE_ROOT
from fco.calculators.tax import calculate_tax
from fco.dialog import DialogReader
from fco.ocr import OCR, normalize
from fco.refresh import ParentReader
from fco.storage import atomic_json
from fco import VERSION


def run_self_test(path):
    report = {"version": VERSION, "frozen": bool(getattr(sys, "frozen", False)), "dialogs": []}
    ocr = None
    try:
        ocr = OCR()
        reported_tab = Image.open(RESOURCE_ROOT / "assets/fixtures/sample-tab-buy-raw.png").convert(
            "RGB"
        )
        assert normalize(ocr.tab(reported_tab)) == "muathuong"
        report["reported_buy_tab"] = {
            "text": "Mua thường",
            "confidences": [round(conf, 2) for _, conf in ocr.labels.last_words],
        }
        for fixture, side, expected in [
            ("buy", "buy", 8070000000),
            ("sell", "sell", 16400000000),
            ("buy-nedved", "buy", 16400000000),
            ("buy-zambrotta", "buy", 770000000),
        ]:
            image = Image.open(RESOURCE_ROOT / "assets/fixtures" / f"sample-{fixture}.png").convert(
                "RGB"
            )
            reader = DialogReader(ocr)
            shot = reader.read(image, exact=True)
            assert shot.side == side and shot.price == expected and shot.quantity == 1
            assert shot.enabled == (fixture in ("sell", "buy-zambrotta"))
            assert reader.read(image, bound=shot, exact=True).price == expected
            report["dialogs"].append(
                dict(
                    fixture=fixture,
                    side=side,
                    price_bp=shot.price,
                    boost=shot.boost,
                    quantity=shot.quantity,
                    enabled=shot.enabled,
                )
            )
        parent = ParentReader(ocr)
        reference = Image.open(RESOURCE_ROOT / "assets/fixtures/sample-orders-3.2.2.png").convert(
            "RGB"
        )
        raw = ImageOps.expand(reference, border=8, fill="black")
        assert not parent.orders_selected(raw)
        assert parent.orders_selected(raw.crop((8, 8, 1928, 1040)))
        report["invisible_border_regression"] = {
            "raw_size": list(raw.size),
            "visible_size": list(reference.size),
            "corrected_tab": True,
        }
        image = Image.open(RESOURCE_ROOT / "assets/fixtures/sample-orders-hover.png").convert("RGB")
        sell = reader.read(
            Image.open(RESOURCE_ROOT / "assets/fixtures/sample-sell.png").convert("RGB")
        )
        entry = parent.find_entry(image, sell)
        assert parent.register_button(image, sell, entry) == (1453, 278)
        buy = reader.read(
            Image.open(RESOURCE_ROOT / "assets/fixtures/sample-buy-nedved.png").convert("RGB")
        )
        assert parent.market_button(
            Image.open(RESOURCE_ROOT / "assets/fixtures/sample-buy-parent.png").convert("RGB"), buy
        ) == (1294, 921)
        report["refresh_controls"] = ["Đăng ký lại", "Mua cầu thủ"]
        from .web_self_test import run_web_self_test

        Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=Path(path).resolve().parent) as folder:
            report["desktop_ui"] = run_web_self_test(Path(folder), snapshot=shot)
        report["gui_tabs"] = 3
        assert calculate_tax(7600000000000, "svip", 30).net_bp == 6384000000000
        report["tax_example_bp"] = 6384000000000
        report["ok"] = True
    except Exception:
        report.update(ok=False, error=traceback.format_exc())
    finally:
        if ocr:
            ocr.close()
    atomic_json(Path(path), report)
    return 0 if report["ok"] else 1
