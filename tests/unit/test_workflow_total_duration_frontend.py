from pathlib import Path


APP = Path(__file__).resolve().parents[2] / "plugins/builtin/short_drama/frontend/App.vue"


def test_workflow_header_displays_cumulative_generation_time() -> None:
    source = APP.read_text(encoding="utf-8")

    assert "elapsed_seconds:current.elapsed_seconds, running:true" in source
    assert "elapsed_seconds:current.elapsed_seconds + Math.max" in source
    assert "return timing.elapsed_seconds + (timing.running" in source
    assert ':elapsed-seconds="workflowElapsedSeconds"' in source
