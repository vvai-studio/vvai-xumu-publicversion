#!/usr/bin/env python3
"""One entry point for the first time 序幕 is used on a computer. Runs every setup step in order and prints one
checklist, so the agent (or the user) calls this once instead of five scripts:

  1. environment      setup_env.py: installs FFmpeg, Python deps, Node, the Remotion cache, the local transcription
                      runtime and the motion reference index on its own (free; nothing is asked item by item)
  2. neighbour skills video-use and video-shotcraft next to xumu (Shotcraft also supplies Freesound SFX sourcing)
  3. 造物社 key        if VVAI_API_KEY is not set, opens the local key page (key_setup.py) and waits for the user to
                      paste the key there; the key never passes through this script or the chat
  4. sound/image conf audio_cloud.py setup --yes: writes the 造物社 defaults into backends.local.json (existing kept)
  5. free check-up    audio_cloud.py doctor: key present, reachable, balance, prices, voices (free)
  6. smoke test       only with --smoke: one paid narration line + one image (~¥0.14), so ask the user first
  7. stamp            writes "first_run" {version, date, steps} into backends.local.json, so later sessions only run
                      the quick setup_env.py

  python first_run.py                 # the normal first call (blocks on the key page up to --key-timeout seconds)
  python first_run.py --check         # report everything, change nothing
  python first_run.py --no-key        # skip the key page (user will say "配置 API" later)
  python first_run.py --smoke         # also run the paid end-to-end test (needs the user's OK)

Exit code: 0 when the environment is complete (the key may still be missing: that only disables paid generation),
1 when a required environment item could not be installed, 2 when the key page timed out, 3 when this process may not
write the skill folder (an agent host's sandbox): nothing can be recorded there, so it stops before starting.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS = SKILL.parent
CONFIG = SKILL / "backends.local.json"
KEY_VAR = "VVAI_API_KEY"

steps: list[tuple[str, bool, str]] = []

for _stream in (sys.stdout, sys.stderr):   # Windows consoles default to the ANSI code page; the agent reads UTF-8
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def say(name: str, ok: bool, note: str) -> None:
    steps.append((name, ok, note))
    print(f"[{'OK' if ok else '!!'}] {name}: {note}", flush=True)


def run(args: list[str], timeout: int | None = None) -> int:
    """Run a sibling script with this interpreter, streaming its output; -1 on a crash or timeout."""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}   # children print Chinese through pipes
    try:
        return subprocess.run([sys.executable, *args], timeout=timeout, env=env).returncode
    except subprocess.TimeoutExpired:
        return -1
    except OSError as exc:
        print(f"  cannot run {args[0]}: {exc}")
        return -1


def skill_version() -> str:
    m = re.search(r'version:\s*"([^"]+)"', (SKILL / "SKILL.md").read_text(encoding="utf-8"))
    return m.group(1) if m else "?"


def load_user_env() -> None:
    """Pick up a key saved by key_setup.py in this same session (the shell env does not change until restart)."""
    sys.path.insert(0, str(HERE))
    try:
        import key_setup
        key_setup.load_user_env()
    except Exception:  # noqa: BLE001 - best effort; the env var may simply not exist yet
        pass


def can_write_skill() -> bool:
    """The config and the stamp live next to the skill. Unwritable there means every new window would start over."""
    probe = CONFIG.parent / ".write_probe"
    try:
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def step_environment(check: bool) -> bool:
    code = run([str(HERE / "setup_env.py"), *(["--check"] if check else [])])
    say("环境", code == 0, "齐了" if code == 0 else "有必需项没装上，看上面的 [!!] 行")
    return code == 0


def skill_dirs() -> list[Path]:
    """Where a neighbour skill may live: next to xumu, or in a host's skills dir (junction / symlink installs)."""
    home = Path.home()
    return [SKILLS, home / ".claude" / "skills", home / ".codex" / "skills", home / ".agents" / "skills"]


def find_skill(name: str) -> Path | None:
    return next((d / name for d in skill_dirs() if (d / name / "SKILL.md").is_file()), None)


def step_neighbours() -> bool:
    found = {n: find_skill(n) for n in ("video-use", "video-shotcraft")}
    missing = [n for n, p in found.items() if p is None]
    if missing:
        say("相邻 Skill", False, f"找不到 {', '.join(missing)}（看过 {SKILLS} 和宿主的 skills 目录）：三个目录要放在同一个 skills/ 里")
        return False
    sfx = found["video-shotcraft"] / "assets" / "scripts" / "sfx-source.py"
    say("相邻 Skill", True, "video-use、video-shotcraft 在" + ("，含 Freesound 音效选材" if sfx.is_file() else "；Shotcraft 版本较旧，没有 sfx-source.py"))
    return True


