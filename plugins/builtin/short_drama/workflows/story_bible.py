"""Transactional story facts used to prevent cross-episode contradictions."""

from __future__ import annotations

from datetime import UTC, datetime
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from threading import RLock
from typing import Any, Mapping


class StoryBibleError(ValueError):
    pass


def _normalized(value: object) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(value or "")).lower()


def _first(item: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    return next((str(item.get(key) or "").strip() for key in keys if str(item.get(key) or "").strip()), "")


class StoryBible:
    def __init__(self, database: Path) -> None:
        if not isinstance(database, Path):
            raise StoryBibleError("story bible database must be a Path")
        self.database = database.resolve(); self.database.parent.mkdir(parents=True, exist_ok=True); self._lock = RLock()
        with self._connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS story_episode_facts (
                    tenant_id TEXT NOT NULL,user_id TEXT NOT NULL,project_id TEXT NOT NULL,episode INTEGER NOT NULL,
                    title TEXT NOT NULL,event TEXT NOT NULL,phase TEXT NOT NULL,ability_stage TEXT NOT NULL,
                    irreversible_change TEXT NOT NULL,hook TEXT NOT NULL,source_stage TEXT NOT NULL,fingerprint TEXT NOT NULL,updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,user_id,project_id,episode)
                );
                CREATE TABLE IF NOT EXISTS story_entities (
                    tenant_id TEXT NOT NULL,user_id TEXT NOT NULL,project_id TEXT NOT NULL,entity_type TEXT NOT NULL,entity_key TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,attributes_json TEXT NOT NULL,source_stage TEXT NOT NULL,updated_at TEXT NOT NULL,
                    PRIMARY KEY(tenant_id,user_id,project_id,entity_type,entity_key)
                );
            """)

    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _identity(identity: Mapping[str, Any]) -> tuple[str, str, str]:
        values = tuple(str(identity.get(key, "")).strip() for key in ("tenant_id", "user_id", "project_id"))
        if not all(values): raise StoryBibleError("tenant_id, user_id and project_id are required")
        return values  # type: ignore[return-value]

    def update(self, identity: Mapping[str, Any], stage: str, data: Mapping[str, Any]) -> dict[str, Any]:
        scope = self._identity(identity)
        try:
            json.dumps(dict(data), ensure_ascii=False, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise StoryBibleError("story bible data must be standard JSON") from error
        episodes = self._episodes(stage, data); violations = self.validate(episodes)
        if violations: raise StoryBibleError("；".join(violations))
        with self._lock, self._connection() as connection:
            existing_numbers = {int(row["episode"]) for row in connection.execute("SELECT episode FROM story_episode_facts WHERE tenant_id=? AND user_id=? AND project_id=?", scope)}
            incoming_numbers = {int(item.get("episode") or 0) for item in episodes}
            if stage in {"script", "storyboard"} and existing_numbers and not incoming_numbers.issubset(existing_numbers):
                raise StoryBibleError("剧本或分镜包含未在已确认大纲登记的集数")
            for item in episodes if stage == "outline" else []:
                episode = int(item.get("episode") or 0)
                if episode < 1: continue
                title = _first(item, ("title", "episode_title")); event = _first(item, ("core_event", "event", "plot", "summary", "content"))
                values = (*scope, episode, title, event, _first(item, ("story_stage", "phase", "story_phase")), _first(item, ("ability_progression", "ability_stage", "power_stage")),
                          _first(item, ("irreversible_change", "change")), _first(item, ("hook", "ending_hook", "cliffhanger")), stage,
                          hashlib.sha256(json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest(), datetime.now(UTC).isoformat())
                connection.execute("""
                    INSERT INTO story_episode_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(tenant_id,user_id,project_id,episode) DO UPDATE SET title=excluded.title,event=excluded.event,phase=excluded.phase,
                    ability_stage=excluded.ability_stage,irreversible_change=excluded.irreversible_change,hook=excluded.hook,
                    source_stage=excluded.source_stage,fingerprint=excluded.fingerprint,updated_at=excluded.updated_at
                """, values)
            self._update_entities(connection, scope, stage, data)
            connection.commit()
        return self.read(identity)

    @staticmethod
    def _episodes(stage: str, data: Mapping[str, Any]) -> list[dict[str, Any]]:
        candidates = data.get("episodes") if stage == "outline" else data.get("scripts") if stage == "script" else data.get("shots") if stage == "storyboard" else []
        items = [dict(item) for item in candidates] if isinstance(candidates, list) else []
        if stage == "storyboard":
            # A storyboard contains many shots for the same episode.  The story
            # bible validates episode identity, not shot cardinality.
            return [{"episode": number} for number in sorted({int(item.get("episode") or 0) for item in items if int(item.get("episode") or 0) > 0})]
        return items

    @staticmethod
    def validate(episodes: list[Mapping[str, Any]]) -> list[str]:
        violations: list[str] = []; titles: dict[str, int] = {}; events: dict[str, int] = {}; seen_numbers: set[int] = set()
        for item in episodes:
            number = int(item.get("episode") or 0)
            if number < 1: violations.append("分集编号必须为正整数"); continue
            if number in seen_numbers: violations.append(f"第{number}集重复")
            seen_numbers.add(number)
            title = _normalized(_first(item, ("title", "episode_title")))
            event = _normalized(_first(item, ("core_event", "event", "plot", "summary")))
            similar_title = next(((value, prior) for value, prior in titles.items() if title and SequenceMatcher(None, title, value).ratio() >= .72), None)
            if similar_title: violations.append(f"第{similar_title[1]}集与第{number}集标题重复或高度同质")
            elif title: titles[title] = number
            similar_event = next(((value, prior) for value, prior in events.items() if event and len(event) >= 8 and SequenceMatcher(None, event, value).ratio() >= .58), None)
            if similar_event: violations.append(f"第{similar_event[1]}集与第{number}集核心事件重复或高度重叠")
            elif event: events[event] = number
        if seen_numbers and seen_numbers != set(range(1, max(seen_numbers) + 1)): violations.append("分集编号不连续")
        return violations

    @staticmethod
    def _update_entities(connection: sqlite3.Connection, scope: tuple[str, str, str], stage: str, data: Mapping[str, Any]) -> None:
        plan = data.get("plan") if isinstance(data.get("plan"), Mapping) else {}
        groups = (("character", data.get("characters") or plan.get("characters")), ("scene", data.get("scenes") or plan.get("scenes")), ("prop", data.get("props") or plan.get("props")))
        known_names: list[tuple[str, str]] = [(str(row["entity_key"]), str(row["canonical_name"])) for row in connection.execute("SELECT entity_key,canonical_name FROM story_entities WHERE tenant_id=? AND user_id=? AND project_id=? AND entity_type='character'", scope)]
        for entity_type, values in groups:
            if not isinstance(values, list): continue
            for item in values:
                if not isinstance(item, Mapping): continue
                name = str(item.get("name") or "").strip(); key = _normalized(name)
                if not key: continue
                if entity_type == "character":
                    collision = next((canonical for prior_key, canonical in known_names if prior_key != key and (SequenceMatcher(None, key, prior_key).ratio() >= .66 or (len(key) == 2 and len(prior_key) == 2 and key[-1] == prior_key[-1]))), "")
                    if collision: raise StoryBibleError(f"角色名{name}与{collision}过于相似")
                    known_names.append((key, name))
                connection.execute("""
                    INSERT INTO story_entities VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(tenant_id,user_id,project_id,entity_type,entity_key) DO UPDATE SET canonical_name=excluded.canonical_name,
                    attributes_json=excluded.attributes_json,source_stage=excluded.source_stage,updated_at=excluded.updated_at
                """, (*scope, entity_type, key, name, json.dumps(dict(item), ensure_ascii=False, sort_keys=True, allow_nan=False), stage, datetime.now(UTC).isoformat()))

    def read(self, identity: Mapping[str, Any]) -> dict[str, Any]:
        scope = self._identity(identity)
        with self._lock, self._connection() as connection:
            episodes = [dict(row) for row in connection.execute("SELECT * FROM story_episode_facts WHERE tenant_id=? AND user_id=? AND project_id=? ORDER BY episode", scope)]
            entities = []
            for row in connection.execute("SELECT * FROM story_entities WHERE tenant_id=? AND user_id=? AND project_id=? ORDER BY entity_type,entity_key", scope):
                try:attributes=json.loads(row["attributes_json"],parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
                except (json.JSONDecodeError,ValueError,TypeError) as error:raise StoryBibleError("story entity attributes are invalid") from error
                if not isinstance(attributes,dict):raise StoryBibleError("story entity attributes are invalid")
                entities.append({**dict(row),"attributes":attributes})
        for item in entities: item.pop("attributes_json", None)
        return {"episodes":episodes, "entities":entities, "violations":self.validate(episodes)}
