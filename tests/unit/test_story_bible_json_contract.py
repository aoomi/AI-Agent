from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from short_drama_workflows.story_bible import StoryBible, StoryBibleError


def test_story_bible_rejects_non_path_database_before_filesystem_side_effects(tmp_path):
    target = tmp_path / "story.sqlite"
    with pytest.raises(StoryBibleError, match="must be a Path"):
        StoryBible(str(target))
    assert not target.exists()


@pytest.mark.parametrize("invalid", [float("nan"), object()])
def test_story_bible_rejects_non_standard_json_without_persisting(invalid):
    with TemporaryDirectory() as temporary:
        bible = StoryBible(Path(temporary) / "story.sqlite")
        identity = {"tenant_id": "t", "user_id": "u", "project_id": "p"}

        with pytest.raises(StoryBibleError, match="standard JSON"):
            bible.update(
                identity,
                "outline",
                {
                    "episodes": [
                        {
                            "episode": 1,
                            "title": "开局",
                            "core_event": "女主进入宗门并遭到质疑",
                            "metadata": invalid,
                        }
                    ]
                },
            )

        assert bible.read(identity) == {"episodes": [], "entities": [], "violations": []}


def test_story_bible_rejects_corrupt_persisted_entity_attributes():
    with TemporaryDirectory() as temporary:
        bible=StoryBible(Path(temporary)/"story.sqlite")
        identity={"tenant_id":"t","user_id":"u","project_id":"p"}
        bible.update(identity,"outline",{"characters":[{"name":"苏璃"}]})
        with bible._connection() as connection:connection.execute("UPDATE story_entities SET attributes_json='NaN'")
        with pytest.raises(StoryBibleError,match="attributes are invalid"):bible.read(identity)


def test_story_bible_rejects_pseudo_scope_stage_and_episode_contracts():
    with TemporaryDirectory() as temporary:
        bible=StoryBible(Path(temporary)/"story.sqlite")
        identity={"tenant_id":"t","user_id":"u","project_id":"p"}
        operations=(
            lambda:bible.read({"tenant_id":1,"user_id":"u","project_id":"p"}),
            lambda:bible.update(identity,"unknown",{}),
            lambda:bible.update(identity,"outline",{"episodes":{}}),
            lambda:bible.update(identity,"outline",{"episodes":[{"episode":True}]}),
            lambda:bible.update(identity,"outline",{"episodes":[object()]}),
        )
        for operation in operations:
            with pytest.raises(StoryBibleError):operation()
        assert bible.read(identity)=={"episodes":[],"entities":[],"violations":[]}
