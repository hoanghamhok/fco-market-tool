import json
import os
from pathlib import Path
import time


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class FileLock:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        import msvcrt

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, 2)
        if not self.handle.tell():
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.handle.close()
            raise RuntimeError("Một phiên khác đang điều khiển FCO")
        return self

    def __exit__(self, *_):
        import msvcrt

        self.handle.seek(0)
        msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        self.handle.close()


class Journal:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / "last-order.json"

    def pending(self):
        if not self.path.exists():
            return None
        try:
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("state") not in (
                "pending",
                "unverified",
                "confirmed",
            ):
                raise ValueError("invalid state")
            return record
        except (ValueError, OSError):
            raise RuntimeError(
                "Không đọc được nhật ký lệnh trước. Kiểm tra DS của bạn rồi xác nhận đã kiểm tra."
            )

    def write(self, state, **details):
        atomic_json(
            self.path, dict(state=state, time=time.strftime("%Y-%m-%dT%H:%M:%S%z"), **details)
        )

    def acknowledge(self):
        if self.path.exists():
            history = self.root / "history"
            history.mkdir(parents=True, exist_ok=True)
            self.path.replace(history / f"order-{time.time_ns()}.json")
