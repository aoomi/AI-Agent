from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE = (ROOT / "docs/technical/系统架构设计.md").read_text(encoding="utf-8")


def test_architecture_v22_records_current_production_kernel_facts():
    for token in (
        "版本：2.2",
        "M1—M4 已完成",
        "M5—M7 已完成",
        "LangGraph生产内核",
        "11节点状态契约",
        "全链路成片验收（M9.198）进行中",
        "通用Skill机器人、多租户商业化",
    ):
        assert token in ARCHITECTURE
    assert "LangGraph 编排适配属于 M7.5，当前尚未完成" not in ARCHITECTURE


def test_architecture_v22_contains_authority_isolation_and_runtime_gates():
    for token in (
        "生产权威台账（ProductionLedger）",
        "generation + revision",
        "content_fingerprint + audit_batch_id",
        "project_id + session_id + epoch",
        "waiting_memory",
        "RecordExporter",
        "inflight",
        "启动恢复器、LangGraph阶段映射、项目存储投影和前端继续入口",
    ):
        assert token in ARCHITECTURE
