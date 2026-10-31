#!/usr/bin/env python3
"""One-shot environment setup for the xumu (序幕) plugin.

Checks and installs, on its own, everything the three skills need to actually cut a film. Free local
dependencies are installed without asking item by item (the agent reports afterwards what was installed);
paid services and accounts (vvai keys etc.) are never touched here.
  - FFmpeg / ffprobe          (winget, apt-get, dnf, apk or brew; static build as last resort)
  - Python deps for Video Use (requests librosa matplotlib pillow numpy + faster-whisper)
  - Node.js >= 18 + npm       (winget / apt-get / dnf / apk / brew; for Remotion / Shotcraft animation shots)
  - Remotion npm cache        (warmed by default so project installs are fast; --no-remotion skips it)
  - Motion reference index    (gongnyang / HyperFrames registry / mg-styles-15 / Opuscar, ~155 MB, needs git;
                               fetched and built by default, rebuilt when it predates Opuscar; --no-refs skips it)
  - Optional: pre-download the local whisper model (--whisper-model small|medium|large-v3)
  - Local transcription runtime probe: loads a whisper model in a separate process; ctranslate2 4.7/4.8
    crash on load on some Windows PCs, so a crash is repaired by pinning the verified ctranslate2 4.6.0

Idempotent: anything already present is skipped. Safe to run at the start of every
production session. Never writes into the plugin/skill directories.

Usage:
    python3 setup_env.py              # check + install everything missing (the normal first-run call)
    python3 setup_env.py --check      # report only, change nothing
    python3 setup_env.py --no-remotion --no-refs --whisper-model small
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):   # Windows pipes default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except (ValueError, OSError):
            pass

PY_DEPS = {  # import name -> pip name
    "requests": "requests",
    "librosa": "librosa",
    "matplotlib": "matplotlib",
    "PIL": "pillow",
    "numpy": "numpy",
    "faster_whisper": "faster-whisper",
}

results: list[tuple[str, bool, str]] = []


def run(cmd: list[str], quiet: bool = True) -> bool:
    try:
        subprocess.run(cmd, check=True,
                       stdout=subprocess.DEVNULL if quiet else None,
                       stderr=subprocess.DEVNULL if quiet else None)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def sudo() -> list[str]:
    if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() != 0 and shutil.which("sudo"):
        return ["sudo", "-n"]
    return []


def system_install(apt: str, brew: str, dnf: str | None = None, apk: str | None = None) -> bool:
    if shutil.which("apt-get"):
        return (run(sudo() + ["apt-get", "install", "-y", "-qq", apt])
                or (run(sudo() + ["apt-get", "update", "-qq"])
                    and run(sudo() + ["apt-get", "install", "-y", "-qq", apt])))
    if shutil.which("dnf"):
        return run(sudo() + ["dnf", "install", "-y", "-q", dnf or apt])
    if shutil.which("apk"):
        return run(sudo() + ["apk", "add", "--no-cache", apk or apt])
    if shutil.which("brew"):
        return run(["brew", "install", brew])
    if os.name == "nt" and shutil.which("winget"):
        return run(["winget", "install", "-e", "--silent", "--accept-source-agreements",
                    "--accept-package-agreements", "--disable-interactivity", "--id", brew])
    return False


def refresh_path() -> None:
    """Windows installers write PATH to the registry; this process keeps the PATH it started with. Merge the
    user + machine PATH and the WinGet / Node default dirs into os.environ so `which` sees what was just installed."""
    if os.name != "nt":
        return
    import winreg
    parts: list[str] = []
    for hive, key in ((winreg.HKEY_CURRENT_USER, "Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(hive, key) as h:
                parts += os.path.expandvars(winreg.QueryValueEx(h, "Path")[0]).split(os.pathsep)
        except OSError:
            pass
    parts.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links"))
    parts.append(os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs"))
    current = os.environ.get("PATH", "")
    have = {p.lower().rstrip("\\") for p in current.split(os.pathsep)}
    extra = [p for p in parts if p and p.lower().rstrip("\\") not in have and os.path.isdir(p)]
    if extra:
        os.environ["PATH"] = current + os.pathsep + os.pathsep.join(dict.fromkeys(extra))


def find_binary(exe: str, roots: list[str], depth: int = 4) -> str | None:
    """First `exe` found under any root, at most `depth` levels down (WinGet keeps portable packages in nested dirs)."""
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for p in base.rglob(exe):
            if len(p.relative_to(base).parts) <= depth and p.is_file():
                return str(p)
    return None


def add_to_user_path(directory: str) -> bool:
    """Put `directory` on PATH for this process and, on Windows, persist it in the user's PATH (registry +
    WM_SETTINGCHANGE broadcast, like setx) so every later shell and agent session finds the tool too."""
    current = os.environ.get("PATH", "")
    if directory.lower() not in current.lower():
        os.environ["PATH"] = directory + os.pathsep + current
    if os.name != "nt":
        return False
    try:
        import ctypes
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as h:
            try:
                old, kind = winreg.QueryValueEx(h, "Path")
            except OSError:
                old, kind = "", winreg.REG_EXPAND_SZ
            entries = [e for e in old.split(os.pathsep) if e]
            if directory.lower() not in {e.lower() for e in entries}:
                winreg.SetValueEx(h, "Path", 0, kind, os.pathsep.join(entries + [directory]))
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, None)
        return True
    except OSError:
        return False


def winget_roots() -> list[str]:
    local = os.environ.get("LOCALAPPDATA", "")
    return [os.path.join(local, "Microsoft", "WinGet", "Packages"), os.path.join(local, "Microsoft", "WinGet", "Links")]


def ensure_ffmpeg(check: bool) -> None:
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        results.append(("FFmpeg / ffprobe", True, "present"))
        return
    if check:
        results.append(("FFmpeg / ffprobe", False, "missing"))
        return
    system_install("ffmpeg", "ffmpeg" if os.name != "nt" else "Gyan.FFmpeg")
    refresh_path()                       # the installer put it on the user PATH; this process did not know yet
    how = "installed"
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")) and os.name == "nt":
        exe = find_binary("ffmpeg.exe", winget_roots())   # installed but its dir is on no PATH at all
        if exe:
            add_to_user_path(os.path.dirname(exe))
            how = f"installed, added to your user PATH: {os.path.dirname(exe)}"
    ok = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    if not ok:  # last resort: static binary via pip, then make its dir permanent on the user PATH
        if pip_install(["static-ffmpeg"]):
            try:
                import static_ffmpeg  # type: ignore
                static_ffmpeg.add_paths()
                exe = shutil.which("ffmpeg")
                if exe:
                    persisted = add_to_user_path(os.path.dirname(exe))
                    ok = True
                    how = (f"installed static build: {os.path.dirname(exe)}"
                           + (" (added to your user PATH)" if persisted else
                              " (add it to PATH, or run `python -m static_ffmpeg -version` once per shell)"))
            except Exception:
                pass
    results.append(("FFmpeg / ffprobe", ok, how if ok else
                    "could not install automatically (no winget/brew/apt, or no network) - install from "
                    "https://ffmpeg.org/download.html and make sure `ffmpeg` is on PATH, then rerun"))


def pip_flags() -> list[str]:
    flags = []
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if not in_venv:
        # PEP 668 distros refuse plain pip installs; --break-system-packages is the documented escape.
        probe = subprocess.run([sys.executable, "-m", "pip", "install", "--help"],
                               capture_output=True, text=True)
        if "--break-system-packages" in probe.stdout:
            flags.append("--break-system-packages")
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            flags.append("--user")
    return flags


def pip_install(packages: list[str]) -> bool:
    """pip into this interpreter; environments created by uv have no pip, so fall back to `uv pip`."""
    if importlib.util.find_spec("pip") is not None:
        return run([sys.executable, "-m", "pip", "install", "-q", *pip_flags(), *packages], quiet=False)
    if shutil.which("uv"):
        return run(["uv", "pip", "install", "-q", "--python", sys.executable, *packages], quiet=False)
    return False


def ensure_python(check: bool) -> None:
    if sys.version_info < (3, 10):
        results.append(("Python >= 3.10", False, f"found {platform.python_version()}"))
        return
    results.append(("Python >= 3.10", True, platform.python_version()))
    missing = [pip for mod, pip in PY_DEPS.items() if importlib.util.find_spec(mod) is None]
    if not missing:
        results.append(("Python deps (Video Use + local transcription)", True, "present"))
        return
    if check:
        results.append(("Python deps (Video Use + local transcription)", False, "missing: " + ", ".join(missing)))
        return
    ok = pip_install(missing)
    results.append(("Python deps (Video Use + local transcription)", ok,
                    ("installed: " if ok else "failed: ") + ", ".join(missing)))


def node_major() -> int:
    node = shutil.which("node")
    if not node:
        return 0
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
        return int(out.lstrip("v").split(".")[0])
    except Exception:
        return 0


def ensure_node(check: bool) -> None:
    if node_major() >= 18 and shutil.which("npm") and shutil.which("npx"):
        results.append(("Node.js >= 18 + npm", True, f"v{node_major()}"))
        return
    installed = False
    if not check:
        installed = system_install("nodejs", "node" if os.name != "nt" else "OpenJS.NodeJS.LTS")
        if shutil.which("apt-get") and not shutil.which("npm"):
            system_install("npm", "node")
        refresh_path()
        if os.name == "nt" and not shutil.which("node"):
            exe = find_binary("node.exe", [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "nodejs"),
                                           *winget_roots()], depth=3)
            if exe:
                add_to_user_path(os.path.dirname(exe))
    ok = node_major() >= 18 and bool(shutil.which("npm"))
    results.append(("Node.js >= 18 + npm", ok,
                    f"v{node_major()}" if ok else
                    "installed just now but not on this process's PATH yet: open a new terminal / agent session and rerun"
                    if installed else
                    "missing/too old - could not install automatically; install Node 20 LTS from https://nodejs.org "
                    "(needed for Remotion and Shotcraft animation shots)"))


def warm_remotion(check: bool) -> None:
    if node_major() < 18:
        return
    if check:
        results.append(("Remotion npm cache", True, "not checked (warmed on an install run; --no-remotion skips)"))
        return
    ok = run([shutil.which("npm") or "npm", "cache", "add", "remotion",   # Windows: npm is npm.cmd, which() finds it "@remotion/cli", "@remotion/bundler",
              "@remotion/renderer", "react", "react-dom"])
    results.append(("Remotion npm cache", ok, "warmed" if ok else "skipped (network?)"))
    # Chrome Headless Shell is fetched by Remotion on first render; Linux needs these libs.
    if shutil.which("apt-get"):
        libs = ("libnss3 libdbus-1-3 libatk1.0-0 libgbm1 libasound2 libxrandr2 libxkbcommon0 "
                "libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2")
        run(sudo() + ["apt-get", "install", "-y", "-qq", *libs.split()])


def ensure_motion_index(check: bool) -> None:
    """Motion reference index (gongnyang / HyperFrames registry / mg-styles-15 / Opuscar): fetch + build when missing,
    rebuild when it was built before the Opuscar source existed."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import motion_index
    except Exception as exc:  # noqa: BLE001 - any import problem just downgrades to a report
        results.append(("Motion reference index", False, f"motion_index.py not importable: {exc}"))
        return
    index = motion_index.default_index_path()
    stale = False
    if index.is_file():
        try:
            stale = "lemo-opuscar" not in json.loads(index.read_text(encoding="utf-8")).get("counts", {})
        except (OSError, ValueError):
            stale = True
        if not stale:
            results.append(("Motion reference index", True, f"present: {index}"))
            return
    what = "predates Opuscar, rebuild" if stale else "missing"
    if check:
        results.append(("Motion reference index", False,
                        f"{what}: {index} (motion_index.py fetch + build, ~155 MB, needs git and network)"))
        return
    if not shutil.which("git"):
        results.append(("Motion reference index", False, f"{what}, but git is not installed - install git, then rerun"))
        return
    script = str(Path(__file__).resolve().parent / "motion_index.py")
    ok = run([sys.executable, script, "fetch"], quiet=False) and run([sys.executable, script, "build", "--force"], quiet=False)
    ok = ok and index.is_file()
    results.append(("Motion reference index", ok, f"built: {index}" if ok else
                    "fetch/build failed (network or git?) - optional; rerun motion_index.py fetch + build --force later"))


