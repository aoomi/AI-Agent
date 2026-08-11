import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NODE = Path("/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/custom_nodes/comfyui-minimax-h3-context-ir-agent")


def test_h3_context_ir_node_and_local_model_configuration_exist():
    assert (NODE / "nodes.py").is_file()
    assert (NODE / "LICENSE").read_text(encoding="utf-8").startswith("MIT License")
    assert (NODE / "config.toml").is_file()
    config = (NODE / "config.toml").read_text(encoding="utf-8")
    assert "http://127.0.0.1:11434/v1" in config
    assert "qwen3-vl-h3-context-ir:latest" in config
    assert (ROOT / "models/text/qwen3-vl-h3-context-ir.Modelfile").is_file()


def test_comfy_startup_whitelists_context_ir_node():
    script = (ROOT / "scripts/start_comfyui_8194.sh").read_text(encoding="utf-8")
    assert "comfyui-minimax-h3-context-ir-agent" in script
    assert "--disable-all-custom-nodes" in script
    assert 'export OPENAI_AGENTS_DISABLE_TRACING="1"' in script
    plist = Path("/Users/aoo/Library/LaunchAgents/com.aiagent.comfyui8194.plist").read_text(encoding="utf-8")
    assert str(ROOT / "scripts/start_comfyui_8194.sh") in plist
    assert "OPENAI_AGENTS_DISABLE_TRACING" in plist


def test_authoritative_docs_record_ref2va_auto_wiring_and_remaining_scope():
    docs = [
        ROOT / "docs/specs/H3 Context IR提示词优化节点.md",
        ROOT / "docs/specs/视频模型选择规则.md",
        ROOT / "docs/specs/短剧从剧本到成片生产规范.md",
        ROOT / "docs/specs/短剧3D资产生产规范.md",
        ROOT / "plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md",
    ]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "Context IR" in text or "Context-IR" in text
        assert "optimized_prompt" in text
        assert "H3" in text


def test_context_ir_supply_chain_is_reproducibly_locked():
    lock = ROOT / "deploy/comfyui/h3-context-ir-requirements.lock"
    manifest = json.loads((ROOT / "deploy/comfyui/h3-context-ir-supply-chain.json").read_text(encoding="utf-8"))
    lock_text = lock.read_text(encoding="utf-8")
    assert ">=" not in lock_text
    assert "--hash=sha256:" in lock_text
    assert hashlib.sha256(lock.read_bytes()).hexdigest() == manifest["python_dependencies"]["lockfile_sha256"]
    assert manifest["source"]["commit"] == "771cb3cb01af9543b4f424518bb19b7fa0cf31d8"
    assert manifest["source"]["license"] == "MIT"
    patch = ROOT / manifest["source"]["local_compatibility_patch"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == manifest["source"]["local_compatibility_patch_sha256"]
    patch_text = patch.read_text(encoding="utf-8")
    assert 'resolved_model == "qwen3-vl-h3-context-ir:latest"' in patch_text
    assert '@function_tool(name_override="h3-prompt-writing")' in patch_text
    assert "from agents import function_tool" in patch_text
    assert '_make_h3_material_tool(skill_text, guide_text)' in patch_text


def test_context_ir_install_script_and_model_use_fixed_digests():
    script = (ROOT / "scripts/install_h3_context_ir_agent.sh").read_text(encoding="utf-8")
    modelfile = (ROOT / "models/text/qwen3-vl-h3-context-ir.Modelfile").read_text(encoding="utf-8")
    digest = "4c7fee11ee9e3b139575eedb4cd68521729ece7fc0a356150a6672e773c607ea"
    assert "--require-hashes" in script
    assert "771cb3cb01af9543b4f424518bb19b7fa0cf31d8" in script
    assert digest in script
    assert "LOCAL_PATCH_SHA" in script
    assert "APPLIED_DIFF_SHA" in script
    assert 'node.name == "_make_h3_material_tool"' in script
    assert 'keyword.value.value == "h3-prompt-writing"' in script
    assert f"FROM /Users/aoo/.ollama/models/blobs/sha256-{digest}" in modelfile
    assert "FROM qwen3-vl:32b" not in modelfile
    assert "PARAMETER num_predict 2048" in modelfile
    assert "RENDERER qwen3-vl-instruct" in modelfile
    assert "PARSER qwen3-vl-instruct" in modelfile


def test_context_ir_sbom_and_security_reports_are_machine_readable():
    sbom = json.loads((ROOT / "docs/security/h3-context-ir-sbom.cdx.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "docs/security/h3-context-ir-pip-audit.json").read_text(encoding="utf-8"))
    bandit = json.loads((ROOT / "docs/security/h3-context-ir-bandit.json").read_text(encoding="utf-8"))
    assert len(sbom["components"]) == 42
    assert sum(len(item.get("vulns", [])) for item in audit["dependencies"]) == 0
    totals = bandit["metrics"]["_totals"]
    assert totals["SEVERITY.HIGH"] == 0
    assert totals["SEVERITY.MEDIUM"] == 0
    manifest = json.loads((ROOT / "deploy/comfyui/h3-context-ir-supply-chain.json").read_text(encoding="utf-8"))
    disposition = manifest["security_evidence"]["static_low_disposition"]
    assert "nodes.py:252" in disposition
    assert "set_tracing_disabled(True)" in disposition
    assert "image cleanup" not in disposition
    smoke = json.loads((ROOT / "docs/security/h3-context-ir-runtime-smoke.json").read_text(encoding="utf-8"))
    assert smoke["status"] == "success" and smoke["completed"] is True
    assert all(smoke["outputs_non_empty"].values())
    assert "integrated_multimodal_description" in smoke["optimized_prompt"]
