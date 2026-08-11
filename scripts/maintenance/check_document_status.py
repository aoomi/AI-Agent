#!/usr/bin/env python3
"""Validate the single current-development-status documentation source."""
from __future__ import annotations
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_REL = Path("docs/product/当前开发状态.md")
TRACKER_REL = Path("Dev_BUG_TRACKER.md")
SECONDARY = (Path("Dev_MainDev.md"), TRACKER_REL, Path("docs/product/项目进度.md"), Path("docs/memory/项目记忆.md"))
START = "<!-- CURRENT_STATUS_INDEX:START -->"
END = "<!-- CURRENT_STATUS_INDEX:END -->"
ALLOWED_STATES = {"主线开发中", "开发完成，待独立软件测试", "软件测试通过，待只读稽查", "排队，未分析", "阻塞"}
BUG_HEADING = re.compile(r"^###\s+(BUG-[0-9-]+)[：:]", re.MULTILINE)
BUG_STATUS = re.compile(r"^-\s*状态[：:]\s*(.+?)\s*$", re.MULTILINE)
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
STATUS_CLAIM_LINE = re.compile(
    r"^(?:###\s+|-\s+)(?P<ids>(?:M\d+\.\d+|BUG(?:-\d{8}-)?\d{3})"
    r"(?:\s*/\s*(?:M\d+\.\d+|BUG(?:-\d{8}-)?\d{3}))?)(?P<rest>[（:].*)$",
    re.MULTILINE,
)
CLAIM_ID = re.compile(r"M\d+\.\d+|BUG(?:-\d{8}-)?\d{3}")
HISTORY_MARKERS = ("历史", "已被", "覆盖", "最终闭环")

def status_family(value: str) -> str:
    value = value.strip().rstrip("。")
    if "排队" in value or "待处理" in value: return "queued"
    if "待独立软件测试" in value or value == "待测试": return "testing"
    if "待只读稽查" in value or "待稽查" in value: return "inspection"
    if "开发" in value or "修复中" in value: return "development"
    if "阻塞" in value: return "blocked"
    if "关闭" in value or ("已修复" in value and "待" not in value): return "closed"
    return value

def claim_family(line: str) -> str | None:
    if any(marker in line for marker in HISTORY_MARKERS): return None
    if "最终稽查通过" in line or "已关闭" in line or "已完成" in line: return "closed"
    if "待只读稽查" in line or "待重新稽查" in line or "待稽查" in line: return "inspection"
    if "待独立软件复测" in line or "待独立软件测试" in line or "待软件测试" in line: return "testing"
    if "整改中" in line or "主线开发中" in line: return "development"
    return None

def normalize_claim_id(identifier: str, indexed_bugs: set[str]) -> str:
    if not identifier.startswith("BUG") or identifier.startswith("BUG-"):
        return identifier
    suffix = identifier.removeprefix("BUG")
    matches = [bug for bug in indexed_bugs if bug.endswith(f"-{suffix}")]
    return matches[0] if len(matches) == 1 else identifier

