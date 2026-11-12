"""Public GitHub releases and a detached, transactional portable-EXE updater."""

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import uuid

from . import VERSION
from .storage import FileLock, atomic_json

REPOSITORY = "hoanghamhok/fco-market-tool"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_EXE_SIZE = 1024 * 1024 * 1024
ACTIVE = {"checking", "downloading", "preparing", "installing"}


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value))
    if not match:
        raise ValueError("Phiên bản phát hành phải có dạng v4.2.0.")
    return tuple(int(part) for part in match.groups())


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def asset_url(url, tag, name):
    expected = f"https://github.com/{REPOSITORY}/releases/download/{quote(tag, safe='')}/{quote(name, safe='')}"
    if url != expected:
        raise ValueError("Đường dẫn cập nhật không thuộc bản phát hành của ứng dụng.")
    return url


def open_url(url):
    request = Request(
        url,
        headers={
            "User-Agent": f"FCO-Market/{VERSION}",
            "Accept": (
                "application/vnd.github+json" if url == API_URL else "application/octet-stream"
            ),
        },
    )
    response = urlopen(request, timeout=20)
    if urlsplit(response.url).scheme != "https":
        response.close()
        raise ValueError("Bản cập nhật phải được tải qua HTTPS.")
    return response


def read_small(url, limit=1024 * 1024):
    with open_url(url) as response:
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Thông tin bản cập nhật quá lớn.")
    return content


