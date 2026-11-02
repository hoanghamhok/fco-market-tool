"""One binding, one changed price, one final click. No setup coordinates."""

import time
from .pricing import ChangeDetector, may_qualify, permits
from .ocr import normalize
from .schedule import now_vn


def verify(snapshot, trigger, limit):
    if snapshot.quantity != 1:
        raise RuntimeError("Chỉ hỗ trợ số lượng 1; hãy đổi trong game rồi nhận diện lại")
    if snapshot.quote != trigger.quote:
        raise RuntimeError("MIN/MAX vừa đổi tiếp; dừng để tránh gửi giá cũ")
    target = snapshot.quote.target(snapshot.side)
    if snapshot.price is None or not target.contains(snapshot.price):
        raise RuntimeError("Ô giá chưa về đúng MIN/MAX; game chưa nhận click hoặc ảnh chưa rõ")
    if not permits(snapshot.side, snapshot.price, limit):
        raise RuntimeError("Giá BP đầy đủ không đạt ngưỡng; chưa gửi")
    if not snapshot.enabled:
        raise RuntimeError(snapshot.error or "Nút gửi đang bị khóa")


def select_price(io, reader, bound, limit=None, current=None):
    # Reuse the just-confirmed reset frame so MAX/MIN is the next action.
    if current is None:
        current = io.scan(reader, bound)
    if current.quantity != 1:
        raise RuntimeError("Hãy chọn số lượng 1 trong game")
    io.click(current, "ceiling" if current.side == "buy" else "floor")
    deadline = time.monotonic() + 0.8
    last = RuntimeError("Game chưa điền giá MIN/MAX sau khi bấm; chưa gửi gì")
    # Read as soon as the game paints the chosen price; never click MAX twice.
    for _ in range(15):
        io.wait(0.02)
        try:
            first = io.scan(reader, bound, exact=True)
        except ValueError as error:
            if "đã đổi" in str(error):
                raise
            last = error
        else:
            if first.quantity != 1:
                raise RuntimeError("Số lượng không còn là 1; chưa gửi")
            if first.quote != current.quote:
                raise RuntimeError("MIN/MAX vừa đổi tiếp; chưa gửi giá cũ")
            if current.quote.target(current.side).contains(first.price or 0):
                if limit is not None:
                    verify(first, current, limit)
                break
        if time.monotonic() >= deadline:
            raise last
    else:
        raise last
    # Two full-price reads must agree before the one final click is allowed.
    io.wait(0.03)
    second = io.scan(reader, bound, exact=True)
    if first.price != second.price:
        raise RuntimeError("Ô giá đang thay đổi; chưa gửi")
    if second.quantity != 1 or second.quote != current.quote:
        raise RuntimeError("Số lượng hoặc MIN/MAX vừa đổi; chưa gửi")
    if limit is not None:
        verify(second, current, limit)
    return second


