from __future__ import annotations
import importlib.util
import shutil
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_document_status", ROOT / "scripts/maintenance/check_document_status.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

def fixture(tmp_path: Path) -> Path:
    for relative in ("docs/product/当前开发状态.md", "Dev_MainDev.md", "Dev_BUG_TRACKER.md", "docs/product/项目进度.md", "docs/memory/项目记忆.md"):
        target = tmp_path / relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / relative, target)
    return tmp_path

def indexed_work_item(root: Path = ROOT) -> tuple[str, str, str]:
    row = next(item for item in MODULE.parse_index(root / MODULE.INDEX_REL) if item["milestone"] != "—" and item["bug"] != "—")
    return row["milestone"], row["bug"], row["status"]

def replace_tracker_status(text: str, bug: str, replacement: str) -> tuple[str, str]:
    headings = list(MODULE.BUG_HEADING.finditer(text))
    target_index = next((index for index, match in enumerate(headings) if match.group(1) == bug), None)
    assert target_index is not None, f"missing fixture BUG section: {bug}"
    heading = headings[target_index]
    section_end = headings[target_index + 1].start() if target_index + 1 < len(headings) else len(text)
    status = MODULE.BUG_STATUS.search(text, heading.end(), section_end)
    assert status is not None, f"missing first status in fixture BUG section: {bug}"
    original = status.group(1).strip()
    mutated = text[:status.start(1)] + replacement + text[status.end(1):]
    assert mutated != text
    return mutated, original

def test_repository_document_status_is_consistent(): assert MODULE.validate(ROOT) == []

def test_duplicate_current_milestone_is_rejected(tmp_path):
    root = fixture(tmp_path); index = root / "docs/product/当前开发状态.md"; text = index.read_text(encoding="utf-8")
    milestone, _, _ = indexed_work_item(root)
    index.write_text(text.replace(MODULE.END, f"| 重复 | {milestone} | BUG-20260812-999 | 主线开发中 | 冲突 |\n" + MODULE.END), encoding="utf-8")
    assert f"当前索引重复里程碑: {milestone}" in MODULE.validate(root)

def test_duplicate_current_bug_is_rejected(tmp_path):
    root = fixture(tmp_path); index = root / "docs/product/当前开发状态.md"; text = index.read_text(encoding="utf-8")
    _, bug, _ = indexed_work_item(root)
    index.write_text(text.replace(MODULE.END, f"| 重复 | M9.999 | {bug} | 主线开发中 | 冲突 |\n" + MODULE.END), encoding="utf-8")
    assert f"当前索引重复 BUG: {bug}" in MODULE.validate(root)

def test_unknown_status_is_rejected(tmp_path):
    root = fixture(tmp_path); index = root / "docs/product/当前开发状态.md"; text = index.read_text(encoding="utf-8")
    _, _, status = indexed_work_item(root)
    index.write_text(text.replace(status, "似乎快完成", 1), encoding="utf-8")
    assert "未知当前状态: 似乎快完成" in MODULE.validate(root)

def test_missing_tracker_detail_is_rejected(tmp_path):
    root = fixture(tmp_path); index = root / "docs/product/当前开发状态.md"; text = index.read_text(encoding="utf-8")
    _, bug, _ = indexed_work_item(root)
    index.write_text(text.replace(bug, "BUG-20260812-998", 1), encoding="utf-8")
    assert "BUG 跟踪记录缺少当前条目: BUG-20260812-998" in MODULE.validate(root)

def test_active_tracker_bug_missing_from_index_is_rejected(tmp_path):
    root = fixture(tmp_path); tracker = root / "Dev_BUG_TRACKER.md"
    tracker.write_text(tracker.read_text(encoding="utf-8") + "\n### BUG-20260812-997：新活动项\n\n- 状态：待测试\n", encoding="utf-8")
    assert any("活动条目未进入当前索引: BUG-20260812-997" in error for error in MODULE.validate(root))

def test_missing_local_markdown_link_is_rejected(tmp_path):
    root = fixture(tmp_path); progress = root / "docs/product/项目进度.md"
    progress.write_text(progress.read_text(encoding="utf-8") + "\n[缺失文件](不存在.md)\n", encoding="utf-8")
    assert any("本地Markdown链接不存在: 不存在.md" in error for error in MODULE.validate(root))