def release_info(release, current=VERSION):
    """Accept only stable, newer releases with an exact Windows artifact name."""
    if not isinstance(release, dict):
        raise ValueError("Thông tin bản phát hành không hợp lệ.")
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease"):
        return None
    version = version_tuple(tag)
    if version <= version_tuple(current):
        return None
    name = "FCO-Market-" + ".".join(map(str, version)) + ".exe"
    assets = release.get("assets", [])
    matches = [asset for asset in assets if asset.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"Bản phát hành chưa có file {name}.")
    asset = matches[0]
    size = asset.get("size")
    if type(size) is not int or not 0 < size <= MAX_EXE_SIZE:
        raise ValueError("Kích thước bộ cập nhật không hợp lệ.")
    url = asset_url(asset.get("browser_download_url"), tag, name)
    digest = asset.get("digest") or ""
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        sums = next((item for item in assets if item.get("name") == "SHA256SUMS.txt"), None)
        if not sums:
            raise ValueError("Bản phát hành thiếu mã SHA-256 để kiểm tra file.")
        text = read_small(
            asset_url(sums.get("browser_download_url"), tag, "SHA256SUMS.txt"), 65536
        ).decode("utf-8-sig")
        digests = [
            m.group(1)
            for line in text.splitlines()
            if (m := re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?" + re.escape(name), line.strip()))
        ]
        if len(digests) != 1:
            raise ValueError("Không tìm thấy mã kiểm tra của bộ cập nhật.")
        digest = "sha256:" + digests[0]
    return dict(
        version=".".join(map(str, version)),
        name=name,
        url=url,
        size=size,
        sha256=digest[7:].lower(),
        notes=str(release.get("body") or "")[:4000],
    )


def download(info, path, progress):
    path = Path(path)
    created = False
    try:
        digest = hashlib.sha256()
        received = 0
        with open_url(info["url"]) as response, path.open("xb") as handle:
            created = True
            while chunk := response.read(256 * 1024):
                received += len(chunk)
                if received > info["size"]:
                    raise ValueError("File tải về lớn hơn kích thước được công bố.")
                handle.write(chunk)
                digest.update(chunk)
                progress(int(received * 100 / info["size"]))
            handle.flush()
            os.fsync(handle.fileno())
        if received != info["size"] or digest.hexdigest() != info["sha256"]:
            raise ValueError("File tải về chưa đầy đủ hoặc sai mã kiểm tra. Hãy thử lại.")
        with path.open("rb") as handle:
            if handle.read(2) != b"MZ":
                raise ValueError("File tải về không phải ứng dụng Windows.")
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def child_environment():
    # A copied one-file PyInstaller executable must extract its own resources.
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def detached(command, cwd):
    return subprocess.Popen(
        command,
        cwd=cwd,
        env=child_environment(),
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def probe_update(path, version):
    report = Path(path).with_suffix(".probe.json")
    process = subprocess.run(
        [str(path), "--update-probe", str(report)],
        cwd=Path(path).parent,
        env=child_environment(),
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    result = json.loads(report.read_text(encoding="utf-8"))
    if process.returncode or result.get("ok") is not True or result.get("version") != version:
        raise ValueError("Không mở được bản cập nhật hoặc phiên bản bên trong không khớp.")


def run_probe(path):
    from .paths import RESOURCE_ROOT

    try:
        import webview  # Check that the packaged desktop dependency can be imported.

        for name in ("ui/index.html", "ui/app.js", "ui/style.css", "assets/fco.ico"):
            if not (RESOURCE_ROOT / name).is_file():
                raise ValueError("Bản cập nhật thiếu tài nguyên giao diện.")
        atomic_json(Path(path), dict(ok=bool(getattr(sys, "frozen", False)), version=VERSION))
        return 0
    except Exception as error:
        atomic_json(Path(path), dict(ok=False, version=VERSION, error=str(error)))
        return 1


class Updater:
    def __init__(self, root, enabled=True):
        self.root = Path(root)
        self.enabled = enabled
        self._lock = threading.RLock()
        self._info = None
        self._folder = None
        self._state = dict(status="idle", message="", progress=0, version="", notes="")
        try:
            result = json.loads((self.root / "updates/result.json").read_text(encoding="utf-8"))
            if result.get("ok") is False:
                self._state.update(
                    status="error", message=str(result.get("message", "Cập nhật chưa hoàn tất."))
                )
        except (OSError, ValueError, AttributeError):
            pass

    def state(self):
        with self._lock:
            return copy.deepcopy(self._state)

    def _set(self, **values):
        with self._lock:
            self._state.update(values)

    def _begin(self, status):
        with self._lock:
            if not self.enabled:
                raise ValueError("Cập nhật đang tắt trong phiên kiểm tra.")
            if self._state["status"] in ACTIVE:
                raise ValueError("Đang xử lý bản cập nhật. Hãy chờ hoàn tất.")
            self._state.update(status=status, message="", progress=0)

    def check(self):
        self._begin("checking")
        threading.Thread(target=self._check, daemon=True).start()
        return self.state()

    def _check(self):
        try:
            self._info = release_info(json.loads(read_small(API_URL)))
            if self._info:
                self._set(
                    status="available", **{key: self._info[key] for key in ("version", "notes")}
                )
            else:
                self._set(status="current", message="Bạn đang dùng phiên bản mới nhất.")
        except HTTPError as error:
            message = {
                404: "Chưa tìm thấy bản phát hành công khai trên GitHub.",
                403: "GitHub đang giới hạn kiểm tra. Hãy thử lại sau.",
                429: "GitHub đang giới hạn kiểm tra. Hãy thử lại sau.",
            }.get(error.code, "Không kết nối được GitHub. Hãy thử lại sau.")
            self._set(status="error", message=message)
        except (URLError, TimeoutError, OSError):
            self._set(
                status="error", message="Không kết nối được GitHub. Kiểm tra mạng và thử lại."
            )
        except Exception as error:
            self._set(status="error", message=str(error))

    def start_download(self):
        with self._lock:
            if self._state["status"] != "available" or not self._info:
                raise ValueError("Hãy kiểm tra bản cập nhật trước.")
            if not getattr(sys, "frozen", False):
                raise ValueError("Hãy chạy bản EXE để cập nhật. Mã nguồn không tự thay Python.")
            self._begin("downloading")
        threading.Thread(target=self._download, daemon=True).start()
        return self.state()

    def _download(self):
        try:
            self._folder = self.root / "updates" / uuid.uuid4().hex
            self._folder.mkdir(parents=True)
            download(
                self._info, self._folder / "payload.exe", lambda value: self._set(progress=value)
            )
            self._set(message="Đang kiểm tra khả năng khởi chạy bản mới…", progress=100)
            probe_update(self._folder / "payload.exe", self._info["version"])
            self._set(
                status="downloaded", message="Đã tải xong. Khởi động lại để cập nhật.", progress=100
            )
        except Exception as error:
            self._set(status="error", message=str(error))

    def prepare_install(self):
        with self._lock:
            if self._state["status"] != "downloaded" or not self._folder:
                raise ValueError("Chưa tải xong bản cập nhật.")
            self._begin("preparing")
        try:
            target = Path(sys.executable).resolve()
            if (
                not getattr(sys, "frozen", False)
                or self.root.resolve() != target.parent / "FCO-Market-3-data"
            ):
                raise ValueError("Chỉ có thể cập nhật EXE trong thư mục dữ liệu của ứng dụng.")
            helper = self._folder / "updater.exe"
            shutil.copy2(target, helper)
            job = dict(
                target=str(target),
                pid=os.getpid(),
                sha256=self._info["sha256"],
                previous_sha256=sha256(target),
                version=self._info["version"],
            )
            atomic_json(self._folder / "job.json", job)
            process = detached([str(helper), "--apply-update"], str(self._folder))
            deadline = time.monotonic() + 45
            while not (self._folder / "ready").exists():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(
                        "Không khởi động được bộ cập nhật. Ứng dụng hiện tại được giữ nguyên."
                    )
                time.sleep(0.1)
            self._set(status="installing", message="Đang khởi động lại để cập nhật…")
            return self.state()
        except Exception as error:
            # A late-starting helper must never replace a still-running application.
            if self._folder:
                (self._folder / "cancel").touch()
            self._set(status="error", message=str(error))
            raise


def wait_for_exit(pid, timeout=120):
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # The process has already exited.
            return
        raise OSError("Không thể chờ ứng dụng cũ đóng.")
    try:
        if kernel.WaitForSingleObject(handle, int(timeout * 1000)) != 0:
            raise TimeoutError("Ứng dụng chưa đóng. Bản hiện tại được giữ nguyên.")
    finally:
        kernel.CloseHandle(handle)


def replace_with_retry(source, target, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)


def apply_job(folder, executable=None):
    """Run only from the copied helper; never accept arbitrary replacement paths."""
    folder = Path(folder).resolve()
    job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    target = Path(job["target"]).resolve()
    helper = Path(executable or sys.executable).resolve()
    data = target.parent / "FCO-Market-3-data"
    if (
        folder.parent != data / "updates"
        or not re.fullmatch(r"[a-f0-9]{32}", folder.name)
        or helper != folder / "updater.exe"
        or target.suffix.lower() != ".exe"
        or target.is_symlink()
    ):
        raise ValueError("Vị trí bộ cập nhật không hợp lệ.")
    if type(job.get("pid")) is not int or job["pid"] <= 0:
        raise ValueError("Tiến trình cập nhật không hợp lệ.")
    version_tuple(job["version"])
    with FileLock(data / "updates/.install.lock"):
        return _apply_locked(folder, job, target, data)


def _apply_locked(folder, job, target, data):
    payload = folder / "payload.exe"
    result_path = data / "updates/result.json"
    backup = folder / "previous.exe"
    replaced = False
    exited = False
    try:
        if not re.fullmatch(r"[a-f0-9]{64}", job["sha256"]) or sha256(payload) != job["sha256"]:
            raise ValueError("Bản cập nhật sai mã kiểm tra.")
        if (folder / "cancel").exists():
            return 1
        (folder / "ready").touch()
        wait_for_exit(job["pid"])
        exited = True
        if (folder / "cancel").exists():
            return 1
        if sha256(target) != job["previous_sha256"]:
            raise ValueError("EXE hiện tại đã thay đổi. Hãy mở lại ứng dụng và kiểm tra cập nhật.")
        if sha256(payload) != job["sha256"]:
            raise ValueError("File cập nhật đã thay đổi sau khi tải. Hãy tải lại.")
        shutil.copy2(target, backup)
        replace_with_retry(payload, target)
        replaced = True
        atomic_json(result_path, dict(ok=True, version=job["version"], target=str(target)))
        detached([str(target)], str(target.parent))
        return 0
    except Exception as error:
        if replaced:
            replace_with_retry(backup, target)
        atomic_json(
            result_path,
            dict(
                ok=False,
                message=f"Cập nhật chưa hoàn tất: {error}",
                target=str(target),
                backup=str(backup),
            ),
        )
        if exited:
            detached([str(target)], str(target.parent))
        return 1


def run_helper():
    if not getattr(sys, "frozen", False):
        return 1
    try:
        return apply_job(Path(sys.executable).parent)
    except Exception:
        return 1