def wait_result(io, reader, bound, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = io.capture()
        # Search the transient center message only. No hand-captured success template.
        try:
            image = frame.image
            crop = image.crop(
                (
                    round(image.width * 0.27),
                    round(image.height * 0.25),
                    round(image.width * 0.83),
                    round(image.height * 0.78),
                )
            )
            text = normalize(reader.ocr.text(crop, 25, block=True))
            if "thanhcong" in text and ("dangky" in text or "dangki" in text):
                return "confirmed"
        except ValueError:
            pass
        io.wait(0.15)
    return "unverified"


def monitor(
    io, reader, bound, limit, dry_run, journal, emit, refresher=None, window=None, clock=now_vn
):
    if type(limit) is not int or limit <= 0:
        raise ValueError("Nhập ngưỡng BP lớn hơn 0")
    previous = journal.pending()
    if not dry_run and previous:
        if previous.get("state") == "confirmed":
            journal.acknowledge()
        else:
            raise RuntimeError(
                "Lệnh trước chưa rõ kết quả. Kiểm tra DS của bạn rồi bấm Đã kiểm tra lệnh trước."
            )
    detector = ChangeDetector()
    detector.baseline = bound.quote
    last = None
    unchanged_since = time.monotonic()
    warned = False
    errors = 0
    announced_wait = False
    if refresher is not None:
        io.require_input()
    emit(
        "status",
        (
            "Bắt đầu Esc → mở lại liên tục; chỉ gửi khi giá đổi và đạt ngưỡng."
            if refresher is not None
            else "Đang lấy giá ban đầu; chỉ xử lý khi MIN/MAX đổi"
        ),
    )
    while True:
        if window is not None:
            state = window.state(clock())
            if state == "ended":
                emit("status", "Hết khung giờ canh; chưa gửi lệnh.")
                return "expired"
            if state == "waiting":
                if not announced_wait:
                    emit("status", "Đang chờ " + window.label)
                    announced_wait = True
                io.wait(0.25)
                continue
        try:
            round_started = time.perf_counter()
            current = (
                refresher.cycle(io, reader, bound)
                if refresher is not None
                else io.scan(reader, bound)
            )
            round_ms = (time.perf_counter() - round_started) * 1000
        except ValueError as error:
            detector.invalidate()
            errors += 1
            if errors >= 3:
                raise
            io.wait(0.12)
            continue
        errors = 0
        if current.quantity != 1:
            raise RuntimeError("Số lượng không còn là 1; đã dừng")
        if current.quote != last:
            emit("snapshot", current)
            last = current.quote
            unchanged_since = time.monotonic()
            warned = False
        if not warned and time.monotonic() - unchanged_since > 45:
            emit(
                "status",
                (
                    "Đang Esc → mở lại; MIN/MAX chưa đổi."
                    if refresher is not None
                    else "Giá chưa đổi. Hộp cần được game làm mới để hiển thị giá mới nhất."
                ),
            )
            warned = True
        changed = detector.observe(current.quote)
        if refresher is not None and (changed or current.quote != detector.baseline):
            # Confirm in the newly opened dialog, without an extra close/open cycle.
            io.wait(0.02)
            confirmed = io.scan(reader, bound)
            if confirmed.quote != current.quote:
                detector.invalidate()
                continue
            changed = detector.observe(confirmed.quote) or changed
            current = confirmed
            if refresher.rounds % 10 == 0:
                emit("status", f"Đã làm mới {refresher.rounds} vòng; đang chờ giá đổi")
        if window is not None and window.state(clock()) != "active":
            emit("status", "Hết khung giờ canh; chưa gửi lệnh.")
            return "expired"
        if changed and may_qualify(current.side, current.quote.target(current.side), limit):
            if dry_run:
                emit("status", "CHẠY THỬ: đã thấy giá mới đạt ngưỡng. Không gửi mua/bán.")
                return "preview"
            trigger_started = time.perf_counter()
            emit(
                "phase",
                (
                    "Giá đã đổi. Bấm MAX → Mua cầu thủ màu đỏ…"
                    if current.side == "buy"
                    else "Giá đã đổi. Bấm MIN → Bán cầu thủ màu xanh…"
                ),
            )
            selected = select_price(io, reader, bound, limit, current=current)
            price_verify_ms = (time.perf_counter() - trigger_started) * 1000
            if window is not None and window.state(clock()) != "active":
                emit("status", "Hết khung giờ trước khi gửi; đã dừng.")
                return "expired"
            record = dict(
                side=selected.side,
                player=selected.name,
                boost=selected.boost,
                price_bp=selected.price,
                quantity=1,
            )
            # Durably record before the final click, so a crash cannot cause retries.
            journal.write("pending", **record)
            try:
                io.click(selected, "submit")
                emit(
                    "timing",
                    dict(
                        round_ms=round_ms,
                        price_verify_ms=price_verify_ms,
                        trigger_to_click_ms=(time.perf_counter() - trigger_started) * 1000,
                    ),
                )
                result = wait_result(io, reader, bound)
            except Exception as error:
                journal.write("unverified", error=str(error), **record)
                raise
            journal.write(result, **record)
            emit(
                "status",
                (
                    "Đã thấy đăng ký thành công. Kết thúc phiên."
                    if result == "confirmed"
                    else "Đã bấm gửi một lần; chưa xác minh đăng ký. Kiểm tra DS của bạn trước khi chạy tiếp."
                ),
            )
            return result
        elif changed:
            emit("status", "Giá đổi nhưng chưa đạt ngưỡng; tiếp tục chờ")
        io.wait(0.05 if refresher is not None else 0.04)
