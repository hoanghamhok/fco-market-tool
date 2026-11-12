from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

VN = timezone(timedelta(hours=7), "Asia/Saigon")


def now_vn():
    return datetime.now(VN)


@dataclass(frozen=True)
class ResetWindow:
    start: datetime
    end: datetime | None

    @classmethod
    def create(cls, start_text, duration, now=None):
        now = (now or now_vn()).astimezone(VN)
        if duration is not None and (type(duration) is not int or not 5 <= duration <= 1800):
            raise ValueError("Thời gian canh phải từ 5 đến 1.800 giây hoặc không giới hạn")
        if not start_text.strip():
            start = now
        else:
            try:
                parsed = datetime.strptime(
                    start_text.strip(), "%H:%M:%S" if start_text.count(":") == 2 else "%H:%M"
                ).time()
            except ValueError:
                raise ValueError("Nhập giờ Việt Nam dạng HH:MM hoặc HH:MM:SS")
            start = datetime.combine(now.date(), parsed, VN)
            if duration is None:
                if start <= now:
                    start += timedelta(days=1)
            else:
                previous = start - timedelta(days=1)
                if previous <= now < previous + timedelta(seconds=duration):
                    start = previous
                if start + timedelta(seconds=duration) <= now:
                    start += timedelta(days=1)
        return cls(start, start + timedelta(seconds=duration) if duration is not None else None)

    def state(self, now):
        if now < self.start:
            return "waiting"
        return "active" if self.end is None or now < self.end else "ended"

    def after_setup(self, immediate, now=None):
        if not immediate:
            return self
        start = (now or now_vn()).astimezone(VN)
        return ResetWindow(start, start + (self.end - self.start) if self.end else None)

    @property
    def label(self):
        if self.end is None:
            return self.start.strftime("từ %d/%m %H:%M:%S · không giới hạn (giờ VN)")
        return self.start.strftime("%d/%m %H:%M:%S") + "–" + self.end.strftime(
            "%H:%M:%S"
        ) + " (giờ VN)"
