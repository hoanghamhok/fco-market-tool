"""Offline OCR benchmark; never captures the desktop or sends game input.

Run from the project root: python -m scripts.benchmark
"""

import json
from pathlib import Path
import statistics
import time

from PIL import Image

from fco.dialog import DialogReader
from fco.ocr import OCR
from fco.paths import RESOURCE_ROOT
from fco.refresh import ParentReader


def main():
    ocr = OCR()
    try:
        fixtures = RESOURCE_ROOT / "assets/fixtures"
        bound = DialogReader(ocr).read(Image.open(fixtures / "sample-sell.png").convert("RGB"))
        image = Image.open(fixtures / "sample-orders-hover.png").convert("RGB")
        parent = ParentReader(ocr)
        times = []
        for _ in range(8):
            start = time.perf_counter()
            parent.root(image)
            assert parent.orders_selected(image)
            entry = parent.find_entry(image, bound)
            assert parent.register_button(image, bound, entry) == (1453, 278)
            times.append((time.perf_counter() - start) * 1000)
        result = dict(
            scenario="verified parent row and register button, identical fixture, 8 rounds",
            cold_ms=round(times[0], 2),
            warm_median_ms=round(statistics.median(times[1:]), 2),
            rounds_ms=[round(value, 2) for value in times],
            scope="Offline OCR only. Excludes capture, network, server and game rendering latency.",
        )
        report = Path("reports/performance-after.json")
        report.parent.mkdir(exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        ocr.close()


if __name__ == "__main__":
    main()
