import copy
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fco import updater
from fco.controller import DesktopAPI
from fco.storage import atomic_json


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.root = Path(self.temp.name)
        self.content = b"MZ" + b"test application" * 100
        self.digest = hashlib.sha256(self.content).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def release(self):
        name = "FCO-Market-4.3.0.exe"
        return dict(
            tag_name="v4.3.0",
            body="Test notes",
            draft=False,
            prerelease=False,
            assets=[
                dict(
                    name=name,
                    size=len(self.content),
                    digest="sha256:" + self.digest,
                    browser_download_url=f"https://github.com/{updater.REPOSITORY}/releases/download/v4.3.0/{name}",
                )
            ],
        )

    def info(self):
        return updater.release_info(self.release(), current="4.2.0")

    def job(self):
        target = self.root / "app.exe"
        target.write_bytes(b"MZold")
        data = self.root / "FCO-Market-3-data"
        folder = data / "updates" / ("a" * 32)
        folder.mkdir(parents=True)
        (folder / "updater.exe").write_bytes(b"helper")
        (folder / "payload.exe").write_bytes(self.content)
        (data / "settings.json").write_text('{"salary":25}', encoding="utf-8")
        job = dict(
            target=str(target),
            pid=os.getpid(),
            sha256=self.digest,
            previous_sha256=updater.sha256(target),
            version="4.3.0",
        )
        atomic_json(folder / "job.json", job)
        return target, data, folder, job

    def test_versions_are_numeric_and_old_or_preview_releases_are_ignored(self):
        self.assertGreater(updater.version_tuple("v4.10.0"), updater.version_tuple("4.9.9"))
        release = self.release()
        self.assertIsNone(updater.release_info(release, "4.3.0"))
        for key in ("draft", "prerelease"):
            modified = copy.deepcopy(release)
            modified[key] = True
            self.assertIsNone(updater.release_info(modified, "4.0.0"))
        for value in ("latest", "4.3.0-rc1", "4.3", "../../../file"):
            with self.assertRaises(ValueError):
                updater.version_tuple(value)

    def test_release_requires_exact_asset_and_trusted_repo_url(self):
        for field, value in (
            ("name", "Other.exe"),
            ("browser_download_url", "https://example.com/app.exe"),
            ("size", 0),
        ):
            release = self.release()
            release["assets"][0][field] = value
            with self.assertRaises(ValueError):
                updater.release_info(release, "4.0.0")

    def test_checksum_file_fallback_and_missing_checksum(self):
        release = self.release()
        release["assets"][0].pop("digest")
        with self.assertRaises(ValueError):
            updater.release_info(release, "4.0.0")
        release["assets"].append(
            dict(
                name="SHA256SUMS.txt",
                browser_download_url=f"https://github.com/{updater.REPOSITORY}/releases/download/v4.3.0/SHA256SUMS.txt",
            )
        )
        text = f"{self.digest}  FCO-Market-4.3.0.exe\n".encode()
        with patch.object(updater, "read_small", return_value=text):
            self.assertEqual(updater.release_info(release, "4.0.0")["sha256"], self.digest)
        with patch.object(updater, "read_small", return_value=b"bad checksum"):
            with self.assertRaises(ValueError):
                updater.release_info(release, "4.0.0")

    def test_download_verifies_length_hash_header_and_progress(self):
        path = self.root / "payload.exe"
        progress = []
        with patch.object(updater, "open_url", return_value=BytesIO(self.content)):
            updater.download(self.info(), path, progress.append)
        self.assertEqual(path.read_bytes(), self.content)
        self.assertEqual(progress[-1], 100)
        path.unlink()
        for content in (self.content[:-1], self.content + b"extra", b"XX" + self.content[2:]):
            with patch.object(updater, "open_url", return_value=BytesIO(content)):
                with self.assertRaises(ValueError):
                    updater.download(self.info(), path, progress.append)
            self.assertFalse(path.exists())

    def test_download_does_not_remove_a_preexisting_file(self):
        path = self.root / "existing.exe"
        path.write_bytes(b"keep")
        with patch.object(updater, "open_url", return_value=BytesIO(self.content)):
            with self.assertRaises(FileExistsError):
                updater.download(self.info(), path, lambda value: None)
        self.assertEqual(path.read_bytes(), b"keep")

    def test_transaction_waits_then_replaces_and_preserves_data_and_backup(self):
        target, data, folder, _ = self.job()

        def waiting(pid):
            self.assertEqual(target.read_bytes(), b"MZold")
            self.assertTrue((folder / "ready").exists())

        with (
            patch.object(updater, "wait_for_exit", side_effect=waiting),
            patch.object(updater, "detached") as launch,
        ):
            self.assertEqual(updater.apply_job(folder, folder / "updater.exe"), 0)
        self.assertEqual(target.read_bytes(), self.content)
        self.assertEqual((folder / "previous.exe").read_bytes(), b"MZold")
        self.assertEqual((data / "settings.json").read_text(), '{"salary":25}')
        result = json.loads((data / "updates/result.json").read_text())
        self.assertEqual(result["target"], str(target))
        launch.assert_called_once_with([str(target)], str(target.parent))

    def test_failed_restart_rolls_back_original_exe(self):
        target, data, folder, _ = self.job()
        with (
            patch.object(updater, "wait_for_exit"),
            patch.object(
                updater, "detached", side_effect=[OSError("cannot start"), None]
            ) as launch,
        ):
            self.assertEqual(updater.apply_job(folder, folder / "updater.exe"), 1)
        self.assertEqual(target.read_bytes(), b"MZold")
        result = json.loads((data / "updates/result.json").read_text())
        self.assertFalse(result["ok"])
        self.assertEqual(result["target"], str(target))
        self.assertEqual(launch.call_count, 2)

    def test_corrupt_payload_and_cancel_never_replace_exe(self):
        target, data, folder, _ = self.job()
        (folder / "payload.exe").write_bytes(b"tampered")
        with (
            patch.object(updater, "wait_for_exit") as wait,
            patch.object(updater, "detached") as launch,
        ):
            self.assertEqual(updater.apply_job(folder, folder / "updater.exe"), 1)
            wait.assert_not_called()
            launch.assert_not_called()
        self.assertEqual(target.read_bytes(), b"MZold")
        (folder / "payload.exe").write_bytes(self.content)
        (folder / "cancel").touch()
        with patch.object(updater, "wait_for_exit") as wait:
            self.assertEqual(updater.apply_job(folder, folder / "updater.exe"), 1)
            wait.assert_not_called()

    def test_changed_executable_after_wait_is_not_overwritten(self):
        target, _, folder, _ = self.job()

        def waiting(pid):
            target.write_bytes(b"MZanother update")

        with (
            patch.object(updater, "wait_for_exit", side_effect=waiting),
            patch.object(updater, "detached"),
        ):
            self.assertEqual(updater.apply_job(folder, folder / "updater.exe"), 1)
        self.assertEqual(target.read_bytes(), b"MZanother update")

    def test_changed_payload_after_wait_is_rejected(self):
        target, _, folder, _ = self.job()

        def waiting(pid):
            (folder / "payload.exe").write_bytes(b"MZtampered")

        with (
            patch.object(updater, "wait_for_exit", side_effect=waiting),
            patch.object(updater, "detached"),
        ):
            self.assertEqual(updater.apply_job(folder, folder / "updater.exe"), 1)
        self.assertEqual(target.read_bytes(), b"MZold")

    def test_helper_rejects_paths_outside_its_application(self):
        target, _, folder, job = self.job()
        job["target"] = str(self.root.parent / "other.exe")
        atomic_json(folder / "job.json", job)
        with self.assertRaises(ValueError):
            updater.apply_job(folder, folder / "updater.exe")
        self.assertEqual(target.read_bytes(), b"MZold")

    def test_source_and_busy_game_guards(self):
        api = DesktopAPI(self.root)
        api._updater._info = self.info()
        api._updater._set(status="available")
        with patch.object(updater.sys, "frozen", False, create=True):
            with self.assertRaises(ValueError):
                api.download_update()
        api._set(busy=True)
        with patch.object(api._updater, "start_download") as start:
            with self.assertRaises(ValueError):
                api.download_update()
            start.assert_not_called()
        api._set(busy=False)
        api._updater._set(status="downloading")
        with patch("fco.controller.Desktop") as desktop:
            with self.assertRaises(ValueError):
                api.start_action("detect", api.bootstrap()["watch"])
            desktop.assert_not_called()

    def test_probe_rejects_wrong_embedded_version(self):
        path = self.root / "payload.exe"
        atomic_json(path.with_suffix(".probe.json"), dict(ok=True, version="4.0.0"))
        with patch.object(updater.subprocess, "run") as run:
            run.return_value.returncode = 0
            with self.assertRaises(ValueError):
                updater.probe_update(path, "4.3.0")

    def test_failed_probe_never_marks_download_ready_to_install(self):
        instance = updater.Updater(self.root)
        instance._info = self.info()
        with (
            patch.object(updater, "download"),
            patch.object(updater, "probe_update", side_effect=ValueError("probe failed")),
        ):
            instance._download()
        self.assertEqual(instance.state()["status"], "error")
        with self.assertRaises(ValueError):
            instance.prepare_install()

    def test_real_windows_wait_handle(self):
        import subprocess
        import sys

        process = subprocess.Popen(
            [sys.executable, "-c", "pass"], creationflags=subprocess.CREATE_NO_WINDOW
        )
        try:
            updater.wait_for_exit(process.pid, timeout=10)
        finally:
            process.wait(timeout=10)
