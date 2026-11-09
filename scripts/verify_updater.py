"""Exercise the packaged updater in an isolated folder, with no game or network."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_case(executable, reports, mode):
    with TemporaryDirectory(dir=reports, prefix="updater-check-") as temp:
        root = Path(temp)
        system = Path(os.environ["SystemRoot"]) / "System32"
        target = root / "app.exe"
        shutil.copy2(system / "where.exe", target)
        original = digest(target)
        data = root / "FCO-Market-3-data"
        folder = data / "updates" / ("a" * 32)
        folder.mkdir(parents=True)
        (data / "settings.json").write_text('{"keep":"user data"}', encoding="utf-8")
        shutil.copy2(executable, folder / "updater.exe")
        if mode == "rollback":
            (folder / "payload.exe").write_bytes(b"MZinvalid Windows executable")
        else:
            shutil.copy2(system / "whoami.exe", folder / "payload.exe")
        expected = digest(folder / "payload.exe")
        parent = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(120)"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        job = dict(
            target=str(target),
            pid=parent.pid,
            previous_sha256=original,
            sha256="0" * 64 if mode == "corrupt" else expected,
            version="4.3.0",
        )
        (folder / "job.json").write_text(json.dumps(job), encoding="utf-8")
        env = os.environ.copy()
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        helper = subprocess.Popen(
            [str(folder / "updater.exe"), "--apply-update"],
            cwd=folder,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            if mode != "corrupt":
                deadline = time.monotonic() + 60
                while not (folder / "ready").exists():
                    if helper.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(f"{mode}: packaged helper did not become ready")
                    time.sleep(0.1)
                assert digest(target) == original, "Must wait until the running application exits"
            parent.terminate()
            parent.wait(timeout=10)
            code = helper.wait(timeout=60)
            result = json.loads((data / "updates/result.json").read_text(encoding="utf-8"))
            assert result["ok"] == (mode == "success"), result
            assert code == (0 if mode == "success" else 1), code
            assert digest(target) == (expected if mode == "success" else original)
            assert (data / "settings.json").read_text(encoding="utf-8") == '{"keep":"user data"}'
            if mode == "success":
                assert digest(folder / "previous.exe") == original
            return dict(case=mode, ok=True, preserved_data=True)
        finally:
            for process in (parent, helper):
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            # Bootloader cleanup and Windows file scanning can briefly retain EXEs.
            for path in (
                target,
                folder / "updater.exe",
                folder / "payload.exe",
                folder / "previous.exe",
            ):
                deadline = time.monotonic() + 15
                while True:
                    try:
                        path.unlink(missing_ok=True)
                        break
                    except PermissionError:
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve()
    reports = Path(__file__).resolve().parent.parent / "reports"
    reports.mkdir(exist_ok=True)
    results = [run_case(executable, reports, mode) for mode in ("success", "corrupt", "rollback")]
    report = dict(ok=True, executable=executable.name, sha256=digest(executable), cases=results)
    (reports / "updater-self-test.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