CT2_PIN = ["ctranslate2==4.6.0", "setuptools<81"]   # 4.6.0 still imports pkg_resources


def cached_whisper_model() -> str | None:
    """Smallest faster-whisper model already in the Hugging Face cache, so --check can test offline."""
    hub = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    if os.environ.get("HF_HUB_CACHE"):
        hub = Path(os.environ["HF_HUB_CACHE"])
    for size in ("tiny", "base", "small", "medium", "large-v3"):
        if (hub / f"models--Systran--faster-whisper-{size}").is_dir():
            return size
    return None


def whisper_probe(model: str, offline: bool) -> tuple[str, str]:
    """Load the model in a child process: a native crash kills the child, not this script."""
    code = ("from faster_whisper import WhisperModel; "
            f"WhisperModel({model!r}, device='cpu', compute_type='int8', local_files_only={offline}); "
            "print('LOAD_OK')")
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return "error", "timed out (model download?)"
    if "LOAD_OK" in r.stdout:
        return "ok", ""
    if "Traceback" in r.stderr:
        return "error", r.stderr.strip().splitlines()[-1][:160]
    return "crash", f"process exited with code {r.returncode} and no Python error"


def check_whisper_runtime(model_arg: str | None, check: bool) -> None:
    if importlib.util.find_spec("faster_whisper") is None:
        return
    name = "Local transcription runtime"
    cached = cached_whisper_model()
    model = model_arg or cached
    if not model:
        if check:
            results.append((name, True, "not tested: no model cached (run without --check to test with 'tiny')"))
            return
        model = "tiny"
    offline = check or (model == cached and not model_arg)
    status, detail = whisper_probe(model, offline)
    if status == "crash" and not check:
        pinned = pip_install(CT2_PIN)   # judge by the re-probe: installers can report errors after installing
        status, detail = whisper_probe(model, offline)
        if status == "crash" and not pinned:
            detail = "pinning ctranslate2 4.6.0 failed"
        if status == "ok":
            results.append((name, True, f"model '{model}' loads after pinning ctranslate2 4.6.0"))
            return
    if status == "ok":
        results.append((name, True, f"model '{model}' loads"))
    elif status == "crash":
        results.append((name, False, f"crashes on model load ({detail}); known ctranslate2 4.7/4.8 issue on some "
                                     f"Windows PCs - run without --check to pin ctranslate2 4.6.0, or use a cloud engine"))
    else:
        results.append((name, False, detail))


