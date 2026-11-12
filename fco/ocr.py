import unicodedata
import re
from PIL import ImageOps, ImageStat
from PIL import Image
import numpy as np
import cv2
from tesserocr import PyTessBaseAPI, PSM, OEM, RIL
from fco.paths import RESOURCE_ROOT
from .pricing import parse_bp, parse_label


def normalize(text):
    text = unicodedata.normalize("NFKD", text).replace("đ", "d").replace("Đ", "D")
    return re.sub(
        r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c)).lower()
    )


def isolate_line(image):
    """Crop the glyph run, excluding badge edges and tab underlines."""
    gray = np.asarray(image.convert("L"))
    mask = (gray < 105).astype("uint8") * 255
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    components = []
    for x, y, width, height, area in stats[1:]:
        if height >= max(5, image.height * 0.22) and width >= 3 and area >= 8:
            if width > image.width * 0.7 and height < image.height * 0.3:
                continue
            components.append((int(x), int(y), int(width), int(height)))
    if not components:
        raise ValueError("Không tách được dòng chữ")
    left = min(x for x, y, w, h in components)
    top = min(y for x, y, w, h in components)
    right = max(x + w for x, y, w, h in components)
    bottom = max(y + h for x, y, w, h in components)
    return ImageOps.expand(image.crop((left, top, right, bottom)), border=5, fill="white")