def step_key(check: bool, skip: bool, timeout: int) -> str:
    """Returns 'present', 'skipped', 'timeout' or 'refused'."""
    load_user_env()
    if os.environ.get(KEY_VAR):
        say("造物社密钥", True, f"{KEY_VAR} 已设置（不显示）")
        return "present"
    if check or skip:
        say("造物社密钥", False, f"{KEY_VAR} 未设置：生图、配音、配乐、数字人不可用；对 Agent 说“配置 API”即可补")
        return "skipped"
    print(f"  正在打开本机密钥网页，请在网页里粘贴造物社密钥并点「验证并保存」（最多等 {timeout // 60} 分钟）…", flush=True)
    code = run([str(HERE / "key_setup.py"), "--var", KEY_VAR, "--timeout", str(timeout)], timeout=timeout + 30)
    load_user_env()
    if code == 0 and os.environ.get(KEY_VAR):
        say("造物社密钥", True, "已保存并通过免费余额检查")
        return "present"
    if code == 4:
        say("造物社密钥", False, "AI 工具的沙箱不允许保存，按上面的提示在沙箱外运行 key_setup.py")
        return "refused"
    if code == 2 or code == -1:
        say("造物社密钥", False, "密钥网页超时关闭：贴好后再跑一次 first_run.py，或对 Agent 说“配置 API”")
        return "timeout"
    say("造物社密钥", False, "密钥没有保存（页面被拒绝或关闭）；对 Agent 说“配置 API”再来一次")
    return "refused"


def step_sound_config(check: bool, key: str) -> None:
    if check:
        has = CONFIG.is_file() and '"audio"' in CONFIG.read_text(encoding="utf-8")
        say("声音与生图配置", has, "backends.local.json 已有 audio 段" if has else "未写入（正式运行时 audio_cloud.py setup --yes 会写）")
        return
    code = run([str(HERE / "audio_cloud.py"), "setup", "--yes"])
    say("声音与生图配置", code == 0, "造物社默认值已写入 backends.local.json（已有的不动）" if code == 0 else "setup 失败，看上面的输出")
    if key != "present":
        say("免费体检", False, "跳过：没有密钥")
        return
    code = run([str(HERE / "audio_cloud.py"), "doctor"])
    say("免费体检", code == 0, "连通、余额、价格、音色见上" if code == 0 else "doctor 报错，按上面的提示处理")


def step_smoke(out_dir: str) -> None:
    code = run([str(HERE / "audio_cloud.py"), "setup", "--smoke", "--out", out_dir, "--confirmed"])
    say("付费试跑", code == 0, f"一句配音 + 一张图在 {out_dir}" if code == 0 else "试跑失败，看上面的输出")


def stamp() -> None:
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.is_file() else {}
    except ValueError:
        print(f"  {CONFIG} 不是合法 JSON，跳过 first_run 记录")
        return
    data["first_run"] = {"version": skill_version(), "date": date.today().isoformat(),
                         "steps": {n: ok for n, ok, _ in steps}}
    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report only, change nothing, no key page")
    ap.add_argument("--no-key", action="store_true", help="skip the key page")
    ap.add_argument("--key-timeout", type=int, default=600, help="seconds to wait on the key page (default 600)")
    ap.add_argument("--smoke", action="store_true", help="also run the paid smoke test (ask the user first)")
    ap.add_argument("--smoke-out", default="xumu-smoke", help="directory for the smoke test outputs")
    a = ap.parse_args(argv)

    print(f"序幕 {skill_version()} 首次自检{'（只看不动）' if a.check else ''}：{SKILL}", flush=True)
    if not a.check and not can_write_skill():
        print(f"这个 AI 工具的沙箱不允许写 {CONFIG.parent}，配置和首次记录都存不住，所以没有开始。\n"
              f"二选一：让 Agent 申请在沙箱外运行 first_run.py，或在系统终端（不是 AI 工具里）运行：\n"
              f"{'& ' if sys.platform == 'win32' else ''}\"{sys.executable}\" \"{Path(__file__).resolve()}\"")
        return 3
    env_ok = step_environment(a.check)
    step_neighbours()
    key = step_key(a.check, a.no_key, a.key_timeout)
    step_sound_config(a.check, key)
    if a.smoke and not a.check and key == "present":
        step_smoke(a.smoke_out)
    if not a.check:
        stamp()

    width = max(len(n) for n, _, _ in steps)
    print("\n汇总")
    for name, ok, note in steps:
        print(f"  [{'OK' if ok else '!!'}] {name.ljust(width)}  {note}")
    if not env_ok:
        return 1
    return 2 if key == "timeout" else 0


if __name__ == "__main__":
    sys.exit(main())