def test_conflicting_current_claim_requires_history_marker(tmp_path):
    root = fixture(tmp_path); progress = root / "docs/product/项目进度.md"
    milestone, _, _ = indexed_work_item(root)
    progress.write_text(progress.read_text(encoding="utf-8") + f"\n- {milestone}（最终稽查通过，已完成）：错误现行声明。\n", encoding="utf-8")
    assert any(f"现行状态与索引冲突 {milestone}" in error for error in MODULE.validate(root))

@pytest.mark.parametrize("relative", ["Dev_MainDev.md", "docs/product/项目进度.md", "docs/memory/项目记忆.md"])
def test_secondary_bug_claim_is_compared_with_index(tmp_path, relative):
    root = fixture(tmp_path); document = root / relative
    _, bug, _ = indexed_work_item(root); shorthand = f"BUG{bug.rsplit('-', 1)[-1]}"
    document.write_text(document.read_text(encoding="utf-8") + f"\n- {shorthand}（最终稽查通过，已关闭）：错误现行声明。\n", encoding="utf-8")
    errors = MODULE.validate(root)
    assert any(f"现行状态与索引冲突 {bug}" in error for error in errors)

@pytest.mark.parametrize("relative", ["Dev_MainDev.md", "docs/product/项目进度.md", "docs/memory/项目记忆.md"])
def test_secondary_milestone_claim_is_compared_with_index(tmp_path, relative):
    root = fixture(tmp_path); document = root / relative
    milestone, _, _ = indexed_work_item(root)
    document.write_text(document.read_text(encoding="utf-8") + f"\n- {milestone}（最终稽查通过，已完成）：错误现行声明。\n", encoding="utf-8")
    errors = MODULE.validate(root)
    assert any(f"现行状态与索引冲突 {milestone}" in error for error in errors)

def test_explicit_history_claim_is_exempt(tmp_path):
    root = fixture(tmp_path); progress = root / "docs/product/项目进度.md"
    milestone, _, _ = indexed_work_item(root)
    progress.write_text(progress.read_text(encoding="utf-8") + f"\n- {milestone}（历史记录，已被后续状态覆盖）：待测试。\n", encoding="utf-8")
    assert MODULE.validate(root) == []

def test_tracker_status_conflict_is_rejected_without_binding_current_lifecycle(tmp_path):
    root = fixture(tmp_path); tracker = root / "Dev_BUG_TRACKER.md"; text = tracker.read_text(encoding="utf-8")
    _, bug, _ = indexed_work_item(root); current = MODULE.tracker_statuses(text)[bug]
    replacement = "待测试" if MODULE.status_family(current) == "closed" else "已关闭"
    mutated, original = replace_tracker_status(text, bug, replacement)
    assert MODULE.status_family(original) != MODULE.status_family(replacement)
    tracker.write_text(mutated, encoding="utf-8")
    assert any(f"当前状态冲突 {bug}" in error for error in MODULE.validate(root))

@pytest.mark.parametrize("lifecycle", ["待测试", "软件测试通过，待稽查", "已关闭（最终稽查通过）"])
def test_tracker_fixture_status_replacement_handles_any_lifecycle(lifecycle):
    source = f"# Tracker\n\n### BUG-20260811-044：任意标题\n\n- 状态：{lifecycle}\n- 证据：保留。\n\n### BUG-20260811-045：下一条\n\n- 状态：待测试\n"
    replacement = "已关闭" if MODULE.status_family(lifecycle) != "closed" else "待测试"
    mutated, original = replace_tracker_status(source, "BUG-20260811-044", replacement)
    assert original == lifecycle
    statuses = MODULE.tracker_statuses(mutated)
    assert statuses["BUG-20260811-044"] == replacement
    assert statuses["BUG-20260811-045"] == "待测试"

def test_second_authority_claim_is_rejected(tmp_path):
    root = fixture(tmp_path); progress = root / "docs/product/项目进度.md"; progress.write_text("本文件是唯一当前状态事实源。\n", encoding="utf-8")
    assert any("声明了第二个当前状态事实源" in error for error in MODULE.validate(root))
