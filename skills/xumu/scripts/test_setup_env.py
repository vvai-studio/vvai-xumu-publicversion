"""setup_env: the parts that decide whether a freshly installed FFmpeg / Node is actually found."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

import setup_env as se


def fake_tool(directory: Path, name: str) -> None:
    """A runnable placeholder that shutil.which() accepts on this platform."""
    if os.name == "nt":
        (directory / f"{name}.bat").write_text("@echo off\r\n", encoding="ascii")
    else:
        p = directory / name
        p.write_text("#!/bin/sh\n", encoding="ascii")
        p.chmod(0o755)


class WingetTests(unittest.TestCase):
    def test_winget_never_waits_on_a_prompt(self):
        calls = []
        with mock.patch.object(se.shutil, "which", lambda n: r"C:\winget.exe" if n == "winget" else None), \
                mock.patch.object(se.os, "name", "nt"), \
                mock.patch.object(se, "run", lambda cmd, quiet=True: calls.append(cmd) or True):
            self.assertTrue(se.system_install("ffmpeg", "Gyan.FFmpeg"))
        self.assertEqual(len(calls), 1)
        for flag in ("--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity", "--silent"):
            self.assertIn(flag, calls[0])
        self.assertEqual(calls[0][-2:], ["--id", "Gyan.FFmpeg"])


class PathTests(unittest.TestCase):
    def test_ffmpeg_installed_on_user_path_is_found_after_refresh(self):
        """The installer wrote the dir to the registry PATH; the process PATH is stale. refresh_path() bridges it."""
        with tempfile.TemporaryDirectory() as d:
            fake_tool(Path(d), "ffmpeg")
            fake_tool(Path(d), "ffprobe")
            fake_winreg = types.SimpleNamespace(
                HKEY_CURRENT_USER=1, HKEY_LOCAL_MACHINE=2, REG_EXPAND_SZ=2,
                OpenKey=lambda hive, key, *a: mock.MagicMock(__enter__=lambda s: s, __exit__=lambda s, *x: False),
                QueryValueEx=lambda h, name: (d, 2),
            )
            stale_path = str(Path(d).parent / "nowhere")
            with mock.patch.dict(os.environ, {"PATH": stale_path, "LOCALAPPDATA": d, "ProgramFiles": d}), \
                    mock.patch.object(se.os, "name", "nt"), \
                    mock.patch.dict(sys.modules, {"winreg": fake_winreg}):
                self.assertIsNone(shutil.which("ffmpeg"))
                se.refresh_path()
                self.assertIsNotNone(shutil.which("ffmpeg"))
                self.assertIn(d.lower(), os.environ["PATH"].lower())
                se.refresh_path()   # idempotent: no duplicate entry
                self.assertEqual(os.environ["PATH"].lower().count(d.lower()), 1)

    def test_find_binary_walks_winget_package_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            nested = Path(d) / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-8.0-full_build" / "bin"
            nested.mkdir(parents=True)
            (nested / "ffmpeg.exe").write_bytes(b"MZ")
            self.assertEqual(se.find_binary("ffmpeg.exe", [d, str(Path(d) / "missing")]), str(nested / "ffmpeg.exe"))
            self.assertIsNone(se.find_binary("ffprobe.exe", [d]))
            self.assertIsNone(se.find_binary("ffmpeg.exe", [d], depth=2))   # too deep for the limit

    def test_add_to_user_path_prepends_for_this_process(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"PATH": "x"}), \
                mock.patch.object(se.os, "name", "posix"):
            self.assertFalse(se.add_to_user_path(d))         # nothing persisted on posix
            self.assertTrue(os.environ["PATH"].startswith(d))

    def test_ensure_ffmpeg_reports_ok_once_the_tool_is_reachable(self):
        se.results.clear()
        with tempfile.TemporaryDirectory() as d:
            fake_tool(Path(d), "ffmpeg")
            fake_tool(Path(d), "ffprobe")

            def install(*a, **k):      # the "installer" only puts the dir on PATH, like a real one via the registry
                os.environ["PATH"] = d + os.pathsep + os.environ["PATH"]
                return True
            with mock.patch.dict(os.environ, {"PATH": str(Path(d).parent / "nowhere")}), \
                    mock.patch.object(se, "system_install", install), \
                    mock.patch.object(se, "refresh_path", lambda: None), \
                    mock.patch.object(se, "pip_install", lambda pkgs: False):
                se.ensure_ffmpeg(check=False)
        name, ok, note = se.results[-1]
        self.assertEqual((name, ok, note), ("FFmpeg / ffprobe", True, "installed"))

    def test_ensure_ffmpeg_failure_note_is_actionable(self):
        se.results.clear()
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.dict(os.environ, {"PATH": str(Path(d) / "nowhere"), "LOCALAPPDATA": d}), \
                mock.patch.object(se, "system_install", lambda *a, **k: False), \
                mock.patch.object(se, "refresh_path", lambda: None), \
                mock.patch.object(se, "pip_install", lambda pkgs: False):
            se.ensure_ffmpeg(check=False)
        name, ok, note = se.results[-1]
        self.assertFalse(ok)
        self.assertIn("ffmpeg.org", note)
        self.assertIn("PATH", note)


if __name__ == "__main__":
    unittest.main()
