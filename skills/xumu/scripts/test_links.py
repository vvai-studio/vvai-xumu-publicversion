"""Dead-link check for the skill's Markdown: every relative link in SKILL.md, agents/ and references/ must point to an
existing file, and an anchor (``#...``) must match a heading in the target file, slugged the way GitHub does it.

Run with the other tests:  python -m pytest skills/xumu/scripts/test_links.py
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
MD_FILES = [SKILL / "SKILL.md", *sorted((SKILL / "agents").glob("*.md")), *sorted((SKILL / "references").glob("*.md"))]

LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def slug(heading: str) -> str:
    """GitHub-style heading id: lowercase, drop punctuation, spaces -> hyphens, keep CJK."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)  # inline code keeps its text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links keep their label
    text = text.lower()
    out = []
    for ch in text:
        if ch in " -":
            out.append("-" if ch == " " else ch)
        elif ch == "_" or unicodedata.category(ch)[0] in ("L", "N"):
            out.append(ch)
    return "".join(out)


def headings(path: Path) -> set[str]:
    body = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    return {slug(m.group(2)) for m in HEADING_RE.finditer(body)}


def links(path: Path) -> list[str]:
    body = FENCE_RE.sub("", path.read_text(encoding="utf-8"))
    return [m.group(1) for m in LINK_RE.finditer(body)]


def is_relative(target: str) -> bool:
    return not re.match(r"^[a-z][a-z0-9+.-]*:", target) and not target.startswith("//")


def check(path: Path) -> list[str]:
    problems = []
    own_headings = None
    for raw in links(path):
        if not is_relative(raw):
            continue
        file_part, _, anchor = raw.partition("#")
        if file_part:
            target = (path.parent / file_part).resolve()
            if not target.exists():
                problems.append(f"{path.relative_to(SKILL)}: missing file {raw}")
                continue
            if anchor and target.suffix == ".md":
                if anchor not in headings(target):
                    problems.append(f"{path.relative_to(SKILL)}: missing anchor {raw}")
        elif anchor:
            if own_headings is None:
                own_headings = headings(path)
            if anchor not in own_headings:
                problems.append(f"{path.relative_to(SKILL)}: missing anchor {raw}")
    return problems


def test_slug_matches_github_style():
    assert slug("1. 三层档案") == "1-三层档案"
    assert slug("交付规格门禁（硬性）") == "交付规格门禁硬性"
    assert slug("造物社 API（配置一次，图片、配音、配乐共用）") == "造物社-api配置一次图片配音配乐共用"
    assert slug("HyperFrames 按需接入") == "hyperframes-按需接入"


def test_identity_and_role_files_exist():
    for name in ("system.md", "screenwriter.md", "director.md", "editor.md"):
        assert (SKILL / "agents" / name).is_file(), name


def test_no_dead_links():
    problems = [p for path in MD_FILES for p in check(path)]
    assert not problems, "\n".join(problems)


def test_skill_md_stays_slim():
    size = (SKILL / "SKILL.md").stat().st_size
    assert size < 12_000, f"SKILL.md is {size} bytes; move detail into references/ (workflow.md, commands.md)"


if __name__ == "__main__":
    found = [p for path in MD_FILES for p in check(path)]
    print("\n".join(found) if found else f"ok: {len(MD_FILES)} files, no dead links")
    raise SystemExit(1 if found else 0)