class OCR:
    def __init__(self, language="eng"):
        self.labels = None
        self.api = PyTessBaseAPI(
            path=str(RESOURCE_ROOT / "vendor/tessdata"),
            lang=language,
            psm=PSM.SINGLE_LINE,
            oem=OEM.LSTM_ONLY,
        )
        self.api.SetVariable("classify_enable_learning", "0")

    def text(self, image, minimum=65, block=False, digits=False):
        self.last_words = []
        if image.width < 3 or image.height < 3 or image.width > 3000 or image.height > 900:
            raise ValueError("Vùng đọc không hợp lệ")
        image = ImageOps.grayscale(image)
        if ImageStat.Stat(image).mean[0] < 127:
            image = ImageOps.invert(image)
        scale = min(3, max(1, round(100 / image.height))) if not block else 2
        image = ImageOps.autocontrast(image).resize((image.width * scale, image.height * scale))
        image = ImageOps.expand(image, border=12, fill="white")
        self.api.Clear()
        self.api.SetPageSegMode(PSM.SINGLE_BLOCK if block else PSM.SINGLE_LINE)
        self.api.SetVariable("tessedit_char_whitelist", "0123456789" if digits else "")
        self.api.SetImage(image)
        if not self.api.Recognize(timeout=2500):
            raise ValueError("OCR quá thời gian")
        iterator, words = self.api.GetIterator(), []
        if iterator:
            while True:
                try:
                    word = iterator.GetUTF8Text(RIL.WORD)
                except RuntimeError:
                    break
                if word and word.strip():
                    words.append((word.strip(), iterator.Confidence(RIL.WORD)))
                if not iterator.Next(RIL.WORD):
                    break
        self.last_words = words
        if not words or any(conf < minimum for _, conf in words):
            raise ValueError("Ảnh chữ chưa đủ rõ; hãy để nguyên hộp và thử nhận diện lại")
        return " ".join(text for text, _ in words)

    def price(self, image):
        # Both focused blue and unfocused gray selections have white digits.
        rgb = np.asarray(image.convert("RGB")).astype(np.int16)
        gray = np.asarray(ImageOps.grayscale(image)).copy()
        blue = (rgb[:, :, 2] - rgb[:, :, 0] > 35) & (rgb[:, :, 1] - rgb[:, :, 0] > 15)
        neutral = rgb.max(axis=2) - rgb.min(axis=2) < 20
        selected_gray = neutral & (gray > 70) & (gray < 175)
        for selection in (blue, selected_gray):
            _, _, stats, _ = cv2.connectedComponentsWithStats(selection.astype("uint8") * 255, 8)
            for left, top, width, height, area in stats[1:]:
                if width < 10 or height < image.height * 0.45 or area < width * height * 0.3:
                    continue
                right, bottom = left + width, top + height
                part = rgb[top:bottom, left:right]
                letters = part.min(axis=2) > 220
                if letters.sum() < 3:
                    continue
                gray[top:bottom, left:right] = np.where(letters, 0, 255)
        # Keep the right-aligned digit run; an isolated mouse cursor at the
        # empty left side of the field must not become a minus/underscore.
        active = np.where((gray < 105).sum(axis=0) >= 2)[0]
        if len(active):
            gaps = np.where(np.diff(active) > max(9, image.height * 0.45))[0]
            left = int(active[gaps[-1] + 1]) if len(gaps) else int(active[0])
            gray = gray[:, max(0, left - 4) : min(gray.shape[1], int(active[-1]) + 5)]
        return parse_bp(self.text(Image.fromarray(gray), 85))

    def label(self, image):
        return parse_label(self.text(image, 85))

    def tab(self, image):
        last = None
        attempts = [image]
        try:
            line = isolate_line(image)
            attempts.extend(
                [line, ImageOps.grayscale(line).point(lambda pixel: 255 if pixel > 145 else 0)]
            )
        except ValueError:
            pass
        allowed = {"muathuong", "bantungcanhan"}
        for read in (lambda crop: self.vietnamese(crop, 75), lambda crop: self.text(crop, 65)):
            for attempt in attempts:
                try:
                    text = read(attempt)
                    if normalize(text) not in allowed:
                        raise ValueError("Không đọc chắc nhãn Mua thường / Bán từng cá nhân")
                    return text
                except ValueError as error:
                    last = error
        raise last

    def number(self, image, minimum=80, badge=False):
        last = None
        if badge:
            # Card grades can use orange/colored backgrounds. A grayscale OCR
            # pass can mistake the background and border for a letter. Keep
            # only the dark connected glyphs before reading the number.
            gray = np.asarray(ImageOps.grayscale(image))
            mask = (gray < 100).astype("uint8") * 255
            _, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
            glyphs = [
                (int(x), int(y), int(width), int(height))
                for x, y, width, height, area in stats[1:]
                if area >= 8
                and height >= max(5, image.height * 0.25)
                and width >= 2
                and x > image.width * 0.08
                and x + width < image.width * 0.9
            ]
            if glyphs:
                left = min(x for x, _, _, _ in glyphs)
                top = min(y for _, y, _, _ in glyphs)
                right = max(x + width for x, _, width, _ in glyphs)
                bottom = max(y + height for _, y, _, height in glyphs)
                isolated_mask = np.where(mask[top:bottom, left:right], 0, 255).astype("uint8")
                glyph_image = ImageOps.expand(Image.fromarray(isolated_mask), border=5, fill=255)
                try:
                    text = self.text(glyph_image, max(minimum, 80))
                    match = re.fullmatch(r"[\W_]*([0-9]{1,2})[\W_]*", text.strip())
                    if match:
                        return int(match.group(1))
                except ValueError as error:
                    last = error
        # Small boost badges often include a border or dropdown arrow. Reading
        # only the glyphs first is both quicker and more reliable for one digit.
        try:
            isolated = isolate_line(image)
        except ValueError:
            isolated = None
        for attempt, digits in ((isolated, False), (isolated, True), (image, False)):
            if attempt is None:
                continue
            try:
                text = self.text(attempt, minimum, digits=digits)
                match = re.fullmatch(r"[\W_]*([0-9]{1,2})[\W_]*", text.strip())
                if not match:
                    raise ValueError("Không đọc rõ số lượng / mức cộng")
                return int(match.group(1))
            except ValueError as error:
                last = error
        raise last

    def lines(self, image):
        """OCR text-line boxes mapped back to the original crop coordinates."""
        gray = ImageOps.grayscale(image)
        if ImageStat.Stat(gray).mean[0] < 127:
            gray = ImageOps.invert(gray)
        rendered = ImageOps.expand(
            ImageOps.autocontrast(gray).resize((image.width * 2, image.height * 2)),
            border=12,
            fill="white",
        )
        self.api.Clear()
        self.api.SetPageSegMode(PSM.SINGLE_BLOCK)
        self.api.SetVariable("tessedit_char_whitelist", "")
        self.api.SetImage(rendered)
        if not self.api.Recognize(timeout=2500):
            raise ValueError("Không đọc được danh sách cầu thủ")
        iterator = self.api.GetIterator()
        result = []
        if iterator:
            while True:
                try:
                    text = iterator.GetUTF8Text(RIL.TEXTLINE)
                except RuntimeError:
                    break
                bbox = iterator.BoundingBox(RIL.TEXTLINE)
                if text and text.strip() and bbox:
                    result.append((text.strip(), tuple(round((value - 12) / 2) for value in bbox)))
                if not iterator.Next(RIL.TEXTLINE):
                    break
        return result

    def vietnamese(self, image, minimum=75):
        if self.labels is None:
            self.labels = OCR("vie")
        return self.labels.text(image, minimum)

    def close(self):
        if self.labels:
            self.labels.close()
        self.api.End()