def report_optional() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))   # also under python -I
    from transcribe_cloud import env_ready, video_use_env_has_key
    local_broken = any(n.startswith("Local transcription") and not ok for n, ok, _ in results)
    scribe_file = video_use_env_has_key()
    cloud = [label for engine, label in (("elevenlabs", "ElevenLabs Scribe"), ("azure", "Azure fast transcription"),
                                         ("funasr", "Fun-ASR")) if env_ready(engine) or (engine == "elevenlabs" and scribe_file)]
    if not local_broken:
        cloud.insert(0, "local faster-whisper")
    note = ("available: " + ", ".join(cloud) if cloud else
            "none usable yet: repair the local runtime (run without --check) or set a cloud key")
    note += " | paid engines need the user's OK first (transcribe_cloud.py estimate)"
    if scribe_file:
        note += " | video-use/.env holds ELEVENLABS_API_KEY: Video Use will pick paid Scribe over the local engine"
    results.append(("Transcription engine", bool(cloud), note))
    sfx = Path(__file__).resolve().parents[2] / "video-shotcraft" / "assets" / "scripts" / "sfx-source.py"
    results.append(("Shotcraft SFX sourcing", sfx.is_file(),
                    "Freesound search/download next to xumu (CC0 by default; get/analyze need ffmpeg)" if sfx.is_file() else
                    "video-shotcraft not found next to xumu: real sound effects fall back to sfx_synth.py presets"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, install nothing")
    ap.add_argument("--remotion", action="store_true", help=argparse.SUPPRESS)   # old flag; warming is now the default
    ap.add_argument("--no-remotion", action="store_true", help="skip warming the Remotion npm cache")
    ap.add_argument("--no-refs", action="store_true", help="skip fetching/building the motion reference index")
    ap.add_argument("--whisper-model", default=None, help="pre-download a faster-whisper model (e.g. small)")
    a = ap.parse_args()

    ensure_ffmpeg(a.check)
    ensure_python(a.check)
    ensure_node(a.check)
    if not a.no_remotion:
        warm_remotion(a.check)
    check_whisper_runtime(a.whisper_model, a.check)
    if not a.no_refs:
        ensure_motion_index(a.check)
    report_optional()

    width = max(len(n) for n, _, _ in results)
    for name, ok, note in results:
        print(f"[{'OK' if ok else '!!'}] {name.ljust(width)}  {note}")
    required_fail = [n for n, ok, _ in results if not ok and not n.startswith(("Local transcription", "Transcription engine", "Shotcraft SFX"))]
    return 1 if required_fail else 0


if __name__ == "__main__":
    sys.exit(main())