def parse_index(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise ValueError("当前状态索引必须且只能包含一组边界标记")
    body = text.split(START, 1)[1].split(END, 1)[0]
    rows = []
    for line in body.splitlines():
        if not line.startswith("|"): continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in {"工作流", "---"}: continue
        rows.append(dict(zip(("workstream", "milestone", "bug", "status", "note"), cells)))
    if not rows: raise ValueError("当前状态索引没有数据行")
    return rows

def tracker_statuses(text: str) -> dict[str, str]:
    matches = list(BUG_HEADING.finditer(text)); result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        status = BUG_STATUS.search(text, match.end(), end)
        if status: result.setdefault(match.group(1), status.group(1).strip())
    return result

def validate(root: Path = ROOT) -> list[str]:
    errors = []
    try: rows = parse_index(root / INDEX_REL)
    except (OSError, ValueError) as exc: return [str(exc)]
    milestones, bugs = set(), set()
    for row in rows:
        milestone, bug, state = row["milestone"], row["bug"], row["status"]
        if state not in ALLOWED_STATES: errors.append(f"未知当前状态: {state}")
        if milestone != "—":
            if not re.fullmatch(r"M\d+\.\d+", milestone): errors.append(f"非法里程碑编号: {milestone}")
            elif milestone in milestones: errors.append(f"当前索引重复里程碑: {milestone}")
            milestones.add(milestone)
        if bug != "—":
            if not re.fullmatch(r"BUG-\d{8}-\d{3}", bug): errors.append(f"非法 BUG 编号: {bug}")
            elif bug in bugs: errors.append(f"当前索引重复 BUG: {bug}")
            bugs.add(bug)
    tracker = tracker_statuses((root / TRACKER_REL).read_text(encoding="utf-8"))
    indexed_bugs = {row["bug"] for row in rows if row["bug"] != "—"}
    indexed_states = {}
    for row in rows:
        if row["milestone"] != "—": indexed_states[row["milestone"]] = status_family(row["status"])
        if row["bug"] != "—": indexed_states[row["bug"]] = status_family(row["status"])
    for row in rows:
        bug = row["bug"]
        if bug == "—": continue
        if bug not in tracker: errors.append(f"BUG 跟踪记录缺少当前条目: {bug}")
        elif status_family(tracker[bug]) != status_family(row["status"]):
            errors.append(f"当前状态冲突 {bug}: 索引={row['status']}，BUG跟踪={tracker[bug]}")
    active_families = {"queued", "development", "testing", "inspection", "blocked"}
    for bug, state in tracker.items():
        if status_family(state) in active_families and bug not in indexed_bugs:
            errors.append(f"BUG 跟踪记录活动条目未进入当前索引: {bug} ({state})")

    claims: dict[str, list[tuple[str, Path, int, str]]] = defaultdict(list)
    for relative in SECONDARY:
        text = (root / relative).read_text(encoding="utf-8")
        for match in STATUS_CLAIM_LINE.finditer(text):
            line = match.group(0)
            family = claim_family(line)
            if family:
                line_number = text.count("\n", 0, match.start()) + 1
                for raw_identifier in CLAIM_ID.findall(match.group("ids")):
                    identifier = normalize_claim_id(raw_identifier, indexed_bugs)
                    claims[identifier].append((family, relative, line_number, line))
                    expected = indexed_states.get(identifier)
                    if expected and expected != family:
                        errors.append(
                            f"现行状态与索引冲突 {identifier}: {relative}:{line_number}={family}，索引={expected}"
                        )
        for number, line in enumerate(text.splitlines(), 1):
            for target in LOCAL_LINK.findall(line):
                clean = target.strip().split("#", 1)[0]
                if not clean or clean.startswith(("#", "http://", "https://", "mailto:")): continue
                if not ((root / relative).parent / clean).resolve().exists():
                    errors.append(f"{relative}:{number} 本地Markdown链接不存在: {target}")
    for identifier, records in claims.items():
        families = {record[0] for record in records}
        if len(families) > 1:
            locations = ", ".join(f"{path}:{line}={family}" for family, path, line, _ in records)
            errors.append(f"同编号存在多个现行状态 {identifier}: {locations}；旧记录须显式标记历史/已被覆盖")
    authority = re.compile(r"本文件.{0,16}唯一.{0,8}(?:当前状态|事实源)")
    for relative in SECONDARY:
        for number, line in enumerate((root / relative).read_text(encoding="utf-8").splitlines(), 1):
            if authority.search(line) and "当前开发状态.md" not in line and "业务状态" not in line:
                errors.append(f"{relative}:{number} 声明了第二个当前状态事实源")
    return errors

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=ROOT); args = parser.parse_args()
    errors = validate(args.root.resolve())
    if errors:
        print("document status check failed:", file=sys.stderr)
        for error in errors: print(f"- {error}", file=sys.stderr)
        return 1
    print("document status check passed"); return 0

if __name__ == "__main__": raise SystemExit(main())
