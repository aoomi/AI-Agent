import pytest

from ai_agent_events import EventBus
from ai_agent_queue import InMemoryTaskQueue
from short_drama_workflows.langgraph_pipeline import ShortDramaLangGraphPipeline
from short_drama_workflows.pipeline import NODES, ShortDramaPipeline, ShortDramaPipelineError


def _runners():
    return {stage: lambda _artifacts: None for stage in NODES}


def test_legacy_pipeline_rejects_non_path_root_before_filesystem_side_effects(tmp_path):
    target = tmp_path / "legacy"
    with pytest.raises(ShortDramaPipelineError, match="root must be a Path"):
        ShortDramaPipeline(str(target), InMemoryTaskQueue(), EventBus(), _runners())
    assert not target.exists()


def test_langgraph_facade_rejects_non_path_root_before_filesystem_side_effects(tmp_path):
    target = tmp_path / "langgraph"
    with pytest.raises(ShortDramaPipelineError, match="root must be a Path"):
        ShortDramaLangGraphPipeline(str(target), _runners())
    assert not target.exists()
